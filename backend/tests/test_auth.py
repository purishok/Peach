import pytest
from httpx import AsyncClient

from app.config import get_settings
from tests.tokens import make_token


async def test_missing_credentials(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"aud": "wrong-client"},
        {"iss": "https://wrong-issuer.example"},
        {"token_use": "access"},
        {"sub": ""},
    ],
)
async def test_rejects_invalid_claims(anon_client: AsyncClient, claims: dict) -> None:
    response = await anon_client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {make_token(**claims)}"}
    )
    assert response.status_code == 401


async def test_rejects_bad_signature(anon_client: AsyncClient) -> None:
    token = make_token()
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    token = f"{header}.{payload}.{replacement}{signature[1:]}"
    response = await anon_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_me_reuses_identity(client: AsyncClient) -> None:
    first = await client.get("/api/v1/me")
    second = await client.get("/api/v1/me")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["email"] == "alice@example.com"


async def test_missing_configuration_fails_closed(anon_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "cognito_user_pool_id", "")
    assert (await anon_client.get("/api/v1/me")).status_code == 503
