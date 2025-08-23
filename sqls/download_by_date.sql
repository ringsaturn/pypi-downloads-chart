#standardSQL
SELECT
  DATE(timestamp) as download_date,
  COUNT(*) as daily_downloads
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  -- time_range: eg 45
  file.project = '{{project_name}}'
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL {{time_range}} DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)    
GROUP BY
  download_date
ORDER BY
  download_date;
