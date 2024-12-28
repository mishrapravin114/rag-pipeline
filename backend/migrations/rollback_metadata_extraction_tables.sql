-- Rollback Migration: Remove Metadata Extraction Tables
-- Date: 2024-11-28
-- Description: Removes tables for metadata extraction feature
-- 
-- WARNING: This will DELETE all metadata extraction data!
-- Make sure to backup any important data before running this script

-- Start transaction
START TRANSACTION;

-- Drop tables in reverse order to respect foreign key constraints
DROP TABLE IF EXISTS collection_extraction_jobs;
DROP TABLE IF EXISTS collection_extracted_metadata;
DROP TABLE IF EXISTS metadata_group_items;
DROP TABLE IF EXISTS metadata_groups;

-- Remove migration record
DELETE FROM schema_migrations 
WHERE version = 'add_metadata_extraction_tables_20241128';

-- Commit transaction
COMMIT;

-- Verify tables were removed
SELECT 
    'Rollback Verification:' as Message
UNION ALL
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN '✓ All metadata extraction tables removed successfully'
        ELSE CONCAT('❌ Warning: ', COUNT(*), ' table(s) still exist')
    END as Message
FROM information_schema.tables 
WHERE table_schema = DATABASE() 
AND table_name IN ('metadata_groups', 'metadata_group_items', 
                   'collection_extracted_metadata', 'collection_extraction_jobs');