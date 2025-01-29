#!/usr/bin/env python3
"""
Standalone Vertex AI Batch Prediction Processor

This service listens to a Pub/Sub topic for new indexing jobs, prepares the data,
creates a Vertex AI Batch Prediction job for generating embeddings, and then
loads the results back into Qdrant vector database.

Usage:
    python -m api.services.vertex_ai_batch_processor
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime

from google.cloud import pubsub_v1, storage
from google.cloud.aiplatform import gapic as aiplatform
from google.api_core import retry, exceptions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

# Add parent directory to path for imports
import sys
sys.path.append('/app')

from database.database import IndexingJob, SourceFiles, DocumentData, Collection, collection_document_association
from utils.qdrant_util import QdrantUtil
from config.settings import settings

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- GCP Configuration ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
PUBSUB_TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID")
PUBSUB_SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION_ID", "batch-indexing-jobs-sub")
EMBEDDING_MODEL = settings.LLM_GEMINI_EMBEDDING.split('/')[-1] if '/' in settings.LLM_GEMINI_EMBEDDING else settings.LLM_GEMINI_EMBEDDING # The model to use for embeddings

class VertexAIBatchProcessor:
    """
    Orchestrates the Vertex AI Batch Prediction workflow for document indexing.
    """
    def __init__(self):
        # Database connection
        self.engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # GCP Clients
        self.storage_client = storage.Client()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(GCP_PROJECT_ID, PUBSUB_SUBSCRIPTION_ID)

        # Vertex AI API Client
        client_options = {"api_endpoint": f"{GCP_REGION}-aiplatform.googleapis.com"}
        self.job_service_client = aiplatform.JobServiceClient(client_options=client_options)

        # Qdrant Utility
        self.qdrant_util = QdrantUtil.get_instance(use_persistent_client=True)

    def get_db(self):
        return self.SessionLocal()

    def _sanitize_name(self, name: str) -> str:
        """Sanitize collection name for vector database."""
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip('_')

    async def _prepare_data_and_upload(self, job: IndexingJob, db) -> str:
        """
        Fetches document content, chunks it, creates a JSONL file,
        and uploads it to GCS.
        """
        logger.info(f"Job {job.job_id}: Preparing data and uploading to GCS.")
        document_ids = job.options.get('document_ids', [])
        documents = db.query(SourceFiles).filter(SourceFiles.id.in_(document_ids)).all()

        jsonl_content = ""
        total_chunks = 0

        # For reindex jobs, we need to reprocess PDFs again
        if job.job_type == 'reindex':
            logger.info(f"Job {job.job_id}: Reindex job detected. Will reprocess PDFs.")
            
            # First, update document status from DOCUMENT_STORED to PENDING
            for doc in documents:
                if doc.status == 'DOCUMENT_STORED':
                    doc.status = 'PENDING'
                    # Remove vectors from current collection if they exist
                    collection = db.query(Collection).filter_by(id=job.collection_id).first()
                    if collection and collection.vector_db_collection_name:
                        try:
                            vector_db_collection = self.qdrant_util.get_or_create_collection(collection.vector_db_collection_name)
                            # Delete all vectors for this document based on metadata
                            results = vector_db_collection.get(
                                where={"source_file_id": doc.id}
                            )
                            if results['ids']:
                                vector_db_collection.delete(ids=results['ids'])
                                logger.info(f"Removed {len(results['ids'])} existing vectors for document {doc.id} from collection {collection.vector_db_collection_name}")
                            else:
                                logger.info(f"No existing vectors found for document {doc.id} in collection {collection.vector_db_collection_name}")
                        except Exception as e:
                            logger.warning(f"Failed to remove existing vectors for doc {doc.id}: {e}")
                    
                    # Clear existing DocumentData entries for reprocessing
                    db.query(DocumentData).filter_by(source_file_id=doc.id).delete()
                    logger.info(f"Cleared DocumentData for doc {doc.id} for reprocessing")
            
            db.commit()
            
            # Now process PDFs using FDAPipelineV2
            from utils.fda_pipeline_v2 import FDAPipelineV2
            pipeline = FDAPipelineV2()
            
            for doc in documents:
                if doc.status == 'PENDING':
                    try:
                        logger.info(f"Processing PDF for document {doc.id}: {doc.file_name}")
                        # Process the PDF
                        result = pipeline.process_single_pdf(doc.file_url, doc.file_name)
                        
                        if result and result.get('chunks'):
                            # Store chunks in DocumentData
                            for chunk_idx, chunk in enumerate(result['chunks']):
                                doc_data = DocumentData(
                                    source_file_id=doc.id,
                                    doc_content=chunk.get('content', ''),
                                    metadata_content=json.dumps(chunk.get('metadata', {}))
                                )
                                db.add(doc_data)
                            
                            # Update document status to DOCUMENT_STORED
                            doc.status = 'DOCUMENT_STORED'
                            doc.metadata_extracted = True
                            logger.info(f"Successfully processed document {doc.id} with {len(result['chunks'])} chunks")
                        else:
                            logger.error(f"Failed to process PDF for document {doc.id}")
                            job.failed_documents += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing document {doc.id}: {e}")
                        job.failed_documents += 1
                        
            db.commit()

        # For both index and reindex jobs, check if document has been indexed in another collection
        for doc in documents:
            # Check if document is already indexed in another collection
            if doc.status == 'DOCUMENT_STORED' and doc.vector_db_collections:
                existing_collection = None
                for coll in doc.vector_db_collections:
                    if coll.get('collection_id') != job.collection_id:
                        existing_collection = coll
                        break
                
                if existing_collection:
                    logger.info(f"Document {doc.id} already indexed in collection {existing_collection['collection_name']}. Copying vectors.")
                    
                    # Copy vectors from existing collection to this collection
                    try:
                        source_collection_name = existing_collection['collection_name']
                        source_collection = self.qdrant_util.get_or_create_collection(source_collection_name)
                        
                        # Get the target collection
                        collection = db.query(Collection).filter_by(id=job.collection_id).first()
                        if not collection:
                            raise ValueError(f"Collection {job.collection_id} not found")
                        
                        target_collection_name = collection.vector_db_collection_name
                        if not target_collection_name:
                            sanitized_name = self._sanitize_name(collection.name)
                            target_collection_name = f"collection_{job.collection_id}_{sanitized_name}"
                            collection.vector_db_collection_name = target_collection_name
                            db.commit()
                        
                        target_collection = self.qdrant_util.get_or_create_collection(target_collection_name)
                        
                        # Copy vectors with updated metadata
                        # Query all vectors for this document from source collection
                        results = source_collection.get(
                            where={"document_id": doc.id},
                            include=["embeddings", "metadatas", "documents"]
                        )
                        
                        if results['ids']:
                            # Update IDs and metadata for the new collection
                            new_ids = []
                            new_metadatas = []
                            
                            for i, old_id in enumerate(results['ids']):
                                # Generate new ID for this collection
                                chunk_num = old_id.split('_chunk_')[-1] if '_chunk_' in old_id else str(i)
                                new_id = f"collection_{job.collection_id}_doc_{doc.id}_chunk_{chunk_num}"
                                new_ids.append(new_id)
                                
                                # Update metadata with new collection info
                                metadata = results['metadatas'][i].copy() if i < len(results['metadatas']) else {}
                                metadata['collection_id'] = job.collection_id
                                metadata['source_file_id'] = doc.id
                                metadata['file_name'] = doc.file_name
                                metadata['entity_name'] = doc.entity_name
                                new_metadatas.append(metadata)
                            
                            # Add to target collection
                            target_collection.add(
                                ids=new_ids,
                                embeddings=results['embeddings'],
                                metadatas=new_metadatas,
                                documents=results.get('documents', ['']*len(new_ids))
                            )
                            
                            logger.info(f"Successfully copied {len(new_ids)} vectors for document {doc.id} to collection {job.collection_id}")
                            
                            # Update document's vector_db_collections
                            if not any(c.get('collection_id') == job.collection_id for c in doc.vector_db_collections):
                                doc.vector_db_collections.append({
                                    'collection_id': job.collection_id,
                                    'collection_name': target_collection_name,
                                    'indexed_at': datetime.utcnow().isoformat()
                                })
                                flag_modified(doc, "vector_db_collections")
                            
                            # Mark as processed
                            job.processed_documents += 1
                            await self._send_progress_update(job, doc.file_name, "processing")
                            
                            # Skip the normal processing for this document
                            continue
                            
                    except Exception as e:
                        logger.error(f"Failed to copy vectors for document {doc.id}: {e}")
                        # Fall through to normal processing
            
            # Normal processing for documents that need indexing
            doc_data_entries = db.query(DocumentData).filter_by(source_file_id=doc.id).all()
            if not doc_data_entries:
                # Process PDF if PENDING
                if doc.status == 'PENDING':
                    try:
                        from utils.fda_pipeline_v2 import FDAPipelineV2
                        pipeline = FDAPipelineV2()
                        
                        logger.info(f"Processing PDF for document {doc.id}: {doc.file_name}")
                        result = pipeline.process_single_pdf(doc.file_url, doc.file_name)
                        
                        if result and result.get('chunks'):
                            for chunk_idx, chunk in enumerate(result['chunks']):
                                doc_data = DocumentData(
                                    source_file_id=doc.id,
                                    doc_content=chunk.get('content', ''),
                                    metadata_content=json.dumps(chunk.get('metadata', {}))
                                )
                                db.add(doc_data)
                                doc_data_entries.append(doc_data)
                            
                            doc.status = 'DOCUMENT_STORED'
                            doc.metadata_extracted = True
                            db.commit()
                            logger.info(f"Successfully processed document {doc.id} with {len(result['chunks'])} chunks")
                        else:
                            logger.error(f"Failed to process PDF for document {doc.id}")
                            job.failed_documents += 1
                            continue
                            
                    except Exception as e:
                        logger.error(f"Error processing document {doc.id}: {e}")
                        job.failed_documents += 1
                        continue
                else:
                    logger.warning(f"Job {job.job_id}: No DocumentData found for doc {doc.id}, skipping.")
                    continue

            for entry_idx, entry in enumerate(doc_data_entries):
                # Simple chunking by splitting content.
                # A more sophisticated chunking strategy from the original service could be used here.
                chunks = entry.doc_content.split('\n\n')
                for chunk_num, chunk_text in enumerate(chunks):
                    if not chunk_text.strip():
                        continue
                    
                    chunk_id = f"collection_{job.collection_id}_doc_{doc.id}_chunk_{total_chunks}"
                    # The `content` field is what the Vertex AI model expects
                    record = {"id": chunk_id, "content": chunk_text}
                    jsonl_content += json.dumps(record) + "\n"
                    total_chunks += 1
        
        if not jsonl_content:
            raise ValueError("No content to index after processing all documents.")

        # Upload to GCS
        gcs_input_filename = f"batch-jobs/{job.job_id}/input.jsonl"
        bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_input_filename)
        blob.upload_from_string(jsonl_content, content_type="application/jsonl")
        
        logger.info(f"Job {job.job_id}: Uploaded {total_chunks} chunks to gs://{GCS_BUCKET_NAME}/{gcs_input_filename}")
        return f"gs://{GCS_BUCKET_NAME}/{gcs_input_filename}"

    async def _create_batch_prediction_job(self, job: IndexingJob, gcs_input_uri: str) -> str:
        """
        Creates and starts a new Vertex AI Batch Prediction job.
        """
        logger.info(f"Job {job.job_id}: Creating Vertex AI Batch Prediction job.")
        
        display_name = f"indexing-job-{job.job_id}-{int(time.time())}"
        gcs_output_uri = f"gs://{GCS_BUCKET_NAME}/batch-jobs/{job.job_id}/output/"
        
        # Configure the batch prediction job
        batch_prediction_job = {
            "display_name": display_name,
            "model": f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{EMBEDDING_MODEL}",
            "input_config": {
                "instances_format": "jsonl",
                "gcs_source": {"uris": [gcs_input_uri]},
            },
            "output_config": {
                "predictions_format": "jsonl",
                "gcs_destination": {"output_uri_prefix": gcs_output_uri},
            },
        }

        parent = f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}"
        
        try:
            response = self.job_service_client.create_batch_prediction_job(
                parent=parent, batch_prediction_job=batch_prediction_job
            )
            logger.info(f"Job {job.job_id}: Successfully created Vertex AI job: {response.name}")
            return response.name # This is the full resource name of the job
        except Exception as e:
            logger.error(f"Job {job.job_id}: Failed to create Vertex AI job: {e}", exc_info=True)
            raise

    async def _monitor_and_load_results(self, job: IndexingJob, vertex_job_name: str, db):
        """
        Waits for the Vertex AI job to complete, then downloads the results,
        enriches them with metadata, and loads them into Qdrant.
        """
        logger.info(f"Job {job.job_id}: Monitoring Vertex AI job for completion...")
        
        # Define a retry policy for transient network errors
        transient_error_retry = retry.Retry(
            predicate=retry.if_exception_type(
                exceptions.ServiceUnavailable,
                exceptions.DeadlineExceeded,
            ),
            initial=5.0,  # Start with a 5-second delay
            maximum=120.0, # Cap the delay at 2 minutes
            multiplier=2.0, # Double the delay each time
            deadline=900.0, # Total deadline of 15 minutes for all retries
        )

        while True:
            response = self.job_service_client.get_batch_prediction_job(
                name=vertex_job_name,
                retry=transient_error_retry
            )
            state = response.state
            if state == aiplatform.JobState.JOB_STATE_SUCCEEDED:
                logger.info(f"Job {job.job_id}: Vertex AI job succeeded.")
                break
            elif state in [aiplatform.JobState.JOB_STATE_FAILED, aiplatform.JobState.JOB_STATE_CANCELLED]:
                error_msg = f"Vertex AI job failed or was cancelled. State: {state.name}, Error: {response.error.message}"
                raise RuntimeError(error_msg)
            
            logger.info(f"Job {job.job_id}: Vertex AI job state is {state.name}. Waiting...")
            await asyncio.sleep(60) # Poll every 60 seconds

        # --- Load results from GCS into Qdrant ---
        logger.info(f"Job {job.job_id}: Loading results from GCS into Qdrant.")
        
        collection = db.query(Collection).filter(Collection.id == job.collection_id).first()
        if not collection:
            raise ValueError(f"Collection {job.collection_id} not found for job {job.job_id}")

        vector_db_collection_name = collection.vector_db_collection_name
        if not vector_db_collection_name:
            # Generate it if not set, ensuring consistency
            sanitized_name = self._sanitize_name(collection.name)
            vector_db_collection_name = f"collection_{job.collection_id}_{sanitized_name}"
            collection.vector_db_collection_name = vector_db_collection_name
            db.commit()
            logger.info(f"Generated and saved vector database collection name: {vector_db_collection_name}")

        bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        prefix = f"batch-jobs/{job.job_id}/output/"
        
        ids = []
        embeddings = []
        
        for blob in bucket.list_blobs(prefix=prefix):
            if blob.name.endswith(".jsonl"):
                content = blob.download_as_string()
                for line in content.decode("utf-8").splitlines():
                    prediction = json.loads(line)
                    
                    embedding_values = None
                    instance_id = prediction.get('instance', {}).get('id')

                    # Handle multiple possible response structures from Vertex AI
                    # Case 1: Nested 'prediction' key (singular)
                    if 'prediction' in prediction and isinstance(prediction.get('prediction'), dict):
                        pred_content = prediction['prediction']
                        if 'embeddings' in pred_content and isinstance(pred_content.get('embeddings'), dict):
                            embedding_values = pred_content['embeddings'].get('values')
                    
                    # Case 2: Nested 'predictions' key (plural, as a list)
                    elif 'predictions' in prediction and isinstance(prediction.get('predictions'), list) and prediction['predictions']:
                        pred_content = prediction['predictions'][0]
                        if isinstance(pred_content, dict) and 'embeddings' in pred_content and isinstance(pred_content.get('embeddings'), dict):
                            embedding_values = pred_content['embeddings'].get('values')

                    # Case 3: Flat 'embeddings' key
                    elif 'embeddings' in prediction and isinstance(prediction.get('embeddings'), dict):
                        embedding_values = prediction['embeddings'].get('values')

                    if instance_id and embedding_values is not None:
                        ids.append(instance_id)
                        embeddings.append(embedding_values)
                    else:
                        logger.warning(
                            f"Job {job.job_id}: Skipping result due to missing instance ID or embedding. "
                            f"Instance: {instance_id}, Has Embedding: {embedding_values is not None}. "
                            f"Prediction keys: {list(prediction.keys())}"
                        )

        if not ids:
            raise ValueError("Vertex AI job produced no embeddings.")

        # --- Enrich with Metadata ---
        logger.info(f"Job {job.job_id}: Enriching {len(ids)} embeddings with metadata.")
        
        # 1. Extract unique document IDs from the chunk IDs
        doc_ids_to_fetch = set()
        id_pattern = re.compile(r"_doc_(\d+)_")
        for chunk_id in ids:
            match = id_pattern.search(chunk_id)
            if match:
                doc_ids_to_fetch.add(int(match.group(1)))
        
        # 2. Fetch all required metadata in a single query
        source_files = db.query(SourceFiles).filter(SourceFiles.id.in_(list(doc_ids_to_fetch))).all()
        metadata_map = {file.id: {"source_filename": file.file_name, "document_id": file.id} for file in source_files}

        # 3. Build the metadatas list for Qdrant
        metadatas = []
        for chunk_id in ids:
            match = id_pattern.search(chunk_id)
            doc_id = int(match.group(1)) if match else None
            if doc_id and doc_id in metadata_map:
                metadatas.append(metadata_map[doc_id])
            else:
                # Append a default/empty metadata if mapping fails
                metadatas.append({"source_filename": "Unknown", "document_id": doc_id})

        # 4. Add to Qdrant with metadata using proper Agno format
        # Convert to format expected by qdrant_util.add_documents()
        documents_to_add = []
        for i, (id_, embedding, metadata) in enumerate(zip(ids, embeddings, metadatas)):
            # Extract content from metadata or use empty string
            content = metadata.get('content', metadata.get('original_content', ''))
            
            # Remove content from metadata to avoid duplication
            clean_metadata = {k: v for k, v in metadata.items() if k not in ['content']}
            
            documents_to_add.append({
                'page_content': content,
                'metadata': clean_metadata
            })
        
        # Use the properly fixed add_documents method that creates Agno format
        result = self.qdrant_util.add_documents(
            documents=documents_to_add,
            collection_name=vector_db_collection_name,
            embeddings=embeddings,
            ids=ids
        )
        
        # 5. Update the status in the association table to 'indexed'
        logger.info(f"Job {job.job_id}: Updating indexing_status for {len(doc_ids_to_fetch)} documents in collection {job.collection_id}.")
        try:
            update_stmt = (
                collection_document_association.update()
                .where(
                    collection_document_association.c.collection_id == job.collection_id,
                    collection_document_association.c.document_id.in_(list(doc_ids_to_fetch)),
                )
                .values(indexing_status="indexed", indexed_at=datetime.utcnow())
            )
            db.execute(update_stmt)
            db.commit()
            logger.info(f"Job {job.job_id}: Successfully updated indexing statuses in association table.")
        except Exception as e:
            logger.error(f"Job {job.job_id}: Failed to update indexing statuses in association table: {e}", exc_info=True)
            db.rollback()
            raise

        # 6. Update the vector_db_collections field (keep status as DOCUMENT_STORED)
        logger.info(f"Job {job.job_id}: Updating vector_db_collections for {len(doc_ids_to_fetch)} documents.")
        try:
            # Fetch the documents to update their JSON field
            source_files_to_update = db.query(SourceFiles).filter(SourceFiles.id.in_(list(doc_ids_to_fetch))).all()
            for sf in source_files_to_update:
                # Keep status as DOCUMENT_STORED (don't change to READY)
                
                # Safely update the JSON field
                existing_collections = sf.vector_db_collections or []
                if not any(c.get('collection_id') == job.collection_id for c in existing_collections):
                    existing_collections.append({
                        'collection_id': job.collection_id,
                        'collection_name': collection.vector_db_collection_name,
                        'indexed_at': datetime.utcnow().isoformat()
                    })
                    sf.vector_db_collections = existing_collections
                    # Explicitly mark the JSON field as modified to ensure SQLAlchemy picks up the change
                    flag_modified(sf, "vector_db_collections")
            
            db.commit()
            logger.info(f"Job {job.job_id}: Successfully updated document statuses and vector_db_collections.")
        except Exception as e:
            logger.error(f"Job {job.job_id}: Failed to update document statuses: {e}", exc_info=True)
            db.rollback()
            raise

        job.processed_documents = job.total_documents # Mark all as processed
        logger.info(f"Job {job.job_id}: Successfully loaded {len(ids)} embeddings with metadata into Qdrant collection '{vector_db_collection_name}.'")

    async def _send_progress_update(self, job: IndexingJob, current_doc_name: str = None, status: str = "processing"):
        """Send progress update for the job via HTTP to backend API."""
        try:
            progress_data = {
                "job_id": job.job_id,
                "collection_id": job.collection_id,
                "status": status,
                "progress": (job.processed_documents / job.total_documents * 100) if job.total_documents > 0 else 0,
                "total_documents": job.total_documents,
                "processed_documents": job.processed_documents,
                "failed_documents": job.failed_documents,
                "current_document": current_doc_name,
                "totalDocuments": job.total_documents,  # Frontend compatibility
                "processedDocuments": job.processed_documents,
                "failedDocuments": job.failed_documents,
                "currentDocument": current_doc_name,
                "stage": f"Processing document {job.processed_documents + 1} of {job.total_documents}"
            }
            
            logger.debug(f"Progress data to send: processed={progress_data['processed_documents']}, total={progress_data['total_documents']}, progress={progress_data['progress']}%")
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"http://backend:8090/api/collections/{job.collection_id}/indexing-progress"
                payload = {
                    "job_id": job.job_id,
                    "progress_data": progress_data
                }
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send progress update: {response.status}")
                    else:
                        logger.debug("Progress update sent successfully to backend API")
            
        except Exception as e:
            logger.error(f"Error sending progress update: {str(e)}")

    async def _send_completion_notification(self, job: IndexingJob):
        """Send completion notification via HTTP to backend API."""
        try:
            completion_data = {
                "job_id": job.job_id,
                "collection_id": job.collection_id,
                "status": "completed",
                "total_documents": job.total_documents,
                "processed_documents": job.processed_documents,
                "failed_documents": job.failed_documents,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "collectionId": job.collection_id,  # Frontend compatibility
                "totalDocuments": job.total_documents,
                "processedDocuments": job.processed_documents,
                "failedDocuments": job.failed_documents
            }
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"http://backend:8090/api/collections/{job.collection_id}/indexing-complete"
                payload = {
                    "job_id": job.job_id,
                    "completion_data": completion_data
                }
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send completion notification: {response.status}")
                    else:
                        logger.info(f"Sent completion notification for job {job.job_id}")
            
        except Exception as e:
            logger.error(f"Error sending completion notification: {str(e)}")

    async def process_job(self, message: pubsub_v1.subscriber.message.Message):
        """
        The main callback function to process a single Pub/Sub message.
        """
        job_id = None
        try:
            data = json.loads(message.data)
            job_id = data.get("job_id")
            if not job_id:
                logger.error("Received message without a job_id.")
                message.ack()
                return

            logger.info(f"Received job {job_id} from Pub/Sub. Starting processing.")
            db = self.get_db()
            job = db.query(IndexingJob).filter(IndexingJob.job_id == job_id).first()

            if not job or job.status != 'pending':
                logger.warning(f"Job {job_id} not found or not in 'pending' state. Acknowledging message.")
                message.ack()
                return

            # 1. Update job status to processing
            job.status = 'processing'
            job.started_at = datetime.utcnow()
            db.commit()
            await self._send_progress_update(job, status="processing")

            # 2. Prepare data and upload to GCS
            gcs_input_uri = await self._prepare_data_and_upload(job, db)

            # 3. Create Vertex AI Batch Prediction Job
            vertex_job_name = await self._create_batch_prediction_job(job, gcs_input_uri)
            job.options['vertex_job_name'] = vertex_job_name # Store for reference
            db.commit()

            # 4. Monitor job and load results
            await self._monitor_and_load_results(job, vertex_job_name, db)

            # 5. Mark job as completed
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            db.commit()
            await self._send_completion_notification(job)
            logger.info(f"Job {job_id} completed successfully.")
            message.ack()

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            try:
                # Mark job as failed in the database
                db = self.get_db()
                job = db.query(IndexingJob).filter(IndexingJob.job_id == job_id).first()
                if job:
                    job.status = 'failed'
                    job.completed_at = datetime.utcnow()
                    job.error_details = [{'error': str(e), 'timestamp': datetime.utcnow().isoformat()}]
                    db.commit()
                    await self._send_completion_notification(job)
            except Exception as db_err:
                logger.error(f"Could not even mark job {job_id} as failed: {db_err}")
            # Acknowledge the message to prevent it from being re-processed indefinitely
            message.ack()
        finally:
            if 'db' in locals() and db:
                db.close()

    def run(self):
        """
        Starts the Pub/Sub subscriber to listen for new jobs.
        """
        # Create subscription if it doesn't exist
        try:
            self.subscriber.create_subscription(
                name=self.subscription_path, topic=f"projects/{GCP_PROJECT_ID}/topics/{PUBSUB_TOPIC_ID}"
            )
            logger.info(f"Created Pub/Sub subscription: {self.subscription_path}")
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"Subscription {self.subscription_path} already exists.")
            else:
                logger.error(f"Failed to create subscription: {e}")
                return

        logger.info(f"Starting Vertex AI Batch Processor. Listening for messages on {self.subscription_path}...")
        streaming_pull_future = self.subscriber.subscribe(self.subscription_path, callback=lambda msg: asyncio.run(self.process_job(msg)))
        
        try:
            # Keep the main thread alive to allow the subscriber to run in the background.
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            logger.info("Processor stopped by user.")
        except Exception as e:
            streaming_pull_future.cancel()
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    processor = VertexAIBatchProcessor()
    processor.run()
