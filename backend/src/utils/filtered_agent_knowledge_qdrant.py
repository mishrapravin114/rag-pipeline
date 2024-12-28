"""
FilteredAgentKnowledge - Extended AgentKnowledge with Qdrant filtering support
"""
import logging
from typing import List, Optional, Dict, Any, Iterator, AsyncIterator
from agno.knowledge.agent import AgentKnowledge
from agno.document import Document
from agno.utils.log import log_debug, log_info

from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)


class FilteredAgentKnowledge(AgentKnowledge):
    """Custom AgentKnowledge that supports Qdrant filtering while maintaining all parent functionality"""
    
    def __init__(self, vector_db, num_documents: int = 10, filters: Optional[Dict[str, Any]] = None, **kwargs):
        # Initialize parent class with all possible parameters
        super().__init__(vector_db=vector_db, num_documents=num_documents, **kwargs)
        # Store filters as a private attribute to avoid Pydantic validation issues
        self._custom_filters = filters
        logger.info(f"Initialized FilteredAgentKnowledge with filters: {filters}")
        logger.info(f"Vector DB type: {type(vector_db).__name__}")
        logger.info(f"Vector DB attributes: {dir(vector_db) if vector_db else 'None'}")
        
        # Initialize valid metadata filters if we have custom filters
        if self._custom_filters:
            if self.valid_metadata_filters is None:
                self.valid_metadata_filters = set()
            for key in self._custom_filters.keys():
                self.valid_metadata_filters.add(key)
    
    def _convert_filters_for_qdrant(self, filters: Dict[str, Any]) -> Optional[Filter]:
        """Convert our filter format to Qdrant's expected format.
        Now adds meta_data prefix to match Agno's document structure."""
        logger.debug(f"Converting filters for Qdrant: {filters}")
        if not filters:
            logger.debug("No filters to convert")
            return None
        
        conditions = []
        
        for key, value in filters.items():
            # Add meta_data prefix for standard fields (not content or name)
            if key not in ['content', 'name'] and not key.startswith('meta_data.'):
                key = f'meta_data.{key}'
            if isinstance(value, dict):
                if '$in' in value:
                    # Qdrant uses MatchAny for 'in' operations
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchAny(any=value['$in'])
                        )
                    )
                elif '$eq' in value:
                    # Handle equality operator
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value['$eq'])
                        )
                    )
                else:
                    # Handle other operators if needed
                    logger.warning(f"Unsupported filter operator: {value}")
                    continue
            else:
                # Direct key-value pairs
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
        
        if conditions:
            qdrant_filter = Filter(must=conditions)
            logger.info(f"Converted filters to Qdrant format: {conditions}")
            logger.debug(f"Qdrant filter object: {qdrant_filter}")
            return qdrant_filter
        
        logger.debug("No conditions created from filters")
        return None
    
    def _merge_filters(self, method_filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Merge method filters with instance filters"""
        logger.debug(f"Merging filters - method_filters: {method_filters}, instance_filters: {self._custom_filters}")
        if method_filters is not None:
            logger.debug(f"Using method filters: {method_filters}")
            return method_filters
        logger.debug(f"Using instance filters: {self._custom_filters}")
        return self._custom_filters
    
    def search(self, query: str, num_documents: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Override search to apply Qdrant filters"""
        try:
            logger.debug("\n" + "="*80)
            logger.debug("SEARCH METHOD CALLED")
            logger.debug(f"Query: {query}")
            logger.debug(f"Num documents requested: {num_documents}")
            logger.debug(f"Filters passed to method: {filters}")
            logger.debug("="*80 + "\n")
            
            if self.vector_db is None:
                logger.warning("No vector db provided")
                return []
            
            num_docs = num_documents or self.num_documents
            filters_to_use = self._merge_filters(filters)
            
            logger.info(f"FilteredAgentKnowledge searching: query='{query[:50]}...', num_docs={num_docs}, filters={filters_to_use}")
            
            if filters_to_use:
                logger.info(f"Passing filters to vector_db: {filters_to_use}")
                
                # If using CustomQdrantWrapper, it handles filters correctly
                if hasattr(self.vector_db, '_format_filters'):
                    logger.debug("Using CustomQdrantWrapper - filters will be applied at root level")
                
                # Convert filters to Qdrant format before passing to vector_db
                qdrant_filters = self._convert_filters_for_qdrant(filters_to_use)
                
                # Use search with converted filters
                if qdrant_filters:
                    # Temporarily store the original _format_filters method
                    original_format_filters = getattr(self.vector_db, '_format_filters', None)
                    
                    # Override _format_filters to return our pre-converted filters
                    def bypass_format_filters(filters_dict):
                        logger.debug(f"Bypassing format_filters, returning pre-converted: {qdrant_filters}")
                        return qdrant_filters
                    
                    try:
                        self.vector_db._format_filters = bypass_format_filters
                        results = self.vector_db.search(
                            query=query, 
                            limit=num_docs,
                            filters={}  # Pass empty dict since we override _format_filters
                        )
                    finally:
                        # Restore original method
                        if original_format_filters:
                            self.vector_db._format_filters = original_format_filters
                        elif hasattr(self.vector_db, '_format_filters'):
                            delattr(self.vector_db, '_format_filters')
                else:
                    results = self.vector_db.search(
                        query=query, 
                        limit=num_docs,
                        filters=None
                    )
                
                logger.info(f"Search returned {len(results) if results else 0} results with filters")
                logger.debug(f"Result types: {[type(r).__name__ for r in results[:3]] if results else 'No results'}")
                if results and len(results) > 0:
                    logger.debug(f"First result: {results[0]}")
                
                return results
            else:
                # No filters, use parent search method
                logger.debug("No filters to apply, calling vector_db.search without filters")
                results = self.vector_db.search(query=query, limit=num_docs, filters=None)
                logger.info(f"Search without filters returned {len(results) if results else 0} results")
                return results
                
        except Exception as e:
            logger.error(f"Error searching for documents: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error args: {e.args if hasattr(e, 'args') else 'No args'}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Check if it's a timeout error - if so, try with smaller batch size first
            if "timeout" in str(e).lower() or "ReadTimeout" in str(type(e).__name__):
                logger.warning("Timeout detected - trying with reduced document limit...")
                try:
                    reduced_limit = min(num_docs // 2, 10)  # Try with half or max 10 docs
                    if reduced_limit > 0:
                        results = self.vector_db.search(
                            query=query, 
                            limit=reduced_limit,
                            filters={}  # Pass empty dict since we override _format_filters
                        )
                        logger.info(f"Reduced limit search successful, returned {len(results) if results else 0} results")
                        return results
                except Exception as retry_e:
                    logger.warning(f"Reduced limit search also failed: {retry_e}")
            
            # Try fallback without filters
            try:
                logger.warning("Attempting search without filters as fallback...")
                logger.debug(f"Fallback search params: query='{query}', limit={num_docs}")
                
                results = self.vector_db.search(query=query, limit=num_docs, filters=None)
                logger.info(f"Fallback search successful, returned {len(results) if results else 0} results")
                
                # If we have filters, manually filter the results
                if filters_to_use and results:
                    logger.debug("Applying manual filtering to results...")
                    filtered_results = []
                    source_filter = filters_to_use.get('source', {}).get('$in', [])
                    logger.debug(f"Source filter values: {source_filter}")
                    
                    for idx, doc in enumerate(results):
                        logger.debug(f"Checking document {idx}: {type(doc).__name__}")
                        if hasattr(doc, 'meta_data') and doc.meta_data:
                            doc_source = doc.meta_data.get('source')
                            logger.debug(f"  - has meta_data.source: {doc_source}")
                            if doc_source in source_filter:
                                filtered_results.append(doc)
                        else:
                            logger.debug(f"  - no meta_data found")
                    
                    logger.info(f"Manually filtered to {len(filtered_results)} results from {len(results)} total")
                    return filtered_results
                
                return results
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
                logger.error(f"Fallback error type: {type(fallback_error).__name__}")
                logger.error(f"Fallback error args: {fallback_error.args if hasattr(fallback_error, 'args') else 'No args'}")
                logger.error(f"Fallback traceback: {traceback.format_exc()}")
                return []
    
    async def async_search(self, query: str, num_documents: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Async version of search with filtering"""
        try:
            logger.debug("\n" + "="*80)
            logger.debug("ASYNC SEARCH METHOD CALLED")
            logger.debug(f"Query: {query}")
            logger.debug(f"Num documents requested: {num_documents}")
            logger.debug(f"Filters passed to method: {filters}")
            logger.debug("="*80 + "\n")
            
            if self.vector_db is None:
                logger.warning("No vector db provided")
                return []
            
            num_docs = num_documents or self.num_documents
            filters_to_use = self._merge_filters(filters)
            
            logger.info(f"FilteredAgentKnowledge async_search: query='{query[:50]}...', num_docs={num_docs}, filters={filters_to_use}")
            
            if filters_to_use:
                logger.info(f"Async search with filters: {filters_to_use}")
                
                try:
                    # Convert filters to Qdrant format before passing to vector_db
                    qdrant_filters = self._convert_filters_for_qdrant(filters_to_use)
                    
                    if qdrant_filters:
                        # Temporarily store the original _format_filters method
                        original_format_filters = getattr(self.vector_db, '_format_filters', None)
                        
                        # Override _format_filters to return our pre-converted filters
                        def bypass_format_filters(filters_dict):
                            logger.debug(f"Bypassing async format_filters, returning pre-converted: {qdrant_filters}")
                            return qdrant_filters
                        
                        try:
                            self.vector_db._format_filters = bypass_format_filters
                            results = await self.vector_db.async_search(
                                query=query, 
                                limit=num_docs,
                                filters={}  # Pass empty dict since we override _format_filters
                            )
                        finally:
                            # Restore original method
                            if original_format_filters:
                                self.vector_db._format_filters = original_format_filters
                            elif hasattr(self.vector_db, '_format_filters'):
                                delattr(self.vector_db, '_format_filters')
                    else:
                        results = await self.vector_db.async_search(
                            query=query, 
                            limit=num_docs,
                            filters=None
                        )
                    
                    logger.info(f"Async search returned {len(results)} results")
                    return results
                except NotImplementedError:
                    logger.info("Vector db does not support async search, using sync search")
                    return self.search(query=query, num_documents=num_docs, filters=filters_to_use)
            else:
                # No filters, try async then fall back to sync
                try:
                    return await self.vector_db.async_search(query=query, limit=num_docs, filters=None)
                except NotImplementedError:
                    logger.debug("Vector db does not support async search, falling back to sync")
                    return self.search(query=query, num_documents=num_docs, filters=None)
                
        except Exception as e:
            logger.error(f"Error in async search: {e}")
            logger.error(f"Async error type: {type(e).__name__}")
            logger.error(f"Async error args: {e.args if hasattr(e, 'args') else 'No args'}")
            import traceback
            logger.error(f"Async traceback: {traceback.format_exc()}")
            return []
    
    @property
    def document_lists(self) -> Iterator[List[Document]]:
        """Return an iterator of documents from the vector database with filters applied"""
        def document_generator():
            if self.vector_db is None:
                logger.warning("No vector db provided for document_lists")
                return
                
            try:
                # Convert filters for Qdrant
                qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
                
                # If vector_db has a method to get all documents with filters
                if hasattr(self.vector_db, 'get_all_documents'):
                    all_docs = self.vector_db.get_all_documents(filters=qdrant_filters)
                    
                    # Yield documents in batches of 100
                    batch_size = 100
                    for i in range(0, len(all_docs), batch_size):
                        yield all_docs[i:i + batch_size]
                else:
                    # Use scroll for Qdrant - more efficient than search
                    if hasattr(self.vector_db, 'scroll_documents'):
                        logger.info("Using scroll-based document retrieval for document_lists")
                        
                        offset = None
                        while True:
                            docs, next_offset = self.vector_db.scroll_documents(
                                filters=qdrant_filters,
                                limit=100,
                                offset=offset
                            )
                            
                            if not docs:
                                break
                                
                            yield docs
                            offset = next_offset
                            
                            if offset is None:
                                break
                    else:
                        # Fallback to search
                        logger.info("Using search-based document retrieval for document_lists")
                        docs = self.vector_db.search(query="document", limit=1000, filters=qdrant_filters)
                        if docs:
                            yield docs
                    
            except Exception as e:
                logger.error(f"Error in document_lists: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
        return document_generator()
    
    @property
    async def async_document_lists(self) -> AsyncIterator[List[Document]]:
        """Return an async iterator of documents from the vector database with filters applied"""
        async def async_document_generator():
            if self.vector_db is None:
                logger.warning("No vector db provided for async_document_lists")
                return
                
            try:
                # Convert filters for Qdrant
                qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
                
                # Try async scroll first
                if hasattr(self.vector_db, 'async_scroll_documents'):
                    logger.info("Using async scroll-based document retrieval")
                    
                    offset = None
                    while True:
                        docs, next_offset = await self.vector_db.async_scroll_documents(
                            filters=qdrant_filters,
                            limit=100,
                            offset=offset
                        )
                        
                        if not docs:
                            break
                            
                        yield docs
                        offset = next_offset
                        
                        if offset is None:
                            break
                            
                elif hasattr(self.vector_db, 'async_get_all_documents'):
                    all_docs = await self.vector_db.async_get_all_documents(filters=qdrant_filters)
                    
                    # Yield documents in batches
                    batch_size = 100
                    for i in range(0, len(all_docs), batch_size):
                        yield all_docs[i:i + batch_size]
                        
                elif hasattr(self.vector_db, 'get_all_documents'):
                    # Fall back to sync method
                    all_docs = self.vector_db.get_all_documents(filters=qdrant_filters)
                    
                    # Yield documents in batches
                    batch_size = 100
                    for i in range(0, len(all_docs), batch_size):
                        yield all_docs[i:i + batch_size]
                else:
                    # Use search as fallback
                    logger.info("Using search-based document retrieval for async_document_lists")
                    
                    try:
                        docs = await self.vector_db.async_search(query="document", limit=1000, filters=qdrant_filters)
                    except NotImplementedError:
                        docs = self.vector_db.search(query="document", limit=1000, filters=qdrant_filters)
                    
                    if docs:
                        yield docs
                        
            except Exception as e:
                logger.error(f"Error in async_document_lists: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
        return async_document_generator()
    
    def initialize_valid_filters(self) -> None:
        """Initialize valid filters without requiring document_lists"""
        if self.valid_metadata_filters is None:
            self.valid_metadata_filters = set()
        
        # Add known filter fields from custom filters
        if self._custom_filters:
            for key in self._custom_filters.keys():
                self.valid_metadata_filters.add(key)
        
        # Add common metadata fields
        common_fields = {'source', 'file_name', 'collection_id', 'drug_name', 'document_type'}
        self.valid_metadata_filters.update(common_fields)
        
        logger.info(f"Initialized valid filters: {self.valid_metadata_filters}")
    
    # Override insert/upsert methods to apply custom filters
    def load_documents(self, documents: List[Document], upsert: bool = False, skip_existing: bool = True, filters: Optional[Dict[str, Any]] = None) -> None:
        """Load documents with custom filters applied"""
        # Merge provided filters with instance filters
        merged_filters = self._merge_filters(filters)
        if merged_filters:
            merged_filters = self._convert_filters_for_qdrant(merged_filters)
        
        # Call parent method with merged filters
        super().load_documents(documents=documents, upsert=upsert, skip_existing=skip_existing, filters=merged_filters)
    
    async def async_load_documents(self, documents: List[Document], upsert: bool = False, skip_existing: bool = True, filters: Optional[Dict[str, Any]] = None) -> None:
        """Async load documents with custom filters applied"""
        # Merge provided filters with instance filters
        merged_filters = self._merge_filters(filters)
        if merged_filters:
            merged_filters = self._convert_filters_for_qdrant(merged_filters)
        
        # Call parent method with merged filters
        await super().async_load_documents(documents=documents, upsert=upsert, skip_existing=skip_existing, filters=merged_filters)
    
    def get_all_documents_with_filters(self, limit: Optional[int] = None) -> List[Document]:
        """Get all documents from the vector database with instance filters applied"""
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return []
        
        try:
            logger.debug(f"\nget_all_documents_with_filters called")
            logger.debug(f"Vector DB type: {type(self.vector_db).__name__}")
            logger.debug(f"Vector DB methods: {[m for m in dir(self.vector_db) if not m.startswith('_')]}")
            
            # Convert filters for Qdrant
            qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
            
            # Handle limit
            if limit is None:
                limit = 1000
            else:
                # Ensure limit is an integer
                limit = int(limit)
            
            logger.info(f"Getting all documents with filters: {self._custom_filters}, limit: {limit}")
            
            # Try to use direct access if available
            if hasattr(self.vector_db, 'scroll_documents'):
                logger.debug("Using vector_db.scroll_documents method")
                # Use scroll for efficient retrieval
                documents = []
                offset = None
                
                while len(documents) < limit:
                    batch_limit = min(100, limit - len(documents))
                    logger.debug(f"Calling scroll_documents with filters={qdrant_filters}, limit={batch_limit}, offset={offset}")
                    docs, next_offset = self.vector_db.scroll_documents(
                        filters=qdrant_filters,
                        limit=batch_limit,
                        offset=offset
                    )
                    
                    if not docs:
                        logger.debug("No more documents from scroll")
                        break
                        
                    logger.debug(f"Retrieved {len(docs)} documents in this batch")
                    documents.extend(docs)
                    offset = next_offset
                    
                    if offset is None:
                        break
                
                logger.info(f"Retrieved {len(documents)} documents using scroll")
                return documents
            else:
                # Fallback to search
                logger.debug("No scroll_documents method, falling back to search")
                logger.debug(f"Calling search with query='document', limit={limit}, filters={qdrant_filters}")
                
                documents = self.vector_db.search(
                    query="document",  # Generic query
                    limit=limit,
                    filters=qdrant_filters
                )
                
                logger.info(f"Retrieved {len(documents)} documents with filters using search")
                logger.debug(f"Document types: {[type(d).__name__ for d in documents[:3]] if documents else 'No documents'}")
                return documents
            
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {e.args if hasattr(e, 'args') else 'No args'}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    async def async_get_all_documents_with_filters(self, limit: Optional[int] = None) -> List[Document]:
        """Async version to get all documents with filters"""
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return []
        
        try:
            # Convert filters for Qdrant
            qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
            
            # Handle limit
            if limit is None:
                limit = 1000
            else:
                limit = int(limit)
            
            logger.info(f"Async getting all documents with filters: {self._custom_filters}, limit: {limit}")
            
            # Try async scroll first
            if hasattr(self.vector_db, 'async_scroll_documents'):
                documents = []
                offset = None
                
                while len(documents) < limit:
                    batch_limit = min(100, limit - len(documents))
                    docs, next_offset = await self.vector_db.async_scroll_documents(
                        filters=qdrant_filters,
                        limit=batch_limit,
                        offset=offset
                    )
                    
                    if not docs:
                        break
                        
                    documents.extend(docs)
                    offset = next_offset
                    
                    if offset is None:
                        break
                
                logger.info(f"Retrieved {len(documents)} documents using async scroll")
                return documents
            else:
                # Fallback to search
                try:
                    documents = await self.vector_db.async_search(
                        query="document",
                        limit=limit,
                        filters=qdrant_filters
                    )
                except NotImplementedError:
                    # Fall back to sync
                    documents = self.vector_db.search(
                        query="document",
                        limit=limit,
                        filters=qdrant_filters
                    )
                
                logger.info(f"Retrieved {len(documents)} documents with filters")
                return documents
            
        except Exception as e:
            logger.error(f"Error in async get all documents: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def update_filters(self, new_filters: Optional[Dict[str, Any]]) -> None:
        """Update the instance filters"""
        self._custom_filters = new_filters
        logger.info(f"Updated filters to: {new_filters}")
        
        # Re-initialize valid metadata filters
        self.initialize_valid_filters()
    
    def add_filter(self, key: str, value: Any) -> None:
        """Add a single filter to the existing filters"""
        if self._custom_filters is None:
            self._custom_filters = {}
        
        self._custom_filters[key] = value
        logger.info(f"Added filter: {key} = {value}")
        
        # Update valid metadata filters
        if self.valid_metadata_filters is None:
            self.valid_metadata_filters = set()
        self.valid_metadata_filters.add(key)
    
    def remove_filter(self, key: str) -> None:
        """Remove a filter by key"""
        if self._custom_filters and key in self._custom_filters:
            del self._custom_filters[key]
            logger.info(f"Removed filter: {key}")
    
    def clear_filters(self) -> None:
        """Clear all custom filters"""
        self._custom_filters = None
        logger.info("Cleared all filters")
    
    def get_current_filters(self) -> Optional[Dict[str, Any]]:
        """Get the current custom filters"""
        return self._custom_filters.copy() if self._custom_filters else None
    
    def get_document_count(self) -> int:
        """Get the count of unique source documents matching the current filters"""
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return 0
        
        try:
            # Get all documents with current filters to count unique sources
            qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
            
            logger.info(f"Counting unique source documents with filters: {self._custom_filters}")
            logger.debug(f"Vector DB type for counting: {type(self.vector_db).__name__}")
            
            # Get documents
            documents = self.get_all_documents_with_filters(limit=10000)
            
            # Count unique sources
            unique_sources = set()
            for doc in documents:
                if doc.meta_data and 'source' in doc.meta_data:
                    unique_sources.add(doc.meta_data['source'])
            
            count = len(unique_sources)
            logger.info(f"Unique source document count with filters: {count}")
            
            return int(count)
            
        except Exception as e:
            logger.error(f"Error getting document count: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0
    
    async def async_get_document_count(self) -> int:
        """Async version to get count of unique source documents"""
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return 0
        
        try:
            logger.info(f"Async counting unique source documents with filters: {self._custom_filters}")
            
            # Get documents
            documents = await self.async_get_all_documents_with_filters(limit=10000)
            
            # Count unique sources
            unique_sources = set()
            for doc in documents:
                if doc.meta_data and 'source' in doc.meta_data:
                    unique_sources.add(doc.meta_data['source'])
            
            count = len(unique_sources)
            logger.info(f"Unique source document count with filters: {count}")
            
            return int(count)
            
        except Exception as e:
            logger.error(f"Error in async get document count: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0
    
    def get_document_count_by_metadata(self, metadata_field: str = "source") -> Dict[str, int]:
        """Get document counts grouped by a metadata field (e.g., source file)"""
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return {}
        
        try:
            # Get all documents with current filters
            documents = self.get_all_documents_with_filters(limit=10000)
            
            # Group by metadata field
            counts = {}
            for doc in documents:
                if doc.meta_data and metadata_field in doc.meta_data:
                    field_value = doc.meta_data[metadata_field]
                    counts[field_value] = counts.get(field_value, 0) + 1
            
            logger.info(f"Document counts by {metadata_field}: {counts}")
            return counts
            
        except Exception as e:
            logger.error(f"Error getting document count by metadata: {e}")
            return {}
    
    async def async_get_document_count_by_metadata(self, metadata_field: str = "source", collection_name: Optional[str] = None) -> Dict[str, int]:
        """
        Async version to get document counts grouped by metadata field
        
        Args:
            metadata_field: The metadata field to group by (default: "source")
            collection_name: Optional collection name to use with QdrantUtil
        """
        try:
            # Use QdrantUtil for cleaner access
            from utils.qdrant_util import QdrantUtil
            qdrant_util = QdrantUtil.get_instance()
            
            # Determine collection name
            if collection_name is None and self.vector_db:
                if hasattr(self.vector_db, 'collection'):
                    collection_name = self.vector_db.collection
                elif hasattr(self.vector_db, 'collection_name'):
                    collection_name = self.vector_db.collection_name
                elif hasattr(self.vector_db, '_collection_name'):
                    collection_name = self.vector_db._collection_name
            
            if collection_name is None:
                logger.warning("Could not determine collection name")
                return {}
            
            logger.info(f"Using QdrantUtil for counting by {metadata_field} in collection: {collection_name}")
            
            # Convert filters
            qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
            
            # Use scroll to get documents efficiently
            offset = None
            counts = {}
            
            while True:
                result = qdrant_util.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filters,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                if not result[0]:
                    break
                
                points, next_offset = result
                
                # Count by metadata field
                for point in points:
                    # Get field from meta_data (new Agno format) or fallback to root payload (old format)
                    meta_data = point.payload.get("meta_data", {})
                    field_value = meta_data.get(metadata_field) or point.payload.get(metadata_field)
                    if field_value:
                        counts[field_value] = counts.get(field_value, 0) + 1
                
                offset = next_offset
                if offset is None:
                    break
            
            logger.info(f"Document counts by {metadata_field}: {counts}")
            return counts
            
        except Exception as e:
            logger.error(f"Error in async get document count by metadata: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}
    
    def get_collection_vector_stats(self, include_documents: bool = True, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get vector statistics for a collection
        """
        try:
            from utils.qdrant_util import QdrantUtil
            qdrant_util = QdrantUtil.get_instance()
            
            # Determine collection name
            if collection_name is None:
                if hasattr(self.vector_db, 'collection'):
                    collection_name = self.vector_db.collection
                elif hasattr(self.vector_db, 'collection_name'):
                    collection_name = self.vector_db.collection_name
                elif hasattr(self.vector_db, '_collection_name'):
                    collection_name = self.vector_db._collection_name
                else:
                    logger.warning("Could not determine collection name")
                    return {
                        "total_vectors": 0,
                        "unique_documents": 0,
                        "average_chunks_per_document": 0,
                        "documents": []
                    }
            
            logger.info(f"Getting vector stats for collection: {collection_name}")
            
            # Get collection stats
            stats = qdrant_util.get_collection_stats(collection_name)
            total_vectors = stats.get("total_documents", 0)
            
            if total_vectors > 0:
                # Always count unique documents for statistics
                qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
                
                # Scroll through collection to count unique documents
                offset = None
                documents_map = {}
                
                while True:
                    result = qdrant_util.client.scroll(
                        collection_name=collection_name,
                        scroll_filter=qdrant_filters,
                        limit=1000,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    if not result[0]:
                        break
                    
                    points, next_offset = result
                    
                    # Extract unique documents with their details
                    for point in points:
                        # Get fields from meta_data (new Agno format) or fallback to root payload (old format)
                        meta_data = point.payload.get("meta_data", {})
                        
                        # Try multiple approaches to get document identifier
                        doc_id = meta_data.get("source_file_id") or point.payload.get("source_file_id")
                        if not doc_id:
                            # Fallback to source filename as identifier
                            source_file = meta_data.get("source") or point.payload.get("source")
                            if source_file:
                                doc_id = f"source_{hash(source_file) % 1000000}"
                        
                        file_name = meta_data.get("file_name") or point.payload.get("file_name") or meta_data.get("source") or point.payload.get("source")
                        drug_name = meta_data.get("drug_name") or point.payload.get("drug_name", "")
                        
                        if doc_id:
                            if doc_id not in documents_map:
                                documents_map[doc_id] = {
                                    "file_name": file_name or f"Unknown (ID: {doc_id})",
                                    "chunk_count": 0,
                                    "drug_name": drug_name
                                }
                            documents_map[doc_id]["chunk_count"] += 1
                    
                    offset = next_offset
                    if offset is None:
                        break
                
                # Calculate statistics
                unique_doc_count = len(documents_map)
                avg_chunks_per_doc = sum(d["chunk_count"] for d in documents_map.values()) / unique_doc_count if unique_doc_count > 0 else 0
                
                # Only include document details if requested
                if include_documents:
                    # Convert to sorted list
                    all_documents = [
                        {
                            "document_id": doc_id,
                            "file_name": doc_info["file_name"],
                            "drug_name": doc_info["drug_name"],
                            "chunk_count": doc_info["chunk_count"]
                        }
                        for doc_id, doc_info in sorted(documents_map.items(), key=lambda x: x[1]["file_name"])
                    ]
                    
                    return {
                        "total_vectors": total_vectors,
                        "unique_documents": unique_doc_count,
                        "average_chunks_per_document": round(avg_chunks_per_doc, 2),
                        "documents": all_documents
                    }
                else:
                    # Return counts only, no document details
                    return {
                        "total_vectors": total_vectors,
                        "unique_documents": unique_doc_count,
                        "average_chunks_per_document": round(avg_chunks_per_doc, 2),
                        "documents": []
                    }
            else:
                return {
                    "total_vectors": total_vectors,
                    "unique_documents": 0,
                    "average_chunks_per_document": 0,
                    "documents": []
                }
                
        except Exception as e:
            logger.error(f"Error getting collection vector stats: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "total_vectors": 0,
                "unique_documents": 0,
                "average_chunks_per_document": 0,
                "documents": [],
                "error": str(e)
            }
    
    async def async_get_collection_vector_stats(self, include_documents: bool = True, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Async version of get_collection_vector_stats
        """
        # For Qdrant, the operations are synchronous anyway, so we just call the sync version
        return self.get_collection_vector_stats(include_documents=include_documents, collection_name=collection_name)
    
    def get_direct_collection_stats(self) -> Dict[str, int]:
        """
        Get collection statistics using direct collection access
        """
        if self.vector_db is None:
            logger.warning("No vector db provided")
            return {"total_documents": 0, "unique_sources": 0}
        
        try:
            from utils.qdrant_util import QdrantUtil
            qdrant_util = QdrantUtil.get_instance()
            
            # Get collection name
            collection_name = None
            if hasattr(self.vector_db, 'collection'):
                collection_name = self.vector_db.collection
            elif hasattr(self.vector_db, 'collection_name'):
                collection_name = self.vector_db.collection_name
            elif hasattr(self.vector_db, '_collection_name'):
                collection_name = self.vector_db._collection_name
            
            if not collection_name:
                logger.warning("Could not determine collection name")
                return {"total_documents": 0, "unique_sources": 0}
            
            # Get count
            qdrant_filters = self._convert_filters_for_qdrant(self._custom_filters) if self._custom_filters else None
            
            if qdrant_filters:
                count_result = qdrant_util.client.count(
                    collection_name=collection_name,
                    count_filter=qdrant_filters,
                    exact=True
                )
            else:
                count_result = qdrant_util.client.count(
                    collection_name=collection_name,
                    exact=True
                )
            
            total_docs = count_result.count
            
            # Count unique sources - need to scroll through
            unique_sources = set()
            offset = None
            
            while True:
                result = qdrant_util.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filters,
                    limit=1000,
                    offset=offset,
                    with_payload=True,  # Get all payload since source is nested in meta_data
                    with_vectors=False
                )
                
                if not result[0]:
                    break
                
                points, next_offset = result
                
                for point in points:
                    # Get source from meta_data (new Agno format) or fallback to root payload (old format)
                    meta_data = point.payload.get("meta_data", {})
                    source = meta_data.get('source') or point.payload.get('source')
                    if source:
                        unique_sources.add(source)
                
                offset = next_offset
                if offset is None:
                    break
            
            unique_count = len(unique_sources)
            
            logger.info(f"Direct collection stats: {total_docs} total documents, {unique_count} unique sources")
            
            return {
                "total_documents": total_docs,
                "unique_sources": unique_count
            }
            
        except Exception as e:
            logger.error(f"Error getting direct collection stats: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"total_documents": 0, "unique_sources": 0}