#!/usr/bin/env python3
"""
Simple script to process all pending files in the FDA RAG pipeline
Can be run as a cron job for periodic processing
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.database import SessionLocal, SourceFiles
from src.fda_pipeline import FDAPipelineV2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_all_pending():
    """Process all files with PENDING status"""
    db = SessionLocal()
    pipeline = FDAPipelineV2()
    
    try:
        # Get count of pending files
        pending_count = db.query(SourceFiles).filter(SourceFiles.status == "PENDING").count()
        logger.info(f"Found {pending_count} pending files to process")
        
        if pending_count == 0:
            logger.info("No pending files to process")
            return
        
        # Process pending files
        result = pipeline.process_pending_files(db)
        
        # Log results
        logger.info(f"Processing complete:")
        logger.info(f"  Successfully processed: {result['successful']}")
        logger.info(f"  Failed: {result['failed']}")
        
        if result['errors']:
            logger.error("Errors encountered:")
            for file_id, error in result['errors'].items():
                logger.error(f"  File {file_id}: {error}")
                
    except Exception as e:
        logger.error(f"Error processing pending files: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting pending files processor...")
    process_all_pending()
    logger.info("Processing complete")