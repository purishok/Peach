"""Collect service evidence and calculate measured scan/cost comparisons."""
import csv
import json
import math
import re
from datetime import datetime, timezone

import boto3

from batch import ROOT, REGION, save


def read_csv(name):
    with (ROOT/"evidence"/(name+".csv")).open() as f:
        return list(csv.DictReader(f))


def main():
    s=boto3.Session(region_name=REGION)
    glue=s.client("glue")
    # Crawl history reports measured DPUHour, not a guess from table row estimates.
    history_path=ROOT/"evidence/crawler-history.json"
    history=json.loads(history_path.read_text()) if history_path.exists() else glue.list_crawls(CrawlerName="peach-lab8")
    save("crawler-history.json",history)
    if not (ROOT/"evidence/crawler-metrics.json").exists():
        save("crawler-metrics.json",glue.get_crawler_metrics(CrawlerNameList=["peach-lab8"]))
    logs=s.client("logs")
    events=[]
    for page in logs.get_paginator("filter_log_events").paginate(logGroupName="/aws/lambda/peach-lab8-alert"):
        events.extend(page.get("events",[]))
    save("lambda-logs.json",events)
    # Poll queries reused a filename. Recover every execution ID from the run
    # log so the cost estimate includes each of those real service executions.
    executions={}
    athena=s.client("athena")
    for file in (ROOT/"evidence").glob("*.execution.json"):
        e=json.loads(file.read_text()); executions[e["QueryExecutionId"]]=e
    ids=re.findall(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
                   (ROOT/"evidence/cloud-run.log").read_text())
    for qid in dict.fromkeys(ids):
        executions[qid]=athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
    save("all-athena-executions.json",list(executions.values()))
    pricing=json.loads((ROOT/"evidence/pricing-eu-north-1.json").read_text())
    def price(service,usage):
        return next(float(r["USD"]) for r in pricing[service]
                    if r["attributes"]["usagetype"]==usage and r["beginRange"]=="0")
    athena_rate=price("AmazonAthena","EUN1-DataScannedInTB")
    def billed_mb(n):
        return max(10,math.ceil(n/(1024**2))) if n else 0
    def scan_cost(n):
        return billed_mb(n)*1024**2/(1024**4)*athena_rate
    compare=[]
    for stem in ["03_turnover","04_failure","05_hours"]:
        if read_csv(stem+"_json")!=read_csv(stem+"_parquet"):
            raise AssertionError("JSON/Parquet results differ: "+stem)
        a=json.loads((ROOT/"evidence"/(stem+"_json.execution.json")).read_text())["Statistics"]
        b=json.loads((ROOT/"evidence"/(stem+"_parquet.execution.json")).read_text())["Statistics"]
        compare.append({"query":stem,"json_bytes":a["DataScannedInBytes"],"parquet_bytes":b["DataScannedInBytes"],
            "json_engine_ms":a["EngineExecutionTimeInMillis"],"parquet_engine_ms":b["EngineExecutionTimeInMillis"],
            "json_total_ms":a["TotalExecutionTimeInMillis"],"parquet_total_ms":b["TotalExecutionTimeInMillis"],
            "scan_reduction":a["DataScannedInBytes"]/b["DataScannedInBytes"],
            "json_estimated_usd":scan_cost(a["DataScannedInBytes"]),
            "parquet_estimated_usd":scan_cost(b["DataScannedInBytes"]),
            "billing_reduction":scan_cost(a["DataScannedInBytes"])/scan_cost(b["DataScannedInBytes"]),
            "results_equal":True})
    save("athena-comparison.json",compare)
    with (ROOT/"evidence/athena-comparison.csv").open("w") as f:
        writer=csv.DictWriter(f,fieldnames=list(compare[0])); writer.writeheader(); writer.writerows(compare)
    producer=json.loads((ROOT/"evidence/cloud-producer.json").read_text())
    start=json.loads((ROOT/"evidence/cloud-start.json").read_text())
    cleanup=json.loads((ROOT/"evidence/cloud-cleanup.json").read_text())
    elapsed=(datetime.fromisoformat(cleanup["utc"])-datetime.fromisoformat(start["utc"])).total_seconds()
    dpu=sum(c.get("DPUHour",0) for c in history.get("Crawls",[]))
    billed_ms=sum(int(x) for e in events for x in re.findall(r"Billed Duration: ([0-9]+) ms",e["message"]))
    request_count=sum(e["message"].startswith("REPORT RequestId") for e in events)
    estimates={
        "region":REGION,"currency":"USD","calculated_utc":datetime.now(timezone.utc).isoformat(),
        "status":"on-demand estimate before credits/taxes; not a posted AWS invoice",
        "kinesis_lifetime_seconds_upper_bound":elapsed,
        "kinesis_billed_shard_hours_upper_bound":math.ceil(elapsed/3600),
        "kinesis_shard_usd":math.ceil(elapsed/3600)*price("AmazonKinesis","EUN1-Storage-ShardHour"),
        "kinesis_put_usd":producer["events"]*price("AmazonKinesis","EUN1-PutRequestPayloadUnits"),
        "firehose_usd":producer["events"]*5*1024/(1024**3)*price("AmazonKinesisFirehose","EUN1-StreamsSourceBilledBytes"),
        "crawler_dpu_hours":dpu,
        "crawler_usd":dpu*price("AWSGlue","EUN1-Crawler-DPU-Hour"),
        "athena_executions":len(executions),
        "athena_all_executions_usd":sum(scan_cost(e["Statistics"].get("DataScannedInBytes",0)) for e in executions.values()),
        "lambda_requests":request_count,"lambda_billed_ms":billed_ms,
        "lambda_gb_seconds":billed_ms/1000*.125,
        "sns_alerts":len(json.loads((ROOT/"evidence/cloud-alerts.json").read_text())),
        "excluded":"S3 requests/storage, Glue catalog, Lambda/SNS/log charges, internet/source transfer charges and local network; add these for a complete invoice",
    }
    estimates["listed_components_usd"]=sum(estimates[k] for k in ["kinesis_shard_usd","kinesis_put_usd","firehose_usd","crawler_usd","athena_all_executions_usd"])
    additional=json.loads((ROOT/"evidence/pricing-additional.json").read_text())
    rates=[r for rows in additional.values() for r in rows]
    def extra_price(usage):
        return next(float(r["USD"]) for r in rates if r["attributes"]["usagetype"]==usage and r["beginRange"]=="0")
    estimates["lambda_estimated_usd_before_free_tier"]=estimates["lambda_gb_seconds"]*extra_price("EUN1-Lambda-GB-Second")+request_count*extra_price("EUN1-Request")
    estimates["sns_estimated_usd_before_free_tier"]=estimates["sns_alerts"]*next(float(r["USD"]) for r in rates if r["attributes"]["usagetype"]=="EUN1-Requests-Tier1" and float(r["USD"])>0)
    estimates["crawler_usage_cost_note"]="Glue reports used DPUHour. AWS Glue FAQ states a 10-minute minimum per crawl; this is not a final bill."
    estimates["crawler_minimum_scenario_dpus"]=2
    estimates["crawler_minimum_scenario_usd"]=2*10/60*price("AWSGlue","EUN1-Crawler-DPU-Hour")
    estimates["total_usage_components_estimated_usd"]=estimates["listed_components_usd"]+estimates["lambda_estimated_usd_before_free_tier"]+estimates["sns_estimated_usd_before_free_tier"]
    estimates["total_2dpu_10min_scenario_usd"]=estimates["total_usage_components_estimated_usd"]-estimates["crawler_usd"]+estimates["crawler_minimum_scenario_usd"]
    storage=json.loads((ROOT/"evidence/s3-verification.json").read_text())
    estimates["retained_s3_bytes"]=sum(x["bytes"] for x in storage["prefixes"].values())
    estimates["retained_s3_estimated_usd_per_month"]=estimates["retained_s3_bytes"]/(1024**3)*extra_price("EUN1-TimedStorage-ByteHrs")
    estimates["excluded"]="Final crawler billing minimum/allocated DPUs, S3 requests, CloudWatch logs, source-owner egress/local network, credits/taxes; S3 storage listed separately"
    save("cost-estimate.json",estimates)
    # Verify actual absence; a cleanup log alone is insufficient.
    previous=ROOT/"evidence/cleanup-verification.json"
    verified=json.loads(previous.read_text()) if previous.exists() else {}
    verified.update({"region":REGION,"checked_utc":datetime.now(timezone.utc).isoformat()})
    k=s.client("kinesis")
    try:k.describe_stream_summary(StreamName="peach-lab8")
    except k.exceptions.ResourceNotFoundException:verified["kinesis_absent"]=True
    f=s.client("firehose")
    try:f.describe_delivery_stream(DeliveryStreamName="peach-lab8")
    except f.exceptions.ResourceNotFoundException:verified["firehose_absent"]=True
    l=s.client("lambda")
    try:l.get_function(FunctionName="peach-lab8-alert")
    except l.exceptions.ResourceNotFoundException:verified["lambda_absent"]=True
    if not all(verified.get(k) for k in ["kinesis_absent","firehose_absent","lambda_absent"]):
        raise AssertionError("Lab compute/streams still exist")
    save("cleanup-verification.json",verified)
    save("aws-summary.json",{"scale":read_csv("02_scale"),"late":read_csv("06_late"),
        "payments":read_csv("02_payments_check"),"crawler":read_csv("crawler_check"),
        "cloud_results":read_csv("cloud_query"),"comparison":compare,"cost":estimates})
    print(json.dumps({"comparison":compare,"cost":estimates,"cleanup":verified},indent=2))


if __name__=="__main__":
    main()
