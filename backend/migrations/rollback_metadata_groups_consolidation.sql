-- Rollback Script for Metadata Groups Consolidation Migration
-- Date: 2025-01-29
-- WARNING: This will revert the metadata groups consolidation changes

START TRANSACTION;

-- 1. Create old metadata_group_items table structure
CREATE TABLE IF NOT EXISTS metadata_group_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    metadata_config_id INT NOT NULL,
    display_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (metadata_config_id) REFERENCES MetadataConfiguration(id),
    UNIQUE KEY unique_group_metadata (group_id, metadata_config_id)
);

-- 2. Migrate data back from metadata_group_configs to metadata_group_items
INSERT IGNORE INTO metadata_group_items (group_id, metadata_config_id, created_at)
SELECT group_id, config_id, added_at
FROM metadata_group_configs;

-- 3. Drop the new tables
DROP TABLE IF EXISTS extraction_history;
DROP TABLE IF EXISTS metadata_group_configs;

-- 4. Remove new columns from metadata_groups
ALTER TABLE metadata_groups 
DROP COLUMN IF EXISTS color,
DROP COLUMN IF EXISTS tags,
DROP COLUMN IF EXISTS is_default;

-- 5. Remove new columns from MetadataConfiguration
ALTER TABLE MetadataConfiguration
DROP COLUMN IF EXISTS extraction_prompt_version,
DROP COLUMN IF EXISTS display_order;

-- 6. Remove extracted_content column from collection_extraction_jobs
ALTER TABLE collection_extraction_jobs
DROP COLUMN IF EXISTS extracted_content;

-- 7. Drop indexes
ALTER TABLE metadata_groups 
DROP INDEX IF EXISTS idx_metadata_groups_name;

ALTER TABLE MetadataConfiguration 
DROP INDEX IF EXISTS idx_metadata_config_active;

-- 8. Update migration record
UPDATE schema_migrations 
SET applied_at = NOW() 
WHERE version LIKE 'rollback_metadata_groups_consolidation_%';

INSERT INTO schema_migrations (version) 
VALUES (CONCAT('rollback_metadata_groups_consolidation_', DATE_FORMAT(NOW(), '%Y%m%d')))
ON DUPLICATE KEY UPDATE applied_at = CURRENT_TIMESTAMP;

COMMIT;

-- Note: The default "General" group will remain in the database as it may have legitimate associations