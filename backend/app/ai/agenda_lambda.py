"""Public function URL: authenticate, validate, parse and log one paid request."""

import base64
import json
import logging
import time
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt

from app.ai.agenda import PROMPT_VERSION, AgendaParseError, cost_usd, parse_agenda
from app.auth import _verify_token
from app.config import get_settings

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event: dict, _context: object) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    authorization = headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return response(401, {"error": "Sign in required"})
    try:
        user = _verify_token(authorization.removeprefix("Bearer "))
    except jwt.PyJWTError, ValueError:
        return response(401, {"error": "Invalid session"})
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw)
        body = json.loads(raw)
        text = body["text"]
        if not isinstance(text, str) or not text.strip():
            return response(400, {"error": "Paste agenda text first"})
        if len(text) > 10_000:
            return response(413, {"error": "Text exceeds 10,000 characters"})
        today = date.fromisoformat(body["today"])
        tz = body["tz"]
        if not isinstance(tz, str) or len(tz) > 64:
            raise ValueError("Invalid time zone")
        ZoneInfo(tz)
    except KeyError, TypeError, ValueError, json.JSONDecodeError, ZoneInfoNotFoundError:
        return response(400, {"error": "Invalid text, date or time zone"})

    started = time.monotonic()
    settings = get_settings()
    usage = None
    result_status = "error"
    error_type = None
    try:
        agenda, usage = parse_agenda(text, today, tz)
        result_status = "ok"
    except AgendaParseError as exc:
        usage = exc.usage
        result_status = "invalid_agenda"
        return response(422, {"error": str(exc)})
    except Exception as exc:
        name = type(exc).__name__
        error_type = name
        if "Throttl" in name or "RateLimit" in name or "Overloaded" in name:
            result_status = "throttled"
            return response(429, {"error": "Parser is busy. Try again shortly."})
        return response(503, {"error": "Parser unavailable. Enter the agenda manually."})
    finally:
        log.info(
            json.dumps(
                {
                    "event": "agenda_parse",
                    "user": user["sub"],
                    "model": settings.parser_model,
                    "prompt_version": PROMPT_VERSION,
                    "status": result_status,
                    "error_type": error_type,
                    "input_tokens": usage["input_tokens"] if usage else None,
                    "output_tokens": usage["output_tokens"] if usage else None,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "cost_usd": cost_usd(settings.parser_model, usage) if usage else None,
                }
            )
        )
    return response(
        200,
        {
            "agenda": agenda.model_dump(mode="json"),
            "model": settings.parser_model,
            "prompt_version": PROMPT_VERSION,
            "usage": usage,
        },
    )
