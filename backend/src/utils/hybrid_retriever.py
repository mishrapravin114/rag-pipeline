from typing import List, Dict, Any, Tuple, Optional
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
import numpy as np
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Implements hybrid retrieval combining dense (semantic) and sparse (keyword) search
    with cross-encoder reranking for optimal document retrieval.
    """
    
    def __init__(
        self,
        vector_store,
        documents: List[Document],
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        initial_k: int = 50,
        final_k: int = 10,
        max_rerank_docs: int = 30,  # Limit for reranking to manage compute
        token_budget: int = 50000,   # Token budget for retrieved documents
        use_filtered_only: bool = False  # If True, only use provided documents
    ):
        self.vector_store = vector_store
        self.documents = documents
        self.reranker = CrossEncoder(reranker_model)
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.initial_k = initial_k
        self.final_k = final_k
        self.max_rerank_docs = max_rerank_docs
        self.token_budget = token_budget
        self.use_filtered_only = use_filtered_only
        
        # Initialize BM25
        self._initialize_bm25()
        
        logger.info(f"Initialized HybridRetriever with {len(documents)} documents")
    
    def _initialize_bm25(self):
        """Initialize BM25 with document texts"""
        # Preprocess documents for BM25
        self.preprocessed_docs = []
        for doc in self.documents:
            # Basic preprocessing: lowercase and split
            tokens = doc.page_content.lower().split()
            # Remove very short tokens
            tokens = [t for t in tokens if len(t) > 2]
            self.preprocessed_docs.append(tokens)
        
        self.bm25 = BM25Okapi(self.preprocessed_docs)
        logger.info(f"BM25 initialized with {len(self.preprocessed_docs)} documents")
    
    async def retrieve(
        self, 
        query: str,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Perform hybrid retrieval with reranking.
        
        Args:
            query: Search query
            filter_dict: Optional metadata filters
            
        Returns:
            List of top-k documents after reranking
        """
        logger.info(f"Hybrid retrieval for query: '{query[:100]}...'")
        
        # Step 1: Dense retrieval (semantic search)
        dense_docs = await self._dense_retrieval(query, filter_dict)
        
        # Step 2: Sparse retrieval (BM25)
        sparse_docs = self._sparse_retrieval(query)
        
        # Step 3: Combine results with weighted scoring
        combined_docs = self._combine_results(dense_docs, sparse_docs)
        
        # Step 4: Apply token budget filtering
        budget_filtered_docs = self._filter_by_token_budget(combined_docs)
        
        # Step 5: Rerank top documents
        reranked_docs = await self._rerank_documents(query, budget_filtered_docs)
        
        logger.info(f"Retrieved {len(reranked_docs)} documents after hybrid search and reranking")
        return reranked_docs[:self.final_k]
    
    async def _dense_retrieval(
        self, 
        query: str, 
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Perform semantic search using vector store"""
        
        # If use_filtered_only is True, skip vector store search and use provided documents
        if self.use_filtered_only:
            logger.info(f"Using filtered documents only mode - returning {len(self.documents)} pre-filtered documents")
            # Return all provided documents (they're already filtered)
            # Limit to initial_k to maintain consistency
            return self.documents[:self.initial_k]
        
        # Original vector store search
        search_kwargs = {"k": self.initial_k}
        if filter_dict:
            search_kwargs["filter"] = filter_dict
        
        try:
            docs = await self.vector_store.asimilarity_search(query, **search_kwargs)
            logger.info(f"Dense retrieval returned {len(docs)} documents")
            return docs
        except Exception as e:
            logger.error(f"Error in dense retrieval: {e}")
            return []
    
    def _sparse_retrieval(self, query: str) -> List[Tuple[Document, float]]:
        """Perform keyword search using BM25"""
        # Preprocess query
        query_tokens = query.lower().split()
        query_tokens = [t for t in query_tokens if len(t) > 2]
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k documents
        top_indices = np.argsort(scores)[::-1][:self.initial_k]
        
        sparse_results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include documents with positive scores
                sparse_results.append((self.documents[idx], scores[idx]))
        
        logger.info(f"Sparse retrieval returned {len(sparse_results)} documents")
        return sparse_results
    
    def _combine_results(
        self, 
        dense_docs: List[Document], 
        sparse_docs: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """Combine dense and sparse results with weighted scoring"""
        doc_scores = {}
        
        # Process dense results
        for i, doc in enumerate(dense_docs):
            doc_id = self._get_doc_id(doc)
            # Normalize rank to score (inverse rank scoring)
            score = 1.0 / (i + 1)
            doc_scores[doc_id] = {
                'doc': doc,
                'dense_score': score * self.dense_weight,
                'sparse_score': 0,
                'combined_score': score * self.dense_weight
            }
        
        # Process sparse results
        if sparse_docs:
            max_sparse_score = max(score for _, score in sparse_docs)
            for doc, score in sparse_docs:
                doc_id = self._get_doc_id(doc)
                normalized_score = score / max_sparse_score if max_sparse_score > 0 else 0
                weighted_sparse_score = normalized_score * self.sparse_weight
                
                if doc_id in doc_scores:
                    doc_scores[doc_id]['sparse_score'] = weighted_sparse_score
                    doc_scores[doc_id]['combined_score'] += weighted_sparse_score
                else:
                    doc_scores[doc_id] = {
                        'doc': doc,
                        'dense_score': 0,
                        'sparse_score': weighted_sparse_score,
                        'combined_score': weighted_sparse_score
                    }
        
        # Convert to list and sort by combined score
        combined = [(info['doc'], info['combined_score']) for info in doc_scores.values()]
        combined.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Combined {len(combined)} unique documents from dense and sparse retrieval")
        return combined
    
    def _filter_by_token_budget(
        self, 
        doc_score_pairs: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """Filter documents to fit within token budget"""
        filtered = []
        total_tokens = 0
        
        for doc, score in doc_score_pairs:
            doc_tokens = self._count_tokens(doc.page_content)
            
            if total_tokens + doc_tokens <= self.token_budget:
                filtered.append((doc, score))
                total_tokens += doc_tokens
            else:
                # Stop adding documents if budget exceeded
                logger.info(f"Token budget reached at {total_tokens} tokens with {len(filtered)} documents")
                break
        
        return filtered[:self.max_rerank_docs]  # Limit documents for reranking
    
    async def _rerank_documents(
        self, 
        query: str, 
        doc_score_pairs: List[Tuple[Document, float]]
    ) -> List[Document]:
        """Rerank documents using cross-encoder"""
        if not doc_score_pairs:
            return []
        
        # Prepare pairs for reranking
        pairs = [[query, doc.page_content[:512]] for doc, _ in doc_score_pairs]  # Limit text for reranker
        
        try:
            # Get reranking scores
            rerank_scores = self.reranker.predict(pairs)
            
            # Combine with initial scores (80% reranker, 20% hybrid)
            final_scores = []
            for i, (doc, initial_score) in enumerate(doc_score_pairs):
                final_score = 0.8 * rerank_scores[i] + 0.2 * initial_score
                final_scores.append((doc, final_score))
            
            # Sort by final score
            final_scores.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"Reranked {len(final_scores)} documents")
            return [doc for doc, _ in final_scores]
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            # Fallback to hybrid scores only
            return [doc for doc, _ in doc_score_pairs]
    
    def _get_doc_id(self, doc: Document) -> str:
        """Generate unique ID for document"""
        # Use first 200 chars of content + metadata hash
        content_preview = doc.page_content[:200]
        metadata_str = str(sorted(doc.metadata.items()))
        return f"{hash(content_preview)}_{hash(metadata_str)}"
    
    def _count_tokens(self, text: str) -> int:
        """Simple token counting approximation (4 chars per token)"""
        # This is a rough approximation - can be replaced with tiktoken or similar
        return len(text) // 4