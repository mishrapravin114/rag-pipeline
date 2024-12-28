"""Analytics service for tracking user interactions."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from database.database import SearchHistory

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for tracking and analytics operations."""
    
    @staticmethod
    async def track_search(
        db: Session,
        username: Optional[str],
        search_query: str,
        search_type: str = "general",
        filters: Optional[Dict[str, Any]] = None,
        results_count: int = 0,
        session_id: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> SearchHistory:
        """
        Track a search operation in the database.
        
        Args:
            db: Database session
            username: Username performing the search
            search_query: The search query text
            search_type: Type of search (general, drug_specific, chat, view)
            filters: Any filters applied to the search
            results_count: Number of results returned
            session_id: Session identifier
            execution_time_ms: Time taken to execute the search
            
        Returns:
            SearchHistory record
        """
        try:
            search_record = SearchHistory(
                username=username,
                search_query=search_query,
                search_type=search_type,
                filters_applied=filters or {},
                results_count=results_count,
                search_timestamp=datetime.now(),
                session_id=session_id,
                execution_time_ms=execution_time_ms
            )
            
            db.add(search_record)
            db.commit()
            db.refresh(search_record)
            
            logger.info(f"Tracked search: {search_type} - {search_query}")
            return search_record
            
        except Exception as e:
            logger.error(f"Error tracking search: {e}")
            db.rollback()
            raise
    
    @staticmethod
    async def track_drug_view(
        db: Session,
        username: Optional[str],
        drug_name: str,
        drug_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> SearchHistory:
        """
        Track when a user views a drug document.
        
        Args:
            db: Database session
            username: Username viewing the drug
            drug_name: Name of the drug being viewed
            drug_id: ID of the drug if available
            session_id: Session identifier
            
        Returns:
            SearchHistory record
        """
        filters = {"drug_name": drug_name}
        if drug_id:
            filters["drug_id"] = drug_id
            
        return await AnalyticsService.track_search(
            db=db,
            username=username,
            search_query=drug_name,
            search_type="view",
            filters=filters,
            results_count=1,
            session_id=session_id
        )
    
    @staticmethod
    async def track_chat_interaction(
        db: Session,
        username: Optional[str],
        chat_query: str,
        drug_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> SearchHistory:
        """
        Track chat interactions.
        
        Args:
            db: Database session
            username: Username in the chat
            chat_query: The chat query/message
            drug_context: Drug context if chat is about a specific drug
            session_id: Session identifier
            
        Returns:
            SearchHistory record
        """
        filters = {}
        if drug_context:
            filters["drug_context"] = drug_context
            
        return await AnalyticsService.track_search(
            db=db,
            username=username,
            search_query=chat_query,
            search_type="chat",
            filters=filters,
            results_count=1,
            session_id=session_id
        )
    
    @staticmethod
    async def track_collection_search(
        db: Session,
        username: Optional[str],
        search_query: str,
        collection_id: int,
        collection_name: str,
        results_count: int = 0,
        session_id: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> SearchHistory:
        """
        Track searches within a collection.
        
        Args:
            db: Database session
            username: Username performing the search
            search_query: The search query text
            collection_id: ID of the collection being searched
            collection_name: Name of the collection
            results_count: Number of results returned
            session_id: Session identifier
            execution_time_ms: Time taken to execute the search
            
        Returns:
            SearchHistory record
        """
        filters = {
            "collection_id": collection_id,
            "collection_name": collection_name
        }
        
        return await AnalyticsService.track_search(
            db=db,
            username=username,
            search_query=search_query,
            search_type="collection_search",
            filters=filters,
            results_count=results_count,
            session_id=session_id,
            execution_time_ms=execution_time_ms
        )