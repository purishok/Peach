SELECT hour(from_iso8601_timestamp(createddate)) hour_utc,
 count(*) payments FROM payments GROUP BY 1 ORDER BY 1;
