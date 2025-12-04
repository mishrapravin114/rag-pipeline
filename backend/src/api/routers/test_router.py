"""Test router for debugging drug details functionality."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db_session, FDAExtractionResults, DrugSections, SourceFiles

router = APIRouter(prefix="/api/test", tags=["test"])

def get_db():
    """Dependency to get database session."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/drug/{drug_id}")
async def test_drug_details(drug_id: int, db: Session = Depends(get_db)):
    """Simple test for drug details."""
    try:
        # Get basic drug info
        drug = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == drug_id
        ).first()
        
        if not drug:
            raise HTTPException(status_code=404, detail="Drug not found")
        
        # Get sections
        sections = db.query(DrugSections).filter(
            DrugSections.source_file_id == drug.source_file_id
        ).all()
        
        return {
            "drug_id": drug.id,
            "drug_name": drug.drug_name,
            "source_file_id": drug.source_file_id,
            "manufacturer": drug.manufacturer,
            "sections_count": len(sections),
            "sections": [
                {
                    "id": s.id,
                    "type": s.section_type,
                    "title": s.section_title,
                    "content": s.section_content[:100] + "..." if s.section_content else None
                } for s in sections
            ]
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@router.get("/health")
async def test_health():
    """Simple health check."""
    return {"status": "ok", "message": "Test router is working"} 