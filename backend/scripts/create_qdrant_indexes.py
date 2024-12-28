#!/usr/bin/env python3
"""
Script to create payload indexes in Qdrant collections for better filtering performance
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.qdrant_singleton import get_qdrant_client
from qdrant_client.http.models import PayloadSchemaType
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_source_index(collection_name: str):
    """Create an index on meta_data.source field for faster filtering"""
    try:
        client = get_qdrant_client()
        
        logger.info(f"Creating payload index for collection: {collection_name}")
        
        # Create index on meta_data.source field
        client.create_payload_index(
            collection_name=collection_name,
            field_name="meta_data.source",
            field_schema=PayloadSchemaType.KEYWORD
        )
        
        logger.info(f"Successfully created index on meta_data.source for {collection_name}")
        
        # Also create index on meta_data.file_name if it exists
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="meta_data.file_name", 
                field_schema=PayloadSchemaType.KEYWORD
            )
            logger.info(f"Successfully created index on meta_data.file_name for {collection_name}")
        except Exception as e:
            logger.warning(f"Could not create index on meta_data.file_name: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create payload index: {e}")
        return False

def main():
    """Create indexes for all collections"""
    client = get_qdrant_client()
    collections = client.get_collections()
    
    for collection in collections.collections:
        if collection.name.startswith('collection_'):
            logger.info(f"Processing collection: {collection.name}")
            create_source_index(collection.name)
    
    logger.info("Index creation completed")

if __name__ == "__main__":
    main()