"""
Pytest configuration for backend tests with enhanced test utilities
"""
import os
import sys
import pytest
import tempfile
from pathlib import Path
from typing import Generator, Any, Dict
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database.database import Base, get_db
from src.config.settings import get_settings

# Override settings for testing
settings = get_settings()
settings.TESTING = True
settings.DATABASE_URL = "sqlite:///:memory:"
settings.QDRANT_HOST = "test-host"
settings.QDRANT_PORT = 6333
settings.ENVIRONMENT = "testing"

# Test file paths
TEST_FILES_DIR = Path(__file__).parent / "test_files"
TEST_PDF = TEST_FILES_DIR / "test_document.pdf"


def pytest_configure():
    """Configure pytest with custom markers"""
    pytest.TEST_FILES_DIR = TEST_FILES_DIR
    pytest.TEST_PDF = TEST_PDF


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine with all tables"""
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a test database session with automatic rollback"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session, tmp_path: Path) -> TestClient:
    """Create a test client with overridden dependencies"""
    from main import app
    from fastapi.testclient import TestClient
    
    # Create test directories
    (tmp_path / "uploads").mkdir()
    (tmp_path / "data").mkdir()
    
    # Override settings
    settings.UPLOAD_DIR = tmp_path / "uploads"
    settings.DATA_DIR = tmp_path / "data"
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    # Apply dependency overrides
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up
    app.dependency_overrides.clear()

    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_id():
    """Provide a sample user ID for testing"""
    return 1


@pytest.fixture
def auth_headers(sample_user_id):
    """Provide authentication headers for testing"""
    # In a real test environment, you would generate a proper JWT token
    # For now, we'll use a mock token
    return {"Authorization": "Bearer test-token"}