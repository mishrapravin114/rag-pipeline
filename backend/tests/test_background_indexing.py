"""
Integration tests for background indexing functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from api.services.collection_indexing_service import CollectionIndexingService
from api.services.background_task_handler import BackgroundTaskHandler
from database.database import Collection, SourceFiles, IndexingJob


@pytest.mark.asyncio
async def test_background_indexing_returns_immediately():
    """Test that indexing endpoint returns immediately after creating job."""
    
    # Create mock database session
    mock_db = Mock(spec=Session)
    
    # Create mock collection
    mock_collection = Mock(spec=Collection)
    mock_collection.id = 1
    mock_collection.name = "Test Collection"
    mock_collection.chromadb_collection_name = None
    
    # Create mock documents
    mock_docs = [Mock(spec=SourceFiles, id=i) for i in range(1, 11)]  # 10 documents
    
    # Mock database queries
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_collection
    mock_db.query.return_value.filter.return_value.all.return_value = mock_docs
    
    # Create service instances
    indexing_service = CollectionIndexingService()
    background_handler = BackgroundTaskHandler()
    
    # Track timing
    import time
    start_time = time.time()
    
    # Start indexing job
    with patch.object(indexing_service, '_create_indexing_job_record') as mock_create_job:
        mock_create_job.return_value = Mock(job_id="test-job-123")
        
        # This should return immediately
        job_id = await indexing_service.start_indexing_job(
            collection_id=1,
            document_ids=[doc.id for doc in mock_docs],
            job_type="index",
            user_id=1,
            db=mock_db
        )
        
        # Start background processing
        await background_handler.start_indexing_job_async(
            collection_id=1,
            document_ids=[doc.id for doc in mock_docs],
            job_type="index",
            user_id=1,
            initial_job_id=job_id
        )
    
    # Check that it returned quickly
    elapsed_time = time.time() - start_time
    
    # Should return in less than 100ms
    assert elapsed_time < 0.1, f"Indexing job took {elapsed_time:.3f}s to return, should be < 0.1s"
    assert job_id == "test-job-123"
    
    # Verify background task was created
    assert job_id in background_handler.active_tasks
    
    # Clean up
    background_handler.shutdown()


@pytest.mark.asyncio
async def test_job_cancellation_with_background_handler():
    """Test that jobs can be cancelled through the background handler."""
    
    # Create mock database session
    mock_db = Mock(spec=Session)
    
    # Create mock job
    mock_job = Mock(spec=IndexingJob)
    mock_job.job_id = "test-job-456"
    mock_job.status = "processing"
    
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_job
    
    # Create service instances
    indexing_service = CollectionIndexingService()
    background_handler = BackgroundTaskHandler()
    
    # Create a long-running task
    async def long_task():
        await asyncio.sleep(10)  # Won't complete
    
    task = asyncio.create_task(long_task())
    background_handler.active_tasks["test-job-456"] = task
    
    # Cancel the job
    result = await indexing_service.cancel_job("test-job-456", mock_db)
    
    # Verify cancellation
    assert result is True
    assert task.cancelled()
    assert "test-job-456" not in background_handler.active_tasks
    
    # Clean up
    background_handler.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])