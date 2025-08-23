#standardSQL
SELECT
  COUNT(*) as recent_30_days_downloads
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  file.project = '{{project_name}}'
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
