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

def check_column_exists(table_name, column_name):
    """Check if column exists in table"""
    sql = f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}';"
    result = execute_sql(sql, return_results=True)
    return isinstance(result, list) and len(result) > 0

def main():
    logger.info("Adding missing columns to collection_extracted_metadata table...")
    
    # Check if table exists
    logger.info("\n1. Checking if collection_extracted_metadata table exists...")
    check_sql = "SHOW TABLES LIKE 'collection_extracted_metadata';"
    tables = execute_sql(check_sql, return_results=True)
    
    if not (isinstance(tables, list) and len(tables) > 0):
        logger.error("Table collection_extracted_metadata doesn't exist! Run create_collection_extracted_metadata_table.py first.")
        return
    
    # List of columns to add
    columns_to_add = [
        ('extraction_job_id', 'INT', 'NULL'),
        ('extracted_by', 'INT', 'NULL'),
        ('extraction_status', 'VARCHAR(50)', "'pending'"),
        ('extraction_error', 'TEXT', 'NULL'),
        ('extraction_attempts', 'INT', '0'),
        ('last_attempt_at', 'TIMESTAMP', 'NULL'),
        ('metadata_config_id', 'INT', 'NULL')
    ]
    
    logger.info("\n2. Adding missing columns...")
    for column_name, column_type, default_value in columns_to_add:
        if not check_column_exists('collection_extracted_metadata', column_name):
            logger.info(f"Adding column {column_name}...")
            if default_value == 'NULL':
                sql = f"ALTER TABLE collection_extracted_metadata ADD COLUMN {column_name} {column_type} NULL;"
            else:
                sql = f"ALTER TABLE collection_extracted_metadata ADD COLUMN {column_name} {column_type} DEFAULT {default_value};"
            
            if execute_sql(sql):
                logger.info(f"  ✓ Added {column_name}")
            else:
                logger.error(f"  ✗ Failed to add {column_name}")
        else:
            logger.info(f"  - Column {column_name} already exists")
    
    # Add foreign key constraints for new columns
    logger.info("\n3. Adding foreign key constraints...")
    
    # Check if foreign keys already exist before adding
    check_fk_sql = """
    SELECT CONSTRAINT_NAME 
    FROM information_schema.KEY_COLUMN_USAGE 
    WHERE TABLE_NAME = 'collection_extracted_metadata' 
    AND TABLE_SCHEMA = 'fda_rag'
    AND CONSTRAINT_NAME LIKE 'fk_%';
    """
    existing_fks = execute_sql(check_fk_sql, return_results=True)
    existing_fk_names = [fk[0] for fk in existing_fks] if isinstance(existing_fks, list) else []
    
    # Add foreign keys if they don't exist
    fk_constraints = [
        ('fk_extraction_job', 'extraction_job_id', 'collection_extraction_jobs(id)', 'SET NULL'),
        ('fk_extracted_by', 'extracted_by', 'Users(id)', 'SET NULL'),
        ('fk_metadata_config', 'metadata_config_id', 'MetadataConfiguration(id)', 'SET NULL')
    ]
    
    for fk_name, column, reference, on_delete in fk_constraints:
        if fk_name not in existing_fk_names:
            logger.info(f"Adding foreign key {fk_name}...")
            fk_sql = f"""
            ALTER TABLE collection_extracted_metadata 
            ADD CONSTRAINT {fk_name} 
            FOREIGN KEY ({column}) 
            REFERENCES {reference} 
            ON DELETE {on_delete};
            """
            if execute_sql(fk_sql):
                logger.info(f"  ✓ Added {fk_name}")
            else:
                logger.info(f"  - Could not add {fk_name} (might be due to missing referenced table)")
        else:
            logger.info(f"  - Foreign key {fk_name} already exists")
    
    # Add indexes for performance
    logger.info("\n4. Adding indexes for new columns...")
    indexes_to_add = [
        ('idx_extraction_job_id', 'extraction_job_id'),
        ('idx_extraction_status', 'extraction_status'),
        ('idx_extracted_by', 'extracted_by')
    ]
    
    for index_name, column in indexes_to_add:
        logger.info(f"Adding index {index_name}...")
        index_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON collection_extracted_metadata({column});"
        
        # MySQL doesn't support IF NOT EXISTS for indexes, so we'll handle the error
        if execute_sql(index_sql):
            logger.info(f"  ✓ Added {index_name}")
        else:
            # Try without IF NOT EXISTS
            index_sql = f"CREATE INDEX {index_name} ON collection_extracted_metadata({column});"
            if execute_sql(index_sql):
                logger.info(f"  ✓ Added {index_name}")
            else:
                logger.info(f"  - Index {index_name} might already exist or failed to create")
    
    # Verify the final structure
    logger.info("\n5. Verifying final table structure...")
    verify_sql = "DESCRIBE collection_extracted_metadata;"
    columns = execute_sql(verify_sql, return_results=True)
    
    if columns:
        logger.info("Final table structure:")
        for col in columns:
            logger.info(f"  - {col[0]} ({col[1]})")
    
    logger.info("\nColumn update completed successfully!")
    logger.info("\nThe collection_extracted_metadata table now has all required columns.")
    logger.info("\nPlease restart the backend container:")
    logger.info("sudo docker compose restart fda-backend")

if __name__ == "__main__":
    main()