#!/usr/bin/env python3
"""
Collection Indexing Processor for FDA RAG Pipeline
Subscribes to a Pub/Sub topic and orchestrates Vertex AI Batch Prediction jobs
for embedding generation and subsequent indexing into Qdrant.
"""

import os
import sys
import time
import logging
import json
import uuid
import sqlite3
import re
import threading
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm.attributes import flag_modified
import asyncio
import aiohttp

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.database import SessionLocal, Collection, SourceFiles, DocumentData, IndexingJob, collection_document_association, save_documents_to_db
from src.utils.qdrant_util import QdrantUtil
from src.utils.qdrant_singleton import get_qdrant_client
from qdrant_client.http.models import PointStruct, PointIdsList
from src.fda_pipeline import FDAPipelineV2
from google.cloud import pubsub_v1, aiplatform, storage
from google.cloud.aiplatform_v1.types import JobState
from google.api_core import exceptions
from google.api_core.exceptions import GoogleAPICallError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('collection_indexer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- GCP Configuration ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
PUBSUB_SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION_ID")
VERTEX_AI_MODEL = "text-embedding-004" # Standard Vertex AI embedding model

@dataclass
class BatchJobMetrics:
    job_id: str
    job_type: str
    start_time: float
    end_time: float = None
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    api_cost_estimate: float = 0.0
    status: str = "running"
    error_message: str = None

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, BatchJobMetrics] = {}
    
    def start_job(self, job_id: str, job_type: str, total_items: int):
        """Record job start."""
        self.metrics[job_id] = BatchJobMetrics(
            job_id=job_id,
            job_type=job_type,
            start_time=time.time(),
            total_items=total_items
        )
    
    def update_job(self, job_id: str, **kwargs):
        """Update job metrics."""
        if job_id in self.metrics:
            for key, value in kwargs.items():
                if hasattr(self.metrics[job_id], key):
                    setattr(self.metrics[job_id], key, value)
    
    def complete_job(self, job_id: str, status: str = "completed"):
        """Mark job as complete."""
        if job_id in self.metrics:
            self.metrics[job_id].end_time = time.time()
            self.metrics[job_id].status = status
            
            # Calculate cost estimate
            if self.metrics[job_id].job_type == "summarization":
                # Gemini 2.0 Flash pricing (example)
                input_cost_per_1k = 0.00001  # $0.01 per 1M tokens
                output_cost_per_1k = 0.00003  # $0.03 per 1M tokens
                
                # Estimate tokens (very rough)
                avg_input_tokens = 500
                avg_output_tokens = 200
                
                total_input_tokens = self.metrics[job_id].processed_items * avg_input_tokens
                total_output_tokens = self.metrics[job_id].processed_items * avg_output_tokens
                
                self.metrics[job_id].api_cost_estimate = (
                    (total_input_tokens / 1000) * input_cost_per_1k +
                    (total_output_tokens / 1000) * output_cost_per_1k
                )
    
    def get_job_summary(self, job_id: str) -> Dict[str, Any]:
        """Get job metrics summary."""
        if job_id not in self.metrics:
            return {}
        
        metrics = self.metrics[job_id]
        duration = (metrics.end_time or time.time()) - metrics.start_time
        
        return {
            **asdict(metrics),
            "duration_seconds": duration,
            "items_per_second": metrics.processed_items / duration if duration > 0 else 0
        }

class CollectionIndexer:
    """Orchestrates Vertex AI batch jobs for collection indexing."""

    def __init__(self):
        # Initialize Google Cloud clients
        if not all([GCP_PROJECT_ID, GCP_REGION, GCS_BUCKET_NAME, PUBSUB_SUBSCRIPTION_ID]):
            raise ValueError("Missing required GCP environment variables.")
        
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        
        # Use singleton Qdrant client
        try:
            self.qdrant_client = get_qdrant_client()
            self.qdrant_util = QdrantUtil(use_persistent_client=True)
            logger.info("Using shared Qdrant client")
        except Exception as e:
            logger.error(f"Failed to get Qdrant client: {e}")
            raise
        
        # Initialize FDA Pipeline for processing PENDING documents
        self.fda_pipeline = FDAPipelineV2()
        
        # Validate configuration
        self._validate_configuration()
        
        # Initialize Vertex AI models
        self._initialize_vertex_ai_models()
        
        # Initialize rate limiting
        self._init_rate_limiting()
        
        # Initialize metrics collector
        self.metrics_collector = MetricsCollector()
        
        logger.info("CollectionIndexer initialized successfully.")
    
    def _validate_configuration(self):
        """Validate GCP configuration and permissions."""
        try:
            # Check for required environment variables
            required_vars = ['GCP_PROJECT_ID', 'GCP_REGION', 'GCS_BUCKET_NAME']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {missing_vars}")
            
            # Validate Vertex AI is enabled
            aiplatform.init(project=GCP_PROJECT_ID, location=GCP_REGION)
            
            # Skip GCS bucket validation - Storage Object Admin doesn't include storage.buckets.get
            # The actual read/write operations will work fine with Storage Object Admin role
            logger.info(f"GCS bucket configured: {GCS_BUCKET_NAME}")
            logger.info("Skipping bucket existence check - Storage Object Admin role is sufficient for operations")
                
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def _initialize_vertex_ai_models(self):
        """Initialize and validate Vertex AI models."""
        self.SUMMARIZATION_MODEL = "gemini-2.5-flash"
        self.EMBEDDINGS_MODEL = "text-embedding-004"
        
        # Model configuration
        self.BATCH_SIZE_LIMIT = int(os.getenv("VERTEX_AI_BATCH_SIZE_LIMIT", "1000"))
        self.MAX_TOKENS_PER_CHUNK = 800000  # Leave buffer for Gemini limits
        self.CLEANUP_RETENTION_HOURS = int(os.getenv("GCS_CLEANUP_RETENTION_HOURS", "24"))
    
    def _init_rate_limiting(self):
        """Initialize rate limiting for Vertex AI API calls."""
        self._api_call_times = deque(maxlen=100)  # Track last 100 API calls
        self._api_call_lock = threading.Lock()
        self.MAX_CALLS_PER_MINUTE = int(os.getenv("VERTEX_AI_RATE_LIMIT_PER_MINUTE", "60"))

    def _process_pending_documents(self, job: IndexingJob, db: Session) -> Dict[int, bool]:
        """Process any PENDING documents before indexing."""
        document_ids = job.options.get('document_ids', [])
        
        # Get all documents for this job
        documents = db.query(SourceFiles).filter(
            SourceFiles.id.in_(document_ids)
        ).all()
        
        processing_results = {}
        pending_count = 0
        
        for doc in documents:
            if doc.status == 'PENDING':
                pending_count += 1
                logger.info(f"Processing PENDING document {doc.id} ({doc.file_name})")
                
                try:
                    # Send progress update
                    asyncio.run(self._send_progress_update(job, {
                        "progress": 5,  # Early stage progress
                        "stage": f"Processing document: {doc.file_name}",
                        "current_document": doc.file_name
                    }))
                    
                    # Process the document using FDA Pipeline
                    result = self.fda_pipeline.process_source_file(doc, db_session=db)
                    
                    if result.get("success"):
                        logger.info(f"Successfully processed document {doc.id}")
                        processing_results[doc.id] = True
                    else:
                        logger.error(f"Failed to process document {doc.id}: {result.get('error')}")
                        processing_results[doc.id] = False
                        doc.status = 'FAILED'
                        doc.comments = f"Processing failed: {result.get('error')}"
                        
                except Exception as e:
                    logger.error(f"Error processing document {doc.id}: {e}", exc_info=True)
                    processing_results[doc.id] = False
                    doc.status = 'FAILED'
                    doc.comments = f"Processing failed: {str(e)}"
                
                db.commit()
        
        if pending_count > 0:
            logger.info(f"Processed {pending_count} PENDING documents")
        
        return processing_results

    def _reindex_from_default_collection(self, job: IndexingJob, db: Session):
        """Copy vectors from default collection to the target collection."""
        document_ids = job.options.get('document_ids', [])
        collection = db.query(Collection).filter_by(id=job.collection_id).first()
        
        # Ensure consistent collection name generation
        collection_name = collection.vector_db_collection_name
        if not collection_name:
            collection_name = f"collection_{collection.id}_{self.qdrant_util.sanitize_collection_name(collection.name)}"
        
        # Ensure collection exists in Qdrant
        self.qdrant_util.get_or_create_collection(collection_name=collection_name)
        logger.info(f"Reindexing to Qdrant collection: {collection_name}")
        
        # Get the default collection
        # Ensure default collection exists in Qdrant
        self.qdrant_util.get_or_create_collection(collection_name="fda_documents")
        
        # Track progress
        total_docs = len(document_ids)
        processed = 0
        failed = 0
        
        for doc_id in document_ids:
            try:
                # Send progress update
                progress = 10 + (60 * processed / total_docs)  # 10-70% range
                asyncio.run(self._send_progress_update(job, {
                    "progress": progress,
                    "stage": f"Copying vectors for document {processed + 1}/{total_docs}"
                }))
                
                # Get document details
                doc = db.query(SourceFiles).filter_by(id=doc_id).first()
                if not doc:
                    logger.warning(f"Document {doc_id} not found")
                    failed += 1
                    continue
                
                # Query vectors from default collection by file_name
                results = default_collection.get(
                    where={"file_name": doc.file_name},
                    include=["documents", "metadatas", "embeddings"]
                )
                
                if not results['ids']:
                    logger.warning(f"No vectors found for document {doc.file_name} in default collection")
                    failed += 1
                    continue
                
                # Prepare data for target collection
                new_ids = []
                new_docs = []
                new_metadatas = []
                new_embeddings = []
                
                for i, (doc_content, metadata, embedding) in enumerate(zip(
                    results['documents'],
                    results['metadatas'],
                    results['embeddings']
                )):
                    # Generate new ID for the target collection
                    new_id = str(uuid.uuid4())
                    new_ids.append(new_id)
                    new_docs.append(doc_content)
                    
                    # Update metadata with collection info
                    new_metadata = metadata.copy()
                    new_metadata.update({
                        "source_file_id": doc_id,
                        "collection_id": collection.id
                    })
                    new_metadatas.append(new_metadata)
                    new_embeddings.append(embedding)
                
                # Add to target collection in batches
                batch_size = 100
                for i in range(0, len(new_ids), batch_size):
                    batch_end = min(i + batch_size, len(new_ids))
                    target_collection.add(
                        ids=new_ids[i:batch_end],
                        documents=new_docs[i:batch_end],
                        metadatas=new_metadatas[i:batch_end],
                        embeddings=new_embeddings[i:batch_end]
                    )
                
                logger.info(f"Copied {len(new_ids)} vectors for document {doc.file_name}")
                processed += 1
                
            except Exception as e:
                logger.error(f"Error reindexing document {doc_id}: {e}", exc_info=True)
                failed += 1
        
        # Update job stats
        job.processed_documents = processed
        job.failed_documents = failed
        
        # Update document status
        if processed > 0:
            self._update_document_status_after_indexing(job, document_ids, db, collection)
        
        # Send final progress
        asyncio.run(self._send_progress_update(job, {
            "progress": 70,
            "stage": f"Completed copying vectors ({processed} succeeded, {failed} failed)"
        }))
        
        logger.info(f"Reindex completed: {processed} documents copied, {failed} failed")

    def _update_document_status_after_indexing(self, job: IndexingJob, document_ids: List[int], db: Session, collection: Collection):
        """Update document status and vector_db_collections after successful indexing."""
        source_files_to_update = db.query(SourceFiles).filter(SourceFiles.id.in_(document_ids)).all()
        for source_file in source_files_to_update:
            # Keep status as DOCUMENT_STORED (don't change to READY)
            
            # Update vector_db_collections
            if source_file.vector_db_collections is None:
                source_file.vector_db_collections = []
            
            # Avoid duplicate entries
            if not any(c.get('collection_id') == collection.id for c in source_file.vector_db_collections):
                source_file.vector_db_collections.append({
                    "collection_id": collection.id,
                    "collection_name": collection.name,
                    "indexed_at": datetime.utcnow().isoformat()
                })
                flag_modified(source_file, "vector_db_collections")
        
        # Update the collection_document_association table
        try:
            update_stmt = (
                collection_document_association.update()
                .where(
                    collection_document_association.c.collection_id == job.collection_id,
                    collection_document_association.c.document_id.in_(document_ids),
                )
                .values(indexing_status="indexed", indexed_at=datetime.utcnow())
            )
            db.execute(update_stmt)
            logger.info(f"Updated indexing status in association table for {len(document_ids)} documents")
            
            # Verify documents in Qdrant
            self._verify_documents_in_qdrant(collection, document_ids)
        except Exception as e:
            logger.error(f"Failed to update association table: {e}", exc_info=True)
        
        db.commit()
        logger.info(f"Updated vector_db_collections info for {len(document_ids)} source files.")
    
    def _cleanup_qdrant_vectors_for_documents(self, documents: List[DocumentData]):
        """Clean up Qdrant vectors for documents that are being deleted."""
        try:
            # Group documents by collection
            collections_to_clean = set()
            doc_ids_to_delete = []
            
            for doc in documents:
                doc_ids_to_delete.append(f"doc_{doc.id}")
                # Track which collections might have these vectors
                if hasattr(doc, 'source_file') and doc.source_file and doc.source_file.vector_db_collections:
                    for coll_info in doc.source_file.vector_db_collections:
                        collections_to_clean.add(coll_info.get('collection_name'))
            
            if not doc_ids_to_delete:
                return
            
            logger.info(f"Attempting to clean up {len(doc_ids_to_delete)} vectors from Qdrant")
            
            # Try to delete from all possible collections
            deleted_count = 0
            for coll_name in collections_to_clean:
                try:
                    # Delete documents by their IDs from Qdrant
                    from qdrant_client.http.models import PointIdsList
                    self.qdrant_client.delete(
                        collection_name=coll_name,
                        points_selector=PointIdsList(points=doc_ids_to_delete),
                        wait=True
                    )
                    deleted_count += 1
                    logger.info(f"Deleted vectors from collection {coll_name}")
                except Exception as e:
                    logger.debug(f"Could not delete from collection {coll_name}: {e}")
            
            if deleted_count == 0:
                logger.info("No vectors found to delete (this is normal for new indexing)")
                
        except Exception as e:
            logger.warning(f"Error cleaning up Qdrant vectors: {e}")
            # Don't fail the whole process if cleanup fails
    
    def _verify_documents_in_qdrant(self, collection: Collection, document_ids: List[int]):
        """Verify that documents were successfully added to Qdrant."""
        try:
            # Get or create collection
            collection_name = collection.vector_db_collection_name
            if not collection_name:
                collection_name = f"collection_{collection.id}_{self.qdrant_util.sanitize_collection_name(collection.name)}"
            
            if not self.qdrant_util.collection_exists(collection_name):
                logger.error(f"Could not access Qdrant collection {collection_name} for verification")
                return
            
            # Query Qdrant to count documents
            stats = self.qdrant_util.get_collection_stats(collection_name)
            count = stats.get('total_documents', 0)
            logger.info(f"Qdrant collection {collection_name} contains {count} vectors")
            
            # For more detailed verification, we could query with a sample and check metadata
            if count > 0:
                # Get sample documents from Qdrant for verification
                from qdrant_client.http.models import Filter, ScrollRequest
                sample_result = self.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=5,
                    with_payload=True
                )
                if sample_result and sample_result[0]:
                    source_file_ids = set()
                    for point in sample_result[0]:
                        if point.payload and "source_file_id" in point.payload:
                            source_file_ids.add(point.payload["source_file_id"])
                    logger.info(f"Sample verification: Found documents from source files: {source_file_ids}")
            
        except Exception as e:
            logger.error(f"Error verifying documents in Qdrant: {e}")

    async def _send_progress_update(self, job: IndexingJob, progress_data: Dict):
        """Send progress update via WebSocket through the backend API."""
        try:
            # Use asyncio to run the async HTTP request
            async with aiohttp.ClientSession() as session:
                # Connect to the general WebSocket endpoint
                ws_url = "ws://backend:8090/api/collections/indexing-updates"
                async with session.ws_connect(ws_url) as ws:
                    # Send progress message
                    message = {
                        "type": "progress",
                        "jobId": job.job_id,
                        "data": {
                            "job_id": job.job_id,
                            "collection_id": job.collection_id,
                            "collectionId": job.collection_id,  # Frontend compatibility
                            "status": job.status,
                            "progress": progress_data.get("progress", 0),
                            "total_documents": job.total_documents,
                            "totalDocuments": job.total_documents,
                            "processed_documents": job.processed_documents,
                            "processedDocuments": job.processed_documents,
                            "failed_documents": job.failed_documents,
                            "failedDocuments": job.failed_documents,
                            "current_document": progress_data.get("current_document"),
                            "currentDocument": progress_data.get("current_document"),
                            "stage": progress_data.get("stage", "Processing")
                        }
                    }
                    await ws.send_json(message)
                    logger.debug(f"Sent progress update for job {job.job_id}: {progress_data}")
        except Exception as e:
            logger.error(f"Failed to send progress update: {e}")

    async def _send_completion_notification(self, job: IndexingJob):
        """Send completion notification via WebSocket through the backend API."""
        try:
            async with aiohttp.ClientSession() as session:
                # Connect to the general WebSocket endpoint
                ws_url = "ws://backend:8090/api/collections/indexing-updates"
                async with session.ws_connect(ws_url) as ws:
                    # Send completion message
                    message = {
                        "type": "complete",
                        "jobId": job.job_id,
                        "data": {
                            "job_id": job.job_id,
                            "collection_id": job.collection_id,
                            "collectionId": job.collection_id,
                            "status": "completed",
                            "total_documents": job.total_documents,
                            "totalDocuments": job.total_documents,
                            "processed_documents": job.processed_documents,
                            "processedDocuments": job.processed_documents,
                            "failed_documents": job.failed_documents,
                            "failedDocuments": job.failed_documents,
                            "completed_at": job.completed_at.isoformat() if job.completed_at else None
                        }
                    }
                    await ws.send_json(message)
                    logger.info(f"Sent completion notification for job {job.job_id}")
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")

    def process_job(self, job_id: str):
        """Orchestrates the entire indexing process with enhanced error handling."""
        db = SessionLocal()
        job = db.query(IndexingJob).filter_by(job_id=job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found.")
            return

        try:
            logger.info(f"Starting processing for job {job_id}...")
            job.status = 'processing'
            job.started_at = datetime.utcnow()
            db.commit()

            document_ids = job.options.get('document_ids', [])
            original_document_count = len(document_ids)
            
            # Filter documents based on job type and indexing status
            if document_ids:
                # Get document statuses from collection_document_association
                association_results = db.execute(
                    collection_document_association.select().where(
                        collection_document_association.c.collection_id == job.collection_id,
                        collection_document_association.c.document_id.in_(document_ids)
                    )
                ).fetchall()
                
                # Create a mapping of document_id to indexing_status
                doc_status_map = {assoc.document_id: assoc.indexing_status for assoc in association_results}
                
                # Filter based on job type
                filtered_document_ids = []
                skipped_documents = []
                
                if job.job_type == 'index':
                    # For index jobs: only process pending or null status
                    for doc_id in document_ids:
                        status = doc_status_map.get(doc_id, 'pending')  # Default to pending if not in association
                        if status in ['pending', None]:
                            filtered_document_ids.append(doc_id)
                        else:
                            skipped_documents.append((doc_id, status))
                            logger.info(f"Skipping document {doc_id} for index job - status: {status}")
                
                elif job.job_type == 'reindex':
                    # For reindex jobs: only process indexed or failed status
                    for doc_id in document_ids:
                        status = doc_status_map.get(doc_id, None)
                        if status in ['indexed', 'failed']:
                            filtered_document_ids.append(doc_id)
                        else:
                            skipped_documents.append((doc_id, status))
                            logger.info(f"Skipping document {doc_id} for reindex job - status: {status}")
                else:
                    # Default behavior for other job types
                    filtered_document_ids = document_ids
                
                # Log summary of filtering
                logger.info(f"Job {job_id} ({job.job_type}): Filtered {original_document_count} documents to {len(filtered_document_ids)} for processing")
                if skipped_documents:
                    logger.info(f"Skipped {len(skipped_documents)} documents due to status mismatch")
                
                document_ids = filtered_document_ids
                
                # If no documents need processing, complete the job
                if not document_ids:
                    logger.info(f"Job {job_id}: No documents match criteria for {job.job_type} job. Completing job.")
                    job.status = 'completed'
                    job.completed_at = datetime.utcnow()
                    job.processed_documents = 0
                    job.failed_documents = 0
                    job.total_documents = original_document_count
                    
                    # Add skipped info to metrics
                    self.metrics_collector.start_job(job_id, "full_pipeline", 0)
                    self.metrics_collector.complete_job(job_id)
                    job.metrics = self.metrics_collector.get_job_summary(job_id)
                    job.metrics['skipped_documents'] = len(skipped_documents)
                    job.metrics['original_request_count'] = original_document_count
                    
                    db.commit()
                    
                    # Send completion notification
                    asyncio.run(self._send_completion_notification(job))
                    return
            
            # Initialize metrics with filtered count
            self.metrics_collector.start_job(job_id, "full_pipeline", len(document_ids))

            # Send initial progress update
            asyncio.run(self._send_progress_update(job, {
                "progress": 0,
                "stage": "Starting job processing"
            }))

            # 1. Prepare summarization batch input
            asyncio.run(self._send_progress_update(job, {
                "progress": 10,
                "stage": "Preparing data for batch processing"
            }))
            
            try:
                batches = self._prepare_summarization_batch_input(job, db, document_ids)
            except Exception as e:
                raise RuntimeError(f"Failed to prepare summarization input: {e}")
            
            # 2. Run summarization batch jobs
            asyncio.run(self._send_progress_update(job, {
                "progress": 20,
                "stage": "Starting batch summarization"
            }))
            
            try:
                summaries = self._run_vertex_ai_summarization_batch(job.job_id, batches, db, job)
                self.metrics_collector.update_job(job_id, processed_items=len(summaries))
            except Exception as e:
                raise RuntimeError(f"Summarization failed: {e}")
            
            # 3. Save summarized chunks to DocumentData
            asyncio.run(self._send_progress_update(job, {
                "progress": 50,
                "stage": "Saving summarized documents"
            }))
            
            try:
                all_metadata = [metadata for _, metadata in batches]
                collection = db.query(Collection).filter_by(id=job.collection_id).first()
                self._save_summarized_chunks(summaries, all_metadata, db, collection)
            except Exception as e:
                logger.error(f"Failed to save summaries: {e}")
                # Continue with successfully saved documents
            
            # 4. Prepare embeddings input (using summaries)
            asyncio.run(self._send_progress_update(job, {
                "progress": 60,
                "stage": "Preparing embeddings input"
            }))
            
            try:
                embedding_batches = self._prepare_embeddings_batch_input(job, db, document_ids)
                if not embedding_batches:
                    raise ValueError("No documents ready for embedding")
            except Exception as e:
                raise RuntimeError(f"Failed to prepare embeddings: {e}")
            
            # 5. Submit and monitor Vertex AI Batch Prediction job for embeddings
            asyncio.run(self._send_progress_update(job, {
                "progress": 70,
                "stage": "Generating embeddings with Vertex AI"
            }))
            
            try:
                embeddings = self._run_vertex_ai_embeddings_batch(job_id, embedding_batches, db, job)
            except Exception as e:
                raise RuntimeError(f"Embeddings generation failed: {e}")
            
            # 6. Add embeddings to Qdrant
            asyncio.run(self._send_progress_update(job, {
                "progress": 90,
                "stage": "Adding embeddings to Qdrant"
            }))
            
            try:
                self._add_embeddings_to_qdrant_batch(job, embeddings, db)
            except Exception as e:
                raise RuntimeError(f"Qdrant indexing failed: {e}")
            
            # Update document status and collection associations
            document_ids = job.options.get('document_ids', [])
            collection = db.query(Collection).filter_by(id=job.collection_id).first()
            self._update_document_status_after_indexing(job, document_ids, db, collection)

            # Complete job
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.processed_documents = job.total_documents - job.failed_documents
            
            # Complete metrics
            self.metrics_collector.complete_job(job_id)
            job.metrics = self.metrics_collector.get_job_summary(job_id)
            
            db.commit()
            
            logger.info(f"Job {job_id} completed successfully.")
            logger.info(f"Job metrics: {json.dumps(job.metrics, indent=2)}")
            
            # Send completion notification
            asyncio.run(self._send_completion_notification(job))

        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}", exc_info=True)
            job.status = 'failed'
            job.error_details = {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Complete metrics with failure
            self.metrics_collector.update_job(job_id, error_message=str(e))
            self.metrics_collector.complete_job(job_id, status="failed")
            
            db.commit()
            
            # Send failure notification
            asyncio.run(self._send_failure_notification(job, str(e)))
            
        finally:
            db.close()

    def _prepare_and_upload_data(self, job: IndexingJob, db: Session) -> tuple:
        """Fetches data from MySQL, formats it as JSONL, and uploads to GCS."""
        document_ids = job.options.get('document_ids', [])
        
        # For index jobs, only process documents that are not already indexed in this collection
        if job.job_type == 'index':
            # Get document statuses from collection_document_association
            association_results = db.execute(
                collection_document_association.select().where(
                    collection_document_association.c.collection_id == job.collection_id,
                    collection_document_association.c.document_id.in_(document_ids)
                )
            ).fetchall()
            
            # Filter to only include documents that need indexing
            documents_to_index = []
            for assoc in association_results:
                if assoc.indexing_status in ['pending', 'failed', None]:  # Include failed for retry
                    documents_to_index.append(assoc.document_id)
                elif assoc.indexing_status == 'indexed':
                    logger.info(f"Skipping document {assoc.document_id} - already indexed in collection {job.collection_id}")
            
            document_ids = documents_to_index
            logger.info(f"Job {job.job_id}: Filtered to {len(document_ids)} documents that need indexing")
            
            # If no documents need indexing, complete the job
            if not document_ids:
                logger.info(f"Job {job.job_id}: No documents need indexing. All documents are already indexed.")
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.processed_documents = 0
                job.failed_documents = 0
                db.commit()
                
                # Send completion notification
                asyncio.run(self._send_completion_notification(job))
                return None, []
        
        documents = db.query(SourceFiles).filter(SourceFiles.id.in_(document_ids)).all()
        
        # For reindex jobs, reprocess PDFs
        if job.job_type == 'reindex':
            logger.info(f"Job {job.job_id}: Reindex job detected. Will reprocess PDFs.")
            collection = db.query(Collection).filter_by(id=job.collection_id).first()
            
            for doc in documents:
                if doc.status == 'DOCUMENT_STORED':
                    doc.status = 'PENDING'
                    
                    # Remove existing vectors from Qdrant collection
                    if collection and collection.vector_db_collection_name:
                        try:
                            # Delete documents by source_file_id from Qdrant
                            result = self.qdrant_util.delete_documents_by_metadata(
                                collection_name=collection.vector_db_collection_name,
                                metadata_filter={"source_file_id": doc.id}
                            )
                            if result.get("status") == "success":
                                logger.info(f"Removed existing vectors for document {doc.id}")
                        except Exception as e:
                            logger.warning(f"Failed to remove existing vectors for doc {doc.id}: {e}")
                    
                    # Clear existing DocumentData for reprocessing
                    db.query(DocumentData).filter_by(source_file_id=doc.id).delete()
                    logger.info(f"Cleared DocumentData for doc {doc.id} for reprocessing")
            db.commit()
        
        # Log document statuses for debugging
        logger.info(f"Job {job.job_id}: Processing {len(documents)} documents")
        for doc in documents:
            logger.info(f"Document {doc.id} ({doc.file_name}): status={doc.status}, vector_db_collections={doc.vector_db_collections}")
        
        # For index jobs, check if documents are already indexed in another collection
        documents_to_copy = []
        documents_to_process = []
        
        for doc in documents:
            if doc.status == 'DOCUMENT_STORED' and doc.vector_db_collections and job.job_type != 'reindex':
                # Check if already indexed in another collection
                existing_collection = None
                for coll in doc.vector_db_collections:
                    if coll.get('collection_id') != job.collection_id:
                        existing_collection = coll
                        break
                
                if existing_collection:
                    documents_to_copy.append((doc, existing_collection))
                    continue
            
            if doc.status in ['PENDING', 'FAILED']:
                documents_to_process.append(doc)
            elif doc.status == 'DOCUMENT_STORED':
                # For DOCUMENT_STORED without vector_db_collections, we should check if DocumentData exists
                documents_to_process.append(doc)
        
        # Copy vectors from existing collections
        if documents_to_copy:
            logger.info(f"Found {len(documents_to_copy)} documents already indexed in other collections")
            collection = db.query(Collection).filter_by(id=job.collection_id).first()
            target_collection_name = collection.vector_db_collection_name
            if not target_collection_name:
                target_collection_name = f"collection_{collection.id}_{self.qdrant_util.sanitize_collection_name(collection.name)}"
                collection.vector_db_collection_name = target_collection_name
                db.commit()
            
            # Ensure target collection exists in Qdrant
            self.qdrant_util.get_or_create_collection(target_collection_name)
            
            for doc, existing_collection in documents_to_copy:
                try:
                    # Query vectors for this document from Qdrant
                    from qdrant_client.http.models import Filter, FieldCondition, MatchValue
                    
                    filter_condition = Filter(
                        must=[
                            FieldCondition(
                                key="source_file_id",
                                match=MatchValue(value=doc.id)
                            )
                        ]
                    )
                    
                    results = self.qdrant_client.scroll(
                        collection_name=existing_collection['collection_name'],
                        scroll_filter=filter_condition,
                        with_payload=True,
                        with_vectors=True,
                        limit=1000
                    )
                    
                    if results and results[0]:  # Qdrant scroll returns (points, next_offset)
                        points = results[0]
                        # Update metadata and add to target collection
                        from qdrant_client.http.models import PointStruct
                        
                        new_points = []
                        for point in points:
                            # Create new point with updated metadata
                            new_id = str(uuid.uuid4())
                            
                            # Copy payload and update metadata
                            old_payload = point.payload.copy() if point.payload else {}
                            
                            # Convert to Agno format (handle both old flat format and new nested format)
                            if 'meta_data' in old_payload:
                                # Already in new Agno format - just update collection info
                                payload = old_payload.copy()
                                payload['meta_data']['collection_id'] = job.collection_id
                                payload['meta_data']['source_file_id'] = doc.id
                                # Apply conditional original_content inclusion
                                if 'original_content' not in payload['meta_data']:
                                    payload['meta_data']['original_content'] = payload.get('content', '')
                            else:
                                # Old flat format - convert to new Agno format
                                logger.info(f"Converting document {point.id} from old flat format to Agno format")
                                content = old_payload.get('content', '')
                                name = old_payload.get('source', old_payload.get('file_name', 'unknown'))
                                
                                # Create new Agno format payload
                                payload = {
                                    'content': content,
                                    'name': name,
                                    'usage': {},  # Required by Agno library
                                    'meta_data': {
                                        **old_payload,  # Include all old metadata
                                        'collection_id': job.collection_id,
                                        'source_file_id': doc.id,
                                        # Ensure original_content is included
                                        **({"original_content": content} if "original_content" not in old_payload else {})
                                    }
                                }
                            
                            # Create new point
                            new_point = PointStruct(
                                id=new_id,
                                vector=point.vector,
                                payload=payload
                            )
                            new_points.append(new_point)
                        
                        # Add points to target collection
                        if new_points:
                            self.qdrant_client.upsert(
                                collection_name=target_collection_name,
                                points=new_points,
                                wait=True
                            )
                        
                        logger.info(f"Copied {len(new_ids)} vectors for document {doc.id} from collection {existing_collection['collection_name']}")
                        
                        # Update document's vector_db_collections
                        if not any(c.get('collection_id') == job.collection_id for c in doc.vector_db_collections):
                            doc.vector_db_collections.append({
                                'collection_id': job.collection_id,
                                'collection_name': target_collection_name,
                                'indexed_at': datetime.utcnow().isoformat()
                            })
                            flag_modified(doc, "vector_db_collections")
                        
                        # Update the association table
                        try:
                            update_stmt = (
                                collection_document_association.update()
                                .where(
                                    collection_document_association.c.collection_id == job.collection_id,
                                    collection_document_association.c.document_id == doc.id,
                                )
                                .values(indexing_status="indexed", indexed_at=datetime.utcnow())
                            )
                            db.execute(update_stmt)
                        except Exception as e:
                            logger.error(f"Failed to update association table for doc {doc.id}: {e}")
                        
                        # Remove from documents list so they won't be processed again
                        document_ids.remove(doc.id)
                        job.processed_documents += 1
                        
                except Exception as e:
                    logger.error(f"Failed to copy vectors for document {doc.id}: {e}")
                    documents_to_process.append(doc)
        
        # Process any PENDING or DOCUMENT_STORED documents that need processing
        logger.info(f"Job {job.job_id}: {len(documents_to_process)} documents need processing")
        
        for doc in documents_to_process:
            # Check if DocumentData already exists
            existing_data = db.query(DocumentData).filter_by(source_file_id=doc.id).first()
            
            if not existing_data:
                try:
                    logger.info(f"Processing PDF for document {doc.id}: {doc.file_name} (status: {doc.status})")
                    
                    # Use FDA pipeline to download PDF (handles both local files and external URLs)
                    try:
                        file_path = self.fda_pipeline.download_pdf(doc.file_url, doc.file_name)
                        logger.info(f"Successfully downloaded/located file at: {file_path}")
                    except Exception as download_error:
                        logger.error(f"Failed to download/access file from {doc.file_url}: {download_error}")
                        job.failed_documents += 1
                        if doc.id in document_ids:
                            document_ids.remove(doc.id)
                        
                        # Update the collection_document_association status to 'failed'
                        try:
                            update_stmt = (
                                collection_document_association.update()
                                .where(
                                    collection_document_association.c.collection_id == job.collection_id,
                                    collection_document_association.c.document_id == doc.id,
                                )
                                .values(
                                    indexing_status="failed", 
                                    error_message=f"Failed to download file: {str(download_error)}",
                                    indexed_at=None
                                )
                            )
                            db.execute(update_stmt)
                            logger.info(f"Updated document {doc.id} status to 'failed' in collection_document_association")
                        except Exception as e:
                            logger.error(f"Failed to update association table status for doc {doc.id}: {e}")
                        
                        continue
                    
                    result = self.fda_pipeline.process_pdf(file_path, doc.file_name, doc.id, db)
                    
                    if result and result.get('success'):
                        logger.info(f"Successfully processed document {doc.id} with {result.get('documents_count', 0)} documents")
                        # The process_pdf method already updates the document status and creates DocumentData
                    else:
                        logger.error(f"Failed to process PDF for document {doc.id}: {result.get('error', 'Unknown error')}")
                        job.failed_documents += 1
                        # Remove this document from the list to process
                        if doc.id in document_ids:
                            document_ids.remove(doc.id)
                        
                        # Update the collection_document_association status to 'failed'
                        try:
                            update_stmt = (
                                collection_document_association.update()
                                .where(
                                    collection_document_association.c.collection_id == job.collection_id,
                                    collection_document_association.c.document_id == doc.id,
                                )
                                .values(
                                    indexing_status="failed", 
                                    error_message=result.get('error', 'Unknown error'),
                                    indexed_at=None
                                )
                            )
                            db.execute(update_stmt)
                            logger.info(f"Updated document {doc.id} status to 'failed' in collection_document_association")
                        except Exception as e:
                            logger.error(f"Failed to update association table status for doc {doc.id}: {e}")
                        
                except Exception as e:
                    logger.error(f"Error processing document {doc.id}: {e}", exc_info=True)
                    job.failed_documents += 1
                    # Remove this document from the list to process
                    if doc.id in document_ids:
                        document_ids.remove(doc.id)
                    
                    # Update the collection_document_association status to 'failed'
                    try:
                        update_stmt = (
                            collection_document_association.update()
                            .where(
                                collection_document_association.c.collection_id == job.collection_id,
                                collection_document_association.c.document_id == doc.id,
                            )
                            .values(
                                indexing_status="failed", 
                                error_message=str(e),
                                indexed_at=None
                            )
                        )
                        db.execute(update_stmt)
                        logger.info(f"Updated document {doc.id} status to 'failed' in collection_document_association")
                    except Exception as update_e:
                        logger.error(f"Failed to update association table status for doc {doc.id}: {update_e}")
            else:
                logger.info(f"Document {doc.id} already has DocumentData ({existing_data.id})")
        
        db.commit()
        
        # Check if any documents remain after processing
        if not document_ids:
            logger.info(f"Job {job.job_id}: All documents failed processing. No documents to index.")
            # Update job status
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.processed_documents = 0
            db.commit()
            
            # Send completion notification
            asyncio.run(self._send_completion_notification(job))
            return None, []
        
        # Now fetch DocumentData
        logger.info(f"Job {job.job_id}: Fetching DocumentData for {len(document_ids)} documents: {document_ids}")
        docs_data = db.query(DocumentData).filter(DocumentData.source_file_id.in_(document_ids)).all()
        logger.info(f"Job {job.job_id}: Found {len(docs_data)} DocumentData entries")

        if not docs_data:
            # Log more details about the documents
            for doc_id in document_ids:
                doc = db.query(SourceFiles).filter_by(id=doc_id).first()
                if doc:
                    logger.error(f"Document {doc_id} ({doc.file_name}): status={doc.status}, has no DocumentData")
                    # Check if file exists
                    import os
                    if doc.file_url and not os.path.exists(doc.file_url):
                        logger.error(f"File not found at: {doc.file_url}")
            
            raise ValueError("No DocumentData found for the specified documents after processing.")

        # Create JSONL content for text-embedding-004 model
        jsonl_content = ""
        for doc_data in docs_data:
            # text-embedding-004 expects { 'content': 'your content here' }
            instance = {
                "content": doc_data.doc_content
            }
            jsonl_content += json.dumps(instance) + "\n"

        # Upload to GCS
        gcs_path = f"batch-indexing-input/{job.job_id}.jsonl"
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(jsonl_content, content_type="application/jsonl")
        
        input_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"
        logger.info(f"Uploaded input data for job {job.job_id} to {input_uri}")
        return input_uri, document_ids

    def _run_vertex_ai_batch_job(self, job_id: str, gcs_input_uri: str, document_ids: List[str], db: Session, job: IndexingJob) -> Dict[str, List[float]]:
        """Submits a Vertex AI Batch Prediction job and waits for its completion."""
        gcs_output_uri = f"gs://{GCS_BUCKET_NAME}/batch-indexing-output/{job_id}/"

        logger.info(f"Submitting Vertex AI Batch Prediction job for job ID: {job_id}")
        
        # Use the correct publisher model format for text-embedding-004
        model_name = f"publishers/google/models/{VERTEX_AI_MODEL}"
        
        model_parameters = {"output_dimensionality": 768}
        
        batch_prediction_job = aiplatform.BatchPredictionJob.create(
            job_display_name=f"indexing_job_{job_id}",
            model_name=model_name,
            instances_format="jsonl",
            predictions_format="jsonl",
            gcs_source=[gcs_input_uri],
            gcs_destination_prefix=gcs_output_uri,
            model_parameters=model_parameters,
        )

        logger.info(f"Waiting for Vertex AI job to complete... (Job resource name: {batch_prediction_job.resource_name})")
        
        # Monitor job progress
        check_interval = 10  # seconds
        progress_base = 10  # Starting progress after submission
        progress_range = 60  # Progress range for this phase (10-70%)
        
        while not batch_prediction_job.done():
            time.sleep(check_interval)
            # Estimate progress based on time elapsed (simplified)
            # In production, you might query job status for actual progress
            elapsed_minutes = (datetime.utcnow() - job.started_at).total_seconds() / 60
            estimated_progress = min(progress_base + (elapsed_minutes / 5) * progress_range, 70)
            
            asyncio.run(self._send_progress_update(job, {
                "progress": estimated_progress,
                "stage": "Generating embeddings with Vertex AI"
            }))
        
        logger.info("Vertex AI job completed.")

        # Process the results
        embeddings = {}
        doc_data_list = db.query(DocumentData).filter(DocumentData.source_file_id.in_(document_ids)).all()
        
        for blob in self.storage_client.list_blobs(GCS_BUCKET_NAME, prefix=f"batch-indexing-output/{job_id}/"):
            if blob.name.endswith(".jsonl"):
                predictions = [json.loads(line) for line in blob.download_as_string().decode("utf-8").splitlines()]
                for i, pred in enumerate(predictions):
                    if i < len(doc_data_list):
                        doc_id = str(doc_data_list[i].id)
                        embeddings[doc_id] = pred['predictions'][0]['embeddings']['values']
        
        if not embeddings:
            raise RuntimeError("Vertex AI Batch Prediction job produced no embeddings.")
            
        return embeddings

    def _add_embeddings_to_qdrant(self, job: IndexingJob, embeddings: Dict[str, List[float]], document_ids: List[int], db: Session):
        """Adds the generated embeddings to the appropriate Qdrant collection."""
        collection = db.query(Collection).filter_by(id=job.collection_id).first()
        
        # Ensure consistent collection name generation
        collection_name = collection.vector_db_collection_name
        if not collection_name:
            collection_name = f"collection_{collection.id}_{self.qdrant_util.sanitize_collection_name(collection.name)}"
        
        # Get or create collection with retry logic and corruption handling
        self.qdrant_util.get_or_create_collection(collection_name)
        
        # Collection already created above
        docs_data = db.query(DocumentData).filter(DocumentData.source_file_id.in_(document_ids)).all()

        docs_to_add = []
        for data in docs_data:
            embedding = embeddings.get(str(data.id))
            if not embedding:
                logger.warning(f"No embedding found for document chunk {data.id}")
                continue

            metadata = json.loads(data.metadata_content)

            # Create payload in Agno format
            payload = {
                "content": data.doc_content or "",
                "name": metadata.get("source", metadata.get("file_name", "unknown")),
                "usage": {},  # Required by Agno library
                "meta_data": {
                    **metadata,
                    "source_file_id": data.source_file_id,
                    "collection_id": collection.id,
                    "document_id": data.id,
                    **({"original_content": data.doc_content or ""} if "original_content" not in metadata else {})
                }
            }
            
            docs_to_add.append({
                "id": str(uuid.uuid4()),
                "document": data.doc_content,
                "metadata": payload,
                "embedding": embedding
            })

        if docs_to_add:
            batch_size = 100
            total_batches = (len(docs_to_add) + batch_size - 1) // batch_size
            
            for batch_idx, i in enumerate(range(0, len(docs_to_add), batch_size)):
                batch = docs_to_add[i:i + batch_size]
                try:
                    # Create PointStructs for Qdrant
                    from qdrant_client.http.models import PointStruct
                    points = []
                    for item in batch:
                        # Payload already contains content and metadata
                        point = PointStruct(
                            id=item['id'],
                            vector=item['embedding'],
                            payload=item['metadata']
                        )
                        points.append(point)
                    
                    # Upsert to Qdrant
                    # Use QdrantUtil for proper handling
                    self.qdrant_util.client.upsert(
                        collection_name=collection_name,
                        points=points,
                        wait=True
                    )
                    logger.info(f"Added batch {batch_idx + 1}/{total_batches} ({len(batch)} documents) to Qdrant")
                    
                    # Update processed documents count and send progress
                    job.processed_documents = min(i + batch_size, len(docs_to_add))
                    progress = 70 + (30 * (batch_idx + 1) / total_batches)  # 70-100% range
                    
                    asyncio.run(self._send_progress_update(job, {
                        "progress": progress,
                        "stage": f"Indexing documents to Qdrant ({job.processed_documents}/{len(docs_to_add)})"
                    }))
                    
                except Exception as e:
                    logger.error(f"Error adding batch to Qdrant: {e}", exc_info=True)
                    job.failed_documents += len(batch)

        # Update the status of the source files to 'READY' and add collection info
        self._update_document_status_after_indexing(job, document_ids, db, collection)
    
    def _check_rate_limits(self):
        """Check and enforce rate limits."""
        with self._api_call_lock:
            now = datetime.utcnow()
            
            # Remove calls older than 1 minute
            while self._api_call_times and (now - self._api_call_times[0]) > timedelta(minutes=1):
                self._api_call_times.popleft()
            
            # If at limit, wait
            if len(self._api_call_times) >= self.MAX_CALLS_PER_MINUTE:
                wait_time = 60 - (now - self._api_call_times[0]).total_seconds()
                if wait_time > 0:
                    logger.info(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
            
            # Record this call
            self._api_call_times.append(now)

    def _schedule_gcs_cleanup(self, gcs_path: str):
        """Schedule cleanup of temporary GCS files."""
        try:
            # Parse bucket and path
            if gcs_path.startswith("gs://"):
                bucket_name, prefix = gcs_path[5:].rstrip('/').split("/", 1)
            else:
                return
            
            # Add to cleanup queue (implement with Cloud Scheduler or similar)
            cleanup_time = datetime.utcnow() + timedelta(hours=self.CLEANUP_RETENTION_HOURS)
            
            # For now, log the cleanup task
            logger.info(f"Scheduled cleanup for {gcs_path} at {cleanup_time}")
            
            # In production, use Cloud Scheduler or Pub/Sub to trigger cleanup
            # self._create_cleanup_task(bucket_name, prefix, cleanup_time)
            
        except Exception as e:
            logger.error(f"Failed to schedule cleanup for {gcs_path}: {e}")
    
    def _upload_batch(self, batch_data: dict, job_id: str, batch_num: int) -> tuple:
        """Upload a batch to GCS and return (gcs_uri, metadata)."""
        gcs_path = f"batch-summary-input/{job_id}/batch_{batch_num}.jsonl"
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(batch_data["jsonl"], content_type="application/jsonl")
        
        input_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"
        logger.info(f"Uploaded batch {batch_num} for job {job_id} to {input_uri}")
        
        return input_uri, batch_data["metadata"]
    
    def _prepare_summarization_batch_input(self, job: IndexingJob, db: Session, document_ids: List[int] = None) -> List[Tuple]:
        """
        Prepare JSONL input for summarization batch job with size validation.
        
        Args:
            job: The IndexingJob
            db: Database session
            document_ids: Optional filtered list of document IDs. If not provided, uses job.options
        
        Returns:
            List of (gcs_uri, chunk_metadata_map) tuples for multiple batches if needed
        """
        if document_ids is None:
            document_ids = job.options.get('document_ids', [])
        
        logger.info(f"Preparing summarization batch for {len(document_ids)} documents: {document_ids}")
        documents = db.query(SourceFiles).filter(SourceFiles.id.in_(document_ids)).all()
        
        batches = []
        current_batch = {"jsonl": "", "metadata": {}, "counter": 0}
        
        for doc in documents:
            try:
                # Download/locate PDF
                file_path = self.fda_pipeline.download_pdf(doc.file_url, doc.file_name)
                
                # Extract chunks only (no summarization)
                chunks = self.fda_pipeline.pdf_processor.extract_chunks_only(
                    file_path, doc.file_name, doc.file_url
                )
                
                for chunk in chunks:
                    # Create a unique chunk identifier
                    chunk_id = f"doc_{doc.id}_chunk_{chunk['chunk_index']}"
                    
                    # Create batch input instance - Vertex AI only accepts the request field
                    instance = {
                        "request": {
                            "contents": [{
                                "role": "user",
                                "parts": [{
                                    "text": f"""[CHUNK_ID: {chunk_id}]
Summarize the following content in 400 words or less. 
Preserve key points, especially from tables, lists, or headings.
If the chunk contains a table, include the most important data succinctly.

Content:
```markdown
{chunk['content']}
```

Summary:"""
                                }]
                            }]
                        }
                    }
                    
                    # Check batch size limit
                    if current_batch["counter"] >= self.BATCH_SIZE_LIMIT:
                        # Save current batch and start new one
                        batches.append(self._upload_batch(current_batch, job.job_id, len(batches)))
                        current_batch = {"jsonl": "", "metadata": {}, "counter": 0}
                    
                    current_batch["jsonl"] += json.dumps(instance) + "\n"
                    current_batch["metadata"][current_batch["counter"]] = {
                        "source_file_id": doc.id,
                        "chunk_index": chunk['chunk_index'],
                        "has_table": chunk.get('has_table', False),
                        "file_name": doc.file_name,
                        "file_url": doc.file_url,
                        "original_content": chunk['content'],
                        "is_sub_chunk": chunk.get('is_sub_chunk', False)
                    }
                    current_batch["counter"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing document {doc.id} for summarization: {e}")
                job.failed_documents += 1
                continue
        
        # Upload final batch
        if current_batch["jsonl"]:
            batches.append(self._upload_batch(current_batch, job.job_id, len(batches)))
        
        if not batches:
            raise ValueError("No chunks prepared for summarization")
        
        return batches
    
    def _run_vertex_ai_batch_with_retry(self, job_id: str, gcs_input_uri: str, model_name: str, 
                                       model_parameters: Dict, job_type: str, max_retries: int = 3) -> aiplatform.BatchPredictionJob:
        """Run Vertex AI batch job with retry logic and rate limiting."""
        
        # Rate limiting check
        self._check_rate_limits()
        
        for attempt in range(max_retries):
            try:
                # Configure output location
                output_uri = f"gs://{GCS_BUCKET_NAME}/batch-{job_type}-output/{job_id}/"
                
                # Create batch prediction job
                if job_type == "summarization":
                    batch_prediction_job = aiplatform.BatchPredictionJob.create(
                        job_display_name=f"summarization_{job_id}_attempt_{attempt + 1}",
                        model_name=f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{model_name}",
                        instances_format="jsonl",
                        predictions_format="jsonl",
                        gcs_source=[gcs_input_uri],
                        gcs_destination_prefix=output_uri,
                        model_parameters=model_parameters,
                    )
                else:  # embeddings
                    batch_prediction_job = aiplatform.BatchPredictionJob.create(
                        job_display_name=f"embeddings_{job_id}_attempt_{attempt + 1}",
                        model_name=f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{model_name}",
                        instances_format="jsonl",
                        predictions_format="jsonl",
                        gcs_source=[gcs_input_uri],
                        gcs_destination_prefix=output_uri,
                    )
                
                return batch_prediction_job
                
            except Exception as e:
                logger.warning(f"Batch job attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def _monitor_and_collect_results(self, batch_job: aiplatform.BatchPredictionJob, 
                                    metadata: Dict, job: IndexingJob, base_progress: float, 
                                    progress_range: float, job_type: str) -> Dict:
        """Monitor batch job with actual progress tracking."""
        
        last_state = None
        while not batch_job.done():
            # Get actual job progress
            batch_job.refresh()
            
            # Check if state changed
            if batch_job.state != last_state:
                logger.info(f"Batch job state: {batch_job.state}")
                last_state = batch_job.state
            
            # Calculate progress based on job metrics if available
            if hasattr(batch_job, 'completed_count') and hasattr(batch_job, 'total_count'):
                if batch_job.total_count > 0:
                    actual_progress = (batch_job.completed_count / batch_job.total_count) * progress_range
                    current_progress = base_progress + actual_progress
                    
                    asyncio.run(self._send_progress_update(job, {
                        "progress": current_progress,
                        "stage": f"Processing {job_type}: {batch_job.completed_count}/{batch_job.total_count} items",
                        "completed_items": batch_job.completed_count,
                        "total_items": batch_job.total_count
                    }))
            
            time.sleep(10)
        
        # Check for errors
        if batch_job.state != JobState.JOB_STATE_SUCCEEDED:
            raise RuntimeError(f"Batch job failed with state: {batch_job.state}")
        
        # Collect results
        return self._parse_batch_results(batch_job, metadata, job_type)
    
    def _parse_batch_results(self, batch_job: aiplatform.BatchPredictionJob, 
                            metadata: Dict, job_type: str) -> Dict:
        """Parse batch job results with robust error handling."""
        results = {}
        
        # Get output location from job
        output_info = batch_job.output_info
        gcs_output_directory = output_info.gcs_output_directory
        
        # Parse GCS path
        if gcs_output_directory.startswith("gs://"):
            bucket_name, prefix = gcs_output_directory[5:].split("/", 1)
        else:
            raise ValueError(f"Invalid GCS output directory: {gcs_output_directory}")
        
        # List all output files
        blobs = self.storage_client.list_blobs(bucket_name, prefix=prefix)
        
        # Create a reverse lookup from content to metadata for summarization
        content_to_metadata = {}
        if job_type == "summarization":
            for idx, meta in metadata.items():
                # Create a unique key from the content (first 100 chars should be enough)
                content_key = meta['original_content'][:100].strip()
                content_to_metadata[content_key] = meta
        
        for blob in blobs:
            if blob.name.endswith(".jsonl"):
                try:
                    content = blob.download_as_text()
                    for line_num, line in enumerate(content.splitlines()):
                        if not line.strip():
                            continue
                            
                        prediction = json.loads(line)
                        
                        if job_type == "summarization":
                            # Extract the chunk_id from the request
                            try:
                                request_text = prediction['request']['contents'][0]['parts'][0]['text']
                                # Extract CHUNK_ID
                                chunk_id_pattern = r'\[CHUNK_ID: (doc_\d+_chunk_\d+)\]'
                                match = re.search(chunk_id_pattern, request_text)
                                
                                if match:
                                    chunk_id = match.group(1)
                                    summary_text = self._extract_summary_from_prediction(prediction)
                                    results[chunk_id] = summary_text
                                    
                                    # Log first few mappings for verification
                                    if len(results) <= 3:
                                        # Extract a snippet of the original content for comparison
                                        content_start = request_text.find("```markdown\n") + len("```markdown\n")
                                        content_snippet = request_text[content_start:content_start + 100] + "..."
                                        logger.info(f"Summary mapping verified - {chunk_id}: Original content starts with: '{content_snippet}' -> Summary starts with: '{summary_text[:100]}...'")
                                else:
                                    # Content mapping not found in summaries
                                    logger.warning(f"No summary mapping found for chunk {chunk_id}")
                            except Exception as e:
                                logger.error(f"Error extracting chunk_id from request: {e}")
                        else:  # embeddings
                            # Extract the original content from instance to match with doc_ids
                            try:
                                if 'instance' in prediction and 'content' in prediction['instance']:
                                    content = prediction['instance']['content']
                                    content_key = content[:200].strip()
                                    
                                    # metadata for embeddings is content_to_doc_id mapping
                                    if content_key in metadata:
                                        doc_id = metadata[content_key]
                                        embedding = self._extract_embedding_from_prediction(prediction)
                                        results[doc_id] = embedding
                                        
                                        # Log first few mappings for verification
                                        if len(results) <= 3:
                                            embedding_preview = str(embedding[:5]) + "..." if embedding and len(embedding) > 5 else str(embedding)
                                            logger.info(f"Embedding mapping verified - doc_id {doc_id}: Content starts with: '{content[:100]}...' -> Embedding starts with: {embedding_preview}")
                                    else:
                                        logger.warning(f"Could not find doc_id for embedding content (line {line_num})")
                                else:
                                    logger.warning(f"No instance/content found in embedding prediction (line {line_num})")
                            except Exception as e:
                                logger.error(f"Error processing embedding result: {e}")
                        
                except Exception as e:
                    logger.error(f"Error parsing output file {blob.name}: {e}")
                    continue
        
        logger.info(f"Parsed {len(results)} results from batch job")
        
        # Log summary of results for verification
        if job_type == "summarization" and results:
            logger.info(f"Summary batch results: Successfully mapped {len(results)} summaries to chunks")
            sample_ids = list(results.keys())[:3]
            logger.info(f"Sample chunk IDs processed: {sample_ids}")
        elif job_type == "embeddings" and results:
            logger.info(f"Embeddings batch results: Successfully mapped {len(results)} embeddings to documents")
            sample_ids = list(results.keys())[:3]
            logger.info(f"Sample document IDs processed: {sample_ids}")
        
        # Schedule cleanup
        self._schedule_gcs_cleanup(gcs_output_directory)
        
        return results
    
    def _extract_summary_from_prediction(self, prediction: Dict) -> str:
        """Extract summary text with multiple parsing strategies."""
        try:
            # Strategy 1: Batch prediction format (the actual format from Gemini)
            if 'response' in prediction:
                response = prediction['response']
                if 'candidates' in response and len(response['candidates']) > 0:
                    candidate = response['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            return parts[0]['text'].strip()
            
            # Strategy 2: Standard Vertex AI response format
            if 'predictions' in prediction and len(prediction['predictions']) > 0:
                pred = prediction['predictions'][0]
                
                # Check for candidates format
                if 'candidates' in pred and len(pred['candidates']) > 0:
                    content = pred['candidates'][0].get('content', {})
                    if 'parts' in content and len(content['parts']) > 0:
                        return content['parts'][0].get('text', '').strip()
                
                # Check for direct text format
                if 'text' in pred:
                    return pred['text'].strip()
                
                # Check for content.text format
                if 'content' in pred and 'text' in pred['content']:
                    return pred['content']['text'].strip()
            
            # Strategy 3: Direct prediction format
            if 'prediction' in prediction:
                if isinstance(prediction['prediction'], str):
                    return prediction['prediction'].strip()
                elif isinstance(prediction['prediction'], dict):
                    return prediction['prediction'].get('text', '').strip()
            
            # Strategy 4: Raw text response
            if 'text' in prediction:
                return prediction['text'].strip()
            
            # Log the structure for debugging
            logger.warning(f"Unknown prediction format: {json.dumps(prediction, indent=2)[:500]}")
            return "[Summary generation failed]"
            
        except Exception as e:
            logger.error(f"Error extracting summary: {e}")
            return "[Summary extraction error]"
    
    def _extract_embedding_from_prediction(self, prediction: Dict) -> List[float]:
        """Extract embedding vector with error handling."""
        try:
            if 'predictions' in prediction and len(prediction['predictions']) > 0:
                pred = prediction['predictions'][0]
                
                # Check for embeddings/values format
                if 'embeddings' in pred:
                    if 'values' in pred['embeddings']:
                        return pred['embeddings']['values']
                    elif isinstance(pred['embeddings'], list):
                        return pred['embeddings']
                
                # Check for direct values format
                if 'values' in pred:
                    return pred['values']
                
                # Check for vector format
                if 'vector' in pred:
                    return pred['vector']
            
            # Direct embedding format
            if 'embedding' in prediction:
                return prediction['embedding']
            
            logger.warning(f"Unknown embedding format: {json.dumps(prediction, indent=2)[:500]}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting embedding: {e}")
            return None
    
    def _run_vertex_ai_summarization_batch(self, job_id: str, batches: List[Tuple], db: Session, job: IndexingJob) -> Dict[str, str]:
        """
        Run Vertex AI batch summarization with proper progress tracking and error handling.
        """
        all_summaries = {}
        total_batches = len(batches)
        
        for batch_idx, (gcs_input_uri, chunk_metadata) in enumerate(batches):
            try:
                batch_num = batch_idx + 1
                logger.info(f"Processing batch {batch_num}/{total_batches} for job {job_id}")
                
                # Calculate progress
                base_progress = 30 + (batch_idx / total_batches) * 20
                
                asyncio.run(self._send_progress_update(job, {
                    "progress": base_progress,
                    "stage": f"Processing summarization batch {batch_num}/{total_batches}",
                    "current_batch": batch_num,
                    "total_batches": total_batches
                }))
                
                # Run batch job with retry
                batch_job = self._run_vertex_ai_batch_with_retry(
                    job_id=f"{job_id}_batch_{batch_num}",
                    gcs_input_uri=gcs_input_uri,
                    model_name=self.SUMMARIZATION_MODEL,
                    model_parameters={
                        "temperature": 0.3,
                        "maxOutputTokens": 512,
                        "topP": 0.8,
                        "topK": 40
                    },
                    job_type="summarization"
                )
                
                # Monitor with actual progress
                summaries = self._monitor_and_collect_results(
                    batch_job, chunk_metadata, job, base_progress, 
                    20/total_batches, "summarization"
                )
                
                all_summaries.update(summaries)
                
            except Exception as e:
                logger.error(f"Failed to process batch {batch_num}: {e}")
                # Continue with other batches
                continue
        
        if not all_summaries:
            raise RuntimeError("All summarization batches failed")
        
        logger.info(f"Generated {len(all_summaries)} summaries across {total_batches} batches")
        
        # Log sample mappings for verification
        if all_summaries:
            sample_items = list(all_summaries.items())[:3]
            for chunk_id, summary in sample_items:
                logger.info(f"Final summary mapping sample - {chunk_id}: '{summary[:80]}...'")
        
        return all_summaries
    
    def _save_summarized_chunks(self, summaries: Dict[str, str], all_metadata: List[Dict], db: Session, collection: Collection):
        """
        Save summarized chunks with batch transaction management.
        """
        from src.database.database import save_documents_to_db
        
        # Process in batches to avoid transaction timeout
        BATCH_SIZE = 100
        processed_count = 0
        
        # Group summaries by source_file_id
        file_summaries = {}
        
        for batch_metadata in all_metadata:
            for chunk_id, summary_text in summaries.items():
                source_file_id = int(chunk_id.split('_')[1])
                
                if source_file_id not in file_summaries:
                    file_summaries[source_file_id] = []
                
                # Find corresponding metadata
                if isinstance(batch_metadata, dict):
                    # batch_metadata is the metadata dictionary from a single batch
                    for idx, meta in batch_metadata.items():
                        if meta['source_file_id'] == source_file_id and chunk_id.endswith(f"_chunk_{meta['chunk_index']}"):
                            file_summaries[source_file_id].append({
                                'page_content': summary_text,
                                'metadata': {
                                    'original_content': meta['original_content'],
                                    'chunk_title': f"Chunk {meta['chunk_index']}",
                                    'source': meta['file_name'],
                                    'chunk_number': meta['chunk_index'],
                                    'has_table': meta['has_table'],
                                    'file_url': meta['file_url'],
                                    'is_sub_chunk': meta.get('is_sub_chunk', False),
                                    'drug_name': 'Unknown'
                                }
                            })
                            break
        
        # Save documents in batches
        for source_file_id, documents in file_summaries.items():
            try:
                # Delete existing DocumentData entries for this source_file_id
                existing_docs = db.query(DocumentData).filter_by(source_file_id=source_file_id).all()
                existing_count = len(existing_docs)
                if existing_count > 0:
                    logger.info(f"Deleting {existing_count} existing DocumentData entries for source_file_id {source_file_id}")
                    
                    # Also clean up any existing vectors in Qdrant
                    # Note: This is important to prevent orphaned vectors
                    self._cleanup_qdrant_vectors_for_documents(existing_docs, collection.vector_db_collection_name)
                    
                    # Now delete from database
                    db.query(DocumentData).filter_by(source_file_id=source_file_id).delete()
                    db.commit()
                    logger.info(f"Successfully deleted old entries for source_file_id {source_file_id}")
                
                # Process in smaller batches
                for i in range(0, len(documents), BATCH_SIZE):
                    batch = documents[i:i + BATCH_SIZE]
                    
                    # Get source file for drug_name
                    source_file = db.query(SourceFiles).filter_by(id=source_file_id).first()
                    drug_name = source_file.drug_name if source_file else "Unknown"
                    
                    # Update drug_name in metadata
                    for doc in batch:
                        doc['metadata']['drug_name'] = drug_name
                    
                    # Save batch to database
                    document_ids = save_documents_to_db(
                        db=db,
                        source_file_id=source_file_id,
                        file_name=source_file.file_name if source_file else "unknown",
                        documents=batch
                    )
                    
                    processed_count += len(batch)
                    
                    # Commit after each batch
                    db.commit()
                    
                    logger.info(f"Saved batch of {len(batch)} documents for source file {source_file_id}")
                    
                    # Log first document in batch for verification
                    if batch and processed_count <= 3:
                        first_doc = batch[0]
                        logger.info(f"Sample saved document - source_file_id: {source_file_id}, content preview: '{first_doc['page_content'][:80]}...'")
                
                # Update source file status
                if source_file:
                    source_file.status = 'DOCUMENT_STORED'
                    source_file.comments = f"Processed with batch summarization. {len(documents)} documents created."
                    db.commit()
                
            except Exception as e:
                logger.error(f"Error saving summarized chunks for source file {source_file_id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Completed saving {processed_count} summarized chunks")
    
    def _prepare_embeddings_batch_input(self, job: IndexingJob, db: Session, document_ids: List[int] = None) -> List[Tuple]:
        """
        Prepare JSONL input for embeddings batch job with batching.
        
        Args:
            job: The IndexingJob
            db: Database session
            document_ids: Optional filtered list of document IDs. If not provided, uses job.options
        """
        if document_ids is None:
            document_ids = job.options.get('document_ids', [])
        
        # Fetch DocumentData (now contains summaries)
        docs_data = db.query(DocumentData).filter(
            DocumentData.source_file_id.in_(document_ids)
        ).all()
        
        if not docs_data:
            logger.warning(f"No DocumentData found for documents: {document_ids}")
            return []
        
        batches = []
        current_batch = {"jsonl": "", "doc_ids": [], "counter": 0}
        
        for doc_data in docs_data:
            # Create instance for text-embedding-004
            instance = {
                "content": doc_data.doc_content,  # Summary text
                "task_type": "RETRIEVAL_DOCUMENT"  # Optimize for retrieval
            }
            
            # Check batch size
            if current_batch["counter"] >= self.BATCH_SIZE_LIMIT:
                batches.append(self._upload_embeddings_batch(
                    current_batch, job.job_id, len(batches)
                ))
                current_batch = {"jsonl": "", "doc_ids": [], "counter": 0}
            
            current_batch["jsonl"] += json.dumps(instance) + "\n"
            current_batch["doc_ids"].append(doc_data.id)
            current_batch["counter"] += 1
        
        # Upload final batch
        if current_batch["jsonl"]:
            batches.append(self._upload_embeddings_batch(
                current_batch, job.job_id, len(batches)
            ))
        
        return batches

    def _upload_embeddings_batch(self, batch_data: dict, job_id: str, batch_num: int) -> tuple:
        """Upload embeddings batch to GCS."""
        gcs_path = f"batch-embeddings-input/{job_id}/batch_{batch_num}.jsonl"
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(batch_data["jsonl"], content_type="application/jsonl")
        
        input_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"
        logger.info(f"Uploaded embeddings batch {batch_num} to {input_uri}")
        
        return input_uri, batch_data["doc_ids"]

    def _run_vertex_ai_embeddings_batch(self, job_id: str, batches: List[Tuple], 
                                       db: Session, job: IndexingJob) -> Dict[Union[int, str], List[float]]:
        """Run embeddings generation with batch processing."""
        all_embeddings = {}
        total_batches = len(batches)
        
        for batch_idx, (gcs_input_uri, doc_ids) in enumerate(batches):
            try:
                batch_num = batch_idx + 1
                base_progress = 70 + (batch_idx / total_batches) * 20
                
                asyncio.run(self._send_progress_update(job, {
                    "progress": base_progress,
                    "stage": f"Processing embeddings batch {batch_num}/{total_batches}"
                }))
                
                # Get document contents for this batch to create content mapping
                batch_docs = db.query(DocumentData).filter(
                    DocumentData.id.in_(doc_ids)
                ).all()
                
                # Create content hash to doc_id mapping
                content_to_doc_id = {}
                for doc in batch_docs:
                    # Use first 200 chars as key to handle potential truncation
                    content_key = doc.doc_content[:200].strip()
                    content_to_doc_id[content_key] = doc.id
                
                # Run batch job
                batch_job = self._run_vertex_ai_batch_with_retry(
                    job_id=f"{job_id}_embeddings_batch_{batch_num}",
                    gcs_input_uri=gcs_input_uri,
                    model_name=self.EMBEDDINGS_MODEL,
                    model_parameters={},  # text-embedding-004 doesn't need parameters
                    job_type="embeddings"
                )
                
                # Monitor and collect results with content mapping
                embeddings = self._monitor_and_collect_results(
                    batch_job, content_to_doc_id, 
                    job, base_progress, 20/total_batches, "embeddings"
                )
                
                # Results are already mapped to doc_ids
                all_embeddings.update(embeddings)
                
            except Exception as e:
                logger.error(f"Failed to process embeddings batch {batch_num}: {e}")
                continue
        
        return all_embeddings

    def _cleanup_qdrant_vectors_for_documents(self, documents: List[DocumentData], collection_name: str):
        """Clean up existing vectors in Qdrant for given documents."""
        try:
            if not documents:
                return
            
            # Get document IDs to delete (use same UUID format as when adding)
            doc_ids = [f"00000000-0000-0000-0000-{doc.id:012d}" for doc in documents]
            
            # Delete vectors from Qdrant using point IDs
            from qdrant_client.http.models import PointIdsList
            self.qdrant_util.client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=doc_ids),
                wait=True
            )
            
            logger.info(f"Cleaned up {len(doc_ids)} vectors from Qdrant collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up Qdrant vectors: {e}")
            # Continue processing even if cleanup fails
    
    def _get_or_create_collection_safe(self, collection_name: str, max_retries: int = 3):
        """Safely get or create a Qdrant collection with error handling."""
        
        for attempt in range(max_retries):
            try:
                # Ensure collection exists in Qdrant
                self.qdrant_util.get_or_create_collection(collection_name=collection_name)
                logger.info(f"Using Qdrant collection: {collection_name}")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to access collection (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep((attempt + 1) * 2)  # Exponential backoff
                    
                    # Get fresh client from singleton if needed
                    try:
                        from src.utils.qdrant_singleton import qdrant_singleton
                        qdrant_singleton.reset_client()
                        self.qdrant_client = get_qdrant_client()
                        self.qdrant_util = QdrantUtil(use_persistent_client=True)
                        logger.info("Got fresh Qdrant client from singleton")
                    except Exception as reset_error:
                        logger.error(f"Failed to reset Qdrant client: {reset_error}")
                else:
                    logger.error(f"Failed to access Qdrant collection after {max_retries} attempts: {e}")
                    raise
        
        return False

    def _add_embeddings_to_qdrant_batch(self, job: IndexingJob, 
                                         embeddings: Dict[Union[int, str], List[float]], db: Session):
        """Add embeddings to Qdrant with batch processing."""
        collection = db.query(Collection).filter_by(id=job.collection_id).first()
        
        # Ensure consistent collection name generation
        collection_name = collection.vector_db_collection_name
        if not collection_name:
            collection_name = f"collection_{collection.id}_{self.qdrant_util.sanitize_collection_name(collection.name)}"
            collection.vector_db_collection_name = collection_name
            db.commit()
        
        # Get or create collection with retry logic
        self.qdrant_util.get_or_create_collection(collection_name)
        
        # Process in batches for Qdrant
        QDRANT_BATCH_SIZE = 500
        
        doc_ids = list(embeddings.keys())
        total_added = 0
        
        from qdrant_client.http.models import PointStruct
        
        for i in range(0, len(doc_ids), QDRANT_BATCH_SIZE):
            batch_doc_ids = doc_ids[i:i + QDRANT_BATCH_SIZE]
            
            # Fetch document data
            docs_data = db.query(DocumentData).filter(
                DocumentData.id.in_(batch_doc_ids)
            ).all()
            
            # Prepare batch data
            points = []
            
            for doc in docs_data:
                # Check for embedding with both int and str keys
                embedding = None
                if doc.id in embeddings:
                    embedding = embeddings[doc.id]
                elif str(doc.id) in embeddings:
                    embedding = embeddings[str(doc.id)]
                
                if embedding is not None:
                    # Parse metadata
                    metadata = json.loads(doc.metadata_content) if doc.metadata_content else {}
                    
                    # Create payload in Agno format
                    payload = {
                        "content": doc.doc_content or "",
                        "name": metadata.get("source", doc.file_name or "unknown"),
                        "usage": {},  # Required by Agno library
                        "meta_data": {
                            **metadata,
                            "document_id": doc.id,
                            "source_file_id": doc.source_file_id,
                            "collection_id": collection.id,
                            "file_name": doc.file_name or "unknown",
                            "page_number": metadata.get("page_number", 0),
                            "chunk_index": metadata.get("chunk_index", metadata.get("chunk_number", 0)),
                            "content_type": metadata.get("content_type", "unknown"),
                            **({"original_content": doc.doc_content or ""} if "original_content" not in metadata else {}),
                            "created_at": doc.created_at.isoformat() if doc.created_at else datetime.utcnow().isoformat(),
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    }
                    
                    # Create PointStruct with UUID format
                    # Qdrant expects either an unsigned integer or UUID string
                    point_id = f"00000000-0000-0000-0000-{doc.id:012d}"  # Format as UUID
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                    points.append(point)
            
            # Add to Qdrant
            if points:  # Only add if we have data
                try:
                    # Debug logging
                    logger.info(f"About to add {len(points)} points to Qdrant collection {collection_name}")
                    for i, point in enumerate(points[:3]):  # Log first 3 points
                        logger.info(f"Point {i}: ID={point.id} (type={type(point.id)}), vector length={len(point.vector) if point.vector else 0}")
                    
                    # Use QdrantUtil for proper handling
                    self.qdrant_util.client.upsert(
                        collection_name=collection_name,
                        points=points,
                        wait=True
                    )
                    total_added += len(points)
                    logger.info(f"Added batch of {len(points)} embeddings to Qdrant")
                except Exception as e:
                    logger.error(f"Failed to add batch to Qdrant: {e}")
                    # Log detailed error info
                    if points:
                        logger.error(f"First point ID: {points[0].id} (type: {type(points[0].id)})")
                    continue
        
        logger.info(f"Successfully added {total_added} embeddings to Qdrant")
        
        # Log sample of what was added for verification
        if total_added > 0 and doc_ids:
            sample_doc_ids = doc_ids[:3]
            logger.info(f"Sample of document IDs added to Qdrant: {sample_doc_ids}")
    
    async def _send_failure_notification(self, job: IndexingJob, error_message: str):
        """Send failure notification via WebSocket."""
        try:
            async with aiohttp.ClientSession() as session:
                ws_url = "ws://backend:8090/api/collections/indexing-updates"
                async with session.ws_connect(ws_url) as ws:
                    message = {
                        "type": "error",
                        "jobId": job.job_id,
                        "data": {
                            "job_id": job.job_id,
                            "collection_id": job.collection_id,
                            "collectionId": job.collection_id,
                            "status": "failed",
                            "error": error_message,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                    await ws.send_json(message)
                    logger.info(f"Sent failure notification for job {job.job_id}")
        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}")

    def subscribe(self):
        """Subscribes to the Pub/Sub topic and processes messages."""
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(GCP_PROJECT_ID, PUBSUB_SUBSCRIPTION_ID)

        def callback(message):
            try:
                data = json.loads(message.data)
                job_id = data.get("job_id")
                if job_id:
                    logger.info(f"Received message for job ID: {job_id}")
                    self.process_job(job_id)
                message.ack()
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                message.nack()

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        logger.info(f"Listening for messages on {subscription_path}...")
        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()

def main():
    """Main entry point"""
    indexer = CollectionIndexer()
    indexer.subscribe()

if __name__ == "__main__":
    main()
