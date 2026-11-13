# Lab 9 — Peach core monthly cost

USD before tax, no credits or discounts, 730 hours. The comparison uses the
lab's AWS us-east-1 pricing baseline and GCP us-central1, with a 0–1 ACU Aurora
Standard writer and a single zonal Cloud SQL Enterprise db-f1-micro. The AWS
side models the core only. Reports, parser, and third-party identity traffic
are outside both totals.

| Component | AWS inputs | GCP inputs |
| --- | --- | --- |
| Frontend, CDN, TLS | CloudFront Free flat-rate plan, including WAF | Firebase Hosting, below 10 GB stored and 360 MB transfer on every day |
| API | Lambda, 512 MiB x86, 200 ms per call, below 1M requests and 400,000 GB-s | Cloud Run request-based, 1 vCPU and 512 MiB, 200 ms per call, below 2M requests, 180,000 vCPU-s and 360,000 GiB-s |
| Database compute | Aurora Standard at $0.12/ACU-hour. Model 0.5 ACU while awake. After each isolated session add the configured five-minute idle timeout. | $0.0105/hour while running, with no automatic idle pause |
| Database storage and I/O | Assume 1 GB at $0.10/GB-month and two billed I/Os per API call at $0.20 per million. Actual Aurora I/O depends on cache and query behavior. | 10 GB SSD at $0.17/GB-month |
| Database network | API and DB in the same AWS region. No public DB IPv4 or cross-region transfer. | Cloud Run and Cloud SQL in the same region. Cloud SQL Auth Proxy over public IP. Idle public IPv4 is $0.01/hour while stopped. |
| Registry, secrets, logs | Assume one 0.2 GB ECR image at $0.10/GB-month, one Secrets Manager secret at $0.40/month and negligible logs/API calls. | Assume one image within Artifact Registry's 0.5 GB and one secret version within Secret Manager's six versions and 10,000 accesses. Logs below 50 GiB/month. |

Traffic assumption: 1,000, 8,800 and 36,500 calls across the three active
profiles, roughly 50 calls per active hour. These fit the API free tiers and
assume those quotas are unused by other workloads. Allow up to 1 GB of monthly
API egress and up to 100 MB/day of Hosting transfer. The continuously busy case
means continuous DB availability at the same modest load. It is not a
throughput benchmark.

| Traffic | Aurora awake h | AWS compute | AWS total | GCP compute if left running | GCP total if left running | GCP total if stopped outside the profile | Cheaper / deciding line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Nobody | 0 | $0.00 | $0.52 | $7.67 | $9.37 | $9.00 | AWS / database compute |
| Class demos, 10 × 2 h | 20.83 | $1.25 | $1.77 | $7.67 | $9.37 | $9.01 | AWS / database compute |
| Office hours, 22 × 8 h | 177.83 | $10.67 | $11.19 | $7.67 | $9.37 | $9.09 | GCP / database compute |
| Busy 24/7 | 730 | $43.80 | $44.33 | $7.67 | $9.37 | $9.37 | GCP / database compute |

AWS total = awake hours × 0.5 × $0.12 + $0.52 fixed + I/O. The stopped GCP
scenario = $1.70 + active hours × $0.0105 + remaining hours × $0.01, with
active hours of 0, 20, 176 and 730. The lab's $1.70 stopped example applies if
there is no billed idle address. With this architecture, deleting the instance
after the demo avoids the ongoing disk and address charges. Cloud Run's zero
minimum does not stop Cloud SQL. Increasing Cloud Run's minimum or switching to
instance-based billing can add compute cost independently.

These are list-price estimates. Calculator inputs are listed above. No shared
calculator estimate has been generated for this submission.

Sources: [AWS Pricing Calculator](https://calculator.aws/),
[Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator),
[Aurora](https://aws.amazon.com/rds/aurora/pricing/),
[CloudFront](https://aws.amazon.com/cloudfront/pricing/),
[Lambda](https://aws.amazon.com/lambda/pricing/),
[ECR](https://aws.amazon.com/ecr/pricing/),
[AWS Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/),
[Cloud SQL](https://cloud.google.com/sql/pricing),
[Cloud SQL public IP](https://docs.cloud.google.com/sql/docs/postgres/configure-ip),
[Cloud Run](https://cloud.google.com/run/pricing),
[Firebase Hosting](https://firebase.google.com/pricing),
[Google Cloud free tiers](https://cloud.google.com/free/docs/free-cloud-features).
