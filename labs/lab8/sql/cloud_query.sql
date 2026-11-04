WITH exact AS (SELECT DISTINCT * FROM streamed_events),
 ranked AS (SELECT *,row_number() OVER (PARTITION BY invoiceid ORDER BY modifieddate DESC,receivedat DESC) rn FROM exact)
 SELECT paymentmethod,count(*) terminal_payments,count_if(status='failure') failures,
 100.0*count_if(status='failure')/count(*) failure_pct FROM ranked
 WHERE rn=1 AND status IN ('success','failure') GROUP BY 1 ORDER BY 1;
