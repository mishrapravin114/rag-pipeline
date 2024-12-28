import hashlib
import time
import json
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SemanticCache:
    """
    Implements semantic caching for RAG responses using similarity-based matching.
    Reduces latency and API costs by caching similar queries.
    """
    
    def __init__(
        self,
        chroma_client,
        cache_collection_name: str = "semantic_cache",
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 3600,
        max_cache_size: int = 10000,
        enable_analytics: bool = True
    ):
        self.chroma_client = chroma_client
        self.cache_collection_name = cache_collection_name
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.enable_analytics = enable_analytics
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'total_queries': 0,
            'cache_saves': 0,
            'cache_errors': 0
        }
        
        # Initialize cache collection
        self._initialize_cache_collection()
    
    def _initialize_cache_collection(self):
        """Create or get cache collection with proper configuration"""
        try:
            # Try to create new collection
            self.cache_collection = self.chroma_client.create_collection(
                name=self.cache_collection_name,
                metadata={
                    "type": "semantic_cache",
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            )
            logger.info(f"Created new semantic cache collection: {self.cache_collection_name}")
        except Exception as e:
            # Collection exists, get it
            self.cache_collection = self.chroma_client.get_collection(
                name=self.cache_collection_name
            )
            logger.info(f"Using existing semantic cache collection: {self.cache_collection_name}")
    
    def _generate_cache_key(
        self, 
        query: str, 
        collection_id: Optional[int] = None,
        context_hash: Optional[str] = None
    ) -> str:
        """Generate unique cache key including query context"""
        components = [query]
        
        if collection_id:
            components.append(f"collection_{collection_id}")
        
        if context_hash:
            components.append(f"context_{context_hash}")
        
        content = "|".join(components)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _hash_context(self, context: List[Tuple[str, str]]) -> str:
        """Generate hash for conversation context"""
        if not context:
            return "no_context"
        
        # Use last conversation for context hashing
        last_user, last_assistant = context[-1]
        context_str = f"{last_user[:100]}:{last_assistant[:100]}"
        return hashlib.md5(context_str.encode()).hexdigest()
    
    async def get(
        self, 
        query: str, 
        context: Optional[List[Tuple[str, str]]] = None,
        collection_id: Optional[int] = None,
        include_analytics: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response if similar query exists.
        
        Returns:
            Cached response dict or None if no valid cache hit
        """
        self.stats['total_queries'] += 1
        
        try:
            # Generate context hash
            context_hash = self._hash_context(context) if context else None
            
            # Search for similar queries
            results = self.cache_collection.query(
                query_texts=[query],
                n_results=10,  # Get more candidates for better matching
                where={
                    "collection_id": collection_id
                } if collection_id else None,
                include=['metadatas', 'distances', 'documents']
            )
            
            if not results['ids'][0]:
                self.stats['misses'] += 1
                return None
            
            current_time = time.time()
            
            # Check each result for validity
            for i, (distance, metadata, cached_query) in enumerate(zip(
                results['distances'][0],
                results['metadatas'][0],
                results['documents'][0]
            )):
                # Calculate similarity
                similarity = 1 - distance
                
                # Check similarity threshold
                if similarity < self.similarity_threshold:
                    continue
                
                # Check TTL
                if current_time - metadata['timestamp'] > self.ttl_seconds:
                    # Expired entry - could delete it here
                    continue
                
                # Check context match (fuzzy)
                cached_context_hash = metadata.get('context_hash', 'no_context')
                if context_hash and cached_context_hash != 'no_context':
                    # Allow some context mismatch for high similarity
                    if similarity < 0.98 and cached_context_hash != context_hash:
                        continue
                
                # Valid cache hit!
                self.stats['hits'] += 1
                
                logger.info(f"Cache hit! Query: '{query[:50]}...' "
                           f"Similarity: {similarity:.3f}, "
                           f"Age: {(current_time - metadata['timestamp'])/60:.1f} minutes")
                
                # Update hit count and last accessed
                await self._update_cache_analytics(metadata['cache_key'])
                
                # Return cached response
                return {
                    'response': metadata['response'],
                    'html_response': metadata.get('html_response'),
                    'cached': True,
                    'cache_metadata': {
                        'similarity': similarity,
                        'cached_at': metadata['timestamp'],
                        'original_query': cached_query,
                        'hit_count': metadata.get('hit_count', 0) + 1,
                        'age_minutes': (current_time - metadata['timestamp']) / 60,
                        'document_ids': metadata.get('document_ids', '').split(',') if metadata.get('document_ids') else []
                    }
                }
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            self.stats['cache_errors'] += 1
            return None
    
    async def set(
        self,
        query: str,
        response: str,
        html_response: Optional[str] = None,
        context: Optional[List[Tuple[str, str]]] = None,
        collection_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        documents_used: Optional[List[Dict]] = None
    ):
        """Store query-response pair in cache with metadata"""
        try:
            # Check cache size and clean if needed
            await self._manage_cache_size()
            
            # Generate cache key and context hash
            context_hash = self._hash_context(context) if context else None
            cache_key = self._generate_cache_key(query, collection_id, context_hash)
            
            # Prepare metadata
            cache_metadata = {
                'cache_key': cache_key,
                'response': response,
                'html_response': html_response,
                'timestamp': time.time(),
                'context_hash': context_hash or 'no_context',
                'collection_id': collection_id,
                'hit_count': 0,
                'last_accessed': time.time(),
                'query_length': len(query),
                'response_length': len(response),
                'has_context': bool(context),
                'documents_count': len(documents_used) if documents_used else 0
            }
            
            # Add custom metadata
            if metadata:
                cache_metadata.update(metadata)
            
            # Store document references if provided
            if documents_used:
                # Extract document IDs, filtering out None values
                doc_ids = []
                for doc in documents_used[:5]:
                    doc_id = doc.get('id')
                    if doc_id:
                        doc_ids.append(str(doc_id))
                
                # Only add document_ids if we have valid IDs
                if doc_ids:
                    # ChromaDB doesn't support lists in metadata, so join them
                    cache_metadata['document_ids'] = ','.join(doc_ids)
            
            # Store in cache
            self.cache_collection.add(
                ids=[cache_key],
                documents=[query],  # Store original query for similarity search
                metadatas=[cache_metadata]
            )
            
            self.stats['cache_saves'] += 1
            logger.info(f"Cached response for query: '{query[:50]}...' "
                       f"(collection_id={collection_id}, context={bool(context)})")
            
        except Exception as e:
            logger.error(f"Error storing in cache: {e}")
            self.stats['cache_errors'] += 1
    
    async def _update_cache_analytics(self, cache_key: str):
        """Update analytics for cache hit"""
        if not self.enable_analytics:
            return
        
        try:
            # Get current metadata
            result = self.cache_collection.get(
                ids=[cache_key],
                include=['metadatas']
            )
            
            if result['ids']:
                metadata = result['metadatas'][0]
                metadata['hit_count'] = metadata.get('hit_count', 0) + 1
                metadata['last_accessed'] = time.time()
                
                # Update metadata
                self.cache_collection.update(
                    ids=[cache_key],
                    metadatas=[metadata]
                )
        except Exception as e:
            logger.error(f"Error updating cache analytics: {e}")
    
    async def _manage_cache_size(self):
        """Manage cache size using LRU-like eviction"""
        try:
            # Get current cache size
            count = self.cache_collection.count()
            
            if count >= self.max_cache_size:
                logger.info(f"Cache size ({count}) exceeded limit ({self.max_cache_size}), cleaning...")
                
                # Get all cache entries
                all_items = self.cache_collection.get(
                    include=['metadatas', 'ids']
                )
                
                if not all_items['ids']:
                    return
                
                # Calculate eviction scores
                current_time = time.time()
                items_with_scores = []
                
                for i, metadata in enumerate(all_items['metadatas']):
                    # Score based on recency, hit count, and age
                    age = current_time - metadata['timestamp']
                    last_accessed_age = current_time - metadata.get('last_accessed', metadata['timestamp'])
                    hits = metadata.get('hit_count', 0)
                    
                    # Higher score = keep, lower score = evict
                    score = (hits * 1000) - (last_accessed_age / 3600)  # Hits heavily weighted
                    
                    items_with_scores.append((
                        all_items['ids'][i],
                        score,
                        metadata
                    ))
                
                # Sort by score (ascending - lowest scores first)
                items_with_scores.sort(key=lambda x: x[1])
                
                # Remove bottom 20%
                to_remove = int(count * 0.2)
                ids_to_remove = [item[0] for item in items_with_scores[:to_remove]]
                
                if ids_to_remove:
                    self.cache_collection.delete(ids=ids_to_remove)
                    logger.info(f"Evicted {len(ids_to_remove)} items from cache")
                    
        except Exception as e:
            logger.error(f"Error managing cache size: {e}")
    
    async def invalidate_collection(self, collection_id: int):
        """Invalidate all cache entries for a specific collection"""
        try:
            # Get all entries for this collection
            results = self.cache_collection.get(
                where={"collection_id": collection_id},
                include=['ids']
            )
            
            if results['ids']:
                self.cache_collection.delete(ids=results['ids'])
                logger.info(f"Invalidated {len(results['ids'])} cache entries for collection {collection_id}")
                
        except Exception as e:
            logger.error(f"Error invalidating collection cache: {e}")
    
    async def invalidate_by_document(self, document_id: str):
        """Invalidate cache entries that used a specific document"""
        try:
            # Get all cache entries and check if they contain the document ID
            # (ChromaDB doesn't support substring search in metadata)
            all_items = self.cache_collection.get(
                include=['metadatas', 'ids']
            )
            
            ids_to_delete = []
            for i, metadata in enumerate(all_items['metadatas']):
                doc_ids_str = metadata.get('document_ids', '')
                if doc_ids_str and document_id in doc_ids_str.split(','):
                    ids_to_delete.append(all_items['ids'][i])
            
            if ids_to_delete:
                self.cache_collection.delete(ids=ids_to_delete)
                logger.info(f"Invalidated {len(ids_to_delete)} cache entries using document {document_id}")
                
        except Exception as e:
            logger.error(f"Error invalidating document cache: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0
        
        return {
            'hit_rate': hit_rate,
            'total_queries': self.stats['total_queries'],
            'cache_hits': self.stats['hits'],
            'cache_misses': self.stats['misses'],
            'cache_saves': self.stats['cache_saves'],
            'cache_errors': self.stats['cache_errors'],
            'cache_size': self.cache_collection.count() if hasattr(self, 'cache_collection') else 0
        }
    
    async def clear_expired(self):
        """Clear expired cache entries"""
        try:
            current_time = time.time()
            cutoff_time = current_time - self.ttl_seconds
            
            # Get all entries
            all_items = self.cache_collection.get(
                include=['metadatas', 'ids']
            )
            
            expired_ids = []
            for i, metadata in enumerate(all_items['metadatas']):
                if metadata['timestamp'] < cutoff_time:
                    expired_ids.append(all_items['ids'][i])
            
            if expired_ids:
                self.cache_collection.delete(ids=expired_ids)
                logger.info(f"Cleared {len(expired_ids)} expired cache entries")
                
        except Exception as e:
            logger.error(f"Error clearing expired entries: {e}")