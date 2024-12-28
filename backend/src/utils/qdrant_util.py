"""
Qdrant Utility Class for Vector Database Operations
Mirrors the functionality of ChromaDBUtil but for Qdrant
"""

import re
import uuid
import logging
import hashlib
import threading
from typing import List, Dict, Any, Optional, Tuple, Iterator
from datetime import datetime
import json

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, 
    MatchValue, Range, PointIdsList, SearchParams,
    UpdateStatus, CountResult, ScrollResult, MatchAny
)

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from textwrap import wrap

from utils.qdrant_singleton import get_qdrant_client
from config.settings import settings

logger = logging.getLogger(__name__)


class QdrantUtil:
    """
    Utility class for interacting with Qdrant vector database.
    Provides methods for document storage, retrieval, and search.
    """
    
    _instances = {}
    _lock = threading.Lock()
    
    def __init__(self, host: str = None, port: int = None, use_persistent_client: bool = True):
        """Initialize QdrantUtil with connection parameters."""
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.vector_size = 768  # Gemini embedding dimension
        self.distance_metric = Distance.COSINE
        
        if use_persistent_client:
            self.client = get_qdrant_client()
        else:
            # Create a new client instance
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=settings.QDRANT_API_KEY,
                https=settings.QDRANT_HTTPS,
                timeout=60.0
            )
        
        logger.info(f"QdrantUtil initialized with host={self.host}, port={self.port}")
    
    @classmethod
    def get_instance(cls, host: str = None, port: int = None, use_persistent_client: bool = True) -> "QdrantUtil":
        """Get or create a singleton instance of QdrantUtil."""
        key = f"{host or settings.QDRANT_HOST}:{port or settings.QDRANT_PORT}"
        
        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    cls._instances[key] = cls(host, port, use_persistent_client)
        
        return cls._instances[key]
    
    def sanitize_collection_name(self, collection_name: str) -> str:
        """
        Sanitize collection name for Qdrant.
        Qdrant allows alphanumeric, dash, and underscore.
        """
        # Replace spaces with underscores
        sanitized = collection_name.replace(" ", "_")
        # Remove any characters that aren't alphanumeric, dash, or underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', sanitized)
        # Ensure it starts with alphanumeric
        if sanitized and not sanitized[0].isalnum():
            sanitized = 'c_' + sanitized
        # Limit length to 255 characters
        sanitized = sanitized[:255]
        
        if not sanitized:
            sanitized = "default_collection"
        
        return sanitized.lower()
    
    def get_or_create_collection(self, collection_name: str, embedding_function=None) -> str:
        """
        Get or create a collection in Qdrant.
        Returns the collection name.
        """
        try:
            sanitized_name = self.sanitize_collection_name(collection_name)
            logger.info(f"Getting or creating collection: {sanitized_name}")
            
            # Check if collection exists
            collections = self.client.get_collections()
            exists = any(col.name == sanitized_name for col in collections.collections)
            
            if not exists:
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=sanitized_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=self.distance_metric
                    ),
                    replication_factor=settings.QDRANT_COLLECTION_REPLICATION_FACTOR,
                    shard_number=1,
                    on_disk_payload=True
                )
                logger.info(f"Created new collection: {sanitized_name}")
            else:
                logger.debug(f"Collection already exists: {sanitized_name}")
            
            return sanitized_name
            
        except Exception as e:
            logger.error(f"Error creating/getting collection {collection_name}: {e}")
            raise
    
    def _generate_point_id(self, content: str, metadata: Dict[str, Any]) -> str:
        """Generate a unique ID for a point based on content and metadata."""
        # Create a unique string from content and key metadata
        unique_str = f"{content[:100]}"
        if metadata.get("source"):
            unique_str += f"_{metadata['source']}"
        if metadata.get("chunk_index"):
            unique_str += f"_{metadata['chunk_index']}"
        
        # Generate UUID from hash for consistency
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_str))
    
    def _chunk_large_document(self, document: Dict[str, Any], max_chunk_size: int = 15000) -> List[Dict[str, Any]]:
        """
        Split large documents into smaller chunks.
        Similar to ChromaDB implementation.
        """
        content = document.get("page_content", document.get("content", ""))
        metadata = document.get("metadata", {})
        
        if len(content) <= max_chunk_size:
            return [document]
        
        # Split text into chunks of max_chunk_size using textwrap
        chunks = []
        # First try to split on paragraphs
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            if len(para) <= max_chunk_size:
                chunks.append(para)
            else:
                # If paragraph is too long, split into lines
                lines = para.split('\n')
                current_chunk = []
                current_length = 0
                
                for line in lines:
                    if current_length + len(line) + 1 > max_chunk_size and current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1  # +1 for the newline
                
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
        
        chunked_docs = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(sentences)
            chunk_metadata["is_chunked"] = True
            
            chunked_docs.append({
                "page_content": chunk,
                "content": chunk,
                "metadata": chunk_metadata
            })
        
        return chunked_docs
    
    def document_exists(self, file_name: str, collection_name: str) -> bool:
        """Check if documents from a file already exist in the collection."""
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Search for documents with the given source file
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=file_name)
                    )
                ]
            )
            
            result = self.client.count(
                collection_name=collection_name,
                count_filter=filter_condition,
                exact=False
            )
            
            exists = result.count > 0
            logger.info(f"Document {file_name} exists in {collection_name}: {exists}")
            return exists
            
        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            return False
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str = "fda_documents",
        batch_size: int = 100,
        embeddings: Optional[List[List[float]]] = None,
        ids: Optional[List[str]] = None,
        embedding_function=None
    ) -> Dict[str, Any]:
        """
        Add documents to Qdrant collection.
        
        Args:
            documents: List of documents with content and metadata
            collection_name: Name of the collection
            batch_size: Number of documents to process in each batch
            embeddings: Pre-computed embeddings (optional)
            ids: Document IDs (optional)
            embedding_function: Function to generate embeddings
            
        Returns:
            Dictionary with status and statistics
        """
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            self.get_or_create_collection(collection_name, embedding_function)
            
            if not documents:
                return {"status": "success", "documents_added": 0}
            
            # Get embedding function if not provided
            if embeddings is None and embedding_function is None:
                from utils.llm_util import get_embeddings_function
                embedding_function = get_embeddings_function()
            
            # Process documents in batches
            total_added = 0
            failed_docs = []
            points_to_upsert = []
            
            for i, doc in enumerate(documents):
                try:
                    # Handle different document formats
                    if isinstance(doc, dict):
                        content = doc.get("page_content", doc.get("content", ""))
                        metadata = doc.get("metadata", {})
                    else:
                        content = str(doc)
                        metadata = {}
                    
                    # Generate ID if not provided
                    point_id = ids[i] if ids and i < len(ids) else self._generate_point_id(content, metadata)
                    
                    # Get embedding
                    if embeddings and i < len(embeddings):
                        vector = embeddings[i]
                    else:
                        # Generate embedding
                        vector = embedding_function.embed_query(content)
                    
                    # Ensure vector is the right size
                    if len(vector) != self.vector_size:
                        logger.warning(f"Vector size mismatch: expected {self.vector_size}, got {len(vector)}")
                        continue
                    
                    # Create point with Agno-compatible format
                    point = PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "content": content,
                            "name": metadata.get("source", metadata.get("file_name", "unknown")),
                            "usage": {},  # Required by Agno library
                            "meta_data": {
                                **metadata,
                                "original_content": metadata.get("original_content", content),
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                    )
                    points_to_upsert.append(point)
                    
                    # Upsert batch if full
                    if len(points_to_upsert) >= batch_size:
                        self.client.upsert(
                            collection_name=collection_name,
                            points=points_to_upsert,
                            wait=True
                        )
                        total_added += len(points_to_upsert)
                        points_to_upsert = []
                        
                except Exception as e:
                    logger.error(f"Error processing document {i}: {e}")
                    failed_docs.append({"index": i, "error": str(e)})
            
            # Upsert remaining points
            if points_to_upsert:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points_to_upsert,
                    wait=True
                )
                total_added += len(points_to_upsert)
            
            logger.info(f"Added {total_added} documents to {collection_name}")
            
            return {
                "status": "success",
                "documents_added": total_added,
                "failed_documents": failed_docs,
                "collection_name": collection_name
            }
            
        except Exception as e:
            logger.error(f"Error adding documents to Qdrant: {e}")
            raise
    
    def search_documents(
        self,
        query: str,
        collection_name: str = "fda_documents",
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        embedding_function=None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents in the collection.
        
        Args:
            query: Search query
            collection_name: Name of the collection
            k: Number of results to return
            filters: Metadata filters
            embedding_function: Function to generate query embedding
            include_metadata: Whether to include metadata in results
            
        Returns:
            List of search results with content, metadata, and scores
        """
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Get embedding function if not provided
            if embedding_function is None:
                from utils.llm_util import get_embeddings_function
                embedding_function = get_embeddings_function()
            
            # Generate query embedding
            query_vector = embedding_function.embed_query(query)
            
            # Convert filters to Qdrant format
            qdrant_filter = None
            if filters:
                qdrant_filter = self._convert_filters_to_qdrant(filters)
            
            # Search
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=k,
                with_payload=include_metadata,
                with_vectors=False
            )
            
            # Format results - expect Agno format only
            results = []
            for hit in search_result:
                payload = hit.payload
                
                # Extract from Agno format
                content = payload.get("content", "")
                metadata = payload.get("meta_data", {})
                
                result = {
                    "content": content,
                    "metadata": metadata,
                    "score": hit.score,
                    "id": str(hit.id)
                }
                results.append(result)
            
            logger.info(f"Found {len(results)} documents for query in {collection_name}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def _convert_filters_to_qdrant(self, filters: Dict[str, Any]) -> Filter:
        """Convert filter dictionary to Qdrant Filter format.
        Adds meta_data prefix for Agno compatibility."""
        conditions = []
        
        for key, value in filters.items():
            # Always add meta_data prefix (filters should only target metadata fields)
            if not key.startswith("meta_data."):
                key = f"meta_data.{key}"
            if isinstance(value, dict):
                # Handle operators
                if "$in" in value:
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchAny(any=value["$in"])
                        )
                    )
                elif "$eq" in value:
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value["$eq"])
                        )
                    )
                elif "$gte" in value and "$lte" in value:
                    conditions.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                gte=value["$gte"],
                                lte=value["$lte"]
                            )
                        )
                    )
            else:
                # Direct equality
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
        
        return Filter(must=conditions) if conditions else None
    
    def delete_documents_by_metadata(
        self,
        collection_name: str,
        metadata_filter: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delete documents matching metadata filter."""
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Convert filter
            qdrant_filter = self._convert_filters_to_qdrant(metadata_filter)
            
            if not qdrant_filter:
                return {"status": "error", "message": "No filter provided"}
            
            # Delete matching points
            result = self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=qdrant_filter
                ),
                wait=True
            )
            
            return {
                "status": "success",
                "operation_id": str(result.operation_id) if hasattr(result, 'operation_id') else None
            }
            
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_documents_by_source_file(
        self,
        source_file_name: str,
        collection_name: str
    ) -> bool:
        """Delete all documents from a specific source file."""
        try:
            result = self.delete_documents_by_metadata(
                collection_name=collection_name,
                metadata_filter={"source": source_file_name}
            )
            return result.get("status") == "success"
            
        except Exception as e:
            logger.error(f"Error deleting documents by source: {e}")
            return False
    
    def get_collection_stats(self, collection_name: str = "fda_documents") -> Dict[str, Any]:
        """Get statistics about a collection."""
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Get collection info
            collection_info = self.client.get_collection(collection_name)
            
            # Get count
            count_result = self.client.count(
                collection_name=collection_name,
                exact=True
            )
            
            return {
                "collection_name": collection_name,
                "total_documents": count_result.count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value,
                "on_disk": collection_info.config.params.on_disk_payload,
                "status": collection_info.status.value
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                "error": str(e),
                "collection_name": collection_name,
                "total_documents": 0
            }
    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        try:
            sanitized_name = self.sanitize_collection_name(collection_name)
            collections = self.client.get_collections()
            return any(col.name == sanitized_name for col in collections.collections)
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            sanitized_name = self.sanitize_collection_name(collection_name)
            self.client.delete_collection(collection_name=sanitized_name)
            logger.info(f"Deleted collection: {sanitized_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
    
    def query_with_llm(
        self,
        query: str,
        collection_name: str = "fda_documents",
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query documents and generate response using LLM.
        """
        try:
            # Search for relevant documents
            search_results = self.search_documents(
                query=query,
                collection_name=collection_name,
                k=k,
                filters=filters
            )
            
            if not search_results:
                return {
                    "answer": "I couldn't find any relevant information in the documents.",
                    "source_documents": []
                }
            
            # Convert to LangChain documents
            documents = []
            for result in search_results:
                doc = Document(
                    page_content=result["content"],
                    metadata=result["metadata"]
                )
                documents.append(doc)
            
            # Get LLM
            from utils.llm_util import get_llm
            llm = get_llm()
            
            # Create prompt and generate response using modern langchain approach
            context = "\n\n".join([doc.page_content for doc in documents])
            prompt_text = (
                "Use the following pieces of context to answer the question. "
                "If you don't know the answer, just say that you don't know.\n\n"
                f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
            )
            response = llm.invoke(prompt_text)
            
            # Extract text from response if it's a message object
            if hasattr(response, 'content'):
                response = response.content
            elif isinstance(response, str):
                response = response
            else:
                response = str(response)
            
            return {
                "answer": response,
                "source_documents": [
                    {
                        "content": doc.page_content[:200] + "...",
                        "metadata": doc.metadata
                    }
                    for doc in documents
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in query_with_llm: {e}")
            return {
                "answer": f"An error occurred: {str(e)}",
                "source_documents": []
            }
    
    def get_document_vectors(self, collection_name: str, document_id: str) -> Dict[str, Any]:
        """Get vectors and metadata for a specific document."""
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Retrieve point by ID
            points = self.client.retrieve(
                collection_name=collection_name,
                ids=[document_id],
                with_payload=True,
                with_vectors=True
            )
            
            if not points:
                return {"error": "Document not found"}
            
            point = points[0]
            return {
                "id": str(point.id),
                "vector": point.vector,
                "metadata": point.payload,
                "content": point.payload.get("content", "")
            }
            
        except Exception as e:
            logger.error(f"Error getting document vectors: {e}")
            return {"error": str(e)}
    
    def copy_vectors_to_collection(
        self,
        source_collection: str,
        target_collection: str,
        source_filter: Optional[Dict[str, Any]] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Copy vectors from one collection to another."""
        try:
            source_collection = self.sanitize_collection_name(source_collection)
            target_collection = self.sanitize_collection_name(target_collection)
            
            # Create target collection
            self.get_or_create_collection(target_collection)
            
            # Convert filter
            qdrant_filter = None
            if source_filter:
                qdrant_filter = self._convert_filters_to_qdrant(source_filter)
            
            # Scroll through source collection
            offset = None
            total_copied = 0
            
            while True:
                scroll_result = self.client.scroll(
                    collection_name=source_collection,
                    scroll_filter=qdrant_filter,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True
                )
                
                if not scroll_result[0]:
                    break
                
                points, next_offset = scroll_result
                
                # Copy points to target collection
                self.client.upsert(
                    collection_name=target_collection,
                    points=points,
                    wait=True
                )
                
                total_copied += len(points)
                offset = next_offset
                
                if offset is None:
                    break
            
            logger.info(f"Copied {total_copied} vectors from {source_collection} to {target_collection}")
            
            return {
                "status": "success",
                "vectors_copied": total_copied,
                "source_collection": source_collection,
                "target_collection": target_collection
            }
            
        except Exception as e:
            logger.error(f"Error copying vectors: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def query_collection(self, collection_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Simple query interface for collection."""
        return self.search_documents(
            query=query,
            collection_name=collection_name,
            k=k
        )
    
    def grade_documents(
        self,
        documents: List[Document],
        query: str
    ) -> Tuple[List[Document], List[Document]]:
        """
        Grade documents for relevance to a query.
        Returns (relevant_docs, irrelevant_docs)
        """
        try:
            from utils.llm_util import get_llm_grading
            llm = get_llm_grading()
            
            relevant_docs = []
            irrelevant_docs = []
            
            for doc in documents:
                try:
                    # Create grading prompt
                    prompt = f"""You are a grader assessing relevance of a retrieved document to a user question.
                    
                    Retrieved document: {doc.page_content[:1000]}
                    
                    User question: {query}
                    
                    If the document contains keyword(s) or semantic meaning related to the question, grade it as relevant.
                    Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.
                    
                    Respond with only 'yes' or 'no'."""
                    
                    response = llm.invoke(prompt)
                    grade = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
                    
                    if 'yes' in grade:
                        relevant_docs.append(doc)
                    else:
                        irrelevant_docs.append(doc)
                        
                except Exception as e:
                    logger.warning(f"Error grading document: {e}")
                    # If grading fails, include the document as relevant to be safe
                    relevant_docs.append(doc)
            
            return relevant_docs, irrelevant_docs
            
        except Exception as e:
            logger.error(f"Error in grade_documents: {e}")
            # Return all as relevant if grading fails
            return documents, []
    
    def query_with_llm_enhanced_metadata(
        self,
        query: str,
        metadata_name: str,
        source_file_name: str,
        collection_name: str = "fda_documents",
        k: int = 10,
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Enhanced query specifically for metadata extraction with confidence scoring.
        """
        try:
            # Search for relevant documents with metadata filters
            metadata_filter = {
                "source": source_file_name,
                "metadata_name": {"$eq": metadata_name}
            }
            
            # First try to find documents with this specific metadata
            search_results = self.search_documents(
                query=query,
                collection_name=collection_name,
                k=k,
                filters=metadata_filter
            )
            
            # If no results, search more broadly
            if not search_results:
                search_results = self.search_documents(
                    query=query,
                    collection_name=collection_name,
                    k=k,
                    filters={"source": source_file_name}
                )
            
            if not search_results:
                return {
                    "answer": "Not Found",
                    "confidence": 0.0,
                    "source_documents": []
                }
            
            # Convert to Document objects
            documents = []
            for result in search_results:
                doc = Document(
                    page_content=result["content"],
                    metadata=result["metadata"]
                )
                documents.append(doc)
            
            # Grade documents for relevance
            relevant_docs, _ = self.grade_documents(documents, query)
            
            if not relevant_docs:
                return {
                    "answer": "Not Found",
                    "confidence": 0.0,
                    "source_documents": []
                }
            
            # Generate response using LLM
            from utils.llm_util import get_llm
            llm = get_llm()
            
            # Create extraction prompt
            context = "\n\n".join([doc.page_content for doc in relevant_docs[:3]])
            
            prompt = f"""Based on the following context, extract the {metadata_name} information.
            
            Context:
            {context}
            
            Question: What is the {metadata_name}?
            
            Instructions:
            - Extract ONLY the specific {metadata_name} value
            - If the information is not found, respond with exactly "Not Found"
            - Do not include explanations or additional text
            
            Answer:"""
            
            response = llm.invoke(prompt)
            answer = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Calculate confidence based on relevance scores
            if search_results:
                avg_score = sum(r["score"] for r in search_results[:3]) / min(3, len(search_results))
                confidence = min(avg_score, 1.0)
            else:
                confidence = 0.0
            
            # Adjust confidence if answer is "Not Found"
            if "not found" in answer.lower():
                confidence = 0.0
            
            return {
                "answer": answer,
                "confidence": confidence,
                "source_documents": [
                    {
                        "content": doc.page_content[:200] + "...",
                        "metadata": doc.metadata
                    }
                    for doc in relevant_docs[:3]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in query_with_llm_enhanced_metadata: {e}")
            return {
                "answer": f"Error: {str(e)}",
                "confidence": 0.0,
                "source_documents": []
            }
    
    def get_document_count_by_source_file(
        self,
        source_file_name: str,
        collection_name: str = "fda_documents"
    ) -> int:
        """Get count of documents for a specific source file."""
        try:
            collection_name = self.sanitize_collection_name(collection_name)
            
            # Count documents with source filter
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=source_file_name)
                    )
                ]
            )
            
            result = self.client.count(
                collection_name=collection_name,
                count_filter=filter_condition,
                exact=True
            )
            
            return result.count
            
        except Exception as e:
            logger.error(f"Error getting document count by source: {e}")
            return 0
    
    def copy_document_by_source_file_id(
        self,
        source_file_id: int,
        source_collection_name: str,
        target_collection_name: str,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Copy all documents from a source file ID to another collection.
        """
        try:
            source_collection_name = self.sanitize_collection_name(source_collection_name)
            target_collection_name = self.sanitize_collection_name(target_collection_name)
            
            # Create target collection
            self.get_or_create_collection(target_collection_name)
            
            # Create filter for source_file_id
            source_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file_id",
                        match=MatchValue(value=source_file_id)
                    )
                ]
            )
            
            # Scroll through source collection
            offset = None
            total_copied = 0
            
            while True:
                scroll_result = self.client.scroll(
                    collection_name=source_collection_name,
                    scroll_filter=source_filter,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True
                )
                
                if not scroll_result[0]:
                    break
                
                points, next_offset = scroll_result
                
                # Copy points to target collection
                self.client.upsert(
                    collection_name=target_collection_name,
                    points=points,
                    wait=True
                )
                
                total_copied += len(points)
                offset = next_offset
                
                if offset is None:
                    break
            
            logger.info(f"Copied {total_copied} documents from source_file_id {source_file_id}")
            
            return {
                "status": "success",
                "documents_copied": total_copied,
                "source_file_id": source_file_id
            }
            
        except Exception as e:
            logger.error(f"Error copying documents by source file ID: {e}")
            return {
                "status": "error",
                "error": str(e),
                "documents_copied": 0
            }
    
    def query_with_llm_multi_doc(
        self,
        query: str,
        collection_name: str = "fda_documents",
        n_results_per_doc: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Tuple[str, str]]] = None,
        expected_sources: Optional[List[str]] = None
    ) -> str:
        """
        Enhanced query for multiple documents with token limit handling and intelligent chunking.
        Adapted for Qdrant vector database.
        """
        try:
            from utils.llm_util import get_llm
            
            logger.info(f"Multi-doc query: {query}")
            logger.info(f"Expected sources: {expected_sources}")
            
            # Token limits for Gemini models
            GEMINI_MAX_TOKENS = 1_000_000  # Conservative limit (actual is 1,048,575)
            CHARS_PER_TOKEN_ESTIMATE = 4  # Rough estimate: 1 token = 4 characters
            MAX_CONTEXT_CHARS = GEMINI_MAX_TOKENS * CHARS_PER_TOKEN_ESTIMATE  # ~4M chars
            RESERVE_TOKENS = 50_000  # Reserve for prompt and response
            MAX_USABLE_CHARS = (GEMINI_MAX_TOKENS - RESERVE_TOKENS) * CHARS_PER_TOKEN_ESTIMATE
            
            # Retrieve documents from Qdrant
            all_docs = []
            drug_names = []
            docs_by_source = {}  # Track docs by source for better organization
            
            if expected_sources and filter_dict and "source" in filter_dict and "$in" in filter_dict["source"]:
                source_files = filter_dict["source"]["$in"]
                
                # Extract drug names from source files for better prompting
                for source_file in source_files:
                    if source_file:
                        # Extract drug name from filename (assuming format like "DRUGNAME_label.pdf")
                        drug_name = source_file.split('_')[0].upper()
                        drug_names.append(drug_name)
                
                # Retrieve documents for each drug with reduced chunk count
                adjusted_chunks_per_doc = min(n_results_per_doc, 3)  # Limit chunks per doc
                for source_file in source_files:
                    # Search with specific source filter
                    source_filter = {"source": source_file}
                    search_results = self.search_documents(
                        query=query,
                        collection_name=collection_name,
                        k=adjusted_chunks_per_doc,
                        filters=source_filter
                    )
                    
                    # Convert search results to Document-like objects for compatibility
                    docs = []
                    for result in search_results:
                        doc = Document(
                            page_content=result["content"],
                            metadata=result["metadata"]
                        )
                        docs.append(doc)
                    
                    docs_by_source[source_file] = docs
                    all_docs.extend(docs)
                    logger.info(f"Retrieved {len(docs)} chunks from {source_file}")
            
            # If no documents retrieved, fall back to general search
            if not all_docs:
                search_results = self.search_documents(
                    query=query,
                    collection_name=collection_name,
                    k=min(n_results_per_doc * 2, 10),
                    filters=filter_dict
                )
                
                # Convert to Document objects
                for result in search_results:
                    doc = Document(
                        page_content=result["content"],
                        metadata=result["metadata"]
                    )
                    all_docs.append(doc)
            
            # Estimate total context size
            total_chars = sum(len(doc.page_content) for doc in all_docs)
            logger.info(f"Total document characters: {total_chars:,} (estimated tokens: {total_chars // CHARS_PER_TOKEN_ESTIMATE:,})")
            
            # If context is too large, implement intelligent sampling
            if total_chars > MAX_USABLE_CHARS:
                logger.warning(f"Context too large ({total_chars:,} chars). Implementing intelligent sampling...")
                all_docs = self._sample_documents_intelligently(
                    all_docs, docs_by_source, query, MAX_USABLE_CHARS, drug_names
                )
                new_total_chars = sum(len(doc.page_content) for doc in all_docs)
                logger.info(f"Reduced to {new_total_chars:,} chars after sampling")
            
            # Create the context from sampled documents
            context_parts = []
            current_drug = None
            
            # Organize by drug for better structure
            for doc in all_docs:
                source = doc.metadata.get("source", "Unknown")
                drug_name = source.split('_')[0].upper() if source != "Unknown" else "Unknown Drug"
                
                # Add drug header if switching to new drug
                if drug_name != current_drug:
                    if context_parts:  # Add separator between drugs
                        context_parts.append("\n---\n")
                    context_parts.append(f"\n## {drug_name} Information:\n")
                    current_drug = drug_name
                
                # Add content with character limit per chunk
                # Use original_content from metadata if available
                full_content = doc.metadata.get('original_content', doc.page_content)
                content = full_content[:5000]  # Limit individual chunks
                if len(content) < len(full_content):
                    content += "... [content truncated]"
                context_parts.append(content)
            
            context = "\n".join(context_parts)
            
            # Further truncate if still too long
            if len(context) > MAX_USABLE_CHARS:
                context = context[:MAX_USABLE_CHARS] + "\n\n[Additional content truncated due to length constraints]"
            
            # Build focused prompt
            system_prompt = self._build_multi_doc_prompt(query, drug_names, context, chat_history)
            
            # Use LLM with token awareness
            llm = get_llm()
            
            # Log token usage estimation
            prompt_chars = len(system_prompt)
            logger.info(f"Prompt size: {prompt_chars:,} chars (~{prompt_chars // CHARS_PER_TOKEN_ESTIMATE:,} tokens)")
            
            # Generate response with error handling
            try:
                response = llm.invoke(system_prompt)
                
                # Extract text from response
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
                
                logger.info(f"Generated response length: {len(response_text)} characters")
                return response_text
                
            except Exception as llm_error:
                if "token" in str(llm_error).lower() or "input" in str(llm_error).lower():
                    # Token limit still exceeded - use fallback approach
                    logger.error(f"Token limit exceeded even after sampling: {str(llm_error)}")
                    return self._generate_summary_response(query, drug_names, all_docs[:5])
                else:
                    raise llm_error
            
        except Exception as e:
            logger.error(f"Error in query_with_llm_multi_doc: {str(e)}")
            
            # Enhanced error handling with specific token limit message
            if "token" in str(e).lower() or "exceeds the maximum" in str(e).lower():
                return ("I encountered a technical limitation while processing multiple documents. "
                       "The combined information is too extensive for a single analysis. "
                       "Please try:\n\n"
                       "1. Asking about fewer drugs at once\n"
                       "2. Being more specific in your query\n"
                       "3. Focusing on particular aspects (e.g., just dosage or just side effects)\n\n"
                       "This will help me provide more detailed and accurate information.")
            elif "embedding" in str(e).lower() or "404" in str(e):
                return "I'm currently experiencing issues with the document search system. Please try again in a few moments."
            elif "api" in str(e).lower() or "key" in str(e).lower():
                return "I'm having trouble connecting to the AI service. Please try again later."
            else:
                return "I'm experiencing a technical issue with document processing. Please try again later."
    
    def _sample_documents_intelligently(
        self, 
        all_docs: List[Any], 
        docs_by_source: Dict[str, List[Any]],
        query: str,
        max_chars: int,
        drug_names: List[str]
    ) -> List[Any]:
        """Intelligently sample documents to fit within token limits while maintaining relevance."""
        try:
            # If docs_by_source is empty, work with all_docs directly
            if not docs_by_source:
                # Group docs by source
                docs_by_source = {}
                for doc in all_docs:
                    source = doc.metadata.get("source", "Unknown")
                    if source not in docs_by_source:
                        docs_by_source[source] = []
                    docs_by_source[source].append(doc)
            
            sampled_docs = []
            current_chars = 0
            
            # Calculate fair share of characters per drug
            num_sources = len(docs_by_source)
            if num_sources == 0:
                return all_docs[:5]  # Fallback to first 5 docs
            
            chars_per_source = max_chars // num_sources
            
            # Sample from each source
            for source, docs in docs_by_source.items():
                source_chars = 0
                for doc in docs:
                    doc_chars = len(doc.page_content)
                    if source_chars + doc_chars <= chars_per_source:
                        sampled_docs.append(doc)
                        source_chars += doc_chars
                        current_chars += doc_chars
                    else:
                        # Include partial document if it's the first from this source
                        if source_chars == 0:
                            # Truncate to fit
                            remaining_chars = chars_per_source - source_chars
                            truncated_content = doc.page_content[:remaining_chars]
                            doc.page_content = truncated_content + "\n... [truncated]"
                            sampled_docs.append(doc)
                            current_chars += len(truncated_content)
                        break
            
            logger.info(f"Sampled {len(sampled_docs)} documents from {num_sources} sources")
            return sampled_docs
            
        except Exception as e:
            logger.error(f"Error in document sampling: {str(e)}")
            # Fallback to simple truncation
            return all_docs[:10]
    
    def _build_multi_doc_prompt(
        self,
        query: str,
        drug_names: List[str],
        context: str,
        chat_history: Optional[List[Tuple[str, str]]]
    ) -> str:
        """Build an optimized prompt for multi-document queries."""
        # Base prompt
        prompt = f"""You are a pharmaceutical expert. Your task is to answer the user's query based ONLY on the provided context.

**CRITICAL INSTRUCTION: Do NOT repeat the user's query in your response. Begin your answer directly.**

CONTEXT:
{context}

INSTRUCTIONS:
1. **Answer this query**: "{query}"
2. Use ONLY the information from the CONTEXT provided above.
3. Do not use any external knowledge.
4. If the answer is not in the context, state that the information is not available in the provided documents.
5. Organize the information clearly, using tables for comparisons if appropriate.

RESPONSE:"""
        
        # Add chat history if available (limited to prevent token overflow)
        if chat_history and len(chat_history) > 0:
            # Only include last 2 exchanges to save tokens
            recent_history = chat_history[-2:] if len(chat_history) > 2 else chat_history
            history_text = "\n".join([f"User: {h}\nAssistant: {a[:200]}..." for h, a in recent_history])
            prompt = f"RECENT CONVERSATION:\n{history_text}\n\n{prompt}"
        
        return prompt
    
    def _generate_summary_response(
        self,
        query: str,
        drug_names: List[str],
        sample_docs: List[Any]
    ) -> str:
        """Generate a summary response when full context exceeds token limits."""
        try:
            logger.info("Generating summary response due to token limits")
            
            # Create a brief summary from sample documents
            summary_parts = [
                f"Due to the extensive nature of the information requested about {', '.join(drug_names)}, "
                f"I'll provide a focused summary addressing your query: '{query}'\n"
            ]
            
            # Group sample docs by drug
            docs_by_drug = {}
            for doc in sample_docs:
                source = doc.metadata.get("source", "Unknown")
                drug_name = source.split('_')[0].upper() if source != "Unknown" else "Unknown"
                if drug_name not in docs_by_drug:
                    docs_by_drug[drug_name] = []
                docs_by_drug[drug_name].append(doc)
            
            # Add brief info for each drug
            for drug_name, docs in docs_by_drug.items():
                summary_parts.append(f"\n**{drug_name}:**")
                # Use first doc's content (truncated) as summary
                if docs:
                    content_preview = docs[0].page_content[:500]
                    if len(docs[0].page_content) > 500:
                        content_preview += "..."
                    summary_parts.append(content_preview)
            
            summary_parts.append(
                "\n\n**Note:** This is a condensed summary. For more detailed information about "
                "specific aspects, please ask about individual drugs or narrow down your query."
            )
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating summary response: {str(e)}")
            return (
                "I apologize, but I'm unable to process this much information at once. "
                "Please try asking about individual drugs or specific aspects for better results."
            )

