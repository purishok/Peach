CREATE TABLE payments_parquet WITH (
 format='PARQUET', parquet_compression='SNAPPY', partitioned_by=ARRAY['dt'],
 external_location='s3://peach-lab8-985040259102-eu-north-1/curated/') AS SELECT * FROM payments;
