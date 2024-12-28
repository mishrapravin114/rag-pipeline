"""Enhanced search router with dual search and drug details."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

from database.database import get_db, FDAExtractionResults, SourceFiles, DrugSections
from api.services.enhanced_search_service import EnhancedSearchService
from api.services.simple_analytics_service import SimpleAnalyticsService
from api.routers.simple_auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["enhanced_search"])

# Pydantic models for requests
class DualSearchRequest(BaseModel):
    brand_name: Optional[str] = None
    therapeutic_area: Optional[str] = None
    collection_id: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None

class DrugDetailResponse(BaseModel):
    basic_info: Dict[str, Any]
    timeline: Dict[str, Any]
    sections: List[Dict[str, Any]]
    file_url: Optional[str]
    metadata: Optional[Dict[str, Any]]


@router.post("/dual")
async def dual_search(
    request: DualSearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dual search by brand name and therapeutic area, optionally filtered by collection."""
    try:
        results = EnhancedSearchService.dual_search(
            brand_name=request.brand_name,
            therapeutic_area=request.therapeutic_area,
            collection_id=request.collection_id,
            filters=request.filters,
            username=current_user["username"],
            db=db
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    search_type: str = Query(..., regex="^(brand|therapeutic)$"),
    db: Session = Depends(get_db)
):
    """Get search suggestions for autocomplete."""
    try:
        suggestions = EnhancedSearchService.get_search_suggestions(
            query, search_type, db
        )
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters")
async def get_advanced_filters(db: Session = Depends(get_db)):
    """Get available filter options for advanced search."""
    try:
        filters = EnhancedSearchService.get_advanced_filters(db)
        return filters
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drugs/{drug_id}/details", response_model=DrugDetailResponse)
async def get_drug_details(
    drug_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive drug details with sections."""
    try:
        from api.services.analytics_service import AnalyticsService
        
        # Get basic drug info
        drug = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == drug_id
        ).first()
        if not drug:
            raise HTTPException(status_code=404, detail="Drug not found")
        
        # Track drug view
        await AnalyticsService.track_drug_view(
            db=db,
            username=current_user.get("username"),
            drug_name=drug.drug_name,
            drug_id=drug_id
        )
        # Get structured sections
        sections = db.query(DrugSections).filter(
            DrugSections.source_file_id == drug.source_file_id
        ).order_by(DrugSections.section_order).all()
        # Get indication from DrugSections
        indication_section = next((s for s in sections if s.section_type == "indication"), None)
        # Get source file info
        source_file = db.query(SourceFiles).filter(
            SourceFiles.id == drug.source_file_id
        ).first()
        return {
            "basic_info": {
                "id": drug.id,
                "drug_name": drug.drug_name,
                "therapeutic_area": indication_section.section_content if indication_section else "Not specified",
                "approval_status": "Approved",  # Default since this field doesn't exist
                "country": "United States",  # Default since this field doesn't exist
                "applicant": drug.manufacturer or "Not specified",
                "active_substance": drug.active_ingredients or "Not specified",
                "regulatory": f"FDA {drug.submission_number}" if drug.submission_number else "FDA"
            },
            "timeline": {
                "submission_date": None,  # Field doesn't exist in current schema
                "pdufa_date": None,  # Field doesn't exist in current schema
                "approval_date": drug.approval_date
            },
            "sections": [
                {
                    "id": section.id,
                    "type": section.section_type,
                    "title": section.section_title or f"{section.section_type.replace('_', ' ').title()}",
                    "content": section.section_content or "No content available",
                    "order": section.section_order or 0
                } for section in sections
            ],
            "file_url": source_file.file_url if source_file else None,
            "metadata": drug.full_metadata or {}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/history")
async def get_user_search_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's search history."""
    try:
        history = SimpleAnalyticsService.get_user_search_history(
            current_user["username"], limit, db
        )
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/trending")
async def get_trending_searches(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get trending searches (simplified)."""
    try:
        trending = SimpleAnalyticsService.get_trending_searches(
            period, limit, db
        )
        return {"trending": trending}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/dashboard")
async def get_dashboard_data(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard data for user."""
    try:
        dashboard_data = SimpleAnalyticsService.get_dashboard_data(
            current_user["username"], db
        )
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_search_statistics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get search statistics for the current user."""
    try:
        stats = SimpleAnalyticsService.get_search_statistics(
            current_user["username"], db
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 