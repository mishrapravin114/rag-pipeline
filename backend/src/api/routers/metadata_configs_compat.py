"""
Compatibility router for legacy metadata configs endpoints.
Maps old frontend endpoints to new metadata configurations endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

from database.database import get_db, MetadataConfiguration, MetadataGroup
from api.routers.auth import get_current_user
from api.services.metadata_configuration_service import MetadataConfigurationService
from api.services.metadata_excel_service import MetadataExcelService

logger = logging.getLogger(__name__)

# Create compatibility router with old path
router = APIRouter(
    prefix="/api/metadata-configs",
    tags=["metadata-configs-compat"]
)

# Request/Response models for compatibility
class MetadataConfigCompat(BaseModel):
    """Compatibility model for metadata configuration"""
    id: Optional[int] = None
    metadata_name: str
    description: Optional[str] = None
    extraction_prompt: str
    data_type: str = Field(..., pattern="^(text|number|date|boolean)$")
    validation_rules: Optional[Any] = None
    is_active: bool = True
    display_order: Optional[int] = 0
    group_count: Optional[int] = 0  # Added field for compatibility
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None
    created_by: Optional[int] = None

class CreateMetadataConfigRequest(BaseModel):
    """Request model for creating configuration (compat)"""
    metadata_name: str
    description: Optional[str] = None
    extraction_prompt: str
    data_type: str = Field(..., pattern="^(text|number|date|boolean)$")
    validation_rules: Optional[Any] = None
    is_active: bool = True

class UpdateMetadataConfigRequest(BaseModel):
    """Request model for updating configuration (compat) - all fields optional"""
    metadata_name: Optional[str] = None
    description: Optional[str] = None
    extraction_prompt: Optional[str] = None
    data_type: Optional[str] = Field(None, pattern="^(text|number|date|boolean)$")
    validation_rules: Optional[Any] = None
    is_active: Optional[bool] = None

# Compatibility endpoints

@router.get("", response_model=List[MetadataConfigCompat])
async def list_metadata_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List metadata configurations (compatibility endpoint)"""
    try:
        configs = db.query(MetadataConfiguration)\
            .order_by(MetadataConfiguration.metadata_name)\
            .offset(skip)\
            .limit(limit)\
            .all()
        
        # Convert to compatibility format
        return [
            MetadataConfigCompat(
                id=config.id,
                metadata_name=config.metadata_name,
                description=config.description,
                extraction_prompt=config.extraction_prompt,
                data_type=config.data_type,
                validation_rules=config.validation_rules,
                is_active=config.is_active,
                display_order=0,  # Compatibility - return 0 since we don't have global display_order anymore
                group_count=len(config.groups),  # Include actual group count
                created_at=config.created_at,
                updated_at=config.updated_at,
                created_by=config.created_by
            )
            for config in configs
        ]
    except Exception as e:
        logger.error(f"Error listing metadata configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("", response_model=MetadataConfigCompat)
async def create_metadata_config(
    config_data: CreateMetadataConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create metadata configuration (compatibility endpoint)"""
    try:
        # Get default group
        default_group = db.query(MetadataGroup).filter(
            MetadataGroup.is_default == True
        ).first()
        
        if not default_group:
            # Create default group if it doesn't exist
            default_group = MetadataGroup(
                name="General",
                description="Default group for uncategorized metadata configurations",
                color="#6B7280",
                is_default=True,
                created_by=current_user.id
            )
            db.add(default_group)
            db.flush()
        
        # Create configuration
        new_config = MetadataConfigurationService.create_configuration(
            db=db,
            user_id=current_user.id,
            config_data={
                'metadata_name': config_data.metadata_name,
                'description': config_data.description,
                'extraction_prompt': config_data.extraction_prompt,
                'data_type': config_data.data_type,
                'validation_rules': config_data.validation_rules,
                'is_active': config_data.is_active,
                # display_order is now per-group, not global
            },
            group_ids=[default_group.id]
        )
        
        return MetadataConfigCompat(
            id=new_config.id,
            metadata_name=new_config.metadata_name,
            description=new_config.description,
            extraction_prompt=new_config.extraction_prompt,
            data_type=new_config.data_type,
            validation_rules=new_config.validation_rules,
            is_active=new_config.is_active,
            display_order=0,  # Compatibility - return 0
            group_count=len(new_config.groups),  # Include actual group count
            created_at=new_config.created_at,
            updated_at=new_config.updated_at,
            created_by=new_config.created_by
        )
    except Exception as e:
        logger.error(f"Error creating metadata config: {e}")
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A metadata configuration with this name already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{config_id}", response_model=MetadataConfigCompat)
async def update_metadata_config(
    config_id: int,
    config_data: UpdateMetadataConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update metadata configuration (compatibility endpoint)"""
    try:
        # Build update data dict with only provided fields
        update_data = {}
        if config_data.metadata_name is not None:
            update_data['metadata_name'] = config_data.metadata_name
        if config_data.description is not None:
            update_data['description'] = config_data.description
        if config_data.extraction_prompt is not None:
            update_data['extraction_prompt'] = config_data.extraction_prompt
        if config_data.data_type is not None:
            update_data['data_type'] = config_data.data_type
        if config_data.validation_rules is not None:
            update_data['validation_rules'] = config_data.validation_rules
        if config_data.is_active is not None:
            update_data['is_active'] = config_data.is_active
        
        updated_config = MetadataConfigurationService.update_configuration(
            db=db,
            config_id=config_id,
            update_data=update_data
        )
        
        return MetadataConfigCompat(
            id=updated_config.id,
            metadata_name=updated_config.metadata_name,
            description=updated_config.description,
            extraction_prompt=updated_config.extraction_prompt,
            data_type=updated_config.data_type,
            validation_rules=updated_config.validation_rules,
            is_active=updated_config.is_active,
            display_order=0,  # Compatibility - return 0
            group_count=len(updated_config.groups),  # Include actual group count
            created_at=updated_config.created_at,
            updated_at=updated_config.updated_at,
            created_by=updated_config.created_by
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating metadata config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{config_id}")
async def delete_metadata_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete metadata configuration (compatibility endpoint)"""
    try:
        success = MetadataConfigurationService.delete_configuration(db, config_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata configuration with id {config_id} not found"
            )
        return {"message": "Metadata configuration deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting metadata config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Group items compatibility endpoints removed - handled by metadata_groups router

# Export/Import compatibility
@router.get("/export")
async def export_configs_compat(
    group_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export configurations (compatibility)"""
    from api.routers.metadata_configurations import export_configurations
    group_ids = str(group_id) if group_id else None
    return await export_configurations(
        group_ids=group_ids,
        active_only=True,
        db=db,
        current_user=current_user
    )