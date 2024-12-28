#!/usr/bin/env python3
"""
Migration to rename chromadb_collection_name to vector_collection_name in collections table
Also updates chromadb_doc_id to vector_doc_id in collection_document_association table
Also updates chromadb_collections to vector_collections in SourceFiles table

This migration is part of the ChromaDB to Qdrant migration effort.
"""

import sys
import os
from sqlalchemy import create_engine, text
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the migration to rename ChromaDB-specific columns"""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.begin() as conn:
            # 1. Rename chromadb_collection_name to vector_collection_name in collections table
            logger.info("Renaming chromadb_collection_name to vector_collection_name in collections table...")
            conn.execute(text("""
                ALTER TABLE collections 
                CHANGE COLUMN chromadb_collection_name vector_collection_name VARCHAR(255) UNIQUE NULL
            """))
            
            # 2. Rename chromadb_doc_id to vector_doc_id in collection_document_association table
            logger.info("Renaming chromadb_doc_id to vector_doc_id in collection_document_association table...")
            conn.execute(text("""
                ALTER TABLE collection_document_association 
                CHANGE COLUMN chromadb_doc_id vector_doc_id VARCHAR(255) NULL
            """))
            
            # 3. Rename chromadb_collections to vector_collections in SourceFiles table
            logger.info("Renaming chromadb_collections to vector_collections in SourceFiles table...")
            conn.execute(text("""
                ALTER TABLE SourceFiles 
                CHANGE COLUMN chromadb_collections vector_collections JSON DEFAULT ('[]')
            """))
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

def rollback_migration():
    """Rollback the migration"""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.begin() as conn:
            # Rollback in reverse order
            logger.info("Rolling back: Renaming vector_collections back to chromadb_collections in SourceFiles table...")
            conn.execute(text("""
                ALTER TABLE SourceFiles 
                CHANGE COLUMN vector_collections chromadb_collections JSON DEFAULT ('[]')
            """))
            
            logger.info("Rolling back: Renaming vector_doc_id back to chromadb_doc_id in collection_document_association table...")
            conn.execute(text("""
                ALTER TABLE collection_document_association 
                CHANGE COLUMN vector_doc_id chromadb_doc_id VARCHAR(255) NULL
            """))
            
            logger.info("Rolling back: Renaming vector_collection_name back to chromadb_collection_name in collections table...")
            conn.execute(text("""
                ALTER TABLE collections 
                CHANGE COLUMN vector_collection_name chromadb_collection_name VARCHAR(255) UNIQUE NULL
            """))
            
            logger.info("Rollback completed successfully!")
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()