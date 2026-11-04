SELECT count(*) events,count(failurereason) reasons,count_if(status='failure') failed_events,count_if(status<>'failure' AND failurereason IS NOT NULL) unexpected_reasons FROM crawler_payments;
