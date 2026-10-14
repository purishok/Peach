#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
TEMPLATE="${ROOT}/infra/reports.yml"

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

if [[ -f "${ENV_FILE}" ]]; then
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
REPORTS_STACK_NAME="${REPORTS_STACK_NAME:-${PROJECT_NAME}-reports}"
ECR_REPOSITORY="${ECR_REPOSITORY:-${PROJECT_NAME}-backend}"
DB_INSTANCE_IDENTIFIER="${DB_INSTANCE_IDENTIFIER:-${PROJECT_NAME}-db}"
REPORTS_LAMBDA_ARCHITECTURE="${REPORTS_LAMBDA_ARCHITECTURE:-arm64}"
REPORT_SENDER_EMAIL="${REPORT_SENDER_EMAIL:-}"
REPORT_RECIPIENT_EMAILS="${REPORT_RECIPIENT_EMAILS:-}"
SES_IDENTITY_NAME="${SES_IDENTITY_NAME:-${REPORT_SENDER_EMAIL}}"
CREATE_SES_EMAIL_IDENTITY="${CREATE_SES_EMAIL_IDENTITY:-false}"

[[ -n "${REPORT_SENDER_EMAIL}" ]] || die "set REPORT_SENDER_EMAIL to a verified SES sender"
[[ -n "${REPORT_RECIPIENT_EMAILS}" ]] || die "set REPORT_RECIPIENT_EMAILS (sandbox recipients must be verified)"
case "${REPORTS_LAMBDA_ARCHITECTURE}" in
  arm64) CFN_ARCHITECTURE=arm64 ;;
  amd64) CFN_ARCHITECTURE=x86_64 ;;
  *) die "REPORTS_LAMBDA_ARCHITECTURE must be arm64 or amd64" ;;
esac

for tool in aws docker jq python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required"
done
docker info >/dev/null 2>&1 || die "docker daemon is not running"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
GIT_SHA="$(git -C "${ROOT}" rev-parse --short=12 HEAD)"
IMAGE_TAG="${REPORTS_IMAGE_TAG:-${GIT_SHA}-reports}"
if ! git -C "${ROOT}" diff --quiet HEAD -- backend; then
  IMAGE_TAG="${IMAGE_TAG}-dirty-$(date -u +%Y%m%d%H%M%S)"
fi
IMAGE_URI="${REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

IFS=$'\t' read -r VPC_ID SUBNET_IDS DATABASE_SECURITY_GROUP_ID < <(aws rds describe-db-instances \
  --region "${AWS_REGION}" \
  --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
  --query 'DBInstances[0].[DBSubnetGroup.VpcId,join(`,`,DBSubnetGroup.Subnets[].SubnetIdentifier),VpcSecurityGroups[0].VpcSecurityGroupId]' \
  --output text)
[[ -n "${VPC_ID}" && -n "${SUBNET_IDS}" && -n "${DATABASE_SECURITY_GROUP_ID}" ]] \
  || die "could not discover network settings from RDS ${DB_INSTANCE_IDENTIFIER}"

DATABASE_SECRET_ARN="${DATABASE_SECRET_ARN:-$(aws secretsmanager describe-secret \
  --region "${AWS_REGION}" \
  --secret-id "${PROJECT_NAME}/rds/credentials" \
  --query ARN --output text)}"

ROUTE_TABLE_IDS="$(VPC_ID="${VPC_ID}" SUBNET_IDS="${SUBNET_IDS}" AWS_REGION="${AWS_REGION}" python3 - <<'PY'
import json
import os
import subprocess

route_tables = json.loads(
    subprocess.check_output(
        [
            "aws", "ec2", "describe-route-tables",
            "--region", os.environ["AWS_REGION"],
            "--filters", f"Name=vpc-id,Values={os.environ['VPC_ID']}",
            "--output", "json",
        ],
        text=True,
    )
)["RouteTables"]
subnets = set(os.environ["SUBNET_IDS"].split(","))
selected = []
for table in route_tables:
    associations = table.get("Associations", [])
    if any(item.get("Main") or item.get("SubnetId") in subnets for item in associations):
        selected.append(table["RouteTableId"])
print(",".join(sorted(set(selected))))
PY
)"
[[ -n "${ROUTE_TABLE_IDS}" ]] || die "could not discover route tables for ${SUBNET_IDS}"

log "building Lambda image ${IMAGE_URI}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}" >/dev/null
docker buildx build \
  --platform "linux/${REPORTS_LAMBDA_ARCHITECTURE}" \
  --target lambda \
  --provenance=false \
  --sbom=false \
  --tag "${IMAGE_URI}" \
  --push \
  "${ROOT}/backend"

PARAMS_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
chmod 600 "${PARAMS_FILE}" "${RESULT_FILE}"
trap 'rm -f "${PARAMS_FILE}" "${RESULT_FILE}"' EXIT

PROJECT_NAME="${PROJECT_NAME}" VPC_ID="${VPC_ID}" SUBNET_IDS="${SUBNET_IDS}" \
ROUTE_TABLE_IDS="${ROUTE_TABLE_IDS}" DATABASE_SECURITY_GROUP_ID="${DATABASE_SECURITY_GROUP_ID}" \
DATABASE_SECRET_ARN="${DATABASE_SECRET_ARN}" IMAGE_URI="${IMAGE_URI}" \
CFN_ARCHITECTURE="${CFN_ARCHITECTURE}" REPORT_SENDER_EMAIL="${REPORT_SENDER_EMAIL}" \
REPORT_RECIPIENT_EMAILS="${REPORT_RECIPIENT_EMAILS}" \
SES_IDENTITY_NAME="${SES_IDENTITY_NAME}" \
CREATE_SES_EMAIL_IDENTITY="${CREATE_SES_EMAIL_IDENTITY}" \
python3 - "${PARAMS_FILE}" <<'PY'
import json
import os
import sys

mapping = {
    "ProjectName": "PROJECT_NAME",
    "VpcId": "VPC_ID",
    "SubnetIds": "SUBNET_IDS",
    "RouteTableIds": "ROUTE_TABLE_IDS",
    "DatabaseSecurityGroupId": "DATABASE_SECURITY_GROUP_ID",
    "DatabaseSecretArn": "DATABASE_SECRET_ARN",
    "ImageUri": "IMAGE_URI",
    "Architecture": "CFN_ARCHITECTURE",
    "ReportSenderEmail": "REPORT_SENDER_EMAIL",
    "ReportRecipientEmails": "REPORT_RECIPIENT_EMAILS",
    "SesIdentityName": "SES_IDENTITY_NAME",
    "CreateSesEmailIdentity": "CREATE_SES_EMAIL_IDENTITY",
}
with open(sys.argv[1], "w", encoding="utf-8") as file:
    json.dump(
        [{"ParameterKey": key, "ParameterValue": os.environ[value]} for key, value in mapping.items()],
        file,
    )
PY

log "deploying ${REPORTS_STACK_NAME} in ${AWS_REGION}"
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${REPORTS_STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides "file://${PARAMS_FILE}" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"

output() {
  aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${REPORTS_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}

BUILDER_FUNCTION="$(output ReportBuilderFunctionName)"
log "applying database migrations through ${BUILDER_FUNCTION}"
aws lambda wait function-active-v2 --region "${AWS_REGION}" --function-name "${BUILDER_FUNCTION}"
aws lambda wait function-updated-v2 --region "${AWS_REGION}" --function-name "${BUILDER_FUNCTION}"
aws lambda invoke \
  --region "${AWS_REGION}" \
  --function-name "${BUILDER_FUNCTION}" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"migrate"}' \
  "${RESULT_FILE}" >/dev/null
jq -e '.status == "ok"' "${RESULT_FILE}" >/dev/null || { cat "${RESULT_FILE}" >&2; exit 1; }

log "reports stack deployed"
printf 'bucket:   %s\nqueue:    %s\nschedule: %s\n' \
  "$(output ReportsBucketName)" "$(output ReportRequestsQueueUrl)" "$(output WeeklyScheduleName)"
