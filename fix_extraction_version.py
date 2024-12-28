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
    logger.info("Fixing extraction_prompt_version data type issue...")
    
    # First, check the current values
    logger.info("\n1. Checking current extraction_prompt_version values...")
    sql = "SELECT DISTINCT extraction_prompt_version FROM MetadataConfiguration;"
    values = execute_sql(sql, return_results=True)
    
    if values:
        logger.info("Current values:")
        for val in values:
            logger.info(f"  - {val[0]}")
    
    # Check the column type
    logger.info("\n2. Checking column data type...")
    sql = "SHOW COLUMNS FROM MetadataConfiguration WHERE Field = 'extraction_prompt_version';"
    column_info = execute_sql(sql, return_results=True)
    
    if column_info:
        logger.info(f"Current column type: {column_info[0][1]}")
    
    logger.info("\n3. Converting string values to integers...")
    
    # Update the values - convert 'v1' to 1, 'v2' to 2, etc.
    update_queries = [
        "UPDATE MetadataConfiguration SET extraction_prompt_version = '1' WHERE extraction_prompt_version = 'v1';",
        "UPDATE MetadataConfiguration SET extraction_prompt_version = '2' WHERE extraction_prompt_version = 'v2';",
        "UPDATE MetadataConfiguration SET extraction_prompt_version = '3' WHERE extraction_prompt_version = 'v3';",
        # Set any null or other values to 1 as default
        "UPDATE MetadataConfiguration SET extraction_prompt_version = '1' WHERE extraction_prompt_version IS NULL OR extraction_prompt_version NOT IN ('1', '2', '3');"
    ]
    
    for query in update_queries:
        logger.info(f"Executing: {query}")
        execute_sql(query)
    
    # Now change the column type to INT
    logger.info("\n4. Changing column type to INT...")
    alter_sql = "ALTER TABLE MetadataConfiguration MODIFY COLUMN extraction_prompt_version INT DEFAULT 1;"
    
    if execute_sql(alter_sql):
        logger.info("Column type changed successfully!")
    else:
        logger.error("Failed to change column type!")
        logger.info("\nTrying alternative approach - adding a new column...")
        
        # Alternative approach - create new column, copy data, drop old, rename
        alternative_queries = [
            "ALTER TABLE MetadataConfiguration ADD COLUMN extraction_prompt_version_new INT DEFAULT 1;",
            "UPDATE MetadataConfiguration SET extraction_prompt_version_new = CAST(extraction_prompt_version AS UNSIGNED);",
            "ALTER TABLE MetadataConfiguration DROP COLUMN extraction_prompt_version;",
            "ALTER TABLE MetadataConfiguration CHANGE COLUMN extraction_prompt_version_new extraction_prompt_version INT DEFAULT 1;"
        ]
        
        for query in alternative_queries:
            logger.info(f"Executing: {query}")
            if not execute_sql(query):
                logger.error(f"Failed at: {query}")
                break
    
    # Verify the fix
    logger.info("\n5. Verifying the fix...")
    sql = "SELECT id, extraction_prompt_version FROM MetadataConfiguration LIMIT 5;"
    results = execute_sql(sql, return_results=True)
    
    if results:
        logger.info("Sample values after fix:")
        for row in results:
            logger.info(f"  ID: {row[0]}, Version: {row[1]}")
    
    # Check column type again
    sql = "SHOW COLUMNS FROM MetadataConfiguration WHERE Field = 'extraction_prompt_version';"
    column_info = execute_sql(sql, return_results=True)
    
    if column_info:
        logger.info(f"\nFinal column type: {column_info[0][1]}")
    
    logger.info("\nFix completed! Please restart the backend container:")
    logger.info("sudo docker-compose restart fda-backend")

if __name__ == "__main__":
    main()