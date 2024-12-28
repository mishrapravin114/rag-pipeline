"""
Association object for metadata_group_configs to allow access to display_order
"""
from sqlalchemy.orm import relationship
from database.database import Base, metadata_group_configs
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime

class MetadataGroupConfig(Base):
    """Association object for the many-to-many relationship with additional attributes"""
    __table__ = metadata_group_configs
    
    group_id = Column(Integer, ForeignKey('metadata_groups.id'), primary_key=True)
    config_id = Column(Integer, ForeignKey('MetadataConfiguration.id'), primary_key=True)
    display_order = Column(Integer, default=0, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by = Column(Integer, ForeignKey('Users.id'), nullable=True)
    
    # Relationships
    group = relationship("MetadataGroup", backref="config_associations")
    configuration = relationship("MetadataConfiguration", backref="group_associations")