# Lab 7 — migration runbook and evidence

## Actual status on 2026-10-29

Migration is in progress. HCP organization `Pitch_organisation`, project
`Default Project`, workspace `peach-dev` is configured for Remote execution,
Terraform 1.13.5, GitHub `purishok/Peach`, branch main, working directory infra.
The two-account OIDC **plan** succeeds in HCP. The first two speculative runs are
`run-XG62e9bHqrkuzeyN` and `run-dSQS5T6Q3jjBLWaZ`.

- 40 imports cover all 29 live CloudFormation resources in auth, reports and AI.
  S3 configuration, IAM inline policies and the shared SQS policy are split into
  separate Terraform resources. There are no planned resource creations or deletions.
- Four in-place adoption entries are understood and reviewed: Google provider and
  both report Lambda updates have identical before/after values, with only sensitive
  metadata added. Cognito's previously implicit access/ID token lifetime is now
  explicitly one hour. This preserves AWS's documented default and avoids passing
  invalid zero validity values when normalizing token units. See
  [AWS CreateUserPoolClient](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_CreateUserPoolClient.html).
- HCP non-secret inputs have been reconciled with the existing deployment. The
  actual secrets remain sensitive workspace variables. The non-secret reference
  is `infra/terraform.tfvars.example`; local terraform.tfvars stays ignored.
- Main-account apply role is created with exact apply-phase/workspace trust,
  ReadOnlyAccess and narrowly scoped writes. See `infra/bootstrap/`.
- Retention-only CloudFormation changesets for peach-auth and peach-reports passed
  cfn-lint and AWS template/service validation and were executed. No stack has
  been deleted and no Terraform apply has run. The AI stack retention update and
  AI apply-role bootstrap require renewal of the expired bedrock-test session.
- The caller's pre-existing .env.example edits are excluded from the migration commit.

All three stacks must be retained and all apply credentials tested before release.
Do not confuse a speculative plan with completed adoption or submission evidence.

## 1. Configure HCP before releasing any stack

Create one Remote workspace, e.g. peach-dev, connected to purishok/Peach, branch
main, working directory **infra**. PRs receive speculative plans; merges enqueue
normal runs. Keep automatic apply OFF during migration and review each plan.
Use the locked CLI version, then set TF_CLOUD_ORGANIZATION and TF_WORKSPACE in
the local shell (and HCP environment if needed by the cloud block).

Already configured: set sensitive Terraform variables `google_client_secret` and
`report_recipient_emails` in HCP. Keep their exact current values. Non-secret dev
inputs are workspace Terraform variables, with terraform.tfvars.example as reference. Never put `.env` or permanent AWS keys in HCP.
The current reports image URI preserves the existing Lambda image; do not use an
ECS-only image for Lambda. Local terraform.tfvars is ignored and is not uploaded by VCS. Do not put secrets
in the tracked example. Workspace variables supply the remote run inputs.

The main and parser accounts need separate HCP OIDC roles. Each trusts the
app.terraform.io OIDC provider, audience aws.workload.identity, with subject:

```text
organization:ORG:project:PROJECT:workspace:peach-dev:run_phase:*
```

Use StringEquals for the audience and StringLike for that exact workspace subject.
Scope role permissions to the services/resources it owns. Main-account actions
include cognito-idp management, lambda management, S3 configuration, SQS,
Scheduler, logs, specific EC2 security group/VPC endpoint actions, and
secretsmanager:GetSecretValue on the existing database secret. Restrict
`iam:PassRole` to the three runtime roles and the Lambda/Scheduler service
principals. The parser role manages its own Lambda, logs and IAM execution role;
the Lambda runtime's Bedrock permission is separate from the Terraform run role.
AdministratorAccess is only the lab's bootstrap shortcut, not a requirement.

HCP environment variables:

| Key | Value |
|---|---|
| TFC_AWS_PROVIDER_AUTH | true |
| TFC_AWS_RUN_ROLE_ARN | main account role ARN |
| TFC_AWS_PROVIDER_AUTH_AI | true |
| TFC_AWS_RUN_ROLE_ARN_AI | parser account role ARN |

`versions.tf` maps HCP's injected `tfc_aws_dynamic_credentials` paths to the default,
auth and AI provider aliases. The auth alias uses the main account credentials.
Leave ai_profile null remotely. For local read-only AI inventory, use
`TF_VAR_ai_profile=bedrock-test`, with no overriding AWS environment keys.
See [HashiCorp's multiple AWS credential configuration](https://developer.hashicorp.com/terraform/cloud-docs/dynamic-provider-credentials/aws-configuration).

## 2. Inventory AI and match the whole configuration

Verified with `aws sts get-caller-identity --profile bedrock-test` that the account
is 985040259102. Read peach-ai-sonnet's live parameters, outputs, resource IDs,
Lambda configuration and role policy. The root now matches the deployed role,
permissions, function URL, image, API, model, concurrency, timeout, logging and tags.
The existing configuration uses Converse, Sonnet 4.5 and unreserved concurrency,
unlike ai.yml's original defaults. All seven AI import blocks are included.
Keep the aws.ai account check and never import a same-named function from the
main account. Recheck account identities if credentials are refreshed again.
The budget stack is deliberately outside these three migrated stacks.

Run a speculative plan while CF still owns the resources. Iterate until the
migration plan contains only imports: **0 to add, 0 to change, 0 to destroy**.
The 40 import blocks cover all 29 live CloudFormation resources across the three
stacks, including the Terraform-specific resource splits described above. There must be no resource replacement, including
the public Cognito client that the browser depends on.

Provider adoption details: omit `generate_secret` for the imported public client
(the provider reads no secret from AWS); setting it explicitly to false caused a
spurious replacement in the initial import plan. Preserve service-populated Google
provider details and username mapping. CloudFormation's LogGroup.Arn contains
`:*`, so the existing inline policy's two wildcard suffixes must be preserved in
this import; tighten it in a separate reviewed change. Do not hide general drift
with ignore_changes. Keep resource tags equal to the observed values during
adoption; introduce additional default tags later through review.

## 3. Release CloudFormation without deleting resources

Do not deploy a stale local template just to set retention. Prepare a copy of the
**currently deployed** template with only the two retention policies added:

```bash
uv run --with pyyaml python scripts/prepare-terraform-retain.py --stack peach-auth --region us-east-1 --output /tmp/peach-auth-retain
uv run --with pyyaml python scripts/prepare-terraform-retain.py --stack peach-reports --region eu-north-1 --output /tmp/peach-reports-retain
uv run --with pyyaml python scripts/prepare-terraform-retain.py --stack peach-ai-sonnet --region eu-north-1 --profile bedrock-test --output /tmp/peach-ai-retain
```

The helper accepts JSON and uses a tag-aware PyYAML loader for YAML so that
CloudFormation intrinsic functions are preserved. The repository templates also
contain Retain on every resource, including children and log groups.

For each stack, inspect a change set using its retain.json and parameters.json,
CAPABILITY_IAM/CAPABILITY_NAMED_IAM as required, and unchanged parameter values.
Review that the change set only changes retention metadata. Execute that reviewed
change set and wait for UPDATE_COMPLETE. Fetch the deployed template again and
verify **every resource** has both policies set to Retain. Save outputs/IDs and
check that every import target is present before proceeding.

Only with HCP credentials and import-only plans ready, delete those three stacks
and wait for stack-delete-complete, using the correct account/profile/region.
Inspect DELETE_SKIPPED events and recheck the pool's user count, reports bucket
contents, queue URLs and Lambda URLs. Do not delete users, empty buckets, rotate
public client IDs or remove Lambda permissions/notifications. Other stacks remain.

## 4. Adopt through HCP, then remove the old definitions

Push the migration branch, review its HCP plan, merge, then approve the HCP run
that imports existing resources. Re-plan after the CF release before approving:
import-only means imports plus **no** creates, updates or destroys. If a plan shows
changes, correct the HCL instead of approving a mixed adoption/change plan.

After successful adoption, remove imports.tf and the three old templates
(cognito.yaml, reports.yml, ai.yml) in a follow-up commit. Keep network/API/site,
GitHub OIDC and ai-budget.yml unchanged. Update the ADR status and the exact import
count in this document. Preserve the final plan output as described below.

## 5. Prove the VCS road, drift and idempotency

Make a small reviewed change, e.g. increase log_retention_days from 14 to 30.
Open a PR and read its plan, merge, approve the VCS-triggered HCP apply, and capture
**Apply finished** with workspace/run/commit visible. A CLI-triggered run is not
submission item 2. If auto-apply is enabled after migration, branch protection and
plan review remain mandatory.

For drift, change parser timeout in AWS, start an HCP plan-only run and observe the
planned restoration. Restore it with a reviewed HCP apply. A real emergency fix
must be committed as HCL so that the next apply preserves the intended repair.

Run `terraform -chdir=infra plan -no-color` against the HCP workspace after the
migration and save its real output privately first. Submit the output ending in
`No changes. Your infrastructure matches the configuration.` after checking for
secrets. Never manufacture this message or reuse an import-plan summary as proof.

Submission checklist (all still pending until the corresponding live action):

- Commit or merged PR URL with completed handover, Makefile, README and ADR.
- Screenshot of a successful VCS-triggered HCP apply.
- Post-migration No changes plan output.
- Exact final imported/recreated counts; explain any recreation explicitly.

## Discussion notes

Changing the reports bucket's `bucket` name forces replacement. prevent_destroy
blocks that plan; bypassing the protection and destroying the bucket risks losing
reports. Cognito immutable username/schema settings can also make replacement or
an API rejection necessary; preserve pool IDs and back up before deliberate changes.
State deletion loses mappings and recorded attributes, not the AWS resources.
Recover a locked backend state version or reconstruct imports after inventory.
Git is unsuitable for state because it exposes secrets through history and does
not provide an apply lock. HCP locking serializes writers, but does not replace
human review or prevent a valid destructive plan.

For staging, propose another workspace/state, environment inputs and isolated
names (including generated role names), preferably a shared module once the first
migration is finished. Do not reuse this dev import file or apply stage variables
to dev state. A partner copy gets its own workspace, account credentials and
branding/domain inputs. No assistant should approve or execute that deployment
without review of the actual plan.
