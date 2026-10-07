#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

AWS_REGION="${AWS_REGION:-eu-north-1}"
COGNITO_REGION="${COGNITO_REGION:-us-east-1}"
ECS_CLUSTER="${ECS_CLUSTER:-peach-cluster}"
ECS_SERVICE="${ECS_SERVICE:-peach-backend-service}"
ECS_CONTAINER_NAME="${ECS_CONTAINER_NAME:-peach-backend}"

for tool in aws curl jq; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
[[ -n "${COGNITO_USER_POOL_ID:-}" ]] || die "COGNITO_USER_POOL_ID is missing; run make auth-deploy"
[[ -n "${COGNITO_CLIENT_ID:-}" ]] || die "COGNITO_CLIENT_ID is missing; run make auth-deploy"

jwks_url="https://cognito-idp.${COGNITO_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}/.well-known/jwks.json"
log "fetching Cognito signing keys"
COGNITO_JWKS="$(curl -fsS --max-time 20 "${jwks_url}" | jq -c .)" \
  || die "could not fetch ${jwks_url}"
export COGNITO_JWKS

current_task_definition="$(aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --query 'services[0].taskDefinition' --output text)"
[[ -n "${current_task_definition}" && "${current_task_definition}" != "None" ]] \
  || die "could not find ${ECS_SERVICE} in ${ECS_CLUSTER}"

source_file="$(mktemp "${TMPDIR:-/tmp}/peach-task-source.XXXXXX")"
updated_file="$(mktemp "${TMPDIR:-/tmp}/peach-task-cognito.XXXXXX")"
chmod 600 "${source_file}" "${updated_file}"
trap 'rm -f "${source_file}" "${updated_file}"' EXIT

aws ecs describe-task-definition \
  --region "${AWS_REGION}" \
  --task-definition "${current_task_definition}" \
  --query taskDefinition --output json > "${source_file}"

jq \
  --arg container "${ECS_CONTAINER_NAME}" \
  --arg cognito_region "${COGNITO_REGION}" \
  --arg user_pool_id "${COGNITO_USER_POOL_ID}" \
  --arg client_id "${COGNITO_CLIENT_ID}" \
  'if any(.containerDefinitions[]; .name == $container) then
     .containerDefinitions |= map(
       if .name == $container then
         .environment = (
           ((.environment // [])
             | map(select((.name == "COGNITO_REGION" or
                           .name == "COGNITO_USER_POOL_ID" or
                           .name == "COGNITO_CLIENT_ID" or
                           .name == "COGNITO_JWKS" or
                           .name == "DEV_AUTH_ENABLED" or
                           .name == "APP_ENV") | not)))
           + [
               {name: "COGNITO_REGION", value: $cognito_region},
               {name: "COGNITO_USER_POOL_ID", value: $user_pool_id},
               {name: "COGNITO_CLIENT_ID", value: $client_id},
               {name: "COGNITO_JWKS", value: env.COGNITO_JWKS},
               {name: "DEV_AUTH_ENABLED", value: "false"},
               {name: "APP_ENV", value: "production"}
             ]
         )
       else . end
     )
   else error("ECS container not found: " + $container) end
   | del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
         .compatibilities, .registeredAt, .registeredBy, .deregisteredAt)' \
  "${source_file}" > "${updated_file}"

log "registering an auth-configured revision of ${current_task_definition}"
new_task_definition="$(aws ecs register-task-definition \
  --region "${AWS_REGION}" \
  --cli-input-json "file://${updated_file}" \
  --query taskDefinition.taskDefinitionArn --output text)"

log "rolling ${ECS_SERVICE} without changing its image or infrastructure"
aws ecs update-service \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --service "${ECS_SERVICE}" \
  --task-definition "${new_task_definition}" >/dev/null
aws ecs wait services-stable \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}"

echo "ECS is using ${new_task_definition} with Cognito authentication."
