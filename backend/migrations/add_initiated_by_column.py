#!/usr/bin/env python3
"""
Add initiated_by column to collection_extraction_jobs table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from src.database.database import SQLALCHEMY_DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_initiated_by_column():
    """Add initiated_by column to track who started the extraction job"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.begin() as conn:
        try:
            # Check if column already exists
            check_column = text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'collection_extraction_jobs' 
                AND column_name = 'initiated_by'
            """)
            
            result = conn.execute(check_column).scalar()
            
            if result == 0:
                # Add the column
                logger.info("Adding initiated_by column...")
                conn.execute(text("""
                    ALTER TABLE collection_extraction_jobs
                    ADD COLUMN initiated_by INT DEFAULT NULL
                    COMMENT 'User ID who initiated the extraction'
                """))
                
                # Add foreign key constraint
                logger.info("Adding foreign key constraint...")
                conn.execute(text("""
                    ALTER TABLE collection_extraction_jobs
                    ADD CONSTRAINT fk_extraction_jobs_user
                    FOREIGN KEY (initiated_by) REFERENCES Users(id)
                    ON DELETE SET NULL
                """))
                
                logger.info("Column added successfully!")
            else:
                logger.info("initiated_by column already exists")
                
        except Exception as e:
            logger.error(f"Error adding initiated_by column: {e}")
            raise


if __name__ == "__main__":
    add_initiated_by_column()