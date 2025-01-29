"""Enhanced search service with dual search capabilities."""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, distinct, func
import time
import logging

# Import existing database models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from database.database import database_session, FDAExtractionResults, SourceFiles, EntitySections

logger = logging.getLogger(__name__)

class EnhancedSearchService:
    
    @staticmethod
    def dual_search(
        brand_name: str = None,
        therapeutic_area: str = None,
        collection_id: int = None,
        filters: dict = None,
        username: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Perform dual search by brand name and therapeutic area, optionally filtered by collection."""
        start_time = time.time()
        
        query = db.query(FDAExtractionResults)
        filter_conditions = []
        
        # Filter by collection if specified
        if collection_id:
            # Import Collection model
            from database.database import Collection, collection_document_association
            
            # Get source file IDs that belong to the collection
            collection_file_ids = db.query(collection_document_association.c.document_id).filter(
                collection_document_association.c.collection_id == collection_id
            ).subquery()
            
            # Filter results to only include documents in the collection
            query = query.filter(FDAExtractionResults.source_file_id.in_(collection_file_ids))
        
        # Brand name search
        if brand_name:
            filter_conditions.append(
                FDAExtractionResults.entity_name.ilike(f"%{brand_name}%")
            )
        
        # Therapeutic area search (use EntitySections for indication)
        if therapeutic_area:
            entity_ids = [s.source_file_id for s in db.query(EntitySections).filter(EntitySections.section_type == "indication", EntitySections.section_content.ilike(f"%{therapeutic_area}%")).all()]
            if entity_ids:
                filter_conditions.append(FDAExtractionResults.source_file_id.in_(entity_ids))
        
        # Apply additional filters
        if filters:
            if filters.get("manufacturer"):
                filter_conditions.append(
                    FDAExtractionResults.manufacturer.ilike(f"%{filters['manufacturer']}%")
                )
            # Skip approval_status filter since field doesn't exist
            if filters.get("document_type"):
                filter_conditions.append(
                    FDAExtractionResults.document_type == filters["document_type"]
                )
        
        # Execute search
        if filter_conditions:
            query = query.filter(and_(*filter_conditions))
        
        results = query.order_by(FDAExtractionResults.created_at.desc()).all()
        execution_time = int((time.time() - start_time) * 1000)
        
        # Save search history
        if username and db:
            search_query = f"Brand: {brand_name or 'Any'}, Therapeutic: {therapeutic_area or 'Any'}"
            EnhancedSearchService._save_search_history(
                username, search_query, "dual_search", filters, len(results), execution_time, db
            )
        
        # Format results
        formatted_results = []
        for result in results:
            # Get indication from EntitySections
            indication_section = db.query(EntitySections).filter(EntitySections.source_file_id == result.source_file_id, EntitySections.section_type == "indication").first()
            formatted_results.append({
                "id": result.id,
                "source_file_id": result.source_file_id,
                "entity_name": result.entity_name or "Unknown",
                "therapeutic_area": indication_section.section_content if indication_section else "Not specified",
                "manufacturer": result.manufacturer or "Unknown",
                "approval_status": "Approved",  # Default since field doesn't exist
                "approval_date": result.approval_date,
                "country": "United States",  # Default since field doesn't exist
                "active_ingredients": result.active_ingredients or [],
                "regulatory_info": f"FDA {result.submission_number}" if result.submission_number else "FDA",
                "document_type": result.document_type or "Unknown",
                "relevance_score": 1.0  # Default score, can be enhanced with ML
            })
        
        return {
            "results": formatted_results,
            "total_count": len(formatted_results),
            "execution_time_ms": execution_time,
            "search_criteria": {
                "brand_name": brand_name,
                "therapeutic_area": therapeutic_area,
                "collection_id": collection_id,
                "filters": filters
            }
        }
    
    @staticmethod
    def get_search_suggestions(query: str, search_type: str, db: Session) -> List[str]:
        """Get search suggestions for autocomplete."""
        if search_type == "brand":
            results = db.query(distinct(FDAExtractionResults.entity_name)).filter(
                FDAExtractionResults.entity_name.ilike(f"%{query}%")
            ).limit(10).all()
        elif search_type == "therapeutic":
            # Get therapeutic suggestions from EntitySections indication content
            from database.database import EntitySections
            results = db.query(distinct(EntitySections.section_content)).filter(
                EntitySections.section_type == "indication",
                EntitySections.section_content.ilike(f"%{query}%")
            ).limit(10).all()
        else:
            return []
        
        return [r[0] for r in results if r[0]]
    
    @staticmethod
    def _save_search_history(username: str, query: str, search_type: str, 
                           filters: dict, results_count: int, execution_time: int, db: Session):
        """Save search to history."""
        try:
            # Import SearchHistory here to avoid circular imports
            from database.database import SearchHistory
            
            search_record = SearchHistory(
                username=username,
                search_query=query,
                search_type=search_type,
                filters_applied=filters,
                results_count=results_count,
                execution_time_ms=execution_time
            )
            db.add(search_record)
            db.commit()
        except Exception as e:
            logger.error(f"Error saving search history: {e}")
            db.rollback()
    
    @staticmethod
    def get_advanced_filters(db: Session) -> Dict[str, List[str]]:
        """Get available filter options for advanced search."""
        try:
            # Get unique values for filter dropdowns
            manufacturers = db.query(distinct(FDAExtractionResults.manufacturer)).filter(
                FDAExtractionResults.manufacturer.isnot(None)
            ).all()
            
            document_types = db.query(distinct(FDAExtractionResults.document_type)).filter(
                FDAExtractionResults.document_type.isnot(None)
            ).all()
            
            approval_statuses = ["Approved", "Pending", "Withdrawn"]
            
            return {
                "manufacturers": ["ALL"] + [m[0] for m in manufacturers if m[0]],
                "document_types": ["ALL"] + [d[0] for d in document_types if d[0]],
                "approval_statuses": ["ALL"] + approval_statuses
            }
        except Exception as e:
            logger.error(f"Error getting filter options: {e}")
            return {
                "manufacturers": ["ALL"],
                "document_types": ["ALL"],
                "approval_statuses": ["ALL", "Approved"]
            } 