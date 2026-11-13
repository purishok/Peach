# Lab 9 — submission evidence

- [Architecture decision](../adr/0009-google-cloud.md)
- [Terraform deployment and cleanup](../../gcp/README.md)
- [Costs for four traffic profiles](costs.md)

## BigQuery

Ran [the query](usa-names.sql) over BigQuery's public USA Names dataset in the
existing sandbox on 13 November 2026. The query summed registered male births
named Michael by year. It returned 20 rows and processed 161.77 MB. BigQuery
reported 162 MB as bytes billed, within the sandbox quota. No permanent dataset
or result table was created. The [CSV](usa-names.csv) contains all 20 results.

![BigQuery query and results](bigquery.jpg)

## Remaining live checks

| Check | Status |
| --- | --- |
| Firebase Hosting URL and authenticated Cloud SQL read | Pending an active Google Cloud Billing account, GCP deployment and Cognito redirect configuration. |
| Looker Studio chart | Pending Data Studio first-use terms. The live BigQuery connector also needs billing. The CSV connector can use the exported public query results without the live BigQuery connection. Use year as the ascending dimension and registered_births as the metric. |
| Dataflow and Vertex AI Studio | Pending a billing-enabled lab project. |

## Document AI OCR

Processed Google's **Expense** sample in the [public Document AI demo](https://docs.cloud.google.com/document-ai/docs/try-docai).
The OCR tab showed detected text such as `STOP&SHOP` alongside the bounding
boxes on the receipt. The Fields tab extracted line items and amounts,
including `JSPH ORG HUMMUS` at `5.99`.

![Document AI OCR result for the sample expense receipt](document-ai-ocr.jpg)

Document OCR is appropriate when the job is to transcribe a receipt or extract
its layout and field coordinates. An LLM is useful when a note implies
actions, owners or deadlines that must be interpreted in context. For a
photographed agenda, OCR can transcribe it before the LLM structures it.

In Lab 8, S3 holds payment data and Glue and Athena make it queryable.
On GCP, Cloud Storage holds the input, Dataflow can parse files and write
normalized rows, and BigQuery combines the SQL query engine and managed tables.
Looker Studio supplies the visualization. A BigQuery native table removes the
need to maintain a separate crawler and external-table metadata for those rows.
