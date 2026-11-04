SELECT count(*) events,
 count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>60) late_over_60s,
 count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>3600) late_over_1h,
 100.0*count_if(date_diff('second',from_iso8601_timestamp(modifieddate),
 from_iso8601_timestamp(receivedat))>3600)/count(*) pct_over_1h
 FROM payment_events;
