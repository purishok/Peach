# ADR 0006: Parse pasted agendas with Bedrock

## Context

People receive meeting agendas as emails and notes rather than form fields. The
product must suggest structured topics while leaving the final write to the
person. The database is private, there is no NAT gateway, every inference costs
money, and pasted text may contain hostile instructions.

## Decision

Use Claude Opus 5.5 through the Anthropic Messages API on Amazon Bedrock in
`us-east-1`. The parser is a container Lambda outside the VPC. It verifies the
Cognito ID token, limits text to 10,000 characters, asks Claude for one tool
call, validates the result, and returns a suggestion. The browser shows that
suggestion in editable fields. Saving uses the existing authenticated API and
stores both the final agenda and the original suggestion. The model has no
database credentials and cannot write. Opus is the baseline to measure against
Haiku on the five lab inputs before optimizing cost.

## Alternatives

- Calling Bedrock from the API inside the VPC needs a paid interface endpoint
  or NAT gateway and couples a slow inference to the database path.
- Calling the Claude API directly would require a separate API key and bill;
  Bedrock uses the Lambda execution role and the existing AWS budget.
- Regular expressions cannot reliably recover topics, owners and relative
  dates from multilingual email and chat text.

## Consequences

At list prices, Opus costs $4 per million input tokens and $20 per million
output tokens; the parser logs actual tokens and computed cost per successful
parse with the model, prompt version and latency. The Lambda logs the Cognito
subject, not the pasted text. A $5 monthly AWS Budget emails the owner. When
Bedrock is unavailable, the user can type the agenda in the same form; meetings,
tasks and reports keep working.

In this account, ECR repository creation is blocked in `us-east-1`, so the
parser Lambda uses the existing ECR in `eu-north-1` and calls Bedrock in
`us-east-1`. CloudFormation does not offer `AWS::Budgets::Budget` in
`eu-north-1`; the budget is therefore in a small `us-east-1` stack declared in
`infra/ai-budget.yml`.
