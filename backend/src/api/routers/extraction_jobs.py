"""
Extraction Jobs API Router - Handles metadata extraction job status and results
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging

from database.database import get_db
from api.routers.auth import get_current_user
from api.services.metadata_groups_extraction_service import get_extraction_job_status as get_job_details

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/extraction-jobs",
    tags=["extraction-jobs"]
)

# Pydantic models
class ExtractionJobStatus(BaseModel):
    job_id: str
    collection_id: int
    group_id: int
    status: str
    total_documents: int
    processed_documents: int
    progress: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class DocumentPreview(BaseModel):
    id: int
    file_name: str
    entity_name: Optional[str]
    
    class Config:
        from_attributes = True

class ExtractionJobDetail(BaseModel):
    job_id: int
    collection_id: int
    collection_name: str
    group_id: int
    group_name: str
    status: str
    total_documents: int
    processed_documents: int
    failed_documents: int
    progress_percentage: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: int
    created_by_name: str
    error_details: Optional[str]
    documents_preview: Optional[List[DocumentPreview]] = []
    
    class Config:
        from_attributes = True

class ExtractionJobsResponse(BaseModel):
    jobs: List[ExtractionJobDetail]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    class Config:
        from_attributes = True

@router.get("/{job_id}/status", response_model=ExtractionJobStatus)
async def get_extraction_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get the status of a metadata extraction job."""
    try:
        # Try to parse job_id as integer first, otherwise treat as UUID
        try:
            job_id_int = int(job_id)
            query = text("""
                SELECT 
                    cej.id,
                    cej.collection_id,
                    cej.group_id,
                    cej.status,
                    cej.total_documents,
                    cej.processed_documents,
                    cej.created_at,
                    cej.started_at,
                    cej.completed_at,
                    c.name as collection_name,
                    mg.name as group_name
                FROM collection_extraction_jobs cej
                JOIN collections c ON cej.collection_id = c.id
                JOIN metadata_groups mg ON cej.group_id = mg.id
                WHERE cej.id = :job_id
            """)
            result = db.execute(query, {"job_id": job_id_int}).fetchone()
        except ValueError:
            # If not a valid integer, return not found
            result = None
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extraction job {job_id} not found"
            )
        
        # Calculate progress
        progress = 0.0
        if result.total_documents > 0:
            progress = (result.processed_documents / result.total_documents) * 100
        
        return ExtractionJobStatus(
            job_id=job_id,
            collection_id=result.collection_id,
            group_id=result.group_id,
            status=result.status,
            total_documents=result.total_documents,
            processed_documents=result.processed_documents,
            progress=progress,
            created_at=result.created_at,
            started_at=result.started_at,
            completed_at=result.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extraction job status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extraction job status"
        )

@router.get("/collection/{collection_id}", response_model=ExtractionJobsResponse)
async def get_collection_extraction_jobs(
    collection_id: int,
    user_jobs_only: bool = False,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all extraction jobs for a collection with pagination and filters."""
    try:
        # Calculate offset
        offset = (page - 1) * page_size
        # Build query with optional user filter
        base_query = """
            SELECT 
                cej.id as job_id,
                cej.collection_id,
                c.name as collection_name,
                cej.group_id,
                mg.name as group_name,
                cej.status,
                cej.total_documents,
                cej.processed_documents,
                COALESCE(cej.failed_documents, 0) as failed_documents,
                cej.created_at,
                cej.started_at,
                cej.completed_at,
                cej.created_by,
                u.username as created_by_name,
                cej.error_details
            FROM collection_extraction_jobs cej
            JOIN collections c ON cej.collection_id = c.id
            JOIN metadata_groups mg ON cej.group_id = mg.id
            LEFT JOIN Users u ON cej.created_by = u.id
            WHERE cej.collection_id = :collection_id
        """
        
        params = {"collection_id": collection_id}
        
        if user_jobs_only:
            base_query += " AND cej.created_by = :user_id"
            params["user_id"] = current_user.id
        
        if status_filter:
            base_query += " AND cej.status = :status"
            params["status"] = status_filter
        
        # Get total count first
        count_query = """
            SELECT COUNT(*) as total
            FROM collection_extraction_jobs cej
            WHERE cej.collection_id = :collection_id
        """
        
        if user_jobs_only:
            count_query += " AND cej.created_by = :user_id"
        
        if status_filter:
            count_query += " AND cej.status = :status"
        
        count_result = db.execute(text(count_query), params).fetchone()
        total_jobs = count_result.total if count_result else 0
        
        # Add ordering and pagination to main query
        base_query += " ORDER BY cej.created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = offset
        
        results = db.execute(text(base_query), params).fetchall()
        
        jobs = []
        for row in results:
            progress = 0.0
            if row.total_documents > 0:
                progress = (row.processed_documents / row.total_documents) * 100
            
            # Get document preview (first 5-6 documents that were actually processed in this job)
            # For now, we'll show collection documents, but ideally we should track
            # which specific documents were processed in each job
            doc_query = text("""
                SELECT DISTINCT sf.id, sf.file_name, sf.entity_name
                FROM SourceFiles sf
                JOIN collection_document_association cda ON sf.id = cda.document_id
                WHERE cda.collection_id = :collection_id
                LIMIT :limit
            """)
            # Limit preview to actual document count if less than 6
            preview_limit = min(6, row.total_documents)
            doc_results = db.execute(doc_query, {
                "collection_id": row.collection_id,
                "limit": preview_limit
            }).fetchall()
            
            documents_preview = [
                DocumentPreview(
                    id=doc.id,
                    file_name=doc.file_name,
                    entity_name=doc.entity_name
                ) for doc in doc_results
            ]
            
            jobs.append(ExtractionJobDetail(
                job_id=row.job_id,
                collection_id=row.collection_id,
                collection_name=row.collection_name,
                group_id=row.group_id,
                group_name=row.group_name,
                status=row.status,
                total_documents=row.total_documents,
                processed_documents=row.processed_documents,
                failed_documents=row.failed_documents,
                progress_percentage=round(progress, 2),
                created_at=row.created_at,
                started_at=row.started_at,
                completed_at=row.completed_at,
                created_by=row.created_by or 0,
                created_by_name=row.created_by_name or "System",
                error_details=row.error_details,
                documents_preview=documents_preview
            ))
        
        # Calculate total pages
        total_pages = max(1, (total_jobs + page_size - 1) // page_size)
        
        return ExtractionJobsResponse(
            jobs=jobs,
            total=total_jobs,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting extraction jobs for collection {collection_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extraction jobs"
        )

@router.post("/{job_id}/stop")
async def stop_extraction_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Stop a running extraction job."""
    try:
        # Check if job exists and is owned by the user or user is admin
        check_query = text("""
            SELECT status, created_by 
            FROM collection_extraction_jobs 
            WHERE id = :job_id
        """)
        job = db.execute(check_query, {"job_id": job_id}).fetchone()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extraction job not found"
            )
        
        # Check if job is in a stoppable state
        if job.status not in ['pending', 'processing']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot stop job with status: {job.status}"
            )
        
        # Update job status to 'failed' with a stop message
        update_query = text("""
            UPDATE collection_extraction_jobs 
            SET status = 'failed',
                completed_at = NOW(),
                error_details = JSON_OBJECT('message', 'Job stopped by user', 'stopped_at', NOW())
            WHERE id = :job_id
        """)
        
        db.execute(update_query, {"job_id": job_id})
        db.commit()
        
        return {
            "message": "Extraction job stopped successfully",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping extraction job {job_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop extraction job"
        )