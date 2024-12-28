"""
Background Task Handler for Collection Indexing
Handles async processing with proper database session management
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session, sessionmaker, scoped_session

from database.database import engine, SessionLocal
from api.services.collection_indexing_service import CollectionIndexingService

logger = logging.getLogger(__name__)


class BackgroundTaskHandler:
    """Handles background processing of indexing jobs with proper session management."""
    
    def __init__(self):
        """Initialize the background task handler."""
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="indexing_worker")
        self.active_tasks: Dict[str, asyncio.Task] = {}
        # Create a scoped session factory for thread-safe operations
        self.Session = scoped_session(sessionmaker(bind=engine))
        
    @contextmanager
    def get_thread_safe_session(self):
        """Create a thread-safe database session."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            # Remove session from registry to prevent cross-thread usage
            self.Session.remove()
    
    async def start_indexing_job_async(
        self,
        collection_id: int,
        document_ids: List[int],
        job_type: str = "index",
        options: Optional[Dict] = None,
        user_id: Optional[int] = None,
        initial_job_id: Optional[str] = None
    ) -> str:
        """
        Start indexing job in background without blocking the request.
        
        Args:
            collection_id: ID of the collection
            document_ids: List of document IDs to index
            job_type: Type of job - 'index', 'reindex', or 'remove'
            options: Additional options
            user_id: User ID
            initial_job_id: Pre-created job ID from the service
            
        Returns:
            Job ID
        """
        try:
            # Create async task for the background processing
            task = asyncio.create_task(
                self._run_indexing_in_background(
                    collection_id,
                    document_ids,
                    job_type,
                    options,
                    user_id,
                    initial_job_id
                )
            )
            
            # Store the task
            if initial_job_id:
                self.active_tasks[initial_job_id] = task
            
            # Don't await the task - let it run in background
            return initial_job_id
            
        except Exception as e:
            logger.error(f"Failed to start background indexing job: {str(e)}")
            raise
    
    async def _run_indexing_in_background(
        self,
        collection_id: int,
        document_ids: List[int],
        job_type: str,
        options: Optional[Dict],
        user_id: Optional[int],
        job_id: str
    ):
        """Run the indexing job in background with new database session."""
        try:
            # Get the indexing service instance
            from api.services.collection_indexing_service import get_indexing_service
            indexing_service = get_indexing_service()
            
            # Use thread-safe session for the entire job processing
            with self.get_thread_safe_session() as db:
                # Process the indexing job with the new session
                await indexing_service._process_indexing_job(
                    job_id,
                    collection_id,
                    document_ids,
                    job_type,
                    options,
                    db
                )
                
        except asyncio.CancelledError:
            logger.info(f"Background indexing job {job_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in background indexing job {job_id}: {str(e)}")
            # Update job status to failed
            try:
                with self.get_thread_safe_session() as db:
                    from database.database import IndexingJob
                    from datetime import datetime
                    
                    job = db.query(IndexingJob).filter_by(job_id=job_id).first()
                    if job:
                        job.status = 'failed'
                        job.completed_at = datetime.utcnow()
                        job.error_details = str(e)
                        db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update job status: {str(update_error)}")
        finally:
            # Clean up task reference
            if job_id in self.active_tasks:
                del self.active_tasks[job_id]
    
    def cancel_task(self, job_id: str) -> bool:
        """Cancel a running background task."""
        if job_id in self.active_tasks:
            task = self.active_tasks[job_id]
            task.cancel()
            return True
        return False
    
    def shutdown(self):
        """Shutdown the executor and cancel all tasks."""
        # Cancel all active tasks
        for task in self.active_tasks.values():
            task.cancel()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clean up session registry
        self.Session.remove()


# Global instance
_background_handler = None


def get_background_handler() -> BackgroundTaskHandler:
    """Get singleton instance of background handler."""
    global _background_handler
    if _background_handler is None:
        _background_handler = BackgroundTaskHandler()
    return _background_handler