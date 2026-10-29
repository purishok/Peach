# ADR 0007 — Terraform and HCP Terraform for Labs 4–6

Date: 2026-10-29
Status: Accepted

## Context

Peach has Cognito in us-east-1 and weekly reports in eu-north-1 in account
505464394565. Its parser runs in eu-north-1 in account 985040259102. Existing
users, reports, client IDs, generated IAM role names and Lambda URLs must survive
an ownership transfer. Earlier network, ECS/database, frontend, GitHub OIDC and
AI budget infrastructure remains outside this migration.

## Decision

Manage auth, reports and AI in one Terraform root, infra/, with HCP Terraform
Remote execution and locked state in Pitch_organisation/peach-dev. The migration
imported 40 provider resources representing 29 existing CloudFormation resources;
S3 settings, inline IAM policies and the shared SQS policy account for the splits.
No resources were recreated. CloudFormation released every resource with both
retention policies set to Retain before the HCP VCS-triggered adoption apply.

The four reviewed adoption updates preserve behavior: three add sensitive-value
annotations without changing values, and one makes Cognito's existing implicit
one-hour access/ID token lifetime explicit. The user pool and reports bucket have
prevent_destroy; the bucket also has force_destroy=false. These protections do
not replace backups or protect resources after their blocks are removed.

Use separate OIDC credentials for the two accounts, with main-account credentials
also used by the auth region alias. Plan and apply roles have separate exact
subjects restricted to the organization, project, workspace and respective run
phase. Apply roles add only scoped reviewed writes to ReadOnlyAccess; PassRole is
limited to existing Lambda runtime roles. The bootstrap trust/policy documents
are recorded in infra/bootstrap/. No permanent AWS keys are stored in HCP or Git.

Contributors and assistants propose branches. An authorized reviewer inspects the
refreshed plan, merges, and approves the HCP apply. Auto-apply stays disabled.
There is no apply target in Makefile. GitHub Actions continues deploying the
application through its existing OIDC role. Apply compatible infrastructure first,
then deploy dependent application code; remove old dependencies after callers move.
Console emergency fixes must promptly become reviewed HCL before the next apply.

## Alternatives

CloudFormation owns state and provides rollback, but is AWS-specific. CDK improves
authoring while retaining CloudFormation's deployment model. OpenTofu is a credible
open-license alternative. Terraform is selected for this course's HCP workflow,
provider ecosystem, and a consistent multi-account/environment review process.
Google OAuth and GitHub can be managed later; this migration does not claim them.
A future environment needs its own state and isolated names, with shared modules
and parameterized role names; dev imports must never be reused for staging.

## Consequences

Non-secret inputs are workspace Terraform variables, with a tracked
terraform.tfvars.example; log retention follows the HCL default. Local tfvars is
ignored by Git and excluded from CLI uploads. The Google OAuth secret and report
recipients are sensitive workspace variables. The database URL remains in Secrets
Manager but is resolved into Lambda configuration and Terraform state.

Sensitive values also exist in HCP state/history and potentially saved plans,
local .env and AWS configuration. sensitive hides ordinary rendering, not state or
JSON exports. Restrict workspace/state access to trusted operators. Keep state,
plans, credentials and private snapshots out of Git and CI logs; rotate leaked
secrets. HCP API tokens stay in the local Terraform credential store.

If HCP is unavailable, running AWS resources continue serving traffic while
infrastructure changes wait. Never start an independent local state. An authorized
operator may make a documented emergency AWS repair and reconcile HCL before HCP
resumes. For a prolonged outage, disable old writers and restore a securely
exported state version to a reviewed backend with locking. Terraform does not
roll back automatically: inspect partial state/resources, fix the cause, then plan.

Evidence and resource-preservation checks: [migration record](../lab7-migration.md).
