"""
Database initialization script for user authentication system
Creates new tables and default admin user
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database import engine, Base, Users, MetadataConfiguration, FileMetadataMapping, get_db_session
from services.password_utils import hash_password
from datetime import datetime

def create_tables():
    """Create all tables in the database"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")

def create_default_user(db):
    """Create the default admin user"""
    try:
        # Check if user already exists
        existing_user = db.query(Users).filter(Users.username == "mathan").first()
        if existing_user:
            if os.getenv("NODE_ENV") != "production":
                print("User 'mathan' already exists! Updating password.")
                existing_user.password_hash = hash_password("password")
                db.commit()
                print("✅ Password updated successfully!")
            return existing_user
        
        # Create default admin user
        hashed_password = hash_password("password")
        default_user = Users(
            username="",
            email="pravin.mishra@gmail.com",
            password_hash=hashed_password,
            role="admin",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
        
        # Check if we're in production mode
        if os.getenv("NODE_ENV") != "production":
            print("✅ Default admin user created successfully!")
            print(f"   Username: {default_user.username}")
            print(f"   Email: {default_user.email}")
            print(f"   Role: {default_user.role}")
        else:
            print("✅ Default admin user created successfully!")
        
        return default_user
        
    except Exception as e:
        print(f"❌ Error creating default user: {e}")
        db.rollback()
        return None

def create_sample_metadata_config(db, user_id: int):
    """Create a sample metadata configuration"""
    try:
        # Check if sample config already exists
        existing_config = db.query(MetadataConfiguration).filter(
            MetadataConfiguration.metadata_name == "Basic Entity Information"
        ).first()
        
        if existing_config:
            if os.getenv("NODE_ENV") != "production":
                print("Sample metadata configuration already exists!")
            return existing_config
        
        sample_config = MetadataConfiguration(
            metadata_name="Basic Entity Information",
            description="Extract basic entity information including name, manufacturer, and approval details",
            extraction_prompt="""Extract the following information from the FDA document:
1. Entity/Brand name
2. Manufacturer name
3. Approval date
4. Active ingredients
5. Dosage forms
6. Therapeutic classification

Return the information in a structured JSON format.""",
            is_active=True,
            created_by=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(sample_config)
        db.commit()
        db.refresh(sample_config)
        
        if os.getenv("NODE_ENV") != "production":
            print("✅ Sample metadata configuration created!")
            print(f"   Name: {sample_config.metadata_name}")
        else:
            print("✅ Sample metadata configuration created!")
        
        return sample_config
        
    except Exception as e:
        print(f"❌ Error creating sample metadata configuration: {e}")
        db.rollback()
        return None

def main():
    """Main initialization function"""
    print("🚀 Initializing FDA RAG User Authentication System...")
    print("=" * 60)
    
    # Step 1: Create tables
    create_tables()
    
    db = get_db_session()
    try:
        # Step 2: Create default user
        default_user = create_default_user(db)
        
        # Step 3: Create sample metadata configuration
        if default_user:
            create_sample_metadata_config(db, default_user.id)
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("=" * 60)
    print("🎉 Initialization completed successfully!")
    
    # Display application info
    if os.getenv("NODE_ENV") != "production":
        print("\nDevelopment Environment:")
        print("• API server available at: http://localhost:8090")
        print("• API documentation: http://localhost:8090/docs")
        print("• User management available via frontend")
    else:
        print("\nApplication initialized successfully. Check documentation for usage.")

if __name__ == "__main__":
    main() 