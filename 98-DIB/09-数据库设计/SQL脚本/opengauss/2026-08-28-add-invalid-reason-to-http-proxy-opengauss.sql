-- OpenGauss migration script for adding invalid_reason column to com_pub_http_proxy table
ALTER TABLE com_pub_http_proxy ADD COLUMN invalid_reason VARCHAR(2000);
COMMENT ON COLUMN com_pub_http_proxy.invalid_reason IS '失效原因';
