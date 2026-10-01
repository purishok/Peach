import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import SessionDep
from app.models import User
from app.schemas.local_auth import AccountCredentials, LocalAccount, LocalAuthResponse, LocalSignUp

router = APIRouter(prefix="/auth/local", tags=["local auth"])
_SCRYPT_N = 1 << 14


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=8, p=1)
    return f"scrypt${_SCRYPT_N}$8$1${salt.hex()}${digest.hex()}"


def _password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except ValueError, TypeError:
        return False


def _response(user: User) -> LocalAuthResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "iss": "peach-local-dev",
            "aud": "peach-local-api",
            "iat": now,
            "exp": now + timedelta(hours=12),
            "token_use": "dev",
        },
        settings.dev_auth_secret,
        algorithm="HS256",
    )
    return LocalAuthResponse(
        access_token=token,
        user=LocalAccount(email=user.email or "", name=user.name or ""),
    )


async def _local_account_for_email(session: SessionDep, email: str) -> User | None:
    return await session.scalar(
        select(User).where(User.email == email, User.password_hash.is_not(None))
    )


@router.post("/signup", response_model=LocalAuthResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(payload: LocalSignUp, session: SessionDep) -> LocalAuthResponse:
    if await _local_account_for_email(session, payload.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        cognito_sub=f"local:{uuid.uuid4().hex}",
        email=payload.email,
        name=payload.name,
        password_hash=await run_in_threadpool(_hash_password, payload.password),
    )
    session.add(user)
    await session.flush()
    return _response(user)


@router.post("/login", response_model=LocalAuthResponse)
async def log_in(payload: AccountCredentials, session: SessionDep) -> LocalAuthResponse:
    user = await _local_account_for_email(session, payload.email)
    valid = (
        await run_in_threadpool(_password_matches, payload.password, user.password_hash)
        if user is not None and user.password_hash is not None
        else False
    )
    if not valid or user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return _response(user)
