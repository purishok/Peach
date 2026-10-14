"""S3 ObjectCreated Lambda adapter that emails CSV reports through SES v2."""

import json
import logging
import os
from email.message import EmailMessage
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

_client_config = Config(
    retries={"total_max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=20,
)
s3: Any | None = None
sesv2: Any | None = None


def _s3_client() -> Any:
    """Create the SDK client on first invocation, when Lambda region env exists."""
    global s3
    if s3 is None:
        s3 = boto3.client("s3", config=_client_config)
    return s3


def _ses_client() -> Any:
    """Create the SDK client on first invocation, when Lambda region env exists."""
    global sesv2
    if sesv2 is None:
        sesv2 = boto3.client("sesv2", config=_client_config)
    return sesv2


def _log(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True, default=str))


def _recipients() -> list[str]:
    recipients = [
        address.strip() for address in os.environ["REPORT_RECIPIENTS"].split(",") if address.strip()
    ]
    if not recipients:
        raise ValueError("REPORT_RECIPIENTS must contain at least one address")
    return recipients


def _send_report(bucket: str, key: str, request_id: str) -> dict[str, str]:
    if not key.startswith("reports/") or not key.endswith(".csv"):
        raise ValueError(f"unexpected report object key: {key}")

    _log(
        "report-mailer triggered",
        trigger="s3",
        bucket=bucket,
        key=key,
        request_id=request_id,
        execution_result="started",
    )
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    with response["Body"] as body:
        report = body.read()

    sender = os.environ["REPORT_SENDER"]
    recipients = _recipients()
    filename = key.rsplit("/", 1)[-1]
    week = filename.removesuffix(".csv")

    message = EmailMessage()
    message["Subject"] = f"Peach weekly meetings report: {week}"
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(f"The Peach weekly meetings report for {week} is attached.")
    message.add_attachment(report, maintype="text", subtype="csv", filename=filename)

    send_response = _ses_client().send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": recipients},
        Content={"Raw": {"Data": message.as_bytes()}},
    )
    result = {
        "trigger": "s3",
        "bucket": bucket,
        "key": key,
        "request_id": request_id,
        "execution_result": "sent",
        "message_id": send_response["MessageId"],
    }
    _log("report-mailer completed", **result)
    return result


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Send every matching S3 event; exceptions intentionally propagate."""
    request_id = str(getattr(context, "aws_request_id", "") or "s3")
    results = []
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            raise ValueError("unsupported event source")
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        results.append(_send_report(bucket, key, request_id))
    if not results:
        raise ValueError("S3 event contained no records")
    return results[0] if len(results) == 1 else {"results": results}
