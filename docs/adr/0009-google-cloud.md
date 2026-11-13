# ADR 0009 — Deploy Peach's core to Google Cloud

Date: 2026-11-13

Status: Accepted for the lab

Peach uses FastAPI, SQLAlchemy and Alembic on PostgreSQL, with a statically
exported Next.js frontend. Deploy a separate, initially empty GCP environment in
us-central1. Existing AWS users keep their Cognito identities. Their GCP tasks
and meetings are independent from the AWS copy.

| AWS service or capability | GCP counterpart | Peach decision |
| --- | --- | --- |
| S3 + CloudFront + WAF | Firebase Hosting | Replace static delivery with Firebase CDN and managed TLS. Route /api/** to Cloud Run. A separate WAF is outside this lab. |
| Lambda and function URL | Cloud Run | Replace core API compute with the existing Uvicorn container. Start at zero instances and cap the revision at one. |
| ECR | Artifact Registry | Replace the image store for the GCP build. Pin the Cloud Run image by digest. |
| Aurora Serverless v2 | Cloud SQL PostgreSQL | Replace with one zonal Enterprise db-f1-micro and 10 GB SSD. Start with Alembic migrations and synthetic demo data. |
| DynamoDB if using NoSQL | Firestore | Drop the NoSQL alternative. Peach uses SQL constraints and relational ownership. |
| Cognito with Google | Identity Platform / Firebase Authentication | Keep Cognito, Google login and JWT validation. Add the Firebase callback and logout URLs to the Cognito client before deployment. |
| EventBridge Scheduler | Cloud Scheduler | Keep the weekly AWS report schedule with its existing worker. |
| SQS | Pub/Sub or Cloud Tasks | Keep the report queue and its delivery/retry behavior on AWS. |
| S3 event to Lambda | Cloud Storage + Eventarc to Cloud Run | Keep AWS report object processing and its trigger with the worker. |
| SES | External email provider or SES | Keep SES. The Lambda execution role authorizes SES, so there is no email API key. |
| Bedrock | Vertex AI | Keep the existing Lab 6 parser and its AWS credentials. Agenda entry remains available manually on the GCP site. |
| SSM / Secrets Manager | Secret Manager | Use GCP Secret Manager for the generated GCP database URL. Keep the AWS secrets with their services. |
| CloudWatch Logs | Cloud Logging | Replace logging for the GCP runtime with Cloud Run stdout/stderr. Keep AWS logs for AWS resources. |
| IAM roles | Service accounts + IAM roles | Separate deployment and runtime service accounts. Use short-lived ADC impersonation locally and repository-scoped federation for any future CI. |
| Terraform AWS provider | Terraform Google provider | Use the independent HCP workspace peach-gcp-lab9 for Google Cloud. |

Cloud SQL keeps the schema and queries and puts the database close to Cloud Run.
Keeping it on continuously gives immediate access and incurs compute charges
24/7. Stopping it outside demos sacrifices availability and still leaves disk
and idle public IPv4 charges. Firestore could cost $0 at this workload, but
requires a redesign of reads, ownership, constraints and migrations. Keeping
Aurora across clouds preserves SQL but adds network latency, egress and a
private connectivity problem. It could also keep Aurora awake.

Reports stay on AWS because they depend on the existing schedule, queue,
Aurora data, storage and SES. The parser stays on AWS because the current
Bedrock implementation already runs there and has separate quotas and cost
controls. It needs a CORS change before the Firebase frontend can call it
directly.
