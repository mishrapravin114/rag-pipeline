-- Metadata Groups Consolidation Migration
-- Date: 2025-01-29
-- Description: Creates and updates tables for metadata groups consolidation as per masterplan

-- Start transaction
START TRANSACTION;

-- 1. Update metadata_groups table to match masterplan
ALTER TABLE metadata_groups 
ADD COLUMN IF NOT EXISTS color VARCHAR(7) DEFAULT '#3B82F6',
ADD COLUMN IF NOT EXISTS tags JSON,
ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;

-- 2. Update MetadataConfiguration table
ALTER TABLE MetadataConfiguration
ADD COLUMN IF NOT EXISTS extraction_prompt_version INT DEFAULT 1,
ADD COLUMN IF NOT EXISTS display_order INT DEFAULT 0;

-- 3. Create metadata_group_configs junction table (replacement for metadata_group_items)
CREATE TABLE IF NOT EXISTS metadata_group_configs (
    group_id INT NOT NULL,
    config_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by INT,
    PRIMARY KEY (group_id, config_id),
    FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (config_id) REFERENCES MetadataConfiguration(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES Users(id),
    INDEX idx_config_groups (config_id, group_id)
);

-- 4. Migrate data from metadata_group_items to metadata_group_configs if exists
-- (This will only run if the old table exists)
INSERT IGNORE INTO metadata_group_configs (group_id, config_id, added_at)
SELECT group_id, metadata_config_id, created_at
FROM metadata_group_items
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'metadata_group_items'
);

-- Drop the old table if exists
DROP TABLE IF EXISTS metadata_group_items;

-- 5. Create extraction_history table
CREATE TABLE IF NOT EXISTS extraction_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    config_id INT NOT NULL,
    prompt_version INT NOT NULL,
    extracted_value JSON,
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (document_id) REFERENCES SourceFiles(id) ON DELETE CASCADE,
    FOREIGN KEY (config_id) REFERENCES MetadataConfiguration(id),
    INDEX idx_doc_config (document_id, config_id),
    INDEX idx_extraction_date (extraction_date)
);

-- 6. Create default "General" metadata group
INSERT IGNORE INTO metadata_groups (name, description, color, is_default)
VALUES ('General', 'Default group for uncategorized metadata configurations', '#6B7280', TRUE);

-- 7. Assign all orphaned MetadataConfiguration to default group
-- Get the default group ID and assign orphaned configurations
INSERT INTO metadata_group_configs (group_id, config_id)
SELECT 
    (SELECT id FROM metadata_groups WHERE is_default = TRUE LIMIT 1),
    mc.id
FROM MetadataConfiguration mc
LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
WHERE mgc.config_id IS NULL;

-- 8. Update collection_extraction_jobs table
ALTER TABLE collection_extraction_jobs
ADD COLUMN IF NOT EXISTS extracted_content JSON,
MODIFY COLUMN status VARCHAR(50) DEFAULT 'pending';

-- 9. Add indexes for performance
ALTER TABLE metadata_groups 
ADD INDEX IF NOT EXISTS idx_metadata_groups_name (name);

ALTER TABLE MetadataConfiguration 
ADD INDEX IF NOT EXISTS idx_metadata_config_active (is_active, display_order);

-- 10. Record migration
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version) 
VALUES (CONCAT('add_metadata_groups_consolidation_', DATE_FORMAT(NOW(), '%Y%m%d')))
ON DUPLICATE KEY UPDATE applied_at = CURRENT_TIMESTAMP;

-- Commit transaction
COMMIT;

-- Verification queries (run these after migration)
-- SELECT COUNT(*) AS total_groups FROM metadata_groups;
-- SELECT COUNT(*) AS total_configs FROM MetadataConfiguration;
-- SELECT COUNT(*) AS total_assignments FROM metadata_group_configs;
-- SELECT COUNT(*) AS orphaned_configs FROM MetadataConfiguration mc LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id WHERE mgc.config_id IS NULL;