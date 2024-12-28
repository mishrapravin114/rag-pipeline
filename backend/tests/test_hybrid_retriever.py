import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from langchain.schema import Document
from src.utils.hybrid_retriever import HybridRetriever

class TestHybridRetriever:
    """Test cases for the HybridRetriever class"""
    
    @pytest.fixture
    def mock_documents(self):
        """Create mock documents for testing"""
        return [
            Document(
                page_content="Aspirin is used for pain relief and fever reduction.",
                metadata={"source": "doc1.pdf", "page": 1}
            ),
            Document(
                page_content="Common side effects of aspirin include stomach upset.",
                metadata={"source": "doc1.pdf", "page": 2}
            ),
            Document(
                page_content="Ibuprofen is an alternative pain reliever to aspirin.",
                metadata={"source": "doc2.pdf", "page": 1}
            ),
            Document(
                page_content="Pain relief medications should be taken with food.",
                metadata={"source": "doc3.pdf", "page": 1}
            ),
            Document(
                page_content="Aspirin dosage varies based on the condition being treated.",
                metadata={"source": "doc1.pdf", "page": 3}
            )
        ]
    
    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store"""
        mock = MagicMock()
        
        # Mock asimilarity_search to return documents
        async def mock_asimilarity_search(query, **kwargs):
            # Return different documents based on query
            if "aspirin" in query.lower():
                return [
                    Document(page_content="Aspirin is used for pain relief.", metadata={"source": "doc1.pdf"}),
                    Document(page_content="Aspirin side effects include stomach upset.", metadata={"source": "doc1.pdf"})
                ]
            else:
                return [
                    Document(page_content="General pain relief information.", metadata={"source": "doc3.pdf"})
                ]
        
        mock.asimilarity_search = mock_asimilarity_search
        return mock
    
    @pytest.fixture
    def hybrid_retriever(self, mock_vector_store, mock_documents):
        """Create HybridRetriever instance with mocks"""
        with patch('sentence_transformers.CrossEncoder') as mock_cross_encoder:
            # Mock the cross encoder
            mock_model = Mock()
            mock_model.predict.return_value = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
            mock_cross_encoder.return_value = mock_model
            
            retriever = HybridRetriever(
                vector_store=mock_vector_store,
                documents=mock_documents,
                dense_weight=0.7,
                sparse_weight=0.3,
                initial_k=5,
                final_k=3
            )
            return retriever
    
    def test_initialization(self, hybrid_retriever, mock_documents):
        """Test HybridRetriever initialization"""
        assert hybrid_retriever.documents == mock_documents
        assert hybrid_retriever.dense_weight == 0.7
        assert hybrid_retriever.sparse_weight == 0.3
        assert hybrid_retriever.initial_k == 5
        assert hybrid_retriever.final_k == 3
        assert hybrid_retriever.bm25 is not None
    
    def test_bm25_initialization(self, hybrid_retriever):
        """Test BM25 initialization with preprocessed documents"""
        assert len(hybrid_retriever.preprocessed_docs) == len(hybrid_retriever.documents)
        # Check that documents are tokenized
        for doc in hybrid_retriever.preprocessed_docs:
            assert isinstance(doc, list)
            assert all(isinstance(token, str) for token in doc)
            assert all(len(token) > 2 for token in doc)  # Short tokens removed
    
    @pytest.mark.asyncio
    async def test_dense_retrieval(self, hybrid_retriever):
        """Test dense retrieval using vector store"""
        query = "aspirin side effects"
        docs = await hybrid_retriever._dense_retrieval(query)
        
        assert len(docs) > 0
        assert all(isinstance(doc, Document) for doc in docs)
        # Should return aspirin-related documents
        assert any("aspirin" in doc.page_content.lower() for doc in docs)
    
    def test_sparse_retrieval(self, hybrid_retriever):
        """Test sparse retrieval using BM25"""
        query = "aspirin dosage"
        results = hybrid_retriever._sparse_retrieval(query)
        
        assert len(results) > 0
        assert all(isinstance(result[0], Document) for result in results)
        assert all(isinstance(result[1], float) for result in results)
        # Should return documents with high BM25 scores for aspirin
        top_doc = results[0][0]
        assert "aspirin" in top_doc.page_content.lower()
    
    def test_combine_results(self, hybrid_retriever, mock_documents):
        """Test combining dense and sparse results"""
        # Mock dense results
        dense_docs = mock_documents[:3]
        
        # Mock sparse results with scores
        sparse_docs = [
            (mock_documents[2], 5.0),  # High score
            (mock_documents[3], 3.0),  # Medium score
            (mock_documents[4], 1.0)   # Low score
        ]
        
        combined = hybrid_retriever._combine_results(dense_docs, sparse_docs)
        
        assert len(combined) > 0
        # Check that results are sorted by combined score
        scores = [score for _, score in combined]
        assert scores == sorted(scores, reverse=True)
        
        # Check that documents appearing in both get higher scores
        doc_ids = [hybrid_retriever._get_doc_id(doc) for doc, _ in combined]
        assert len(set(doc_ids)) == len(doc_ids)  # No duplicates
    
    def test_filter_by_token_budget(self, hybrid_retriever, mock_documents):
        """Test token budget filtering"""
        # Create doc-score pairs
        doc_score_pairs = [(doc, 0.9 - i*0.1) for i, doc in enumerate(mock_documents)]
        
        # Set a small token budget
        hybrid_retriever.token_budget = 200  # Very small budget
        
        filtered = hybrid_retriever._filter_by_token_budget(doc_score_pairs)
        
        assert len(filtered) < len(doc_score_pairs)
        assert len(filtered) <= hybrid_retriever.max_rerank_docs
        
        # Check total tokens don't exceed budget
        total_tokens = sum(
            hybrid_retriever.text_chunker.count_tokens(doc.page_content) 
            for doc, _ in filtered
        )
        assert total_tokens <= hybrid_retriever.token_budget
    
    @pytest.mark.asyncio
    async def test_rerank_documents(self, hybrid_retriever):
        """Test document reranking with cross-encoder"""
        query = "aspirin side effects"
        doc_score_pairs = [
            (Document(page_content="Aspirin causes stomach upset", metadata={}), 0.8),
            (Document(page_content="Pain relief options", metadata={}), 0.7),
            (Document(page_content="Aspirin dosage information", metadata={}), 0.6)
        ]
        
        reranked = await hybrid_retriever._rerank_documents(query, doc_score_pairs)
        
        assert len(reranked) == len(doc_score_pairs)
        assert all(isinstance(doc, Document) for doc in reranked)
        
        # Mock reranker should have been called
        hybrid_retriever.reranker.predict.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retrieve_full_pipeline(self, hybrid_retriever):
        """Test the full retrieval pipeline"""
        query = "What are the side effects of aspirin?"
        
        with patch.object(hybrid_retriever, '_sparse_retrieval') as mock_sparse:
            # Mock sparse retrieval results
            mock_sparse.return_value = [
                (Document(page_content="Aspirin side effects", metadata={}), 5.0),
                (Document(page_content="General side effects", metadata={}), 3.0)
            ]
            
            results = await hybrid_retriever.retrieve(query)
            
            assert len(results) <= hybrid_retriever.final_k
            assert all(isinstance(doc, Document) for doc in results)
            
            # Check that all steps were called
            mock_sparse.assert_called_once_with(query)
    
    def test_get_doc_id(self, hybrid_retriever):
        """Test document ID generation"""
        doc1 = Document(
            page_content="Test content",
            metadata={"source": "test.pdf", "page": 1}
        )
        doc2 = Document(
            page_content="Test content",
            metadata={"source": "test.pdf", "page": 2}
        )
        doc3 = Document(
            page_content="Different content",
            metadata={"source": "test.pdf", "page": 1}
        )
        
        id1 = hybrid_retriever._get_doc_id(doc1)
        id2 = hybrid_retriever._get_doc_id(doc2)
        id3 = hybrid_retriever._get_doc_id(doc3)
        
        # Same content but different metadata should have different IDs
        assert id1 != id2
        # Different content should have different IDs
        assert id1 != id3
        assert id2 != id3
    
    @pytest.mark.asyncio
    async def test_error_handling_dense_retrieval(self, hybrid_retriever):
        """Test error handling in dense retrieval"""
        # Make vector store raise an error
        hybrid_retriever.vector_store.asimilarity_search = Mock(
            side_effect=Exception("Vector store error")
        )
        
        docs = await hybrid_retriever._dense_retrieval("test query")
        
        # Should return empty list on error
        assert docs == []
    
    @pytest.mark.asyncio
    async def test_error_handling_reranking(self, hybrid_retriever):
        """Test error handling in reranking"""
        # Make reranker raise an error
        hybrid_retriever.reranker.predict = Mock(
            side_effect=Exception("Reranker error")
        )
        
        doc_score_pairs = [
            (Document(page_content="Test doc", metadata={}), 0.8)
        ]
        
        reranked = await hybrid_retriever._rerank_documents("test query", doc_score_pairs)
        
        # Should fallback to original order
        assert len(reranked) == 1
        assert reranked[0].page_content == "Test doc"