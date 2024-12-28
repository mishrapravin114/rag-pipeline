"""Simple drug details router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db_session, FDAExtractionResults, DrugSections, SourceFiles
from api.routers.simple_auth import get_current_user

router = APIRouter(prefix="/api/drugs", tags=["drug_details"])

# Import JSON type
from sqlalchemy import JSON

def get_db():
    """Dependency to get database session."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/{drug_id}/details")
async def get_drug_details(
    drug_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive drug details with sections."""
    try:
        # First try to find by FDAExtractionResults ID
        drug = db.query(FDAExtractionResults).filter(
            FDAExtractionResults.id == drug_id
        ).first()
        
        # If not found, try to find by source_file_id
        if not drug:
            drug = db.query(FDAExtractionResults).filter(
                FDAExtractionResults.source_file_id == drug_id
            ).first()
        
        if not drug:
            # If still not found, create a minimal response from SourceFiles
            source_file = db.query(SourceFiles).filter(
                SourceFiles.id == drug_id
            ).first()
            
            if source_file:
                # Get sections directly using source_file_id
                sections = db.query(DrugSections).filter(
                    DrugSections.source_file_id == drug_id
                ).order_by(DrugSections.section_order).all()
                
                # Extract drug name from sections or filename
                drug_name = None
                if sections:
                    drug_name = sections[0].drug_name
                if not drug_name:
                    drug_name = source_file.file_name.replace(".pdf", "").replace("_", " ").upper()
                    if "lbl" in drug_name.lower():
                        drug_name = drug_name.split("LBL")[0].strip()
                
                # Get indication from sections
                indication_section = next((s for s in sections if s.section_type in ["indication", "indications"]), None)
                
                return {
                    "basic_info": {
                        "id": source_file.id,
                        "drug_name": drug_name,
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
                raise HTTPException(status_code=404, detail="Drug not found")
        
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
                "approval_status": "Approved",
                "country": "United States",
                "applicant": drug.manufacturer or "Not specified",
                "active_substance": drug.active_ingredients or "Not specified",
                "regulatory": f"FDA {drug.submission_number}" if drug.submission_number else "FDA"
            },
            "timeline": {
                "submission_date": None,
                "pdufa_date": None,
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