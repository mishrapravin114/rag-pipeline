#!/usr/bin/env python3
import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
DB_NAME = "fda_rag"
DB_USER = "fda_user"
DB_PASSWORD = "fda_password"
DB_HOST = "localhost"
DB_PORT = "3307"
CONTAINER_NAME = "mysql-db"

def execute_sql(sql, return_results=False):
    """Execute SQL command using docker"""
    try:
        cmd = [
            'sudo', 'docker', 'exec', '-i', CONTAINER_NAME,
            'mysql', '-u', DB_USER, f'-p{DB_PASSWORD}', DB_NAME, '-e', sql
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"SQL Error: {result.stderr}")
            return False if not return_results else []
            
        if return_results and result.stdout:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header
                return [line.split('\t') for line in lines[1:]]
            return []
        
        return True
        
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return False if not return_results else []

def main():
    logger.info("Creating collection_extracted_metadata table...")
    
    # Check if table already exists
    logger.info("\n1. Checking if collection_extracted_metadata table exists...")
    check_sql = "SHOW TABLES LIKE 'collection_extracted_metadata';"
    tables = execute_sql(check_sql, return_results=True)
    
    if isinstance(tables, list) and len(tables) > 0:
        logger.info("Table collection_extracted_metadata already exists!")
        return
    
    # Create the table
    logger.info("\n2. Creating collection_extracted_metadata table...")
    create_table_sql = """
    CREATE TABLE collection_extracted_metadata (
        id INT AUTO_INCREMENT PRIMARY KEY,
        collection_id INT NOT NULL,
        document_id INT NOT NULL,
        group_id INT NOT NULL,
        metadata_name VARCHAR(255) NOT NULL,
        extracted_value TEXT,
        confidence_score FLOAT,
        extraction_method VARCHAR(50),
        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        -- Foreign keys
        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
        FOREIGN KEY (document_id) REFERENCES SourceFiles(id) ON DELETE CASCADE,
        FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
        
        -- Indexes for performance
        INDEX idx_collection_id (collection_id),
        INDEX idx_document_id (document_id),
        INDEX idx_group_id (group_id),
        INDEX idx_metadata_name (metadata_name),
        INDEX idx_collection_group (collection_id, group_id),
        INDEX idx_collection_document (collection_id, document_id),
        
        -- Unique constraint to prevent duplicate metadata entries
        UNIQUE KEY unique_collection_doc_group_metadata (collection_id, document_id, group_id, metadata_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    if execute_sql(create_table_sql):
        logger.info("Table created successfully!")
    else:
        logger.error("Failed to create table!")
        return
    
    # Verify the table was created
    logger.info("\n3. Verifying table creation...")
    verify_sql = "DESCRIBE collection_extracted_metadata;"
    columns = execute_sql(verify_sql, return_results=True)
    
    if columns:
        logger.info("Table structure:")
        for col in columns:
            logger.info(f"  - {col[0]} ({col[1]})")
    
    # Check if there's any data to migrate from collection_extraction_jobs
    logger.info("\n4. Checking for existing extraction data to migrate...")
    check_data_sql = """
    SELECT COUNT(*) 
    FROM collection_extraction_jobs 
    WHERE status = 'completed' AND extracted_content IS NOT NULL;
    """
    result = execute_sql(check_data_sql, return_results=True)
    
    if result and result[0][0] != '0':
        count = result[0][0]
        logger.info(f"Found {count} completed extraction jobs that might have data to migrate")
        logger.info("Note: You may need to run a separate migration script to populate this table with existing data")
    else:
        logger.info("No existing extraction data found to migrate")
    
    # Add a sample record to test
    logger.info("\n5. Adding migration record...")
    migration_sql = """
    INSERT IGNORE INTO schema_migrations (version) 
    VALUES ('20240115_create_collection_extracted_metadata');
    """
    execute_sql(migration_sql)
    
    logger.info("\nTable creation completed successfully!")
    logger.info("\nThe collection_extracted_metadata table is now ready to store extracted metadata from collections.")
    logger.info("\nPlease restart the backend container:")
    logger.info("sudo docker compose restart fda-backend")

if __name__ == "__main__":
    main()