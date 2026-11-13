#!/usr/bin/env bash
set -euo pipefail

project_id=${1:?Usage: bash gcp/bootstrap-iam.sh PROJECT_ID GOOGLE_ACCOUNT_EMAIL}
operator=${2:?Provide the Google account email that will impersonate Terraform}
deployer="peach-terraform@${project_id}.iam.gserviceaccount.com"
runtime="peach-run@${project_id}.iam.gserviceaccount.com"

gcloud services enable iam.googleapis.com iamcredentials.googleapis.com \
  serviceusage.googleapis.com --project "$project_id"

for account in peach-terraform peach-run; do
  if ! gcloud iam service-accounts describe "${account}@${project_id}.iam.gserviceaccount.com" \
    --project "$project_id" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account" --project "$project_id"
  fi
done

for role in run.admin cloudsql.admin artifactregistry.admin secretmanager.admin serviceusage.serviceUsageAdmin; do
  gcloud projects add-iam-policy-binding "$project_id" \
    --member "serviceAccount:$deployer" --role "roles/$role" --condition=None
done

gcloud projects add-iam-policy-binding "$project_id" \
  --member "serviceAccount:$runtime" --role roles/cloudsql.client --condition=None
gcloud iam service-accounts add-iam-policy-binding "$runtime" --project "$project_id" \
  --member "serviceAccount:$deployer" --role roles/iam.serviceAccountUser --condition=None
gcloud iam service-accounts add-iam-policy-binding "$deployer" --project "$project_id" \
  --member "user:$operator" --role roles/iam.serviceAccountTokenCreator --condition=None
