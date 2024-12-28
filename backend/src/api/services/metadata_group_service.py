"""
Metadata Group Service - Business logic for metadata group management
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime
import logging

from database.database import MetadataGroup, MetadataConfiguration, metadata_group_configs

logger = logging.getLogger(__name__)


class MetadataGroupService:
    """Service class for metadata group operations"""
    
    @staticmethod
    def ensure_default_group(db: Session, user_id: int) -> MetadataGroup:
        """Ensure the default 'General' group exists"""
        default_group = db.query(MetadataGroup).filter(
            MetadataGroup.is_default == True
        ).first()
        
        if not default_group:
            default_group = MetadataGroup(
                name="General",
                description="Default group for uncategorized metadata configurations",
                color="#6B7280",
                tags=["default"],
                is_default=True,
                created_by=user_id
            )
            db.add(default_group)
            db.commit()
            db.refresh(default_group)
            logger.info(f"Created default metadata group with ID: {default_group.id}")
        
        return default_group
    
    @staticmethod
    def assign_orphaned_configurations(db: Session, user_id: int) -> int:
        """Assign all orphaned configurations to the default group"""
        # Ensure default group exists
        default_group = MetadataGroupService.ensure_default_group(db, user_id)
        
        # Find configurations with no groups
        orphaned_configs = db.query(MetadataConfiguration).filter(
            ~MetadataConfiguration.groups.any()
        ).all()
        
        # Get the current maximum display_order for the default group
        max_order_result = db.query(func.max(metadata_group_configs.c.display_order)).filter(
            metadata_group_configs.c.group_id == default_group.id
        ).first()
        
        current_max_order = max_order_result[0] if max_order_result[0] is not None else -1
        
        count = 0
        for config in orphaned_configs:
            current_max_order += 1
            db.execute(
                metadata_group_configs.insert().values(
                    group_id=default_group.id,
                    config_id=config.id,
                    display_order=current_max_order,
                    added_at=datetime.utcnow(),
                    added_by=user_id
                )
            )
            count += 1
            logger.info(f"Assigned orphaned configuration '{config.metadata_name}' to default group")
        
        if count > 0:
            db.commit()
            logger.info(f"Successfully assigned {count} orphaned configurations to default group")
        
        return count
    
    @staticmethod
    def validate_group_name(db: Session, name: str, exclude_id: Optional[int] = None) -> bool:
        """Check if a group name is already taken"""
        query = db.query(MetadataGroup).filter(
            func.lower(MetadataGroup.name) == func.lower(name)
        )
        
        if exclude_id:
            query = query.filter(MetadataGroup.id != exclude_id)
        
        return query.first() is None
    
    @staticmethod
    def get_group_statistics(db: Session) -> Dict[str, Any]:
        """Get overall statistics about metadata groups"""
        total_groups = db.query(MetadataGroup).count()
        total_configs = db.query(MetadataConfiguration).count()
        orphaned_configs = db.query(MetadataConfiguration).filter(
            ~MetadataConfiguration.groups.any()
        ).count()
        
        # Get configuration count per group
        group_stats = db.query(
            MetadataGroup.name,
            func.count(MetadataConfiguration.id).label('config_count')
        ).join(
            MetadataGroup.configurations
        ).group_by(MetadataGroup.id).all()
        
        return {
            "total_groups": total_groups,
            "total_configurations": total_configs,
            "orphaned_configurations": orphaned_configs,
            "groups": [
                {"name": stat.name, "configuration_count": stat.config_count}
                for stat in group_stats
            ]
        }
    
    @staticmethod
    def bulk_assign_configurations(
        db: Session, 
        group_id: int, 
        config_ids: List[int]
    ) -> Dict[str, Any]:
        """Bulk assign configurations to a group"""
        from sqlalchemy import text
        
        group = db.query(MetadataGroup).filter(MetadataGroup.id == group_id).first()
        if not group:
            raise ValueError(f"Group with ID {group_id} not found")
        
        configs = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id.in_(config_ids)
        ).all()
        
        # Get the current maximum display_order for this group
        max_order_result = db.query(func.max(metadata_group_configs.c.display_order)).filter(
            metadata_group_configs.c.group_id == group_id
        ).first()
        
        current_max_order = max_order_result[0] if max_order_result[0] is not None else -1
        
        added = 0
        skipped = 0
        
        for config in configs:
            # Check if already in group
            existing = db.query(metadata_group_configs).filter(
                metadata_group_configs.c.group_id == group_id,
                metadata_group_configs.c.config_id == config.id
            ).first()
            
            if not existing:
                # Add configuration with proper display_order
                current_max_order += 1
                db.execute(
                    metadata_group_configs.insert().values(
                        group_id=group_id,
                        config_id=config.id,
                        display_order=current_max_order,
                        added_at=datetime.utcnow()
                    )
                )
                added += 1
            else:
                skipped += 1
        
        db.commit()
        
        return {
            "group_id": group_id,
            "requested": len(config_ids),
            "added": added,
            "skipped": skipped
        }
    
    @staticmethod
    def clone_group(
        db: Session, 
        source_group_id: int, 
        new_name: str,
        user_id: int
    ) -> MetadataGroup:
        """Clone a metadata group with all its configurations"""
        source_group = db.query(MetadataGroup).filter(
            MetadataGroup.id == source_group_id
        ).first()
        
        if not source_group:
            raise ValueError(f"Source group with ID {source_group_id} not found")
        
        # Create new group
        new_group = MetadataGroup(
            name=new_name,
            description=f"Cloned from {source_group.name}",
            color=source_group.color,
            tags=source_group.tags.copy() if source_group.tags else [],
            is_default=False,
            created_by=user_id
        )
        
        # Copy configurations
        new_group.configurations = source_group.configurations.copy()
        
        db.add(new_group)
        db.commit()
        db.refresh(new_group)
        
        logger.info(f"Cloned group {source_group.name} to {new_group.name}")
        return new_group
    
    @staticmethod
    def search_groups(
        db: Session,
        search_term: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_configurations: Optional[bool] = None
    ) -> List[MetadataGroup]:
        """Advanced search for metadata groups"""
        query = db.query(MetadataGroup)
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    MetadataGroup.name.ilike(search_pattern),
                    MetadataGroup.description.ilike(search_pattern)
                )
            )
        
        if tags:
            # Filter groups that have any of the specified tags
            for tag in tags:
                query = query.filter(
                    MetadataGroup.tags.contains([tag])
                )
        
        if has_configurations is not None:
            if has_configurations:
                query = query.filter(MetadataGroup.configurations.any())
            else:
                query = query.filter(~MetadataGroup.configurations.any())
        
        return query.order_by(
            MetadataGroup.is_default.desc(),
            MetadataGroup.updated_at.desc()
        ).all()
    
    @staticmethod
    def get_configuration_groups(
        db: Session, 
        config_id: int
    ) -> List[MetadataGroup]:
        """Get all groups that contain a specific configuration"""
        config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.id == config_id
        ).first()
        
        if not config:
            raise ValueError(f"Configuration with ID {config_id} not found")
        
        return config.groups