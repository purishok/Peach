"""Create isolated lab streams, replay a bounded sample, query S3, then clean up."""
import argparse
import io
import json
import time
import zipfile
from datetime import datetime, timezone

import boto3

from batch import ROOT, REGION, FIELDS, query, role, save
from stream import load

NAME = "peach-lab8"


def wait_delivery(firehose):
    while True:
        desc = firehose.describe_delivery_stream(DeliveryStreamName=NAME)["DeliveryStreamDescription"]
        if desc["DeliveryStreamStatus"] == "ACTIVE":
            return desc
        if desc["DeliveryStreamStatus"] in {"CREATING_FAILED", "DELETING_FAILED"}:
            raise RuntimeError(desc)
        time.sleep(3)


def run(session, bucket):
    account = session.client("sts").get_caller_identity()["Account"]
    kinesis = session.client("kinesis")
    firehose = session.client("firehose")
    lam = session.client("lambda")
    sns = session.client("sns")
    stream_arn = f"arn:aws:kinesis:{REGION}:{account}:stream/{NAME}"
    delivery_arn = f"arn:aws:firehose:{REGION}:{account}:deliverystream/{NAME}"
    topic = sns.create_topic(Name=NAME)["TopicArn"]
    save("cloud-start.json", {"utc": datetime.now(timezone.utc), "account": account,
                              "stream_arn": stream_arn, "bucket": bucket, "topic_arn": topic})
    kinesis.create_stream(StreamName=NAME,ShardCount=1,
                          StreamModeDetails={"StreamMode":"PROVISIONED"})
    kinesis.get_waiter("stream_exists").wait(StreamName=NAME,WaiterConfig={"Delay":3,"MaxAttempts":100})
    delivery_role = role(session, NAME+"-firehose", "firehose.amazonaws.com", delivery_arn, [
        {"Effect":"Allow","Action":["kinesis:DescribeStream","kinesis:ListShards",
         "kinesis:GetShardIterator","kinesis:GetRecords"],"Resource":stream_arn},
        {"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket","s3:ListBucketMultipartUploads"],
         "Resource":f"arn:aws:s3:::{bucket}"},
        {"Effect":"Allow","Action":["s3:AbortMultipartUpload","s3:PutObject","s3:GetObject"],
         "Resource":[f"arn:aws:s3:::{bucket}/stream/*",f"arn:aws:s3:::{bucket}/stream-errors/*"]}])
    # Lambda AssumeRole does not provide SourceArn/SourceAccount context: use the
    # documented Lambda service trust, with scoped runtime and PassRole permissions.
    iam = session.client("iam")
    trust = {"Version":"2012-10-17","Statement":[{"Effect":"Allow",
             "Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
    alert_role = iam.create_role(RoleName=NAME+"-alert",AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
    iam.put_role_policy(RoleName=NAME+"-alert",PolicyName="lab8",PolicyDocument=json.dumps({
        "Version":"2012-10-17","Statement":[
            {"Effect":"Allow","Action":["kinesis:DescribeStream","kinesis:DescribeStreamSummary",
             "kinesis:GetRecords","kinesis:GetShardIterator","kinesis:ListShards"],"Resource":stream_arn},
            {"Effect":"Allow","Action":"sns:Publish","Resource":topic},
            {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
             "Resource":f"arn:aws:logs:{REGION}:{account}:log-group:/aws/lambda/{NAME}-alert:*"}]}))
    time.sleep(15)
    firehose.create_delivery_stream(DeliveryStreamName=NAME,DeliveryStreamType="KinesisStreamAsSource",
        KinesisStreamSourceConfiguration={"KinesisStreamARN":stream_arn,"RoleARN":delivery_role},
        ExtendedS3DestinationConfiguration={"RoleARN":delivery_role,"BucketARN":f"arn:aws:s3:::{bucket}",
            "Prefix":"stream/","ErrorOutputPrefix":"stream-errors/",
            "BufferingHints":{"SizeInMBs":1,"IntervalInSeconds":60},"CompressionFormat":"UNCOMPRESSED"})
    wait_delivery(firehose)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        z.write(ROOT/"cloud_alert.py","cloud_alert.py")
    lam.create_function(FunctionName=NAME+"-alert",Runtime="python3.12",Role=alert_role,
        Handler="cloud_alert.handler",Code={"ZipFile":buf.getvalue()},Timeout=60,MemorySize=128,
        Environment={"Variables":{"TOPIC_ARN":topic}})
    lam.get_waiter("function_active_v2").wait(FunctionName=NAME+"-alert",WaiterConfig={"Delay":2,"MaxAttempts":60})
    mapping=lam.create_event_source_mapping(FunctionName=NAME+"-alert",EventSourceArn=stream_arn,
        StartingPosition="TRIM_HORIZON",BatchSize=100,TumblingWindowInSeconds=60,
        MaximumBatchingWindowInSeconds=1,MaximumRetryAttempts=2,ParallelizationFactor=1)
    save("cloud-mapping.json",mapping)
    # One source day, receivedAt order; 3000 real events, deterministic 30% failures.
    events=load(ROOT/"data/day.jsonl",True)[:3000]
    payloads=[{"Data":(json.dumps(e,separators=(",",":"))+"\n").encode(),
               "PartitionKey":e["invoiceId"]} for e in events]
    receipts=[]
    for start in range(0,len(payloads),100):
        pending=payloads[start:start+100]
        for attempt in range(8):
            response=kinesis.put_records(StreamName=NAME,Records=pending)
            receipts.extend(r for r in response["Records"] if "ErrorCode" not in r)
            pending=[p for p,r in zip(pending,response["Records"]) if "ErrorCode" in r]
            if not pending:
                break
            time.sleep(min(2**attempt,10))
        if pending:
            raise RuntimeError("Kinesis records still failing after retries")
        time.sleep(.15)
    save("cloud-producer.json",{"events":len(events),"accepted":len(receipts),
         "invoices":len({e['invoiceId'] for e in events}),"bytes":sum(len(p['Data']) for p in payloads),
         "first_receivedAt":events[0]['receivedAt'],"last_receivedAt":events[-1]['receivedAt']})
    query(session,bucket,"cloud_table",f"""CREATE EXTERNAL TABLE IF NOT EXISTS streamed_events
({FIELDS}) ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://{bucket}/stream/'""")
    # Buffering is a hint; poll for complete delivery before any stream deletion.
    for attempt in range(60):
        rows=query(session,bucket,"cloud_delivery_count","SELECT count(*) events FROM streamed_events")
        if int(rows[1][0])>=len(events):
            break
        time.sleep(5)
    else:
        raise RuntimeError("Firehose did not deliver the complete sample")
    query(session,bucket,"cloud_query","""WITH exact AS (SELECT DISTINCT * FROM streamed_events),
 ranked AS (SELECT *,row_number() OVER (PARTITION BY invoiceid ORDER BY modifieddate DESC,receivedat DESC) rn FROM exact)
 SELECT paymentmethod,count(*) terminal_payments,count_if(status='failure') failures,
 100.0*count_if(status='failure')/count(*) failure_pct FROM ranked
 WHERE rn=1 AND status IN ('success','failure') GROUP BY 1 ORDER BY 1""")
    # Give the final arrival-time window a chance to invoke and publish.
    deadline=time.monotonic()+150
    logs=session.client("logs")
    alerts=[]
    while time.monotonic()<deadline:
        try:
            for page in logs.get_paginator("filter_log_events").paginate(logGroupName="/aws/lambda/"+NAME+"-alert"):
                alerts.extend(e for e in page.get("events",[]) if 'sns_message_id' in e["message"])
        except logs.exceptions.ResourceNotFoundException:
            pass
        if alerts:
            break
        time.sleep(5)
    save("cloud-alerts.json",alerts)
    if not alerts:
        raise RuntimeError("No SNS alert observed")


def cleanup(session):
    lam=session.client("lambda")
    try:
        for page in lam.get_paginator("list_event_source_mappings").paginate(FunctionName=NAME+"-alert"):
            for m in page["EventSourceMappings"]:
                lam.delete_event_source_mapping(UUID=m["UUID"])
    except lam.exceptions.ResourceNotFoundException:
        pass
    try:
        lam.delete_function(FunctionName=NAME+"-alert")
    except lam.exceptions.ResourceNotFoundException:
        pass
    firehose=session.client("firehose")
    try:
        firehose.delete_delivery_stream(DeliveryStreamName=NAME,AllowForceDelete=True)
        for attempt in range(100):
            try:
                firehose.describe_delivery_stream(DeliveryStreamName=NAME)
            except firehose.exceptions.ResourceNotFoundException:
                break
            time.sleep(3)
        else:
            raise RuntimeError("Firehose deletion timed out; Kinesis retained to protect delivery")
    except firehose.exceptions.ResourceNotFoundException:
        pass
    kinesis=session.client("kinesis")
    try:
        kinesis.delete_stream(StreamName=NAME,EnforceConsumerDeletion=True)
        kinesis.get_waiter("stream_not_exists").wait(StreamName=NAME,WaiterConfig={"Delay":3,"MaxAttempts":100})
    except kinesis.exceptions.ResourceNotFoundException:
        pass
    sns=session.client("sns")
    account=session.client("sts").get_caller_identity()["Account"]
    sns.delete_topic(TopicArn=f"arn:aws:sns:{REGION}:{account}:{NAME}")
    iam=session.client("iam")
    for suffix in ["firehose","alert"]:
        try:
            iam.delete_role_policy(RoleName=NAME+"-"+suffix,PolicyName="lab8")
        except iam.exceptions.NoSuchEntityException:
            pass
        try:
            iam.delete_role(RoleName=NAME+"-"+suffix)
        except iam.exceptions.NoSuchEntityException:
            pass
    save("cloud-cleanup.json",{"utc":datetime.now(timezone.utc),"kinesis_deleted":True,
         "firehose_deleted":True,"lambda_deleted":True,"sns_deleted":True,"roles_deleted":True})


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["run","cleanup"])
    p.add_argument("--bucket",required=True)
    args=p.parse_args()
    session=boto3.Session(region_name=REGION)
    if args.action=="run":
        try:
            run(session,args.bucket)
        finally:
            cleanup(session)
    else:
        cleanup(session)


if __name__ == "__main__":
    main()
