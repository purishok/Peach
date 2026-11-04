WITH raw AS (
 SELECT count(*) events, count(DISTINCT invoiceid) invoices FROM payment_events),
 exact AS (SELECT count(*) n FROM (SELECT DISTINCT * FROM payment_events))
 SELECT events,invoices,events-n exact_duplicates,
 events-invoices events_beyond_one_per_invoice FROM raw CROSS JOIN exact;
