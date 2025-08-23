#standardSQL
SELECT
  COUNT(*) as total_downloads
FROM
  `bigquery-public-data.pypi.file_downloads`
WHERE
  -- project_name: eg 'tzfpy'
  file.project = '{{project_name}}'
