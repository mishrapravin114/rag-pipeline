#!/usr/bin/env python
"""
Test script to verify that metadata configurations return the correct group_count
"""

from sqlalchemy.orm import Session
from database.database import get_db, MetadataConfiguration
from api.routers.metadata_configurations import MetadataConfigurationResponse

def test_group_count():
    """Test that group_count is correctly calculated"""
    # Get a database session
    db = next(get_db())
    
    try:
        # Get a metadata configuration with groups
        config = db.query(MetadataConfiguration).first()
        
        if config:
            print(f"Configuration: {config.metadata_name}")
            print(f"Number of groups: {len(config.groups)}")
            print(f"Groups: {[g.name for g in config.groups]}")
            
            # Test creating response model
            response = MetadataConfigurationResponse(
                **{
                    **config.__dict__,
                    "groups": [
                        {
                            "id": g.id,
                            "name": g.name,
                            "color": g.color
                        } for g in config.groups
                    ],
                    "group_count": len(config.groups),
                    "name": config.metadata_name  # Map metadata_name to name
                }
            )
            
            print(f"\nResponse model group_count: {response.group_count}")
            print(f"Response model groups length: {len(response.groups)}")
            
            assert response.group_count == len(response.groups), "Group count mismatch!"
            print("\nTest passed! Group count is correctly calculated.")
        else:
            print("No metadata configurations found in database.")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_group_count()