"""Simple entity details router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db_session, FDAExtractionResults, EntitySections, SourceFiles
from api.routers.simple_auth import get_current_user

router = APIRouter(prefix="/api/entities", tags=["entity_details"])

# Import JSON type
from sqlalchemy import JSON

def get_db():
    """Dependency to get database session."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/{entity_id}/details")
async def get_entity_details(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive entity details with sections."""
    try:
        # First try to find by FDAExtractionResults ID
        entity = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == entity_id
        ).first()
        
        # If not found, try to find by source_file_id
        if not entity:
            entity = db.query(FDAExtractionResults).filter(
                FDAExtractionResults.source_file_id == entity_id
            ).first()
        
        if not entity:
            # If still not found, create a minimal response from SourceFiles
            source_file = db.query(SourceFiles).filter(
                SourceFiles.id == entity_id
            ).first()
            
            if source_file:
                # Get sections directly using source_file_id
                sections = db.query(EntitySections).filter(
                    EntitySections.source_file_id == entity_id
                ).order_by(EntitySections.section_order).all()
                
                # Extract entity name from sections or filename
                entity_name = None
                if sections:
                    entity_name = sections[0].entity_name
                if not entity_name:
                    entity_name = source_file.file_name.replace(".pdf", "").replace("_", " ").upper()
                    if "lbl" in entity_name.lower():
                        entity_name = entity_name.split("LBL")[0].strip()
                
                # Get indication from sections
                indication_section = next((s for s in sections if s.section_type in ["indication", "indications"]), None)
                
                return {
                    "basic_info": {
                        "id": source_file.id,
                        "entity_name": entity_name,
                        "therapeutic_area": indication_section.section_content[:200] + "..." if indication_section and len(indication_section.section_content) > 200 else (indication_section.section_content if indication_section else "Not specified"),
                        "approval_status": "Approved",
                        "country": "United States",
                        "applicant": "Pharmaceutical Company",
                        "active_substance": "Not specified",
                        "regulatory": "FDA"
                    },
                    "timeline": {
                        "submission_date": None,
                        "pdufa_date": None,
                        "approval_date": source_file.created_at.strftime("%Y-%m-%d") if source_file.created_at else None
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
                    "file_url": source_file.file_url,
                    "metadata": {},
                    "page_info": {
                        "total_pages": 0,
                        "page_numbers": [],
                        "total_chunks": len(sections),
                        "total_tokens": 0
                    }
                }
            else:
                raise HTTPException(status_code=404, detail="Entity not found")
        
        # Get structured sections
        sections = db.query(EntitySections).filter(
            EntitySections.source_file_id == entity.source_file_id
        ).order_by(EntitySections.section_order).all()
        
        # Get indication from EntitySections
        indication_section = next((s for s in sections if s.section_type == "indication"), None)
        
        # Get source file info
        source_file = db.query(SourceFiles).filter(
            SourceFiles.id == entity.source_file_id
        ).first()
        
        return {
            "basic_info": {
                "id": entity.id,
                "entity_name": entity.entity_name,
                "therapeutic_area": indication_section.section_content if indication_section else "Not specified",
                "approval_status": "Approved",
                "country": "United States",
                "applicant": entity.manufacturer or "Not specified",
                "active_substance": entity.active_ingredients or "Not specified",
                "regulatory": f"FDA {entity.submission_number}" if entity.submission_number else "FDA"
            },
            "timeline": {
                "submission_date": None,
                "pdufa_date": None,
                "approval_date": entity.approval_date
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
            "metadata": entity.full_metadata or {}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 