"""
API endpoints for metadata extraction functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database.database import get_db
from api.services.metadata_extraction_service import MetadataExtractionService
from api.routers.auth import get_current_user
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import threading
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# Request/Response Models
class ExtractMetadataRequest(BaseModel):
    source_file_id: int

class ExtractMetadataSequentialRequest(BaseModel):
    source_file_ids: List[int]

class ExtractMetadataResponse(BaseModel):
    success: bool
    message: str
    source_file_id: Optional[int] = None
    file_name: Optional[str] = None
    total_configurations: Optional[int] = None
    successful_extractions: Optional[int] = None
    extraction_results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

class ViewMetadataResponse(BaseModel):
    success: bool
    source_file_id: Optional[int] = None
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    drug_name: Optional[str] = None
    metadata_extracted: Optional[bool] = None
    metadata_count: Optional[int] = None
    metadata: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

class SourceFileForMetadataResponse(BaseModel):
    id: int
    file_name: str
    file_url: str
    drug_name: Optional[str]
    status: str
    metadata_extracted: bool
    metadata_count: int
    extracted_metadata_names: List[str]
    created_at: Optional[str]
    updated_at: Optional[str]

# API Endpoints

@router.get("/api/metadata-extraction/source-files")
async def get_source_files_for_metadata(
    limit: int = Query(25, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all source files with their metadata extraction status with pagination."""
    try:
        logger.info(f"Getting source files for metadata view - User: {current_user.username}, limit: {limit}, offset: {offset}")
        
        # Get paginated results
        result = MetadataExtractionService.get_source_files_for_metadata_view_paginated(
            db=db,
            limit=limit,
            offset=offset,
            status=status,
            search=search
        )
        
        logger.info(f"Retrieved {len(result['source_files'])} source files (total: {result['total_count']})")
        return result
        
    except Exception as e:
        logger.error(f"Error getting source files for metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve source files: {str(e)}"
        )

@router.get("/api/metadata-extraction/stats")
async def get_metadata_extraction_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics for metadata extraction."""
    try:
        logger.info(f"Getting metadata extraction stats - User: {current_user.username}")
        
        stats = MetadataExtractionService.get_metadata_extraction_stats(db)
        
        logger.info(f"Retrieved metadata extraction stats: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting metadata extraction stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )

@router.post("/api/metadata-extraction/extract", response_model=ExtractMetadataResponse)
async def extract_metadata(
    request: ExtractMetadataRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract metadata for a specific source file."""
    try:
        logger.info("Extracting metadata for source_file_id: " + str(request.source_file_id) + " - User: " + str(current_user.username))
        
        user_id = current_user.id  # Use the actual user ID
        
        result = MetadataExtractionService.extract_metadata_for_source_file(
            source_file_id=request.source_file_id,
            user_id=user_id,
            db=db
        )
        
        if result["success"]:
            logger.info(f"Successfully extracted metadata for source_file_id: {request.source_file_id}")
            return ExtractMetadataResponse(**result)
        else:
            logger.error(f"Failed to extract metadata: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Unknown error during metadata extraction')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract metadata endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract metadata: {str(e)}"
        )

@router.get("/api/metadata-extraction/view/{source_file_id}", response_model=ViewMetadataResponse)
async def view_extracted_metadata(
    source_file_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View all extracted metadata for a specific source file."""
    try:
        logger.info("Viewing extracted metadata for source_file_id: " + str(source_file_id) + " - User: " + str(current_user.username))
        
        result = MetadataExtractionService.get_extracted_metadata_for_source_file(
            source_file_id=source_file_id,
            db=db
        )
        
        if result["success"]:
            logger.info(f"Successfully retrieved metadata for source_file_id: {source_file_id}")
            
            # Extract source file information from the nested structure
            source_file_info = result.get("source_file", {})
            
            response_data = {
                "success": True,
                "source_file_id": source_file_info.get("id", source_file_id),
                "file_name": source_file_info.get("file_name"),
                "file_url": source_file_info.get("file_url"),
                "drug_name": source_file_info.get("drug_name"),
                "metadata_extracted": True,
                "metadata_count": result.get("total_count", 0),
                "metadata": result.get("metadata", [])
            }
            
            return ViewMetadataResponse(**response_data)
        else:
            logger.error(f"Failed to retrieve metadata: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get('error', 'Metadata not found')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in view metadata endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metadata: {str(e)}"
        )

@router.delete("/api/metadata-extraction/delete/{source_file_id}")
async def delete_extracted_metadata(
    source_file_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all extracted metadata for a source file."""
    try:
        logger.info("Deleting extracted metadata for source_file_id: " + str(source_file_id) + " - User: " + str(current_user.username))
        
        result = MetadataExtractionService.delete_extracted_metadata(
            source_file_id=source_file_id,
            db=db
        )
        
        if result["success"]:
            logger.info(f"Successfully deleted metadata for source_file_id: {source_file_id}")
            return result
        else:
            logger.error(f"Failed to delete metadata: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Failed to delete metadata')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete metadata endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete metadata: {str(e)}"
        )

@router.post("/api/metadata-extraction/re-extract", response_model=ExtractMetadataResponse)
async def re_extract_metadata(
    request: ExtractMetadataRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-extract metadata for a source file by deleting existing metadata first."""
    try:
        logger.info(f"Re-extracting metadata for source_file_id: {request.source_file_id} - User: {current_user.username}")
        
        # First, delete existing metadata
        delete_result = MetadataExtractionService.delete_extracted_metadata(
            source_file_id=request.source_file_id,
            db=db
        )
        
        if not delete_result["success"]:
            logger.warning(f"Could not delete existing metadata: {delete_result.get('error')}")
            # Continue with extraction even if delete fails (might not have existing metadata)
        
        # Now extract metadata again
        user_id = current_user.id
        
        result = MetadataExtractionService.extract_metadata_for_source_file(
            source_file_id=request.source_file_id,
            user_id=user_id,
            db=db
        )
        
        if result["success"]:
            logger.info(f"Successfully re-extracted metadata for source_file_id: {request.source_file_id}")
            return ExtractMetadataResponse(**result)
        else:
            logger.error(f"Failed to re-extract metadata: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Unknown error during metadata re-extraction')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in re-extract metadata endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to re-extract metadata: {str(e)}"
        )

@router.post("/api/metadata-extraction/extract-sequential")
async def extract_metadata_sequential(
    request: ExtractMetadataSequentialRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract metadata for multiple source files sequentially in the background."""
    try:
        logger.info(f"Starting sequential metadata extraction for {len(request.source_file_ids)} files - User: {current_user.username}")
        
        # Validate that all source files exist and are eligible for extraction
        from database.database import SourceFiles
        
        eligible_files = []
        for file_id in request.source_file_ids:
            source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
            
            if not source_file:
                logger.warning(f"Source file with ID {file_id} not found")
                continue
                
            # Check if file is eligible for metadata extraction (should be READY or COMPLETED - must be indexed)
            if source_file.status in ['READY', 'COMPLETED']:
                eligible_files.append({
                    'id': source_file.id,
                    'file_name': source_file.file_name,
                    'drug_name': source_file.drug_name
                })
            else:
                logger.warning(f"Source file {file_id} has status {source_file.status}, skipping (must be READY/indexed)")
        
        if not eligible_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No eligible files found for metadata extraction"
            )
        
        # Start sequential extraction in a separate thread
        user_id = current_user.id
        
        def extract_sequentially():
            """Function to run in separate thread for sequential extraction."""
            logger.info(f"Starting sequential metadata extraction thread for {len(eligible_files)} files")
            
            for idx, file_info in enumerate(eligible_files):
                file_id = file_info['id']
                file_name = file_info['file_name']
                
                try:
                    logger.info(f"[{idx+1}/{len(eligible_files)}] Extracting metadata for {file_name} (ID: {file_id})")
                    
                    # Create a new database session for this thread
                    from database.database import get_db_session
                    thread_db = get_db_session()
                    
                    try:
                        # Extract metadata for this file
                        result = MetadataExtractionService.extract_metadata_for_source_file(
                            source_file_id=file_id,
                            user_id=user_id,
                            db=thread_db
                        )
                        
                        if result["success"]:
                            logger.info(f"Successfully extracted metadata for {file_name}")
                        else:
                            logger.error(f"Failed to extract metadata for {file_name}: {result.get('error')}")
                            
                    finally:
                        thread_db.close()
                    
                    # Add a small delay between extractions to avoid overwhelming the system
                    if idx < len(eligible_files) - 1:
                        time.sleep(2)
                        
                except Exception as e:
                    logger.error(f"Error extracting metadata for {file_name}: {str(e)}")
                    continue
            
            logger.info(f"Completed sequential metadata extraction for {len(eligible_files)} files")
        
        # Start the extraction thread
        extraction_thread = threading.Thread(target=extract_sequentially, name=f"metadata-extraction-{time.time()}")
        extraction_thread.daemon = True
        extraction_thread.start()
        
        return {
            "success": True,
            "message": f"Started sequential metadata extraction for {len(eligible_files)} files",
            "extraction_files": eligible_files,
            "total_requested": len(request.source_file_ids),
            "total_queued": len(eligible_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sequential metadata extraction endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sequential metadata extraction: {str(e)}"
        )

@router.get("/api/metadata-extraction/export-data")
async def get_metadata_export_data(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all metadata using join query for JSON and Excel export."""
    try:
        logger.info("Getting metadata export data - User: " + str(current_user.username))
        
        result = MetadataExtractionService.get_all_metadata_for_export(db)
        
        if result["success"]:
            logger.info(f"Successfully retrieved export data: {result['total_records']} records for {result['total_drugs']} drugs")
            return result
        else:
            logger.error(f"Failed to get export data: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to retrieve export data')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in metadata export data endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve export data: {str(e)}"
        )