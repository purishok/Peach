#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
REPORTS_STACK_NAME="${REPORTS_STACK_NAME:-${PROJECT_NAME}-reports}"

WEEK="${WEEK:-$(TZ=Europe/Kyiv python3 - <<'PY'
from datetime import date, timedelta

previous = date.today() - timedelta(days=7)
year, week, _ = previous.isocalendar()
print(f"{year:04d}-W{week:02d}")
PY
)}"
python3 - "${WEEK}" <<'PY'
import datetime
import re
import sys

value = sys.argv[1]
match = re.fullmatch(r"([0-9]{4})-W([0-9]{2})", value)
if not match:
    raise SystemExit("WEEK must use ISO format YYYY-Www")
try:
    datetime.date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
except ValueError as error:
    raise SystemExit(f"invalid ISO week: {value}") from error
PY

QUEUE_URL="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${REPORTS_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='ReportRequestsQueueUrl'].OutputValue | [0]" \
  --output text)"
MESSAGE_BODY="$(python3 - "${WEEK}" <<'PY'
import json
import sys

print(json.dumps({"source": "manual", "week": sys.argv[1]}, separators=(",", ":")))
PY
)"
MESSAGE_ID="$(aws sqs send-message \
  --region "${AWS_REGION}" \
  --queue-url "${QUEUE_URL}" \
  --message-body "${MESSAGE_BODY}" \
  --query MessageId \
  --output text)"
printf 'Queued weekly report %s\nMessageId: %s\n' "${WEEK}" "${MESSAGE_ID}"
