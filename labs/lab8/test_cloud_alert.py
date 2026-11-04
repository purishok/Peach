import base64
import importlib
import json
import unittest
from unittest.mock import patch


class AlertTests(unittest.TestCase):
    def test_duplicates_state_and_strict_threshold(self):
        with patch("boto3.client") as client, patch.dict("os.environ",{"TOPIC_ARN":"test-topic"}):
            alert=importlib.import_module("cloud_alert")
            alert.SNS=client.return_value
            alert.SNS.publish.return_value={"MessageId":"test-message"}
            def record(invoice,status):
                raw=json.dumps({"invoiceId":invoice,"paymentMethod":"card","status":status}).encode()
                return {"kinesis":{"data":base64.b64encode(raw).decode()}}
            records=[record(str(i),"failure" if i==0 else "success") for i in range(10)]
            state=alert.handler({"Records":records+[records[0]]},None)["state"]
            self.assertEqual(state["methods"]["card"],[10,1])
            alert.handler({"Records":[],"state":state,"isFinalInvokeForWindow":True},None)
            alert.SNS.publish.assert_not_called() # exactly 10% does not breach
            state=alert.handler({"Records":[record("11","failure")],"state":state},None)["state"]
            alert.handler({"Records":[],"state":state,"isFinalInvokeForWindow":True},None)
            alert.SNS.publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
