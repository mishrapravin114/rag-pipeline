"""
Tests for the RAG (Retrieval-Augmented Generation) service
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from src.services.rag_service import RAGService
from tests.test_utils import assert_http_ok

class TestRAGService:
    """Test cases for RAGService"""
    
    @pytest.fixture
    def mock_embedding_model(self):
        """Mock the embedding model"""
        with patch('src.services.rag_service.EmbeddingModel') as mock:
            mock.return_value.embed_documents.return_value = [[0.1] * 768]  # Mock embedding vector
            yield mock
    
    @pytest.fixture
    def mock_llm(self):
        """Mock the language model"""
        with patch('src.services.rag_service.ChatOpenAI') as mock:
            mock.return_value.return_value = MagicMock(content="Test response")
            yield mock
    
    @pytest.fixture
    def rag_service(self, mock_embedding_model, mock_llm):
        """Create a RAGService instance with mocked dependencies"""
        from src.config.settings import get_settings
        settings = get_settings()
        return RAGService(
            embedding_model=mock_embedding_model(),
            llm=mock_llm(),
            vector_store_path=Path("test_vector_store"),
            chunk_size=500,
            chunk_overlap=50
        )
    
    def test_process_document(self, rag_service, tmp_path):
        """Test document processing and chunking"""
        # Create a test document
        test_doc = tmp_path / "test.txt"
        test_doc.write_text("This is a test document. " * 100)  # ~2000 chars
        
        # Process the document
        result = rag_service.process_document(test_doc, {"source": "test", "type": "text"})
        
        # Verify results
        assert len(result["chunks"]) > 1  # Should be split into multiple chunks
        assert all(len(chunk["text"]) <= 500 for chunk in result["chunks"])  # Check chunk size
        assert all("metadata" in chunk for chunk in result["chunks"])  # Check metadata
    
    def test_retrieve_relevant_chunks(self, rag_service):
        """Test retrieving relevant chunks for a query"""
        # Mock the vector store
        mock_chunk = {
            "text": "Test document chunk",
            "metadata": {"source": "test", "page": 1}
        }
        rag_service.vector_store.similarity_search.return_value = [mock_chunk]
        
        # Test retrieval
        query = "Test query"
        results = rag_service.retrieve_relevant_chunks(query, k=3)
        
        # Verify results
        assert len(results) == 1
        assert results[0]["text"] == mock_chunk["text"]
        rag_service.vector_store.similarity_search.assert_called_once_with(query, k=3)
    
    @pytest.mark.asyncio
    async def test_generate_response(self, rag_service):
        """Test generating a response using the RAG pipeline"""
        # Mock the retrieval and generation
        rag_service.retrieve_relevant_chunks.return_value = [
            {"text": "Relevant context", "metadata": {"source": "test"}}
        ]
        
        # Test generation
        response = await rag_service.generate_response("Test query")
        
        # Verify response
        assert "response" in response
        assert "sources" in response
        assert response["response"] == "Test response"
        assert len(response["sources"]) > 0


class TestRAGEndpoints:
    """Integration tests for RAG API endpoints"""
    
    def test_chat_endpoint(self, client, mock_rag_service):
        """Test the chat endpoint"""
        # Mock the RAG service
        from src.dependencies import get_rag_service
        
        mock_response = {
            "response": "Test response",
            "sources": [{"source": "test.pdf", "page": 1}]
        }
        
        mock_rag_service.generate_response.return_value = mock_response
        
        # Test the endpoint
        response = client.post(
            "/api/chat/",
            json={"message": "Test query"}
        )
        
        # Verify response
        data = assert_http_ok(response)
        assert data["response"] == "Test response"
        assert len(data["sources"]) > 0
        
        # Verify the service was called
        mock_rag_service.generate_response.assert_called_once()
    
    def test_document_upload(self, client, tmp_path, monkeypatch):
        """Test document upload and processing"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test document content")
        
        # Test the upload endpoint
        with open(test_file, "rb") as f:
            response = client.post(
                "/api/documents/",
                files={"file": ("test.txt", f, "text/plain")},
                data={"metadata": json.dumps({"source": "test"})}
            )
        
        # Verify response
        data = assert_http_ok(response, 201)
        assert "document_id" in data
        assert "status" in data
        assert data["status"] == "processing"
