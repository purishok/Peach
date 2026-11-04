SELECT merchantid,merchantname,ccy,
 sum(CAST(finalamount AS decimal(20,2)))/100 AS turnover
 FROM payments WHERE status='success' GROUP BY 1,2,3 ORDER BY turnover DESC;
