"""
Production-optimized database configuration with enhanced connection pooling
"""
import os
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
import logging

logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment or settings"""
    return os.environ.get('DATABASE_URL', 'mysql+pymysql://fda_user:fda_password@mysql:3306/fda_rag?charset=utf8mb4')

def create_production_engine():
    """Create SQLAlchemy engine with production-optimized settings"""
    
    # Connection pool configuration from environment
    pool_size = int(os.environ.get('SQLALCHEMY_POOL_SIZE', 20))
    max_overflow = int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', 40))
    pool_timeout = int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', 30))
    pool_recycle = int(os.environ.get('SQLALCHEMY_POOL_RECYCLE', 3600))
    pool_pre_ping = os.environ.get('SQLALCHEMY_POOL_PRE_PING', 'true').lower() == 'true'
    
    # Create engine with production settings
    engine = create_engine(
        get_database_url(),
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        echo=False,  # Disable SQL echo in production
        echo_pool=False,
        connect_args={
            'connect_timeout': 10,
            'read_timeout': 300,
            'write_timeout': 300,
            'charset': 'utf8mb4',
            'use_unicode': True,
            # MySQL specific optimizations
            'sql_mode': 'TRADITIONAL',
            'isolation_level': 'READ COMMITTED'
        }
    )
    
    # Add connection pool logging
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        connection_record.info['pid'] = os.getpid()
        logger.debug(f"New database connection established by PID {os.getpid()}")
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        if connection_record.info.get('pid') != pid:
            # Connection was established by a different process, invalidate it
            connection_record.invalidate()
            logger.debug(f"Invalidating connection from different PID. Current: {pid}, Original: {connection_record.info.get('pid')}")
    
    # Add pessimistic disconnect handling
    @event.listens_for(engine, "engine_connect")
    def ping_connection(connection, branch):
        if branch:
            # "branch" refers to a sub-connection of a connection,
            # we don't want to bother pinging on these.
            return
        
        # Check if we need to invalidate the connection
        try:
            # Run a simple query to test the connection
            connection.scalar("SELECT 1")
        except Exception as e:
            # The connection is stale, invalidate it
            logger.warning(f"Database connection ping failed: {e}")
            connection.invalidate()
            # Re-raise to let SQLAlchemy handle reconnection
            raise
    
    return engine

def create_production_session_factory(engine):
    """Create session factory with production settings"""
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False  # Prevent lazy loading issues in async contexts
    )

# Production connection retry decorator
def retry_on_db_error(max_retries=3, delay=1.0):
    """Decorator to retry database operations on connection errors"""
    import time
    from functools import wraps
    from sqlalchemy.exc import OperationalError, DisconnectionError
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator

# Create production engine and session factory
if os.environ.get('ENV', 'development') == 'production':
    from .database import Base
    engine = create_production_engine()
    SessionLocal = create_production_session_factory(engine)
    
    # Export for use in application
    __all__ = ['engine', 'SessionLocal', 'Base', 'retry_on_db_error']