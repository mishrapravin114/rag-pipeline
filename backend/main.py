"""
Main FastAPI application for FDA Pipeline Frontend Integration
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from fastapi import FastAPI, Depends, HTTPException, Query, status, UploadFile, File, Request, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging
import json
import time
import uuid
import aiofiles
from datetime import datetime, timedelta
from io import BytesIO
from fastapi.responses import StreamingResponse
from sqlalchemy import text, inspect, or_
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Import our services and models
from database.database import get_db, create_tables, get_db_session,DrugSections, SourceFiles, Users, DocumentData, update_source_file_status, SearchHistory, DrugMetadata, get_pool_status, log_pool_status, cleanup_expired_sessions, monitor_session_usage, Collection
from api.services.basic_auth_service import BasicAuthService
from api.services.enhanced_search_service import EnhancedSearchService
from api.services.simple_analytics_service import SimpleAnalyticsService
from api.services.chat_management_service import FDAChatManagementService
from api.routers.auth import router as auth_router, get_current_user as get_current_user_jwt

# Import ChromaDB utility for RAG functionality
from src.utils.qdrant_util import QdrantUtil

# Import WebSocket health monitoring
from api.services.websocket_health_monitor import start_websocket_health_monitoring, stop_websocket_health_monitoring

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=4)

from src.api.state import oauth_state_store
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Starting FDA Pipeline API...")
        
        # Create database tables
        create_tables()
        logger.info("Database tables created/verified")
        
        # Ensure MetadataConfiguration table has required columns
        ensure_metadata_config_schema()
        
        # Initialize some sample data if needed
        from src.database.init_users import main as init_data
        init_data()
        
        # Ensure default metadata group exists
        from src.api.services.metadata_group_service import MetadataGroupService
        logger.info("Ensuring default metadata group exists...")
        db = get_db_session()
        try:
            # Get admin user ID (assuming ID 1 for system operations)
            admin_user_id = 1
            MetadataGroupService.ensure_default_group(db, admin_user_id)
            MetadataGroupService.assign_orphaned_configurations(db, admin_user_id)
            db.commit()
            logger.info("Default metadata group initialized")
        except Exception as e:
            logger.error(f"Error initializing default metadata group: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Initialize Qdrant
        from utils.qdrant_util import QdrantUtil
        logger.info("Initializing Qdrant...")
        qdrant_util = QdrantUtil.get_instance()
        
        # Check if any collections exist
        try:
            collections = qdrant_util.client.get_collections()
            collection_count = len(collections.collections) if collections.collections else 0
            logger.info(f"Qdrant initialized - Found {collection_count} collections")
        except Exception as e:
            logger.warning(f"Could not get collection count: {e}")
            logger.info("Qdrant initialized")
        
        # Initialize WebSocket health monitoring
        logger.info("Starting WebSocket health monitor")
        await start_websocket_health_monitoring()
        
        logger.info("FDA Pipeline API started successfully")
        
        # Log initial pool status
        log_pool_status("INFO")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise e
    
    yield
    
    # Shutdown
    logger.info("Shutting down thread pool executor")
    executor.shutdown(wait=True)
    
    # Stop WebSocket health monitoring
    logger.info("Stopping WebSocket health monitor")
    await stop_websocket_health_monitoring()
    
    # Log final pool status and cleanup
    final_status = get_pool_status()
    logger.info(f"Final MySQL pool status: {final_status}")
    log_pool_status("SHUTDOWN")
    cleanup_expired_sessions()
    logger.info("FDA Pipeline API shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="FDA Pipeline API",
    description="Backend API for FDA Pipeline Frontend Integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure logging to suppress non-critical warnings
from utils.logging_config import configure_logging
configure_logging()

# CORS configuration for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React default
        "http://localhost:3001",  # Frontend port specified
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://34.9.3.61 ",      # GCP instance IP
        "http://34.9.3.61 :3000", # GCP instance with port
        "http://34.9.3.61 :3001", # GCP instance with port
        "http://34.9.3.61 :8090"  # GCP instance API port
        "http://dxdemo.rxinsightx.com",
        "https://dxdemo.rxinsightx.com",
        "https://staging.api-rxinsightx.com",
        "https://roche.rxinsightx.com",
        "http://localhost:4200"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With"
    ],
)

# Create upload directory if it doesn't exist
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Configure static file serving for uploads
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mount static files for file downloads
app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")

# Initialize authentication service
auth_service = BasicAuthService()
security = HTTPBasic()

# Pydantic models for request/response
class DualSearchRequest(BaseModel):
    brand_name: Optional[str] = Field(None)
    therapeutic_area: Optional[str] = Field(None)
    filters: Optional[Dict[str, Any]] = Field(None)

class FileUploadResponse(BaseModel):
    success: bool
    file_id: str
    processing_status: str
    message: str = ""

class FileIdsRequest(BaseModel):
    file_ids: List[int]

class FileStatusResponse(BaseModel):
    file_id: str
    status: str
    progress: Optional[int] = Field(None)
    error: Optional[str] = Field(None)
    extraction_id: Optional[int] = Field(None)

# Chat message model for requests
class ChatMessageRequest(BaseModel):
    message: str
    drugId: Optional[Union[str, int]] = Field(None)
    drugIds: Optional[List[Union[str, int]]] = Field(None)  # For multiple drug support
    collection_id: Optional[int] = Field(None)  # For collection-based chat

# Chat message model for responses
class ChatMessageResponse(BaseModel):
    id: str
    content: str
    role: str
    timestamp: datetime
    drugId: Optional[str] = Field(None)

# Include routers
app.include_router(auth_router)

# Import and include metadata extraction router
from api.routers.metadata_extraction import router as metadata_extraction_router
app.include_router(metadata_extraction_router)

# Import and include chat router
from api.routers.chat import router as chat_router
app.include_router(chat_router)

from api.routers.multi_chat import router as multi_chat_router
app.include_router(multi_chat_router, prefix="/api/chat")


# Import and include collections router
from src.api.routers.collections import router as collections_router
app.include_router(collections_router)

# Import and include Google Drive router
from src.api.routers.google_drive import router as google_drive_router
app.include_router(google_drive_router, prefix="/api")

# Import and include metadata groups router
from src.api.routers.metadata_groups import router as metadata_groups_router
app.include_router(metadata_groups_router)

# Import and include metadata configurations router
from src.api.routers.metadata_configurations import router as metadata_configurations_router
app.include_router(metadata_configurations_router)

# Import and include metadata configs compatibility router
from src.api.routers.metadata_configs_compat import router as metadata_configs_compat_router
app.include_router(metadata_configs_compat_router)

# Import and include extraction jobs router
from src.api.routers.extraction_jobs import router as extraction_jobs_router
app.include_router(extraction_jobs_router)

# Create wrapper function to convert Users object to dict for compatibility
async def get_current_user_dependency(user: Users = Depends(get_current_user_jwt)) -> dict:
    """Convert Users object to dict format expected by main.py endpoints"""
    return {
        "user_id": user.id,
        "username": user.username,
        "name": user.username,  # Use username as name if no separate name field
        "role": user.role,
        "email": user.email,
        "is_active": user.is_active
    }

# ============================
# Background Processing Functions
# ============================

def process_file_background(file_id: int, username: str):
    """
    Background task to process a source file through the FDA pipeline.
    
    Status progression: PENDING → PROCESSING → DOCUMENT_STORED
    """
    import asyncio
    asyncio.run(_process_file_async(file_id, username))

async def _process_file_async(file_id: int, username: str):
    """Async implementation of file processing."""
    from src.fda_pipeline import FDAPipelineV2
    from database.database import update_source_file_status
    
    db = get_db_session()
    try:
        logger.info(f"Background processing started for file_id: {file_id} by {username}")
        
        # Get source file
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        if not source_file:
            logger.error(f"Source file not found: {file_id}")
            return
        
        # Initialize FDA Pipeline
        pipeline = FDAPipelineV2()
        
        # Update status to PROCESSING (already done in endpoint, but ensure it's set)
        update_source_file_status(
            db, 
            file_id, 
            "PROCESSING", 
            f"Document processing in progress - downloading and extracting content"
        )
        
        # Process the source file through FDA pipeline
        # This will:
        # 1. Download the PDF from file_url
        # 2. Extract metadata and text content
        # 3. Create document chunks
        # 4. Save to DocumentData table
        # 5. Save extraction results to FDAExtractionResults table
        results = pipeline.process_source_file(source_file)
        
        if results.get("success"):
            # Update status to DOCUMENT_STORED
            document_count = results.get("documents_count", 0)
            update_source_file_status(
                db, 
                file_id, 
                "DOCUMENT_STORED",
                f"Document processed successfully. {document_count} chunks stored in database. Starting auto-indexing..."
            )
            logger.info(f"✅ File {file_id} processed successfully. {document_count} documents stored.")
            
            # Auto-trigger indexing immediately after successful processing
            logger.info(f"🚀 Auto-starting indexing for file {file_id}...")
            try:
                # Call indexing function directly in the same background task
                await _index_file_async(file_id, username)
            except Exception as e:
                logger.error(f"❌ Auto-indexing failed for file {file_id}: {e}")
                # Update status to FAILED if auto-indexing fails
                update_source_file_status(
                    db, 
                    file_id, 
                    "FAILED",
                    f"Auto-indexing failed after processing: {str(e)}"
                )
        else:
            # Update status to FAILED
            error_msg = results.get("error", "Unknown processing error")
            update_source_file_status(
                db, 
                file_id, 
                "FAILED",
                f"Processing failed: {error_msg}"
            )
            logger.error(f"❌ File {file_id} processing failed: {error_msg}")
            
    except Exception as e:
        # Update status to FAILED on exception
        try:
            update_source_file_status(
                db, 
                file_id, 
                "FAILED",
                f"Processing exception: {str(e)}"
            )
        except Exception as update_e:
            logger.error(f"Failed to update status after exception: {update_e}")
        
        logger.error(f"❌ Exception during background processing of file {file_id}: {e}")
    finally:
        db.close()

def index_file_background(file_id: int, username: str):
    """
    Background task to index a processed file to ChromaDB.
    
    Status progression: DOCUMENT_STORED → INDEXING → READY
    """
    import asyncio
    asyncio.run(_index_file_async(file_id, username))

async def _index_file_async(file_id: int, username: str):
    """Async implementation of file indexing to vector database."""
    from database.database import update_source_file_status, DocumentData
    from src.utils.qdrant_util import QdrantUtil
    
    db = get_db_session()
    try:
        logger.info(f"Background indexing started for file_id: {file_id} by {username}")
        
        # Get source file
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        if not source_file:
            logger.error(f"Source file not found: {file_id}")
            return
        
        # Get all documents for this source file
        documents = db.query(DocumentData).filter(
            DocumentData.source_file_id == file_id
        ).all()
        
        if not documents:
            update_source_file_status(
                db, 
                file_id, 
                "FAILED",
                "No documents found to index. File must be processed first."
            )
            logger.error(f"No documents found for file {file_id}")
            return
        
        # Update status to INDEXING
        update_source_file_status(
            db, 
            file_id, 
            "INDEXING", 
            f"Adding {len(documents)} document chunks to vector database"
        )
        
        # Initialize ChromaDB
        qdrant_util = QdrantUtil()
        
        # Prepare documents for ChromaDB using the correct format
        qdrant_documents = []
        for doc in documents:
            # Parse metadata if it's JSON string
            metadata = {}
            if doc.metadata_content:
                try:
                    if isinstance(doc.metadata_content, str):
                        metadata = json.loads(doc.metadata_content)
                    else:
                        metadata = doc.metadata_content
                except:
                    metadata = {"raw_metadata": str(doc.metadata_content)}
            
            # Add source tracking to metadata for ChromaDBUtil.add_documents
            metadata.update({
                "source": source_file.file_name,  # Required by ChromaDBUtil
                "source_file_id": file_id,
                "document_id": doc.id,
                "file_name": source_file.file_name
            })
            
            # Use correct format for ChromaDBUtil.add_documents
            qdrant_documents.append({
                "page_content": doc.doc_content,
                "metadata": metadata
            })
        
        # Add all documents to ChromaDB using batched add_documents method
        try:
            result = qdrant_util.add_documents(
                documents=qdrant_documents,
                collection_name="fda_documents",
                use_chromadb_batching=True  # Use ChromaDB's official batching utilities
            )
            
            success_count = result.get("documents_added", 0)
            total_documents = result.get("total_documents", len(documents))
            status = result.get("status", "failure")
            
            logger.info(f"ChromaDB indexing result: {result.get('message', 'No message')}")
            
        except Exception as e:
            success_count = 0
            total_documents = len(documents)
            status = "failure"
            logger.error(f"Exception adding documents to ChromaDB: {e}")
        
        # Determine final status based on results
        if status == "success" and success_count == total_documents:
            # All documents successfully indexed
            update_source_file_status(
                db, 
                file_id, 
                "READY",
                f"Successfully indexed {success_count} documents to vector database. Ready for search and chat."
            )
            logger.info(f"✅ File {file_id} indexed successfully. {success_count}/{total_documents} documents added to ChromaDB.")
        elif status in ["success", "partial_success"] and success_count > 0:
            # Partial success - some documents indexed
            update_source_file_status(
                db, 
                file_id, 
                "READY",
                f"Partially indexed {success_count}/{total_documents} documents. Ready for search and chat with available content."
            )
            logger.warning(f"⚠️ File {file_id} partially indexed: {success_count}/{total_documents} documents added to ChromaDB.")
        else:
            # Complete failure
            update_source_file_status(
                db, 
                file_id, 
                "FAILED",
                f"Indexing failed. {success_count}/{total_documents} documents indexed. Try retry indexing."
            )
            logger.error(f"❌ File {file_id} indexing failed: {success_count}/{total_documents} indexed")
            
    except Exception as e:
        # Update status to FAILED on exception
        try:
            update_source_file_status(
                db, 
                file_id, 
                "FAILED",
                f"Indexing exception: {str(e)}"
            )
        except Exception as update_e:
            logger.error(f"Failed to update status after indexing exception: {update_e}")
        
        logger.error(f"❌ Exception during background indexing of file {file_id}: {e}")
    finally:
        db.close()

# ============================
# Search Endpoints
# ============================

@app.post("/api/search/dual")
async def dual_search(
    request: DualSearchRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Dual search by brand name and therapeutic area using existing fields."""
    try:
        logger.info(f"Dual search request from user {current_user['username']}: {request}")
        
        results = EnhancedSearchService.dual_search(
            brand_name=request.brand_name,
            therapeutic_area=request.therapeutic_area,
            filters=request.filters,
            username=current_user["username"],
            db=db
        )
        
        logger.info(f"Search completed. Found {results['total_count']} results in {results['execution_time_ms']}ms")
        return results
        
    except Exception as e:
        logger.error(f"Error in dual search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    type: str = Query(..., regex="^(brand|therapeutic)$"),
    db: Session = Depends(get_db)
):
    """Get search suggestions from existing fields."""
    try:
        suggestions = EnhancedSearchService.get_search_suggestions(query, type, db)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/filters")
async def get_search_filters(db: Session = Depends(get_db)):
    """Get available filter options for advanced search."""
    try:
        filters = EnhancedSearchService.get_advanced_filters(db)
        return filters
    except Exception as e:
        logger.error(f"Error getting filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Drug Details Endpoints
# ============================

@app.get("/api/drugs/{drug_id}/details")
async def get_drug_details(
    drug_id: int,
    db: Session = Depends(get_db)
):
    """Get drug details from existing fields and DrugSections."""
    try:
        # Get basic drug info
        drug = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == drug_id
        ).first()
        
        if not drug:
            raise HTTPException(status_code=404, detail="Drug not found")
        
        # Get structured sections
        sections = db.query(DrugSections).filter(
            DrugSections.source_file_id == drug.source_file_id
        ).order_by(DrugSections.section_order).all()
        
        # Get source file info
        source_file = db.query(SourceFiles).filter(
            SourceFiles.id == drug.source_file_id
        ).first()
        
        # If no sections in DrugSections table, create them from metadata
        sections_data = []
        if sections:
            sections_data = [
                {
                    "id": section.id,
                    "type": section.section_type,
                    "title": section.section_title,
                    "content": section.section_content,
                    "order": section.section_order
                } for section in sections
            ]
        elif drug.full_metadata:
            # Extract sections from metadata
            metadata = drug.full_metadata
            section_id = 1
            
            # Create sections from metadata fields
            if metadata.get('indication'):
                sections_data.append({
                    "id": section_id,
                    "type": "indication",
                    "title": "Indications and Usage",
                    "content": metadata['indication'],
                    "order": section_id
                })
                section_id += 1
            
            if metadata.get('dosage_administration'):
                content = '\n\n'.join(metadata['dosage_administration']) if isinstance(metadata['dosage_administration'], list) else str(metadata['dosage_administration'])
                sections_data.append({
                    "id": section_id,
                    "type": "dosage",
                    "title": "Dosage and Administration",
                    "content": content,
                    "order": section_id
                })
                section_id += 1
            
            if metadata.get('contraindications'):
                content = '\n\n'.join(metadata['contraindications']) if isinstance(metadata['contraindications'], list) else str(metadata['contraindications'])
                sections_data.append({
                    "id": section_id,
                    "type": "contraindications",
                    "title": "Contraindications",
                    "content": content,
                    "order": section_id
                })
                section_id += 1
            
            if metadata.get('warnings_precautions'):
                content = '\n\n'.join(metadata['warnings_precautions']) if isinstance(metadata['warnings_precautions'], list) else str(metadata['warnings_precautions'])
                sections_data.append({
                    "id": section_id,
                    "type": "warnings",
                    "title": "Warnings and Precautions",
                    "content": content,
                    "order": section_id
                })
                section_id += 1
            
            if metadata.get('adverse_reactions'):
                content = '\n\n'.join(metadata['adverse_reactions']) if isinstance(metadata['adverse_reactions'], list) else str(metadata['adverse_reactions'])
                sections_data.append({
                    "id": section_id,
                    "type": "adverse_reactions",
                    "title": "Adverse Reactions",
                    "content": content,
                    "order": section_id
                })
                section_id += 1
            
            if metadata.get('efficacy_details'):
                content = '\n\n'.join(metadata['efficacy_details']) if isinstance(metadata['efficacy_details'], list) else str(metadata['efficacy_details'])
                sections_data.append({
                    "id": section_id,
                    "type": "clinical_studies",
                    "title": "Clinical Studies",
                    "content": content,
                    "order": section_id
                })
                section_id += 1
        
        # Extract page information from metadata
        page_info = {}
        if drug.full_metadata and drug.full_metadata.get('processing_metadata'):
            proc_meta = drug.full_metadata['processing_metadata']
            if proc_meta.get('chunk_summary'):
                chunk_summary = proc_meta['chunk_summary']
                page_info = {
                    "total_pages": chunk_summary.get('pages_covered', 0),
                    "page_numbers": chunk_summary.get('page_numbers', []),
                    "total_chunks": chunk_summary.get('total_chunks', 0),
                    "total_tokens": chunk_summary.get('total_tokens', 0)
                }
        
        return {
            "basic_info": {
                "id": drug.id,
                "drug_name": drug.drug_name or "Unknown",
                "therapeutic_area": drug.full_metadata.get('indication', 'Not specified') if drug.full_metadata else "Not specified",
                "approval_status": "Approved",  # Default status, can be enhanced
                "country": "United States",     # Default country, can be enhanced
                "applicant": drug.manufacturer or "Unknown",
                "active_substance": drug.active_ingredients or "Not specified",
                "regulatory": f"FDA {drug.submission_number}" if drug.submission_number else "FDA"
            },
            "timeline": {
                "submission_date": drug.submission_date if hasattr(drug, 'submission_date') else None,
                "pdufa_date": drug.pdufa_date if hasattr(drug, 'pdufa_date') else None,
                "approval_date": drug.approval_date
            },
            "sections": sections_data,
            "page_info": page_info,
            "file_url": f"/files/{source_file.file_name}" if source_file else None,
            "metadata": drug.full_metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drug details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Analytics Endpoints
# ============================

@app.get("/api/analytics/history")
async def get_search_history(
    limit: int = Query(default=10, ge=1, le=100),
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get user's search history."""
    try:
        history = SimpleAnalyticsService.get_user_search_history(
            username=current_user["username"],
            limit=limit,
            db=db
        )
        return {"history": history}
    except Exception as e:
        logger.error(f"Error getting search history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/trending")
async def get_trending_searches(
    period: str = Query(default="weekly", regex="^(daily|weekly|monthly)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get trending searches."""
    try:
        trending = SimpleAnalyticsService.get_trending_searches(
            period=period,
            limit=limit,
            db=db
        )
        return {"trending": trending}
    except Exception as e:
        logger.error(f"Error getting trending searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/dashboard")
async def get_dashboard_data(
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard data."""
    try:
        dashboard = SimpleAnalyticsService.get_dashboard_data(
            username=current_user["username"],
            db=db
        )
        return dashboard
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# File Management Endpoints
# ============================

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Upload and process PDF files."""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are supported"
            )
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
        
        # Save uploaded file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Save to database
        from database.database import SourceFiles
        source_file = SourceFiles(
            file_name=file.filename,
            file_url=str(file_path),
            status="PENDING",
            comments=f"Uploaded by {current_user['username']}",
            created_by=current_user["user_id"]
        )
        db.add(source_file)
        db.commit()
        db.refresh(source_file)
        
        logger.info(f"File uploaded: {file.filename} by {current_user['username']}")
        
        return FileUploadResponse(
            success=True,
            file_id=file_id,
            processing_status="pending",
            message=f"File {file.filename} uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{file_id}/status")
async def get_file_status(file_id: str, db: Session = Depends(get_db)):
    """Get processing status of uploaded file."""
    try:
        from database.database import SourceFiles
        
        # Simple status check (you can enhance this based on actual processing)
        source_file = db.query(SourceFiles).filter(
            SourceFiles.file_url.like(f"%{file_id}%")
        ).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileStatusResponse(
            file_id=file_id,
            status=source_file.status.lower(),
            progress=100 if source_file.status == "COMPLETED" else 50,
            extraction_id=source_file.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Source Files CRUD Endpoints
# ============================

class SourceFileResponse(BaseModel):
    id: int
    file_name: str
    file_url: str
    drug_name: Optional[str] = Field(None)
    status: str
    comments: Optional[str] = Field(None)
    created_by: Optional[int] = Field(None)
    us_ma_date: Optional[str] = Field(None)
    created_at: datetime
    updated_at: datetime
    file_size: Optional[str] = Field(None)
    file_type: Optional[str] = Field(None)
    processing_progress: Optional[int] = Field(None)
    error_message: Optional[str] = Field(None)
    extraction_count: Optional[int] = Field(None)
    creator_username: Optional[str] = Field(None)

class SourceFileCreate(BaseModel):
    file_name: str
    file_url: str
    drug_name: Optional[str] = Field(None)
    comments: Optional[str] = Field(None)
    us_ma_date: Optional[str] = Field(None)
    status: str = Field("PENDING")

class SourceFileUpdate(BaseModel):
    file_name: Optional[str] = Field(None)
    file_url: Optional[str] = Field(None)
    drug_name: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    comments: Optional[str] = Field(None)
    us_ma_date: Optional[str] = Field(None)

@app.get("/api/source-files")
async def get_source_files(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    exclude_collection: Optional[int] = Query(None, description="Exclude files already in this collection"),
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get all source files with optional filtering."""
    try:
        from database.database import SourceFiles, Users
        
        query = db.query(SourceFiles).join(Users, SourceFiles.created_by == Users.id, isouter=True)
        
        # Apply status filter
        if status and status != "all":
            query = query.filter(SourceFiles.status == status.upper())
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                SourceFiles.file_name.ilike(search_term) |
                SourceFiles.file_url.ilike(search_term) |
                SourceFiles.drug_name.ilike(search_term) |
                SourceFiles.comments.ilike(search_term) |
                Users.username.ilike(search_term)
            )
        
        # Exclude files already in a specific collection
        if exclude_collection is not None:
            from database.database import Collection, collection_document_association
            # Subquery to get document IDs in the collection
            docs_in_collection = db.query(collection_document_association.c.document_id).filter(
                collection_document_association.c.collection_id == exclude_collection
            ).subquery()
            # Exclude these documents
            query = query.filter(~SourceFiles.id.in_(docs_in_collection))
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        source_files = query.order_by(SourceFiles.created_at.desc()).offset(offset).limit(limit).all()
        
        # Get extraction counts for each source file
        results = []
        for source_file in source_files:
            # Count extractions for this source file using DrugMetadata
            extraction_count = db.query(DrugMetadata).filter(
                DrugMetadata.source_file_id == source_file.id
            ).count()
            
            # Determine file type and size (mock for now, could be enhanced)
            file_type = "PDF" if source_file.file_name.lower().endswith('.pdf') else "Unknown"
            file_size = f"{(hash(source_file.file_name) % 5000 + 500)} KB"  # Mock file size
            
            # Calculate progress based on status
            progress = {
                "PENDING": 0,
                "PROCESSING": 50,
                "COMPLETED": 100,
                "FAILED": 0,
                "READY": 0
            }.get(source_file.status, 0)
            
            results.append(SourceFileResponse(
                id=source_file.id,
                file_name=source_file.file_name,
                file_url=source_file.file_url,
                drug_name=source_file.drug_name,
                status=source_file.status,
                comments=source_file.comments,
                us_ma_date=source_file.us_ma_date,
                created_by=source_file.created_by,
                created_at=source_file.created_at,
                updated_at=source_file.updated_at,
                file_size=file_size,
                file_type=file_type,
                processing_progress=progress,
                extraction_count=extraction_count,
                creator_username=source_file.creator.username if source_file.creator else None
            ))
        
        return {
            "source_files": results,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting source files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files/upload")
async def upload_source_file(
    request: Request,
    file: UploadFile = File(...),
    drug_name: Optional[str] = Form(None),
    comments: Optional[str] = Form(None),
    us_ma_date: Optional[str] = Form(None),
    collection_id: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Upload a PDF file and create a source file record."""
    try:
        from database.database import SourceFiles, Collection
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        safe_filename = file.filename.replace(" ", "_").replace("/", "_")
        file_path = UPLOAD_DIR / f"{file_id}_{safe_filename}"
        
        # Save uploaded file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Create source file record with proper URL
        # Generate the URL based on the request host
        base_url = str(request.base_url).rstrip('/')
        uploaded_file_url = f"{base_url}/uploads/{file_id}_{safe_filename}"
        
        source_file = SourceFiles(
            file_name=safe_filename,
            file_url=uploaded_file_url,
            drug_name=drug_name,
            status="PENDING",
            comments=comments,
            us_ma_date=us_ma_date,
            created_by=current_user["user_id"]
        )
        
        db.add(source_file)
        db.flush()  # Flush to get the ID
        
        # Add to collection if specified
        if collection_id:
            collection = db.query(Collection).filter(Collection.id == collection_id).first()
            if collection:
                collection.documents.append(source_file)
        
        db.commit()
        db.refresh(source_file)
        
        logger.info(f"Source file uploaded: {source_file.file_name} by {current_user['username']}")
        
        # Return the created file with additional data
        file_type = "PDF"
        file_size = f"{len(content) // 1024} KB"
        
        return SourceFileResponse(
            id=source_file.id,
            file_name=source_file.file_name,
            file_url=source_file.file_url,
            drug_name=source_file.drug_name,
            status=source_file.status,
            comments=source_file.comments,
            us_ma_date=source_file.us_ma_date,
            created_by=source_file.created_by,
            created_at=source_file.created_at,
            updated_at=source_file.updated_at,
            file_size=file_size,
            file_type=file_type,
            processing_progress=0,
            extraction_count=0,
            creator_username=current_user['username']
        )
        
    except Exception as e:
        logger.error(f"Error uploading source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files")
async def create_source_file(
    request: Request,
    source_file_data: SourceFileCreate = None,
    file: UploadFile = File(None),
    collection_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Create a new source file from URL or file upload, optionally adding to a collection."""
    try:
        from database.database import SourceFiles, Collection
        
        # Validate input - either source_file_data or file must be provided
        if not source_file_data and not file:
            raise HTTPException(
                status_code=400,
                detail="Either source file data or file upload must be provided"
            )
        
        # Handle file upload
        if file:
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF files are supported"
                )
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
            
            # Save uploaded file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # Create source file record with proper URL
            base_url = str(request.base_url).rstrip('/')
            uploaded_file_url = f"{base_url}/uploads/{file_path}"
            
            source_file = SourceFiles(
                file_name=file.filename,
                file_url=uploaded_file_url,
                drug_name=None,  # Will be extracted during processing
                status="PENDING",
                comments="Uploaded file",
                us_ma_date=None,
                created_by=current_user["user_id"]
            )
        else:
            # Create from URL
            source_file = SourceFiles(
                file_name=source_file_data.file_name,
                file_url=source_file_data.file_url,
                drug_name=source_file_data.drug_name,
                status=source_file_data.status,
                comments=source_file_data.comments,
                us_ma_date=source_file_data.us_ma_date,
                created_by=current_user["user_id"]
            )
        
        db.add(source_file)
        db.flush()  # Flush to get the ID
        
        # Add to collection if specified
        if collection_id:
            collection = db.query(Collection).filter(Collection.id == collection_id).first()
            if not collection:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection with id {collection_id} not found"
                )
            collection.documents.append(source_file)
        
        db.commit()
        db.refresh(source_file)
        
        logger.info(f"Source file created: {source_file.file_name} by {current_user['username']}")
        
        # Return the created file with additional data
        file_type = "PDF" if source_file.file_name.lower().endswith('.pdf') else "Unknown"
        file_size = f"{(hash(source_file.file_name) % 5000 + 500)} KB"
        
        return SourceFileResponse(
            id=source_file.id,
            file_name=source_file.file_name,
            file_url=source_file.file_url,
            drug_name=source_file.drug_name,
            status=source_file.status,
            comments=source_file.comments,
            us_ma_date=source_file.us_ma_date,
            created_by=source_file.created_by,
            created_at=source_file.created_at,
            updated_at=source_file.updated_at,
            file_size=file_size,
            file_type=file_type,
            processing_progress=0,
            extraction_count=0,
            creator_username=current_user['username']
        )
        
    except Exception as e:
        logger.error(f"Error creating source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/source-files/{file_id}")
async def get_source_file(
    file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get a specific source file by ID."""
    try:
        from database.database import SourceFiles, Users
        
        source_file = db.query(SourceFiles).join(
            Users, SourceFiles.created_by == Users.id, isouter=True
        ).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Get extraction count
        extraction_count = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.source_file_id == source_file.id
        ).count()
        
        # Determine file type and size
        file_type = "PDF" if source_file.file_name.lower().endswith('.pdf') else "Unknown"
        file_size = f"{(hash(source_file.file_name) % 5000 + 500)} KB"
        
        # Calculate progress
        progress = {
            "PENDING": 0,
            "PROCESSING": 50,
            "COMPLETED": 100,
            "FAILED": 0,
            "READY": 0
        }.get(source_file.status, 0)
        
        return SourceFileResponse(
            id=source_file.id,
            file_name=source_file.file_name,
            file_url=source_file.file_url,
            drug_name=source_file.drug_name,
            status=source_file.status,
            comments=source_file.comments,
            us_ma_date=source_file.us_ma_date,
            created_by=source_file.created_by,
            created_at=source_file.created_at,
            updated_at=source_file.updated_at,
            file_size=file_size,
            file_type=file_type,
            processing_progress=progress,
            extraction_count=extraction_count,
            creator_username=source_file.creator.username if source_file.creator else "Unknown"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/source-files/{file_id}")
async def update_source_file(
    file_id: int,
    source_file_data: SourceFileUpdate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Update a source file."""
    try:
        from database.database import SourceFiles
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Update fields if provided
        if source_file_data.file_name is not None:
            source_file.file_name = source_file_data.file_name
        if source_file_data.file_url is not None:
            source_file.file_url = source_file_data.file_url
        if source_file_data.drug_name is not None:
            source_file.drug_name = source_file_data.drug_name
        if source_file_data.status is not None:
            source_file.status = source_file_data.status
        if source_file_data.comments is not None:
            source_file.comments = source_file_data.comments
        if source_file_data.us_ma_date is not None:
            source_file.us_ma_date = source_file_data.us_ma_date
        
        source_file.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(source_file)
        
        logger.info(f"Source file updated: {source_file.file_name} by {current_user['username']}")
        
        # Return updated file with additional data
        file_type = "PDF" if source_file.file_name.lower().endswith('.pdf') else "Unknown"
        file_size = f"{(hash(source_file.file_name) % 5000 + 500)} KB"
        extraction_count = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.source_file_id == source_file.id
        ).count()
        
        progress = {
            "PENDING": 0,
            "PROCESSING": 50,
            "COMPLETED": 100,
            "FAILED": 0,
            "READY": 0
        }.get(source_file.status, 0)
        
        return SourceFileResponse(
            id=source_file.id,
            file_name=source_file.file_name,
            file_url=source_file.file_url,
            drug_name=source_file.drug_name,
            status=source_file.status,
            comments=source_file.comments,
            us_ma_date=source_file.us_ma_date,
            created_by=source_file.created_by,
            created_at=source_file.created_at,
            updated_at=source_file.updated_at,
            file_size=file_size,
            file_type=file_type,
            processing_progress=progress,
            extraction_count=extraction_count,
            creator_username=current_user['username']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/source-files/{file_id}")
async def delete_source_file(
    file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Delete a source file and its associated data."""
    try:
        from database.database import SourceFiles
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Check if there are associated extractions
        #extraction_count = db.query(FDAExtractionResults).filter(
        #    FDAExtractionResults.source_file_id == source_file.id
        #).count()
        
        # Delete associated extractions first
        #if extraction_count > 0:
        #    db.query(FDAExtractionResults).filter(
        #        FDAExtractionResults.source_file_id == source_file.id
       #     ).delete()
        extraction_count = 0
        # Delete associated drug sections
        db.query(DrugSections).filter(
            DrugSections.source_file_id == source_file.id
        ).delete()
        
        # Delete the source file
        file_name = source_file.file_name
        db.delete(source_file)
        db.commit()
        
        logger.info(f"Source file deleted: {file_name} by {current_user['username']}")
        
        return {
            "success": True,
            "message": f"Source file '{file_name}' and {extraction_count} associated extractions deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting source file: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files/{file_id}/process")
async def process_source_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Trigger processing of a source file through the FDA pipeline."""
    try:
        from database.database import SourceFiles
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Check if file is in a processable state
        if source_file.status not in ["PENDING", "FAILED", "READY"]:
            raise HTTPException(
                status_code=400, 
                detail=f"File cannot be processed in current status: {source_file.status}"
            )
        
        # Update status to processing
        source_file.status = "PROCESSING"
        source_file.updated_at = datetime.utcnow()
        source_file.comments = f"Processing started by {current_user['username']}"
        
        db.commit()
        
        logger.info(f"Processing started for source file: {source_file.file_name} by {current_user['username']}")
        
        # Add background task to process the file
        background_tasks.add_task(
            process_file_background,
            file_id,
            current_user['username']
        )
        
        return {
            "success": True,
            "message": f"Processing started for '{source_file.file_name}'",
            "file_id": file_id,
            "status": "PROCESSING"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files/{file_id}/index")
async def index_source_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Index a processed source file to the vector database."""
    try:
        from database.database import SourceFiles, DocumentData
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Check if file is ready for indexing
        # Allow indexing for DOCUMENT_STORED status or FAILED status with existing documents
        if source_file.status == "DOCUMENT_STORED":
            # Normal case - file just finished processing
            pass
        elif source_file.status == "FAILED":
            # Check if there are documents available for retry indexing
            existing_docs = db.query(DocumentData).filter(
                DocumentData.source_file_id == file_id
            ).count()
            
            if existing_docs == 0:
                raise HTTPException(
                    status_code=400, 
                    detail="No documents found for indexing retry. File must be processed first."
                )
            
            # File failed but has documents - allow retry indexing
            logger.info(f"Retry indexing for file {file_id} - found {existing_docs} documents")
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"File must be in DOCUMENT_STORED or FAILED status to index. Current status: {source_file.status}"
            )
        
        # Update status to indexing
        source_file.status = "INDEXING"
        source_file.updated_at = datetime.utcnow()
        source_file.comments = f"Vector indexing started by {current_user['username']}"
        
        db.commit()
        
        logger.info(f"Indexing started for source file: {source_file.file_name} by {current_user['username']}")
        
        # Add background task to index the file
        background_tasks.add_task(
            index_file_background,
            file_id,
            current_user['username']
        )
        
        return {
            "success": True,
            "message": f"Vector indexing started for '{source_file.file_name}'",
            "file_id": file_id,
            "status": "INDEXING"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing source file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/source-files/{file_id}/vectordb")
async def delete_source_file_vectordb(
    file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Delete vector database documents for a specific source file."""
    try:
        from database.database import SourceFiles, update_source_file_status
        from src.utils.qdrant_util import QdrantUtil
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Initialize ChromaDB
        qdrant_util = QdrantUtil()
        
        # Delete vector database documents for this source file
        result = qdrant_util.delete_documents_by_source_file(
            source_file_name=source_file.file_name,
            collection_name="fda_documents"
        )
        
        if result["status"] == "success":
            # Update source file status to DOCUMENT_STORED since vector DB docs are deleted
            update_source_file_status(
                db, 
                file_id, 
                "DOCUMENT_STORED", 
                f"Vector DB documents deleted by {current_user['username']} - {result['deleted_count']} documents removed"
            )
            
            logger.info(f"Vector DB documents deleted for '{source_file.file_name}' by {current_user['username']}: {result['deleted_count']} documents")
            logger.info(f"Source file {file_id} status updated to DOCUMENT_STORED")
            
            return {
                "success": True,
                "message": result["message"],
                "deleted_count": result["deleted_count"],
                "source_file_name": source_file.file_name,
                "file_id": file_id,
                "new_status": "DOCUMENT_STORED"
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to delete vector DB documents: {result.get('error', 'Unknown error')}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vector DB documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/source-files/{file_id}/vectordb/count")
async def get_source_file_vectordb_count(
    file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get the count of vector database documents for a specific source file."""
    try:
        from database.database import SourceFiles
        from src.utils.qdrant_util import QdrantUtil
        
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Initialize ChromaDB
        qdrant_util = QdrantUtil()
        
        # Get document count for this source file
        document_count = qdrant_util.get_document_count_by_source_file(
            source_file_name=source_file.file_name,
            collection_name="fda_documents"
        )
        
        return {
            "success": True,
            "source_file_name": source_file.file_name,
            "file_id": file_id,
            "document_count": document_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vector DB document count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files/bulk-process")
async def bulk_process_source_files(
    request: FileIdsRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Trigger processing of multiple source files."""
    try:
        from database.database import SourceFiles
        
        # Get all files with the provided IDs
        source_files = db.query(SourceFiles).filter(SourceFiles.id.in_(request.file_ids)).all()
        
        if not source_files:
            raise HTTPException(status_code=404, detail="No source files found")
        
        processed_files = []
        for source_file in source_files:
            if source_file.status in ["PENDING", "READY", "FAILED"]:
                source_file.status = "PROCESSING"
                source_file.updated_at = datetime.utcnow()
                source_file.comments = f"Bulk processing started by {current_user['username']}"
                processed_files.append(source_file.file_name)
        
        db.commit()
        
        logger.info(f"Bulk processing started for {len(processed_files)} files by {current_user['username']}")
        
        return {
            "success": True,
            "message": f"Processing started for {len(processed_files)} files",
            "processed_files": processed_files,
            "total_requested": len(request.file_ids),
            "total_processed": len(processed_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-files/process-sequential")
async def process_source_files_sequential(
    request: FileIdsRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Trigger sequential processing of multiple source files asynchronously.
    Files will be processed one by one in a separate thread to avoid blocking.
    """
    try:
        from database.database import SourceFiles, DocumentData
        from src.fda_pipeline import FDAPipelineV2
        from src.utils.qdrant_util import QdrantUtil
        
        logger.info(f"Sequential processing request for files: {request.file_ids} by user {current_user['username']}")
        
        # Validate that all files exist and are eligible for processing
        eligible_files = []
        for file_id in request.file_ids:
            source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
            if source_file and source_file.status in ['PENDING', 'FAILED']:
                eligible_files.append({
                    'id': source_file.id,
                    'file_name': source_file.file_name,
                    'drug_name': source_file.drug_name,
                    'file_url': source_file.file_url
                })
        
        if not eligible_files:
            logger.warning(f"No eligible files found for processing from list: {request.file_ids}")
            raise HTTPException(
                status_code=400, 
                detail="No eligible files found for processing. Files must be in PENDING or FAILED status."
            )
        
        logger.info(f"Found {len(eligible_files)} eligible files for sequential processing")
        
        # Function to process files sequentially in a thread
        def process_files_in_thread(files_to_process):
            """Process files one by one in a separate thread."""
            logger.info(f"Thread started: Processing {len(files_to_process)} files sequentially")
            
            try:
                pipeline = FDAPipelineV2()
                qdrant = QdrantUtil()
                logger.info("Successfully initialized pipeline and ChromaDB in thread")
            except Exception as e:
                logger.error(f"Failed to initialize pipeline or ChromaDB: {str(e)}")
                return
            
            for idx, file_info in enumerate(files_to_process, 1):
                file_id = file_info['id']
                logger.info(f"Thread processing file {idx}/{len(files_to_process)}: {file_info['file_name']} (ID: {file_id})")
                
                db_session = get_db_session()
                try:
                    # Get fresh source file instance
                    source_file = db_session.query(SourceFiles).filter(SourceFiles.id == file_id).first()
                    if not source_file:
                        logger.error(f"Source file {file_id} not found")
                        continue
                    
                    # Update status to PROCESSING
                    source_file.status = "PROCESSING"
                    source_file.processing_progress = 0
                    db_session.commit()
                    logger.info(f"Updated file {file_id} status to PROCESSING")
                    
                    # Process the file
                    logger.info(f"Calling pipeline.process_source_file for {file_id}")
                    result = pipeline.process_source_file(source_file)
                    
                    if result.get('success'):
                        # Update status to DOCUMENT_STORED
                        source_file.status = "DOCUMENT_STORED"
                        source_file.processing_progress = 50
                        source_file.comments = f"Successfully processed {result.get('documents_count', 0)} documents"
                        db_session.commit()
                        logger.info(f"File {file_id} processed successfully, {result.get('documents_count', 0)} documents created")
                        
                        # Now index to ChromaDB
                        try:
                            logger.info(f"Starting ChromaDB indexing for file {file_id}")
                            source_file.status = "INDEXING"
                            source_file.processing_progress = 75
                            db_session.commit()
                            
                            # Get documents from database
                            documents = db_session.query(DocumentData).filter(
                                DocumentData.source_file_id == file_id
                            ).all()
                            
                            if documents:
                                # Prepare documents for ChromaDB
                                qdrant_documents = []
                                for doc in documents:
                                    metadata = json.loads(doc.metadata_content)
                                    metadata['source_file_id'] = str(doc.source_file_id)
                                    metadata['source_file_name'] = source_file.file_name
                                    metadata['drug_name'] = source_file.drug_name or ''
                                    metadata['chunk_id'] = doc.id
                                    metadata['document_id'] = f"doc_{doc.id}"
                                    
                                    qdrant_documents.append({
                                        'page_content': doc.doc_content,
                                        'metadata': metadata
                                    })
                                
                                # Add to ChromaDB
                                qdrant_result = qdrant.add_documents(
                                    documents=qdrant_documents,
                                    collection_name="fda_documents"
                                )
                                
                                # Update status to READY
                                source_file.status = "READY"
                                source_file.processing_progress = 100
                                source_file.comments = f"Successfully indexed {len(documents)} documents"
                                db_session.commit()
                                logger.info(f"File {file_id} indexed successfully to ChromaDB")
                            else:
                                logger.warning(f"No documents found for file {file_id}")
                                source_file.status = "READY"
                                source_file.processing_progress = 100
                                db_session.commit()
                                
                        except Exception as e:
                            logger.error(f"Error indexing file {file_id} to ChromaDB: {str(e)}")
                            source_file.status = "FAILED"
                            source_file.comments = f"Indexing error: {str(e)}"
                            db_session.commit()
                    else:
                        # Mark as failed
                        error_msg = result.get('error', 'Unknown error')
                        source_file.status = "FAILED"
                        source_file.comments = f"Processing error: {error_msg}"
                        db_session.commit()
                        logger.error(f"Failed to process file {file_id}: {error_msg}")
                        
                except Exception as e:
                    logger.error(f"Exception processing file {file_id}: {str(e)}")
                    try:
                        source_file = db_session.query(SourceFiles).filter(SourceFiles.id == file_id).first()
                        if source_file:
                            source_file.status = "FAILED"
                            source_file.comments = f"Processing error: {str(e)}"
                            db_session.commit()
                    except:
                        pass
                finally:
                    db_session.close()
                
                # Add a small delay between files to prevent overload
                time.sleep(2)
            
            logger.info(f"Thread completed: Processed {len(files_to_process)} files")
        
        # Submit the processing task to thread pool executor
        logger.info("Submitting sequential processing task to thread pool")
        future = executor.submit(process_files_in_thread, eligible_files)
        logger.info(f"Task submitted to thread pool, future: {future}")
        
        # Return immediate response
        return {
            "success": True,
            "message": f"Sequential processing started for {len(eligible_files)} files",
            "processing_files": [
                {
                    "id": f['id'],
                    "file_name": f['file_name'],
                    "drug_name": f['drug_name']
                } for f in eligible_files
            ],
            "total_requested": len(request.file_ids),
            "total_queued": len(eligible_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating sequential processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/source-files/processing-status")
async def get_processing_status(
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get status of currently processing files."""
    try:
        from database.database import SourceFiles
        
        # Get files that are currently being processed
        processing_files = db.query(SourceFiles).filter(
            SourceFiles.status.in_(['PROCESSING', 'INDEXING'])
        ).all()
        
        return {
            "processing_count": len(processing_files),
            "processing_files": [
                {
                    "id": f.id,
                    "file_name": f.file_name,
                    "drug_name": f.drug_name,
                    "status": f.status,
                    "processing_progress": f.processing_progress,
                    "updated_at": f.updated_at.isoformat() if f.updated_at else None
                } for f in processing_files
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/source-files/stats")
async def get_source_files_stats(
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get statistics about source files."""
    try:
        from database.database import SourceFiles
        from sqlalchemy import func
        
        # Get total count
        total_count = db.query(SourceFiles).count()
        
        # Get status counts
        status_counts = db.query(
            SourceFiles.status,
            func.count(SourceFiles.id).label('count')
        ).group_by(SourceFiles.status).all()
        
        # Get recent files (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_count = db.query(SourceFiles).filter(
            SourceFiles.created_at >= seven_days_ago
        ).count()
        
        # Get files by user
        user_counts = db.query(
            SourceFiles.created_by,
            func.count(SourceFiles.id).label('count')
        ).group_by(SourceFiles.created_by).all()
        
        status_distribution = {status: count for status, count in status_counts}
        
        return {
            "total_files": total_count,
            "recent_files": recent_count,
            "status_distribution": status_distribution,
            "user_file_counts": len(user_counts),
            "stats_generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting source files stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Document Download Endpoints
# ============================

@app.get("/api/documents/download/{drug_id}")
async def download_drug_document(
    drug_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Download the PDF document for a specific drug from the FDA source
    """
    try:
        from database.database import FDAExtractionResults, SourceFiles
        import httpx
        import os
        
        logger.info(f"Document download request from user {current_user['username']} for drug_id: {drug_id}")
        
        # Get the drug and its source file
        drug = db.query(FDAExtractionResults).filter(FDAExtractionResults.id == drug_id).first()
        if not drug:
            raise HTTPException(status_code=404, detail="Drug not found")
        
        # Get the source file information
        source_file = db.query(SourceFiles).filter(SourceFiles.id == drug.source_file_id).first()
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        if not source_file.file_url:
            raise HTTPException(status_code=404, detail="PDF file URL not available")
        
        # Generate a clean filename
        safe_drug_name = (drug.drug_name or "Unknown").replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
        filename = f"{safe_drug_name}_FDA_Label.pdf"
        
        # Check if the file_url is a local file path or HTTP URL
        if source_file.file_url.startswith(('http://', 'https://')):
            # Try to download the PDF from the HTTP URL
            async with httpx.AsyncClient(
                timeout=30.0, 
                follow_redirects=True, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            ) as client:
                try:
                    response = await client.get(source_file.file_url)
                    response.raise_for_status()
                    
                    # Check if we got redirected to an error page (common with FDA site)
                    if 'apology' in str(response.url).lower() or 'error' in str(response.url).lower():
                        raise httpx.HTTPStatusError("Redirected to error page", request=response.request, response=response)
                    
                    # Check if the response is actually a PDF
                    content_type = response.headers.get('content-type', '').lower()
                    if 'pdf' in content_type or source_file.file_url.lower().endswith('.pdf'):
                        logger.info(f"Document download completed for user {current_user['username']}, drug: {drug.drug_name}")
                        
                        # Return the PDF as a downloadable file
                        return StreamingResponse(
                            BytesIO(response.content),
                            media_type="application/pdf",
                            headers={"Content-Disposition": f"attachment; filename={filename}"}
                        )
                        
                except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                    logger.warning(f"Failed to download PDF from URL {source_file.file_url}: {e}")
                    # Continue to fallback instead of raising error
                    pass
            
            # If we reach here, the HTTP download failed, so create sample content
            sample_content = f"""FDA Document for {drug.drug_name}

This is a sample document because the original FDA PDF could not be accessed.
The actual document can be found at: {source_file.file_url}

Drug Information:
- Name: {drug.drug_name}
- Manufacturer: {drug.manufacturer}
- Document Type: {drug.document_type}
- Approval Date: {drug.approval_date}
- Submission Number: {drug.submission_number}
- Active Ingredients: {', '.join(drug.active_ingredients) if drug.active_ingredients else 'N/A'}
- Regulatory Classification: {drug.regulatory_classification}

Note: In a production system, this would be the actual FDA document PDF.
The FDA website may block automated downloads for security reasons.
            """
            
            return StreamingResponse(
                BytesIO(sample_content.encode('utf-8')),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename={filename.replace('.pdf', '_info.txt')}"}
            )
        
        else:
            # Handle local file path
            file_path = source_file.file_url
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"Local file not found: {file_path}")
                # Create a sample PDF content for demo purposes
                sample_content = f"""Sample PDF content for {drug.drug_name}
                
This would be the actual FDA document PDF in a production system.

Drug Information:
- Name: {drug.drug_name}
- Manufacturer: {drug.manufacturer}
- Document Type: {drug.document_type}
- Approval Date: {drug.approval_date}

File path: {file_path}
                """
                
                # Return sample content as text file (since we don't have the actual PDF)
                return StreamingResponse(
                    BytesIO(sample_content.encode('utf-8')),
                    media_type="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={filename.replace('.pdf', '.txt')}"}
                )
            
            # Read and return the local file
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                logger.info(f"Document download completed for user {current_user['username']}, drug: {drug.drug_name}")
                
                return StreamingResponse(
                    BytesIO(file_content),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
                
            except Exception as e:
                logger.error(f"Error reading local file {file_path}: {e}")
                raise HTTPException(status_code=500, detail="Error reading local file")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document for drug_id {drug_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Document download error: {str(e)}")

# ============================
# Chat Endpoints
# ============================

@app.post("/api/chat")
async def send_chat_message(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Send a chat message and get AI response about drug information
    """
    try:
        # Handle both single drugId and multiple drugIds
        drug_ids = []
        if request.drugIds:
            # Multiple drug IDs provided
            drug_ids = [str(drug_id) for drug_id in request.drugIds]
        elif request.drugId is not None:
            # Single drug ID provided
            drug_ids = [str(request.drugId)]
        
        logger.info(f"Chat message from user {current_user['username']}: '{request.message[:50]}...' (drug_ids: {drug_ids}, collection_id: {request.collection_id})")
        
        # Generate AI response based on the message and drug/collection context
        ai_response = await generate_chat_response(request.message, drug_ids, request.collection_id, db)
        
        # Return chat response (use first drug ID for compatibility)
        response_drug_id = drug_ids[0] if drug_ids else None
        response = ChatMessageResponse(
            id=str(uuid.uuid4()),
            content=ai_response,
            role="assistant",
            timestamp=datetime.utcnow(),
            drugId=response_drug_id
        )
        
        logger.info(f"Chat response generated for user {current_user['username']}")
        return response
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat service error")

@app.get("/api/chat/history")
async def get_chat_history(
    drugId: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user_dependency)
):
    """
    Get chat history for the user, optionally filtered by drug ID
    """
    try:
        logger.info(f"Chat history request from user {current_user['username']} (drug_id: {drugId}, limit: {limit})")
        
        # For now, return empty history since we don't have chat storage implemented
        # In a full implementation, you would query a ChatHistory table
        history = []
        
        logger.info(f"Chat history retrieved: {len(history)} messages")
        return history
        
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat history error")

# Helper function to generate AI responses
async def generate_chat_response(message: str, drug_ids: List[str], collection_id: Optional[int], db: Session) -> str:
    """
    Generate an AI response using ChromaDB RAG functionality
    """
    try:
        # Initialize ChromaDB utility
        qdrant_util = ChromaDBUtil.get_instance(use_persistent_client=True)
        
        # Prepare filter for specific drugs or collection
        filter_dict = None
        context = ""
        
        if collection_id:
            # Get all documents in the collection
            from database.database import collection_document_association
            
            # Get source file IDs that belong to the collection
            collection_docs = db.query(collection_document_association.c.document_id).filter(
                collection_document_association.c.collection_id == collection_id
            ).all()
            
            if collection_docs:
                source_file_ids = [doc[0] for doc in collection_docs]
                # Create filter for ChromaDB to focus on documents in this collection
                filter_dict = {"source_file_id": {"$in": [str(id) for id in source_file_ids]}}
                
                # Get collection name for context
                collection = db.query(Collection).filter(Collection.id == collection_id).first()
                if collection:
                    context = f"Questions about documents in collection '{collection.name}'"
                    logger.info(f"Chat query with collection context: {context}")
            else:
                logger.warning(f"Collection {collection_id} has no documents")
                
        elif drug_ids:
            try:
                # Get drug information from database
                drugs = db.query(FDAExtractionResults).filter(FDAExtractionResults.id.in_(drug_ids)).all()
                if drugs:
                    drug_names = [drug.drug_name for drug in drugs]
                    context = f"Questions about {' and '.join(drug_names)}"
                    # Create filter for ChromaDB to focus on these specific drugs
                    filter_dict = {"drug_name": {"$in": drug_names}}
                    logger.info(f"Chat query with drug context: {context}")
                else:
                    logger.warning(f"Drugs with IDs {drug_ids} not found in database")
            except Exception as e:
                logger.error(f"Error retrieving drug context: {e}")
        
        # Use ChromaDB's RAG functionality to generate response
        logger.info(f"Querying ChromaDB with message: '{message[:100]}...'")
        
        # Enhance the query with context if available
        enhanced_query = f"{context}: {message}" if context else message
        
        response = qdrant_util.query_with_llm(
            query=enhanced_query,
            collection_name="fda_documents",
            n_results=5,
            filter_dict=filter_dict,
            chat_history=None  # Could be enhanced to store chat history
        )
        
        logger.info(f"ChromaDB response generated: {len(response)} characters")
        return response
        
    except Exception as e:
        logger.error(f"Error in ChromaDB query: {str(e)}")
        # Fallback to simple response if ChromaDB fails
        if "hello" in message.lower() or "hi" in message.lower():
            return "Hello! I'm your FDA drug information assistant powered by AI. How can I help you with drug information today?"
        elif "side effect" in message.lower() or "adverse" in message.lower():
            return "I can help you with side effect information. Please note that you should always consult with a healthcare provider for medical advice."
        elif "dosage" in message.lower() or "dose" in message.lower():
            return "For dosage information, please refer to the official prescribing information and consult with a healthcare provider for personalized recommendations."
        else:
            return "I'm here to help with FDA drug information. Please ask me about drug indications, dosages, side effects, or other regulatory information."

# ============================
# Document Data Endpoints
# ============================

@app.get("/api/source-files/{file_id}/documents")
async def get_source_file_documents(
    file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get all document chunks for a source file with their metadata."""
    try:
        from database.database import DocumentData
        import json
        
        # Verify source file exists
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Get all document chunks for this source file
        documents = db.query(DocumentData).filter(
            DocumentData.source_file_id == file_id
        ).order_by(DocumentData.id).all()
        
        documents_data = []
        for doc in documents:
            try:
                # Parse metadata JSON
                metadata = json.loads(doc.metadata_content) if doc.metadata_content else {}
            except json.JSONDecodeError:
                metadata = {"error": "Invalid JSON in metadata_content"}
            
            documents_data.append({
                "id": doc.id,
                "doc_content": doc.doc_content,
                "metadata": metadata,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat()
            })
        
        return {
            "source_file": {
                "id": source_file.id,
                "file_name": source_file.file_name,
                "file_url": source_file.file_url,
                "drug_name": source_file.drug_name,
                "status": source_file.status
            },
            "documents": documents_data,
            "total_documents": len(documents_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source file documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Bulk Upload Endpoints
# ============================

class BulkUploadItem(BaseModel):
    file_name: str
    file_url: str
    drug_name: Optional[str] = Field(None)
    comments: Optional[str] = Field(None)
    us_ma_date: Optional[str] = Field(None)

class BulkUploadRequest(BaseModel):
    items: List[BulkUploadItem]

@app.post("/api/source-files/bulk-upload")
async def bulk_upload_source_files(
    request: BulkUploadRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Bulk upload multiple source files."""
    try:
        from database.database import SourceFiles
        
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
                    failed_items.append({
                        "row": idx + 1,
                        "item": item.dict(),
                        "error": f"File with name '{item.file_name}' already exists"
                    })
                    continue
                
                # Create new source file
                new_file = SourceFiles(
                    file_name=item.file_name,
                    file_url=item.file_url,
                    drug_name=item.drug_name,
                    comments=item.comments,
                    us_ma_date=item.us_ma_date,
                    status="PENDING",
                    created_by=current_user["user_id"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(new_file)
                db.flush()  # Flush to get the ID
                
                success_items.append({
                    "row": idx + 1,
                    "id": new_file.id,
                    "file_name": new_file.file_name,
                    "drug_name": new_file.drug_name
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
        
        logger.info(f"Bulk upload completed by {current_user['username']}: {len(success_items)} success, {len(failed_items)} failed")
        
        return {
            "success": True,
            "total_items": len(request.items),
            "successful_items": len(success_items),
            "failed_items": len(failed_items),
            "success_details": success_items,
            "failure_details": failed_items
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================
# Metadata Configuration Export/Import Endpoints
# ============================

class MetadataConfigResponse(BaseModel):
    id: int
    metadata_name: str
    description: str
    extraction_prompt: str
    is_active: bool
    data_type: str
    validation_rules: Optional[str] = Field(None)
    created_by: int
    created_at: datetime
    updated_at: datetime

class MetadataConfigCreate(BaseModel):
    metadata_name: str
    description: str
    extraction_prompt: str
    data_type: str = Field("text")
    validation_rules: Optional[str] = Field(None)
    is_active: bool = Field(True)

def refresh_metadata():
    """Refresh SQLAlchemy metadata to pick up schema changes"""
    try:
        from src.database.database import Base, engine
        
        # Force SQLAlchemy to re-inspect the database
        inspector = inspect(engine)
        
        # Clear the existing metadata
        Base.metadata.clear()
        
        # Create a new connection to ensure fresh state
        with engine.connect() as conn:
            # Verify the columns exist in the database
            columns = inspector.get_columns('MetadataConfiguration')
            column_names = [col['name'] for col in columns]
            logger.info(f"Available columns in MetadataConfiguration: {column_names}")
            
            if 'data_type' not in column_names or 'validation_rules' not in column_names:
                logger.error("Missing columns in MetadataConfiguration table")
                # Try to add missing columns directly
                if 'data_type' not in column_names:
                    conn.execute(text("ALTER TABLE MetadataConfiguration ADD COLUMN data_type VARCHAR(50) DEFAULT 'text' NOT NULL"))
                if 'validation_rules' not in column_names:
                    conn.execute(text("ALTER TABLE MetadataConfiguration ADD COLUMN validation_rules TEXT"))
                conn.commit()
                logger.info("Added missing columns to MetadataConfiguration table")
        
        # Recreate the metadata with fresh schema
        Base.metadata.reflect(bind=engine)
        logger.info("Database metadata refreshed successfully")
        
    except Exception as e:
        logger.error(f"Failed to refresh metadata: {e}")
        raise

# Commented out - handled by metadata_configs_compat router
# The metadata-configs endpoints have been moved to metadata_configs_compat router

# Create endpoint moved to metadata_configs_compat router

# Update endpoint moved to metadata_configs_compat router

# Delete endpoint moved to metadata_configs_compat router

# Export endpoint moved to metadata_configs_compat router
# The export functionality is now handled by the metadata_configs_compat router

# Import endpoint moved to metadata_configs_compat router
# The import functionality is now handled by the metadata_configs_compat router

# ============================
# New Search Endpoints
# ============================

class SearchRequest(BaseModel):
    query: str
    drug_name: Optional[str] = None
    collection_id: Optional[int] = None
    source_file_id: Optional[int] = None
    page: int = 1
    page_size: int = 20  # Default page size to prevent loading too many results

@app.post("/api/chat/search")
async def search_documents(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Search FDA documents by drug name with SQL first, then vector search fallback."""
    try:
        # Calculate offset from page and page_size
        offset = (request.page - 1) * request.page_size
        
        # Perform search with user_id for history tracking
        result = FDAChatManagementService.search_fda_documents(
            search_query=request.query,
            user_id=current_user["user_id"],
            drug_name=request.drug_name,
            collection_id=request.collection_id,
            source_file_id=request.source_file_id,
            limit=request.page_size,
            offset=offset,
            db=db
        )
        
        # Add pagination metadata to response
        total_pages = (result.get("total_results", 0) + request.page_size - 1) // request.page_size
        result["pagination"] = {
            "page": request.page,
            "page_size": request.page_size,
            "total_pages": total_pages,
            "has_next": request.page < total_pages,
            "has_previous": request.page > 1
        }
        
        return result
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/drug-names")
async def get_unique_drug_names(
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get all unique drug names from SourceFiles for filter dropdown."""
    try:
        drug_names = FDAChatManagementService.get_unique_drug_names(db)
        return {
            "success": True,
            "drug_names": drug_names
        }
    except Exception as e:
        logger.error(f"Error getting drug names: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get dynamic dashboard statistics from database."""
    try:
        from sqlalchemy import func, distinct
        from database.database import DrugMetadata
        
        # Get total unique drugs from DrugMetadata where metadata_name = 'Drug Name'
        total_drugs = db.query(func.count(distinct(DrugMetadata.value))).filter(
            DrugMetadata.metadata_name == "Drug Name",
            DrugMetadata.value.isnot(None),
            DrugMetadata.value != ""
        ).scalar() or 0
        
        # Get top 10 drug names
        top_drugs = db.query(DrugMetadata.value, func.count(DrugMetadata.id).label('count')).filter(
            DrugMetadata.metadata_name == "Drug Name",
            DrugMetadata.value.isnot(None),
            DrugMetadata.value != ""
        ).group_by(DrugMetadata.value).order_by(func.count(DrugMetadata.id).desc()).limit(10).all()
        
        # Get total unique manufacturers from DrugMetadata where metadata_name = 'Manufacturer'
        total_manufacturers = db.query(func.count(distinct(DrugMetadata.value))).filter(
            DrugMetadata.metadata_name == "Manufacturer",
            DrugMetadata.value.isnot(None),
            DrugMetadata.value != ""
        ).scalar() or 0
        
        # Get top 10 manufacturer names
        top_manufacturers = db.query(DrugMetadata.value, func.count(DrugMetadata.id).label('count')).filter(
            DrugMetadata.metadata_name == "Manufacturer",
            DrugMetadata.value.isnot(None),
            DrugMetadata.value != ""
        ).group_by(DrugMetadata.value).order_by(func.count(DrugMetadata.id).desc()).limit(10).all()
        
        # Get recent approvals - count source files added in last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_approvals = db.query(SourceFiles).filter(
            SourceFiles.created_at >= thirty_days_ago
        ).count()
        
        # Get total searches from SearchHistory
        total_searches = db.query(SearchHistory).count()
        
        # Additional statistics
        # Get total source files
        total_source_files = db.query(SourceFiles).count()
        
        # Get processed files count
        processed_files = db.query(SourceFiles).filter(
            SourceFiles.status.in_(["INDEXED", "DOCUMENT_STORED", "METADATA_EXTRACTED"])
        ).count()
        
        # Get total metadata entries
        total_metadata_entries = db.query(DrugMetadata).count()
        
        # Get search statistics for last 7 days
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_searches = db.query(SearchHistory).filter(
            SearchHistory.search_timestamp >= seven_days_ago
        ).count()
        
        # Get most searched drugs (from SearchHistory filters)
        trending_drugs = []
        search_filters = db.query(SearchHistory.filters_applied).filter(
            SearchHistory.filters_applied.isnot(None)
        ).all()
        
        drug_search_counts = {}
        for (filters,) in search_filters:
            if filters and isinstance(filters, dict) and 'drug_name' in filters:
                drug_name = filters['drug_name']
                if drug_name:
                    drug_search_counts[drug_name] = drug_search_counts.get(drug_name, 0) + 1
        
        # Get top 5 trending drugs
        trending_drugs = sorted(drug_search_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_drugs": total_drugs,
            "total_manufacturers": total_manufacturers,
            "recent_approvals": recent_approvals,
            "total_searches": total_searches,
            "additional_stats": {
                "total_source_files": total_source_files,
                "processed_files": processed_files,
                "total_metadata_entries": total_metadata_entries,
                "recent_searches_7d": recent_searches,
                "trending_drugs": [{"drug_name": name, "search_count": count} for name, count in trending_drugs],
                "top_drugs": [{"name": drug[0], "count": drug[1]} for drug in top_drugs],
                "top_manufacturers": [{"name": manuf[0], "count": manuf[1]} for manuf in top_manufacturers]
            },
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Drug Metadata Endpoints
# ============================

@app.get("/api/drugs/{source_file_id}/metadata")
async def get_drug_metadata(
    source_file_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get all metadata for a specific drug/source file."""
    try:
        from database.database import DrugMetadata
        
        # Get source file details
        source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Get all metadata for this source file
        metadata_entries = db.query(DrugMetadata).filter(
            DrugMetadata.source_file_id == source_file_id
        ).order_by(DrugMetadata.metadata_name).all()
        
        # Format response
        metadata_list = []
        for entry in metadata_entries:
            metadata_list.append({
                "id": entry.id,
                "metadata_name": entry.metadata_name,
                "value": entry.value,
                "drugname": entry.drugname,
                "source_file_id": entry.source_file_id,
                "file_url": entry.file_url,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "metadata_details": entry.metadata_details
            })
        
        return {
            "source_file": {
                "id": source_file.id,
                "file_name": source_file.file_name,
                "file_url": source_file.file_url,
                "drug_name": source_file.drug_name,
                "status": source_file.status
            },
            "metadata": metadata_list,
            "total_count": len(metadata_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drug metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# User Management Endpoints
# ============================

class SetPasswordRequest(BaseModel):
    password: str

@app.post("/api/auth/users/{user_id}/set-password")
async def set_user_password(
    user_id: int,
    request: SetPasswordRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Set password for a user (admin only)."""
    try:
        # Check if current user is admin
        # Handle both dict and Users object cases
        user_role = current_user['role']
        user_username = current_user['username']
        
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Only administrators can set user passwords")
        
        # Get the user
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Hash the new password
        from src.services.password_utils import hash_password
        user.password_hash = hash_password(request.password)
        user.updated_at = datetime.now()
        
        db.commit()
        
        logger.info(f"Password set for user {user.username} by admin {user_username}")
        
        return {
            "success": True,
            "message": f"Password successfully set for user {user.username}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user password: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set password: {str(e)}")

# ============================
# Health Check Endpoints
# ============================

@app.get("/api/health")
async def health_check():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/templates/bulk-upload")
async def get_bulk_upload_template():
    """Get a sample template for bulk upload as XLSX file. Public endpoint - no authentication required."""
    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse
    
    # Template data
    template_data = [
        {
            "file_name": "example_drug_label.pdf",
            "file_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/example.pdf",
            "drug_name": "Example Drug Name",
            "comments": "Example description of the drug document"
        },
        {
            "file_name": "another_drug_label.pdf", 
            "file_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/another_example.pdf",
            "drug_name": "Another Drug",
            "comments": "Another example entry"
        }
    ]
    
    # Create DataFrame
    df = pd.DataFrame(template_data)
    
    # Create Excel file in memory
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Write template data
        df.to_excel(writer, sheet_name='Template', index=False)
        
        # Add instructions sheet
        instructions_data = [
            {
                "Field": "file_name",
                "Required": "Yes",
                "Description": "The name of the PDF file (must be unique)"
            },
            {
                "Field": "file_url", 
                "Required": "Yes",
                "Description": "The direct URL to the PDF document"
            },
            {
                "Field": "drug_name",
                "Required": "No", 
                "Description": "The name of the drug (helps with categorization)"
            },
            {
                "Field": "comments",
                "Required": "No",
                "Description": "Additional notes or description about the document"
            }
        ]
        instructions_df = pd.DataFrame(instructions_data)
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
    
    excel_buffer.seek(0)
    
    return StreamingResponse(
        io.BytesIO(excel_buffer.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=source_files_template.xlsx"}
    )

@app.get("/api/health/database")
async def database_health_check(db: Session = Depends(get_db)):
    """Database connectivity health check."""
    try:
        from database.database import FDAExtractionResults
        count = db.query(FDAExtractionResults).count()
        return {
            "status": "healthy",
            "database": "connected",
            "total_records": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")

@app.get("/api/health/pool")
async def pool_health_check():
    """Database connection pool health check."""
    try:
        status = get_pool_status()
        total_connections = status.get("total_connections", 0)
        checked_out = status.get("checked_out", 0)
        
        # Calculate utilization safely
        if total_connections > 0:
            utilization = (checked_out / total_connections) * 100
            
            # Determine health status based on utilization
            if utilization > 90:
                health_status = "critical"
            elif utilization > 75:
                health_status = "warning"
            else:
                health_status = "healthy"
        else:
            utilization = 0
            health_status = "healthy"
        
        return {
            "status": health_status,
            "pool_utilization": f"{utilization:.1f}%",
            "pool_details": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Pool health check failed: {e}")
        raise HTTPException(status_code=503, detail="Pool health check failed")

@app.post("/api/admin/cleanup-sessions")
async def cleanup_sessions(current_user: dict = Depends(get_current_user_dependency)):
    """Admin endpoint to cleanup expired database sessions."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Log status before cleanup
        pre_status = get_pool_status()
        
        # Perform cleanup
        cleanup_expired_sessions()
        
        # Log status after cleanup
        post_status = get_pool_status()
        
        return {
            "success": True,
            "message": "Session cleanup completed",
            "pre_cleanup": pre_status,
            "post_cleanup": post_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise HTTPException(status_code=500, detail="Session cleanup failed")

# ============================
# Startup Events
# ============================

# Note: Startup logic has been moved to the lifespan context manager

def ensure_metadata_config_schema():
    """Ensure MetadataConfiguration table has the required columns"""
    try:
        from src.database.database import engine
        
        inspector = inspect(engine)
        columns = inspector.get_columns('MetadataConfiguration')
        column_names = [col['name'] for col in columns]
        
        with engine.connect() as conn:
            if 'data_type' not in column_names:
                logger.info("Adding missing data_type column to MetadataConfiguration")
                conn.execute(text("ALTER TABLE MetadataConfiguration ADD COLUMN data_type VARCHAR(50) DEFAULT 'text' NOT NULL"))
                
            if 'validation_rules' not in column_names:
                logger.info("Adding missing validation_rules column to MetadataConfiguration")
                conn.execute(text("ALTER TABLE MetadataConfiguration ADD COLUMN validation_rules TEXT"))
            
            conn.commit()
            
        logger.info("MetadataConfiguration schema verification complete")
        
    except Exception as e:
        logger.error(f"Failed to ensure MetadataConfiguration schema: {e}")

@app.post("/api/source-files/{file_id}/reprocess")
async def reprocess_source_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Reprocess a source file by clearing existing data and restarting processing.
    
    Steps:
    1. Clear DocumentData entries for this source file
    2. Clear ChromaDB vector data for this source file
    3. Set status to PENDING
    4. Start processing in background
    """
    try:
        # Get source file
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        logger.info(f"Starting reprocess for source file {file_id}: {source_file.file_name}")
        
        # Step 1: Clear DocumentData entries for this source file
        try:
            deleted_docs = db.query(DocumentData).filter(DocumentData.source_file_id == file_id).delete()
            logger.info(f"Deleted {deleted_docs} DocumentData entries for source file {file_id}")
        except Exception as e:
            logger.warning(f"Error deleting DocumentData entries: {e}")
        
        # Step 2: Clear FDAExtractionResults for this source file
        try:
            deleted_extractions = db.query(FDAExtractionResults).filter(FDAExtractionResults.source_file_id == file_id).delete()
            logger.info(f"Deleted {deleted_extractions} FDAExtractionResults entries for source file {file_id}")
        except Exception as e:
            logger.warning(f"Error deleting FDAExtractionResults entries: {e}")
        
        # Step 3: Clear ChromaDB vector data for this source file
        try:
            qdrant_util = QdrantUtil()
            result = qdrant_util.delete_documents_by_source_file(
                source_file_name=source_file.file_name,
                collection_name="fda_documents"
            )
            logger.info(f"ChromaDB cleanup result: {result}")
        except Exception as e:
            logger.warning(f"Error clearing ChromaDB data: {e}")
        
        # Step 4: Set status to PENDING
        update_source_file_status(
            db, 
            file_id, 
            "PENDING", 
            f"File queued for reprocessing by {current_user.get('username', 'unknown')}"
        )
        
        # Step 5: Start processing in background
        background_tasks.add_task(
            process_file_background, 
            file_id, 
            current_user.get("username", "unknown")
        )
        
        logger.info(f"✅ Source file {file_id} queued for reprocessing")
        
        return {
            "success": True,
            "message": f"Source file '{source_file.file_name}' has been cleared and queued for reprocessing",
            "file_id": file_id,
            "status": "PENDING"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error reprocessing source file {file_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess source file: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8090,  # Use specified port
        reload=True,
        log_level="info"
    ) 