#standardSQL
SELECT
  details.installer.name as installer_name,
  COUNT(*) as download_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  file.project = '{{project_name}}'
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND details.installer.name IS NOT NULL
GROUP BY
  installer_name
ORDER BY
  download_count DESC
