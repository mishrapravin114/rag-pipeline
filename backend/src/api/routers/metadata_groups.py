"""
Metadata Groups API Router - Handles CRUD operations for metadata groups
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, func, or_, and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import json

from database.database import get_db, MetadataGroup, MetadataConfiguration
from api.routers.auth import get_current_user
from api.services.metadata_group_service import MetadataGroupService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/metadata-groups",
    tags=["metadata-groups"]
)

# Pydantic models
class MetadataConfigurationResponse(BaseModel):
    id: int
    metadata_name: str
    description: Optional[str] = None
    extraction_prompt: str
    extraction_prompt_version: int
    data_type: str
    validation_rules: Optional[str] = None
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    class Config:
        from_attributes = True

class MetadataGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = '#3B82F6'
    tags: Optional[List[str]] = None

class MetadataGroupCreate(MetadataGroupBase):
    pass

class MetadataGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    tags: Optional[List[str]] = None

class MetadataGroupResponse(MetadataGroupBase):
    id: int
    is_default: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    configuration_count: int
    configurations: List[MetadataConfigurationResponse] = []

    class Config:
        from_attributes = True

class PaginatedMetadataGroupResponse(BaseModel):
    groups: List[MetadataGroupResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

# Models for configuration assignment
class ConfigurationAssignment(BaseModel):
    config_ids: List[int]

class GroupAssignment(BaseModel):
    group_ids: List[int]

# Helper functions
def get_group(db: Session, group_id: int):
    """Get a metadata group by ID with existence check"""
    from database.database import MetadataGroup
    group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata group not found")
    return group

def check_group_is_default(db: Session, group_id: int) -> bool:
    """Check if a group is the default group"""
    from database.database import MetadataGroup
    group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
    return group and group.is_default

def ensure_default_group_exists(db: Session, user_id: int) -> None:
    """Ensure the default 'General' group exists"""
    MetadataGroupService.ensure_default_group(db, user_id)

@router.get("", response_model=PaginatedMetadataGroupResponse)
async def list_metadata_groups(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for name or description"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all metadata groups with pagination"""
    from database.database import MetadataGroup
    from sqlalchemy import or_
    
    # Ensure default group exists
    ensure_default_group_exists(db, current_user.id)
    
    # Build base query
    query = db.query(MetadataGroup)
    
    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                MetadataGroup.name.ilike(search_term),
                MetadataGroup.description.ilike(search_term)
            )
        )
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    skip = (page - 1) * per_page
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    # Order by is_default (default group first), then by updated_at
    groups = query.order_by(
        MetadataGroup.is_default.desc(),
        MetadataGroup.updated_at.desc()
    ).offset(skip).limit(per_page).all()
    
    # Build response
    response_groups = []
    for group in groups:
        # Load configurations with group-specific display_order
        from database.database import metadata_group_configs
        
        configs_with_order = db.query(
            MetadataConfiguration,
            metadata_group_configs.c.display_order
        ).join(
            metadata_group_configs,
            metadata_group_configs.c.config_id == MetadataConfiguration.id
        ).filter(
            metadata_group_configs.c.group_id == group.id,
            MetadataConfiguration.is_active == True
        ).order_by(
            metadata_group_configs.c.display_order,
            MetadataConfiguration.id
        ).all()
        
        configurations = [
            MetadataConfigurationResponse(
                id=config.id,
                metadata_name=config.metadata_name,
                description=config.description,
                extraction_prompt=config.extraction_prompt,
                extraction_prompt_version=config.extraction_prompt_version,
                data_type=config.data_type,
                validation_rules=config.validation_rules,
                is_active=config.is_active,
                display_order=display_order,
                created_at=config.created_at,
                updated_at=config.updated_at,
                created_by=config.created_by
            )
            for config, display_order in configs_with_order
        ]
        
        response_groups.append(
            MetadataGroupResponse(
                id=group.id,
                name=group.name,
                description=group.description,
                color=group.color,
                tags=group.tags or [],
                is_default=group.is_default,
                created_at=group.created_at,
                updated_at=group.updated_at,
                created_by=group.created_by,
                configuration_count=len(configurations),
                configurations=configurations
            )
        )
    
    return PaginatedMetadataGroupResponse(
        groups=response_groups,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.post("", response_model=MetadataGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_metadata_group(
    group: MetadataGroupCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new metadata group"""
    from database.database import MetadataGroup
    
    # Check if group name already exists
    existing = db.query(MetadataGroup).filter(
        func.lower(MetadataGroup.name) == func.lower(group.name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A metadata group with this name already exists"
        )
    
    # Create new group
    new_group = MetadataGroup(
        name=group.name,
        description=group.description,
        color=group.color or '#3B82F6',
        tags=group.tags,
        is_default=False,
        created_by=current_user.id
    )
    
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    return MetadataGroupResponse(
        id=new_group.id,
        name=new_group.name,
        description=new_group.description,
        color=new_group.color,
        tags=new_group.tags or [],
        is_default=new_group.is_default,
        created_at=new_group.created_at,
        updated_at=new_group.updated_at,
        created_by=new_group.created_by,
        configuration_count=0,
        configurations=[]
    )

@router.get("/{group_id}", response_model=MetadataGroupResponse)
async def get_metadata_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific metadata group with its configurations"""
    group = get_group(db, group_id)
    
    # Get configurations with group-specific display_order from the association table
    from database.database import metadata_group_configs
    
    # Query to get configurations with their group-specific display_order
    configs_with_order = db.query(
        MetadataConfiguration,
        metadata_group_configs.c.display_order
    ).join(
        metadata_group_configs,
        metadata_group_configs.c.config_id == MetadataConfiguration.id
    ).filter(
        metadata_group_configs.c.group_id == group_id
    ).order_by(
        metadata_group_configs.c.display_order,
        MetadataConfiguration.id
    ).all()
    
    configurations = [
        MetadataConfigurationResponse(
            id=config.id,
            metadata_name=config.metadata_name,
            description=config.description,
            extraction_prompt=config.extraction_prompt,
            extraction_prompt_version=config.extraction_prompt_version,
            data_type=config.data_type,
            validation_rules=config.validation_rules,
            is_active=config.is_active,
            display_order=display_order,  # Use group-specific display_order
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by
        )
        for config, display_order in configs_with_order
    ]
    
    return MetadataGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        tags=group.tags or [],
        is_default=group.is_default,
        created_at=group.created_at,
        updated_at=group.updated_at,
        created_by=group.created_by,
        configuration_count=len(configurations),
        configurations=configurations
    )

@router.put("/{group_id}", response_model=MetadataGroupResponse)
async def update_metadata_group(
    group_id: int,
    group_update: MetadataGroupUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a metadata group"""
    from database.database import MetadataGroup
    
    group = get_group(db, group_id)
    
    # Prevent updating default group's name
    if group.is_default and group_update.name and group_update.name != group.name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot rename the default group"
        )
    
    # Check if new name conflicts with existing group
    if group_update.name and group_update.name != group.name:
        existing = db.query(MetadataGroup).filter(
            MetadataGroup.id != group_id,
            func.lower(MetadataGroup.name) == func.lower(group_update.name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A metadata group with this name already exists"
            )
    
    # Update fields
    if group_update.name is not None:
        group.name = group_update.name
    if group_update.description is not None:
        group.description = group_update.description
    if group_update.color is not None:
        group.color = group_update.color
    if group_update.tags is not None:
        group.tags = group_update.tags
    
    group.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(group)
    
    # Get configurations with group-specific display_order
    from database.database import metadata_group_configs
    
    configs_with_order = db.query(
        MetadataConfiguration,
        metadata_group_configs.c.display_order
    ).join(
        metadata_group_configs,
        metadata_group_configs.c.config_id == MetadataConfiguration.id
    ).filter(
        metadata_group_configs.c.group_id == group.id,
        MetadataConfiguration.is_active == True
    ).order_by(
        metadata_group_configs.c.display_order,
        MetadataConfiguration.id
    ).all()
    
    configurations = [
        MetadataConfigurationResponse(
            id=config.id,
            metadata_name=config.metadata_name,
            description=config.description,
            extraction_prompt=config.extraction_prompt,
            extraction_prompt_version=config.extraction_prompt_version,
            data_type=config.data_type,
            validation_rules=config.validation_rules,
            is_active=config.is_active,
            display_order=display_order,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by
        )
        for config, display_order in configs_with_order
    ]
    
    return MetadataGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        tags=group.tags or [],
        is_default=group.is_default,
        created_at=group.created_at,
        updated_at=group.updated_at,
        created_by=group.created_by,
        configuration_count=len(configurations),
        configurations=configurations
    )

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metadata_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a metadata group"""
    from database.database import MetadataGroup, MetadataConfiguration
    
    group = get_group(db, group_id)
    
    # Prevent deletion of default group
    if group.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete the default group"
        )
    
    # Check if there are configurations only in this group
    orphaned_configs = []
    for config in group.configurations:
        if len(config.groups) == 1:  # Only in this group
            orphaned_configs.append(config)
    
    if orphaned_configs:
        # Move orphaned configurations to default group
        default_group = db.query(MetadataGroup).filter(
            MetadataGroup.is_default == True
        ).first()
        
        if not default_group:
            # Create default group if it doesn't exist
            ensure_default_group_exists(db, current_user.id)
            default_group = db.query(MetadataGroup).filter(
                MetadataGroup.is_default == True
            ).first()
        
        # Move orphaned configurations to default group
        for config in orphaned_configs:
            default_group.configurations.append(config)
    
    # Delete the group (cascade will handle the junction table entries)
    db.delete(group)
    db.commit()
    
    logger.info(f"Deleted metadata group {group_id}, moved {len(orphaned_configs)} orphaned configurations to default group")
    return

# Compatibility endpoint for legacy frontend
from pydantic import BaseModel
from typing import Optional

class AddItemRequest(BaseModel):
    metadata_config_id: Optional[int] = None

@router.post("/{group_id}/items")
async def add_item_to_group(
    group_id: int,
    metadata_config_id: Optional[int] = Query(None),
    request: Optional[AddItemRequest] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add a single metadata configuration to a group (legacy compatibility)"""
    from database.database import MetadataConfiguration
    
    # Get config_id from either query param or request body
    config_id = metadata_config_id
    if config_id is None and request and request.metadata_config_id:
        config_id = request.metadata_config_id
    
    if config_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="metadata_config_id is required either as query parameter or in request body"
        )
    
    # Check if group exists
    group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with id {group_id} not found"
        )
    
    # Check if configuration exists
    config = db.query(MetadataConfiguration).filter(
        MetadataConfiguration.id == config_id
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata configuration with id {config_id} not found"
        )
    
    # Add to group if not already present
    if config not in group.configurations:
        group.configurations.append(config)
        db.commit()
    
    return {"message": "Configuration added to group successfully"}

@router.post("/{group_id}/configurations", response_model=List[MetadataConfigurationResponse])
async def add_configurations_to_group(
    group_id: int,
    assignment: ConfigurationAssignment,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add multiple metadata configurations to a group"""
    from database.database import MetadataConfiguration
    
    group = get_group(db, group_id)
    
    # Validate all configuration IDs exist
    configs = db.query(MetadataConfiguration).filter(
        MetadataConfiguration.id.in_(assignment.config_ids)
    ).all()
    
    if len(configs) != len(assignment.config_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more metadata configurations not found"
        )
    
    # Add configurations to group (skip if already present)
    added_configs = []
    for config in configs:
        if config not in group.configurations:
            group.configurations.append(config)
            added_configs.append(config)
    
    db.commit()
    
    # Return the added configurations
    return [
        MetadataConfigurationResponse(
            id=config.id,
            metadata_name=config.metadata_name,
            description=config.description,
            extraction_prompt=config.extraction_prompt,
            extraction_prompt_version=config.extraction_prompt_version,
            data_type=config.data_type,
            validation_rules=config.validation_rules,
            is_active=config.is_active,
            display_order=config.display_order,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by
        )
        for config in added_configs
    ]

@router.delete("/{group_id}/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_configuration_from_group(
    group_id: int,
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Remove a metadata configuration from a group"""
    from database.database import MetadataConfiguration, MetadataGroup
    
    group = get_group(db, group_id)
    
    # Find the configuration
    config = db.query(MetadataConfiguration).filter(
        MetadataConfiguration.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata configuration not found"
        )
    
    # Check if configuration is in this group
    if config not in group.configurations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found in this group"
        )
    
    # Check if this is the only group for this configuration
    if len(config.groups) == 1:
        # Move to default group instead of orphaning
        default_group = db.query(MetadataGroup).filter(
            MetadataGroup.is_default == True
        ).first()
        
        if not default_group or default_group.id == group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove configuration as it would be orphaned. Move it to another group first."
            )
        
        # Add to default group before removing
        default_group.configurations.append(config)
    
    # Remove from current group
    group.configurations.remove(config)
    db.commit()
    
    return

@router.post("/{config_id}/groups", response_model=List[MetadataGroupResponse])
async def assign_configuration_to_groups(
    config_id: int,
    assignment: GroupAssignment,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign a metadata configuration to multiple groups"""
    from database.database import MetadataConfiguration, MetadataGroup
    
    # Get the configuration
    config = db.query(MetadataConfiguration).filter(
        MetadataConfiguration.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata configuration not found"
        )
    
    # Validate all group IDs exist
    groups = db.query(MetadataGroup).filter(
        MetadataGroup.id.in_(assignment.group_ids)
    ).all()
    
    if len(groups) != len(assignment.group_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more groups not found"
        )
    
    # Clear existing group assignments
    config.groups = []
    
    # Add to specified groups
    config.groups = groups
    
    db.commit()
    
    # Return the groups this configuration is now part of
    response_groups = []
    for group in groups:
        configurations = [
            MetadataConfigurationResponse(
                id=c.id,
                metadata_name=c.metadata_name,
                description=c.description,
                extraction_prompt=c.extraction_prompt,
                extraction_prompt_version=c.extraction_prompt_version,
                data_type=c.data_type,
                validation_rules=c.validation_rules,
                is_active=c.is_active,
                display_order=c.display_order,
                created_at=c.created_at,
                updated_at=c.updated_at,
                created_by=c.created_by
            )
            for c in group.configurations if c.is_active
        ]
        
        response_groups.append(
            MetadataGroupResponse(
                id=group.id,
                name=group.name,
                description=group.description,
                color=group.color,
                tags=group.tags or [],
                is_default=group.is_default,
                created_at=group.created_at,
                updated_at=group.updated_at,
                created_by=group.created_by,
                configuration_count=len(configurations),
                configurations=configurations
            )
        )
    
    return response_groups

@router.get("/configurations/orphaned", response_model=List[MetadataConfigurationResponse])
async def get_orphaned_configurations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get metadata configurations that are not assigned to any group"""
    from database.database import MetadataConfiguration
    
    # Find configurations with no groups
    orphaned = db.query(MetadataConfiguration).filter(
        ~MetadataConfiguration.groups.any()
    ).all()
    
    return [
        MetadataConfigurationResponse(
            id=config.id,
            metadata_name=config.metadata_name,
            description=config.description,
            extraction_prompt=config.extraction_prompt,
            extraction_prompt_version=config.extraction_prompt_version,
            data_type=config.data_type,
            validation_rules=config.validation_rules,
            is_active=config.is_active,
            display_order=config.display_order,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by
        )
        for config in orphaned
    ]

@router.post("/assign-orphaned-to-default", status_code=status.HTTP_200_OK)
async def assign_orphaned_to_default(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign all orphaned configurations to the default group"""
    count = MetadataGroupService.assign_orphaned_configurations(db, current_user.id)
    
    return {
        "message": f"Assigned {count} orphaned configurations to the default group",
        "assigned_count": count
    }

@router.get("/statistics")
async def get_metadata_group_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get statistics about metadata groups and configurations"""
    stats = MetadataGroupService.get_group_statistics(db)
    return stats

@router.post("/{group_id}/clone", response_model=MetadataGroupResponse)
async def clone_metadata_group(
    group_id: int,
    new_name: str = Query(..., description="Name for the cloned group"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Clone a metadata group with all its configurations"""
    try:
        # Check if name is already taken
        if not MetadataGroupService.validate_group_name(db, new_name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A metadata group with this name already exists"
            )
        
        cloned_group = MetadataGroupService.clone_group(
            db, group_id, new_name, current_user.id
        )
        
        configurations = [
            MetadataConfigurationResponse(
                id=config.id,
                metadata_name=config.metadata_name,
                description=config.description,
                extraction_prompt=config.extraction_prompt,
                extraction_prompt_version=config.extraction_prompt_version,
                data_type=config.data_type,
                validation_rules=config.validation_rules,
                is_active=config.is_active,
                display_order=config.display_order,
                created_at=config.created_at,
                updated_at=config.updated_at,
                created_by=config.created_by
            )
            for config in cloned_group.configurations if config.is_active
        ]
        
        return MetadataGroupResponse(
            id=cloned_group.id,
            name=cloned_group.name,
            description=cloned_group.description,
            color=cloned_group.color,
            tags=cloned_group.tags or [],
            is_default=cloned_group.is_default,
            created_at=cloned_group.created_at,
            updated_at=cloned_group.updated_at,
            created_by=cloned_group.created_by,
            configuration_count=len(configurations),
            configurations=configurations
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{group_id}/configurations/{config_id}/reorder", response_model=Dict[str, Any])
async def reorder_configuration_in_group(
    group_id: int,
    config_id: int,
    new_order: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update the display order of a configuration within a specific group"""
    from database.database import metadata_group_configs
    
    # Verify group exists
    group = get_group(db, group_id)
    
    # Verify configuration is in this group
    association = db.query(metadata_group_configs).filter(
        metadata_group_configs.c.group_id == group_id,
        metadata_group_configs.c.config_id == config_id
    ).first()
    
    if not association:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found in this group"
        )
    
    old_order = association.display_order
    
    # Get all configurations in this group ordered by display_order
    all_configs = db.query(
        metadata_group_configs.c.config_id,
        metadata_group_configs.c.display_order
    ).filter(
        metadata_group_configs.c.group_id == group_id
    ).order_by(
        metadata_group_configs.c.display_order
    ).all()
    
    # Update display orders
    if new_order > old_order:
        # Moving down - shift others up
        db.execute(
            metadata_group_configs.update()
            .where(
                and_(
                    metadata_group_configs.c.group_id == group_id,
                    metadata_group_configs.c.display_order > old_order,
                    metadata_group_configs.c.display_order <= new_order
                )
            )
            .values(display_order=metadata_group_configs.c.display_order - 1)
        )
    elif new_order < old_order:
        # Moving up - shift others down
        db.execute(
            metadata_group_configs.update()
            .where(
                and_(
                    metadata_group_configs.c.group_id == group_id,
                    metadata_group_configs.c.display_order >= new_order,
                    metadata_group_configs.c.display_order < old_order
                )
            )
            .values(display_order=metadata_group_configs.c.display_order + 1)
        )
    
    # Update the target configuration's order
    db.execute(
        metadata_group_configs.update()
        .where(
            and_(
                metadata_group_configs.c.group_id == group_id,
                metadata_group_configs.c.config_id == config_id
            )
        )
        .values(display_order=new_order)
    )
    
    db.commit()
    
    logger.info(f"Reordered configuration {config_id} in group {group_id} from position {old_order} to {new_order}")
    return {"success": True, "message": f"Configuration moved to position {new_order} in group {group_id}"}

@router.post("/{group_id}/bulk-assign")
async def bulk_assign_configurations(
    group_id: int,
    config_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk assign multiple configurations to a group"""
    try:
        result = MetadataGroupService.bulk_assign_configurations(db, group_id, config_ids)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))