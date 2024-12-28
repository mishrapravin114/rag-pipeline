#!/usr/bin/env python3
"""
Add unique constraint to collection_extracted_metadata table
to ensure only one entry per collection/document/group/metadata_name combination
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database.database import SQLALCHEMY_DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_unique_constraint():
    """Add unique constraint to prevent duplicate metadata entries"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.begin() as conn:
        try:
            # First, remove any existing duplicates (keep the most recent one)
            logger.info("Removing duplicate entries...")
            
            # This query keeps only the most recent entry for each unique combination
            conn.execute(text("""
                DELETE t1 FROM collection_extracted_metadata t1
                INNER JOIN collection_extracted_metadata t2
                WHERE t1.id < t2.id
                AND t1.collection_id = t2.collection_id
                AND t1.document_id = t2.document_id
                AND t1.group_id = t2.group_id
                AND t1.metadata_name = t2.metadata_name
            """))
            
            # Now add the unique constraint
            logger.info("Adding unique constraint...")
            conn.execute(text("""
                ALTER TABLE collection_extracted_metadata
                ADD UNIQUE KEY unique_metadata_entry (
                    collection_id, 
                    document_id, 
                    group_id, 
                    metadata_name
                )
            """))
            
            logger.info("Unique constraint added successfully!")
            
        except Exception as e:
            if "Duplicate key name" in str(e):
                logger.info("Unique constraint already exists")
            else:
                logger.error(f"Error adding unique constraint: {e}")
                raise


if __name__ == "__main__":
    add_unique_constraint()