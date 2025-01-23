"""Test router for debugging entity details functionality."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db_session, FDAExtractionResults, EntitySections, SourceFiles

router = APIRouter(prefix="/api/test", tags=["test"])

def get_db():
    """Dependency to get database session."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/entity/{entity_id}")
async def test_entitie_details(entity_id: int, db: Session = Depends(get_db)):
    """Simple test for entity details."""
    try:
        # Get basic entity info
        entity = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == entity_id
        ).first()
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Get sections
        sections = db.query(EntitySections).filter(
            EntitySections.source_file_id == entity.source_file_id
        ).all()
        
        return {
            "entity_id": entity.id,
            "entity_name": entity.entity_name,
            "source_file_id": entity.source_file_id,
            "manufacturer": entity.manufacturer,
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