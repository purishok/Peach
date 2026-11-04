"""Replay real webhooks; durable event-time windows over a three-partition log.

The two local consumers share SQLite (WAL). State and the next Kafka offset are
committed in one transaction. Kafka commits follow that transaction. Assignment
seeks to the SQLite offset, so a crash between commits cannot lose state.
"""
import argparse
import hashlib
import json
import signal
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import Consumer, Producer, TopicPartition

ROOT = Path(__file__).resolve().parent


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def load(path, force_failure=False):
    with open(path) as source:
        events = [json.loads(line) for line in source if line.strip()]
    if force_failure:
        for e in events:
            if e["status"] in {"success", "failure"}:
                # Stable by invoice: duplicates get exactly the same mutation.
                failed = int(hashlib.sha256(e["invoiceId"].encode()).hexdigest(), 16) % 100 < 30
                e["status"] = "failure" if failed else "success"
                e["finalAmount"] = 0 if failed else e["amount"]
                e["failureReason"] = "Lab injected failure" if failed else None
    return sorted(events, key=lambda e: (timestamp(e["receivedAt"]), timestamp(e["modifiedDate"])))


def produce(args):
    events = load(args.file, args.failure30)
    producer = Producer({"bootstrap.servers": args.broker, "broker.address.family":"v4", "enable.idempotence": True})
    errors = []
    def delivered(error, message):
        if error:
            errors.append(str(error))
    # Mean event rate gives the requested mean payments/second over a full replay.
    rate = args.rate * len(events) / len({e["invoiceId"] for e in events})
    start = time.monotonic()
    for n, event in enumerate(events):
        payload = json.dumps(event, separators=(",", ":")).encode()
        while True:
            try:
                producer.produce(args.topic, key=event["invoiceId"].encode(),
                                 value=payload, on_delivery=delivered)
                break
            except BufferError:
                producer.poll(.1)
        producer.poll(0)
        delay = start + (n + 1) / rate - time.monotonic()
        if delay > 0:
            time.sleep(delay)
    pending = producer.flush(60)
    if pending or errors:
        raise RuntimeError({"pending": pending, "errors": errors})
    print(json.dumps({"sent": len(events), "unique_invoices": len({e['invoiceId'] for e in events}),
                      "payments_per_second": args.rate, "seconds": time.monotonic()-start}), flush=True)


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
        db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
CREATE TABLE IF NOT EXISTS offsets(partition INTEGER PRIMARY KEY, next_offset INTEGER, max_event REAL);
CREATE TABLE IF NOT EXISTS seen(hash TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY, modified REAL, window INTEGER, method TEXT, failed INTEGER);
CREATE TABLE IF NOT EXISTS windows(window INTEGER,method TEXT,total INTEGER,failed INTEGER,closed INTEGER DEFAULT 0,
 PRIMARY KEY(window,method));
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY,n INTEGER);
CREATE TABLE IF NOT EXISTS outbox(window INTEGER,method TEXT,total INTEGER,failed INTEGER,PRIMARY KEY(window,method));
""")
    return db


def count(db, name):
    db.execute("INSERT INTO counters VALUES (?,1) ON CONFLICT(name) DO UPDATE SET n=n+1", (name,))


def watermark(db, wait):
    rows = db.execute("SELECT max_event FROM offsets").fetchall()
    return min(r[0] for r in rows) - wait if len(rows) == 3 else float("-inf")


def close_windows(db, mark):
    rows = db.execute("SELECT window,method,total,failed FROM windows WHERE closed=0 AND window+60<=?",
                      (mark,)).fetchall()
    for w, method, total, failed in rows:
        db.execute("INSERT OR IGNORE INTO outbox VALUES (?,?,?,?)", (w,method,total,failed))
        db.execute("UPDATE windows SET closed=1 WHERE window=? AND method=?", (w,method))
    return rows


def report(rows):
    for w, method, total, failed in rows:
        print(json.dumps({"window_utc": datetime.fromtimestamp(w, timezone.utc).isoformat(),
                          "paymentMethod": method, "payments": total, "failures": failed,
                          "failure_pct": 100*failed/total if total else 0,
                          "alert": failed/total > .10 if total else False}), flush=True)


def process(db, event, partition, offset, wait):
    t = timestamp(event["modifiedDate"])
    digest = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    count(db, "read")
    mark = watermark(db, wait)  # Before this record advances the watermark.
    duplicate = db.execute("INSERT OR IGNORE INTO seen VALUES (?)", (digest,)).rowcount == 0
    db.execute("""INSERT INTO offsets VALUES (?,?,?) ON CONFLICT(partition) DO UPDATE
 SET next_offset=excluded.next_offset,max_event=max(max_event,excluded.max_event)""", (partition,offset+1,t))
    if duplicate:
        count(db,"duplicates")
    elif (int(t)//60)*60+60 <= mark:
        count(db,"late")
    elif event["status"] in {"success","failure"}:
        # Keep one terminal status per payment. Newer corrections retract the old
        # contribution only if its window is still open.
        old = db.execute("SELECT modified,window,method,failed FROM invoices WHERE id=?",
                         (event["invoiceId"],)).fetchone()
        w = (int(t)//60)*60
        if old is None or t > old[0]:
            if old:
                closed = db.execute("SELECT closed FROM windows WHERE window=? AND method=?", old[1:3]).fetchone()[0]
                if closed:
                    count(db,"late_corrections")
                    return close_windows(db,watermark(db,wait))
                db.execute("UPDATE windows SET total=total-1,failed=failed-? WHERE window=? AND method=?",
                           (old[3],old[1],old[2]))
            failed = int(event["status"] == "failure")
            db.execute("INSERT OR REPLACE INTO invoices VALUES (?,?,?,?,?)",
                       (event["invoiceId"],t,w,event["paymentMethod"],failed))
            db.execute("""INSERT INTO windows(window,method,total,failed) VALUES (?,?,1,?)
 ON CONFLICT(window,method) DO UPDATE SET total=total+1,failed=failed+excluded.failed""",
                       (w,event["paymentMethod"],failed))
    return close_windows(db,watermark(db,wait))


def consume(args):
    db = connect(args.state)
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    consumer = Consumer({"bootstrap.servers": args.broker,"broker.address.family":"v4","group.id": args.group,
                         "client.id": args.client,"auto.offset.reset":"earliest",
                         "enable.auto.commit":False,"enable.auto.offset.store":False})
    def assign(c, parts):
        for p in parts:
            row = db.execute("SELECT next_offset FROM offsets WHERE partition=?", (p.partition,)).fetchone()
            if row:
                p.offset = row[0]
        print(json.dumps({"assigned": [p.partition for p in parts],"client":args.client}),flush=True)
        c.assign(parts)
    def revoke(c, parts):
        print(json.dumps({"revoked":[p.partition for p in parts],"client":args.client}),flush=True)
    consumer.subscribe([args.topic],on_assign=assign,on_revoke=revoke)
    last = time.monotonic()
    since_commit = 0
    try:
        while not stopping:
            msg = consumer.poll(.2)
            if msg is None:
                if args.idle_exit and time.monotonic()-last > args.idle_exit:
                    break
                continue
            if msg.error():
                raise RuntimeError(msg.error())
            last = time.monotonic()
            with db:
                rows = process(db,json.loads(msg.value()),msg.partition(),msg.offset(),args.wait)
            report(rows)
            consumer.store_offsets(message=msg)
            since_commit += 1
            if since_commit >= 500:
                consumer.commit(asynchronous=False)
                since_commit=0
    finally:
        if since_commit:
            consumer.commit(asynchronous=False)
        consumer.close()
        print(json.dumps({"counters":dict(db.execute("SELECT name,n FROM counters"))}),flush=True)
        db.close()


def summarize(args):
    db = connect(args.state)
    # Only called after producer and every consumer have stopped; finite replay EOF.
    with db:
        report(close_windows(db,float("inf")))
    summary = {"counters":dict(db.execute("SELECT name,n FROM counters")),
               "totals":db.execute("SELECT sum(total),sum(failed),count(*),sum(failed*1.0/total>0.1) FROM outbox WHERE total>0").fetchone(),
               "offsets":list(db.execute("SELECT * FROM offsets ORDER BY partition"))}
    Path(args.output).write_text(json.dumps(summary,indent=2))
    import csv
    with Path(args.output).with_suffix(".csv").open("w") as f:
        writer=csv.writer(f)
        writer.writerow(["window_epoch","payment_method","payments","failures"])
        writer.writerows(db.execute("SELECT * FROM outbox ORDER BY window,method"))
    print(json.dumps(summary),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["produce","consume","summarize"])
    p.add_argument("--broker",default="localhost:19092")
    p.add_argument("--topic",default="payments")
    p.add_argument("--group",default="lab8")
    p.add_argument("--client",default="consumer-1")
    p.add_argument("--file",default=str(ROOT/"data/day.jsonl"))
    p.add_argument("--state",default=str(ROOT/"data/state.sqlite"))
    p.add_argument("--rate",type=float,default=20)
    p.add_argument("--wait",type=int,default=120)
    p.add_argument("--idle-exit",type=int,default=0)
    p.add_argument("--failure30",action="store_true")
    p.add_argument("--output",default=str(ROOT/"evidence/stream-summary.json"))
    args=p.parse_args()
    {"produce":produce,"consume":consume,"summarize":summarize}[args.action](args)


if __name__ == "__main__":
    main()
