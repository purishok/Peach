# ADR 0006: Parse pasted agendas with Bedrock

## Context

People receive meeting agendas as emails and notes rather than form fields. The
product must suggest structured topics while leaving the final write to the
person. The database is private, there is no NAT gateway, every inference costs
money, and pasted text may contain hostile instructions.

## Decision

Use Claude Sonnet 4.5 through the Bedrock Converse API in `us-east-1`. This is
the Claude model that the available AWS account can invoke: attempts to use
Opus 5.5 through the Anthropic Messages API returned 403 even after the model
agreement became available. The model and API are configuration values, so a
future account can use the requested Messages API without changing the UI or
save path. The parser is a container Lambda outside the VPC. It verifies the
Cognito ID token, limits text to 10,000 characters, asks Claude for one tool
call, validates the result, and returns a suggestion. The browser shows that
suggestion in editable fields. Saving uses the existing authenticated API and
stores both the final agenda and the original suggestion. The model has no
database credentials and cannot write. The parser runs in AWS account
`985040259102`; the existing site, Cognito pool and main API remain in account
`505464394565`. The function accepts ID tokens from that Cognito pool.

## Alternatives

- Calling Bedrock from the API inside the VPC needs a paid interface endpoint
  or NAT gateway and couples a slow inference to the database path.
- Calling the Claude API directly would require a separate API key and bill;
  Bedrock uses the Lambda execution role and the existing AWS budget.
- Regular expressions cannot reliably recover topics, owners and relative
  dates from multilingual email and chat text.

## Consequences

At the [published Bedrock rates](https://aws.amazon.com/blogs/aws-cloud-financial-management/optimize-llm-costs-on-amazon-bedrock-from-billing-attribution-to-operational-telemetry/),
Sonnet 4.5 costs $3 per million input tokens and $15 per million output tokens.
The current noisy-note parse used 1,367 input and 142 output tokens, or
$0.006231 in model charges. The parser logs tokens, estimated model cost,
model, prompt version, latency and Cognito subject; it does not log the pasted
text. A $5 monthly AWS Budget emails the owner in the parser account. When
Bedrock is unavailable, the user can type the agenda in the same form; meetings,
tasks and reports keep working.

The parser image and Lambda are in `eu-north-1` and call Bedrock in
`us-east-1`. CloudFormation does not offer `AWS::Budgets::Budget` in
`eu-north-1`, so the budget is in a small `us-east-1` stack declared in
`infra/ai-budget.yml`. The estimate excludes Lambda, CloudWatch and data
transfer charges.
