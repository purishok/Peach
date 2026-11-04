"""Run real broker experiments; no fabricated outputs or synthetic dataset."""
import json
import sqlite3
import subprocess
import sys
import time

from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic, OffsetSpec

from batch import ROOT, save
from stream import connect

PYTHON = sys.executable


def topic(name):
    admin=AdminClient({"bootstrap.servers":"127.0.0.1:19092","broker.address.family":"v4"})
    result=admin.create_topics([NewTopic(name,3,1)])
    for f in result.values():
        f.result()


def launch(action,name,extra=None,client="one"):
    out=(ROOT/"evidence"/f"{name}-{action}-{client}.log").open("a")
    cmd=[PYTHON,str(ROOT/"stream.py"),action,"--topic",name,
         "--group",name,"--state",str(ROOT/"data"/f"{name}.sqlite"),"--client",client]
    return subprocess.Popen(cmd+(extra or []),stdout=out,stderr=subprocess.STDOUT)


def stop(p):
    if p.poll() is None:
        p.terminate()
    code=p.wait(timeout=30)
    if code:
        raise RuntimeError(f"Consumer failed with exit {code}")


def offsets(name):
    db=sqlite3.connect(ROOT/"data"/f"{name}.sqlite")
    consumed=dict(db.execute("SELECT partition,next_offset FROM offsets"))
    db.close()
    from confluent_kafka import TopicPartition
    admin=AdminClient({"bootstrap.servers":"127.0.0.1:19092","broker.address.family":"v4"})
    futures=admin.list_offsets({TopicPartition(name,i):OffsetSpec.latest() for i in range(3)})
    high={p.partition:f.result(timeout=15).offset for p,f in futures.items()}
    return {"consumed":consumed,"high_water":high,"lag":sum(high[i]-consumed.get(i,0) for i in high)}


def experiment(name,rate=2000,wait=120,failure=False,restart=False,two=False):
    topic(name)
    # Initialize WAL once before starting competing processes.
    connect(ROOT/"data"/f"{name}.sqlite").close()
    consumers=[launch("consume",name,["--wait",str(wait)])]
    if two:
        consumers.append(launch("consume",name,["--wait",str(wait)],"two"))
    time.sleep(4)
    producer=launch("produce",name,["--rate",str(rate)]+(["--failure30"] if failure else []))
    lifecycle=[]
    if restart:
        time.sleep(5)
        stop(consumers.pop())
        lifecycle.append({"action":"stop","wall_epoch":time.time(),**offsets(name)})
        # Producer continues throughout the 60-second interruption.
        time.sleep(60)
        lifecycle.append({"action":"before_resume","wall_epoch":time.time(),**offsets(name)})
        consumers.append(launch("consume",name,["--wait",str(wait)],"resumed"))
    if producer.wait(timeout=300):
        raise RuntimeError("Producer failed; see log")
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        progress=offsets(name)
        if progress["lag"]==0:
            break
        for c in consumers:
            if c.poll() is not None:
                raise RuntimeError("Consumer exited before catch-up")
        time.sleep(1)
    else:
        raise RuntimeError("Consumer did not drain")
    lifecycle.append({"action":"drained","wall_epoch":time.time(),**progress})
    for c in consumers:
        stop(c)
    save(name+"-lifecycle.json",lifecycle)
    with (ROOT/"evidence"/(name+"-finalize.log")).open("w") as out:
        subprocess.run([PYTHON,str(ROOT/"stream.py"),"summarize","--state",
            str(ROOT/"data"/(name+".sqlite")),"--output",str(ROOT/"evidence"/(name+".json"))],
            stdout=out,check=True)
    print(name,(ROOT/"evidence"/(name+".json")).read_text(),flush=True)


def main():
    if not (ROOT/"evidence/payments-baseline.json").exists():
        experiment("payments-baseline")
    if not (ROOT/"evidence/payments-restart-v2.json").exists():
        experiment("payments-restart-v2",rate=400,restart=True)
    experiment("payments-two-v2",rate=700,two=True)
    experiment("payments-failure30",failure=True)
    experiment("payments-wait0",wait=0)


if __name__ == "__main__":
    main()
