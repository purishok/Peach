"""Ephemeral test signing key; never used by the application outside pytest."""

import json
import os
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_private_key.public_key()))
_public_jwk.update(kid="test-key", use="sig", alg="RS256")

os.environ["COGNITO_REGION"] = "us-east-1"
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_test"
os.environ["COGNITO_CLIENT_ID"] = "test-client"
os.environ["COGNITO_JWKS"] = json.dumps({"keys": [_public_jwk]})


def make_token(sub: str = "alice-sub", email: str = "alice@example.com", **overrides: Any) -> str:
    claims = {
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test",
        "aud": "test-client",
        "sub": sub,
        "email": email,
        "name": "Test user",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "token_use": "id",
        **overrides,
    }
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": "test-key"})


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}
