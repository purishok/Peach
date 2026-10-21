#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
AI_REGION="${AI_REGION:-eu-north-1}"
BEDROCK_REGION="${BEDROCK_REGION:-us-east-1}"
AI_STACK_NAME="${AI_STACK_NAME:-${PROJECT_NAME}-ai}"
AI_BUDGET_STACK_NAME="${AI_BUDGET_STACK_NAME:-${PROJECT_NAME}-ai-budget}"
PARSER_MODEL="${PARSER_MODEL:-anthropic.claude-opus-5-5}"
AI_BUDGET_EMAIL="${AI_BUDGET_EMAIL:-${REPORT_RECIPIENT_EMAILS:-}}"
[[ -n "${AI_BUDGET_EMAIL}" ]] || { echo 'Set AI_BUDGET_EMAIL' >&2; exit 1; }
[[ -n "${COGNITO_USER_POOL_ID:-}" && -n "${COGNITO_CLIENT_ID:-}" ]] \
  || { echo 'Set Cognito pool and client IDs' >&2; exit 1; }

account="$(aws sts get-caller-identity --query Account --output text)"
registry="${account}.dkr.ecr.${AI_REGION}.amazonaws.com"
repository="${ECR_REPOSITORY:-${PROJECT_NAME}-backend}"
image_tag="$(git -C "${ROOT}" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image_uri="${registry}/${repository}:${image_tag}"

if ! aws ecr describe-repositories --region "${AI_REGION}" --repository-names "${repository}" >/dev/null 2>&1; then
  aws ecr create-repository --region "${AI_REGION}" --repository-name "${repository}" \
    --image-scanning-configuration scanOnPush=true \
    --tags "Key=PROJECT_NAME,Value=${PROJECT_NAME}" >/dev/null
fi
aws ecr get-login-password --region "${AI_REGION}" \
  | docker login --username AWS --password-stdin "${registry}" >/dev/null
docker buildx build --platform linux/arm64 --target lambda --provenance=false --sbom=false \
  --tag "${image_uri}" --push "${ROOT}/backend"

aws cloudformation deploy --region "${AI_REGION}" --stack-name "${AI_STACK_NAME}" \
  --template-file "${ROOT}/infra/ai.yml" \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" "ImageUri=${image_uri}" \
    "ParserModel=${PARSER_MODEL}" "BedrockRegion=${BEDROCK_REGION}" \
    "CognitoRegion=${COGNITO_REGION:-us-east-1}" \
    "CognitoUserPoolId=${COGNITO_USER_POOL_ID}" "CognitoClientId=${COGNITO_CLIENT_ID}" \
    "SiteOrigin=${FRONTEND_URL:-https://dqvalqr0apze.cloudfront.net}" \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"

url="$(aws cloudformation describe-stacks --region "${AI_REGION}" \
  --stack-name "${AI_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='ParserUrl'].OutputValue | [0]" --output text)"
python3 - "${ROOT}/.env" "${url}" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
line = "PARSER_URL=" + sys.argv[2]
old = path.read_text().splitlines() if path.exists() else []
new = [item for item in old if not item.startswith("PARSER_URL=")]
new.append(line)
path.write_text("\n".join(new) + "\n")
PY
echo "Parser URL: ${url}"
aws cloudformation deploy --region us-east-1 --stack-name "${AI_BUDGET_STACK_NAME}" \
  --template-file "${ROOT}/infra/ai-budget.yml" \
  --parameter-overrides "ProjectName=${PROJECT_NAME}" "BudgetEmail=${AI_BUDGET_EMAIL}" \
  --no-fail-on-empty-changeset --tags "PROJECT_NAME=${PROJECT_NAME}"
echo "Deploy the frontend to compile NEXT_PUBLIC_PARSER_URL into the site."
