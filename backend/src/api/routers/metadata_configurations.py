"""
API endpoints for metadata configuration management within groups.
Phase 2: Configuration CRUD operations with group context.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging
import io

from database.database import get_db, MetadataConfiguration, MetadataGroup
from api.routers.auth import get_current_user
from api.services.metadata_configuration_service import MetadataConfigurationService
from api.services.metadata_excel_service import MetadataExcelService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/metadata-configurations",
    tags=["metadata-configurations"]
)

# Request/Response Models
class MetadataConfigurationBase(BaseModel):
    """Base model for metadata configuration"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    data_type: str = Field(..., pattern="^(text|number|date|boolean)$")
    extraction_prompt: str = Field(..., min_length=1)
    is_active: bool = True
    display_order: Optional[int] = 0
    validation_rules: Optional[Dict[str, Any]] = None
    default_value: Optional[Any] = None
    
class MetadataConfigurationCreate(MetadataConfigurationBase):
    """Model for creating a new configuration"""
    group_ids: List[int] = Field(..., min_items=1, description="Must belong to at least one group")

class MetadataConfigurationUpdate(BaseModel):
    """Model for updating a configuration"""
    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = Field(None, pattern="^(text|number|date|boolean)$")
    extraction_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None
    validation_rules: Optional[Dict[str, Any]] = None
    default_value: Optional[Any] = None

class MetadataConfigurationResponse(BaseModel):
    """Response model for metadata configuration"""
    id: int
    name: str
    description: Optional[str]
    data_type: str
    extraction_prompt: str
    extraction_prompt_version: int
    is_active: bool
    display_order: int
    validation_rules: Optional[Dict[str, Any]]
    default_value: Optional[Any]
    groups: List[Dict[str, Any]]
    group_count: int  # Added field for the number of groups
    created_at: datetime
    updated_at: datetime
    created_by: int
    
    class Config:
        from_attributes = True

class BulkOperationRequest(BaseModel):
    """Request model for bulk operations"""
    configuration_ids: List[int]
    action: str = Field(..., pattern="^(activate|deactivate|delete|move|copy)$")
    target_group_id: Optional[int] = None  # For move/copy operations

class BulkOperationResponse(BaseModel):
    """Response model for bulk operations"""
    success: bool
    total_items: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = []

class CloneConfigurationRequest(BaseModel):
    """Request model for cloning a configuration"""
    new_name: str
    target_group_ids: List[int] = Field(..., min_items=1)
    include_prompt: bool = True

# Endpoints

@router.get("/", response_model=List[MetadataConfigurationResponse])
async def list_configurations(
    group_id: Optional[int] = Query(None, description="Filter by group"),
    active_only: bool = Query(True, description="Show only active configurations"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List metadata configurations with optional filters.
    - Can filter by group, active status, data type
    - Supports search in name and description
    - Returns configurations with their group assignments
    """
    try:
        configs = MetadataConfigurationService.list_configurations(
            db=db,
            group_id=group_id,
            active_only=active_only,
            search=search,
            data_type=data_type,
            skip=skip,
            limit=limit
        )
        
        # Format response
        return [
            MetadataConfigurationResponse(
                **{
                    **config.__dict__,
                    "groups": [
                        {
                            "id": g.id,
                            "name": g.name,
                            "color": g.color
                        } for g in config.groups
                    ],
                    "group_count": len(config.groups)
                }
            ) for config in configs
        ]
        
    except Exception as e:
        logger.error(f"Error listing configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/", response_model=MetadataConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    config_data: MetadataConfigurationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new metadata configuration.
    - Must be assigned to at least one group
    - Extraction prompt version starts at 1
    - Created by the current user
    """
    try:
        # Validate group IDs exist
        for group_id in config_data.group_ids:
            group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group with id {group_id} not found"
                )
        
        # Create configuration
        new_config = MetadataConfigurationService.create_configuration(
            db=db,
            user_id=current_user.id,
            config_data=config_data.dict(exclude={"group_ids"}),
            group_ids=config_data.group_ids
        )
        
        # Format response
        return MetadataConfigurationResponse(
            **{
                **new_config.__dict__,
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "color": g.color
                    } for g in new_config.groups
                ],
                "group_count": len(new_config.groups)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{config_id}", response_model=MetadataConfigurationResponse)
async def get_configuration(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific metadata configuration by ID."""
    config = db.query(MetadataConfiguration).filter(
        MetadataConfiguration.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration with id {config_id} not found"
        )
    
    return MetadataConfigurationResponse(
        **{
            **config.__dict__,
            "groups": [
                {
                    "id": g.id,
                    "name": g.name,
                    "color": g.color
                } for g in config.groups
            ],
            "group_count": len(config.groups)
        }
    )

@router.put("/{config_id}", response_model=MetadataConfigurationResponse)
async def update_configuration(
    config_id: int,
    update_data: MetadataConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a metadata configuration.
    - Increments extraction_prompt_version if prompt changes
    - Updates the updated_at timestamp
    """
    try:
        updated_config = MetadataConfigurationService.update_configuration(
            db=db,
            config_id=config_id,
            update_data=update_data.dict(exclude_unset=True)
        )
        
        return MetadataConfigurationResponse(
            **{
                **updated_config.__dict__,
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "color": g.color
                    } for g in updated_config.groups
                ],
                "group_count": len(updated_config.groups)
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a metadata configuration.
    - Removes from all groups
    - Cascades to related extraction history
    """
    try:
        success = MetadataConfigurationService.delete_configuration(db, config_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration with id {config_id} not found"
            )
        
    except Exception as e:
        logger.error(f"Error deleting configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{config_id}/groups/{group_id}", response_model=Dict[str, Any])
async def add_configuration_to_group(
    config_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add a configuration to an additional group."""
    try:
        success = MetadataConfigurationService.add_to_group(
            db=db,
            config_id=config_id,
            group_id=group_id,
            user_id=current_user.id
        )
        
        if success:
            return {"success": True, "message": "Configuration added to group"}
        else:
            return {"success": False, "message": "Configuration already in group"}
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error adding configuration to group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{config_id}/groups/{group_id}", response_model=Dict[str, Any])
async def remove_configuration_from_group(
    config_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Remove a configuration from a group (if it has other groups)."""
    try:
        success = MetadataConfigurationService.remove_from_group(
            db=db,
            config_id=config_id,
            group_id=group_id
        )
        
        return {"success": True, "message": "Configuration removed from group"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error removing configuration from group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/bulk-operation", response_model=BulkOperationResponse)
async def bulk_operation(
    request: BulkOperationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Perform bulk operations on multiple configurations.
    - activate/deactivate: Change active status
    - delete: Remove configurations
    - move: Move to a different group
    - copy: Copy to additional group
    """
    try:
        result = MetadataConfigurationService.bulk_operation(
            db=db,
            config_ids=request.configuration_ids,
            action=request.action,
            target_group_id=request.target_group_id,
            user_id=current_user.id
        )
        
        return BulkOperationResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in bulk operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{config_id}/clone", response_model=MetadataConfigurationResponse)
async def clone_configuration(
    config_id: int,
    request: CloneConfigurationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Clone an existing configuration.
    - Creates a new configuration with a different name
    - Can optionally copy the extraction prompt
    - Assigns to specified groups
    """
    try:
        cloned_config = MetadataConfigurationService.clone_configuration(
            db=db,
            config_id=config_id,
            new_name=request.new_name,
            target_group_ids=request.target_group_ids,
            include_prompt=request.include_prompt,
            user_id=current_user.id
        )
        
        return MetadataConfigurationResponse(
            **{
                **cloned_config.__dict__,
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "color": g.color
                    } for g in cloned_config.groups
                ],
                "group_count": len(cloned_config.groups)
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error cloning configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{config_id}/reorder", response_model=Dict[str, Any])
async def reorder_configuration(
    config_id: int,
    new_order: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update the display order of a configuration.
    - Adjusts other configurations' order as needed
    """
    try:
        success = MetadataConfigurationService.reorder_configuration(
            db=db,
            config_id=config_id,
            new_order=new_order
        )
        
        return {"success": True, "message": f"Configuration moved to position {new_order}"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error reordering configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Multi-group assignment endpoints

class UpdateGroupAssignmentsRequest(BaseModel):
    """Request model for updating group assignments"""
    group_ids: List[int] = Field(..., min_items=1, description="Must belong to at least one group")

@router.put("/{config_id}/groups", response_model=Dict[str, Any])
async def update_group_assignments(
    config_id: int,
    request: UpdateGroupAssignmentsRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update all group assignments for a configuration.
    - Replaces all current group assignments
    - Ensures configuration belongs to at least one group
    """
    try:
        success = MetadataConfigurationService.update_group_assignments(
            db=db,
            config_id=config_id,
            new_group_ids=request.group_ids,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "message": f"Updated group assignments for configuration {config_id}",
            "group_count": len(request.group_ids)
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating group assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{config_id}/available-groups", response_model=List[Dict[str, Any]])
async def get_available_groups(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get list of groups that a configuration can be added to.
    - Returns groups the configuration is NOT already in
    """
    try:
        available_groups = MetadataConfigurationService.get_available_groups(
            db=db,
            config_id=config_id
        )
        
        return [
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "color": group.color,
                "configuration_count": len(group.configurations)
            }
            for group in available_groups
        ]
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting available groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Import/Export endpoints

class ImportResponse(BaseModel):
    """Response model for import operation"""
    success: bool
    imported: int
    skipped: int
    errors: List[str]
    created_groups: List[str]
    details: List[Dict[str, Any]]

@router.get("/template/download", response_class=StreamingResponse)
async def download_template(
    current_user = Depends(get_current_user)
):
    """
    Download Excel template for importing metadata configurations.
    - Includes sample data and instructions
    - Shows all required and optional fields
    """
    try:
        template_bytes = MetadataExcelService.generate_template()
        
        return StreamingResponse(
            io.BytesIO(template_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=metadata_configurations_template_{datetime.now().strftime('%Y%m%d')}.xlsx"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/import", response_model=ImportResponse)
async def import_configurations(
    file: UploadFile = File(..., description="Excel file with configurations"),
    skip_duplicates: bool = Query(True, description="Skip existing configurations"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Import metadata configurations from Excel file.
    - Validates all data before importing
    - Creates groups if they don't exist
    - Can update existing configurations if skip_duplicates=false
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an Excel file (.xlsx or .xls)"
            )
        
        # Read file content
        content = await file.read()
        
        # Import configurations
        result = MetadataExcelService.import_configurations(
            db=db,
            file_content=content,
            user_id=current_user.id,
            skip_duplicates=skip_duplicates
        )
        
        if not result['success'] and result['errors']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(result['errors'])
            )
        
        return ImportResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/export", response_class=StreamingResponse)
async def export_configurations(
    group_ids: Optional[str] = Query(None, description="Comma-separated group IDs to filter"),
    active_only: bool = Query(True, description="Export only active configurations"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Export metadata configurations to Excel.
    - Can filter by groups
    - Can filter by active status
    - Includes all configuration details
    """
    try:
        # Parse group IDs
        group_id_list = None
        if group_ids:
            try:
                group_id_list = [int(id.strip()) for id in group_ids.split(',')]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid group IDs format"
                )
        
        # Export configurations
        export_bytes = MetadataExcelService.export_configurations(
            db=db,
            group_ids=group_id_list,
            active_only=active_only
        )
        
        filename = f"metadata_configurations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(export_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
