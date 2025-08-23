#standardSQL
SELECT
  country_code,
  COUNT(*) as download_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  file.project = '{{project_name}}'
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND country_code IS NOT NULL
GROUP BY
  country_code
ORDER BY
  download_count DESC
LIMIT 20
