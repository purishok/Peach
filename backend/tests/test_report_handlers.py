import io
import json
from email import policy
from email.parser import BytesParser
from types import SimpleNamespace

import pytest

from app.reports import lambda_handler, mailer


class FakeS3Put:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"ETag": '"etag"'}


def test_builder_processes_sqs_and_uses_deterministic_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s3 = FakeS3Put()
    monkeypatch.setattr(lambda_handler, "s3", s3)
    monkeypatch.setattr(lambda_handler, "build_weekly_report", lambda week: b"report")
    monkeypatch.setenv("REPORTS_BUCKET", "reports-bucket")
    event = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "messageId": "message-1",
                "body": json.dumps({"source": "manual", "week": "2026-W40"}),
            }
        ]
    }

    result = lambda_handler.handler(event, SimpleNamespace(aws_request_id="request-1"))

    assert result["trigger"] == "sqs"
    assert result["source"] == "manual"
    assert result["object_key"] == "reports/2026-W40.csv"
    assert s3.calls[0]["Key"] == "reports/2026-W40.csv"


def test_builder_direct_null_week_uses_previous_week(monkeypatch: pytest.MonkeyPatch) -> None:
    s3 = FakeS3Put()
    monkeypatch.setattr(lambda_handler, "s3", s3)
    monkeypatch.setattr(lambda_handler, "previous_iso_week_for", lambda: "2026-W40")
    monkeypatch.setattr(lambda_handler, "build_weekly_report", lambda week: b"report")
    monkeypatch.setenv("REPORTS_BUCKET", "reports-bucket")
    result = lambda_handler.handler({"source": "schedule", "week": None}, None)
    assert result["week"] == "2026-W40"
    assert result["trigger"] == "direct"


def test_builder_controlled_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORT_FAILURE_TEST_WEEK", "2026-W40")
    with pytest.raises(RuntimeError, match="controlled report failure"):
        lambda_handler.handler({"source": "manual", "week": "2026-W40"}, None)


class FakeBody(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeS3Get:
    def get_object(self, **kwargs):
        return {"Body": FakeBody(b"header\nvalue\n")}


class FakeSes:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "ses-message"}


def test_mailer_downloads_and_sends_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    ses = FakeSes()
    monkeypatch.setattr(mailer, "s3", FakeS3Get())
    monkeypatch.setattr(mailer, "sesv2", ses)
    monkeypatch.setenv("REPORT_SENDER", "reports@example.com")
    monkeypatch.setenv("REPORT_RECIPIENTS", "recipient@example.com")
    event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "reports-bucket"},
                    "object": {"key": "reports%2F2026-W40.csv"},
                },
            }
        ]
    }

    result = mailer.handler(event, SimpleNamespace(aws_request_id="request-2"))

    assert result["message_id"] == "ses-message"
    raw = ses.calls[0]["Content"]["Raw"]["Data"]
    assert b'filename="2026-W40.csv"' in raw
    parsed = BytesParser(policy=policy.default).parsebytes(raw)
    attachment = next(parsed.iter_attachments())
    assert attachment.get_payload(decode=True) == b"header\nvalue\n"


def test_mailer_rejects_non_report_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORT_SENDER", "reports@example.com")
    monkeypatch.setenv("REPORT_RECIPIENTS", "recipient@example.com")
    event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "s3": {"bucket": {"name": "bucket"}, "object": {"key": "other.csv"}},
            }
        ]
    }
    with pytest.raises(ValueError, match="unexpected report object key"):
        mailer.handler(event, None)
