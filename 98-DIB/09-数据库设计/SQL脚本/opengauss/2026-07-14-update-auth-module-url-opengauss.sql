UPDATE p_auth_module
SET url = REPLACE(url, '/#/', '/')
WHERE url LIKE '/app-%'
  AND url LIKE '%/#/%';