#!/usr/bin/env python3
"""
Simple ChromaDB to Qdrant migration script focusing on collection_35_ema.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_collection_35_ema():
    """Migrate collection_35_ema from ChromaDB to Qdrant."""
    
    try:
        # Setup ChromaDB
        import chromadb
        from chromadb.config import Settings
        
        chromadb_path = "/app/data/chromadb"
        client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=False)
        )
        
        # Setup Qdrant
        qdrant_client = QdrantClient(host="qdrant", port=6333, timeout=60)
        
        # Get source collection
        source_collection = client.get_collection("collection_35_ema")
        total_count = source_collection.count()
        logger.info(f"Source collection has {total_count} documents")
        
        # Create target collection in Qdrant
        target_collection_name = "collection_35_ema"
        vector_size = 1536  # Default size, will adjust if needed
        
        try:
            qdrant_client.create_collection(
                collection_name=target_collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {target_collection_name}")
        except Exception:
            logger.info(f"Collection {target_collection_name} already exists")
        
        # Migration parameters
        batch_size = 100
        total_migrated = 0
        
        # Get all documents in batches
        offset = 0
        
        while offset < total_count:
            logger.info(f"Processing batch {offset}-{offset+batch_size} / {total_count}")
            
            try:
                # Get batch from ChromaDB
                results = source_collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=['embeddings', 'metadatas', 'documents']
                )
                
                if not results['ids']:
                    break
                
                # Detect vector size from first embedding
                if offset == 0:
                    try:
                        embeddings = results.get('embeddings')
                        if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
                            actual_vector_size = len(embeddings[0])
                            if actual_vector_size != vector_size:
                                logger.info(f"Adjusting vector size from {vector_size} to {actual_vector_size}")
                                # Recreate collection with correct size
                                try:
                                    qdrant_client.delete_collection(target_collection_name)
                                except:
                                    pass
                                qdrant_client.create_collection(
                                    collection_name=target_collection_name,
                                    vectors_config=VectorParams(size=actual_vector_size, distance=Distance.COSINE)
                                )
                                vector_size = actual_vector_size
                    except Exception as size_error:
                        logger.warning(f"Could not detect vector size: {size_error}")
                
                # Convert to Qdrant points
                points = []
                for i in range(len(results['ids'])):
                    doc_id = results['ids'][i]
                    
                    # Safely get content
                    content = ""
                    if results.get('documents') is not None and len(results['documents']) > i:
                        content = results['documents'][i] or ""
                    
                    # Safely get metadata  
                    metadata = {}
                    if results.get('metadatas') is not None and len(results['metadatas']) > i:
                        metadata = results['metadatas'][i] or {}
                    
                    # Safely get embedding
                    embedding = None
                    if results.get('embeddings') is not None and len(results['embeddings']) > i:
                        embedding = results['embeddings'][i]
                    
                    # Skip if no embedding (handle numpy arrays properly)
                    try:
                        if embedding is None:
                            continue
                        # Convert to list if it's a numpy array
                        if hasattr(embedding, 'tolist'):
                            embedding = embedding.tolist()
                        if not embedding or len(embedding) == 0:
                            continue
                    except Exception as embed_error:
                        logger.debug(f"Skipping document {doc_id} due to embedding issue: {embed_error}")
                        continue
                    
                    # Create Agno format payload
                    name = metadata.get("source", metadata.get("file_name", f"doc_{doc_id[:8]}"))
                    
                    agno_payload = {
                        "content": content,
                        "name": name,
                        "usage": {},
                        "meta_data": {
                            **metadata,
                            "original_content": metadata.get("original_content", content),
                            "migrated_from_chromadb": True,
                            "migration_timestamp": datetime.now().isoformat(),
                            "chromadb_document_id": doc_id
                        }
                    }
                    
                    point = PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload=agno_payload
                    )
                    points.append(point)
                
                # Upload batch to Qdrant
                if points:
                    qdrant_client.upsert(
                        collection_name=target_collection_name,
                        points=points,
                        wait=True
                    )
                    total_migrated += len(points)
                    logger.info(f"Migrated {len(points)} documents. Total: {total_migrated}")
                
                offset += batch_size
                
            except Exception as e:
                logger.error(f"Error in batch {offset}: {e}")
                import traceback
                traceback.print_exc()
                offset += batch_size  # Skip this batch and continue
                continue
        
        logger.info(f"Migration completed! Total documents migrated: {total_migrated}")
        
        # Verify migration
        qdrant_count = qdrant_client.count(collection_name=target_collection_name)
        logger.info(f"Verification: Qdrant collection has {qdrant_count.count} documents")
        
        # Check a sample document
        sample = qdrant_client.scroll(
            collection_name=target_collection_name,
            limit=1,
            with_payload=True
        )
        
        if sample[0]:
            payload = sample[0][0].payload
            has_agno_format = all(key in payload for key in ['content', 'name', 'usage', 'meta_data'])
            logger.info(f"Sample document Agno compliance: {has_agno_format}")
            logger.info(f"Sample payload keys: {list(payload.keys())}")
        
        return {
            "status": "success",
            "source_count": total_count,
            "migrated_count": total_migrated,
            "target_count": qdrant_count.count
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    print("🚀 Starting collection_35_ema migration...")
    result = migrate_collection_35_ema()
    
    print("\n" + "="*60)
    print("MIGRATION RESULTS")
    print("="*60)
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Source documents: {result['source_count']}")
        print(f"Migrated: {result['migrated_count']}")
        print(f"Target documents: {result['target_count']}")
        print("✅ Migration completed successfully!")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    print("="*60)