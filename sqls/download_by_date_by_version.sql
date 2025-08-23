#standardSQL
SELECT
  DATE(timestamp) as download_date,
  file.version as version,
  COUNT(*) as daily_downloads
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  -- time_range: eg 45
  -- version_filter: eg '1.0.0' or 'all' for all versions
  file.project = '{{project_name}}'
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL {{time_range}} DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  {{version_condition}}
GROUP BY
  download_date, file.version
ORDER BY
  download_date, version;
