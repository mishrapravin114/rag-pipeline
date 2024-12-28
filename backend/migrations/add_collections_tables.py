#!/usr/bin/env python
"""
Migration script to add collections and collection_document_association tables
"""

import os
import sys
import pymysql
from sqlalchemy import create_engine, text

# Add parent directory to path to import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.settings import settings

def migrate():
    """Add collections and collection_document_association tables"""
    
    # Get database URL from settings
    DATABASE_URL = settings.DATABASE_URL
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if collections table already exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'collections'"
            ))
            
            if result.scalar() > 0:
                print("Table 'collections' already exists")
            else:
                # Create collections table
                print("Creating 'collections' table...")
                connection.execute(text("""
                    CREATE TABLE collections (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        description TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_collections_name (name)
                    )
                """))
                connection.commit()
                print("Successfully created 'collections' table")
            
            # Check if collection_document_association table already exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'collection_document_association'"
            ))
            
            if result.scalar() > 0:
                print("Table 'collection_document_association' already exists")
            else:
                # Create collection_document_association table
                print("Creating 'collection_document_association' table...")
                connection.execute(text("""
                    CREATE TABLE collection_document_association (
                        collection_id INT NOT NULL,
                        document_id INT NOT NULL,
                        PRIMARY KEY (collection_id, document_id),
                        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                        FOREIGN KEY (document_id) REFERENCES SourceFiles(id) ON DELETE CASCADE,
                        INDEX idx_collection_document_collection (collection_id),
                        INDEX idx_collection_document_document (document_id)
                    )
                """))
                connection.commit()
                print("Successfully created 'collection_document_association' table")
            
            print("Migration completed successfully")
            return True
            
    except Exception as e:
        print(f"Migration error: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)