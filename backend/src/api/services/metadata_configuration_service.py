"""
Service layer for metadata configuration management.
Handles business logic for configuration CRUD operations within groups.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from database.database import MetadataConfiguration, MetadataGroup, metadata_group_configs

logger = logging.getLogger(__name__)


class MetadataConfigurationService:
    """Service class for metadata configuration operations"""
    
    @staticmethod
    def list_configurations(
        db: Session,
        group_id: Optional[int] = None,
        active_only: bool = True,
        search: Optional[str] = None,
        data_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MetadataConfiguration]:
        """
        List configurations with optional filters.
        """
        query = db.query(MetadataConfiguration)
        
        # Filter by group if specified
        if group_id:
            query = query.join(MetadataConfiguration.groups).filter(
                MetadataGroup.id == group_id
            )
        
        # Filter by active status
        if active_only:
            query = query.filter(MetadataConfiguration.is_active == True)
        
        # Search in name and description
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    MetadataConfiguration.metadata_name.ilike(search_term),
                    MetadataConfiguration.description.ilike(search_term)
                )
            )
        
        # Filter by data type
        if data_type:
            query = query.filter(MetadataConfiguration.data_type == data_type)
        
        # Order by name (display_order is now per-group)
        query = query.order_by(
            MetadataConfiguration.metadata_name
        )
        
        # Apply pagination
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def create_configuration(
        db: Session,
        user_id: int,
        config_data: Dict[str, Any],
        group_ids: List[int]
    ) -> MetadataConfiguration:
        """
        Create a new metadata configuration and assign to groups.
        """
        # Create the configuration
        new_config = MetadataConfiguration(
            **config_data,
            created_by=user_id,
            extraction_prompt_version=1
        )
        
        db.add(new_config)
        db.flush()  # Get the ID
        
        # Assign to groups
        for group_id in group_ids:
            group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
            if group:
                new_config.groups.append(group)
        
        db.commit()
        db.refresh(new_config)
        
        logger.info(f"Created configuration '{new_config.metadata_name}' (ID: {new_config.id})")
        return new_config
    
    @staticmethod
    def update_configuration(
        db: Session,
        config_id: int,
        update_data: Dict[str, Any]
    ) -> MetadataConfiguration:
        """
        Update a metadata configuration.
        Increments version if extraction prompt changes.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        # Check if extraction prompt is being updated
        if "extraction_prompt" in update_data and update_data["extraction_prompt"] != config.extraction_prompt:
            config.extraction_prompt_version += 1
            logger.info(f"Incremented prompt version to {config.extraction_prompt_version} for config {config_id}")
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(config)
        
        logger.info(f"Updated configuration '{config.metadata_name}' (ID: {config_id})")
        return config
    
    @staticmethod
    def delete_configuration(db: Session, config_id: int) -> bool:
        """
        Delete a metadata configuration.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            return False
        
        config_name = config.metadata_name
        db.delete(config)
        db.commit()
        
        logger.info(f"Deleted configuration '{config_name}' (ID: {config_id})")
        return True
    
    @staticmethod
    def add_to_group(
        db: Session,
        config_id: int,
        group_id: int,
        user_id: int
    ) -> bool:
        """
        Add a configuration to a group.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        group = db.query(MetadataGroup).filter(
            MetadataGroup.id == group_id
        ).first()
        
        if not group:
            raise ValueError(f"Group with id {group_id} not found")
        
        # Check if already in group
        if group in config.groups:
            return False
        
        # Add to group
        config.groups.append(group)
        db.commit()
        
        logger.info(f"Added configuration {config_id} to group {group_id}")
        return True
    
    @staticmethod
    def remove_from_group(
        db: Session,
        config_id: int,
        group_id: int
    ) -> bool:
        """
        Remove a configuration from a group.
        Prevents orphaning by checking if it has other groups.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        # Check if configuration has multiple groups
        if len(config.groups) <= 1:
            raise ValueError("Cannot remove configuration from its only group. Configurations must belong to at least one group.")
        
        # Find and remove from group
        group = db.query(MetadataGroup).filter(
            MetadataGroup.id == group_id
        ).first()
        
        if not group or group not in config.groups:
            raise ValueError(f"Configuration is not in group {group_id}")
        
        config.groups.remove(group)
        db.commit()
        
        logger.info(f"Removed configuration {config_id} from group {group_id}")
        return True
    
    @staticmethod
    def bulk_operation(
        db: Session,
        config_ids: List[int],
        action: str,
        target_group_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform bulk operations on multiple configurations.
        """
        result = {
            "success": True,
            "total_items": len(config_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for config_id in config_ids:
            try:
                if action == "activate":
                    config = db.query(MetadataConfiguration).filter(
                        MetadataConfiguration.id == config_id
                    ).first()
                    if config:
                        config.is_active = True
                        result["successful"] += 1
                    else:
                        raise ValueError(f"Configuration {config_id} not found")
                
                elif action == "deactivate":
                    config = db.query(MetadataConfiguration).filter(
                        MetadataConfiguration.id == config_id
                    ).first()
                    if config:
                        config.is_active = False
                        result["successful"] += 1
                    else:
                        raise ValueError(f"Configuration {config_id} not found")
                
                elif action == "delete":
                    if MetadataConfigurationService.delete_configuration(db, config_id):
                        result["successful"] += 1
                    else:
                        raise ValueError(f"Configuration {config_id} not found")
                
                elif action == "move":
                    if not target_group_id:
                        raise ValueError("Target group ID required for move operation")
                    
                    config = db.query(MetadataConfiguration).filter(
                        MetadataConfiguration.id == config_id
                    ).first()
                    if config:
                        # Remove from all current groups
                        config.groups = []
                        # Add to target group
                        target_group = db.query(MetadataGroup).filter(
                            MetadataGroup.id == target_group_id
                        ).first()
                        if target_group:
                            config.groups.append(target_group)
                            result["successful"] += 1
                        else:
                            raise ValueError(f"Target group {target_group_id} not found")
                    else:
                        raise ValueError(f"Configuration {config_id} not found")
                
                elif action == "copy":
                    if not target_group_id:
                        raise ValueError("Target group ID required for copy operation")
                    
                    if MetadataConfigurationService.add_to_group(
                        db, config_id, target_group_id, user_id
                    ):
                        result["successful"] += 1
                
            except Exception as e:
                result["failed"] += 1
                result["errors"].append({
                    "config_id": config_id,
                    "error": str(e)
                })
                logger.error(f"Error in bulk operation for config {config_id}: {e}")
        
        # Commit all changes
        if result["successful"] > 0:
            db.commit()
        
        return result
    
    @staticmethod
    def clone_configuration(
        db: Session,
        config_id: int,
        new_name: str,
        target_group_ids: List[int],
        include_prompt: bool,
        user_id: int
    ) -> MetadataConfiguration:
        """
        Clone an existing configuration with a new name.
        """
        # Get original configuration
        original = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not original:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        # Check if name already exists
        existing = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.metadata_name == new_name
        ).first()
        
        if existing:
            raise ValueError(f"Configuration with name '{new_name}' already exists")
        
        # Create clone
        clone_data = {
            "metadata_name": new_name,
            "description": f"Cloned from {original.metadata_name}",
            "data_type": original.data_type,
            "extraction_prompt": original.extraction_prompt if include_prompt else "",
            "is_active": original.is_active,
            # display_order is now per-group, not global
            "validation_rules": original.validation_rules
        }
        
        cloned = MetadataConfigurationService.create_configuration(
            db=db,
            user_id=user_id,
            config_data=clone_data,
            group_ids=target_group_ids
        )
        
        logger.info(f"Cloned configuration {config_id} to new configuration {cloned.id}")
        return cloned
    
    @staticmethod
    def reorder_configuration(
        db: Session,
        config_id: int,
        new_order: int
    ) -> bool:
        """
        DEPRECATED: Reordering is now handled per-group.
        Use the group-specific reorder endpoint instead.
        This method is kept for backward compatibility but does nothing.
        """
        logger.warning(
            f"Deprecated reorder_configuration called for config {config_id}. "
            "Reordering should be done per-group now."
        )
        # Return True to maintain compatibility
        return True
    
    @staticmethod
    def update_group_assignments(
        db: Session,
        config_id: int,
        new_group_ids: List[int],
        user_id: int
    ) -> bool:
        """
        Update all group assignments for a configuration.
        Replaces existing assignments with new ones.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        # Validate all group IDs exist
        groups = []
        for group_id in new_group_ids:
            group = db.query(MetadataGroup).filter(
                MetadataGroup.id == group_id
            ).first()
            if not group:
                raise ValueError(f"Group with id {group_id} not found")
            groups.append(group)
        
        # Clear existing group assignments
        config.groups = []
        db.flush()
        
        # Add new group assignments
        for group in groups:
            config.groups.append(group)
        
        db.commit()
        
        logger.info(f"Updated configuration {config_id} with {len(groups)} group assignments")
        return True
    
    @staticmethod
    def get_available_groups(
        db: Session,
        config_id: int
    ) -> List[MetadataGroup]:
        """
        Get groups that a configuration is not currently assigned to.
        """
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with id {config_id} not found")
        
        # Get IDs of groups the config is already in
        current_group_ids = [g.id for g in config.groups]
        
        # Query for groups not in the current list
        available_groups = db.query(MetadataGroup).filter(
            ~MetadataGroup.id.in_(current_group_ids) if current_group_ids else True
        ).order_by(MetadataGroup.name).all()
        
        return available_groups