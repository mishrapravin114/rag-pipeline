#!/usr/bin/env python3
"""
Rollback script for group-specific display_order migration.
Restores display_order to MetadataConfiguration table.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_rollback():
    """Rollback the group-specific display_order migration"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Step 1: Add display_order column back to MetadataConfiguration table
        logger.info("Checking if display_order column exists in MetadataConfiguration table...")
        
        # Check if column already exists
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MetadataConfiguration' 
            AND COLUMN_NAME = 'display_order'
        """))
        column_exists = result.scalar() > 0
        
        if not column_exists:
            logger.info("Adding display_order column back to MetadataConfiguration table...")
            session.execute(text("""
                ALTER TABLE MetadataConfiguration 
                ADD COLUMN display_order INT DEFAULT 0
            """))
            session.commit()
        else:
            logger.info("display_order column already exists in MetadataConfiguration, skipping...")
        
        # Step 2: Restore display_order values (use average or first group's order)
        logger.info("Restoring display_order values to MetadataConfiguration...")
        
        # For each configuration, set display_order to its order in its first group
        session.execute(text("""
            UPDATE MetadataConfiguration mc
            SET display_order = COALESCE(
                (SELECT mgc.display_order 
                 FROM metadata_group_configs mgc 
                 WHERE mgc.config_id = mc.id 
                 ORDER BY mgc.group_id 
                 LIMIT 1), 
                0
            )
        """))
        session.commit()
        
        # Step 3: Remove display_order column from metadata_group_configs table
        logger.info("Checking if display_order column exists in metadata_group_configs table...")
        
        # Check if column exists
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'metadata_group_configs' 
            AND COLUMN_NAME = 'display_order'
        """))
        column_exists = result.scalar() > 0
        
        if column_exists:
            logger.info("Removing display_order column from metadata_group_configs table...")
            session.execute(text("""
                ALTER TABLE metadata_group_configs 
                DROP COLUMN display_order
            """))
            session.commit()
        else:
            logger.info("display_order column doesn't exist in metadata_group_configs, skipping...")
        
        logger.info("Rollback completed successfully!")
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_rollback()