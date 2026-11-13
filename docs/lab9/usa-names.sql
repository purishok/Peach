SELECT year, SUM(number) AS registered_births
FROM `bigquery-public-data.usa_names.usa_1910_current`
WHERE name = 'Michael' AND gender = 'M' AND year BETWEEN 2000 AND 2019
GROUP BY year
ORDER BY year;
