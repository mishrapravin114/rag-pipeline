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
    logger.info("Fixing extraction jobs datetime issue...")
    
    # First, check the collection_extraction_jobs table structure
    logger.info("\n1. Checking collection_extraction_jobs table structure...")
    sql = "SHOW COLUMNS FROM collection_extraction_jobs;"
    columns = execute_sql(sql, return_results=True)
    
    if columns:
        logger.info("collection_extraction_jobs columns:")
        for col in columns:
            logger.info(f"  - {col[0]} ({col[1]})")
    
    # Check for rows with NULL created_at
    logger.info("\n2. Checking for rows with NULL created_at...")
    sql = "SELECT COUNT(*) FROM collection_extraction_jobs WHERE created_at IS NULL;"
    result = execute_sql(sql, return_results=True)
    
    if result and result[0][0] != '0':
        count = result[0][0]
        logger.info(f"Found {count} rows with NULL created_at")
        
        # Fix by setting created_at to current timestamp
        logger.info("Setting created_at to current timestamp for NULL values...")
        fix_sql = "UPDATE collection_extraction_jobs SET created_at = NOW() WHERE created_at IS NULL;"
        if execute_sql(fix_sql):
            logger.info("Updated NULL created_at values successfully!")
        else:
            logger.error("Failed to update NULL created_at values!")
    else:
        logger.info("No rows with NULL created_at found")
    
    # Check the extraction_jobs table if it exists
    logger.info("\n3. Checking extraction_jobs table (if exists)...")
    table_check_sql = "SHOW TABLES LIKE 'extraction_jobs';"
    tables = execute_sql(table_check_sql, return_results=True)
    
    if isinstance(tables, list) and len(tables) > 0:
        # Check structure
        sql = "SHOW COLUMNS FROM extraction_jobs;"
        columns = execute_sql(sql, return_results=True)
        
        if columns:
            logger.info("extraction_jobs columns:")
            for col in columns:
                logger.info(f"  - {col[0]} ({col[1]})")
        
        # Check for NULL created_at
        sql = "SELECT COUNT(*) FROM extraction_jobs WHERE created_at IS NULL;"
        result = execute_sql(sql, return_results=True)
        
        if result and result[0][0] != '0':
            count = result[0][0]
            logger.info(f"Found {count} rows with NULL created_at in extraction_jobs")
            
            # Fix by setting created_at to current timestamp
            logger.info("Setting created_at to current timestamp for NULL values...")
            fix_sql = "UPDATE extraction_jobs SET created_at = NOW() WHERE created_at IS NULL;"
            if execute_sql(fix_sql):
                logger.info("Updated NULL created_at values successfully!")
            else:
                logger.error("Failed to update NULL created_at values!")
    
    # Add default value to created_at column to prevent future NULLs
    logger.info("\n4. Adding default value to created_at columns...")
    
    # For collection_extraction_jobs
    alter_sql1 = """
    ALTER TABLE collection_extraction_jobs 
    MODIFY COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """
    
    logger.info("Updating collection_extraction_jobs.created_at column...")
    if execute_sql(alter_sql1):
        logger.info("Updated successfully!")
    else:
        logger.info("Column might already have default value or update failed")
    
    # For extraction_jobs if it exists
    if isinstance(tables, list) and len(tables) > 0:
        alter_sql2 = """
        ALTER TABLE extraction_jobs 
        MODIFY COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """
        
        logger.info("Updating extraction_jobs.created_at column...")
        if execute_sql(alter_sql2):
            logger.info("Updated successfully!")
        else:
            logger.info("Column might already have default value or update failed")
    
    # Verify the fix
    logger.info("\n5. Verifying the fix...")
    sql = "SELECT id, status, created_at FROM collection_extraction_jobs ORDER BY id DESC LIMIT 5;"
    results = execute_sql(sql, return_results=True)
    
    if results:
        logger.info("Sample collection_extraction_jobs records:")
        for row in results:
            logger.info(f"  ID: {row[0]}, Status: {row[1]}, Created: {row[2]}")
    
    logger.info("\nDatetime fix completed!")
    logger.info("Please restart the backend container if the error persists:")
    logger.info("sudo docker compose restart fda-backend")

if __name__ == "__main__":
    main()