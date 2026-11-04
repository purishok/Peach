CREATE EXTERNAL TABLE IF NOT EXISTS payment_events
(invoiceid string, status string, failurereason string,
amount bigint, finalamount bigint, ccy int, reference string,
createddate string, modifieddate string, receivedat string,
merchantid string, merchantname string, mcc int, customerid string,
paymentmethod string, device string) PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://peach-lab8-985040259102-eu-north-1/payments/';
