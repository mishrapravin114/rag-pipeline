"""
Logging configuration to suppress non-critical warnings
"""
import logging
import os

def configure_logging():
    """Configure logging levels to suppress non-critical warnings"""
    
    # Suppress ChromaDB telemetry errors (harmless)
    logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
    
    # Suppress ChromaDB segment warnings about non-existing IDs (happens during re-indexing)
    logging.getLogger("chromadb.segment.impl.vector.local_persistent_hnsw").setLevel(logging.ERROR)
    
    # Suppress LangChain deprecation warnings if needed
    logging.getLogger("langchain").setLevel(logging.ERROR)
    
    # Set ChromaDB general logging to WARNING
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    
    # Keep our application loggers at INFO level
    logging.getLogger("utils").setLevel(logging.INFO)
    logging.getLogger("api").setLevel(logging.INFO)
    
    # Configure based on environment
    if os.getenv("SUPPRESS_WARNINGS", "true").lower() == "true":
        # In production, suppress more warnings
        logging.getLogger("chromadb").setLevel(logging.ERROR)
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# Call this function at startup
configure_logging()