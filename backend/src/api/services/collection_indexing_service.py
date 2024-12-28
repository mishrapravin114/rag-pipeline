"""
Collection Indexing Service - Handles document indexing for collections
"""

import asyncio
import json
import logging
import re
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# GCP Pub/Sub Client
from google.cloud import pubsub_v1

from database.database import (
    Collection, SourceFiles, IndexingJob, collection_document_association,
    DrugSections, DocumentData
)
from utils.qdrant_util import QdrantUtil
from api.services.websocket_manager import get_connection_manager

logger = logging.getLogger(__name__)

# --- GCP Configuration ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
PUBSUB_TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID")


class CollectionIndexingService:
    """
    Service for creating and managing collection-specific indexing jobs.
    This service now delegates the actual embedding generation to a background
    processor via Google Cloud Pub/Sub.
    """
    
    def __init__(self):
        """Initialize the collection indexing service."""
        self.qdrant_util = QdrantUtil.get_instance(use_persistent_client=True)
        self.connection_manager = get_connection_manager()
        
        # Initialize Pub/Sub publisher client
        if GCP_PROJECT_ID and PUBSUB_TOPIC_ID:
            self.publisher = pubsub_v1.PublisherClient()
            self.topic_path = self.publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC_ID)
        else:
            self.publisher = None
            self.topic_path = None
            logger.warning("GCP_PROJECT_ID or PUBSUB_TOPIC_ID not set. Pub/Sub functionality will be disabled.")

    async def start_indexing_job(
        self,
        collection_id: int,
        document_ids: List[int],
        job_type: str = "index",
        options: Optional[Dict] = None,
        user_id: Optional[int] = None,
        db: Session = None
    ) -> str:
        """
        Starts a new indexing job by creating a job record in the database
        and publishing a message to a Google Cloud Pub/Sub topic.
        
        Returns:
            Job ID as a string.
        """
        if not self.publisher:
            raise ConnectionError("Pub/Sub publisher is not initialized. Check GCP configuration.")

        try:
            # Validate collection exists
            collection = db.query(Collection).filter_by(id=collection_id).first()
            if not collection:
                raise ValueError(f"Collection with ID {collection_id} not found")

            # Ensure the collection has a vector database-compatible name stored
            if not collection.vector_db_collection_name:
                sanitized_name = self._sanitize_name(collection.name)
                collection.vector_db_collection_name = f"collection_{collection_id}_{sanitized_name}"
                db.commit()

            # Get all documents to index (including PENDING ones)
            valid_docs = db.query(SourceFiles).filter(
                SourceFiles.id.in_(document_ids)
            ).all()

            found_ids = {doc.id for doc in valid_docs}
            if len(valid_docs) != len(document_ids):
                missing_ids = set(document_ids) - found_ids
                logger.warning(f"Skipping documents that were not found: {missing_ids}")

            if not valid_docs:
                raise ValueError("No valid documents found to index.")

            valid_doc_ids = [doc.id for doc in valid_docs]
            
            # Create the job record in our database
            job_id = str(uuid.uuid4())
            job_options = options or {}
            job_options['document_ids'] = valid_doc_ids
            
            job = IndexingJob(
                job_id=job_id,
                collection_id=collection_id,
                user_id=user_id,
                total_documents=len(valid_doc_ids),
                status='pending', # The job is pending until the background processor picks it up
                job_type=job_type,
                options=job_options
            )
            db.add(job)
            db.commit()
            
            # Publish a message to the Pub/Sub topic to trigger the background processor
            message_data = json.dumps({"job_id": job_id}).encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data)
            future.result() # Wait for the message to be published

            logger.info(f"Successfully created indexing job {job_id} and published to Pub/Sub topic '{PUBSUB_TOPIC_ID}'.")
            
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to start indexing job: {str(e)}", exc_info=True)
            raise

    def _sanitize_name(self, name: str) -> str:
        """Sanitize collection names for vector database."""
        # Convert to lowercase and replace spaces/special chars with underscores
        sanitized = re.sub(r'[^\w\-]', '_', name.lower())
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        if not sanitized:
            sanitized = 'collection'
        return sanitized

    async def get_job_status(self, job_id: str, db: Session) -> Optional[Dict]:
        """Get the current status of an indexing job directly from the database."""
        try:
            job = db.query(IndexingJob).filter_by(job_id=job_id).first()
            if not job:
                return None
            
            return {
                'job_id': job.job_id,
                'collection_id': job.collection_id,
                'status': job.status,
                'total_documents': job.total_documents,
                'processed_documents': job.processed_documents,
                'failed_documents': job.failed_documents,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'error_details': job.error_details
            }
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {str(e)}")
            return None

# Global instance for singleton pattern
_indexing_service_instance = None

def get_indexing_service() -> CollectionIndexingService:
    """Get singleton instance of the indexing service."""
    global _indexing_service_instance
    if _indexing_service_instance is None:
        _indexing_service_instance = CollectionIndexingService()
    return _indexing_service_instance