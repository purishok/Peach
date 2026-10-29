# ADR 0007 — Terraform and HCP Terraform for Labs 4–6

Date: 2026-10-29
Status: Proposed; migration in progress; HCP speculative plans and reviewed adoption deltas verified.

## Context

Peach has Cognito in us-east-1 and weekly reports in eu-north-1 in account
505464394565. The agenda parser is a separate CloudFormation stack,
peach-ai-sonnet, in account 985040259102. Existing users, reports, queue messages,
public client IDs and the parser URL must survive adoption. Earlier network,
ECS/database, frontend, GitHub OIDC and AI budget infrastructure remains outside
this migration. AWS service control policies still constrain both accounts.

## Decision

Use one Terraform root in infra/ and one HCP Terraform Remote workspace per
environment. Adopt existing resources through import blocks after CloudFormation
has released every resource with both retention policies. Preserve physical names
and imported values, including generated IAM role names. Reject creations and replacements in the adoption plan. Four reviewed in-place
entries preserve behavior: three only add sensitive annotations, and the fourth
makes the existing implicit one-hour access/ID token lifetime explicit. Split S3 settings and notifications,
IAM inline policies and the shared SQS policy into the provider's resource model.
Protect the user pool and reports bucket with prevent_destroy and keep bucket
force_destroy false. This protects against replacement while the blocks remain
in configuration; it is not a backup or protection against console deletion.

Use separate AWS provider credentials for the main and parser accounts, with the
same main-account credentials for the us-east-1 auth alias. HCP exchanges OIDC
claims for short-lived roles in each account. Trust is restricted to the chosen
organization, project and workspace, with the audience aws.workload.identity;
only run_phase may vary. Account IDs are checked by providers. No permanent AWS
keys are stored in HCP or Git.

A contributor or assistant proposes HCL in a branch. A person reviews the refreshed
plan and merges it. HCP plans PRs and applies merged changes; the Makefile has no
apply target. GitHub Actions continues to deploy the ECS application through its
existing OIDC role. A change requiring a new cloud dependency is delivered in two
steps: apply compatible infrastructure first, then deploy dependent application
code. Removing an old dependency happens after all callers have moved away.
Emergency console fixes must promptly become reviewed HCL, before the next apply
would undo them. Assistants may draft and plan; they do not approve replacements
or perform a laptop apply.

## Alternatives

CloudFormation avoids operating our own state backend and offers rollback, but is
AWS-specific and retains its intrinsic-function and nested-stack overhead. CDK
would improve authoring in a general-purpose language but still produces
CloudFormation and retains the same provider boundary. OpenTofu offers an open
license and compatible HCL; it is a credible future option. Terraform is selected
here for the course's HCP workflow, provider tooling and multi-account/environment
workflow. External Google OAuth and GitHub resources can later join the same
review process; this migration does not claim to manage them already.

## Consequences

Non-secret dev values are configured in HCP workspace Terraform variables, with
a tracked terraform.tfvars.example for reproduction. Local terraform.tfvars is ignored. The Google OAuth secret
and report recipients are sensitive workspace Terraform variables. The database
URL stays in AWS Secrets Manager but is read into Lambda configuration by Terraform.
Sensitive values, including the Google secret and resolved database URL, also exist
in HCP state and possibly saved plans, historical state versions, local .env and
AWS service configuration. sensitive hides ordinary plan rendering, not state or
JSON exports. Only trusted operators receive workspace/state access. Local state,
plans, credential files and private migration snapshots must not enter Git or CI
logs. Rotate secrets if such artifacts leak. HCP API tokens remain in Terraform's
local credential store, never repository files.

If HCP is unavailable, running application resources continue to work, while
infrastructure changes wait. Do not start an independent local state. In an urgent
incident an authorized operator may make a documented AWS repair, followed by HCL
reconciliation before HCP resumes. For a prolonged outage, restore a securely
exported state version to a reviewed remote backend with locking, after disabling
all previous writers. Terraform does not automatically roll back failed applies;
inspect the partial state and real resources, fix the cause, then plan again.

Migration counts and evidence are tracked in [the runbook](../lab7-migration.md); they must be
updated after the actual adoption, rather than treating preparation as completion.
