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
    logger.info("Checking SourceFiles table structure...")
    
    # Check SourceFiles columns
    sql = "SHOW COLUMNS FROM SourceFiles;"
    columns = execute_sql(sql, return_results=True)
    
    if columns:
        logger.info("\nSourceFiles table columns:")
        column_names = []
        for col in columns:
            column_names.append(col[0])
            logger.info(f"  - {col[0]} ({col[1]})")
        
        # Check if extracted_content exists
        if 'extracted_content' not in column_names:
            logger.warning("\n'extracted_content' column does NOT exist in SourceFiles table!")
            logger.info("\nThis is causing the error. The SQLAlchemy model needs to be updated.")
            
            logger.info("\nTo fix this issue, you need to:")
            logger.info("1. Remove the 'extracted_content' field from the SourceFiles model in the backend code")
            logger.info("2. OR add the column to the database with this SQL:")
            logger.info("\n   ALTER TABLE SourceFiles ADD COLUMN extracted_content LONGTEXT NULL;")
            
            # Ask user what to do
            logger.info("\nWould you like to add the missing column to the database? (y/n)")
            response = input().strip().lower()
            
            if response == 'y':
                logger.info("\nAdding extracted_content column to SourceFiles table...")
                add_column_sql = "ALTER TABLE SourceFiles ADD COLUMN extracted_content LONGTEXT NULL;"
                if execute_sql(add_column_sql):
                    logger.info("Column added successfully!")
                    logger.info("\nPlease restart the backend container:")
                    logger.info("sudo docker-compose restart fda-backend")
                else:
                    logger.error("Failed to add column!")
            else:
                logger.info("\nTo fix this manually, edit the SourceFiles model in the backend code")
                logger.info("and remove the 'extracted_content' field.")
                logger.info("\nThe model is likely located at:")
                logger.info("backend/src/database/models.py or backend/src/models/source_files.py")
        else:
            logger.info("\n'extracted_content' column EXISTS in the database.")
            logger.info("The error might be caused by something else.")
    else:
        logger.error("Could not retrieve SourceFiles table structure!")
        
if __name__ == "__main__":
    main()