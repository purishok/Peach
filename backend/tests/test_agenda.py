"""The important boundary: parsed text cannot bypass ownership or validation."""

import json
from datetime import date

import pytest
from httpx import AsyncClient

from app.ai.agenda import ParsedAgenda, cost_usd, parse_agenda
from app.ai.agenda_lambda import handler
from tests.tokens import make_token


def test_parser_retries_invalid_tool_input(monkeypatch):
    class Block:
        type = "tool_use"
        name = "record_agenda"
        id = "call-1"

        def __init__(self, payload):
            self.input = payload

        def model_dump(self, **_kwargs):
            return {"type": self.type, "name": self.name, "id": self.id, "input": self.input}

    class Message:
        stop_reason = "tool_use"
        usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()

        def __init__(self, payload):
            self.content = [Block(payload)]

    answers = iter(
        [
            Message({"items": [{"topic": "Pricing", "minutes": -2}], "language": "en"}),
            Message({"items": [{"topic": "Pricing", "minutes": 15}], "language": "en"}),
        ]
    )

    class Client:
        def __init__(self, **_kwargs):
            self.messages = self

        def create(self, **_kwargs):
            return next(answers)

    monkeypatch.setattr("app.ai.agenda.AnthropicBedrockMantle", Client)
    agenda, usage = parse_agenda("Pricing — 15 minutes", date(2026, 10, 21), "Europe/Kyiv")
    assert agenda.items[0].minutes == 15
    assert usage == {"input_tokens": 20, "output_tokens": 10}
    assert cost_usd("anthropic.claude-opus-5-5", usage) == 0.00028


def test_invalid_start_time_is_rejected():
    with pytest.raises(ValueError):
        ParsedAgenda.model_validate(
            {
                "items": [{"topic": "Pricing"}],
                "language": "en",
                "starts_at": "2026-10-26T10:00:00",
            }
        )


def test_lambda_rejects_unauthenticated_and_oversize_before_inference(monkeypatch):
    def no_inference(*_args, **_kwargs):
        raise AssertionError("The model must not be called")

    monkeypatch.setattr("app.ai.agenda_lambda.parse_agenda", no_inference)
    assert handler({"headers": {}, "body": "{}"}, None)["statusCode"] == 401
    monkeypatch.setattr("app.ai.agenda_lambda._verify_token", lambda _token: {"sub": "alice"})
    large = handler(
        {
            "headers": {"authorization": "Bearer valid"},
            "body": json.dumps({"text": "x" * 10_001, "today": "2026-10-21", "tz": "Europe/Kyiv"}),
        },
        None,
    )
    assert large["statusCode"] == 413


async def test_save_keeps_original_suggestion_and_is_private(client: AsyncClient):
    created = (
        await client.post(
            "/api/v1/meetings",
            json={
                "title": "Pricing",
                "starts_at": "2026-10-26T10:00:00+02:00",
                "ends_at": "2026-10-26T10:45:00+02:00",
            },
        )
    ).json()
    assert created["id"]
    suggested = {
        "title": "Pricing",
        "starts_at": None,
        "duration_minutes": 45,
        "items": [{"topic": "Pro", "owner": "Olena", "minutes": 15}],
        "action_items": [],
        "language": "en",
    }
    final = {**suggested, "items": [{"topic": "Pro", "owner": "Olena", "minutes": 20}]}
    saved = (
        await client.put(
            f"/api/v1/meetings/{created['id']}/agenda",
            json={
                "agenda": final,
                "ai_suggestion": {
                    "agenda": suggested,
                    "model": "test",
                    "prompt_version": "agenda-v1",
                },
            },
        )
    ).json()
    assert saved["agenda"]["items"][0]["minutes"] == 20
    assert saved["ai_suggestion"]["agenda"]["items"][0]["minutes"] == 15
    bob = {"Authorization": f"Bearer {make_token('bob-sub', 'bob@example.com')}"}
    assert (await client.get(f"/api/v1/meetings/{created['id']}", headers=bob)).status_code == 404
    assert (
        await client.put(
            f"/api/v1/meetings/{created['id']}/agenda", headers=bob, json={"agenda": final}
        )
    ).status_code == 404
