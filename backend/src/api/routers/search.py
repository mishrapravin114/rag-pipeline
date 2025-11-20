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
    drug_name: Optional[str] = None


@router.post("")
async def search_documents(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search FDA documents by drug name with SQL first, then vector search fallback."""
    try:
        # Perform search with user_id for history tracking
        result = await FDAChatManagementService.search_fda_documents(
            search_query=request.query,
            user_id=current_user.id,
            drug_name=request.drug_name,
            db=db
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drug-names")
async def get_unique_drug_names(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all unique drug names from SourceFiles for filter dropdown."""
    try:
        drug_names = FDAChatManagementService.get_unique_drug_names(db)
        return {
            "success": True,
            "drug_names": drug_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))