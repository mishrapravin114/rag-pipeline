"""
Unit tests for MetadataGroupService
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from unittest.mock import Mock, patch

from src.api.services.metadata_group_service import MetadataGroupService
from src.database.database import MetadataGroup, MetadataConfiguration


class TestMetadataGroupService:
    """Test cases for MetadataGroupService"""
    
    def test_ensure_default_group_creates_when_not_exists(self, db_session: Session):
        """Test that default group is created when it doesn't exist"""
        # Ensure no default group exists
        existing = db_session.query(MetadataGroup).filter(
            MetadataGroup.is_default == True
        ).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
        
        # Call ensure_default_group
        user_id = 1
        default_group = MetadataGroupService.ensure_default_group(db_session, user_id)
        
        # Verify default group was created
        assert default_group is not None
        assert default_group.name == "General"
        assert default_group.is_default == True
        assert default_group.color == "#6B7280"
        assert default_group.created_by == user_id
    
    def test_ensure_default_group_returns_existing(self, db_session: Session):
        """Test that existing default group is returned"""
        # Create a default group
        user_id = 1
        existing_group = MetadataGroup(
            name="Existing Default",
            description="Test default group",
            is_default=True,
            color="#123456",
            created_by=user_id
        )
        db_session.add(existing_group)
        db_session.commit()
        
        # Call ensure_default_group
        default_group = MetadataGroupService.ensure_default_group(db_session, user_id)
        
        # Verify existing group was returned
        assert default_group.id == existing_group.id
        assert default_group.name == "Existing Default"
    
    def test_assign_orphaned_configs_to_default(self, db_session: Session):
        """Test assigning orphaned configurations to default group"""
        user_id = 1
        
        # Create default group
        default_group = MetadataGroupService.ensure_default_group(db_session, user_id)
        
        # Create some orphaned configurations
        orphaned_configs = []
        for i in range(3):
            config = MetadataConfiguration(
                name=f"Orphaned Config {i}",
                description=f"Test orphaned config {i}",
                data_type="text",
                extraction_prompt=f"Extract {i}",
                created_by=user_id
            )
            db_session.add(config)
            orphaned_configs.append(config)
        
        # Create a group with configurations (not orphaned)
        other_group = MetadataGroup(
            name="Other Group",
            description="Non-default group",
            created_by=user_id
        )
        db_session.add(other_group)
        
        non_orphaned_config = MetadataConfiguration(
            name="Non-orphaned Config",
            description="Has a group",
            data_type="text",
            extraction_prompt="Extract",
            created_by=user_id
        )
        db_session.add(non_orphaned_config)
        db_session.flush()
        
        other_group.configurations.append(non_orphaned_config)
        db_session.commit()
        
        # Assign orphaned configs
        count = MetadataGroupService.assign_orphaned_configs_to_default(db_session, user_id)
        
        # Verify
        assert count == 3
        for config in orphaned_configs:
            db_session.refresh(config)
            assert default_group in config.groups
        
        # Verify non-orphaned config wasn't touched
        db_session.refresh(non_orphaned_config)
        assert len(non_orphaned_config.groups) == 1
        assert non_orphaned_config.groups[0] == other_group
    
    def test_create_group(self, db_session: Session):
        """Test creating a new metadata group"""
        user_id = 1
        
        # Create group
        group = MetadataGroupService.create_group(
            db=db_session,
            user_id=user_id,
            name="Test Group",
            description="Test description",
            color="#FF0000",
            tags=["tag1", "tag2"]
        )
        
        # Verify
        assert group.name == "Test Group"
        assert group.description == "Test description"
        assert group.color == "#FF0000"
        assert group.tags == ["tag1", "tag2"]
        assert group.created_by == user_id
        assert group.is_default == False
    
    def test_update_group(self, db_session: Session):
        """Test updating a metadata group"""
        user_id = 1
        
        # Create a group
        group = MetadataGroup(
            name="Original Name",
            description="Original description",
            created_by=user_id
        )
        db_session.add(group)
        db_session.commit()
        
        # Update group
        updated = MetadataGroupService.update_group(
            db=db_session,
            group_id=group.id,
            name="Updated Name",
            description="Updated description",
            color="#00FF00",
            tags=["new", "tags"]
        )
        
        # Verify
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.color == "#00FF00"
        assert updated.tags == ["new", "tags"]
    
    def test_delete_group_prevents_default_deletion(self, db_session: Session):
        """Test that default group cannot be deleted"""
        user_id = 1
        
        # Ensure default group exists
        default_group = MetadataGroupService.ensure_default_group(db_session, user_id)
        
        # Try to delete default group
        with pytest.raises(ValueError, match="Cannot delete the default group"):
            MetadataGroupService.delete_group(db_session, default_group.id)
    
    def test_delete_group_reassigns_configs(self, db_session: Session):
        """Test that configurations are reassigned when group is deleted"""
        user_id = 1
        
        # Ensure default group exists
        default_group = MetadataGroupService.ensure_default_group(db_session, user_id)
        
        # Create a group to delete
        group_to_delete = MetadataGroup(
            name="To Delete",
            description="Will be deleted",
            created_by=user_id
        )
        db_session.add(group_to_delete)
        
        # Create configurations in the group
        configs = []
        for i in range(2):
            config = MetadataConfiguration(
                name=f"Config {i}",
                description=f"Test config {i}",
                data_type="text",
                extraction_prompt=f"Extract {i}",
                created_by=user_id
            )
            db_session.add(config)
            configs.append(config)
        
        db_session.flush()
        
        for config in configs:
            group_to_delete.configurations.append(config)
        
        db_session.commit()
        
        # Delete the group
        success = MetadataGroupService.delete_group(db_session, group_to_delete.id)
        
        # Verify
        assert success == True
        assert db_session.query(MetadataGroup).filter_by(id=group_to_delete.id).first() is None
        
        # Verify configs were reassigned to default group
        for config in configs:
            db_session.refresh(config)
            assert len(config.groups) == 1
            assert config.groups[0] == default_group
    
    def test_add_configuration_to_group(self, db_session: Session):
        """Test adding configuration to a group"""
        user_id = 1
        
        # Create group and configuration
        group = MetadataGroup(
            name="Test Group",
            description="Test",
            created_by=user_id
        )
        db_session.add(group)
        
        config = MetadataConfiguration(
            name="Test Config",
            description="Test",
            data_type="text",
            extraction_prompt="Extract",
            created_by=user_id
        )
        db_session.add(config)
        db_session.commit()
        
        # Add configuration to group
        result = MetadataGroupService.add_configuration_to_group(
            db_session, group.id, config.id
        )
        
        # Verify
        assert result == True
        db_session.refresh(group)
        assert config in group.configurations
    
    def test_remove_configuration_from_group_prevents_orphaning(self, db_session: Session):
        """Test that removing last group assignment is prevented"""
        user_id = 1
        
        # Create group and configuration
        group = MetadataGroup(
            name="Only Group",
            description="Test",
            created_by=user_id
        )
        db_session.add(group)
        
        config = MetadataConfiguration(
            name="Test Config",
            description="Test",
            data_type="text",
            extraction_prompt="Extract",
            created_by=user_id
        )
        db_session.add(config)
        db_session.flush()
        
        group.configurations.append(config)
        db_session.commit()
        
        # Try to remove configuration (would orphan it)
        with pytest.raises(ValueError, match="Cannot remove configuration from its only group"):
            MetadataGroupService.remove_configuration_from_group(
                db_session, group.id, config.id
            )
    
    def test_search_groups(self, db_session: Session):
        """Test searching groups"""
        user_id = 1
        
        # Create test groups
        groups = [
            MetadataGroup(name="Alpha Group", description="First group", created_by=user_id),
            MetadataGroup(name="Beta Group", description="Second group", created_by=user_id),
            MetadataGroup(name="Gamma Group", description="Third alpha group", created_by=user_id)
        ]
        
        for group in groups:
            db_session.add(group)
        db_session.commit()
        
        # Search for "alpha"
        results = MetadataGroupService.search_groups(db_session, "alpha")
        
        # Verify
        assert len(results) == 2
        assert any(g.name == "Alpha Group" for g in results)
        assert any(g.name == "Gamma Group" for g in results)
    
    def test_get_group_statistics(self, db_session: Session):
        """Test getting group statistics"""
        user_id = 1
        
        # Create groups
        group1 = MetadataGroup(name="Group 1", created_by=user_id)
        group2 = MetadataGroup(name="Group 2", created_by=user_id)
        db_session.add(group1)
        db_session.add(group2)
        
        # Create configurations
        for i in range(3):
            config = MetadataConfiguration(
                name=f"Config {i}",
                data_type="text",
                extraction_prompt=f"Extract {i}",
                created_by=user_id,
                is_active=(i % 2 == 0)  # Alternate active/inactive
            )
            db_session.add(config)
            db_session.flush()
            
            if i < 2:
                group1.configurations.append(config)
            else:
                group2.configurations.append(config)
        
        db_session.commit()
        
        # Get statistics
        stats = MetadataGroupService.get_group_statistics(db_session)
        
        # Verify
        assert stats["total_groups"] == 2
        assert stats["total_configurations"] == 3
        assert stats["active_configurations"] == 2
        assert stats["inactive_configurations"] == 1
        
        # Check group details
        group_configs = stats["configurations_per_group"]
        assert len(group_configs) == 2
        assert any(g["group_name"] == "Group 1" and g["configuration_count"] == 2 for g in group_configs)
        assert any(g["group_name"] == "Group 2" and g["configuration_count"] == 1 for g in group_configs)


@pytest.fixture
def db_session():
    """Create a test database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database.database import Base
    
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()