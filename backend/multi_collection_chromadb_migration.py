#!/usr/bin/env python3
"""
Multi-Collection ChromaDB to Qdrant migration script.
Lists all available ChromaDB collections and allows selective or bulk migration.
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

def list_chromadb_collections():
    """List all available ChromaDB collections."""
    try:
        import chromadb
        from chromadb.config import Settings
        
        chromadb_path = "/app/data/chromadb"
        client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=False)
        )
        
        collections = client.list_collections()
        logger.info(f"Found {len(collections)} ChromaDB collections")
        
        collection_info = []
        for collection in collections:
            try:
                count = collection.count()
                collection_info.append({
                    "name": collection.name,
                    "count": count
                })
                logger.info(f"  - {collection.name}: {count} documents")
            except Exception as e:
                logger.warning(f"  - {collection.name}: Error getting count - {e}")
                collection_info.append({
                    "name": collection.name,
                    "count": "error"
                })
        
        return collection_info
        
    except Exception as e:
        logger.error(f"Error listing ChromaDB collections: {e}")
        return []

def migrate_single_collection(collection_name):
    """Migrate a single collection from ChromaDB to Qdrant."""
    
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
        try:
            source_collection = client.get_collection(collection_name)
            total_count = source_collection.count()
            logger.info(f"Source collection '{collection_name}' has {total_count} documents")
        except Exception as e:
            logger.error(f"Collection '{collection_name}' not found: {e}")
            return {"status": "error", "error": f"Collection not found: {e}"}
        
        # Create target collection in Qdrant
        target_collection_name = collection_name
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
            "collection_name": collection_name,
            "source_count": total_count,
            "migrated_count": total_migrated,
            "target_count": qdrant_count.count
        }
        
    except Exception as e:
        logger.error(f"Migration failed for {collection_name}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "collection_name": collection_name, "error": str(e)}

def migrate_all_collections(collection_names):
    """Migrate multiple collections."""
    results = []
    
    for collection_name in collection_names:
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting migration for: {collection_name}")
        logger.info(f"{'='*60}")
        
        result = migrate_single_collection(collection_name)
        results.append(result)
        
        if result["status"] == "success":
            logger.info(f"✅ {collection_name} migrated successfully")
        else:
            logger.error(f"❌ {collection_name} migration failed: {result.get('error')}")
    
    return results

def interactive_migration():
    """Interactive migration with user selection."""
    print("🚀 ChromaDB to Qdrant Migration Tool")
    print("="*50)
    
    # List available collections
    print("\n📋 Discovering ChromaDB collections...")
    collections = list_chromadb_collections()
    
    if not collections:
        print("❌ No ChromaDB collections found or error accessing ChromaDB")
        return
    
    print(f"\n📊 Found {len(collections)} collections:")
    print("-" * 50)
    for i, col in enumerate(collections, 1):
        print(f"  {i}. {col['name']} ({col['count']} documents)")
    
    print("\n🎯 Migration Options:")
    print("  a - Migrate ALL collections")
    print("  q - Quit")
    print("  [number] - Migrate specific collection")
    print("  [numbers separated by commas] - Migrate multiple collections")
    
    choice = input("\nEnter your choice: ").strip().lower()
    
    if choice == 'q':
        print("👋 Goodbye!")
        return
    
    elif choice == 'a':
        # Migrate all collections
        collection_names = [col['name'] for col in collections]
        print(f"\n🔄 Starting migration for ALL {len(collection_names)} collections...")
        results = migrate_all_collections(collection_names)
        
    else:
        # Parse specific collection selections
        try:
            if ',' in choice:
                # Multiple collections
                indices = [int(x.strip()) for x in choice.split(',')]
                collection_names = [collections[i-1]['name'] for i in indices if 1 <= i <= len(collections)]
            else:
                # Single collection
                index = int(choice)
                if 1 <= index <= len(collections):
                    collection_names = [collections[index-1]['name']]
                else:
                    print("❌ Invalid selection")
                    return
            
            print(f"\n🔄 Starting migration for {len(collection_names)} collection(s)...")
            results = migrate_all_collections(collection_names)
            
        except ValueError:
            print("❌ Invalid input. Please enter numbers, 'a', or 'q'")
            return
    
    # Print final summary
    print("\n" + "="*60)
    print("📈 MIGRATION SUMMARY")
    print("="*60)
    
    successful = 0
    failed = 0
    total_documents = 0
    
    for result in results:
        if result["status"] == "success":
            successful += 1
            total_documents += result["migrated_count"]
            print(f"✅ {result['collection_name']}: {result['migrated_count']} documents")
        else:
            failed += 1
            print(f"❌ {result['collection_name']}: {result.get('error', 'Unknown error')}")
    
    print("-" * 60)
    print(f"📊 Results: {successful} successful, {failed} failed")
    print(f"📄 Total documents migrated: {total_documents}")
    print("="*60)

if __name__ == "__main__":
    interactive_migration()