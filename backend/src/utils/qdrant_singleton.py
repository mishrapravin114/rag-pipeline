"""
Qdrant Singleton Client
Ensures a single Qdrant client instance is used across the application
"""

import threading
import logging
import time
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from config.settings import settings

logger = logging.getLogger(__name__)


class QdrantSingleton:
    """Thread-safe singleton Qdrant client."""
    
    _instance = None
    _lock = threading.Lock()
    _client = None
    _initialization_lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self, max_retries: int = 5) -> QdrantClient:
        """Get or create the Qdrant client with retry logic."""
        if self._client is None:
            with self._initialization_lock:
                if self._client is None:
                    self._initialize_client(max_retries)
        return self._client
    
    def _initialize_client(self, max_retries: int):
        """Initialize the Qdrant client with retry logic."""
        # Determine connection parameters
        host = settings.QDRANT_HOST
        port = settings.QDRANT_GRPC_PORT if settings.QDRANT_PREFER_GRPC else settings.QDRANT_PORT
        prefer_grpc = settings.QDRANT_PREFER_GRPC
        https = settings.QDRANT_HTTPS
        api_key = settings.QDRANT_API_KEY
        
        logger.info(f"Initializing Qdrant client: host={host}, port={port}, grpc={prefer_grpc}")
        
        for attempt in range(max_retries):
            try:
                self._client = QdrantClient(
                    host=host,
                    port=port,
                    api_key=api_key,
                    https=https,
                    prefer_grpc=prefer_grpc,
                    timeout=120.0,  # 120 second timeout for large collections with filters
                )
                
                # Test connection
                _ = self._client.get_collections()
                logger.info("Qdrant client initialized successfully")
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.warning(
                        f"Failed to initialize Qdrant (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to initialize Qdrant after {max_retries} attempts: {e}")
                    raise RuntimeError(f"Could not initialize Qdrant: {e}")
    
    def reset_client(self):
        """Reset the client connection."""
        with self._initialization_lock:
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    logger.warning(f"Error closing Qdrant client: {e}")
            self._client = None
            logger.info("Qdrant client reset")
    
    def health_check(self) -> bool:
        """Check if Qdrant is healthy and accessible."""
        try:
            if self._client is None:
                return False
            # Try to get collections as a health check
            _ = self._client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Global instance
qdrant_singleton = QdrantSingleton()


def get_qdrant_client(max_retries: int = 5) -> QdrantClient:
    """Get the shared Qdrant client instance."""
    return qdrant_singleton.get_client(max_retries)


def reset_qdrant_client():
    """Reset the Qdrant client connection."""
    qdrant_singleton.reset_client()


def check_qdrant_health() -> bool:
    """Check if Qdrant is healthy."""
    return qdrant_singleton.health_check()