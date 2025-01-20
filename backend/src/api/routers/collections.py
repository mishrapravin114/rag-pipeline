"""
Collections API Router - Handles CRUD operations for document collections
"""

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, text
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import asyncio
import os
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
import uuid

from ...database.database import get_db, Collection, SourceFiles, IndexingJob, collection_document_association
from api.routers.auth import get_current_user
from api.services.collection_indexing_service import get_indexing_service
from api.services.websocket_manager import get_connection_manager, ConnectionManager, MessageType
from api.services.background_task_handler import get_background_handler

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/collections",
    tags=["collections"]
)

# Pydantic models for request/response
class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class CollectionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    indexed_count: int = 0
    pending_count: int = 0
    stored_count: int = 0
    failed_count: int = 0
    indexing_status: Optional[str] = 'idle'
    active_job_id: Optional[str] = None
    active_job_progress: Optional[float] = None
    
    class Config:
        from_attributes = True

class CollectionDetailResponse(CollectionResponse):
    documents: List[dict] = []
    total_documents: int = 0
    current_page: int = 1
    page_size: int = 50
    total_pages: int = 1

class DocumentAssociation(BaseModel):
    document_ids: List[int]

class BulkUploadItem(BaseModel):
    file_name: str
    file_url: str
    entity_name: Optional[str] = None
    comments: Optional[str] = None
    us_ma_date: Optional[str] = None

class BulkUploadRequest(BaseModel):
    items: List[BulkUploadItem]

# New models for indexing functionality
class IndexDocumentsRequest(BaseModel):
    document_ids: Optional[List[int]] = None
    reindex_from_default: bool = False
    remove_from_default: bool = False

class ReindexDocumentsRequest(BaseModel):
    document_ids: List[int]
    remove_from_default: bool = False

class IndexingJobResponse(BaseModel):
    job_id: str
    collection_id: int
    total_documents: int
    message: str

class IndexingStatusResponse(BaseModel):
    job_id: str
    collection_id: int
    status: str
    total_documents: int
    processed_documents: int
    failed_documents: int
    current_document: Optional[str]
    documents: List[Dict]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_details: Optional[List[Dict]]
    progress_percentage: Optional[float] = 0


# CRUD Endpoints
@router.post("/", response_model=CollectionResponse)
async def create_collection(
    collection: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new collection"""
    # Check if collection with same name exists
    existing = db.query(Collection).filter(Collection.name == collection.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collection with name '{collection.name}' already exists"
        )
    
    # Create new collection
    db_collection = Collection(
        name=collection.name,
        description=collection.description
    )
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    
    response = CollectionResponse(
        id=db_collection.id,
        name=db_collection.name,
        description=db_collection.description,
        created_at=db_collection.created_at,
        updated_at=db_collection.updated_at,
        document_count=0,
        indexed_count=0,
        pending_count=0,
        stored_count=0,
        failed_count=0,
        indexing_status='idle'
    )
    return response

@router.get("/", response_model=List[CollectionResponse])
async def list_collections(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all collections"""
    collections = db.query(Collection).options(
        joinedload(Collection.documents)
    ).offset(skip).limit(limit).all()
    
    response = []
    for collection in collections:
        # Calculate document status counts from collection_association table
        indexed_count = 0
        pending_count = 0
        stored_count = 0
        failed_count = 0
        indexing_status = 'idle'
        
        # Query the association table for status counts
        association_records = db.execute(
            collection_document_association.select().where(
                collection_document_association.c.collection_id == collection.id
            )
        ).fetchall()
        
        for assoc in association_records:
            if assoc.indexing_status == 'indexed':
                indexed_count += 1
            elif assoc.indexing_status == 'pending':
                pending_count += 1
            elif assoc.indexing_status == 'failed':
                failed_count += 1
            else:
                # Default status or other statuses count as stored
                stored_count += 1
        
        # Check if there's an active indexing job for this collection
        active_job = db.query(IndexingJob).filter(
            IndexingJob.collection_id == collection.id,
            IndexingJob.status.in_(['pending', 'processing'])
        ).order_by(IndexingJob.created_at.desc()).first()
        
        active_job_id = None
        active_job_progress = None
        
        if active_job:
            logger.info(f"Found active job for collection {collection.id}: {active_job.job_id}, status: {active_job.status}")
            indexing_status = active_job.status
            active_job_id = active_job.job_id
            
            # Get indexing service for real-time progress
            indexing_service = get_indexing_service()
            job_status = await indexing_service.get_job_status(active_job.job_id, db)
            
            # Calculate progress
            if active_job.total_documents > 0:
                processed = job_status.get('processed_documents', active_job.processed_documents) if job_status else active_job.processed_documents
                active_job_progress = round((processed / active_job.total_documents) * 100, 2)
            else:
                active_job_progress = 0
        elif indexed_count == len(collection.documents) and len(collection.documents) > 0:
            indexing_status = 'completed'
        
        collection_resp = CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            document_count=len(collection.documents),
            indexed_count=indexed_count,
            pending_count=pending_count,
            stored_count=stored_count,
            failed_count=failed_count,
            indexing_status=indexing_status,
            active_job_id=active_job_id,
            active_job_progress=active_job_progress
        )
        
        if active_job_id:
            logger.info(f"Added active job info to collection {collection.id}: job_id={active_job_id}, progress={active_job_progress}")
        
        response.append(collection_resp)
    
    return response

@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search term for filtering documents"),
    status_filter: Optional[str] = Query(None, description="Filter by collection status")
):
    """Get a specific collection with its documents with pagination"""
    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(Collection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    # Get association records for accurate status counts
    association_map = {}
    association_records = db.execute(
        collection_document_association.select().where(
            collection_document_association.c.collection_id == collection.id
        )
    ).fetchall()
    
    indexed_count = 0
    pending_count = 0
    stored_count = 0
    failed_count = 0
    
    for assoc in association_records:
        association_map[assoc.document_id] = {
            'status': assoc.indexing_status,
            'error_message': assoc.error_message
        }
        if assoc.indexing_status == 'indexed':
            indexed_count += 1
        elif assoc.indexing_status == 'pending':
            pending_count += 1
        elif assoc.indexing_status == 'failed':
            failed_count += 1
        else:
            stored_count += 1
    
    # Filter documents based on search and status
    filtered_documents = []
    for doc in collection.documents:
        # Get collection-specific status from association table
        assoc_data = association_map.get(doc.id, None)
        assoc_status = assoc_data['status'] if assoc_data else None
        
        # Determine collection-specific status
        if assoc_status == 'indexed':
            collection_status = "INDEXED"
        elif assoc_status == 'pending':
            collection_status = "PENDING"
        elif assoc_status == 'failed':
            collection_status = "FAILED"
        else:
            collection_status = "NOT_INDEXED"
        
        # Apply status filter
        if status_filter:
            if status_filter == 'indexed' and collection_status != 'INDEXED':
                continue
            elif status_filter == 'failed' and collection_status != 'FAILED':
                continue
            elif status_filter == 'pending' and collection_status != 'PENDING':
                continue
            elif status_filter == 'not_indexed' and collection_status != 'NOT_INDEXED':
                continue
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            if not (search_lower in doc.file_name.lower() or 
                    (doc.entity_name and search_lower in doc.entity_name.lower())):
                continue
        
        filtered_documents.append(doc)
    
    # Calculate pagination
    total_documents = len(filtered_documents)
    total_pages = (total_documents + page_size - 1) // page_size
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    # Get paginated documents
    paginated_documents = filtered_documents[start_index:end_index]
    
    # Format documents for response
    documents = []
    for doc in paginated_documents:
        # Get collection-specific status from association table
        assoc_data = association_map.get(doc.id, None)
        assoc_status = assoc_data['status'] if assoc_data else None
        error_message = assoc_data.get('error_message', None) if assoc_data else None
        
        # Determine collection-specific status
        if assoc_status == 'indexed':
            collection_status = "INDEXED"
        elif assoc_status == 'pending':
            collection_status = "PENDING"
        elif assoc_status == 'failed':
            collection_status = "FAILED"
        else:
            collection_status = "NOT_INDEXED"
        
        # Check vector_db_collections for backward compatibility
        vector_db_collections = doc.vector_db_collections or []
        is_indexed_in_collection = assoc_status == 'indexed'
        
        documents.append({
            "id": doc.id,
            "file_name": doc.file_name,
            "file_url": doc.file_url,
            "entity_name": doc.entity_name,
            "status": doc.status,  # Global document status
            "collection_status": collection_status,  # Status within this collection
            "error_message": error_message,  # Error message if failed
            "is_indexed_in_collection": is_indexed_in_collection,
            "indexed_collections": [c.get('collection_name', f"collection_{c.get('collection_id')}") for c in vector_db_collections],
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "us_ma_date": doc.us_ma_date  # Add US MA date
        })
    
    return CollectionDetailResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=len(collection.documents),
        indexed_count=indexed_count,
        pending_count=pending_count,
        stored_count=stored_count,
        failed_count=failed_count,
        documents=documents,
        total_documents=total_documents,
        current_page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    collection_update: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a collection"""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    # Update fields if provided
    if collection_update.name is not None:
        # Check if new name already exists
        existing = db.query(Collection).filter(
            Collection.name == collection_update.name,
            Collection.id != collection_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Collection with name '{collection_update.name}' already exists"
            )
        collection.name = collection_update.name
    
    if collection_update.description is not None:
        collection.description = collection_update.description
    
    db.commit()
    db.refresh(collection)
    
    # Get document count
    document_count = len(collection.documents)
    
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=document_count
    )

@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: int,
    delete_source_files: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a collection.
    
    Args:
        collection_id: ID of the collection to delete
        delete_source_files: If True, also delete the source files (default: False)
    """
    # Get collection with documents
    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(Collection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    collection_name = collection.name
    documents_to_delete = list(collection.documents) if delete_source_files else []
    
    try:
        # 1. Delete Qdrant collection for this specific collection
        from ...utils.qdrant_util import QdrantUtil
        qdrant_util = QdrantUtil()
        
        # Delete the collection-specific Qdrant collection
        collection_vector_db_name = f"collection_{collection_id}"
        if qdrant_util.collection_exists(collection_vector_db_name):
            qdrant_util.delete_collection(collection_vector_db_name)
            logger.info(f"Deleted Qdrant collection: {collection_vector_db_name}")
        
        # 2. Delete source files if requested
        if delete_source_files:
            deleted_files = []
            if documents_to_delete:
                import os
                for doc in documents_to_delete:
                    try:
                        # Delete file from filesystem
                        if doc.file_url and os.path.exists(doc.file_url):
                            os.remove(doc.file_url)
                            deleted_files.append(doc.file_name)
                        
                        # Also delete from default vector database collection
                        qdrant_util.delete_documents_by_source_file(
                            source_file_name=doc.file_name,
                            collection_name="fda_documents"
                        )
                        
                        # Delete the document record
                        db.delete(doc)
                    except Exception as e:
                        logger.error(f"Error deleting file {doc.file_name}: {str(e)}")
                
                logger.info(f"Deleted {len(deleted_files)} source files: {deleted_files}")
        
        # 3. Update document status if not deleting source files
        status_updated_count = 0
        if not delete_source_files:
            # For each document in this collection, check if it's in any other collection
            for doc in collection.documents:
                # Check if document is in any other collections
                remaining_collections = db.query(Collection).join(
                    Collection.documents
                ).filter(
                    SourceFiles.id == doc.id,
                    Collection.id != collection_id
                ).count()
                
                # If document is not in any other collection and was READY, 
                # change status to DOCUMENT_STORED
                if remaining_collections == 0 and doc.status == 'READY':
                    doc.status = 'DOCUMENT_STORED'
                    status_updated_count += 1
                    logger.info(f"Changed status of {doc.file_name} to DOCUMENT_STORED as it will no longer be in any collection")
        
        # 4. Delete any active indexing jobs for this collection
        active_jobs = db.query(IndexingJob).filter(
            IndexingJob.collection_id == collection_id,
            IndexingJob.status.in_(['pending', 'processing'])
        ).all()
        
        for job in active_jobs:
            job.status = 'cancelled'
            job.completed_at = datetime.utcnow()
        
        # 5. Delete the collection (this will cascade delete associations)
        db.delete(collection)
        db.commit()
        
        return {
            "message": f"Collection '{collection_name}' deleted successfully",
            "deleted_source_files": len(deleted_files) if delete_source_files else 0,
            "vector_db_cleaned": True,
            "status_updated": status_updated_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete collection: {str(e)}"
        )

# Document association endpoints
@router.post("/{collection_id}/documents")
async def add_documents_to_collection(
    collection_id: int,
    document_association: DocumentAssociation,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Add documents to a collection"""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    # Get documents
    documents = db.query(SourceFiles).filter(
        SourceFiles.id.in_(document_association.document_ids)
    ).all()
    
    if len(documents) != len(document_association.document_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more documents not found"
        )
    
    # Add documents to collection
    documents_added = 0
    for doc in documents:
        if doc not in collection.documents:
            collection.documents.append(doc)
            documents_added += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Added {documents_added} documents to collection '{collection.name}'",
        "documents_added": documents_added,
        "total_documents": len(collection.documents)
    }

@router.post("/{collection_id}/bulk-upload")
async def bulk_upload_to_collection(
    collection_id: int,
    request: BulkUploadRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk upload documents directly to a collection"""
    from datetime import datetime
    
    # Verify collection exists
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    success_items = []
    failed_items = []
    
    for idx, item in enumerate(request.items):
        try:
            # Validate required fields
            if not item.file_name or not item.file_url:
                failed_items.append({
                    "row": idx + 1,
                    "item": item.dict(),
                    "error": "Missing required fields: file_name and file_url"
                })
                continue
            
            # Check if file already exists
            existing_file = db.query(SourceFiles).filter(
                SourceFiles.file_name == item.file_name
            ).first()
            
            if existing_file:
                # Check if already in this collection
                if existing_file in collection.documents:
                    failed_items.append({
                        "row": idx + 1,
                        "item": item.dict(),
                        "error": f"File '{item.file_name}' already exists in this collection"
                    })
                else:
                    # Add existing file to collection
                    collection.documents.append(existing_file)
                    
                    # Add association record with initial status
                    db.execute(
                        collection_document_association.update().where(
                            (collection_document_association.c.collection_id == collection_id) &
                            (collection_document_association.c.document_id == existing_file.id)
                        ).values(
                            indexing_status='pending',
                            indexed_at=None,
                            error_message=None
                        )
                    )
                    
                    success_items.append({
                        "row": idx + 1,
                        "id": existing_file.id,
                        "file_name": existing_file.file_name,
                        "entity_name": existing_file.entity_name,
                        "note": "Existing file added to collection"
                    })
                continue
            
            # Create new source file
            new_file = SourceFiles(
                file_name=item.file_name,
                file_url=item.file_url,
                entity_name=item.entity_name,
                comments=item.comments,
                us_ma_date=item.us_ma_date,
                status="PENDING",
                created_by=current_user.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(new_file)
            db.flush()  # Flush to get the ID
            
            # Add to collection
            collection.documents.append(new_file)
            
            # Add association record with initial status
            db.execute(
                collection_document_association.update().where(
                    (collection_document_association.c.collection_id == collection_id) &
                    (collection_document_association.c.document_id == new_file.id)
                ).values(
                    indexing_status='pending',
                    indexed_at=None,
                    error_message=None
                )
            )
            
            success_items.append({
                "row": idx + 1,
                "id": new_file.id,
                "file_name": new_file.file_name,
                "entity_name": new_file.entity_name
            })
            
        except Exception as e:
            failed_items.append({
                "row": idx + 1,
                "item": item.dict(),
                "error": str(e)
            })
    
    # Commit all successful items
    if success_items:
        db.commit()
    else:
        db.rollback()
    
    logger.info(f"Bulk upload to collection {collection_id} by {current_user.username}: {len(success_items)} success, {len(failed_items)} failed")
    
    return {
        "success": True,
        "total_items": len(request.items),
        "successful_items": len(success_items),
        "failed_items": len(failed_items),
        "success_details": success_items,
        "failure_details": failed_items
    }

@router.delete("/{collection_id}/documents")
async def remove_documents_from_collection(
    collection_id: int,
    document_association: DocumentAssociation,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove documents from a collection"""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with id {collection_id} not found"
        )
    
    # Get documents
    documents = db.query(SourceFiles).filter(
        SourceFiles.id.in_(document_association.document_ids)
    ).all()
    
    try:
        # Remove vectors from collection-specific Qdrant
        from ...utils.qdrant_util import QdrantUtil
        qdrant_util = QdrantUtil.get_instance(use_persistent_client=True)
        
        # Check if collection has a vector database collection name
        if collection.vector_db_collection_name:
            collection_vector_db_name = collection.vector_db_collection_name
        else:
            collection_vector_db_name = f"collection_{collection_id}_{qdrant_util.sanitize_collection_name(collection.name)}"
        
        # Try to get the collection - if it exists, remove documents
        vector_db_collection = qdrant_util.get_or_create_collection(collection_vector_db_name)
        if vector_db_collection:
            for doc in documents:
                # Delete all chunks for this document from the collection
                # Generate all possible chunk IDs for this document
                chunk_ids = []
                for i in range(1000):  # Support up to 1000 chunks per document
                    chunk_ids.append(f"collection_{collection_id}_doc_{doc.id}_chunk_{i}")
                
                try:
                    vector_db_collection.delete(ids=chunk_ids)
                    logger.info(f"Removed vectors for document {doc.id} ({doc.file_name}) from {collection_vector_db_name}")
                except Exception as e:
                    # Ignore errors for non-existent IDs
                    logger.debug(f"No vectors found or error deleting for document {doc.id}: {str(e)}")
                    pass
        
        # Remove documents from collection association
        removed_count = 0
        status_updated_count = 0
        
        for doc in documents:
            if doc in collection.documents:
                collection.documents.remove(doc)
                removed_count += 1
                
                # Check if document is still in any other collections
                remaining_collections = db.query(Collection).join(
                    Collection.documents
                ).filter(
                    SourceFiles.id == doc.id,
                    Collection.id != collection_id
                ).count()
                
                # Update the document's vector_db_collections field
                if doc.vector_db_collections:
                    # Remove this collection from the vector_db_collections list
                    doc.vector_db_collections = [
                        c for c in doc.vector_db_collections 
                        if c.get('collection_id') != collection_id
                    ]
                    logger.info(f"Updated vector_db_collections for {doc.file_name}")
                
                # If document is not in any other collection and was READY, 
                # change status to DOCUMENT_STORED
                if remaining_collections == 0 and doc.status == 'READY':
                    doc.status = 'DOCUMENT_STORED'
                    status_updated_count += 1
                    logger.info(f"Changed status of {doc.file_name} to DOCUMENT_STORED as it's no longer in any collection")
        
        db.commit()
        
        return {
            "message": f"Removed {removed_count} documents from collection '{collection.name}'",
            "document_count": len(collection.documents),
            "vectors_cleaned": True,
            "status_updated": status_updated_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing documents from collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove documents: {str(e)}"
        )

# Collection Indexing Endpoints
@router.post("/{collection_id}/index", response_model=IndexingJobResponse)
async def index_documents(
    collection_id: int,
    request: IndexDocumentsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Start indexing selected documents in the collection.
    All document processing is handled by the background processor.
    """
    try:
        logger.info(f"Index documents request for collection {collection_id}: document_ids={request.document_ids}")
        
        collection = db.query(Collection).options(
            joinedload(Collection.documents)
        ).filter(Collection.id == collection_id).first()
        
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Collection with id {collection_id} not found")

        # Determine which documents to work with
        if request.document_ids:
            target_docs = [doc for doc in collection.documents if doc.id in request.document_ids]
        else:
            target_docs = collection.documents

        if not target_docs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents found for indexing.")

        # Get all document IDs (including PENDING ones)
        valid_doc_ids = [doc.id for doc in target_docs]
        
        # Count different document states for informational purposes
        pending_count = sum(1 for doc in target_docs if doc.status == 'PENDING')
        ready_count = len(target_docs) - pending_count
        
        logger.info(f"Submitting {len(valid_doc_ids)} documents for indexing (PENDING: {pending_count}, READY: {ready_count})")
        
        # Start the indexing job - the processor will handle PENDING documents
        indexing_service = get_indexing_service()
        job_type = "reindex" if request.reindex_from_default else "index"
        
        job_options = {
            "remove_from_default": request.remove_from_default,
            "document_ids": valid_doc_ids
        }
        
        job_id = await indexing_service.start_indexing_job(
            collection_id=collection_id,
            document_ids=valid_doc_ids,
            job_type=job_type,
            options=job_options,
            user_id=current_user.id,
            db=db
        )
        
        # Update collection status to indicate indexing is in progress
        collection.indexing_status = 'in_progress'
        db.commit()
        
        message = f"Started indexing job for {len(valid_doc_ids)} documents."
        if pending_count > 0:
            message += f" {pending_count} documents will be processed before indexing."
        
        return IndexingJobResponse(
            job_id=job_id,
            collection_id=collection_id,
            total_documents=len(valid_doc_ids),
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting indexing job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start indexing job: {str(e)}"
        )

@router.get("/{collection_id}/indexing-status", response_model=Optional[IndexingStatusResponse])
async def get_indexing_status(
    collection_id: int,
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get indexing status for collection or specific job.
    
    If job_id is provided, returns status for that specific job.
    Otherwise, returns the most recent job status for the collection.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        indexing_service = get_indexing_service()
        
        if job_id:
            # Get specific job status
            job_status = await indexing_service.get_job_status(job_id, db)
            if not job_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job with id {job_id} not found"
                )
            return IndexingStatusResponse(**job_status)
        else:
            # Get most recent job for collection
            recent_job = db.query(IndexingJob).filter(
                IndexingJob.collection_id == collection_id
            ).order_by(IndexingJob.created_at.desc()).first()
            
            if not recent_job:
                return None
            
            job_status = await indexing_service.get_job_status(recent_job.job_id, db)
            if job_status:
                return IndexingStatusResponse(**job_status)
            return None
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting indexing status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get indexing status: {str(e)}"
        )

@router.get("/{collection_id}/indexing-status/{job_id}", response_model=IndexingStatusResponse)
async def get_indexing_job_status(
    collection_id: int,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the status of a specific indexing job.
    
    Returns detailed status information including progress percentage.
    """
    try:
        # Validate collection exists and user has access
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Get the specific job by job_id and collection_id
        job = db.query(IndexingJob).filter(
            IndexingJob.job_id == job_id,
            IndexingJob.collection_id == collection_id
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Indexing job with id {job_id} not found for collection {collection_id}"
            )
        
        # Get current document being processed (if any)
        current_document = None
        if job.status == 'processing' and job.options:
            current_doc_id = job.options.get('current_document_id')
            if current_doc_id:
                current_doc = db.query(SourceFiles).filter(SourceFiles.id == current_doc_id).first()
                if current_doc:
                    current_document = current_doc.file_name
        
        # Calculate progress percentage
        progress_percentage = 0
        if job.total_documents > 0:
            progress_percentage = round((job.processed_documents / job.total_documents) * 100, 2)
        
        # Get document details if available
        documents = []
        if job.options and 'document_ids' in job.options:
            doc_ids = job.options.get('document_ids', [])
            docs = db.query(SourceFiles).filter(SourceFiles.id.in_(doc_ids)).all()
            documents = [
                {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "status": "processed" if job.processed_documents > 0 else "pending"
                }
                for doc in docs
            ]
        
        return IndexingStatusResponse(
            job_id=job.job_id,
            collection_id=job.collection_id,
            status=job.status,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            failed_documents=job.failed_documents,
            current_document=current_document,
            documents=documents,
            created_at=job.created_at.isoformat() if job.created_at else None,
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error_details=job.error_details if job.error_details else None,
            progress_percentage=progress_percentage  # Additional field for convenience
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting indexing job status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get indexing job status: {str(e)}"
        )

@router.get("/{collection_id}/entity-names")
async def get_collection_entitie_names(
    collection_id: int,
    search: Optional[str] = Query(None, description="Search term for filtering entity names"),
    limit: int = Query(200, ge=1, le=1000, description="Number of entity names to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    include_counts: bool = Query(True, description="Include document counts for each entity"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get unique entity names from a collection with optional search and pagination.
    
    This endpoint is optimized for large collections and returns entity names
    efficiently without loading all document details.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Base query for documents in the collection that are indexed
        base_query = db.query(SourceFiles).join(
            SourceFiles.collections
        ).join(
            collection_document_association,
            (collection_document_association.c.collection_id == collection_id) &
            (collection_document_association.c.document_id == SourceFiles.id)
        ).filter(
            Collection.id == collection_id,
            collection_document_association.c.indexing_status == 'indexed'
        )
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            base_query = base_query.filter(
                or_(
                    SourceFiles.entity_name.ilike(f"%{search_lower}%"),
                    SourceFiles.file_name.ilike(f"%{search_lower}%")
                )
            )
        
        # Get all documents to extract unique entity names
        all_documents = base_query.all()
        
        # Extract unique entity names with their document counts
        entitie_map = {}
        for doc in all_documents:
            entity_name = doc.entity_name or doc.file_name
            if entity_name not in entitie_map:
                entitie_map[entity_name] = {
                    "name": entity_name,
                    "document_count": 0,
                    "document_ids": [],
                    "documents": []
                }
            entitie_map[entity_name]["document_count"] += 1
            entitie_map[entity_name]["document_ids"].append(doc.id)
            entitie_map[entity_name]["documents"].append({
                "id": doc.id,
                "file_name": doc.file_name
            })
        
        # Convert to sorted list
        entitie_list = list(entitie_map.values())
        entitie_list.sort(key=lambda x: x["name"].lower())
        
        # Calculate total count before pagination
        total_count = len(entitie_list)
        
        # Apply pagination
        paginated_entities = entitie_list[offset:offset + limit]
        
        # Format response based on include_counts flag
        if include_counts:
            entity_names = [
                {
                    "entity_name": entity["name"],
                    "document_count": entity["document_count"],
                    "document_ids": entity["document_ids"],
                    "documents": entity["documents"]
                }
                for entity in paginated_entities
            ]
        else:
            entity_names = [entity["name"] for entity in paginated_entities]
        
        return {
            "collection_id": collection_id,
            "collection_name": collection.name,
            "entity_names": entity_names,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
            "search_term": search
        }
        
    except Exception as e:
        logger.error(f"Error getting collection entity names: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity names: {str(e)}"
        )

@router.get("/{collection_id}/vector-details")
async def get_collection_vector_details(
    collection_id: int,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get vector database details for a collection including document count and chunk statistics.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        logger.info(f"Getting vector details for collection: {collection.name} ({collection_id})")
        # Get vector database collection name
        collection_name = collection.vector_db_collection_name
        if not collection_name:
            from ...utils.qdrant_util import QdrantUtil
            qdrant_util = QdrantUtil.get_instance()
            collection_name = f"collection_{collection_id}_{qdrant_util.sanitize_collection_name(collection.name)}"
        
        logger.info(f"Querying Qdrant collection: {collection_name}")
        
        # Get Qdrant util instance
        from ...utils.qdrant_util import QdrantUtil
        qdrant_util = QdrantUtil.get_instance()
        
        # Get collection stats from Qdrant
        try:
            vector_db_collection_name = qdrant_util.get_or_create_collection(collection_name)
            
            # Get total count using Qdrant client
            count_result = qdrant_util.client.count(collection_name=collection_name)
            total_vectors = count_result.count
            logger.info(f"Total vectors in collection '{collection_name}': {total_vectors}")
            
            # Get ALL vectors to extract complete document information
            if total_vectors > 0:
                # Get all vectors metadata using Qdrant client
                scroll_result = qdrant_util.client.scroll(
                    collection_name=collection_name,
                    limit=total_vectors,
                    with_payload=True
                )
                all_results = scroll_result[0]  # First element contains the points
                
                # Extract unique documents with their details
                documents_map = {}  # key: doc_id, value: {file_name, chunk_count}
                
                for point in all_results:
                    if point and point.payload:
                        # Check for different payload structures (ChromaDB migration vs Agno format)
                        if 'meta_data' in point.payload:
                            # Agno format
                            metadata = point.payload.get('meta_data', {})
                            doc_id = metadata.get("source_file_id")
                            file_name = metadata.get("file_name") or point.payload.get('name')
                        else:
                            # Direct metadata format
                            metadata = point.payload
                            doc_id = metadata.get("source_file_id")
                            file_name = metadata.get("file_name")
                        
                        if doc_id:
                            if doc_id not in documents_map:
                                documents_map[doc_id] = {
                                    "file_name": file_name or f"Unknown (ID: {doc_id})",
                                    "chunk_count": 0,
                                    "entity_name": metadata.get("entity_name", "")
                                }
                            documents_map[doc_id]["chunk_count"] += 1
                
                # Convert to sorted list
                all_documents = [
                    {
                        "document_id": doc_id,
                        "file_name": doc_info["file_name"],
                        "entity_name": doc_info["entity_name"],
                        "chunk_count": doc_info["chunk_count"]
                    }
                    for doc_id, doc_info in sorted(documents_map.items(), key=lambda x: x[1]["file_name"])
                ]
                
                # Calculate statistics
                unique_doc_count = len(documents_map)
                avg_chunks_per_doc = sum(d["chunk_count"] for d in documents_map.values()) / unique_doc_count if unique_doc_count > 0 else 0
                
                # Paginate results
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                paginated_documents = all_documents[start_idx:end_idx]
                total_pages = (len(all_documents) + page_size - 1) // page_size
            else:
                unique_doc_count = 0
                avg_chunks_per_doc = 0
                all_documents = []
                paginated_documents = []
                total_pages = 0
            
            # Get document count from database for comparison
            db_doc_count = db.query(SourceFiles).join(
                SourceFiles.collections
            ).filter(
                Collection.id == collection_id
            ).count()
            
            return {
                "collection_id": collection_id,
                "collection_name": collection.name,
                "vector_db_collection_name": collection_name,
                "vector_stats": {
                    "total_vectors": total_vectors,
                    "unique_documents": unique_doc_count,
                    "average_chunks_per_document": round(avg_chunks_per_doc, 2)
                },
                "documents": {
                    "items": paginated_documents,
                    "total": len(all_documents),
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                },
                "database_stats": {
                    "documents_in_collection": db_doc_count,
                    "synced": db_doc_count == unique_doc_count
                },
                "status": "active" if total_vectors > 0 else "empty"
            }
            
        except Exception as e:
            logger.error(f"Error getting Qdrant stats: {str(e)}")
            return {
                "collection_id": collection_id,
                "collection_name": collection.name,
                "vector_db_collection_name": collection_name,
                "error": f"Failed to retrieve vector database stats: {str(e)}",
                "database_stats": {
                    "documents_in_collection": db.query(SourceFiles).join(
                        SourceFiles.collections
                    ).filter(Collection.id == collection_id).count()
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting collection vector details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vector details: {str(e)}"
        )

@router.post("/{collection_id}/reindex", response_model=IndexingJobResponse)
async def reindex_documents(
    collection_id: int,
    request: ReindexDocumentsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Reindex documents from default collection to this collection.
    
    This endpoint copies existing vectors from the default collection
    to avoid re-processing documents.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Validate documents - only accept documents with status DOCUMENT_STORED
        documents = db.query(SourceFiles).filter(
            SourceFiles.id.in_(request.document_ids),
            SourceFiles.status == 'DOCUMENT_STORED'
        ).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid documents found for reindexing"
            )
        
        valid_doc_ids = [doc.id for doc in documents]
        
        # Get indexing service
        indexing_service = get_indexing_service()
        
        # Create the job record with document IDs in options
        job_options = {
            "remove_from_default": request.remove_from_default,
            "document_ids": valid_doc_ids  # Store document IDs for the job processor
        }
        
        job_id = await indexing_service.start_indexing_job(
            collection_id=collection_id,
            document_ids=valid_doc_ids,
            job_type="reindex",
            options=job_options,
            user_id=current_user.id,
            db=db
        )
        
        # Job will be processed by the separate job processor
        # No need to start background task here
        
        return IndexingJobResponse(
            job_id=job_id,
            collection_id=collection_id,
            total_documents=len(valid_doc_ids),
            message=f"Started reindexing {len(valid_doc_ids)} documents from default collection"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting reindex job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start reindexing job: {str(e)}"
        )

@router.get("/websocket/health")
async def get_websocket_health(
    current_user: dict = Depends(get_current_user)
):
    """
    Get WebSocket connection health statistics.
    
    Returns information about active connections, channels, and health status.
    """
    connection_manager = get_connection_manager()
    health_stats = await connection_manager.health_check()
    
    return {
        "status": "healthy" if health_stats["healthy_connections"] > 0 else "degraded",
        "statistics": health_stats,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.delete("/{collection_id}/documents/{document_id}/index")
async def remove_document_from_index(
    collection_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a document from the collection's vector index.
    
    This removes the document's vectors from Qdrant but keeps
    the document association in the database.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Validate document exists and is in collection
        document = db.query(SourceFiles).join(
            collection.documents
        ).filter(
            SourceFiles.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with id {document_id} not found in collection"
            )
        
        # Get indexing service
        indexing_service = get_indexing_service()
        
        # Create removal job with document ID in options
        job_options = {
            "document_ids": [document_id]  # Store document ID for the job processor
        }
        
        job_id = await indexing_service.start_indexing_job(
            collection_id=collection_id,
            document_ids=[document_id],
            job_type="remove",
            options=job_options,
            user_id=current_user.id,
            db=db
        )
        
        # Job will be processed by the separate job processor
        # No need to start background task here
        
        return {
            "message": f"Started removing document '{document.file_name}' from collection index",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing document from index: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove document from index: {str(e)}"
        )


@router.websocket("/indexing-updates")
async def indexing_updates_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time indexing updates across all collections.
    
    This endpoint allows clients to receive updates for all active indexing jobs
    without specifying a particular collection or job ID.
    
    Note: This endpoint requires authentication via access token in the WebSocket URL
    or headers, but FastAPI WebSockets don't support dependency injection for auth.
    """
    connection_manager = get_connection_manager()
    
    try:
        # Simple authentication check - in production, implement proper WebSocket auth
        # For now, we'll accept all connections since they're coming from authenticated frontend
        
        # Register connection with a general channel for all indexing updates
        # The connection manager will handle accepting the WebSocket
        connected = await connection_manager.connect(
            websocket=websocket,
            channel_id="all_indexing_updates",
            metadata={"type": "general_updates"}
        )
        
        if not connected:
            await websocket.close(code=1011, reason="Failed to establish connection")
            return
        
        # Send initial connection success message
        await connection_manager.send_to_websocket(websocket, {
            "type": "connected",
            "message": "Connected to indexing updates"
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message from client (like ping/pong)
                data = await websocket.receive_text()
                
                # Handle client messages (e.g., ping/pong)
                await connection_manager.handle_client_message(websocket, data)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected for indexing updates")
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid message format",
                    "details": {"expected": "JSON string"}
                })
            except Exception as e:
                logger.error(f"WebSocket error for indexing updates: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "error": "Internal server error",
                    "details": {"error": str(e)}
                })
                break
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
    finally:
        # Clean up
        await connection_manager.disconnect(websocket)

# Import metadata extraction processing function
from api.services.metadata_groups_extraction_service import process_metadata_extraction

# Metadata extraction endpoints
class MetadataExtractionRequest(BaseModel):
    group_id: int
    document_ids: Optional[List[int]] = None  # None means all documents

class MetadataExtractionJobResponse(BaseModel):
    job_id: str
    collection_id: int
    group_id: int
    total_documents: int
    message: str

@router.post("/{collection_id}/extract-metadata", response_model=MetadataExtractionJobResponse)
async def extract_metadata(
    collection_id: int,
    request: MetadataExtractionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Extract metadata for documents in a collection using a metadata group.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Validate metadata group exists
        group_check = text("SELECT id, name FROM metadata_groups WHERE id = :id")
        group = db.execute(group_check, {"id": request.group_id}).fetchone()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata group with id {request.group_id} not found"
            )
        
        # Get documents to process
        if request.document_ids:
            # Validate specified documents are in collection
            documents = db.query(SourceFiles).join(
                SourceFiles.collections
            ).filter(
                Collection.id == collection_id,
                SourceFiles.id.in_(request.document_ids)
            ).all()
            
            if len(documents) != len(request.document_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Some documents not found in collection"
                )
        else:
            # Get all documents in collection
            documents = db.query(SourceFiles).join(
                SourceFiles.collections
            ).filter(
                Collection.id == collection_id
            ).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No documents found in collection"
            )
        
        # Check for active extraction jobs to prevent duplicates
        active_job_check = text("""
            SELECT id, status, created_at, created_by
            FROM collection_extraction_jobs
            WHERE collection_id = :collection_id
            AND group_id = :group_id
            AND status IN ('pending', 'processing')
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        active_job = db.execute(active_job_check, {
            "collection_id": collection_id,
            "group_id": request.group_id
        }).fetchone()
        
        if active_job:
            # Get user name for the active job if created_by is available
            user_name = "Another user"
            if hasattr(active_job, 'created_by') and active_job.created_by:
                user_query = text("SELECT username FROM Users WHERE id = :user_id")
                user_result = db.execute(user_query, {"user_id": active_job.created_by}).fetchone()
                user_name = user_result.username if user_result else "Unknown User"
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An extraction job is already {active_job.status} for this collection and group. Started by {user_name} at {active_job.created_at}. Please wait for it to complete."
            )
        
        # Create extraction job
        insert_job = text("""
            INSERT INTO collection_extraction_jobs 
            (collection_id, group_id, status, total_documents, processed_documents, created_by)
            VALUES (:collection_id, :group_id, 'pending', :total, 0, :user_id)
        """)
        
        result = db.execute(
            insert_job,
            {
                "collection_id": collection_id,
                "group_id": request.group_id,
                "total": len(documents),
                "user_id": current_user.id
            }
        )
        db.commit()
        
        extraction_job_id = result.lastrowid
        # Use the database ID as the job_id for now
        job_id = str(extraction_job_id)
        
        # Add background task for extraction
        background_tasks.add_task(
            process_metadata_extraction,
            extraction_job_id=extraction_job_id,
            collection_id=collection_id,
            group_id=request.group_id,
            document_ids=[doc.id for doc in documents],
            user_id=current_user.id
        )
        
        return MetadataExtractionJobResponse(
            job_id=job_id,
            collection_id=collection_id,
            group_id=request.group_id,
            total_documents=len(documents),
            message=f"Started metadata extraction for {len(documents)} documents using group '{group.name}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting metadata extraction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start metadata extraction"
        )

@router.get("/{collection_id}/metadata")
async def get_extracted_metadata(
    collection_id: int,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get extracted metadata for a collection, optionally filtered by group.
    """
    try:
        # Validate collection exists
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection with id {collection_id} not found"
            )
        
        # Build query
        query = text("""
            SELECT 
                cem.id,
                cem.document_id,
                cem.group_id,
                cem.metadata_name,
                cem.extracted_value,
                cem.extracted_at,
                sf.file_name,
                sf.entity_name,
                mg.name as group_name
            FROM collection_extracted_metadata cem
            JOIN SourceFiles sf ON cem.document_id = sf.id
            JOIN metadata_groups mg ON cem.group_id = mg.id
            WHERE cem.collection_id = :collection_id
        """)
        
        params = {"collection_id": collection_id}
        
        if group_id:
            query = text(str(query) + " AND cem.group_id = :group_id")
            params["group_id"] = group_id
        
        query = text(str(query) + " ORDER BY sf.file_name, cem.metadata_name")
        
        results = db.execute(query, params)
        
        # Format results by document
        documents_metadata = {}
        for row in results:
            doc_id = row.document_id
            if doc_id not in documents_metadata:
                documents_metadata[doc_id] = {
                    "document_id": doc_id,
                    "file_name": row.file_name,
                    "entity_name": row.entity_name,
                    "metadata": {},
                    "groups": set()
                }
            
            documents_metadata[doc_id]["metadata"][row.metadata_name] = row.extracted_value
            documents_metadata[doc_id]["groups"].add(row.group_name)
        
        # Convert to list and convert sets to lists
        results_list = []
        for doc_data in documents_metadata.values():
            doc_data["groups"] = list(doc_data["groups"])
            results_list.append(doc_data)
        
        return {
            "collection_id": collection_id,
            "collection_name": collection.name,
            "total_documents": len(results_list),
            "documents": results_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extracted metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extracted metadata"
        )

@router.post("/{collection_id}/export-metadata")
async def export_metadata(
    collection_id: int,
    format: str = Query("excel", enum=["excel", "csv"]),
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Export extracted metadata as Excel or CSV file.
    """
    try:
        # Get metadata
        metadata_response = await get_extracted_metadata(collection_id, group_id, db, current_user)
        
        if not metadata_response["documents"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No metadata found for export"
            )
        
        # Prepare data for export
        export_data = []
        for doc in metadata_response["documents"]:
            row = {
                "Document ID": doc["document_id"],
                "File Name": doc["file_name"],
                "Entity Name": doc["entity_name"]
            }
            # Add metadata fields
            row.update(doc["metadata"])
            export_data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(export_data)
        
        # Generate file
        output = BytesIO()
        if format == "excel":
            df.to_excel(output, index=False, sheet_name="Metadata")
            output.seek(0)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"metadata_collection_{collection_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        else:
            df.to_csv(output, index=False)
            output.seek(0)
            media_type = "text/csv"
            filename = f"metadata_collection_{collection_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export metadata"
        )

@router.get("/{collection_id}/extracted-groups")
async def get_extracted_metadata_groups(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get metadata groups that have extraction results for this collection"""
    try:
        # Query to get distinct groups that have extracted metadata for this collection
        query = text("""
            SELECT DISTINCT 
                mg.id,
                mg.name,
                mg.description,
                COUNT(DISTINCT cem.document_id) as document_count,
                COUNT(DISTINCT cem.metadata_name) as metadata_count
            FROM metadata_groups mg
            INNER JOIN collection_extracted_metadata cem ON mg.id = cem.group_id
            WHERE cem.collection_id = :collection_id
            GROUP BY mg.id, mg.name, mg.description
            ORDER BY mg.name
        """)
        
        results = db.execute(query, {"collection_id": collection_id}).fetchall()
        
        groups = [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "document_count": row.document_count,
                "metadata_count": row.metadata_count
            }
            for row in results
        ]
        
        return {"groups": groups, "total": len(groups)}
        
    except Exception as e:
        logger.error(f"Error getting extracted metadata groups for collection {collection_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extracted metadata groups"
        )

@router.get("/metadata-group/{group_id}/documents")
async def get_documents_by_metadata_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all documents associated with a metadata group"""
    try:
        # Query to get document_ids from collection_extracted_metadata
        doc_ids_query = text("""
            SELECT DISTINCT document_id
            FROM collection_extracted_metadata
            WHERE group_id = :group_id
        """)
        doc_ids_result = db.execute(doc_ids_query, {"group_id": group_id}).fetchall()
        doc_ids = [row[0] for row in doc_ids_result]

        if not doc_ids:
            return {"documents": []}

        # Query to get document details
        documents = db.query(SourceFiles).filter(SourceFiles.id.in_(doc_ids)).all()
        
        return {"documents": documents}

    except Exception as e:
        logger.error(f"Error getting documents by metadata group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents for the metadata group"
        )