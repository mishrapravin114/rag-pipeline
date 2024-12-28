import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import json
import time
from datetime import datetime

# Import the components we're testing
from src.api.routers.chat import router, _get_all_chat_history_with_timestamps
from src.utils.feature_flags import FeatureFlags
from src.utils.semantic_cache import SemanticCache
from src.utils.dynamic_context_selector import DynamicContextSelector
from src.utils.multi_query_generator import MultiQueryGenerator
from src.utils.hybrid_retriever import HybridRetriever
from langchain.schema import Document

class TestSOTARAGIntegration:
    """Integration tests for the complete SOTA RAG pipeline"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock_session = MagicMock()
        
        # Mock collection query
        mock_collection = MagicMock()
        mock_collection.id = 1
        mock_collection.name = "Test Collection"
        mock_collection.chromadb_collection_name = "test_collection"
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_collection
        
        # Mock chat history
        mock_chat = MagicMock()
        mock_chat.user_query = "Previous question about aspirin"
        mock_chat.response_details = json.dumps({
            "response": "Previous answer about aspirin"
        })
        mock_chat.created_at = datetime.now()
        
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_chat]
        
        return mock_session
    
    @pytest.fixture
    def mock_chromadb_util(self):
        """Mock ChromaDB utility"""
        mock_util = MagicMock()
        mock_util.chroma_client = MagicMock()
        
        # Mock collection
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            'ids': ['doc1', 'doc2', 'doc3'],
            'documents': [
                'Aspirin is used for pain relief',
                'Side effects include stomach upset',
                'Dosage varies by condition'
            ],
            'metadatas': [
                {'meta_data': {'source': 'doc1.pdf'}},
                {'meta_data': {'source': 'doc1.pdf'}},
                {'meta_data': {'source': 'doc2.pdf'}}
            ]
        }
        
        mock_util.chroma_client.get_collection.return_value = mock_collection
        mock_util.sanitize_collection_name.return_value = "test_collection"
        
        # Mock the response generation
        mock_util._generate_response_with_docs.return_value = "Generated response about aspirin"
        
        return mock_util
    
    @pytest.fixture
    def test_request(self):
        """Create test request"""
        return {
            "collection_id": 1,
            "query": "What are the side effects of aspirin?",
            "session_id": "test-session-123",
            "user_id": 1
        }
    
    @pytest.fixture
    def setup_feature_flags(self):
        """Set up feature flags for testing"""
        # Enable all SOTA features
        FeatureFlags.enable_all_improvements()
        yield
        # Reset after test
        FeatureFlags._flags = FeatureFlags._flags.copy()
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_cache_hit(
        self, 
        mock_db_session, 
        mock_chromadb_util,
        test_request,
        setup_feature_flags
    ):
        """Test the full pipeline with a cache hit"""
        with patch('src.api.routers.chat.get_db') as mock_get_db, \
             patch('src.api.routers.chat.ChromaDBUtil.get_instance') as mock_chromadb_instance, \
             patch('src.api.routers.chat.FDAChatManagementService') as mock_chat_service, \
             patch('src.api.routers.chat.SemanticCache') as mock_cache_class:
            
            # Set up mocks
            mock_get_db.return_value = mock_db_session
            mock_chromadb_instance.return_value = mock_chromadb_util
            
            # Mock chat service
            mock_chat_service.save_chat_request.return_value = 123
            mock_chat_service.update_chat_response.return_value = None
            
            # Mock cache with a hit
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value={
                'response': 'Cached response about aspirin side effects',
                'html_response': '<p>Cached response about aspirin side effects</p>',
                'cached': True,
                'cache_metadata': {
                    'similarity': 0.98,
                    'hit_count': 2
                }
            })
            mock_cache_class.return_value = mock_cache
            
            # Import and call the endpoint
            from src.api.routers.chat import query_multiple_documents
            
            result = await query_multiple_documents(
                MagicMock(**test_request),
                mock_db_session
            )
            
            # Verify cache was checked
            mock_cache.get.assert_called_once()
            
            # Verify response
            assert result['response'] == '<p>Cached response about aspirin side effects</p>'
            assert result['chat_id'] == 123
            assert result['query_type'] == 'collection'
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_cache_miss(
        self,
        mock_db_session,
        mock_chromadb_util,
        test_request,
        setup_feature_flags
    ):
        """Test the full pipeline with cache miss and all SOTA features"""
        with patch('src.api.routers.chat.get_db') as mock_get_db, \
             patch('src.api.routers.chat.ChromaDBUtil.get_instance') as mock_chromadb_instance, \
             patch('src.api.routers.chat.FDAChatManagementService') as mock_chat_service, \
             patch('src.api.routers.chat.SemanticCache') as mock_cache_class, \
             patch('src.api.routers.chat.DynamicContextSelector') as mock_context_class, \
             patch('src.api.routers.chat._convert_response_to_html_unified') as mock_html_convert:
            
            # Set up mocks
            mock_get_db.return_value = mock_db_session
            mock_chromadb_instance.return_value = mock_chromadb_util
            
            # Mock chat service
            mock_chat_service.save_chat_request.return_value = 123
            mock_chat_service.update_chat_response.return_value = None
            
            # Mock cache with a miss
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=None)
            mock_cache_class.return_value = mock_cache
            
            # Mock dynamic context selector
            mock_context_selector = MagicMock()
            mock_context_selector.select_context = AsyncMock(return_value=[
                ("Previous question", "Previous answer"),
                ("Another question", "Another answer")
            ])
            mock_context_class.return_value = mock_context_selector
            
            # Mock multi-query retrieval
            mock_documents = [
                Document(page_content="Aspirin side effects info", metadata={"source": "doc1.pdf"}),
                Document(page_content="Common side effects", metadata={"source": "doc2.pdf"})
            ]
            mock_chromadb_util.retrieve_with_multi_query = AsyncMock(return_value=mock_documents)
            
            # Mock HTML conversion
            mock_html_convert.return_value = "<p>HTML formatted response</p>"
            
            # Import and call the endpoint
            from src.api.routers.chat import query_multiple_documents
            
            result = await query_multiple_documents(
                MagicMock(**test_request),
                mock_db_session
            )
            
            # Verify all components were used
            mock_cache.get.assert_called_once()  # Cache checked
            mock_context_selector.select_context.assert_called_once()  # Dynamic context used
            mock_chromadb_util.retrieve_with_multi_query.assert_called_once()  # Multi-query used
            mock_cache.set.assert_called_once()  # Result cached
            
            # Verify response
            assert result['response'] == "<p>HTML formatted response</p>"
            assert result['chat_id'] == 123
    
    @pytest.mark.asyncio
    async def test_pipeline_with_legacy_fallback(
        self,
        mock_db_session,
        mock_chromadb_util,
        test_request,
        setup_feature_flags
    ):
        """Test pipeline falls back to legacy when feature flags disabled"""
        # Disable SOTA features
        FeatureFlags.set("FALLBACK_TO_LEGACY", True)
        
        with patch('src.api.routers.chat.get_db') as mock_get_db, \
             patch('src.api.routers.chat.ChromaDBUtil.get_instance') as mock_chromadb_instance, \
             patch('src.api.routers.chat.FDAChatManagementService') as mock_chat_service, \
             patch('src.api.routers.chat._convert_response_to_html_unified') as mock_html_convert:
            
            # Set up mocks
            mock_get_db.return_value = mock_db_session
            mock_chromadb_instance.return_value = mock_chromadb_util
            
            # Mock legacy query_with_llm
            mock_chromadb_util.query_with_llm.return_value = "Legacy response"
            
            # Mock chat service
            mock_chat_service.save_chat_request.return_value = 123
            mock_chat_service.update_chat_response.return_value = None
            
            # Mock HTML conversion
            mock_html_convert.return_value = "<p>Legacy HTML response</p>"
            
            # Import and call the endpoint
            from src.api.routers.chat import query_multiple_documents
            
            result = await query_multiple_documents(
                MagicMock(**test_request),
                mock_db_session
            )
            
            # Verify legacy method was called
            mock_chromadb_util.query_with_llm.assert_called_once()
            
            # Verify SOTA components were NOT used
            assert 'SemanticCache' not in str(mock_chromadb_instance.mock_calls)
            
            # Verify response
            assert result['response'] == "<p>Legacy HTML response</p>"
    
    @pytest.mark.asyncio
    async def test_multi_query_generation(self):
        """Test multi-query generation component"""
        from src.utils.llm_util import get_llm
        
        with patch('src.utils.multi_query_generator.get_llm') as mock_get_llm:
            # Mock LLM response
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = json.dumps([
                "What are the adverse reactions of aspirin?",
                "Aspirin side effects and contraindications",
                "Common negative effects of acetylsalicylic acid"
            ])
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm
            
            # Test multi-query generation
            generator = MultiQueryGenerator(mock_llm, max_queries=5)
            queries = await generator.generate_queries(
                "What are the side effects of aspirin?",
                chat_history=[("Previous Q", "Previous A")]
            )
            
            assert len(queries) >= 2  # Original + variations
            assert "What are the side effects of aspirin?" in queries
            assert any("adverse" in q.lower() for q in queries)
    
    @pytest.mark.asyncio
    async def test_dynamic_context_selection(self):
        """Test dynamic context selection component"""
        with patch('src.utils.dynamic_context_selector.cosine_similarity') as mock_cosine:
            # Mock embeddings model
            mock_embeddings = MagicMock()
            mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
            mock_embeddings.aembed_documents = AsyncMock(return_value=[
                [0.1, 0.2, 0.3],  # High similarity
                [0.8, 0.9, 0.7],  # Low similarity
                [0.15, 0.25, 0.35]  # Medium similarity
            ])
            
            # Mock cosine similarity results
            mock_cosine.side_effect = [
                [[0.95]],  # High relevance
                [[0.3]],   # Low relevance
                [[0.7]]    # Medium relevance
            ]
            
            selector = DynamicContextSelector(
                embeddings_model=mock_embeddings,
                max_tokens=1000
            )
            
            # Test context selection
            all_history = [
                ("Q1", "A1", time.time() - 100),
                ("Q2", "A2", time.time() - 3600),
                ("Q3", "A3", time.time() - 300)
            ]
            
            selected = await selector.select_context(
                "Current query",
                all_history,
                min_conversations=1,
                max_conversations=2
            )
            
            # Should select most relevant within token budget
            assert len(selected) <= 2
            assert len(selected) >= 1
    
    @pytest.mark.asyncio
    async def test_error_handling_collection_not_found(
        self,
        mock_db_session,
        test_request
    ):
        """Test error handling when collection not found"""
        with patch('src.api.routers.chat.get_db') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            # Make collection query return None
            mock_db_session.query.return_value.filter.return_value.first.return_value = None
            
            from src.api.routers.chat import query_multiple_documents
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc_info:
                await query_multiple_documents(
                    MagicMock(**test_request),
                    mock_db_session
                )
            
            assert exc_info.value.status_code == 404
            assert "Collection with id 1 not found" in str(exc_info.value.detail)
    
    def test_feature_flags_configuration(self):
        """Test feature flags configuration"""
        # Test enabling/disabling features
        FeatureFlags.set("ENABLE_SEMANTIC_CACHE", False)
        assert not FeatureFlags.is_enabled("ENABLE_SEMANTIC_CACHE")
        
        FeatureFlags.set("ENABLE_SEMANTIC_CACHE", True)
        assert FeatureFlags.is_enabled("ENABLE_SEMANTIC_CACHE")
        
        # Test getting numeric values
        FeatureFlags.set("SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.9)
        assert FeatureFlags.get("SEMANTIC_CACHE_SIMILARITY_THRESHOLD") == 0.9
        
        # Test configuration summary
        summary = FeatureFlags.get_config_summary()
        assert "SOTA RAG Configuration" in summary
        assert "Enabled:" in summary
        assert "Disabled:" in summary
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation functionality"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        
        cache = SemanticCache(
            chroma_client=mock_client,
            cache_collection_name="test_cache"
        )
        
        # Test collection invalidation
        await cache.invalidate_collection(5)
        mock_collection.get.assert_called_with(
            where={"collection_id": 5},
            include=['ids']
        )
        
        # Test document invalidation
        await cache.invalidate_by_document("doc123")
        mock_collection.get.assert_called_with(
            where={"document_ids": {"$contains": "doc123"}},
            include=['ids']
        )