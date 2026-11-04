SELECT count(*) final_payments,count(DISTINCT invoiceid) invoices,count_if(status='failure') failures FROM payments;
