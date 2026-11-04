# Lab 8: payments batch and streaming

This directory is isolated from the Peach application and its Terraform state.
Read `submission/report.md` for the measured results and completion status.
AWS execution completed in eu-north-1, approved because the organization SCP
blocks the required services in us-east-1. A verified AWS Console screenshot is included
as `submission/athena-console.png` and in the evidence archive.
The input is the supplied public dataset, never a generated replacement.

## Setup

```sh
cd labs/lab8
mkdir -p data evidence sql submission
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
docker compose up -d
docker compose exec redpanda rpk topic create payments --partitions 3
aws s3 cp s3://ucu-ooad-lab8-payments/payments/dt=2026-10-01/events.jsonl data/day.jsonl --no-sign-request --region us-east-1
```

Console: http://localhost:8088. Port 8080 was occupied by an existing service on
this laptop. Set `LAB8_CONSOLE_PORT=8080 docker compose up -d` on a free port to
use the exact port in the assignment. Kafka: localhost:19092 (IPv4).
The local single broker has three partitions and replication factor one; this
demonstrates consumer parallelism, not broker failure tolerance.

## Local replay and consumer

In separate terminals:

```sh
.venv/bin/python stream.py consume --topic payments --group lab8 --state data/manual.sqlite
.venv/bin/python stream.py produce --topic payments
```

Producer defaults to 20 payments/s averaged over the replay. Since each payment
has several events, the event rate is higher. It sorts a real day by `receivedAt`
and uses `invoiceId` as the Kafka key. `--failure30` deterministically assigns
terminal status using SHA-256(invoiceId) modulo 100, so the failure share is
approximately 30%; it also updates finalAmount and failureReason consistently.
This modifies the supplied events for the required experiment, not a generator.
`--rate 2000` accelerates a full day; timestamps inside events do not change.

The consumer uses UTC one-minute **event-time** windows. Its watermark is the
minimum of the maximum `modifiedDate` observed in all three partitions, minus
`--wait` seconds (120 by default). Until all partitions have a timestamp it
does not close windows. An unseen event whose window has already closed is
rejected and counted as late. This is a conservative partition-aware watermark;
an idle partition holds it back. Real deployments need an explicit idle-source
policy. The final few windows remain open until the finite replay is explicitly
finalized. Waiting 120 seconds refers to replayed event time, not laptop time.

The denominator is terminal payments, not all status transitions. Exact repeated
events are discarded first; each invoice has at most one current terminal
contribution. Newer corrections retract the previous contribution if that
window is still open; corrections to closed windows are counted separately.
Alerts use a strict `failure / terminal > 0.10` threshold. Small windows can
trigger an alert with one failure; a production rule would also require a
minimum sample size and possibly consecutive breached windows.

State and the next offset commit atomically in SQLite before the Kafka offset
commit. Assignment seeks to that stored next offset. This gives durable local
counting across restarts, while printing and SNS publishing remain at-least-once
side effects. The SQL outbox is the authoritative window result if the process
stops between writing state and printing a line. Two consumers on this laptop
share one SQLite file and use WAL plus a busy timeout; this is a lab design,
not a distributed state store for different machines. Use a distinct database
file for every independent topic/experiment; offsets are keyed by partition.

To start a second consumer, use the same topic, group, wait and state file and
add `--client two`. Check group ownership with:

```sh
docker compose exec redpanda rpk group describe lab8
```

After stopping the producer and all consumers, finalize the finite replay:

```sh
.venv/bin/python stream.py summarize --state data/manual.sqlite --output evidence/manual.json
```

`experiments.py` automates baseline, a real 60-second consumer interruption,
two consumers, 30% failures, and zero grace. Each experiment has a separate topic
and durable state file. Full runs are accelerated; the restart still lasts a
real minute. Fresh runs require fresh topic names/state. Existing successful
baseline/restart artifacts are reused by the supplied runner to preserve them.

```sh
.venv/bin/python experiments.py
.venv/bin/python analyze_local.py
.venv/bin/python -m unittest -v test_stream.py
```

`seen`, invoice state and window/outbox tables grow in this teaching version.
Production needs bounded state: expire only after the watermark plus the
maximum supported replay/dedup horizon, coordinate TTL with log retention and
offset recovery, and keep final reports outside the live state. Expiring a key
too soon allows an old duplicate to count again. Redis TTL or Flink-managed
checkpointed state can replace SQLite; a consumer group alone never deduplicates
business events.

## Batch on AWS

Use an authorized account allowing Athena, Glue, S3, Kinesis, Firehose, Lambda,
IAM and SNS. The assignment specifies `us-east-1`; the approved actual run uses
`eu-north-1` because of the SCP. Credentials stay in the AWS credential provider chain.
The default profile on this laptop was blocked by an organization SCP when
creating the lab bucket; see the report. No SCP or existing IAM policy is changed.

```sh
export AWS_PROFILE=bedrock-test
export LAB8_REGION=eu-north-1
export LAB8_BUCKET=peach-lab8-985040259102-eu-north-1
.venv/bin/python batch.py copy --via-local --bucket "$LAB8_BUCKET"
.venv/bin/python batch.py batch --bucket "$LAB8_BUCKET"
.venv/bin/python batch.py crawler --bucket "$LAB8_BUCKET"
```

`copy` creates a private bucket and attempts AWS CLI CopyObject. The actual
run used `--via-local`: anonymous public source downloads followed by
authenticated AWS CLI uploads. Direct CopyObject was denied. All 31 source
objects (1,260,672,849 bytes) were verified against destination sizes.
This approved regional deviation is not free same-region copying. `batch` saves the exact submitted SQL, query execution IDs, CSV results,
bytes scanned and durations from Athena's service API, with result reuse off.
The database is `peach_lab8`. Dates stay ISO strings at the raw JSON boundary
and are explicitly parsed in queries. Money uses integer minor units and
decimal arithmetic. Currencies are grouped separately. Peak hours use UTC
`createdDate` and count one payment once. The failure denominator is the set of
terminal payments; this matches the stream's business metric.

`payments` removes exact row duplicates, then chooses the latest modifiedDate
per invoice across **all** day partitions. Deterministic tie breakers prefer a
terminal status and later receipt. No latest-selection query filters a day
before choosing the invoice's final status. `payments_parquet` is Snappy Parquet
partitioned by dt. CTAS requires an empty curated prefix and a new table name;
do not rerun it blindly. There are 31 partitions, below Athena's CTAS partition
write limit of 100. SQL-only rendering without AWS is available:

```sh
.venv/bin/python batch.py sql --bucket "$LAB8_BUCKET"
```

Scale counts distinguish exact duplicates from legitimate multiple status
events per invoice. The lateness query reads raw events, including duplicates,
and measures both >60s and >3600s, as requested in the two different places in
the assignment. Comparing JSON and Parquet includes the cost of on-query
deduplication for JSON versus precomputed final payments for Parquet; it is a
practical pipeline comparison, not a file-format-only benchmark. CTAS itself
also incurs a scan and S3 storage/write cost. Scanned bytes times the regional
Athena price is an estimate; include per-query billing rounding/minimums and
use actual billing records for a final invoice.

## Cloud stream

```sh
.venv/bin/python cloud.py run --bucket "$LAB8_BUCKET"
```

The producer takes the first 3,000 events from that day's receivedAt-sorted
events, with the deterministic failure experiment applied. It writes newline
delimited JSON into a provisioned one-shard Kinesis stream. PutRecords retries
only failed entries; retries may change per-key order, so downstream SQL uses
event timestamps and deduplication, not delivery position, to choose final state.
Firehose buffers to S3; the table covers only `stream/`, never the original
`payments/` data. The script polls Athena for complete sample delivery before
deleting either stream. It saves the final query and the Lambda SNS message IDs.

A Lambda tumbling window aggregates terminal failures and publishes alerts to
SNS. This demonstration has no external SNS subscribers. Its one-minute
windows use **Kinesis insertion time**, as AWS Lambda defines them, not the
original October modifiedDate. Exact duplicates are remembered only inside each
arrival-time window; cross-window retries need external deduplication. With one
shard there is no cross-shard aggregate. This is deliberately described as a
different clock/guarantee from Part 3, not an equivalent Flink implementation.

`run` attempts teardown in `finally`. Verify `evidence/cloud-cleanup.json` and
AWS state. If an interrupted run leaves resources, execute:

```sh
.venv/bin/python cloud.py cleanup --bucket "$LAB8_BUCKET"
```

The cleanup deletes only the dedicated `peach-lab8` streams/function/topic and
stream roles, retaining S3 and Athena/Glue evidence. After exporting the crawler schema/history, delete its configuration and role
with `python batch.py crawler-cleanup --bucket "$LAB8_BUCKET"`. S3 data and
CloudWatch logs continue to incur small storage charges until removed. Do not
remove the evidence before submitting.

## Sources

To rebuild the written report on this Mac after completing cloud evidence:
when starting from the ZIPs, extract code.zip into a directory and evidence.zip
into its `evidence/` subdirectory. Then
install `requirements-report.txt`, run `build_submission.py`. The script reads the saved measured AWS evidence.
The real AWS Console screenshot is included as `athena-console.png`. The
additional `cloud-query-export.png` remains labeled as an API export.
The report uses the Mac's Arial fonts. PDF QA uses Poppler's `pdftoppm`.

- [Athena JSON SerDe](https://docs.aws.amazon.com/athena/latest/ug/json-serde.html)
- [CTAS limits](https://docs.aws.amazon.com/athena/latest/ug/ctas-considerations-limitations.html)
- [Glue crawlers](https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html)
- [Lambda Kinesis tumbling windows](https://docs.aws.amazon.com/lambda/latest/dg/services-kinesis-windows.html)
- [Firehose permissions](https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html)
- [Kinesis pricing](https://aws.amazon.com/kinesis/data-streams/pricing/)
- [Firehose pricing](https://aws.amazon.com/firehose/pricing/)
- [Athena pricing](https://aws.amazon.com/athena/pricing/)

## Measured AWS execution

- Region: eu-north-1, account 985040259102, private bucket peach-lab8-985040259102-eu-north-1.
- Month: 3,030,197 events, 1,000,000 invoices, 30,197 exact duplicates.
- Late >60s: 60,824; late >1h: zero. Latest failures: 60,180.
- JSON scans 1,260,692,423 bytes per turnover/failure/hour query.
- Parquet scans 6,389,672 / 675,513 / 6,545,829 bytes respectively; all CSVs match.
- Cloud: 3,000 accepted and delivered events, 989 invoices, 988 terminal, 295 failed.
- Four SNS MessageIds logged; Kinesis, Firehose, Lambda, SNS, roles and crawler removed.
- Raw/curated/stream data, Data Catalog tables and logs remain as evidence.
- Cost is an estimate from Price List API and service usage, not a posted invoice.

The verified screenshot is `submission/athena-console.png`. It shows account
985040259102, Europe (Stockholm), the SQL, Completed status, all four result
rows and runtime 441 ms, matching query 51754667-06cb-44df-854c-244a4262c465.
Both archives include the original PNG; the report includes a preview.
