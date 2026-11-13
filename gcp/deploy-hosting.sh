#!/usr/bin/env bash
set -euo pipefail

project_id=${1:?Usage: bash gcp/deploy-hosting.sh PROJECT_ID}
: "${COGNITO_AUTHORITY:?Set the public Cognito issuer URL}"
: "${COGNITO_CLIENT_ID:?Set the public Cognito browser app client ID}"
: "${COGNITO_DOMAIN:?Set the public Cognito login domain URL}"

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
site="https://${project_id}.web.app"

(
  cd "$root/frontend"
  pnpm install --frozen-lockfile
  NEXT_OUTPUT=export \
    NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_PARSER_URL="${GCP_PARSER_URL:-}" \
    NEXT_PUBLIC_COGNITO_AUTHORITY="$COGNITO_AUTHORITY" \
    NEXT_PUBLIC_COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" \
    NEXT_PUBLIC_COGNITO_DOMAIN="$COGNITO_DOMAIN" \
    NEXT_PUBLIC_COGNITO_REDIRECT_URI="$site/auth/callback" \
    NEXT_PUBLIC_COGNITO_LOGOUT_URI="$site" \
    pnpm build
)
cd "$root/gcp"
mkdir -p out
rsync -a --delete "$root/frontend/out/" out/
firebase deploy --project "$project_id" --only hosting
