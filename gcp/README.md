# Peach on Google Cloud

Deploy a second copy of the core in us-central1. The FastAPI service runs on
Cloud Run and reaches PostgreSQL through the Cloud SQL Auth Proxy socket.
Firebase Hosting serves the Next.js export and forwards /api/** to Cloud Run.
Cognito still validates user identities on AWS. The AWS weekly report, SES,
SQS and the Bedrock agenda parser still use the existing AWS deployment.

## Bootstrap

1. Create a dedicated Google Cloud project, link active billing, and set a
   project-scoped $5 monthly budget with alerts at 50%, 90% and 100%. The
   budget sends alerts and does not cap spending.
2. Add Firebase to that project and initialize its default Hosting site in
   Firebase Console. Accept the Firebase terms if prompted. The Hosting
   rewrite uses the billing-enabled Blaze plan.
3. Install gcloud, Terraform, Docker with buildx, Node, pnpm and Firebase CLI.
   Sign in with an operator who can create service accounts and manage project
   IAM. Run this from the repository root:

   ```bash
   export PROJECT_ID=your-lab9-project
   export GOOGLE_ACCOUNT=your-google-account-email
   gcloud auth login
   gcloud auth application-default login
   bash gcp/bootstrap-iam.sh "$PROJECT_ID" "$GOOGLE_ACCOUNT"
   firebase login
   terraform login
   ```

4. In HCP Terraform, create a **CLI-driven** workspace named
   `peach-gcp-lab9` in `Pitch_organisation` and set execution mode to
   **Local** before applying. HCP stores GCP state and the local Google
   provider impersonates `peach-terraform` using ADC. State contains the
   generated password and DSN. Keep workspace state access restricted.
5. Copy `gcp/terraform.tfvars.example` to `gcp/terraform.tfvars` and set
   the project ID, service account email and existing Cognito pool/client IDs.
   The deployer may act as `peach-run` only on that service account. The
   runtime may connect to Cloud SQL and read only the lab database secret.
   If you automate CI later, use GitHub OIDC Workload Identity Federation
   with numeric repository and repository-owner IDs in the provider condition,
   and grant Workload Identity User on the deployer to that repository only.

## Deploy

Apply with the image unset first to create the Artifact Registry and enable
the APIs. Subsequent applies should retain the current image in tfvars.

```bash
terraform -chdir=gcp init
terraform -chdir=gcp apply
registry=$(terraform -chdir=gcp output -raw artifact_registry)
gcloud auth configure-docker us-central1-docker.pkg.dev
image="$registry/backend:$(git rev-parse --short HEAD)"
metadata=$(mktemp)
docker buildx build --platform linux/amd64 --target runtime \
  --tag "$image" --push --metadata-file "$metadata" backend
printf '%s@%s\n' "$registry/backend" "$(jq -r '."containerimage.digest"' "$metadata")"
rm "$metadata"
```

The operator who pushes the image needs Artifact Registry Writer on the
repository, or equivalent existing access. Copy the printed digest into
`backend_image` in tfvars, then run `terraform -chdir=gcp apply` again.
This creates the database and deploys the API. The container runs
`alembic upgrade head` against the new database before serving HTTP. This
initializes an empty database, with no Aurora dump or existing user data.

If a Cloud SQL PostgreSQL instance reports `permission denied for schema public`
during the migration, connect as the database administrator and run
`GRANT USAGE, CREATE ON SCHEMA public TO peach;` inside the `peach` database.
Then retry the Cloud Run revision. Leave Cloud SQL authorized networks empty.

Add the Firebase callback (`https://PROJECT_ID.web.app/auth/callback`) and
logout (`https://PROJECT_ID.web.app`) URLs to the existing Cognito client
through the AWS infrastructure workflow in `infra/`. Set `additional_callback_urls`
and `additional_logout_urls` in the AWS workspace to the corresponding lists.
The original AWS and localhost URLs remain part of both lists.

Export the existing public `COGNITO_AUTHORITY`, `COGNITO_CLIENT_ID` and
`COGNITO_DOMAIN` values, then run:

```bash
bash gcp/deploy-hosting.sh "$PROJECT_ID"
curl -fsS "https://$PROJECT_ID.web.app/api/health"
```

The browser uses relative API URLs so Hosting forwards API traffic with no
cross-origin configuration. Cognito JWTs are required by every `/api/v1`
endpoint. The public liveness endpoint exposes no database data.
To verify the database, open the Firebase URL in a private browser window,
sign in with Cognito, create a synthetic item and reload the Items page.
In Network, verify `GET /api/v1/items` returns 200 and contains the new item.
An authenticated `GET /api/v1/health/ready` also executes `SELECT 1`.
Optionally set `GCP_PARSER_URL` after allowing the Firebase origin on the
AWS parser and verifying that the Cognito client is accepted there.

## Stop or clean up

To stop compute, keep the digest in tfvars, set `database_running = false`
and apply. Set it back to `true` and apply to resume. Storage and public IPv4
are still billed while stopped. The authenticated DB checks will fail while
the database is off.

After the live grading window, disable the Firebase Hosting release with
`firebase hosting:disable --project "$PROJECT_ID"` and run
`terraform -chdir=gcp destroy` using the GCP workspace. The manually
bootstrapped Firebase project, budget and IAM identities are outside the
Terraform state. Remove them with the dedicated project when it is no
longer needed. Remove any demo Dataflow output or BigQuery tables and check
Billing Reports the next day.
