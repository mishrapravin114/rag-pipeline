"""
ChromaDB Utility for FDA RAG Pipeline
Handles vector database operations including document storage and retrieval
"""
import os
# Disable ChromaDB telemetry before importing
os.environ['CHROMA_TELEMETRY_DISABLED'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_SERVER_TELEMETRY_ANONYMIZED_TELEMETRY'] = 'False'

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Tuple
import logging
import uuid
import asyncio
from datetime import datetime
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

logger = logging.getLogger(__name__)

class ChromaDBUtil:
    """Utility class for ChromaDB operations in FDA pipeline."""

    def __init__(self, host: str = "localhost", port: int = 8000, use_persistent_client: bool = True):
        """Initialize ChromaDB client."""
        try:
            if use_persistent_client:
                # Use persistent client (local file-based)
                import tempfile
                db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'chromadb')
                os.makedirs(db_path, exist_ok=True)
                
                # Configure settings with available options for better performance
                client_settings = Settings(
                    allow_reset=True, 
                    anonymized_telemetry=False,
                    # Memory settings for better performance
                    chroma_memory_limit_bytes=2 * 1024 * 1024 * 1024,  # 2GB memory limit
                    # Server thread pool for better concurrency
                    chroma_server_thread_pool_size=80,  # Increased from default 40
                )
                
                self.chroma_client = chromadb.PersistentClient(
                    path=db_path,
                    settings=client_settings
                )
                logger.info(f"ChromaDBUtil initialized with persistent client at: {db_path} (Enhanced performance settings)")
            else:
                # Use HTTP client (for Docker)
                http_settings = Settings(
                    allow_reset=True, 
                    anonymized_telemetry=False,
                    # Memory and performance settings
                    chroma_memory_limit_bytes=2 * 1024 * 1024 * 1024,  # 2GB memory limit
                    chroma_server_thread_pool_size=80,  # Increased from default 40
                )
                
                self.chroma_client = chromadb.HttpClient(
                    host=host, 
                    port=port, 
                    settings=http_settings
                )
                logger.info(f"ChromaDBUtil initialized with HTTP client at {host}:{port} (Enhanced performance settings)")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise

    @staticmethod
    def get_instance(host: str = "localhost", port: int = 8000, use_persistent_client: bool = True) -> "ChromaDBUtil":
        """Static method to return an instance of ChromaDBUtil."""
        return ChromaDBUtil(host=host, port=port, use_persistent_client=use_persistent_client)

    def sanitize_collection_name(self, collection_name: str) -> str:
        """Sanitize the collection name by replacing spaces and special characters."""
        import re
        # Replace spaces with underscores and remove special characters
        sanitized_name = re.sub(r'[^\w\-_]', '_', collection_name)
        # Ensure it starts with a letter or underscore
        if sanitized_name and not sanitized_name[0].isalpha() and sanitized_name[0] != '_':
            sanitized_name = f"_{sanitized_name}"
        # Only log if name was actually changed
        if sanitized_name != collection_name:
            logger.debug(f"Sanitized collection name: {collection_name} -> {sanitized_name}")
        return sanitized_name

    def get_or_create_collection(self, collection_name: str, embedding_function=None):
        """Get or create a collection with the sanitized name and robust error handling."""
        try:
            sanitized_collection_name = self.sanitize_collection_name(collection_name)
            
            # Import Gemini embedding function
            embedding_function = None
            try:
                from utils.llm_util import get_embeddings_function
                embedding_function = get_embeddings_function()
                # Log only once per session, not every time
                if not hasattr(self, '_logged_embedding_type'):
                    logger.info("Using Gemini embedding function for collections")
                    self._logged_embedding_type = True
            except Exception as embed_error:
                logger.error(f"Failed to get embedding function: {str(embed_error)}")
                logger.warning("Falling back to ChromaDB default embeddings")
            
            # Create collection with embedding function and optimized HNSW parameters
            collection = self.chroma_client.get_or_create_collection(
                name=sanitized_collection_name,
                embedding_function=embedding_function,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:ef_construction": 400,  # Increased from default 200 for better build quality
                    "hnsw:M": 48,  # Increased from default 16 for more connections
                    "hnsw:search_ef": 200,  # Increased for better search quality
                    "hnsw:num_threads": 4  # Use multiple threads for operations
                }
            )
            # Debug level for routine operations
            logger.debug(f"Collection retrieved/created: {sanitized_collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Error creating or retrieving collection '{collection_name}': {str(e)}")
            # Try without custom embedding function as fallback
            try:
                logger.warning("Attempting collection creation with default embedding")
                sanitized_collection_name = self.sanitize_collection_name(collection_name)
                collection = self.chroma_client.get_or_create_collection(
                    name=sanitized_collection_name
                )
                logger.info(f"Collection created with default embedding: {sanitized_collection_name}")
                return collection
            except Exception as fallback_error:
                logger.error(f"Fallback collection creation also failed: {str(fallback_error)}")
                return None

    def _chunk_large_document(self, document: Dict[str, Any], max_chunk_size: int = 15000) -> List[Dict[str, Any]]:
        """
        Chunk a large document into smaller pieces to handle payload size limits.
        
        Args:
            document: Document dictionary with 'page_content' and 'metadata'
            max_chunk_size: Maximum size for each chunk in characters
            
        Returns:
            List of chunked document dictionaries
        """
        content = document["page_content"]
        metadata = document["metadata"].copy()
        
        if len(content) <= max_chunk_size:
            return [document]
        
        chunks = []
        start = 0
        chunk_index = 1
        
        while start < len(content):
            end = start + max_chunk_size
            
            # Try to break at word boundaries
            if end < len(content):
                # Look for the last space within the chunk
                last_space = content.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_content = content[start:end].strip()
            
            # Skip empty chunks or chunks that are too small
            if not chunk_content or len(chunk_content) < 10:
                start = end + 1
                continue
            
            # Update metadata for this chunk
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_part"] = chunk_index
            chunk_metadata["total_chunks"] = None  # Will be updated after all chunks are created
            chunk_metadata["original_size"] = len(content)
            
            chunks.append({
                "page_content": chunk_content,
                "metadata": chunk_metadata
            })
            
            start = end + 1  # Move past the space to avoid duplicate content
            chunk_index += 1
        
        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = total_chunks
        
        logger.info(f"Chunked document of {len(content)} chars into {total_chunks} chunks")
        return chunks

    def document_exists(self, file_name: str, collection_name: str) -> bool:
        """Check if documents from a file already exist in the collection."""
        try:
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return False

            # Query for documents with this file name
            results = collection.get(
                where={"source": file_name},
                limit=1,
                include=["metadatas"]
            )

            exists = len(results['metadatas']) > 0
            logger.info(f"Document exists: {exists} for file: {file_name}")
            return exists
        except Exception as e:
            logger.error(f"Error checking if document exists: {str(e)}")
            return False

    def add_documents(
        self, 
        documents: List[Dict[str, Any]], 
        collection_name: str = "fda_documents",
        use_chromadb_batching: bool = True
    ) -> Dict[str, Any]:
        """
        Add FDA documents to ChromaDB collection using official ChromaDB batching utilities.
        
        Args:
            documents: List of document dictionaries with 'page_content' and 'metadata'
            collection_name: Name of the collection
            use_chromadb_batching: Whether to use ChromaDB's official batch utilities (default: True)
            
        Returns:
            Dictionary with status and details
        """
        try:
            logger.info(f"Adding {len(documents)} documents to collection: {collection_name} using ChromaDB batching")

            # Get or create the collection
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return {"status": "failure", "error": "Could not create collection"}

            # Extract file name from first document's metadata
            if documents and documents[0].get("metadata", {}).get("source"):
                file_name = documents[0]["metadata"]["source"]
                
                # Check if documents from this file already exist
                if self.document_exists(file_name, collection_name):
                    logger.warning(f"Documents from {file_name} already exist. Deleting old documents.")
                    # Delete existing documents from this file
                    collection.delete(where={"source": file_name})
                    logger.info(f"Deleted existing documents from file: {file_name}")

            # Prepare data for ChromaDB batching
            texts = []
            metadatas = []
            ids = []
            
            for doc in documents:
                # Generate unique ID
                doc_id = str(uuid.uuid4())
                
                # Clean metadata - ChromaDB only accepts str, int, float, bool
                clean_metadata = {}
                for key, value in doc["metadata"].items():
                    if isinstance(value, (str, int, float, bool)):
                        clean_metadata[key] = value
                    elif isinstance(value, list):
                        # Convert list to comma-separated string
                        clean_metadata[key] = ", ".join(str(v) for v in value)
                    elif value is None:
                        clean_metadata[key] = ""
                    else:
                        # Convert other types to string
                        clean_metadata[key] = str(value)
                
                # Extract content and metadata
                texts.append(doc["page_content"])
                metadatas.append(clean_metadata)
                ids.append(doc_id)

            if use_chromadb_batching:
                # Use ChromaDB's official batching utilities
                try:
                    from chromadb.utils.batch_utils import create_batches
                    
                    logger.info(f"Using ChromaDB official batching for {len(documents)} documents")
                    
                    # Get max_batch_size if available
                    try:
                        max_batch_size = getattr(self.chroma_client, 'max_batch_size', 'Unknown')
                        logger.info(f"ChromaDB max_batch_size: {max_batch_size}")
                    except AttributeError:
                        logger.info("ChromaDB max_batch_size: Not available in this version")
                    
                    # Create batches using ChromaDB's official utility
                    batches = create_batches(
                        api=self.chroma_client,
                        ids=ids,
                        documents=texts,
                        metadatas=metadatas
                    )
                    
                    total_added = 0
                    failed_batches = 0
                    
                    # Process each batch
                    for batch_idx, batch in enumerate(batches):
                        batch_ids, batch_embeddings, batch_metadatas, batch_documents = batch
                        batch_size = len(batch_ids)
                        
                        logger.info(f"Processing ChromaDB batch {batch_idx + 1}/{len(batches)} ({batch_size} documents)")
                        
                        try:
                            collection.add(
                                ids=batch_ids,
                                documents=batch_documents,
                                metadatas=batch_metadatas,
                                embeddings=batch_embeddings
                            )
                            total_added += batch_size
                            logger.info(f"# Batch {batch_idx + 1} added successfully ({batch_size} documents)")
                            
                        except Exception as batch_error:
                            initial_failed_batches = failed_batches + 1
                            logger.error(f"# Batch {batch_idx + 1} failed: {str(batch_error)}")
                            
                            # Fallback: try to add documents individually for this batch
                            logger.info(f"Retrying batch {batch_idx + 1} with individual documents...")
                            batch_recovered_docs = 0
                            
                            for i in range(batch_size):
                                try:
                                    collection.add(
                                        ids=[batch_ids[i]],
                                        documents=[batch_documents[i]],
                                        metadatas=[batch_metadatas[i]],
                                        embeddings=[batch_embeddings[i]] if batch_embeddings else None
                                    )
                                    total_added += 1
                                    batch_recovered_docs += 1
                                except Exception as single_error:
                                    logger.error(f"Failed to add individual document {i}: {str(single_error)}")
                                    
                                    # If individual document is too large, try chunking
                                    if "payload size exceeds" in str(single_error).lower():
                                        logger.info(f"Document {i} too large, trying content chunking...")
                                        try:
                                            # Create a document dict for chunking
                                            large_doc = {
                                                "page_content": batch_documents[i],
                                                "metadata": batch_metadatas[i]
                                            }
                                            
                                            # Chunk the large document
                                            chunked_docs = self._chunk_large_document(large_doc, max_chunk_size=10000)
                                            
                                            # Add each chunk individually
                                            chunks_added = 0
                                            for chunk_idx, chunk_doc in enumerate(chunked_docs):
                                                try:
                                                    chunk_id = f"{batch_ids[i]}_chunk_{chunk_idx + 1}"
                                                    collection.add(
                                                        ids=[chunk_id],
                                                        documents=[chunk_doc["page_content"]],
                                                        metadatas=[chunk_doc["metadata"]],
                                                        embeddings=None  # Let ChromaDB generate embeddings for chunks
                                                    )
                                                    total_added += 1
                                                    chunks_added += 1
                                                except Exception as chunk_error:
                                                    logger.error(f"Failed to add chunk {chunk_idx + 1}: {str(chunk_error)}")
                                            
                                            if chunks_added > 0:
                                                batch_recovered_docs += 1  # Count as recovered if any chunks were added
                                            
                                            logger.info(f"Successfully chunked document {i} into {len(chunked_docs)} parts ({chunks_added} added)")
                                            
                                        except Exception as chunking_error:
                                            logger.error(f"Failed to chunk document {i}: {str(chunking_error)}")
                            
                            # If we recovered all documents in the batch, don't count it as failed
                            if batch_recovered_docs == batch_size:
                                logger.info(f"# Batch {batch_idx + 1} fully recovered through individual/chunked additions")
                                # Don't increment failed_batches since we recovered everything
                            else:
                                failed_batches = initial_failed_batches
                                logger.warning(f"## Batch {batch_idx + 1} partially recovered: {batch_recovered_docs}/{batch_size} documents")
                    
                except ImportError:
                    logger.warning("ChromaDB batch_utils not available, falling back to manual batching")
                    use_chromadb_batching = False
                    
            if not use_chromadb_batching:
                # Fallback to direct addition without ChromaDB batching
                logger.info("Adding documents directly to collection")
                try:
                    collection.add(
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_added = len(documents)
                    failed_batches = 0
                    logger.info(f"# Successfully added all {total_added} documents directly")
                    
                except Exception as direct_error:
                    logger.error(f"# Direct addition failed: {str(direct_error)}")
                    
                    # If direct addition fails due to payload size, try individual documents with chunking
                    if "payload size exceeds" in str(direct_error).lower():
                        logger.info("Direct addition failed due to payload size, trying individual documents with chunking...")
                        total_added = 0
                        failed_batches = 0
                        
                        for i, (doc_id, doc_text, doc_metadata) in enumerate(zip(ids, texts, metadatas)):
                            try:
                                collection.add(
                                    ids=[doc_id],
                                    documents=[doc_text],
                                    metadatas=[doc_metadata]
                                )
                                total_added += 1
                            except Exception as individual_error:
                                if "payload size exceeds" in str(individual_error).lower():
                                    logger.info(f"Document {i} too large, chunking...")
                                    try:
                                        # Create document for chunking
                                        large_doc = {
                                            "page_content": doc_text,
                                            "metadata": doc_metadata
                                        }
                                        
                                        # Chunk the document
                                        chunked_docs = self._chunk_large_document(large_doc, max_chunk_size=10000)
                                        
                                        # Add each chunk
                                        for chunk_idx, chunk_doc in enumerate(chunked_docs):
                                            try:
                                                chunk_id = f"{doc_id}_chunk_{chunk_idx + 1}"
                                                collection.add(
                                                    ids=[chunk_id],
                                                    documents=[chunk_doc["page_content"]],
                                                    metadatas=[chunk_doc["metadata"]]
                                                )
                                                total_added += 1
                                            except Exception as chunk_error:
                                                logger.error(f"Failed to add chunk {chunk_idx + 1}: {str(chunk_error)}")
                                        
                                        logger.info(f"Chunked document {i} into {len(chunked_docs)} parts")
                                        
                                    except Exception as chunking_error:
                                        logger.error(f"Failed to chunk document {i}: {str(chunking_error)}")
                                        failed_batches += 1
                                else:
                                    logger.error(f"Failed to add document {i}: {str(individual_error)}")
                                    failed_batches += 1
                    else:
                        total_added = 0
                        failed_batches = 1
            
            # Determine overall status
            if total_added >= len(documents):  # >= because chunking can create more documents than original
                status = "success"
                if total_added > len(documents):
                    message = f"Successfully added all content as {total_added} documents (some large documents were chunked)"
                else:
                    message = f"Successfully added all {total_added} documents"
            elif total_added > 0:
                status = "partial_success"
                if failed_batches > 0:
                    message = f"Added {total_added} documents from {len(documents)} originals ({failed_batches} batches had unrecoverable failures)"
                else:
                    message = f"Added {total_added} documents from {len(documents)} originals (all content successfully processed)"
            else:
                status = "failure"
                message = f"Failed to add any documents ({failed_batches} batches failed)"
            
            logger.info(f"# Final result: {message}")
            return {
                "status": status,
                "documents_added": total_added,
                "total_documents": len(documents),
                "failed_batches": failed_batches,
                "collection": collection_name,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error adding documents to ChromaDB: {str(e)}")
            return {"status": "failure", "error": str(e)}

    def search_documents(
        self, 
        query: str, 
        collection_name: str = "fda_documents", 
        n_results: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents in the collection.
        
        Args:
            query: Search query
            collection_name: Name of the collection
            n_results: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of relevant documents with metadata
        """
        try:
            logger.info(f"Searching in collection: {collection_name} for query: {query}")
            
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return []

            # Perform search
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_dict,
                include=["metadatas", "documents", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results.get('documents') is not None and len(results.get('documents', [])) > 0 and results['documents'][0] is not None:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results.get('metadatas') is not None else {},
                        'distance': results['distances'][0][i] if results.get('distances') is not None else None
                    })
            
            logger.info(f"Found {len(formatted_results)} documents")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
    
    def grade_documents(
        self, 
        search_results: List[Dict[str, Any]], 
        query: str,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Grade documents based on relevance to the query.
        
        Args:
            search_results: List of search results from search_documents
            query: Original search query
            metadata_filter: Optional metadata filters applied
            
        Returns:
            Dictionary with file paths, weights, and comments
        """
        try:
            from utils.llm_util import get_llm_grading
            from utils.models import GradeDocuments
            
            logger.info(f"Grading {len(search_results)} documents for relevance")
            
            # Remove duplicates
            unique_docs = []
            unique_metadatas = []
            seen_content = set()
            
            for result in search_results:
                doc_str = str(result['content'])
                if doc_str not in seen_content:
                    seen_content.add(doc_str)
                    unique_docs.append(result['content'])
                    unique_metadatas.append(result['metadata'])
            
            logger.info(f"Unique documents to grade: {len(unique_docs)}")
            
            # Initialize grader
            grader = get_llm_grading().with_structured_output(GradeDocuments)
            grader_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a grader assessing the relevance of FDA document content to a user question.
                If the document contains keyword(s) or semantic meaning related to the question, grade it as relevant.
                Give a binary score 'yes' or 'no' to indicate whether the document is relevant to the question.
                Along with binary score, provide comments that explain how it's relevant."""),
                ("human", "Retrieved document: \n\n {document} \n\n User question: {prompt}"),
            ])
            grader_chain = grader_prompt | grader
            
            # Grade documents
            relevant_file_weights = {}
            total_file_chunks = {}  # Track total chunks per file
            file_comments = {}
            
            logger.info(f"=== GRADING {len(unique_docs)} DOCUMENTS ===")
            logger.info(f"Query: '{query}'")
            
            for i, (doc, meta) in enumerate(zip(unique_docs, unique_metadatas)):
                # Create document context including metadata
                doc_context = f"Content: {doc}\n\nMetadata: {meta}"
                
                logger.info(f"Grading document {i + 1}/{len(unique_docs)}: {meta.get('source', 'Unknown')}")
                logger.info(f"  Chunk index: {meta.get('chunk_index', 'N/A')}")
                logger.info(f"  Content preview: {doc[:150]}...")
                
                try:
                    grade = grader_chain.invoke({
                        'document': doc_context,
                        'prompt': query
                    })
                    
                    logger.info(f"  Grade result: {grade.binary_score}")
                    logger.info(f"  Comments: {grade.comments}")
                    
                    file_name = meta.get('source', 'Unknown')
                    
                    # Track total chunks per file
                    if file_name in total_file_chunks:
                        total_file_chunks[file_name] += 1
                    else:
                        total_file_chunks[file_name] = 1
                    
                    if grade.binary_score == 'yes':
                        if file_name in relevant_file_weights:
                            relevant_file_weights[file_name] += 1
                        else:
                            relevant_file_weights[file_name] = 1
                        
                        # Store the best comment for each file
                        if file_name not in file_comments or len(grade.comments or '') > len(file_comments.get(file_name, '')):
                            file_comments[file_name] = grade.comments
                            logger.info(f"  Updated comment for {file_name}")
                except Exception as e:
                    logger.error(f"  Error grading document: {str(e)}")
            
            if not relevant_file_weights:
                logger.info("No relevant files found after grading.")
                return {'file_paths': [], 'weights': [], 'comments': []}
            
            # Log detailed grading summary for debugging
            logger.info("# GRADING SUMMARY:")
            total_chunks_processed = len(search_results) if search_results else 0
            logger.info(f"   Total chunks processed: {total_chunks_processed}")
            logger.info(f"   Files with 'yes' grades: {len(relevant_file_weights)}")
            
            for file_name, weight in relevant_file_weights.items():
                total_chunks = total_file_chunks.get(file_name, 1)
                relevance_percentage = (weight / total_chunks) * 100
                logger.info(f"   # {file_name}: {weight}/{total_chunks} chunks relevant ({relevance_percentage:.1f}%)")
                
                # WARNING: Files with low relevance percentage
                if relevance_percentage < 50:
                    logger.warning(f"   ##  {file_name} has low chunk relevance ({relevance_percentage:.1f}%) - may be false positive")
            
            logger.info(f"Final file weight mapping: {relevant_file_weights}")
            
            # Sort by weight
            sorted_files = sorted(relevant_file_weights.items(), key=lambda x: x[1], reverse=True)
            file_paths = [f[0] for f in sorted_files]
            weights = [f[1] for f in sorted_files]
            comments = [file_comments.get(f, '') for f in file_paths]
            
            return {
                'file_paths': file_paths,
                'weights': weights,
                'comments': comments
            }
            
        except Exception as e:
            logger.error(f"Error grading documents: {str(e)}")
            return {'file_paths': [], 'weights': [], 'comments': []}

    def query_with_llm(
        self,
        query: str,
        collection_name: str = "fda_documents",
        n_results: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Tuple[str, str]]] = None
    ) -> str:
        """
        Query documents and generate response using LLM.
        
        Args:
            query: User query
            collection_name: Name of the collection
            n_results: Number of documents to retrieve
            filter_dict: Optional metadata filters
            chat_history: Optional chat history
            
        Returns:
            LLM generated response
        """
        try:
            from utils.llm_util import get_llm, get_embeddings_model
            
            logger.info(f"Querying with LLM in collection: {collection_name}")
            
            # Create Langchain Chroma vector store
            vector_store = Chroma(
                client=self.chroma_client,
                collection_name=self.sanitize_collection_name(collection_name),
                embedding_function=get_embeddings_model()
            )
            
            # Create retriever with filters
            search_kwargs = {"k": n_results}
            if filter_dict:
                search_kwargs["filter"] = filter_dict
                logger.info(f"filter_dict: {filter_dict}")
                
                
            retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
            
            # Create history-aware retriever if chat history exists
            if chat_history:
                contextualize_q_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Given a chat history and the latest user question "
                               "which might reference context in the chat history, "
                               "formulate a standalone question which can be understood "
                               "without the chat history."),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ])
                
                llm = get_llm()
                history_aware_retriever = create_history_aware_retriever(
                    llm, retriever, contextualize_q_prompt
                )
            else:
                history_aware_retriever = retriever
            
            # Create QA chain
            messages = [
                ("system", """You are a pharmaceutical expert providing answers about FDA-approved drugs based STRICTLY on the provided context.

CRITICAL RULES:
1. You MUST ONLY use information explicitly stated in the provided context below
2. DO NOT use any external knowledge or information not present in the context
3. If the answer is not in the context, say "The information about [specific topic] is not available in the provided documents"
4. NEVER make up or hallucinate information about drugs not mentioned in the context
5. ONLY mention drugs that appear in the context documents

# Conversational Context Handling
- Pay attention to previous messages in the conversation for context
- Reference earlier topics naturally when relevant (e.g., "As we discussed earlier about...", "Building on your previous question...")
- Maintain conversation continuity and remember what the user has asked about
- If the user asks follow-up questions, assume they relate to previous topics unless explicitly stated otherwise
- Use pronouns and references appropriately (e.g., "this drug", "that side effect" when referring to previously mentioned items)

When multiple drug documents are provided, you MUST:
1. Analyze and include information from ALL documents in the context
2. Clearly identify which drug each piece of information relates to
3. Compare and contrast information across all drugs when relevant
4. Use drug names as section headers when organizing your response
5. ONLY discuss drugs that are explicitly mentioned in the context

Format clearly and professionally with bold headings, line breaks, bullet points, tables (where needed), no repetition, and comprehensive coverage of all drugs mentioned.

Remember: Base your response ONLY on the information provided in the context below.

CONTEXT:
{context}"""),
            ]
            
            if chat_history:
                messages.append(MessagesPlaceholder("chat_history"))
                
            messages.append(("human", "{input}"))
            
            qa_prompt = ChatPromptTemplate.from_messages(messages)
            
            llm = get_llm()
            question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
            rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
            
            # Execute chain
            # Format chat history for LangChain
            formatted_history = []
            if chat_history:
                for human_msg, ai_msg in chat_history:
                    formatted_history.extend([
                        ("human", human_msg),
                        ("assistant", ai_msg)
                    ])
            
            result = rag_chain.invoke({
                "input": query,
                "chat_history": formatted_history
            })
            
            response = result.get("answer", "No response generated.")
            
            # Clean response to remove unwanted prefixes
            cleaned_response = self._clean_response(response)
            logger.info(f"Generated response: {cleaned_response[:100]}...")
            
            return cleaned_response
            
        except Exception as e:
            logger.error(f"Error in query_with_llm: {str(e)}")
            
            # Provide user-friendly error messages based on error type
            if "embedding" in str(e).lower() or "404" in str(e):
                return "I'm currently experiencing issues with the search system. Please try again in a few moments, or contact support if the problem persists."
            elif "api" in str(e).lower() or "key" in str(e).lower():
                return "I'm having trouble connecting to the AI service. Please try again later or contact support if this continues."
            elif "timeout" in str(e).lower():
                return "The request took too long to process. Please try with a shorter query or try again later."
            else:
                return "I'm experiencing a technical issue and cannot process your request right now. Please try again later or contact support."

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
        """
        try:
            from utils.llm_util import get_llm, get_embeddings_model
            
            logger.info(f"Multi-doc query: {query}")
            logger.info(f"Expected sources: {expected_sources}")
            
            # Token limits for Gemini models
            GEMINI_MAX_TOKENS = 1_000_000  # Conservative limit (actual is 1,048,575)
            CHARS_PER_TOKEN_ESTIMATE = 4  # Rough estimate: 1 token # 4 characters
            MAX_CONTEXT_CHARS = GEMINI_MAX_TOKENS * CHARS_PER_TOKEN_ESTIMATE  # ~4M chars
            RESERVE_TOKENS = 50_000  # Reserve for prompt and response
            MAX_USABLE_CHARS = (GEMINI_MAX_TOKENS - RESERVE_TOKENS) * CHARS_PER_TOKEN_ESTIMATE
            
            # Create Langchain Chroma vector store
            vector_store = Chroma(
                client=self.chroma_client,
                collection_name=self.sanitize_collection_name(collection_name),
                embedding_function=get_embeddings_model()
            )
            
            # Simplified retrieval - get documents from each source
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
                    source_filter = {"source": source_file}
                    search_kwargs = {"k": adjusted_chunks_per_doc, "filter": source_filter}
                    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
                    docs = retriever.get_relevant_documents(query)
                    docs_by_source[source_file] = docs
                    all_docs.extend(docs)
                    logger.info(f"Retrieved {len(docs)} chunks from {source_file}")
            
            # If no documents retrieved, fall back to general search
            if not all_docs:
                search_kwargs = {"k": min(n_results_per_doc * 2, 10)}
                if filter_dict:
                    search_kwargs["filter"] = filter_dict
                retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
                all_docs = retriever.get_relevant_documents(query)
            
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
                # Use original_content from metadata instead of page_content
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
            
            # First pass: get most relevant chunks from each source
            for source, docs in docs_by_source.items():
                source_chars = 0
                source_docs = []
                
                # Sort docs by relevance (assuming they're already sorted by retriever)
                for doc in docs:
                    doc_chars = len(doc.page_content)
                    if source_chars + doc_chars <= chars_per_source:
                        source_docs.append(doc)
                        source_chars += doc_chars
                    else:
                        # Add truncated version of this doc if there's room
                        remaining_chars = chars_per_source - source_chars
                        if remaining_chars > 1000:  # Only add if meaningful content remains
                            truncated_doc = type(doc)(
                                page_content=doc.page_content[:remaining_chars] + "... [truncated]",
                                metadata=doc.metadata
                            )
                            source_docs.append(truncated_doc)
                        break
                
                sampled_docs.extend(source_docs)
                current_chars += source_chars
            
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
                "Please try asking about fewer drugs or more specific aspects of the drugs you're interested in."
            )
    
    def _clean_response(self, response: str) -> str:
        """Clean LLM response to remove unwanted prefixes and references."""
        if not response:
            return ""
        
        cleaned_response = response.strip()
        
        # Remove common prefixes that reference documents explicitly
        prefixes_to_remove = [
            "According to the FDA document,",
            "According to the FDA documents,",
            "Based on the FDA document,", 
            "Based on the FDA documents,",
            "Based on the provided FDA documents,",
            "The FDA document states that",
            "The FDA documents state that",
            "From the FDA document:",
            "From the FDA documents:",
            "The FDA document indicates",
            "The FDA documents indicate",
            "According to FDA documentation,",
            "From FDA documentation,",
            "According to the document,",
            "According to the documents,",
            "Based on the document,",
            "Based on the documents,",
            "Based on the provided documents,",
            "The document states that",
            "The documents state that",
            "From the document:",
            "From the documents:",
            "The document indicates",
            "The documents indicate",
            "According to documentation,",
            "Based on the provided information,",
            "From the provided context,",
            "Based on the information provided,",
            "According to the information provided,",
            "The provided documents show that",
            "The provided information indicates",
            "Based on these documents,",
            "According to these documents,"
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned_response.startswith(prefix):
                cleaned_response = cleaned_response[len(prefix):].strip()
                # Capitalize the first letter after removing prefix
                if cleaned_response:
                    cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
        
        # Remove redundant references throughout the text
        phrases_to_remove = [
            " according to the FDA document",
            " according to the FDA documents",
            " based on the FDA document", 
            " based on the FDA documents",
            " from the FDA document",
            " from the FDA documents",
            " as stated in the FDA document",
            " as stated in the FDA documents",
            " according to FDA documents",
            " based on FDA documents",
            " from FDA documents",
            " as stated in FDA documents",
            " according to the document",
            " according to the documents",
            " based on the document",
            " based on the documents",
            " from the document",
            " from the documents",
            " as stated in the document",
            " as stated in the documents",
            " according to documentation",
            " based on documentation",
            " from documentation",
            " as per the document",
            " as per the documents",
            " as mentioned in the document",
            " as mentioned in the documents"
        ]
        
        for phrase in phrases_to_remove:
            cleaned_response = cleaned_response.replace(phrase, "")
        
        # Clean up any double spaces and normalize whitespace
        import re
        cleaned_response = re.sub(r'\s+', ' ', cleaned_response).strip()
        
        return cleaned_response

    def get_collection_stats(self, collection_name: str = "fda_documents") -> Dict[str, Any]:
        """Get statistics about a collection."""
        try:
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return {"error": "Collection not found"}
            
            count = collection.count()
            
            # Get sample of unique sources
            sample_results = collection.get(limit=100, include=["metadatas"])
            unique_sources = set()
            unique_drugs = set()
            
            for metadata in sample_results.get("metadatas", []):
                if metadata.get("source"):
                    unique_sources.add(metadata["source"])
                if metadata.get("drug_name"):
                    unique_drugs.add(metadata["drug_name"])
            
            return {
                "collection_name": collection_name,
                "total_documents": count,
                "unique_sources": len(unique_sources),
                "unique_drugs": len(unique_drugs),
                "sample_sources": list(unique_sources)[:5],
                "sample_drugs": list(unique_drugs)[:5]
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        try:
            sanitized_name = self.sanitize_collection_name(collection_name)
            # Try to get the collection, if it exists it will return successfully
            self.chroma_client.get_collection(sanitized_name)
            return True
        except Exception as e:
            # Collection doesn't exist
            return False
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            sanitized_name = self.sanitize_collection_name(collection_name)
            self.chroma_client.delete_collection(sanitized_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {str(e)}")
            return False

    def delete_documents_by_metadata(
        self, 
        metadata_filter: Dict[str, Any], 
        collection_name: str = "fda_documents"
    ) -> Dict[str, Any]:
        """
        Delete documents from ChromaDB collection based on metadata filter.
        
        Args:
            metadata_filter: Dictionary of metadata filters (e.g., {"source": "filename.pdf"})
            collection_name: Name of the collection
            
        Returns:
            Dictionary with status, deleted count, and details
        """
        try:
            logger.info(f"Deleting documents from collection: {collection_name} with filter: {metadata_filter}")
            
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return {"status": "failure", "error": "Collection not found", "deleted_count": 0}
            
            # First, get the count of documents that match the filter
            existing_docs = collection.get(
                where=metadata_filter,
                include=["metadatas"]
            )
            
            documents_to_delete = len(existing_docs.get("metadatas", []))
            
            if documents_to_delete == 0:
                logger.info(f"No documents found matching filter: {metadata_filter}")
                return {
                    "status": "success",
                    "message": "No documents found matching the specified criteria",
                    "deleted_count": 0,
                    "filter_used": metadata_filter
                }
            
            # Delete the documents
            collection.delete(where=metadata_filter)
            
            logger.info(f"Successfully deleted {documents_to_delete} documents from collection: {collection_name}")
            
            return {
                "status": "success",
                "message": f"Successfully deleted {documents_to_delete} documents",
                "deleted_count": documents_to_delete,
                "filter_used": metadata_filter,
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(f"Error deleting documents by metadata: {str(e)}")
            return {
                "status": "failure", 
                "error": str(e),
                "deleted_count": 0
            }

    def delete_documents_by_source_file(
        self, 
        source_file_name: str, 
        collection_name: str = "fda_documents"
    ) -> Dict[str, Any]:
        """
        Delete all documents from a specific source file.
        
        Args:
            source_file_name: Name of the source file
            collection_name: Name of the collection
            
        Returns:
            Dictionary with status, deleted count, and details
        """
        return self.delete_documents_by_metadata(
            metadata_filter={"source": source_file_name},
            collection_name=collection_name
        )

    def get_document_count_by_source_file(
        self, 
        source_file_name: str, 
        collection_name: str = "fda_documents"
    ) -> int:
        """
        Get the count of documents for a specific source file.
        
        Args:
            source_file_name: Name of the source file
            collection_name: Name of the collection
            
        Returns:
            Number of documents for the source file
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return 0
            
            # Get documents with the specified source
            results = collection.get(
                where={"source": source_file_name},
                include=["metadatas"]
            )
            
            count = len(results.get("metadatas", []))
            logger.info(f"Found {count} documents for source file: {source_file_name}")
            return count
            
        except Exception as e:
            logger.error(f"Error getting document count for source file: {str(e)}")
            return 0

    def query_with_llm_enhanced_metadata(
        self,
        query: str,
        collection_name: str = "fda_documents",
        n_results: int = 15,
        filter_dict: Optional[Dict[str, Any]] = None,
        metadata_name: str = "",
        enable_document_grading: bool = True
    ) -> Dict[str, Any]:
        """
        Enhanced query for metadata extraction with Gemini 2.0 Flash optimization.
        
        Args:
            query: User query for metadata extraction
            collection_name: Name of the collection
            n_results: Number of documents to retrieve (default 15, increased from 5)
            filter_dict: Optional metadata filters
            metadata_name: Name of metadata being extracted for logging
            enable_document_grading: Whether to grade and filter documents for relevance
            
        Returns:
            Dict with response, confidence score, and supporting evidence
        """
        try:
            from utils.llm_util import get_llm, get_embeddings_model
            
            logger.info(f"Enhanced metadata extraction for: {metadata_name} using {n_results} documents")
            
            # Create Langchain Chroma vector store
            vector_store = Chroma(
                client=self.chroma_client,
                collection_name=self.sanitize_collection_name(collection_name),
                embedding_function=get_embeddings_model()
            )
            
            # Create retriever with enhanced search parameters
            search_kwargs = {"k": n_results}
            if filter_dict:
                search_kwargs["filter"] = filter_dict
                logger.info(f"Enhanced filter_dict: {filter_dict}")
                
            retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
            
            # Get documents first for potential grading
            docs = retriever.get_relevant_documents(query)
            logger.info(f"Retrieved {len(docs)} documents for metadata extraction")
            
            # Optional document grading for relevance (helps improve confidence)
            if enable_document_grading and len(docs) > 5:
                graded_docs = self._grade_documents_for_metadata(docs, query, metadata_name)
                if graded_docs["relevant_count"] > 0:
                    # Use only relevant documents for better accuracy
                    relevant_docs = graded_docs["relevant_documents"][:min(n_results, 15)]
                    logger.info(f"Using {len(relevant_docs)} relevant documents after grading")
                else:
                    relevant_docs = docs[:min(n_results, 10)]  # Fallback to fewer docs
                    logger.info("No relevant documents found by grading, using top 10 documents")
            else:
                relevant_docs = docs
            
            # Enhanced QA chain optimized for advanced language models
            enhanced_qa_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert pharmaceutical document analyst with advanced reasoning capabilities. "
                          "Your task is to extract specific metadata with maximum accuracy and confidence.\n\n"
                          "ANALYSIS INSTRUCTIONS:\n"
                          "1. Carefully examine ALL provided document chunks\n"
                          "2. Look for explicit statements, implied information, and contextual evidence\n"
                          "3. Cross-reference information across multiple document sections\n"
                          "4. Consider medical terminology, abbreviations, and alternative phrasings\n"
                          "5. Validate findings against pharmaceutical standards and medical terminology\n"
                          "6. Provide high confidence scores (80-100%) when evidence is clear\n"
                          "7. Use medium confidence (60-79%) for implied or contextual evidence\n"
                          "8. Use low confidence (<60%) only when evidence is weak or ambiguous\n\n"
                          "CONTEXT:\n{context}"),
                ("human", "{input}")
            ])
            
            llm = get_llm()
            
            # Create enhanced document chain with relevant documents
            from langchain.chains.combine_documents import create_stuff_documents_chain
            question_answer_chain = create_stuff_documents_chain(llm, enhanced_qa_prompt)
            
            # Create custom retrieval chain with pre-filtered documents
            class EnhancedRetrievalChain:
                def __init__(self, qa_chain, documents):
                    self.qa_chain = qa_chain
                    self.documents = documents
                
                def invoke(self, inputs):
                    # Use pre-retrieved relevant documents
                    result = self.qa_chain.invoke({
                        "context": self.documents,
                        "input": inputs["input"]
                    })
                    return {"answer": result, "context": self.documents}
            
            enhanced_chain = EnhancedRetrievalChain(question_answer_chain, relevant_docs)
            
            # Execute enhanced chain
            result = enhanced_chain.invoke({"input": query})
            response = result.get("answer", "No response generated.")
            
            # Clean response to remove unwanted prefixes
            cleaned_response = self._clean_response(response)
            
            # Calculate confidence based on document relevance and response quality
            confidence_score = self._calculate_metadata_confidence(
                cleaned_response, relevant_docs, query, metadata_name
            )
            
            logger.info(f"Enhanced metadata extraction completed with confidence: {confidence_score}")

            # Collect metadata details for each relevant doc
            # Maintain the same structure as stored in DocumentData
            metadata_details = []
            for doc in relevant_docs:
                # Get the complete metadata as stored in DocumentData
                if hasattr(doc, 'metadata') and doc.metadata:
                    # Create a copy of the metadata to preserve the original structure
                    doc_metadata = {
                        'file_name': doc.metadata.get('file_name', doc.metadata.get('source', 'Unknown')),
                        'drug_name': doc.metadata.get('drug_name', 'Unknown'),
                        'original_content': getattr(doc, 'page_content', ''),
                        'page_number': doc.metadata.get('page_number')
                    }
                    # Include any additional metadata fields that might exist
                    for key, value in doc.metadata.items():
                        if key not in doc_metadata:
                            doc_metadata[key] = value
                else:
                    # Fallback structure if metadata is missing
                    doc_metadata = {
                        'file_name': 'Unknown',
                        'drug_name': 'Unknown',
                        'original_content': getattr(doc, 'page_content', ''),
                        'page_number': None
                    }
                metadata_details.append(doc_metadata)

            return {
                "response": cleaned_response,
                "confidence_score": confidence_score,
                "documents_used": len(relevant_docs),
                "total_documents_available": len(docs),
                "source_sections": [doc.metadata.get("source", "Unknown") for doc in relevant_docs[:3]],
                "metadata_details": metadata_details
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced metadata extraction: {str(e)}")
            return {
                "response": f"Error occurred while extracting metadata: {str(e)}",
                "confidence_score": 0.0,
                "documents_used": 0,
                "total_documents_available": 0,
                "source_sections": [],
                "metadata_details": []
            }
    
    def _grade_documents_for_metadata(
        self, 
        documents: List[Dict[str, Any]], 
        query: str,
        metadata_name: str
    ) -> Dict[str, Any]:
        """Grade documents for relevance to metadata extraction query."""
        try:
            from utils.llm_util import get_llm_grading
            
            llm = get_llm_grading()
            
            relevant_documents = []
            relevance_scores = []
            
            # Grade each document for relevance
            for doc in documents:
                grade_prompt = f"""
You are a document relevance grader for FDA metadata extraction.

METADATA TO EXTRACT: {metadata_name}
EXTRACTION QUERY: {query}

DOCUMENT CONTENT: {doc.metadata.get('original_content', doc.page_content)[:1000]}...

Grade this document's relevance for extracting the specified metadata:
- Score 'yes' if the document contains information directly related to {metadata_name}
- Score 'no' if the document is not relevant to {metadata_name}

Provide only 'yes' or 'no' as your answer.
"""
                
                try:
                    grade_result = llm.invoke(grade_prompt)
                    grade = grade_result.content.lower().strip()
                    
                    if "yes" in grade:
                        relevant_documents.append(doc)
                        relevance_scores.append(1.0)
                    else:
                        relevance_scores.append(0.0)
                        
                except Exception as e:
                    logger.warning(f"Document grading failed: {e}")
                    # If grading fails, assume document is relevant
                    relevant_documents.append(doc)
                    relevance_scores.append(0.5)
            
            logger.info(f"Document grading: {len(relevant_documents)}/{len(documents)} relevant")
            
            return {
                "relevant_documents": relevant_documents,
                "relevance_scores": relevance_scores,
                "relevant_count": len(relevant_documents),
                "total_count": len(documents)
            }
            
        except Exception as e:
            logger.error(f"Error grading documents: {str(e)}")
            # Return all documents if grading fails
            return {
                "relevant_documents": documents,
                "relevance_scores": [0.5] * len(documents),
                "relevant_count": len(documents),
                "total_count": len(documents)
            }
    
    def _calculate_metadata_confidence(
        self, 
        response: str, 
        documents: List[Dict[str, Any]], 
        query: str,
        metadata_name: str
    ) -> float:
        """Calculate confidence score for metadata extraction based on multiple factors."""
        try:
            base_confidence = 0.6  # Base confidence
            
            # Factor 1: Response quality and specificity
            response_lower = response.lower()
            
            # Boost for specific, detailed responses
            if len(response.strip()) > 20 and "not found" not in response_lower:
                base_confidence += 0.15
            
            # Boost for FDA-specific terminology
            fda_terms = ["fda", "approval", "indication", "dosage", "adverse", "contraindication", 
                        "clinical", "trial", "efficacy", "safety", "pharmacology", "toxicity"]
            fda_term_count = sum(1 for term in fda_terms if term in response_lower)
            if fda_term_count > 0:
                base_confidence += min(fda_term_count * 0.03, 0.15)
            
            # Factor 2: Document relevance and count
            if len(documents) >= 10:
                base_confidence += 0.1  # More documents = better context
            elif len(documents) >= 5:
                base_confidence += 0.05
            
            # Factor 3: Consistency across documents (simplified check)
            # Check if response contains specific values that suggest good extraction
            if any(pattern in response for pattern in [
                "mg", "ml", "day", "daily", "week", "month", "year", "%", "approved", "indicated"
            ]):
                base_confidence += 0.1
            
            # Factor 4: Response certainty indicators
            certainty_indicators = ["specifically", "clearly", "explicitly", "states", "indicates", "shows"]
            if any(indicator in response_lower for indicator in certainty_indicators):
                base_confidence += 0.05
            
            # Cap confidence at 1.0
            final_confidence = min(base_confidence, 1.0)
            
            logger.info(f"Confidence calculation for {metadata_name}: {final_confidence:.2f}")
            return final_confidence
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0.7  # Default medium confidence

    def create_collection_specific(self, collection_name: str, metadata: Dict = None) -> Any:
        """
        Create a collection with specific name and metadata.
        
        Args:
            collection_name: Name for the new collection
            metadata: Optional metadata to attach to the collection
            
        Returns:
            The created collection object or None if failed
        """
        try:
            logger.info(f"Creating collection: {collection_name} with metadata: {metadata}")
            
            # Sanitize the collection name
            sanitized_name = self.sanitize_collection_name(collection_name)
            
            # Try to get embedding function
            embedding_function = None
            try:
                from utils.llm_util import get_embeddings_function
                embedding_function = get_embeddings_function()
            except Exception as embed_error:
                logger.warning(f"Could not get embedding function: {embed_error}")
                # Continue without custom embedding function
            
            # Create collection metadata with optimized HNSW parameters
            collection_metadata = {
                "hnsw:space": "cosine",
                "hnsw:ef_construction": 400,  # Increased from default 200 for better build quality
                "hnsw:M": 48,  # Increased from default 16 for more connections
                "hnsw:search_ef": 200,  # Increased for better search quality
                "hnsw:num_threads": 4  # Use multiple threads for operations
            }
            if metadata:
                # Add custom metadata, ensuring it's serializable
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        collection_metadata[key] = value
                    else:
                        collection_metadata[key] = str(value)
            
            # Create the collection
            collection = self.chroma_client.create_collection(
                name=sanitized_name,
                embedding_function=embedding_function,
                metadata=collection_metadata
            )
            
            logger.info(f"Successfully created collection: {sanitized_name}")
            return collection
            
        except ValueError as ve:
            # Collection might already exist
            if "already exists" in str(ve):
                logger.warning(f"Collection {collection_name} already exists")
                return self.get_or_create_collection(collection_name)
            else:
                logger.error(f"ValueError creating collection: {str(ve)}")
                return None
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {str(e)}")
            return None

    def get_document_vectors(self, collection_name: str, document_id: str) -> Dict[str, Any]:
        """
        Retrieve vectors for a specific document from a collection.
        
        Args:
            collection_name: Name of the collection
            document_id: ID of the document (typically the source file name)
            
        Returns:
            Dictionary containing document vectors and metadata
        """
        try:
            logger.info(f"Retrieving vectors for document {document_id} from collection {collection_name}")
            
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                return {"error": "Collection not found", "vectors": []}
            
            # Query by document source metadata
            results = collection.get(
                where={"source": document_id},
                include=["embeddings", "metadatas", "documents"]
            )
            
            if results.get('ids') is None or len(results.get('ids', [])) == 0:
                logger.warning(f"No vectors found for document {document_id}")
                return {
                    "document_id": document_id,
                    "collection": collection_name,
                    "vectors": [],
                    "count": 0
                }
            
            # Format the results
            vectors_data = []
            for i, doc_id in enumerate(results['ids']):
                vector_info = {
                    "id": doc_id,
                    "content": results['documents'][i] if results.get('documents') and i < len(results['documents']) else None,
                    "metadata": results['metadatas'][i] if results.get('metadatas') and i < len(results['metadatas']) else {},
                    "embedding": results['embeddings'][i] if results.get('embeddings') and i < len(results['embeddings']) else None
                }
                vectors_data.append(vector_info)
            
            logger.info(f"Retrieved {len(vectors_data)} vectors for document {document_id}")
            
            return {
                "document_id": document_id,
                "collection": collection_name,
                "vectors": vectors_data,
                "count": len(vectors_data)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving document vectors: {str(e)}")
            return {
                "error": str(e),
                "document_id": document_id,
                "collection": collection_name,
                "vectors": [],
                "count": 0
            }

    def copy_vectors_to_collection(self, vectors_data: Dict, target_collection: str) -> Dict[str, Any]:
        """
        Copy vectors from one collection to another.
        
        Args:
            vectors_data: Dictionary containing vectors data (from get_document_vectors)
            target_collection: Name of the target collection
            
        Returns:
            Dictionary with copy operation status
        """
        try:
            if not vectors_data or "vectors" not in vectors_data:
                return {"status": "failure", "error": "Invalid vectors data provided"}
            
            vectors = vectors_data.get("vectors", [])
            if not vectors:
                return {"status": "success", "message": "No vectors to copy", "copied_count": 0}
            
            source_document = vectors_data.get("document_id", "Unknown")
            logger.info(f"Copying {len(vectors)} vectors from {source_document} to collection {target_collection}")
            
            # Get or create target collection
            target_col = self.get_or_create_collection(target_collection)
            if not target_col:
                return {"status": "failure", "error": "Could not create target collection"}
            
            # Prepare batch data
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for vector in vectors:
                # Generate new ID for target collection
                new_id = str(uuid.uuid4())
                ids.append(new_id)
                
                # Copy document content
                documents.append(vector.get("content", ""))
                
                # Copy and update metadata
                metadata = vector.get("metadata", {}).copy()
                metadata["copied_from"] = vectors_data.get("collection", "Unknown")
                metadata["copy_timestamp"] = str(uuid.uuid4())[:8]  # Add timestamp marker
                metadatas.append(metadata)
                
                # Copy embedding if available
                if vector.get("embedding"):
                    embeddings.append(vector["embedding"])
            
            # Add to target collection
            try:
                if embeddings:
                    target_col.add(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas,
                        embeddings=embeddings
                    )
                else:
                    # Let ChromaDB generate embeddings
                    target_col.add(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                
                logger.info(f"Successfully copied {len(vectors)} vectors to {target_collection}")
                
                return {
                    "status": "success",
                    "copied_count": len(vectors),
                    "source_document": source_document,
                    "source_collection": vectors_data.get("collection", "Unknown"),
                    "target_collection": target_collection,
                    "message": f"Successfully copied {len(vectors)} vectors"
                }
                
            except Exception as add_error:
                logger.error(f"Error adding vectors to target collection: {str(add_error)}")
                
                # Try batch processing if direct add fails
                if len(vectors) > 100:
                    logger.info("Attempting batch processing for large vector set")
                    copied_count = 0
                    batch_size = 50
                    
                    for i in range(0, len(vectors), batch_size):
                        batch_end = min(i + batch_size, len(vectors))
                        try:
                            if embeddings:
                                target_col.add(
                                    ids=ids[i:batch_end],
                                    documents=documents[i:batch_end],
                                    metadatas=metadatas[i:batch_end],
                                    embeddings=embeddings[i:batch_end]
                                )
                            else:
                                target_col.add(
                                    ids=ids[i:batch_end],
                                    documents=documents[i:batch_end],
                                    metadatas=metadatas[i:batch_end]
                                )
                            copied_count += (batch_end - i)
                        except Exception as batch_error:
                            logger.error(f"Batch {i//batch_size + 1} failed: {str(batch_error)}")
                    
                    if copied_count > 0:
                        return {
                            "status": "partial_success",
                            "copied_count": copied_count,
                            "total_vectors": len(vectors),
                            "source_document": source_document,
                            "target_collection": target_collection,
                            "message": f"Copied {copied_count} of {len(vectors)} vectors"
                        }
                
                return {"status": "failure", "error": str(add_error)}
            
        except Exception as e:
            logger.error(f"Error copying vectors to collection: {str(e)}")
            return {"status": "failure", "error": str(e)}

    def copy_document_by_source_file_id(
        self,
        source_file_id: int,
        source_collection: str = "fda_documents",
        target_collection: str = None,
        collection_id: int = None,
        update_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Copy all vectors for a document (identified by source_file_id) from one collection to another.
        This method is optimized for the collection indexing service to avoid regenerating embeddings.
        
        Args:
            source_file_id: The source file ID to copy vectors for
            source_collection: Source collection name (default: "fda_documents")
            target_collection: Target collection name
            collection_id: Collection ID for generating consistent IDs in target
            update_metadata: Additional metadata to add/update in copied vectors
            
        Returns:
            Dictionary with copy operation status and details
        """
        try:
            if not target_collection:
                return {"status": "failure", "error": "Target collection name is required"}
            
            logger.info(f"Copying vectors for source_file_id {source_file_id} from {source_collection} to {target_collection}")
            
            # Get source and target collections
            source_col = self.get_or_create_collection(source_collection)
            target_col = self.get_or_create_collection(target_collection)
            
            if not source_col or not target_col:
                return {"status": "failure", "error": "Could not access collections"}
            
            # Query all vectors for this source_file_id
            # ChromaDB might store integers as either int or string, so we'll try both
            results = None
            
            # Try 1: Query by integer source_file_id
            try:
                results = source_col.get(
                    where={"source_file_id": source_file_id},
                    include=["embeddings", "metadatas", "documents"]
                )
                if results.get('ids') is not None and len(results.get('ids', [])) > 0:
                    logger.debug(f"Found vectors using integer source_file_id: {source_file_id}")
            except Exception as e:
                logger.debug(f"Integer query failed: {str(e)}")
                results = None
            
            # Try 2: Query by string source_file_id if integer didn't work
            if results is None or results.get('ids') is None or len(results.get('ids', [])) == 0:
                try:
                    results = source_col.get(
                        where={"source_file_id": str(source_file_id)},
                        include=["embeddings", "metadatas", "documents"]
                    )
                    if results.get('ids') is not None and len(results.get('ids', [])) > 0:
                        logger.debug(f"Found vectors using string source_file_id: '{source_file_id}'")
                except Exception as e:
                    logger.debug(f"String query failed: {str(e)}")
                    results = None
            
            # Try 3: Get all documents and filter manually (fallback for small collections)
            # IMPORTANT: This is expensive and should only be done for small collections
            if results is None or results.get('ids') is None or len(results.get('ids', [])) == 0:
                try:
                    # First check collection size to avoid expensive operations
                    collection_count = source_col.count()
                    logger.info(f"No vectors found for source_file_id {source_file_id} using direct queries. Collection {source_collection} has {collection_count} documents.")
                    
                    # For large collections, skip the expensive manual search
                    if collection_count > 1000:
                        logger.warning(f"Collection {source_collection} has {collection_count} documents. Skipping manual search to avoid performance issues.")
                        return {
                            "status": "not_found",
                            "message": f"Document {source_file_id} not found in {source_collection} (collection too large for manual search)",
                            "copied_count": 0
                        }
                    
                    # For very large collections, don't even attempt
                    if collection_count > 100:
                        logger.info(f"Collection {source_collection} has {collection_count} documents. Document likely doesn't exist, skipping manual search.")
                        return {
                            "status": "not_found", 
                            "message": f"Document {source_file_id} not found in {source_collection}",
                            "copied_count": 0
                        }
                    
                    logger.info(f"Falling back to manual search for source_file_id {source_file_id} in collection with {collection_count} documents")
                    all_results = source_col.get(
                        limit=collection_count + 100,  # Get all documents with some buffer
                        include=["embeddings", "metadatas", "documents"]
                    )
                    
                    # Filter manually
                    filtered_ids = []
                    filtered_embeddings = []
                    filtered_metadatas = []
                    filtered_documents = []
                    
                    for i, metadata in enumerate(all_results.get('metadatas', [])):
                        # Check if this document matches our source_file_id
                        if (metadata.get('source_file_id') == source_file_id or 
                            metadata.get('source_file_id') == str(source_file_id) or
                            str(metadata.get('source_file_id', '')) == str(source_file_id)):
                            
                            filtered_ids.append(all_results['ids'][i])
                            if all_results.get('embeddings') and i < len(all_results['embeddings']):
                                filtered_embeddings.append(all_results['embeddings'][i])
                            if all_results.get('documents') and i < len(all_results['documents']):
                                filtered_documents.append(all_results['documents'][i])
                            filtered_metadatas.append(metadata)
                    
                    if filtered_ids:
                        results = {
                            'ids': filtered_ids,
                            'embeddings': filtered_embeddings,
                            'metadatas': filtered_metadatas,
                            'documents': filtered_documents
                        }
                        logger.info(f"Found {len(filtered_ids)} vectors through manual search")
                except Exception as e:
                    logger.error(f"Manual search failed: {str(e)}")
                    results = None
            
            if results is None or results.get('ids') is None or len(results.get('ids', [])) == 0:
                logger.warning(f"No vectors found for source_file_id {source_file_id} in {source_collection}")
                return {
                    "status": "success",
                    "message": "No vectors found to copy",
                    "source_file_id": source_file_id,
                    "copied_count": 0
                }
            
            # Prepare data for batch copying
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            num_vectors = len(results['ids'])
            logger.info(f"Found {num_vectors} vectors to copy for source_file_id {source_file_id}")
            
            for i in range(num_vectors):
                # Generate consistent ID for target collection
                if collection_id:
                    # Use the same ID pattern as in collection_indexing_service
                    chunk_idx = i
                    new_id = f"collection_{collection_id}_doc_{source_file_id}_chunk_{chunk_idx}"
                else:
                    new_id = str(uuid.uuid4())
                
                ids.append(new_id)
                
                # Copy document content
                doc_content = results['documents'][i] if results.get('documents') and i < len(results['documents']) else ""
                documents.append(doc_content)
                
                # Copy and update metadata
                original_metadata = results['metadatas'][i] if results.get('metadatas') and i < len(results['metadatas']) else {}
                metadata = original_metadata.copy()
                
                # Update metadata with new collection info
                if collection_id:
                    metadata['collection_id'] = collection_id
                
                # Add any additional metadata updates
                if update_metadata:
                    metadata.update(update_metadata)
                
                # Ensure source_file_id is in metadata
                metadata['source_file_id'] = source_file_id
                
                # Add copy tracking info
                metadata['copied_from_collection'] = source_collection
                metadata['copy_timestamp'] = datetime.utcnow().isoformat()
                
                metadatas.append(metadata)
                
                # Copy embedding
                if results.get('embeddings') is not None and i < len(results['embeddings']):
                    embeddings.append(results['embeddings'][i])
            
            # Batch add to target collection
            batch_size = 50  # ChromaDB recommended batch size
            total_copied = 0
            failed_batches = 0
            
            for batch_start in range(0, num_vectors, batch_size):
                batch_end = min(batch_start + batch_size, num_vectors)
                
                try:
                    if embeddings:
                        # Add with existing embeddings
                        target_col.add(
                            ids=ids[batch_start:batch_end],
                            documents=documents[batch_start:batch_end],
                            metadatas=metadatas[batch_start:batch_end],
                            embeddings=embeddings[batch_start:batch_end]
                        )
                    else:
                        # Let ChromaDB generate embeddings (fallback)
                        logger.warning("No embeddings found, ChromaDB will generate new ones")
                        target_col.add(
                            ids=ids[batch_start:batch_end],
                            documents=documents[batch_start:batch_end],
                            metadatas=metadatas[batch_start:batch_end]
                        )
                    
                    total_copied += (batch_end - batch_start)
                    
                    if batch_end % 100 == 0:  # Log progress every 100 vectors
                        logger.info(f"Progress: Copied {batch_end}/{num_vectors} vectors")
                    
                except Exception as batch_error:
                    logger.error(f"Error copying batch {batch_start}-{batch_end}: {str(batch_error)}")
                    failed_batches += 1
            
            # Log final results
            success_rate = (total_copied / num_vectors * 100) if num_vectors > 0 else 0
            logger.info(
                f"Copy operation completed: {total_copied}/{num_vectors} vectors copied successfully "
                f"({success_rate:.1f}% success rate)"
            )
            
            return {
                "status": "success" if total_copied > 0 else "failure",
                "source_file_id": source_file_id,
                "source_collection": source_collection,
                "target_collection": target_collection,
                "total_vectors": num_vectors,
                "copied_count": total_copied,
                "failed_batches": failed_batches,
                "success_rate": success_rate,
                "message": f"Copied {total_copied} of {num_vectors} vectors with existing embeddings"
            }
            
        except Exception as e:
            logger.error(f"Error copying document vectors by source_file_id: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failure",
                "error": str(e),
                "source_file_id": source_file_id
            }

    def query_collection(self, collection_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Query a specific collection.
        
        Args:
            collection_name: Name of the collection to query
            query: Search query
            k: Number of results to return (default 5)
            
        Returns:
            List of search results with content and metadata
        """
        try:
            logger.info(f"Querying collection {collection_name} with: {query} (k={k})")
            
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                logger.error(f"Collection {collection_name} not found")
                return []
            
            # Perform the query
            results = collection.query(
                query_texts=[query],
                n_results=k,
                include=["metadatas", "documents", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results.get('documents') is not None and len(results.get('documents', [])) > 0 and results['documents'][0] is not None:
                for i, doc in enumerate(results['documents'][0]):
                    result = {
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results.get('metadatas') is not None else {},
                        'distance': results['distances'][0][i] if results.get('distances') is not None else None,
                        'score': 1 - results['distances'][0][i] if results.get('distances') is not None and results['distances'][0][i] is not None else None
                    }
                    formatted_results.append(result)
            
            logger.info(f"Found {len(formatted_results)} results in collection {collection_name}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying collection {collection_name}: {str(e)}")
            return []
    
    async def query_with_hybrid_retrieval(
        self,
        query: str,
        collection_name: str = "fda_documents",
        n_results: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Tuple[str, str]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Query using hybrid retrieval with reranking"""
        
        logger.info(f"Starting hybrid retrieval for collection: {collection_name}")
        
        # Get all documents from collection for BM25
        collection = self.chroma_client.get_collection(
            self.sanitize_collection_name(collection_name)
        )
        
        # Retrieve documents (with pagination for large collections)
        all_docs = []
        offset = 0
        batch_size = 1000
        
        while True:
            batch = collection.get(
                limit=batch_size,
                offset=offset,
                include=['documents', 'metadatas', 'embeddings']
            )
            
            if not batch['ids']:
                break
            
            for i, doc_id in enumerate(batch['ids']):
                doc = Document(
                    page_content=batch['documents'][i],
                    metadata=batch['metadatas'][i] if batch['metadatas'] else {}
                )
                all_docs.append(doc)
            
            offset += batch_size
            
            # Limit total documents for performance
            if len(all_docs) >= 10000:
                logger.warning(f"Limited document retrieval to 10000 documents")
                break
        
        logger.info(f"Retrieved {len(all_docs)} documents for hybrid search")
        
        # Create vector store
        from utils.llm_util import get_embeddings_model
        vector_store = Chroma(
            client=self.chroma_client,
            collection_name=self.sanitize_collection_name(collection_name),
            embedding_function=get_embeddings_model()
        )
        
        # Initialize hybrid retriever
        from .hybrid_retriever import HybridRetriever
        
        hybrid_retriever = HybridRetriever(
            vector_store=vector_store,
            documents=all_docs,
            initial_k=50,
            final_k=n_results,
            token_budget=50000  # Reserve tokens for context and generation
        )
        
        # Perform hybrid retrieval
        retrieved_docs = await hybrid_retriever.retrieve(query, filter_dict)
        
        # Continue with existing LLM chain logic
        return self._generate_response_with_docs(
            query=query,
            documents=retrieved_docs,
            chat_history=chat_history
        )
    
    def _is_no_information_response(self, response: str) -> bool:
        """Check if the response indicates no relevant information was found"""
        no_info_patterns = [
            "information about .* is not available in the provided documents",
            "no.*information.*found",
            "no.*relevant.*information",
            "no.*data.*available",
            "not.*found.*in.*documents",
            "cannot.*find.*information",
            "no.*details.*available",
            "information.*not.*available",
            "unable to find",
            "no information in the provided documents",
            "doesn't contain.*information",
            "don't have.*information"
        ]
        
        response_lower = response.lower()
        for pattern in no_info_patterns:
            import re
            if re.search(pattern, response_lower):
                return True
        return False
    
    def _create_enhanced_generation_prompt(
        self,       
        documents: List[Document],       
        original_query: str
    ) -> str:
        """
        Create a detailed, structured prompt for response generation
        
        Args:
            documents: Retrieved documents
            original_query: User's original query (not enhanced)
            
        Returns:
            Structured prompt for LLM
        """
        
        # Detect query type for better response formatting
        query_lower = original_query.lower()        

        formatted_docs = ""
        for i, doc in enumerate(documents, 1):
            # Use original_content from metadata
            content = doc.metadata.get('original_content', '')
            if not content:
                logger.warning(f"Document {i} missing original_content in metadata")
                continue  # Skip documents without original_content
            content = content[:1500]  # Limit per document
            metadata = doc.metadata
            formatted_docs += f"""
            [Document {i}]
            Source: {metadata.get('source', 'Unknown')}
            Drug: {metadata.get('drug_name', 'Not specified')}
            Content: {content}
            ---""" 

        qa_system_prompt = (
            "You are an expert pharmaceutical regulatory and HTA information specialist with deep knowledge of FDA, EMA, "
            "NICE, TLV, and other international regulatory/HTA processes. Your task is to provide a professional response "
            "strictly based on the provided context.\n\n"

            "=== RESPONSE STYLE REQUIREMENTS ===\n"
            "1. Always adapt your response length and style to the user's request:\n"
            "   - If the user explicitly asks for a short or concise answer, provide only what is requested.\n"
            "   - If the user does not specify brevity, provide a full structured professional response.\n"
            "2. For detailed responses:\n"
            "   - If the query is about a decision, status, or outcome's begin with a short executive summary, then expand.\n"
            "   - For FDA/regulatory queries: Approval Status, Indication(s), Supporting Evidence, Rationale, Additional Notes.\n"
            "   - For HTA queries: Decision, Rationale, Cost/Pricing, Clinical Evidence, Additional Notes.\n"
            "   - For technical/explanatory queries: Definitions, Explanation, Context, Practical Significance.\n"
            "3. Use markdown formatting (bold, headings, tables if needed).\n"
            "4. Always explain technical terms and acronyms.\n"
            "5. Maintain a professional but clear tone like a regulatory or HTA briefing.\n\n"  
            "6. Always provide a clear and relevant initial response that sets the right context for the user's query.\n\n"    

            "=== LANGUAGE & PRESENTATION ===\n"
            "- Always respond in English.\n"
            "- Translate and explain any non-English terms in context.\n"
            "- Be thorough but concise, balancing context, data, and interpretation.\n\n"

            "=== HANDLING MISSING INFORMATION ===\n"
            "If the requested detail (e.g., FDA approval date, HTA price decision) is not available in the context, state clearly: "
            "'This information is not available in the provided sources.'\n\n"

            "=== CONTEXT ===\n"
            f"{formatted_docs}\n\n"

            "=== USER QUESTION ===\n"
            f"{original_query}\n\n"

            "Now provide a response that directly matches the user's request in style and length, "
            "while remaining accurate and professional in English only."
            "\n\nCRITICAL INSTRUCTION: Do NOT repeat the user's query in your response. Begin your answer directly"
        )




        return qa_system_prompt

    def _generate_response_with_docs(
        self,
        query: str,
        documents: List[Document],
        chat_history: Optional[List[Tuple[str, str]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate response using retrieved documents and return source information"""
        try:
            from utils.llm_util import get_llm
            
            # Create history-aware chain if chat history exists
            if chat_history:
                from langchain.chains import create_history_aware_retriever
                
                contextualize_q_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Given a chat history and the latest user question "
                               "which might reference context in the chat history, "
                               "formulate a standalone question which can be understood "
                               "without the chat history."),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ])
                
                llm = get_llm()
                # Create a simple retriever from documents using LangChain's base class
                from langchain_core.retrievers import BaseRetriever
                from langchain_core.callbacks import CallbackManagerForRetrieverRun
                
                class DocListRetriever(BaseRetriever):
                    docs: List[Document]
                    
                    class Config:
                        arbitrary_types_allowed = True
                    
                    def _get_relevant_documents(
                        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
                    ) -> List[Document]:
                        return self.docs
                    
                    async def _aget_relevant_documents(
                        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
                    ) -> List[Document]:
                        return self.docs
                
                retriever = DocListRetriever(docs=documents)
                history_aware_retriever = create_history_aware_retriever(
                    llm, retriever, contextualize_q_prompt
                )
            else:
                from langchain_core.retrievers import BaseRetriever
                from langchain_core.callbacks import CallbackManagerForRetrieverRun
                
                class DocListRetriever(BaseRetriever):
                    docs: List[Document]
                    
                    class Config:
                        arbitrary_types_allowed = True
                    
                    def _get_relevant_documents(
                        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
                    ) -> List[Document]:
                        return self.docs
                    
                    async def _aget_relevant_documents(
                        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
                    ) -> List[Document]:
                        return self.docs
                
                retriever = DocListRetriever(docs=documents)
                history_aware_retriever = retriever
            
            # Create QA chain
            messages = [
                ("system", """You are a pharmaceutical expert providing answers about FDA-approved drugs based STRICTLY on the provided context.

CRITICAL RULES:
1. You MUST ONLY use information explicitly stated in the provided context below
2. DO NOT use any external knowledge or information not present in the context
3. If the answer is not in the context, say "The information about [specific topic] is not available in the provided documents"
4. NEVER make up or hallucinate information about drugs not mentioned in the context
5. ONLY mention drugs that appear in the context documents

# Conversational Context Handling
- Pay attention to previous messages in the conversation for context
- Reference earlier topics naturally when relevant
- Maintain conversation continuity and remember what the user has asked about
- If the user asks follow-up questions, assume they relate to previous topics unless explicitly stated otherwise

When multiple drug documents are provided, you MUST:
1. Analyze and include information from ALL documents in the context
2. Clearly identify which drug each piece of information relates to
3. Compare and contrast information across all drugs when relevant
4. ONLY discuss drugs that are explicitly mentioned in the context

{context}

Remember: Base your response ONLY on the information provided above. Do not add information from external sources."""),
            ]
            
            # Only add chat history placeholder if there's actual history
            if chat_history:
                messages.append(MessagesPlaceholder("chat_history"))
            
            messages.append(("human", "{input}"))
            
            qa_prompt = ChatPromptTemplate.from_messages(messages)
            
            llm = get_llm()
            from langchain.chains.combine_documents import create_stuff_documents_chain
            from langchain.chains import create_retrieval_chain
            
            question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
            rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
            
            # Execute chain
            # Format chat history for LangChain
            formatted_history = []
            if chat_history:
                for human_msg, ai_msg in chat_history:
                    formatted_history.extend([
                        ("human", human_msg),
                        ("assistant", ai_msg)
                    ])
            
            result = rag_chain.invoke({
                "input": query,
                "chat_history": formatted_history
            })
            
            response = result.get("answer", "No response generated.")
            
            # Clean response to remove unwanted prefixes
            cleaned_response = self._clean_response(response)
            logger.info(f"Generated response: {cleaned_response[:100]}...")
            
            # Prepare source documents information
            source_docs = []
            for idx, doc in enumerate(documents[:10]):  # Limit to top 10 most relevant
                # Generate a unique ID based on metadata or use index
                doc_id = doc.metadata.get("id", f"doc_{idx}")
                if not doc_id:
                    doc_id = f"doc_{idx}"
                    
                # Use original_content if available, otherwise fall back to page_content
                content_preview = doc.metadata.get("original_content", doc.page_content)
                if isinstance(content_preview, str) and len(content_preview) > 300:
                    content_preview = content_preview[:300] + "..."
                    
                # Copy metadata and ensure file_url is included
                metadata = {k: v for k, v in doc.metadata.items() if k not in ["id", "source", "file_name", "chunk_id", "original_content"]}
                # Note: file_url should be added during indexing or fetched from DB
                    
                source_info = {
                    "id": doc_id,
                    "source": doc.metadata.get("source", ""),
                    "file_name": doc.metadata.get("file_name", doc.metadata.get("source", "")),
                    "chunk_id": doc.metadata.get("chunk_id", f"chunk_{doc.metadata.get('chunk_index', idx)}"),
                    "page_content_preview": content_preview,
                    "metadata": metadata
                }
                source_docs.append(source_info)
            
            # Check if response indicates no information was found
            if self._is_no_information_response(cleaned_response):
                logger.info("Response indicates no relevant information found, returning empty source docs")
                return cleaned_response, []
            
            return cleaned_response, source_docs
            
        except Exception as e:
            logger.error(f"Error generating response with docs: {str(e)}")
            return "I'm experiencing a technical issue and cannot process your request right now. Please try again later.", []
    
    async def retrieve_with_multi_query(
        self,
        original_query: str,
        collection_name: str,
        chat_history: Optional[List[Tuple[str, str]]] = None,
        n_results_per_query: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve documents using multiple query variations with deduplication
        and intelligent ranking.
        """
        from .multi_query_generator import MultiQueryGenerator
        from utils.llm_util import get_llm
        
        # Initialize generator
        generator = MultiQueryGenerator(get_llm(), max_queries=5)
        
        # Generate query variations
        queries = await generator.generate_queries(
            original_query, 
            chat_history,
            domain="FDA pharmaceutical"
        )
        
        # Parallel retrieval for all queries
        async def retrieve_for_query(query: str) -> List[Tuple[Document, float, str]]:
            """Retrieve and tag documents with query source"""
            try:
                # If metadata filter provided, use collection query with filter
                if metadata_filter:
                    collection = self.get_or_create_collection(collection_name)
                    if not collection:
                        logger.error(f"Collection {collection_name} not found")
                        return []
                    
                    # Use ChromaDB's query method with metadata filter
                    results = collection.query(
                        query_texts=[query],
                        n_results=n_results_per_query,
                        where=metadata_filter,
                        include=["metadatas", "documents", "distances"]
                    )
                    
                    # Convert results to Document format
                    docs_with_scores = []
                    if results.get('documents') and results['documents'][0]:
                        for i, doc_content in enumerate(results['documents'][0]):
                            metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                            distance = results['distances'][0][i] if results.get('distances') else 0.0
                            # Convert distance to similarity score (lower distance = higher similarity)
                            score = 1.0 - distance
                            
                            doc = Document(
                                page_content=doc_content,
                                metadata=metadata
                            )
                            docs_with_scores.append((doc, score, query))
                    
                    return docs_with_scores
                else:
                    # Original code without filter
                    from utils.llm_util import get_embeddings_model
                    vector_store = Chroma(
                        client=self.chroma_client,
                        collection_name=self.sanitize_collection_name(collection_name),
                        embedding_function=get_embeddings_model()
                    )
                    
                    docs = await vector_store.asimilarity_search_with_score(
                        query, 
                        k=n_results_per_query
                    )
                    # Tag with source query for ranking
                    return [(doc, score, query) for doc, score in docs]
            except Exception as e:
                logger.error(f"Error retrieving for query '{query}': {e}")
                return []
        
        # Execute parallel retrieval
        all_results = await asyncio.gather(*[
            retrieve_for_query(q) for q in queries
        ])
        
        # Deduplicate and rank
        unique_docs = self._deduplicate_and_rank_multi_query(all_results)
        
        return unique_docs

    async def retrieve_single_query(
        self,
        query: str,
        collection_name: str,
        n_results: int = 30,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Simple single-query retrieval without multi-query expansion.
        
        Args:
            query: The search query
            collection_name: Name of the collection to search
            n_results: Number of results to return
            metadata_filter: Optional metadata filter
            
        Returns:
            List of Document objects
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                logger.error(f"Collection {collection_name} not found")
                return []
            
            # Build query parameters
            query_params = {
                "query_texts": [query],
                "n_results": n_results,
                "include": ["metadatas", "documents", "distances"]
            }
            
            if metadata_filter:
                query_params["where"] = metadata_filter
                
            # Execute query
            results = collection.query(**query_params)
            
            # Convert to Document objects
            documents = []
            if results.get('documents') and results['documents'][0]:
                for i, doc_content in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                    
                    doc = Document(
                        page_content=doc_content,
                        metadata=metadata
                    )
                    documents.append(doc)
            
            logger.info(f"Retrieved {len(documents)} documents with single query")
            return documents
            
        except Exception as e:
            logger.error(f"Error in single query retrieval: {str(e)}")
            return []
    
    def _deduplicate_and_rank_multi_query(
        self, 
        results_lists: List[List[Tuple[Document, float, str]]]
    ) -> List[Document]:
        """
        Deduplicate documents and rank by frequency, position, and relevance.
        """
        from collections import defaultdict
        
        doc_info = defaultdict(lambda: {
            'doc': None,
            'queries': [],
            'scores': [],
            'positions': [],
            'frequency': 0
        })
        
        # Aggregate information for each document
        for query_results in results_lists:
            for position, (doc, score, source_query) in enumerate(query_results):
                doc_id = self._get_doc_id(doc)
                
                if doc_info[doc_id]['doc'] is None:
                    doc_info[doc_id]['doc'] = doc
                
                doc_info[doc_id]['queries'].append(source_query)
                doc_info[doc_id]['scores'].append(score)
                doc_info[doc_id]['positions'].append(position)
                doc_info[doc_id]['frequency'] += 1
        
        # Calculate final rankings
        ranked_docs = []
        for doc_id, info in doc_info.items():
            # Composite score based on:
            # - Frequency (how many queries retrieved it)
            # - Average position (how high it ranked)
            # - Average score (relevance)
            
            avg_position = sum(info['positions']) / len(info['positions'])
            avg_score = sum(info['scores']) / len(info['scores'])
            frequency_bonus = info['frequency'] / len(results_lists)
            
            # Weighted composite score
            final_score = (
                0.4 * frequency_bonus +  # 40% weight for appearing in multiple queries
                0.3 * (1 / (avg_position + 1)) +  # 30% weight for position
                0.3 * avg_score  # 30% weight for relevance score
            )
            
            ranked_docs.append((info['doc'], final_score, info))
        
        # Sort by final score
        ranked_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Log ranking information
        logger.info(f"Deduplicated to {len(ranked_docs)} unique documents")
        for i, (doc, score, info) in enumerate(ranked_docs[:5]):
            logger.debug(f"Rank {i+1}: Score={score:.3f}, Frequency={info['frequency']}, "
                        f"Queries={len(info['queries'])}")
        
        return [doc for doc, _, _ in ranked_docs]
    
    def _get_doc_id(self, doc: Document) -> str:
        """Generate unique ID for document"""
        # Use first 200 chars of content + metadata hash
        content_preview = doc.page_content[:200]
        metadata_str = str(sorted(doc.metadata.items()))
        return f"{hash(content_preview)}_{hash(metadata_str)}"