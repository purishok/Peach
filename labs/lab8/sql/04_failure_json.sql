SELECT paymentmethod,device,count(*) terminal_payments,
 count_if(status='failure') failures,
 100.0*count_if(status='failure')/count(*) failure_pct FROM payments
 WHERE status IN ('success','failure') GROUP BY 1,2 ORDER BY failure_pct DESC;
