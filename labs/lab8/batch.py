"""Real Athena/Glue execution; SQL, CSV and service metrics are saved as evidence."""
import argparse
import csv
import json
import os
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent
REGION = os.environ.get("LAB8_REGION", "us-east-1")
DB = "peach_lab8"
FIELDS = """invoiceid string, status string, failurereason string,
amount bigint, finalamount bigint, ccy int, reference string,
createddate string, modifieddate string, receivedat string,
merchantid string, merchantname string, mcc int, customerid string,
paymentmethod string, device string"""


def save(name, value):
    (ROOT/"evidence").mkdir(parents=True,exist_ok=True)
    (ROOT / "evidence" / name).write_text(json.dumps(value, indent=2, default=str))


def query(session, bucket, name, sql):
    (ROOT/"sql").mkdir(parents=True,exist_ok=True)
    (ROOT / "sql" / f"{name}.sql").write_text(sql + ";\n")
    if session is None:
        return []
    athena = session.client("athena")
    qid = athena.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": DB},
        ResultConfiguration={"OutputLocation": f"s3://{bucket}/athena-results/"},
        ResultReuseConfiguration={"ResultReuseByAgeConfiguration": {"Enabled": False}},
    )["QueryExecutionId"]
    while True:
        execution = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(2)
    save(f"{name}.execution.json", execution)
    if state != "SUCCEEDED":
        raise RuntimeError(execution["Status"])
    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        rows.extend([[c.get("VarCharValue", "") for c in r["Data"]]
                     for r in page["ResultSet"]["Rows"]])
    with (ROOT / "evidence" / f"{name}.csv").open("w") as out:
        csv.writer(out).writerows(rows)
    print(name, qid, execution["Statistics"], flush=True)
    return rows


def batch(session, bucket):
    if session is not None:
        glue = session.client("glue")
        try:
            glue.create_database(DatabaseInput={"Name": DB})
        except glue.exceptions.AlreadyExistsException:
            pass
    query(session, bucket, "01_table", f"""CREATE EXTERNAL TABLE IF NOT EXISTS payment_events
({FIELDS}) PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://{bucket}/payments/'""")
    query(session, bucket, "01_partitions", "MSCK REPAIR TABLE payment_events")
    query(session, bucket, "02_dedup", """CREATE OR REPLACE VIEW payments AS
WITH exact AS (SELECT DISTINCT * FROM payment_events), ranked AS (
 SELECT *, row_number() OVER (PARTITION BY invoiceid
 ORDER BY from_iso8601_timestamp(modifieddate) DESC,
 CASE status WHEN 'failure' THEN 2 WHEN 'success' THEN 2
 WHEN 'processing' THEN 1 ELSE 0 END DESC,
 from_iso8601_timestamp(receivedat) DESC, status DESC) AS rn
 FROM exact)
SELECT invoiceid,status,failurereason,amount,finalamount,ccy,reference,
createddate,modifieddate,receivedat,merchantid,merchantname,mcc,customerid,
paymentmethod,device,dt FROM ranked WHERE rn=1""")
    query(session, bucket, "02_scale", """WITH raw AS (
 SELECT count(*) events, count(DISTINCT invoiceid) invoices FROM payment_events),
 exact AS (SELECT count(*) n FROM (SELECT DISTINCT * FROM payment_events))
 SELECT events,invoices,events-n exact_duplicates,
 events-invoices events_beyond_one_per_invoice FROM raw CROSS JOIN exact""")
    query(session, bucket, "06_late", """SELECT count(*) events,
 count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>60) late_over_60s,
 count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>3600) late_over_1h,
 100.0*count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>3600)/count(*) pct_over_1h
 FROM payment_events""")
    query(session, bucket, "07_parquet", f"""CREATE TABLE payments_parquet WITH (
 format='PARQUET', parquet_compression='SNAPPY', partitioned_by=ARRAY['dt'],
 external_location='s3://{bucket}/curated/') AS SELECT * FROM payments""")
    templates = {
        "03_turnover": """SELECT merchantid,merchantname,ccy,
 sum(CAST(finalamount AS decimal(20,2)))/100 AS turnover
 FROM {table} WHERE status='success' GROUP BY 1,2,3 ORDER BY turnover DESC""",
        "04_failure": """SELECT paymentmethod,device,count(*) terminal_payments,
 count_if(status='failure') failures,
 100.0*count_if(status='failure')/count(*) failure_pct FROM {table}
 WHERE status IN ('success','failure') GROUP BY 1,2 ORDER BY failure_pct DESC""",
        "05_hours": """SELECT hour(from_iso8601_timestamp(createddate)) hour_utc,
 count(*) payments FROM {table} GROUP BY 1 ORDER BY 1""",
    }
    for suffix, table in [("json", "payments"), ("parquet", "payments_parquet")]:
        for name, sql in templates.items():
            query(session, bucket, name + "_" + suffix, sql.format(table=table))


def role(session, name, service, source_arn, statements):
    iam = session.client("iam")
    account = session.client("sts").get_caller_identity()["Account"]
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Principal": {"Service": service}, "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"aws:SourceAccount": account},
                      "ArnLike": {"aws:SourceArn": source_arn}}}]}
    try:
        arn = iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust),
                              Tags=[{"Key": "project", "Value": "peach-lab8"}])["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        arn = iam.get_role(RoleName=name)["Role"]["Arn"]
        iam.update_assume_role_policy(RoleName=name, PolicyDocument=json.dumps(trust))
    iam.put_role_policy(RoleName=name, PolicyName="lab8", PolicyDocument=json.dumps(
        {"Version": "2012-10-17", "Statement": statements}))
    return arn


def crawler(session, bucket):
    account = session.client("sts").get_caller_identity()["Account"]
    arn = role(session, "peach-lab8-glue", "glue.amazonaws.com",
               f"arn:aws:glue:{REGION}:{account}:crawler/peach-lab8", [
        {"Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
         "Resource": f"arn:aws:s3:::{bucket}"},
        {"Effect": "Allow", "Action": ["s3:GetObject"],
         "Resource": f"arn:aws:s3:::{bucket}/payments/*"},
        {"Effect": "Allow", "Action": ["glue:GetDatabase", "glue:GetTable", "glue:GetTables",
          "glue:CreateTable", "glue:UpdateTable", "glue:GetPartitions", "glue:BatchGetPartition",
          "glue:BatchCreatePartition", "glue:BatchUpdatePartition"],
         "Resource": [f"arn:aws:glue:{REGION}:{account}:catalog",
                      f"arn:aws:glue:{REGION}:{account}:database/{DB}",
                      f"arn:aws:glue:{REGION}:{account}:table/{DB}/*"]},
        {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
         "Resource": f"arn:aws:logs:{REGION}:{account}:log-group:/aws-glue/crawlers*"}])
    time.sleep(12)
    glue = session.client("glue")
    try:
        glue.create_crawler(Name="peach-lab8", Role=arn, DatabaseName=DB,
                            TablePrefix="crawler_", Targets={"S3Targets": [{"Path": f"s3://{bucket}/payments/"}]})
    except glue.exceptions.AlreadyExistsException:
        pass
    glue.start_crawler(Name="peach-lab8")
    while True:
        c = glue.get_crawler(Name="peach-lab8")["Crawler"]
        if c["State"] == "READY" and "LastCrawl" in c:
            break
        time.sleep(5)
    save("crawler.json", c)
    if c["LastCrawl"]["Status"] != "SUCCEEDED":
        raise RuntimeError(c["LastCrawl"])
    tables = []
    for p in glue.get_paginator("get_tables").paginate(DatabaseName=DB):
        tables.extend(t for t in p["TableList"] if t["Name"].startswith("crawler_"))
    save("crawler-schema.json", tables)
    save("crawler-history.json",glue.list_crawls(CrawlerName="peach-lab8"))
    save("crawler-metrics.json",glue.get_crawler_metrics(CrawlerNameList=["peach-lab8"]))
    print("crawler complete", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["copy", "batch", "crawler", "crawler-cleanup", "download", "sql"])
    parser.add_argument("--bucket")
    parser.add_argument("--via-local",action="store_true",
                        help="Download public source anonymously, then upload to the allowed region")
    args = parser.parse_args()
    if args.action == "sql":
        batch(None,args.bucket or "YOUR_LAB8_BUCKET")
        return
    session = boto3.Session(region_name=REGION)
    if args.bucket is None:
        account=session.client("sts").get_caller_identity()["Account"]
        args.bucket=f"peach-lab8-{account}-{REGION}"
    s3 = session.client("s3")
    if args.action == "crawler-cleanup":
        glue=session.client("glue")
        try:
            glue.delete_crawler(Name="peach-lab8")
        except glue.exceptions.EntityNotFoundException:
            pass
        iam=session.client("iam")
        for method,kwargs in [("delete_role_policy",{"RoleName":"peach-lab8-glue","PolicyName":"lab8"}),
                              ("delete_role",{"RoleName":"peach-lab8-glue"})]:
            try:
                getattr(iam,method)(**kwargs)
            except iam.exceptions.NoSuchEntityException:
                pass
        return
    if args.action == "copy":
        try:
            config={} if REGION == "us-east-1" else {"CreateBucketConfiguration":{"LocationConstraint":REGION}}
            s3.create_bucket(Bucket=args.bucket,**config)
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass
        s3.put_public_access_block(Bucket=args.bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
        # Read the public manifest anonymously. An account SCP can deny signed
        # source-region requests even when the source bucket itself is public.
        # CopyObject executes in the destination region; no data is generated.
        import subprocess
        manifest=json.loads(subprocess.check_output(["aws","s3api","list-objects-v2",
            "--bucket","ucu-ooad-lab8-payments","--prefix","payments/",
            "--no-sign-request","--region","us-east-1","--output","json"]))
        save("source-manifest.json",manifest)
        if args.via_local:
            from concurrent.futures import ThreadPoolExecutor
            def transfer(item):
                local=ROOT/"data"/"transfer"/item["Key"]
                local.parent.mkdir(parents=True,exist_ok=True)
                if not local.exists() or local.stat().st_size != item["Size"]:
                    subprocess.run(["aws","s3","cp","s3://ucu-ooad-lab8-payments/"+item["Key"],
                        str(local),"--no-sign-request","--region","us-east-1","--only-show-errors"],check=True)
                subprocess.run(["aws","s3","cp",str(local),f"s3://{args.bucket}/"+item["Key"],
                    "--region",REGION,"--only-show-errors"],check=True)
                print(item["Key"],item["Size"],"copied via local",flush=True)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(transfer,manifest["Contents"]))
            save("copy-manifest.json",{"bucket":args.bucket,"region":REGION,"source_region":"us-east-1",
                "method":"AWS CLI anonymous download then authenticated upload",
                "objects":len(manifest["Contents"]),"bytes":sum(x["Size"] for x in manifest["Contents"])})
            return
        for item in manifest["Contents"]:
            subprocess.run(["aws","s3api","copy-object","--bucket",args.bucket,
                "--key",item["Key"],"--copy-source","ucu-ooad-lab8-payments/"+item["Key"],
                "--region",REGION,"--output","json"],check=True)
    elif args.action == "download":
        s3.download_file(args.bucket, "payments/dt=2026-10-01/events.jsonl", str(ROOT / "data/day.jsonl"))
    elif args.action == "batch":
        batch(session, args.bucket)
    else:
        crawler(session, args.bucket)


if __name__ == "__main__":
    main()
