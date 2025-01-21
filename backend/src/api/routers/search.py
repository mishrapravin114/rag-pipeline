from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from database.database import get_db
from api.services.chat_management_service import FDAChatManagementService
from api.routers.auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])

# Pydantic models for request/response
class SearchRequest(BaseModel):
    query: str
    entity_name: Optional[str] = None


@router.post("")
async def search_documents(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search FDA documents by entity name with SQL first, then vector search fallback."""
    try:
        # Perform search with user_id for history tracking
        result = await FDAChatManagementService.search_fda_documents(
            search_query=request.query,
            user_id=current_user.id,
            entity_name=request.entity_name,
            db=db
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entity-names")
async def get_unique_entitie_names(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all unique entity names from SourceFiles for filter dropdown."""
    try:
        entity_names = FDAChatManagementService.get_unique_entitie_names(db)
        return {
            "success": True,
            "entity_names": entity_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))