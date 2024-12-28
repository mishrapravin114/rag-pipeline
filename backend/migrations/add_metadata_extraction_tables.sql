-- Migration: Add Metadata Extraction Tables
-- Date: 2024-11-28
-- Description: Creates tables for metadata groups, extraction jobs, and extracted metadata
-- 
-- Usage: 
-- 1. Backup your database before running this migration
-- 2. Run this script in your production MySQL database
-- 3. Verify all tables are created successfully

-- Start transaction
START TRANSACTION;

-- 1. Create metadata_groups table
CREATE TABLE IF NOT EXISTS metadata_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    FOREIGN KEY (created_by) REFERENCES Users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Create metadata_group_items table
CREATE TABLE IF NOT EXISTS metadata_group_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    metadata_config_id INT NOT NULL,
    display_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (metadata_config_id) REFERENCES MetadataConfiguration(id),
    UNIQUE KEY unique_group_metadata (group_id, metadata_config_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Create collection_extracted_metadata table
CREATE TABLE IF NOT EXISTS collection_extracted_metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    collection_id INT NOT NULL,
    document_id INT NOT NULL,
    group_id INT NOT NULL,
    metadata_name VARCHAR(255) NOT NULL,
    extracted_value TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES SourceFiles(id),
    FOREIGN KEY (group_id) REFERENCES metadata_groups(id),
    INDEX idx_collection_group (collection_id, group_id),
    INDEX idx_document_metadata (document_id, metadata_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Create collection_extraction_jobs table
CREATE TABLE IF NOT EXISTS collection_extraction_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    collection_id INT NOT NULL,
    group_id INT NOT NULL,
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    total_documents INT DEFAULT 0,
    processed_documents INT DEFAULT 0,
    failed_documents INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_by INT,
    error_details JSON,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    FOREIGN KEY (group_id) REFERENCES metadata_groups(id),
    FOREIGN KEY (created_by) REFERENCES Users(id),
    INDEX idx_status (status),
    INDEX idx_collection_status (collection_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Create schema_migrations table if it doesn't exist
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Record this migration
INSERT INTO schema_migrations (version) 
VALUES ('add_metadata_extraction_tables_20241128')
ON DUPLICATE KEY UPDATE applied_at = CURRENT_TIMESTAMP;

-- Commit transaction
COMMIT;

-- Verify tables were created
SELECT 
    'Verification Results:' as Message
UNION ALL
SELECT 
    CONCAT('✓ ', table_name, ' table exists') as Message
FROM information_schema.tables 
WHERE table_schema = DATABASE() 
AND table_name IN ('metadata_groups', 'metadata_group_items', 
                   'collection_extracted_metadata', 'collection_extraction_jobs');

-- Show table structures
SELECT '--- Table Structures ---' as Message;
SHOW CREATE TABLE metadata_groups;
SHOW CREATE TABLE metadata_group_items;
SHOW CREATE TABLE collection_extracted_metadata;
SHOW CREATE TABLE collection_extraction_jobs;