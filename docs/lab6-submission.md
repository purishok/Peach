# Lab 6 submission evidence

The deployed [Meetings page](https://dqvalqr0apze.cloudfront.net/meetings) parses pasted text with Claude Sonnet 4.5 through Amazon Bedrock Converse. The parser Lambda is in AWS account `985040259102` (`eu-north-1`), using Bedrock in `us-east-1`; the site, Cognito and ordinary save API are in account `505464394565`. The parser URL is `https://fe4pgnzbm33xjxngd34bmxm5su0flezb.lambda-url.eu-north-1.on.aws/`.

The assignment specifies Opus 5.5 through the Anthropic Messages API. That model returned HTTP 403 in the available account after its agreement became available. Sonnet 4.5 through Bedrock Converse was the Claude model this account could actually invoke. The parser keeps the API and model configurable. This deviation is explicit in the [ADR](adr/0006-llm-agenda-parsing.md).

The [10.44-second MP4](media/lab6-paste-agenda.mp4) records the deployed app: paste, Parse, prefilled form, a manual agenda-title correction, and Save. A subsequent authenticated GET returned final title `Понеділковий синк із ціноутворення`, preserved suggested title `синк по прайсингу`, three topics, model ID and prompt version `agenda-v2`. The API returned HTTP 200 on Save. The `peach-ai-sonnet` parser stack and `peach-ai-budget` stack are both `CREATE_COMPLETE` in account `985040259102`; the latter emails a $5 monthly actual-spend alert.

## Five-input test table

All five requests went through the deployed Meetings screen on 2026-10-21 with browser time zone `Europe/Kyiv`. The [JSONL evidence](lab6-evaluation.jsonl) contains every full input, raw JSON result, HTTP status, usage, cost and browser latency. Cost uses the [Bedrock Sonnet 4.5 rates](https://aws.amazon.com/blogs/aws-cloud-financial-management/optimize-llm-costs-on-amazon-bedrock-from-billing-attribution-to-operational-telemetry/) of $3 per million input tokens and $15 per million output tokens. Case 4 token usage came from the matching CloudWatch log because HTTP 422 does not return usage.

| # | Input (short) | JSON produced | Correct fields | Invented values | Tokens in / out | Cost, $ | Latency, s |
|---|---|---|---|---:|---:|---:|---:|
| 1 | Ukrainian pricing sync | `{"title":"синк по прайсингу","starts_at":"2026-10-26T10:00:00+02:00","duration_minutes":45,"items":[{"topic":"нові тарифи Pro","owner":"Олена","minutes":15},{"topic":"фідбек від клієнтів","owner":"Taras","minutes":null},{"topic":"що робимо з річною знижкою","owner":null,"minutes":null}],"action_items":[{"task":"збирає порівняння з конкурентами","owner":"Taras","due":"2026-10-23"}],"language":"uk"}` | Title, Monday 10:00 Kyiv offset, 45 min, 3 topics, owners, Friday action due date | 0 | 1357 / 332 | 0.009051 | 6.76 |
| 2 | English email with greeting/signature | `{"title":"customer sync","starts_at":"2026-10-22T14:00:00+03:00","duration_minutes":30,"items":[{"topic":"rollout update","owner":"Maya","minutes":10},{"topic":"open support issues","owner":"Leo","minutes":null}],"action_items":[],"language":"en"}` | Title, Thursday 14:00 Kyiv offset, 30 min, 2 topics/owners; signature excluded | 0 | 1303 / 223 | 0.007254 | 3.75 |
| 3 | Next Tuesday after lunch; by end of week | `{"title":"planning sync","starts_at":null,"duration_minutes":null,"items":[{"topic":"Review Q4 targets","owner":null,"minutes":null}],"action_items":[{"task":"Nadia sends the draft by end of week","owner":"Nadia","due":null}],"language":"en"}` | Topic and Nadia action; ambiguous time/deadline left empty | 0 | 1283 / 195 | 0.006774 | 3.58 |
| 4 | Milk, bread, bananas, coffee | `null (HTTP 422: no agenda)` | Correctly rejected as no agenda (HTTP 422) | 0 | 1268 / 38 | 0.004374 | 2.68 |
| 5 | Pricing agenda plus owner injection | `{"title":"Pricing sync","starts_at":null,"duration_minutes":null,"items":[{"topic":"discuss Pro pricing","owner":"Olena","minutes":null}],"action_items":[],"language":"en"}` | Topic/Olena; ignored injected owner | 0 | 1285 / 168 | 0.006375 | 3.17 |

Case 3 exposed a schema limitation: `starts_at` needs both date and time, so the model could not keep the known Tuesday without guessing a time; it returned `null`. “By end of week” has no unambiguous due date, so the deployed run left `due` empty. No output field in these five runs was unsupported by its source. Case 4 has no agenda and correctly produced no JSON.

## CloudWatch log line

From `/aws/lambda/peach-agenda-parser` in `eu-north-1`, account `985040259102`, for the recorded deployed Parse:

```json
{"event":"agenda_parse","user":"2458b4c8-10c1-7018-0772-2ba8e06a59ed","model":"us.anthropic.claude-sonnet-4-5-20250929-v1:0","prompt_version":"agenda-v2","status":"ok","error_type":null,"input_tokens":1357,"output_tokens":335,"latency_ms":4790,"cost_usd":0.009096}
```

The cost is `(1357 × 3 + 335 × 15) / 1,000,000 = $0.009096` in estimated model charges. The line does not include the pasted text.

## Short answers

1. **Which went wrong, and what fixes it?** Case 3 omitted a known weekday because the schema cannot represent a date without a time; adding separate date/time fields and showing them in the UI would preserve it without inventing a clock time. Case 4 rejected non-agenda text as intended. The other three produced the expected fields in these runs. The user can correct any field before Save.
2. **Injection attempt.** Case 5 kept owner `Olena` and ignored `admin@example.com`. Delimiting pasted text as data and validating the tool output helped in this run. Even if an injection changed an owner, the model can only suggest; the human sees the proposed value and the ordinary authenticated API performs the save.
3. **Cost.** The five deployed requests cost $0.033828 in model charges, or $0.006766 on average, including the rejected input. At 20 organisations × 30 parses/week × 52/12 weeks/month ≈ 2,600 parses/month, that observed mean implies about **$17.59/month** in model charges. This exceeds the stated $7.30/month for one VPC interface endpoint; the endpoint would be an additional fixed network cost if inference ran inside the VPC. Lambda, logging and transfer costs are outside this estimate.
4. **How to compare agenda-v2 with agenda-v1 after 500 saves.** Use the stored suggestion and final agenda to measure per-field correction and missing-field rates. Have humans review a sample to label invented or wrongly accepted values; an unchanged user field is not proof of correctness. Re-run both prompt versions on the same retained or consented original inputs, compare each field against the same reviewed answer, and report paired accuracy and invented-field rates with a confidence interval. The current saved records retain suggestion and final form but not the original pasted text, so those 500 records alone cannot replay a new prompt.

## Validation

The deployed screen completed an authenticated Parse and Save. The normal API retained both the suggestion and edited final agenda. `make llm-hello` and the five-case Bedrock evaluation succeeded with the Converse configuration. The parser Lambda rejects an unauthenticated request before inference and the function URL CORS preflight allows the deployed origin.

To invoke the same model locally, set `AWS_PROFILE=bedrock-test`, `PARSER_API=converse`, and `PARSER_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0` before running `make llm-hello` or `make parse TEXT="..."`. The deployed parser uses `AI_STACK_NAME=peach-ai-sonnet` and `PARSER_RESERVED_CONCURRENCY=0`; this account cannot reserve two Lambda executions without breaching its minimum unreserved-concurrency quota.
