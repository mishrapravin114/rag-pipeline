"""
Test utilities and helpers
"""
import json
from typing import Dict, Any, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

async def assert_http_ok(response, expected_status: int = 200) -> Dict[str, Any]:
    """Assert that the response has the expected status code and returns JSON."""
    assert response.status_code == expected_status, f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
    return response.json()

def assert_pagination(response_data: Dict[str, Any], expected_page: int, expected_page_size: int):
    """Assert pagination metadata in the response."""
    assert "pagination" in response_data
    pagination = response_data["pagination"]
    assert "total" in pagination
    assert "page" in pagination
    assert "page_size" in pagination
    assert pagination["page"] == expected_page
    assert pagination["page_size"] == expected_page_size

def create_test_file(client: TestClient, file_path: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """Helper to create a test file."""
    with open(file_path, "rb") as f:
        files = {"file": ("test_file.pdf", f, "application/pdf")}
        data = {}
        if metadata:
            data["metadata"] = json.dumps(metadata)
        response = client.post("/api/files/", files=files, data=data)
    return assert_http_ok(response, 201)

def create_test_collection(client: TestClient, name: str, description: str = "Test collection") -> Dict[str, Any]:
    """Helper to create a test collection."""
    response = client.post(
        "/api/collections/",
        json={"name": name, "description": description}
    )
    return assert_http_ok(response, 201)

def cleanup_test_data(db: Session):
    """Clean up test data from all tables."""
    # Get all tables in reverse order to respect foreign key constraints
    tables = reversed([t for t in db.get_bind().table_names()])
    
    for table in tables:
        if table != "alembic_version":  # Skip alembic version table
            db.execute(f"DELETE FROM {table}")
    db.commit()
