#!/usr/bin/env python3
"""
Migration to fix vector collection name column naming mismatch.
The code expects 'vector_db_collection_name' but the previous migration created 'vector_collection_name'.
This fixes the naming to match what the code expects.
"""

import sys
import os
from sqlalchemy import create_engine, text
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Fix the vector collection name column naming"""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.begin() as conn:
            # Fix collections table
            logger.info("Checking collections table columns...")
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'collections' 
                AND TABLE_SCHEMA = DATABASE()
                AND COLUMN_NAME IN ('chromadb_collection_name', 'vector_collection_name', 'vector_db_collection_name')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Found collections columns: {existing_columns}")
            
            if 'vector_db_collection_name' not in existing_columns:
                if 'chromadb_collection_name' in existing_columns:
                    logger.info("Renaming chromadb_collection_name to vector_db_collection_name...")
                    conn.execute(text("""
                        ALTER TABLE collections 
                        CHANGE COLUMN chromadb_collection_name vector_db_collection_name VARCHAR(255) UNIQUE NULL
                    """))
                    logger.info("Successfully renamed chromadb_collection_name to vector_db_collection_name")
                    
                elif 'vector_collection_name' in existing_columns:
                    logger.info("Renaming vector_collection_name to vector_db_collection_name...")
                    conn.execute(text("""
                        ALTER TABLE collections 
                        CHANGE COLUMN vector_collection_name vector_db_collection_name VARCHAR(255) UNIQUE NULL
                    """))
                    logger.info("Successfully renamed vector_collection_name to vector_db_collection_name")
                    
                else:
                    logger.info("Creating new vector_db_collection_name column...")
                    conn.execute(text("""
                        ALTER TABLE collections 
                        ADD COLUMN vector_db_collection_name VARCHAR(255) UNIQUE NULL
                    """))
                    logger.info("Created new vector_db_collection_name column")
            else:
                logger.info("Column vector_db_collection_name already exists in collections table.")
            
            # Fix SourceFiles table
            logger.info("Checking SourceFiles table columns...")
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'SourceFiles' 
                AND TABLE_SCHEMA = DATABASE()
                AND COLUMN_NAME IN ('chromadb_collections', 'vector_collections', 'vector_db_collections')
            """))
            
            sourcefiles_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Found SourceFiles columns: {sourcefiles_columns}")
            
            if 'vector_db_collections' not in sourcefiles_columns:
                if 'chromadb_collections' in sourcefiles_columns:
                    logger.info("Renaming chromadb_collections to vector_db_collections in SourceFiles...")
                    conn.execute(text("""
                        ALTER TABLE SourceFiles 
                        CHANGE COLUMN chromadb_collections vector_db_collections JSON DEFAULT ('[]')
                    """))
                    logger.info("Successfully renamed chromadb_collections to vector_db_collections")
                    
                elif 'vector_collections' in sourcefiles_columns:
                    logger.info("Renaming vector_collections to vector_db_collections in SourceFiles...")
                    conn.execute(text("""
                        ALTER TABLE SourceFiles 
                        CHANGE COLUMN vector_collections vector_db_collections JSON DEFAULT ('[]')
                    """))
                    logger.info("Successfully renamed vector_collections to vector_db_collections")
                    
                else:
                    logger.info("Creating new vector_db_collections column in SourceFiles...")
                    conn.execute(text("""
                        ALTER TABLE SourceFiles 
                        ADD COLUMN vector_db_collections JSON DEFAULT ('[]')
                    """))
                    logger.info("Created new vector_db_collections column")
            else:
                logger.info("Column vector_db_collections already exists in SourceFiles table.")
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()