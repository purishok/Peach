#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/cognito.yaml"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

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
AUTH_AWS_REGION="${AUTH_AWS_REGION:-us-east-1}"
AUTH_STACK_NAME="${AUTH_STACK_NAME:-${PROJECT_NAME}-auth}"
FRONTEND_URL="${FRONTEND_URL:-}"

for tool in aws jq; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no usable AWS credentials; set AWS_PROFILE or authenticate with the AWS CLI"

[[ -n "${GOOGLE_CLIENT_ID:-}" ]] || die "GOOGLE_CLIENT_ID is required in .env"
[[ -n "${GOOGLE_CLIENT_SECRET:-}" ]] || die "GOOGLE_CLIENT_SECRET is required in .env"
[[ -n "${COGNITO_DOMAIN_PREFIX:-}" ]] || die "COGNITO_DOMAIN_PREFIX is required in .env"

if [[ -z "${FRONTEND_URL}" && -n "${CLOUDFRONT_DISTRIBUTION_ID:-}" ]]; then
  distribution_domain="$(aws cloudfront get-distribution \
    --id "${CLOUDFRONT_DISTRIBUTION_ID}" \
    --query Distribution.DomainName --output text)"
  [[ -n "${distribution_domain}" && "${distribution_domain}" != "None" ]] \
    || die "could not derive the frontend URL from CloudFront"
  FRONTEND_URL="https://${distribution_domain}"
fi

FRONTEND_URL="${FRONTEND_URL%/}"
[[ "${FRONTEND_URL}" == https://* ]] \
  || die "FRONTEND_URL must be the deployed HTTPS origin"

CALLBACK_URL="${FRONTEND_URL}/auth/callback"
LOGOUT_URL="${FRONTEND_URL}/"

parameters_file="$(mktemp "${TMPDIR:-/tmp}/peach-cognito.XXXXXX")"
chmod 600 "${parameters_file}"
trap 'rm -f "${parameters_file}"' EXIT
jq -n \
  --arg project_name "${PROJECT_NAME}" \
  --arg domain_prefix "${COGNITO_DOMAIN_PREFIX}" \
  --arg callback_url "${CALLBACK_URL}" \
  --arg logout_url "${LOGOUT_URL}" \
  '[
    {ParameterKey: "ProjectName", ParameterValue: $project_name},
    {ParameterKey: "CognitoDomainPrefix", ParameterValue: $domain_prefix},
    {ParameterKey: "GoogleClientId", ParameterValue: env.GOOGLE_CLIENT_ID},
    {ParameterKey: "GoogleClientSecret", ParameterValue: env.GOOGLE_CLIENT_SECRET},
    {ParameterKey: "ApplicationCallbackUrl", ParameterValue: $callback_url},
    {ParameterKey: "ApplicationLogoutUrl", ParameterValue: $logout_url}
  ]' > "${parameters_file}"

log "deploying ${AUTH_STACK_NAME} in ${AUTH_AWS_REGION}"
# CloudFormation masks the NoEcho parameter. A mode-0600 temporary file keeps
# the secret out of logs and process arguments, and the EXIT trap removes it.
aws cloudformation deploy \
  --region "${AUTH_AWS_REGION}" \
  --stack-name "${AUTH_STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides "file://${parameters_file}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"

output() {
  aws cloudformation describe-stacks \
    --region "${AUTH_AWS_REGION}" \
    --stack-name "${AUTH_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" \
    --output text
}

USER_POOL_ID="$(output UserPoolId)"
CLIENT_ID="$(output UserPoolClientId)"
DOMAIN="$(output CognitoDomain)"
AUTHORITY="$(output CognitoAuthority)"

upsert_env() {
  local key="$1" value="$2" env_file="${ROOT}/.env" temp_file
  temp_file="$(mktemp "${ROOT}/.env.XXXXXX")"
  chmod 600 "${temp_file}"
  if [[ -f "${env_file}" ]]; then
    awk -v key="${key}" -v value="${value}" \
      'BEGIN { found=0 } $0 ~ "^" key "=" { print key "=" value; found=1; next } { print } END { if (!found) print key "=" value }' \
      "${env_file}" > "${temp_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" > "${temp_file}"
  fi
  mv "${temp_file}" "${env_file}"
}

upsert_env COGNITO_REGION "${AUTH_AWS_REGION}"
upsert_env COGNITO_USER_POOL_ID "${USER_POOL_ID}"
upsert_env COGNITO_CLIENT_ID "${CLIENT_ID}"
upsert_env COGNITO_DOMAIN "${DOMAIN}"
upsert_env COGNITO_AUTHORITY "${AUTHORITY}"
upsert_env COGNITO_REDIRECT_URI "${CALLBACK_URL}"
upsert_env COGNITO_LOGOUT_URI "${LOGOUT_URL}"

echo
echo "  user pool       ${USER_POOL_ID}"
echo "  client           ${CLIENT_ID}"
echo "  managed login    ${DOMAIN}"
echo "  callback         ${CALLBACK_URL}"
echo "  logout           ${LOGOUT_URL}"
echo "  Google origin    ${DOMAIN}"
echo "  Google redirect  ${DOMAIN}/oauth2/idpresponse"
echo
echo "Public Cognito outputs were written to .env; the Google secret was not changed or printed."
