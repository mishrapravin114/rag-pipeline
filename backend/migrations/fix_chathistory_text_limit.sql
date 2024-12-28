-- Migration to fix ChatHistory text column limits
-- This changes TEXT columns to LONGTEXT to support larger response data

-- Change response_details column from TEXT to LONGTEXT
ALTER TABLE `ChatHistory` 
MODIFY COLUMN `response_details` LONGTEXT NULL;

-- Change request_details column from TEXT to LONGTEXT for consistency
ALTER TABLE `ChatHistory` 
MODIFY COLUMN `request_details` LONGTEXT NULL;

-- Also update user_query to LONGTEXT in case of very long queries
ALTER TABLE `ChatHistory` 
MODIFY COLUMN `user_query` LONGTEXT NOT NULL;

-- Verify the changes
-- SHOW CREATE TABLE `ChatHistory`;