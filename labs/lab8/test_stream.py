"""Small semantic tests; these fixtures are not the lab dataset."""
import tempfile
import unittest
from datetime import datetime, timezone

from stream import connect, process, close_windows


def event(invoice, second, status="success"):
    return {"invoiceId":invoice,"modifiedDate":datetime.fromtimestamp(second,timezone.utc).isoformat(),
            "status":status,"paymentMethod":"card"}


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=connect(self.tmp.name+"/test.sqlite")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_duplicate_and_atomic_offset(self):
        for offset in range(2):
            with self.db:
                process(self.db,event("a",61),0,offset,120)
        self.assertEqual(self.db.execute("SELECT total FROM windows").fetchone()[0],1)
        self.assertEqual(dict(self.db.execute("SELECT name,n FROM counters"))["duplicates"],1)
        self.assertEqual(self.db.execute("SELECT next_offset FROM offsets").fetchone()[0],2)

    def test_zero_wait_rejects_closed_window(self):
        for partition in range(3):
            process(self.db,event(str(partition),240),partition,0,0)
        process(self.db,event("late",61),0,1,0)
        self.assertEqual(dict(self.db.execute("SELECT name,n FROM counters"))["late"],1)

    def test_two_minute_grace_accepts_same_event(self):
        for partition in range(3):
            process(self.db,event(str(partition),240),partition,0,120)
        process(self.db,event("on-time",121),0,1,120)
        self.assertEqual(self.db.execute("SELECT count(*) FROM invoices").fetchone()[0],4)

    def test_terminal_correction_retracts_previous(self):
        process(self.db,event("a",61),0,0,120)
        process(self.db,event("a",62,"failure"),0,1,120)
        self.assertEqual(self.db.execute("SELECT total,failed FROM windows").fetchone(),(1,1))

    def test_reopen_retains_state(self):
        with self.db:
            process(self.db,event("a",61),0,0,120)
        self.db.close()
        self.db=connect(self.tmp.name+"/test.sqlite")
        with self.db:
            process(self.db,event("a",61),0,1,120)
        self.assertEqual(self.db.execute("SELECT total FROM windows").fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
