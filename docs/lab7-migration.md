# Lab 7 — migration record

## Ownership transfer completed on 2026-10-29

HCP organization `Pitch_organisation`, project `Default Project`, workspace
`peach-dev` uses Remote execution, Terraform 1.13.5 and the locked AWS provider
6.70.0. Its VCS source is `purishok/Peach`, main, working directory infra.
Auto-apply remains disabled; plans are reviewed before HCP applies.

[PR #1](https://github.com/purishok/Peach/pull/1) added the Terraform root, Makefile,
pipeline integration and OIDC bootstrap policies. GitHub checks and the HCP PR plan
passed. Merge commit `43e069e61c55103d53a99352701e4c5b34362185` triggered
[the successful adoption run](https://app.terraform.io/app/Pitch_organisation/workspaces/peach-dev/runs/run-iX7mZn9E1RduKsWt).
The run source is `tfe-configuration-version`; no laptop apply was used.

| Former stack | Account / region | Live CF resources | Deletion result |
|---|---|---:|---|
| peach-auth | 505464394565 / us-east-1 | 5 | 5 DELETE_SKIPPED |
| peach-reports | 505464394565 / eu-north-1 | 18 | 18 DELETE_SKIPPED |
| peach-ai-sonnet | 985040259102 / eu-north-1 | 6 | 6 DELETE_SKIPPED |

The optional SES identity was never created by the reports stack. The failed
`peach-ai` stack and the separate `peach-ai-budget` stack were outside this transfer.
Network/API/database/site and GitHub OIDC infrastructure remains unchanged.

## Retention and plan review

Retention-only change sets were prepared from the **deployed** templates, keeping
all parameter values. Every resource received DeletionPolicy=Retain and
UpdateReplacePolicy=Retain. cfn-lint, AWS ValidateTemplate and service pre-deployment
validation passed. YAML intrinsic syntax was preserved to avoid a spurious
DirectModification caused by converting GetAtt from scalar to list form.
No resource properties were edited in the retention updates. A separate cfn-guard
compliance evaluation was not run; these were retention metadata changes.

Only after all retention policies were verified were the three stack records
deleted. All 29 resources were DELETE_SKIPPED and remained available. Terraform
then imported **40 resources, recreated 0, created 0 and destroyed 0**. Its provider
model splits the S3 bucket/settings/notification, IAM inline policies and the
shared SQS policy into separate addresses.

The reviewed plan contained four in-place entries. Google provider details and the
two report Lambda environments had identical before/after values; only sensitivity
annotations changed. Cognito's previously implicit access/ID validity became an
explicit one hour, preserving [AWS's documented default](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_CreateUserPoolClient.html).
The explicit values also avoid sending invalid zero token lifetimes while
normalizing units. There were no name changes, replacements or secret rotations.

Provider adoption details: generate_secret is omitted for the imported public
client because explicitly setting false produced a spurious replacement during
import planning. Service-populated Google details and username mapping are kept.
The existing CloudFormation log policy's wildcard suffixes were preserved; policy
cleanup requires its own reviewed change. No general ignore_changes masks drift.

## Preservation and state

HCP state serial 1 contains 40 managed resources. Checks confirmed the same:

- Cognito pool `us-east-1_Mqco1qka2`, with 4 users.
- Public browser client `1r45prm239cn18b3felrql6s2g`.
- Reports bucket `peach-reports-505464394565`, with 4 report objects.
- Parser URL `https://fe4pgnzbm33xjxngd34bmxm5su0flezb.lambda-url.eu-north-1.on.aws/`.
- Generated runtime-role names, permission statement IDs and event-source mapping.

The immediate post-adoption remote CLI plan reports
`No changes. Your infrastructure matches the configuration.` Its unmodified output
is [lab7-plan-after-migration.txt](lab7-plan-after-migration.txt), run
[run-obbbXx5LDvguLMNf](https://app.terraform.io/app/Pitch_organisation/workspaces/peach-dev/runs/run-obbbXx5LDvguLMNf).
The old three CloudFormation templates and imports.tf are removed after this check.

## Credentials and normal workflow

Read-only plan and separate scoped apply roles exist in each account. Their exact
workspace/phase OIDC subjects and inline policies are recorded in
[infra/bootstrap](../infra/bootstrap/README.md). The main plan role can read only
the existing database secret beyond ReadOnlyAccess. Apply policies have no resource
creation/destruction actions and restrict PassRole to existing runtime roles.
Further infrastructure operations need a reviewed bootstrap-policy change.

Google client secret and report recipients are sensitive HCP Terraform variables.
Non-secret inputs are workspace variables with terraform.tfvars.example as a
reference. Local tfvars, secrets, provider caches, state and saved plans are
excluded from CLI uploads; VCS runs receive only committed files. State and raw
plan JSON can contain secrets and must not be published. Only checked text logs
and screenshots are submission evidence.

GitHub Actions validates HCL and deploys application code separately. HCP plans PRs
and applies merges. A cloud dependency is applied before application code needs it;
removal follows application migration. Makefile has no terraform apply target.

## Follow-up verification

The follow-up PR removes migration files and changes the HCL log-retention default
from 14 to 30 days for the existing three Lambda log groups. The workspace override
is removed so this value is controlled by reviewed code. Its expected plan is
0 to add, 3 to change, 0 to destroy. This provides the small VCS change requested
by the lab; its apply and the timeout drift exercise are recorded in the final
submission evidence after they complete.

For a real emergency console repair, commit the intended HCL promptly: otherwise
the next apply restores the old code-defined configuration. HCP locking serializes
writers; local state in Git exposes secrets/history and cannot provide that lock.
Recover lost state from a secured HCP version or reconstruct imports after inventory;
state loss does not delete AWS resources. Staging requires separate state and
isolated names, not a different tfvars file applied to this dev state.
