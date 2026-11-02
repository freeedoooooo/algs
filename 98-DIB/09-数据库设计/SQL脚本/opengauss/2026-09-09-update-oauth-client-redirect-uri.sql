-- 修改授权码回调地址
-- 脚本需要配合前端、gateway模块一起部署
UPDATE oauth_client_details 
SET web_server_redirect_uri = REPLACE(web_server_redirect_uri, 'api-oauth', 'api/oauth');
