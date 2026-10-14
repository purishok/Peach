"""SQS/direct Lambda adapter for weekly meeting report generation."""

import json
import logging
import os
from typing import Any

import boto3
from botocore.config import Config

from app.reports.weekly import build_weekly_report, parse_iso_week, previous_iso_week_for

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

_client_config = Config(
    retries={"total_max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=20,
)
s3: Any | None = None


def _s3_client() -> Any:
    """Create the SDK client on first invocation, when Lambda region env exists."""
    global s3
    if s3 is None:
        s3 = boto3.client("s3", config=_client_config)
    return s3


def _log(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True, default=str))


def _request_id(context: Any, fallback: str) -> str:
    return str(getattr(context, "aws_request_id", "") or fallback)


def _payloads(event: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
    records = event.get("Records")
    if records is None:
        return [("direct", event, "direct")]

    payloads: list[tuple[str, dict[str, Any], str]] = []
    for record in records:
        if record.get("eventSource") != "aws:sqs":
            raise ValueError("unsupported event source")
        body = json.loads(record["body"])
        if not isinstance(body, dict):
            raise ValueError("SQS message body must be a JSON object")
        payloads.append(("sqs", body, str(record.get("messageId", "sqs"))))
    return payloads


def _process(payload: dict[str, Any], trigger: str, request_id: str) -> dict[str, Any]:
    source = payload.get("source", "manual")
    if source not in {"schedule", "manual"}:
        raise ValueError("source must be schedule or manual")

    requested_week = payload.get("week")
    week = previous_iso_week_for() if requested_week is None else str(requested_week)
    parse_iso_week(week)

    failure_week = os.environ.get("REPORT_FAILURE_TEST_WEEK", "")
    if failure_week and week == failure_week:
        raise RuntimeError(f"controlled report failure for {week}")

    bucket = os.environ["REPORTS_BUCKET"]
    object_key = f"reports/{week}.csv"
    _log(
        "report-builder triggered",
        trigger=trigger,
        source=source,
        week=week,
        bucket=bucket,
        object_key=object_key,
        request_id=request_id,
        execution_result="started",
    )

    report = build_weekly_report(week)
    response = _s3_client().put_object(
        Bucket=bucket,
        Key=object_key,
        Body=report,
        ContentType="text/csv; charset=utf-8",
        ServerSideEncryption="AES256",
    )
    result = {
        "trigger": trigger,
        "source": source,
        "week": week,
        "bucket": bucket,
        "object_key": object_key,
        "request_id": request_id,
        "execution_result": "uploaded",
        "etag": response.get("ETag", ""),
    }
    _log("report-builder completed", **result)
    return result


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process a direct command or SQS records; exceptions intentionally propagate."""
    if event.get("action") == "migrate":
        from app.lambda_handler import _migrate

        return _migrate()
    results = [
        _process(payload, trigger, _request_id(context, fallback))
        for trigger, payload, fallback in _payloads(event)
    ]
    return results[0] if len(results) == 1 else {"results": results}
