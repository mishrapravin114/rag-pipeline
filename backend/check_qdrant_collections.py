#!/usr/bin/env python3
"""
Check what collections exist in Qdrant
"""

from qdrant_client import QdrantClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_qdrant_collections():
    """Check what collections exist in Qdrant"""
    try:
        # Connect to Qdrant
        client = QdrantClient(host="qdrant", port=6333, timeout=60)
        
        # Get all collections
        collections = client.get_collections()
        
        logger.info(f"Found {len(collections.collections)} collections in Qdrant:")
        
        for collection in collections.collections:
            name = collection.name
            
            # Get collection info
            info = client.get_collection(name)
            count = client.count(collection_name=name)
            
            logger.info(f"  - {name}: {count.count} vectors, status: {info.status}")
            
            # Get a sample document to check format
            sample = client.scroll(
                collection_name=name,
                limit=1,
                with_payload=True
            )
            
            if sample[0]:
                payload = sample[0][0].payload
                has_agno_format = all(key in payload for key in ['content', 'name', 'usage', 'meta_data'])
                logger.info(f"    Sample Agno format: {has_agno_format}")
                logger.info(f"    Sample keys: {list(payload.keys())}")
            
        return collections.collections
        
    except Exception as e:
        logger.error(f"Error checking Qdrant collections: {e}")
        return []

if __name__ == "__main__":
    check_qdrant_collections()