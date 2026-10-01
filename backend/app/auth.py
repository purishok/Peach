import uuid
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import SessionDep
from app.models import User

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5)


def _verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise jwt.InvalidTokenError("Invalid signing algorithm or key ID")
    if settings.cognito_jwks:
        try:
            keys = jwt.PyJWKSet.from_json(settings.cognito_jwks)
        except (ValueError, jwt.PyJWTError) as exc:
            raise HTTPException(503, "Authentication keys are not configured correctly") from exc
        key = next((key for key in keys.keys if key.key_id == header["kid"]), None)
        if key is None:
            raise jwt.InvalidTokenError("Unknown signing key")
    else:
        key = _jwks_client(settings.cognito_issuer).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        audience=settings.cognito_client_id,
        issuer=settings.cognito_issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub", "token_use"]},
    )
    if claims["token_use"] != "id" or not claims["sub"] or len(claims["sub"]) > 64:
        raise jwt.InvalidTokenError("Invalid identity claims")
    for field, limit in (("email", 320), ("name", 200)):
        value = claims.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise jwt.InvalidTokenError("Invalid profile claims")
    return claims


async def current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    settings = get_settings()
    if not settings.auth_configured:
        if settings.app_env == "development" and settings.dev_auth_enabled:
            if credentials is None:
                raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
            try:
                claims = jwt.decode(
                    credentials.credentials,
                    settings.dev_auth_secret,
                    algorithms=["HS256"],
                    issuer="peach-local-dev",
                    audience="peach-local-api",
                    options={"require": ["exp", "iat", "iss", "aud", "sub", "token_use"]},
                )
                if claims["token_use"] != "dev":
                    raise jwt.InvalidTokenError("Wrong token type")
                user_id = uuid.UUID(claims["sub"])
            except (jwt.PyJWTError, ValueError) as exc:
                raise HTTPException(
                    401, "Invalid local session", headers={"WWW-Authenticate": "Bearer"}
                ) from exc
            user = await session.scalar(
                select(User).where(User.id == user_id, User.password_hash.is_not(None))
            )
            if user is not None:
                return user
            raise HTTPException(401, "Local account not found")
        raise HTTPException(503, "Authentication is not configured")
    unauthorized = HTTPException(
        401, "Invalid or missing credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = await run_in_threadpool(_verify_token, credentials.credentials)
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Authentication keys are unavailable") from exc
    except jwt.PyJWTError as exc:
        raise unauthorized from exc

    # Concurrent first requests must create a single identity, never duplicate users.
    await session.execute(
        insert(User)
        .values(cognito_sub=claims["sub"], email=claims.get("email"), name=claims.get("name"))
        .on_conflict_do_nothing(index_elements=[User.cognito_sub])
    )
    user = await session.scalar(select(User).where(User.cognito_sub == claims["sub"]))
    if user is None:
        raise HTTPException(503, "User identity is unavailable")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
