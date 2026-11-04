"""Lambda tumbling window: one Kinesis shard; arrival-time, not payload event-time.

Lambda carries the returned JSON state between invocations of a window. SNS has
no external subscriptions in this lab; Publish's message ID is the evidence.
"""
import base64
import hashlib
import json
import os

import boto3

SNS = boto3.client("sns")


def handler(event, context):
    state = event.get("state", {})
    seen = set(state.get("seen", []))
    methods = state.get("methods", {})
    for record in event["Records"]:
        raw = base64.b64decode(record["kinesis"]["data"])
        key = hashlib.sha256(raw).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        e = json.loads(raw)
        if e["status"] in ("success", "failure"):
            counts = methods.setdefault(e["paymentMethod"], [0, 0])
            counts[0] += 1
            counts[1] += int(e["status"] == "failure")
    if event.get("isFinalInvokeForWindow"):
        for method, (total, failed) in methods.items():
            if failed / total > .1:
                alert = {"method": method, "total": total, "failures": failed,
                         "window": event.get("window"), "clock": "Kinesis arrival time"}
                response = SNS.publish(TopicArn=os.environ["TOPIC_ARN"], Message=json.dumps(alert))
                print(json.dumps({"alert": alert, "sns_message_id": response["MessageId"]}))
    return {"state": {"seen": list(seen), "methods": methods}}
