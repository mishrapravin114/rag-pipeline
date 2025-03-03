import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional

# Load environment variables from .env files (backend/.env first, then root .env)
backend_dir = Path(__file__).parent.parent.parent
root_dir = backend_dir.parent
load_dotenv(backend_dir / ".env")  # Load backend/.env first
load_dotenv(root_dir / ".env", override=False)  # Then root .env (don't override if already set)

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mysql+pymysql://fda_user:fda_password@localhost:3307/fda_rag"
    
    # LLM Configuration
    LLM_TYPE: str = "gemini"
    
    # Google Gemini Configuration
    GOOGLE_API_KEY: Optional[str] = None
    LLM_GEMINI_MODEL: str = "gemini-2.0-flash"
    LLM_GEMINI_EMBEDDING: str = "models/text-embedding-004"  # Latest Gemini embedding model with 768 dimensions
    LLM_GEMINI_TEMPERATURE: float = 0.1

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CLIENT_SECRETS_FILE: Optional[str] = None
    
    # File processing
    DOWNLOAD_DIR: str = "./downloads"
    OUTPUT_DIR: str = "./output"
    
    # Frontend Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8090")
    
    # Text processing
    MAX_TOKENS_PER_CHUNK: int = 1000
    OVERLAP_TOKENS: int = 100
    
    # PyMuPDF Processor Configuration
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "3000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "400"))
    
    # Embedding configuration
    USE_PRECOMPUTED_EMBEDDINGS: bool = False  # Set to False to let ChromaDB handle embeddings
    EMBEDDING_RATE_LIMIT_DELAY: float = 1.0  # Delay between embedding requests in seconds
    
    # Telemetry
    CHROMA_TELEMETRY_DISABLED: str = "1"
    
    # Qdrant Configuration
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "qdrant")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_GRPC_PORT: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    QDRANT_HTTPS: bool = os.getenv("QDRANT_HTTPS", "false").lower() == "true"
    QDRANT_COLLECTION_REPLICATION_FACTOR: int = int(os.getenv("QDRANT_COLLECTION_REPLICATION_FACTOR", "1"))
    QDRANT_PREFER_GRPC: bool = os.getenv("QDRANT_PREFER_GRPC", "false").lower() == "true"
    
    # Output directories
    @property
    def LOG_OUTPUT_DIR(self) -> str:
        return os.path.join(self.OUTPUT_DIR, "logs")
    
    @property
    def JSON_OUTPUT_DIR(self) -> str:
        return os.path.join(self.OUTPUT_DIR, "json")
    
    class Config:
        env_file = ".env"  # Will use the one loaded by dotenv above
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

# Create settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.LOG_OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.JSON_OUTPUT_DIR, exist_ok=True)