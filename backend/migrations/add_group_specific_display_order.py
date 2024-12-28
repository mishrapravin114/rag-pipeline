#!/usr/bin/env python3
"""
Migration script to add group-specific display_order to metadata_group_configs association table.
This allows configurations to have different display orders in different groups.
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

def run_migration():
    """Add display_order column to metadata_group_configs association table"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Step 1: Add display_order column to the association table
        logger.info("Checking if display_order column already exists...")
        
        # Check if column already exists
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'metadata_group_configs' 
            AND COLUMN_NAME = 'display_order'
        """))
        column_exists = result.scalar() > 0
        
        if not column_exists:
            logger.info("Adding display_order column to metadata_group_configs table...")
            session.execute(text("""
                ALTER TABLE metadata_group_configs 
                ADD COLUMN display_order INT DEFAULT 0
            """))
            session.commit()
        else:
            logger.info("display_order column already exists, skipping...")
        
        # Step 2: Initialize display_order values based on current configuration order
        logger.info("Initializing display_order values for existing associations...")
        
        # Get all groups
        groups = session.execute(text("SELECT DISTINCT group_id FROM metadata_group_configs")).fetchall()
        
        for (group_id,) in groups:
            # Get configurations for this group ordered by their current display_order
            configs = session.execute(text("""
                SELECT mgc.config_id, mc.display_order 
                FROM metadata_group_configs mgc
                JOIN MetadataConfiguration mc ON mgc.config_id = mc.id
                WHERE mgc.group_id = :group_id
                ORDER BY mc.display_order, mc.id
            """), {"group_id": group_id}).fetchall()
            
            # Update each association with its position in the group
            for idx, (config_id, _) in enumerate(configs):
                session.execute(text("""
                    UPDATE metadata_group_configs 
                    SET display_order = :order_idx
                    WHERE group_id = :group_id AND config_id = :config_id
                """), {
                    "order_idx": idx,
                    "group_id": group_id,
                    "config_id": config_id
                })
            
            logger.info(f"Updated display_order for {len(configs)} configurations in group {group_id}")
        
        session.commit()
        
        # Step 3: Remove display_order column from MetadataConfiguration table
        logger.info("Checking if display_order column exists in MetadataConfiguration table...")
        
        # Check if column exists
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MetadataConfiguration' 
            AND COLUMN_NAME = 'display_order'
        """))
        column_exists = result.scalar() > 0
        
        if column_exists:
            logger.info("Removing display_order column from MetadataConfiguration table...")
            session.execute(text("""
                ALTER TABLE MetadataConfiguration 
                DROP COLUMN display_order
            """))
            session.commit()
        else:
            logger.info("display_order column doesn't exist in MetadataConfiguration, skipping...")
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()