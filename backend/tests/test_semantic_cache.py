import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from src.utils.semantic_cache import SemanticCache

class TestSemanticCache:
    """Test cases for the SemanticCache class"""
    
    @pytest.fixture
    def mock_chroma_client(self):
        """Create mock ChromaDB client"""
        mock_client = MagicMock()
        
        # Mock collection
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        
        # Mock query results for cache lookup
        mock_collection.query.return_value = {
            'ids': [['cache_key_1']],
            'distances': [[0.02]],  # High similarity (1 - 0.02 = 0.98)
            'documents': [['What are the side effects of aspirin?']],
            'metadatas': [[{
                'cache_key': 'cache_key_1',
                'response': 'Aspirin side effects include stomach upset...',
                'html_response': '<p>Aspirin side effects include stomach upset...</p>',
                'timestamp': time.time() - 300,  # 5 minutes ago
                'context_hash': 'test_context_hash',
                'collection_id': 1,
                'hit_count': 2
            }]]
        }
        
        # Mock get and update operations
        mock_collection.get.return_value = {
            'ids': ['cache_key_1'],
            'metadatas': [{
                'cache_key': 'cache_key_1',
                'hit_count': 2,
                'timestamp': time.time() - 300
            }]
        }
        
        mock_collection.add.return_value = None
        mock_collection.update.return_value = None
        mock_collection.delete.return_value = None
        
        # Mock client methods
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.return_value = mock_collection
        
        return mock_client
    
    @pytest.fixture
    def semantic_cache(self, mock_chroma_client):
        """Create SemanticCache instance with mocks"""
        # First attempt to create will succeed
        mock_chroma_client.create_collection.side_effect = [
            mock_chroma_client.get_collection.return_value
        ]
        
        cache = SemanticCache(
            chroma_client=mock_chroma_client,
            similarity_threshold=0.95,
            ttl_seconds=3600,
            max_cache_size=1000
        )
        return cache
    
    def test_initialization(self, semantic_cache):
        """Test SemanticCache initialization"""
        assert semantic_cache.similarity_threshold == 0.95
        assert semantic_cache.ttl_seconds == 3600
        assert semantic_cache.max_cache_size == 1000
        assert semantic_cache.enable_analytics == True
        assert semantic_cache.cache_collection is not None
    
    def test_generate_cache_key(self, semantic_cache):
        """Test cache key generation"""
        query = "What are the side effects?"
        collection_id = 123
        context_hash = "context_abc"
        
        key1 = semantic_cache._generate_cache_key(query)
        key2 = semantic_cache._generate_cache_key(query, collection_id)
        key3 = semantic_cache._generate_cache_key(query, collection_id, context_hash)
        
        # Keys should be different for different inputs
        assert key1 != key2
        assert key2 != key3
        assert key1 != key3
        
        # Keys should be consistent for same inputs
        assert key1 == semantic_cache._generate_cache_key(query)
        assert key2 == semantic_cache._generate_cache_key(query, collection_id)
    
    def test_hash_context(self, semantic_cache):
        """Test context hashing"""
        context1 = [("User question 1", "Assistant response 1")]
        context2 = [("User question 2", "Assistant response 2")]
        context3 = []
        
        hash1 = semantic_cache._hash_context(context1)
        hash2 = semantic_cache._hash_context(context2)
        hash3 = semantic_cache._hash_context(context3)
        
        assert hash1 != hash2
        assert hash3 == "no_context"
        
        # Same context should produce same hash
        assert hash1 == semantic_cache._hash_context(context1)
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, semantic_cache):
        """Test successful cache hit"""
        query = "What are the side effects of aspirin?"
        context = [("Previous question", "Previous answer")]
        collection_id = 1
        
        result = await semantic_cache.get(
            query=query,
            context=context,
            collection_id=collection_id
        )
        
        assert result is not None
        assert result['cached'] == True
        assert result['response'] == 'Aspirin side effects include stomach upset...'
        assert 'cache_metadata' in result
        assert result['cache_metadata']['similarity'] == 0.98
        assert semantic_cache.stats['hits'] == 1
        assert semantic_cache.stats['misses'] == 0
    
    @pytest.mark.asyncio
    async def test_cache_miss_low_similarity(self, semantic_cache):
        """Test cache miss due to low similarity"""
        # Mock low similarity result
        semantic_cache.cache_collection.query.return_value = {
            'ids': [['cache_key_1']],
            'distances': [[0.1]],  # Low similarity (1 - 0.1 = 0.9)
            'documents': [['Different question']],
            'metadatas': [[{
                'cache_key': 'cache_key_1',
                'response': 'Some response',
                'timestamp': time.time() - 300
            }]]
        }
        
        result = await semantic_cache.get(
            query="What are the side effects of aspirin?",
            collection_id=1
        )
        
        assert result is None
        assert semantic_cache.stats['misses'] == 1
        assert semantic_cache.stats['hits'] == 0
    
    @pytest.mark.asyncio
    async def test_cache_miss_expired(self, semantic_cache):
        """Test cache miss due to expired entry"""
        # Mock expired result
        semantic_cache.cache_collection.query.return_value = {
            'ids': [['cache_key_1']],
            'distances': [[0.02]],  # High similarity
            'documents': [['What are the side effects of aspirin?']],
            'metadatas': [[{
                'cache_key': 'cache_key_1',
                'response': 'Aspirin side effects...',
                'timestamp': time.time() - 7200,  # 2 hours ago (expired)
                'ttl_seconds': 3600
            }]]
        }
        
        result = await semantic_cache.get(
            query="What are the side effects of aspirin?",
            collection_id=1
        )
        
        assert result is None
        assert semantic_cache.stats['misses'] == 1
    
    @pytest.mark.asyncio
    async def test_cache_set(self, semantic_cache):
        """Test setting cache entry"""
        query = "What is the dosage of ibuprofen?"
        response = "The typical dosage is 200-400mg..."
        html_response = "<p>The typical dosage is 200-400mg...</p>"
        context = [("Previous Q", "Previous A")]
        collection_id = 2
        
        await semantic_cache.set(
            query=query,
            response=response,
            html_response=html_response,
            context=context,
            collection_id=collection_id
        )
        
        # Check that add was called with correct parameters
        semantic_cache.cache_collection.add.assert_called_once()
        call_args = semantic_cache.cache_collection.add.call_args
        
        assert call_args[1]['documents'] == [query]
        metadata = call_args[1]['metadatas'][0]
        assert metadata['response'] == response
        assert metadata['html_response'] == html_response
        assert metadata['collection_id'] == collection_id
        assert metadata['has_context'] == True
        assert semantic_cache.stats['cache_saves'] == 1
    
    @pytest.mark.asyncio
    async def test_update_analytics(self, semantic_cache):
        """Test cache analytics update"""
        cache_key = "test_cache_key"
        
        await semantic_cache._update_cache_analytics(cache_key)
        
        # Check that get and update were called
        semantic_cache.cache_collection.get.assert_called_once_with(
            ids=[cache_key],
            include=['metadatas']
        )
        semantic_cache.cache_collection.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manage_cache_size(self, semantic_cache):
        """Test cache size management and eviction"""
        # Mock cache at max size
        semantic_cache.cache_collection.count.return_value = 1001  # Over limit
        
        # Mock items for eviction
        all_items = {
            'ids': ['key1', 'key2', 'key3'],
            'metadatas': [
                {'timestamp': time.time() - 3600, 'hit_count': 0, 'last_accessed': time.time() - 3600},
                {'timestamp': time.time() - 1800, 'hit_count': 5, 'last_accessed': time.time() - 100},
                {'timestamp': time.time() - 900, 'hit_count': 2, 'last_accessed': time.time() - 500}
            ]
        }
        semantic_cache.cache_collection.get.return_value = all_items
        
        await semantic_cache._manage_cache_size()
        
        # Should delete some items
        semantic_cache.cache_collection.delete.assert_called_once()
        deleted_ids = semantic_cache.cache_collection.delete.call_args[1]['ids']
        assert len(deleted_ids) > 0
    
    @pytest.mark.asyncio
    async def test_invalidate_collection(self, semantic_cache):
        """Test invalidating all cache entries for a collection"""
        collection_id = 5
        
        # Mock items to invalidate
        semantic_cache.cache_collection.get.return_value = {
            'ids': ['key1', 'key2', 'key3']
        }
        
        await semantic_cache.invalidate_collection(collection_id)
        
        # Check that get was called with correct filter
        semantic_cache.cache_collection.get.assert_called_once_with(
            where={"collection_id": collection_id},
            include=['ids']
        )
        
        # Check that delete was called
        semantic_cache.cache_collection.delete.assert_called_once_with(
            ids=['key1', 'key2', 'key3']
        )
    
    def test_get_statistics(self, semantic_cache):
        """Test getting cache statistics"""
        # Set some stats
        semantic_cache.stats = {
            'hits': 10,
            'misses': 5,
            'total_queries': 15,
            'cache_saves': 8,
            'cache_errors': 2
        }
        
        stats = semantic_cache.get_statistics()
        
        assert stats['hit_rate'] == 10/15  # 0.667
        assert stats['total_queries'] == 15
        assert stats['cache_hits'] == 10
        assert stats['cache_misses'] == 5
        assert stats['cache_saves'] == 8
        assert stats['cache_errors'] == 2
        assert stats['cache_size'] == 100  # From mock
    
    @pytest.mark.asyncio
    async def test_clear_expired(self, semantic_cache):
        """Test clearing expired cache entries"""
        current_time = time.time()
        
        # Mock all items with some expired
        all_items = {
            'ids': ['key1', 'key2', 'key3'],
            'metadatas': [
                {'timestamp': current_time - 7200},  # Expired
                {'timestamp': current_time - 300},   # Not expired
                {'timestamp': current_time - 4000}   # Expired
            ]
        }
        semantic_cache.cache_collection.get.return_value = all_items
        
        await semantic_cache.clear_expired()
        
        # Should delete expired items
        semantic_cache.cache_collection.delete.assert_called_once()
        deleted_ids = semantic_cache.cache_collection.delete.call_args[1]['ids']
        assert 'key1' in deleted_ids
        assert 'key3' in deleted_ids
        assert 'key2' not in deleted_ids
    
    @pytest.mark.asyncio
    async def test_error_handling_get(self, semantic_cache):
        """Test error handling in get method"""
        # Make query raise an error
        semantic_cache.cache_collection.query.side_effect = Exception("Query error")
        
        result = await semantic_cache.get(
            query="Test query",
            collection_id=1
        )
        
        assert result is None
        assert semantic_cache.stats['cache_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_set(self, semantic_cache):
        """Test error handling in set method"""
        # Make add raise an error
        semantic_cache.cache_collection.add.side_effect = Exception("Add error")
        
        # Should not raise, just log error
        await semantic_cache.set(
            query="Test query",
            response="Test response"
        )
        
        assert semantic_cache.stats['cache_errors'] == 1