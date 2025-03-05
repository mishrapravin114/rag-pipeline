import os
import sys
import json
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, Text, String, DateTime, func, JSON, Boolean, Float, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path to import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

# Database configuration
DATABASE_URL = settings.DATABASE_URL

# Configure engine with connection pooling settings to prevent timeout
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.environ.get('SQLALCHEMY_POOL_SIZE', 15)),           # Increase pool size
    max_overflow=int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', 30)),     # Increase overflow
    pool_timeout=int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', 60)),     # Pool timeout
    pool_recycle=int(os.environ.get('SQLALCHEMY_POOL_RECYCLE', 3600)),   # Recycle connections after 1 hour
    pool_pre_ping=bool(os.environ.get('SQLALCHEMY_POOL_PRE_PING', 'true').lower() == 'true'),  # Validate connections before use
    echo_pool=bool(os.environ.get('SQLALCHEMY_ECHO_POOL', 'false').lower() == 'true')          # Enable pool debugging if needed
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Configure logging for database operations
logger = logging.getLogger(__name__)

# Association table for many-to-many relationship between Collections and SourceFiles
collection_document_association = Table(
    'collection_document_association',
    Base.metadata,
    Column('collection_id', Integer, ForeignKey('collections.id'), primary_key=True),
    Column('document_id', Integer, ForeignKey('SourceFiles.id'), primary_key=True),
    Column('indexed_at', DateTime, nullable=True),
    Column('indexing_status', String(50), default='pending'),
    Column('indexing_progress', Integer, default=0),
    Column('error_message', Text, nullable=True),
    Column('vector_doc_id', String(255), nullable=True)
)

# Association table for many-to-many relationship between MetadataGroups and MetadataConfiguration
metadata_group_configs = Table(
    'metadata_group_configs',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('metadata_groups.id'), primary_key=True),
    Column('config_id', Integer, ForeignKey('MetadataConfiguration.id'), primary_key=True),
    Column('display_order', Integer, default=0, nullable=False),
    Column('added_at', DateTime, default=datetime.utcnow),
    Column('added_by', Integer, ForeignKey('Users.id'), nullable=True)
)

class Collection(Base):
    __tablename__ = 'collections'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    vector_db_collection_name = Column(String(255), unique=True, nullable=True)
    indexing_stats = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to SourceFiles
    documents = relationship("SourceFiles", secondary=collection_document_association, back_populates="collections")
    
    def __repr__(self):
        return f"<Collection(name={self.name}, documents_count={len(self.documents)})>"

class Users(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(username={self.username}, email={self.email}, role={self.role})>"

class MetadataConfiguration(Base):
    __tablename__ = "MetadataConfiguration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metadata_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    extraction_prompt = Column(Text, nullable=False)
    extraction_prompt_version = Column(Integer, nullable=False, default=1)
    data_type = Column(String(50), nullable=False, default="text")
    validation_rules = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    creator = relationship("Users", backref="metadata_configs")
    groups = relationship("MetadataGroup", secondary="metadata_group_configs", back_populates="configurations")

class FileMetadataMapping(Base):
    __tablename__ = "FileMetadataMapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("SourceFiles.id"), nullable=False)
    metadata_name = Column(String(255), nullable=False)
    metadata_actual_content = Column(Text, nullable=True)
    metadata_summary = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    source_file = relationship("SourceFiles", backref="metadata_mappings")
    creator = relationship("Users", backref="created_mappings")

    __table_args__ = (
        {'extend_existing': True}
    )

class SourceFiles(Base):
    __tablename__ = "SourceFiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(Text, nullable=False)
    file_url = Column(Text, nullable=False)
    entity_name = Column(Text, nullable=True)  # Generic: was entity_name
    entity_name = Column(Text, nullable=True)  # Backward compatibility: use entity_name
    status = Column(String(50), nullable=False, default="PENDING")
    metadata_extracted = Column(Boolean, nullable=False, default=False)  # NEW COLUMN for metadata extraction status
    comments = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=True)  # Nullable for existing records
    us_ma_date = Column(String(10), nullable=True)  # NEW COLUMN for US MA date in DD/MM/YYYY format
    vector_db_collections = Column(JSON, default=[])  # Track which collections this document is indexed in
    extracted_content = Column(JSON, nullable=True)  # Stores extracted metadata content as JSON
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    creator = relationship("Users", backref="source_files")
    document_data = relationship("DocumentData", back_populates="source_file", cascade="all, delete-orphan")
    # Generic relationship (preferred)
    entity_metadata = relationship("EntityMetadata", back_populates="source_file", cascade="all, delete-orphan")
    # Backward compatibility
    entity_metadata = entity_metadata  # Alias for backward compatibility
    # Relationship to Collections
    collections = relationship("Collection", secondary=collection_document_association, back_populates="documents")

# Generic EntityMetadata model (preferred)
class EntityMetadata(Base):
    __tablename__ = "EntityMetadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metadata_name = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    entity_name = Column(String(255), nullable=True)  # Generic: was entityname
    # Backward compatibility
    entityname = Column(String(255), nullable=True)  # Deprecated: use entity_name
    source_file_id = Column(Integer, ForeignKey("SourceFiles.id"), nullable=False)
    file_url = Column(Text, nullable=False)
    extracted_by = Column(Integer, ForeignKey("Users.id"), nullable=True)
    extraction_prompt = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    metadata_details = Column(Text, nullable=True)
    # Generic flexible fields
    attributes = Column(JSON, nullable=True)  # Generic attributes (was active_ingredient, etc.)
    properties = Column(JSON, nullable=True)  # Generic properties (was dosage_form, etc.)
    features = Column(JSON, nullable=True)  # Generic features (was side_effects, etc.)
    use_cases = Column(JSON, nullable=True)  # Generic use cases (was indications, etc.)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    source_file = relationship("SourceFiles", back_populates="entity_metadata")
    extractor = relationship("Users", backref="extracted_metadata")

# Backward compatibility alias
EntityMetadata = EntityMetadata

class FDAExtractionResults(Base):
    __tablename__ = "FDAExtractionResults"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, nullable=False)
    file_name = Column(Text, nullable=False)
    document_type = Column(Text, nullable=True)
    entity_name = Column(Text, nullable=True)
    active_ingredients = Column(JSON, nullable=True)  # Store as JSON array
    manufacturer = Column(Text, nullable=True)
    approval_date = Column(Text, nullable=True)
    submission_number = Column(Text, nullable=True)
    regulatory_classification = Column(Text, nullable=True)
    extraction_metadata = Column(JSON, nullable=True)  # Store processing metadata
    full_metadata = Column(JSON, nullable=True)  # Store complete metadata JSON
    elements_count = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=True)  # Nullable for existing records
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    creator = relationship("Users", backref="extraction_results")

class DocumentData(Base):
    __tablename__ = "DocumentData"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, ForeignKey("SourceFiles.id"), nullable=False)
    file_name = Column(Text, nullable=False)
    doc_content = Column(Text, nullable=False)  # Page content for ChromaDB
    metadata_content = Column(Text, nullable=False)  # Metadata as JSON string
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    source_file = relationship("SourceFiles", back_populates="document_data")

    def __repr__(self):
        return f"<DocumentData(source_file_id={self.source_file_id}, file_name={self.file_name}, doc_content={self.doc_content[:50]}...)>"

class ChatHistory(Base):
    __tablename__ = "ChatHistory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    session_id = Column(String(100), nullable=False)
    user_query = Column(Text, nullable=False)  # Changed to LONGTEXT in DB
    request_details = Column(Text, nullable=True)  # JSON string - Changed to LONGTEXT in DB
    response_details = Column(Text, nullable=True)  # JSON string - Changed to LONGTEXT in DB
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

class ShareChat(Base):
    __tablename__ = "ShareChat"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    share_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    messages = Column(JSON, nullable=False)  # Store messages as JSON
    password_hash = Column(String(255), nullable=True)  # Optional password protection
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    
    # Relationship to Users
    creator = relationship("Users", backref="shared_chats")

# New models for frontend support
class SearchHistory(Base):
    __tablename__ = "SearchHistory"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100))  # Simple username tracking
    search_query = Column(Text, nullable=False)
    search_type = Column(String(50))
    filters_applied = Column(JSON)
    results_count = Column(Integer)
    search_timestamp = Column(DateTime, default=func.now())
    session_id = Column(String(255))
    execution_time_ms = Column(Integer)

class TrendingSearches(Base):
    __tablename__ = "TrendingSearches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_term = Column(String(500), nullable=False)
    search_type = Column(String(50))
    frequency = Column(Integer, default=1)
    time_period = Column(String(20))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    last_updated = Column(DateTime, default=func.now())

# Generic DocumentSections model (preferred)
class DocumentSections(Base):
    __tablename__ = "DocumentSections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, ForeignKey("SourceFiles.id"), nullable=False)
    entity_name = Column(String(500))  # Generic: was entity_name
    # Backward compatibility
    entity_name = Column(String(500))  # Deprecated: use entity_name
    section_type = Column(String(100))
    section_title = Column(String(500))
    section_content = Column(Text)
    section_order = Column(Integer, default=0)
    extraction_confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=func.now())

# Backward compatibility alias
EntitySections = DocumentSections

class IndexingJob(Base):
    __tablename__ = "indexing_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), unique=True, nullable=False)  # UUID
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=True)
    total_documents = Column(Integer, nullable=False)
    processed_documents = Column(Integer, default=0)
    failed_documents = Column(Integer, default=0)
    status = Column(String(50), nullable=False, default='pending')  # pending, processing, completed, failed, cancelled
    job_type = Column(String(50), nullable=False)  # index, reindex, remove
    options = Column(JSON, default={})
    error_details = Column(JSON, default=[])
    created_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    collection = relationship("Collection", backref="indexing_jobs")
    user = relationship("Users", backref="indexing_jobs")
    
    def __repr__(self):
        return f"<IndexingJob(job_id={self.job_id}, status={self.status}, progress={self.processed_documents}/{self.total_documents})>"

class MetadataGroup(Base):
    __tablename__ = "metadata_groups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=False, default='#3B82F6')
    tags = Column(JSON, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("Users", backref="metadata_groups")
    configurations = relationship("MetadataConfiguration", secondary="metadata_group_configs", back_populates="groups")
    
    def __repr__(self):
        return f"<MetadataGroup(id={self.id}, name={self.name}, is_default={self.is_default})>"

class CollectionExtractionJob(Base):
    __tablename__ = "collection_extraction_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("metadata_groups.id"), nullable=False)
    status = Column(String(50), nullable=True, default='pending')  # Using String instead of ENUM for flexibility
    total_documents = Column(Integer, default=0)
    processed_documents = Column(Integer, default=0)
    failed_documents = Column(Integer, default=0)
    extracted_content = Column(JSON, nullable=True)  # Stores aggregated extracted content for the job
    error_details = Column(JSON, nullable=True)  # Stores error details for failed documents
    created_by = Column(Integer, ForeignKey("Users.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True, default=func.now())
    
    # Relationships
    collection = relationship("Collection", backref="extraction_jobs")
    group = relationship("MetadataGroup", backref="extraction_jobs")
    creator = relationship("Users", backref="extraction_jobs")
    
    def __repr__(self):
        return f"<CollectionExtractionJob(id={self.id}, status={self.status}, progress={self.processed_documents}/{self.total_documents})>"

class ExtractionHistory(Base):
    __tablename__ = "extraction_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("SourceFiles.id"), nullable=False)
    config_id = Column(Integer, ForeignKey("MetadataConfiguration.id"), nullable=False)
    prompt_version = Column(Integer, nullable=False)
    extracted_value = Column(JSON, nullable=True)
    extraction_date = Column(DateTime, nullable=False, default=func.now())
    success = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    document = relationship("SourceFiles", backref="extraction_history")
    configuration = relationship("MetadataConfiguration", backref="extraction_history")
    
    def __repr__(self):
        return f"<ExtractionHistory(document_id={self.document_id}, config_id={self.config_id}, version={self.prompt_version}, success={self.success})>"

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get database session for direct use"""
    return SessionLocal()

@contextmanager
def database_session():
    """
    Context manager for database sessions with proper resource management.
    
    Usage:
        with database_session() as db:
            # Use db session
            pass
    """
    db = SessionLocal()
    session_id = id(db)
    logger.debug(f"Database session created: {session_id}")
    
    try:
        yield db
        db.commit()
        logger.debug(f"Database session committed: {session_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database session rollback: {session_id}, Error: {e}")
        raise
    finally:
        db.close()
        logger.debug(f"Database session closed: {session_id}")

def get_db_with_cleanup():
    """
    Generator function that provides a database session with guaranteed cleanup.
    This is an alternative to database_session() context manager for use in services.
    """
    db = SessionLocal()
    session_id = id(db)
    logger.debug(f"Database session created (with cleanup): {session_id}")
    
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {session_id}, Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug(f"Database session closed (with cleanup): {session_id}")

def get_pool_status():
    """
    Get current connection pool status for monitoring.
    
    Returns:
        dict: Pool status information
    """
    pool = engine.pool
    try:
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow(),
            "available_connections": pool.size() - pool.checkedout(),
            "pool_timeout": getattr(pool, '_timeout', 'N/A'),
            "pool_recycle": getattr(pool, '_recycle', 'N/A')
        }
    except AttributeError as e:
        logger.warning(f"Pool status attribute error: {e}")
        # Return basic info if detailed stats aren't available
        return {
            "pool_size": getattr(pool, 'size', lambda: 'N/A')(),
            "checked_in": getattr(pool, 'checkedin', lambda: 'N/A')(),
            "checked_out": getattr(pool, 'checkedout', lambda: 'N/A')(),
            "overflow": getattr(pool, 'overflow', lambda: 'N/A')(),
            "total_connections": "N/A",
            "available_connections": "N/A",
            "pool_timeout": "N/A",
            "pool_recycle": "N/A"
        }

def log_pool_status(level="INFO"):
    """
    Log current pool status for monitoring.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    try:
        status = get_pool_status()
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"Connection Pool Status: {status}")
    except Exception as e:
        logger.error(f"Failed to get pool status: {e}")

def cleanup_expired_sessions():
    """
    Cleanup utility for expired or orphaned sessions.
    This can be called periodically to ensure proper resource management.
    """
    try:
        # Force connection pool to recycle old connections
        engine.pool.recreate()
        logger.info("Connection pool recreated - expired sessions cleaned up")
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")

def monitor_session_usage():
    """
    Monitor and log session usage patterns for debugging.
    """
    try:
        status = get_pool_status()
        
        # Handle case where total_connections might be 0 or negative
        total_connections = status.get("total_connections", 0)
        checked_out = status.get("checked_out", 0)
        
        if total_connections > 0:
            utilization = (checked_out / total_connections) * 100
            if utilization > 80:
                logger.warning(f"High pool utilization: {utilization:.1f}% ({checked_out}/{total_connections})")
            
            # Log info about current usage
            logger.info(f"Pool utilization: {utilization:.1f}% - Available: {status['available_connections']}")
        else:
            logger.info(f"Pool status: {checked_out} checked out, {status['available_connections']} available")
        
    except Exception as e:
        logger.error(f"Session monitoring failed: {e}")

def save_extraction_results(db, file_id: int, file_name: str, metadata: dict, elements_count: int) -> int:
    """Save extraction results to the database"""
    try:
        # Only use summary/search fields, not deprecated sectioned fields
        extraction_result = FDAExtractionResults(
            source_file_id=file_id,
            file_name=file_name,
            document_type=metadata.get("document_type"),
            entity_name=metadata.get("entity_name"),
            active_ingredients=metadata.get("active_ingredients"),
            manufacturer=metadata.get("manufacturer"),
            approval_date=metadata.get("approval_date"),
            submission_number=metadata.get("submission_number"),
            regulatory_classification=metadata.get("regulatory_classification"),
            extraction_metadata=metadata.get("processing_metadata"),
            full_metadata=metadata,
            elements_count=elements_count
        )
        db.add(extraction_result)
        db.commit()
        db.refresh(extraction_result)
        return extraction_result.id
    except Exception as e:
        db.rollback()
        raise Exception(f"Error saving extraction results: {e}")

def update_source_file_status(db, file_id: int, status: str, comments: str = None):
    """Update the status of a source file"""
    try:
        source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
        if source_file:
            source_file.status = status
            if comments:
                source_file.comments = comments
            source_file.updated_at = datetime.now()
            db.commit()
    except Exception as e:
        db.rollback()
        raise Exception(f"Error updating source file status: {e}")

def get_pending_files(db):
    """Get all pending files from the database"""
    return db.query(SourceFiles).filter(SourceFiles.status == "PENDING").all()

def save_documents_to_db(db, source_file_id: int, file_name: str, documents: List[Dict[str, Any]]) -> List[int]:
    """Save documents to the database for ChromaDB format"""
    try:
        document_ids = []
        
        for doc in documents:
            # Create document record
            doc_record = DocumentData(
                source_file_id=source_file_id,
                file_name=file_name,
                doc_content=doc["page_content"],
                metadata_content=json.dumps(doc["metadata"])
            )
            
            db.add(doc_record)
            db.flush()  # Get the ID
            document_ids.append(doc_record.id)
        
        db.commit()
        return document_ids
        
    except Exception as e:
        db.rollback()
        raise Exception(f"Error saving documents to database: {e}")

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine) 