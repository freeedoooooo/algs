-- MySQL migration script for adding invalid_reason column to com_pub_http_proxy table
ALTER TABLE `com_pub_http_proxy` ADD COLUMN `invalid_reason` varchar(2000) COMMENT '失效原因' AFTER `del_flag`;
