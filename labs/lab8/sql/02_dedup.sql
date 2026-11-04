CREATE OR REPLACE VIEW payments AS
WITH exact AS (SELECT DISTINCT * FROM payment_events), ranked AS (
 SELECT *, row_number() OVER (PARTITION BY invoiceid
 ORDER BY from_iso8601_timestamp(modifieddate) DESC,
 CASE status WHEN 'failure' THEN 2 WHEN 'success' THEN 2
 WHEN 'processing' THEN 1 ELSE 0 END DESC,
 from_iso8601_timestamp(receivedat) DESC, status DESC) AS rn
 FROM exact)
SELECT invoiceid,status,failurereason,amount,finalamount,ccy,reference,
createddate,modifieddate,receivedat,merchantid,merchantname,mcc,customerid,
paymentmethod,device,dt FROM ranked WHERE rn=1;
