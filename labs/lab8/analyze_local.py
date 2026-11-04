"""Measure the actual source day and compare the broker experiment outputs."""
import csv
import json
from collections import Counter

from batch import ROOT, save
from stream import load, timestamp


def main():
    events=load(ROOT/"data/day.jsonl")
    latest={}
    for e in events:
        old=latest.get(e["invoiceId"])
        if old is None or (e["modifiedDate"],e["receivedAt"],e["status"]) > (old["modifiedDate"],old["receivedAt"],old["status"]):
            latest[e["invoiceId"]]=e
    stats={"scope":"2026-10-01 only; NOT month-wide Athena results",
           "events":len(events),"unique_invoices":len(latest),
           "exact_duplicates":len(events)-len({json.dumps(e,sort_keys=True) for e in events}),
           "late_over_60s":sum(timestamp(e["receivedAt"])-timestamp(e["modifiedDate"])>60 for e in events),
           "late_over_1h":sum(timestamp(e["receivedAt"])-timestamp(e["modifiedDate"])>3600 for e in events),
           "final_statuses":dict(Counter(e["status"] for e in latest.values()))}
    save("source-day.json",stats)
    print(json.dumps(stats,indent=2))
    names=["payments-baseline","payments-restart-v2","payments-two-v2","payments-failure30","payments-wait0"]
    results={}
    for name in names:
        file=ROOT/"evidence"/(name+".json")
        if file.exists():
            r=json.loads(file.read_text())
            if r["counters"]["read"] != len(events):
                raise AssertionError((name,"events lost",r["counters"]["read"],len(events)))
            results[name]=r
    save("experiment-comparison.json",results)
    zero=ROOT/"evidence/payments-wait0.csv"
    if zero.exists():
        def windows(name):
            with (ROOT/"evidence"/(name+".csv")).open() as f:
                return {(r["window_epoch"],r["payment_method"]):(int(r["payments"]),int(r["failures"]))
                        for r in csv.DictReader(f)}
        baseline=windows("payments-baseline")
        now=windows("payments-wait0")
        changes=[]
        for key in sorted(baseline.keys()|now.keys()):
            a=baseline.get(key,(0,0)); b=now.get(key,(0,0))
            if a!=b:
                changes.append([*key,*a,*b,b[0]-a[0],b[1]-a[1]])
        with (ROOT/"evidence/window-differences.csv").open("w") as f:
            w=csv.writer(f)
            w.writerow(["window_epoch","method","wait120_total","wait120_failed",
                        "wait0_total","wait0_failed","delta_total","delta_failed"])
            w.writerows(changes)
        save("window-differences.json",{"changed_windows":len(changes),"examples":changes[:10]})


if __name__ == "__main__":
    main()
