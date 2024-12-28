"""
RAG (Retrieval-Augmented Generation) Service

This module provides a service for document processing, retrieval, and generation
using a RAG (Retrieval-Augmented Generation) pipeline.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging
import json
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.base import Embeddings
from langchain_core.documents import Document as LangchainDocument
from langchain.vectorstores import Qdrant
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
import tiktoken

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RAGService:
    """
    A service for handling RAG (Retrieval-Augmented Generation) operations.
    
    This service provides functionality for:
    - Document processing and chunking
    - Vector storage and retrieval
    - Response generation using language models
    """
    
    def __init__(
        self,
        embedding_model: Embeddings,
        llm: Any,
        vector_store_path: Union[str, Path],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_chunks: int = 1000
    ):
        """
        Initialize the RAG service.
        
        Args:
            embedding_model: The embedding model to use for document embeddings
            llm: The language model to use for generation
            vector_store_path: Path to store the vector database
            chunk_size: Maximum size of document chunks (in tokens)
            chunk_overlap: Overlap between chunks (in tokens)
            max_chunks: Maximum number of chunks to process per document
        """
        self.embedding_model = embedding_model
        self.llm = llm
        self.vector_store_path = Path(vector_store_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks
        
        # Initialize tokenizer for chunking
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Initialize vector store
        self.vector_store = self._init_vector_store()
        
        # Initialize QA chain
        self.qa_chain = self._init_qa_chain()
    
    def _init_vector_store(self) -> Qdrant:
        """Initialize the Qdrant vector store."""
        return Qdrant(
            location=str(self.vector_store_path),
            embedding_function=self.embedding_model.embed_documents,
            collection_name="documents"
        )
    
    def _init_qa_chain(self) -> RetrievalQA:
        """Initialize the QA chain for question answering."""
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever(
                search_kwargs={"k": 3}
            ),
            return_source_documents=True
        )
    
    def chunk_document(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a document into chunks with metadata.
        
        Args:
            text: The text to chunk
            metadata: Metadata to include with each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=lambda x: len(self.tokenizer.encode(x)),
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Split text into chunks
        chunks = text_splitter.split_text(text)
        
        # Create chunk dictionaries with metadata
        chunk_docs = []
        for i, chunk in enumerate(chunks[:self.max_chunks]):
            chunk_metadata = metadata.copy()
            chunk_meta = {
                "chunk_id": f"{metadata.get('document_id', '')}-{i}",
                "chunk_index": i,
                "total_chunks": min(len(chunks), self.max_chunks),
                "created_at": datetime.utcnow().isoformat(),
                **chunk_metadata
            }
            chunk_docs.append({
                "text": chunk,
                "metadata": chunk_meta
            })
        
        return chunk_docs
    
    async def process_document(self, file_path: Union[str, Path], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a document file and prepare it for the vector store.
        
        Args:
            file_path: Path to the document file
            metadata: Metadata for the document
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Read the file content
            text = self._read_file(file_path)
            
            # Chunk the document
            chunks = self.chunk_document(text, metadata)
            
            # Prepare documents for vector store
            documents = [
                LangchainDocument(
                    page_content=chunk["text"],
                    metadata=chunk["metadata"]
                )
                for chunk in chunks
            ]
            
            # Add to vector store
            if documents:
                self.vector_store.add_documents(documents)
            
            return {
                "status": "success",
                "document_id": metadata.get("document_id"),
                "chunk_count": len(chunks),
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "document_id": metadata.get("document_id")
            }
    
    async def retrieve_relevant_chunks(
        self,
        query: str,
        k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks for a query.
        
        Args:
            query: The search query
            k: Number of results to return
            filters: Optional filters to apply to the search
            
        Returns:
            List of relevant chunks with scores and metadata
        """
        try:
            # Convert filters to Qdrant format if needed
            qdrant_filters = self._prepare_filters(filters) if filters else None
            
            # Perform similarity search
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=min(k, 10),  # Limit to 10 results max
                filter=qdrant_filters
            )
            
            # Format results
            return [
                {
                    "text": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                }
                for doc, score in results
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}", exc_info=True)
            return []
    
    async def generate_response(
        self,
        query: str,
        chat_history: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response to a query using the RAG pipeline.
        
        Args:
            query: The user's query
            chat_history: Optional chat history for context
            **kwargs: Additional parameters for the QA chain
            
        Returns:
            Dictionary with the response and source documents
        """
        try:
            # Prepare the QA chain input
            result = self.qa_chain({"query": query, "chat_history": chat_history or []})
            
            # Format sources
            sources = [
                {
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 0.0  # Not available in basic QA chain
                }
                for doc in result.get("source_documents", [])
            ]
            
            return {
                "response": result["result"],
                "sources": sources,
                "query": query,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return {
                "response": "I'm sorry, I encountered an error processing your request.",
                "sources": [],
                "error": str(e),
                "query": query
            }
    
    def _read_file(self, file_path: Union[str, Path]) -> str:
        """Read a file and return its content as text."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # TODO: Add support for different file types (PDF, DOCX, etc.)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _prepare_filters(self, filters: Dict[str, Any]) -> Dict:
        """Convert filters to Qdrant filter format."""
        # Simple implementation - can be extended based on Qdrant's filter requirements
        return {"must": [{"key": k, "match": {"value": v}} for k, v in filters.items()]}


def get_rag_service() -> RAGService:
    """Factory function to create a RAGService instance with default settings."""
    # Initialize embedding model
    from langchain.embeddings import HuggingFaceEmbeddings
    
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2",
        model_kwargs={"device": "cpu"}
    )
    
    # Initialize language model
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.1,
        max_tokens=1000
    )
    
    # Create RAG service
    return RAGService(
        embedding_model=embedding_model,
        llm=llm,
        vector_store_path=settings.VECTOR_STORE_PATH,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
