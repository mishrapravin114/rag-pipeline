#!/usr/bin/env python
"""
Migration script to add collection indexing feature enhancements
This migration adds:
1. Collections table enhancements (chromadb_collection_name, indexing_stats)
2. Collection_document_association enhancements (indexed_at, indexing_status, etc.)
3. SourceFiles enhancements (chromadb_collections)
4. New indexing_jobs table
"""

import os
import sys
import json
from sqlalchemy import create_engine, text
from datetime import datetime

# Add parent directory to path to import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.settings import settings

def migrate():
    """Add collection indexing feature enhancements"""
    
    # Get database URL from settings
    DATABASE_URL = settings.DATABASE_URL
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            print("Starting collection indexing enhancements migration...")
            
            # 1. Enhance collections table
            print("\n1. Enhancing collections table...")
            
            # Check if chromadb_collection_name column exists
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collections' 
                AND column_name = 'chromadb_collection_name'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collections 
                    ADD COLUMN chromadb_collection_name VARCHAR(255) UNIQUE"""
                ))
                print("   - Added chromadb_collection_name column")
            else:
                print("   - chromadb_collection_name column already exists")
            
            # Check if indexing_stats column exists
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collections' 
                AND column_name = 'indexing_stats'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collections 
                    ADD COLUMN indexing_stats JSON"""
                ))
                print("   - Added indexing_stats column")
            else:
                print("   - indexing_stats column already exists")
            
            connection.commit()
            
            # 2. Enhance collection_document_association table
            print("\n2. Enhancing collection_document_association table...")
            
            # Add indexed_at column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND column_name = 'indexed_at'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collection_document_association 
                    ADD COLUMN indexed_at TIMESTAMP NULL"""
                ))
                print("   - Added indexed_at column")
            else:
                print("   - indexed_at column already exists")
            
            # Add indexing_status column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND column_name = 'indexing_status'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collection_document_association 
                    ADD COLUMN indexing_status VARCHAR(50) DEFAULT 'pending'"""
                ))
                print("   - Added indexing_status column")
            else:
                print("   - indexing_status column already exists")
            
            # Add indexing_progress column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND column_name = 'indexing_progress'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collection_document_association 
                    ADD COLUMN indexing_progress INTEGER DEFAULT 0"""
                ))
                print("   - Added indexing_progress column")
            else:
                print("   - indexing_progress column already exists")
            
            # Add error_message column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND column_name = 'error_message'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collection_document_association 
                    ADD COLUMN error_message TEXT NULL"""
                ))
                print("   - Added error_message column")
            else:
                print("   - error_message column already exists")
            
            # Add chromadb_doc_id column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND column_name = 'chromadb_doc_id'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE collection_document_association 
                    ADD COLUMN chromadb_doc_id VARCHAR(255) NULL"""
                ))
                print("   - Added chromadb_doc_id column")
            else:
                print("   - chromadb_doc_id column already exists")
            
            # Add index on collection_id and indexing_status
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND index_name = 'idx_collection_doc_status'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """CREATE INDEX idx_collection_doc_status 
                    ON collection_document_association(collection_id, indexing_status)"""
                ))
                print("   - Added idx_collection_doc_status index")
            else:
                print("   - idx_collection_doc_status index already exists")
            
            connection.commit()
            
            # 3. Enhance SourceFiles table
            print("\n3. Enhancing SourceFiles table...")
            
            # Add chromadb_collections column
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'SourceFiles' 
                AND column_name = 'chromadb_collections'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text(
                    """ALTER TABLE SourceFiles 
                    ADD COLUMN chromadb_collections JSON"""
                ))
                print("   - Added chromadb_collections column")
            else:
                print("   - chromadb_collections column already exists")
            
            connection.commit()
            
            # 4. Create indexing_jobs table
            print("\n4. Creating indexing_jobs table...")
            
            # Check if table exists
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'indexing_jobs'"""
            ))
            
            if result.scalar() == 0:
                connection.execute(text("""
                    CREATE TABLE indexing_jobs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        job_id CHAR(36) DEFAULT (UUID()),
                        collection_id INT,
                        user_id INT,
                        total_documents INT NOT NULL,
                        processed_documents INT DEFAULT 0,
                        failed_documents INT DEFAULT 0,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        job_type VARCHAR(50) NOT NULL,
                        options JSON,
                        error_details JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP NULL,
                        completed_at TIMESTAMP NULL,
                        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL,
                        INDEX idx_indexing_jobs_status (status, created_at),
                        INDEX idx_indexing_jobs_collection (collection_id, status),
                        INDEX idx_indexing_jobs_job_id (job_id)
                    )
                """))
                print("   - Created indexing_jobs table")
            else:
                print("   - indexing_jobs table already exists")
            
            connection.commit()
            
            print("\nMigration completed successfully!")
            return True
            
    except Exception as e:
        print(f"\nMigration error: {e}")
        return False

def rollback():
    """Rollback the migration (downgrade)"""
    
    # Get database URL from settings
    DATABASE_URL = settings.DATABASE_URL
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            print("Starting rollback of collection indexing enhancements...")
            
            # 1. Drop indexing_jobs table
            print("\n1. Dropping indexing_jobs table...")
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'indexing_jobs'"""
            ))
            
            if result.scalar() > 0:
                connection.execute(text("DROP TABLE indexing_jobs"))
                print("   - Dropped indexing_jobs table")
            
            # 2. Remove columns from SourceFiles
            print("\n2. Removing columns from SourceFiles...")
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'SourceFiles' 
                AND column_name = 'chromadb_collections'"""
            ))
            
            if result.scalar() > 0:
                connection.execute(text("ALTER TABLE SourceFiles DROP COLUMN chromadb_collections"))
                print("   - Removed chromadb_collections column")
            
            # 3. Remove columns and index from collection_document_association
            print("\n3. Removing enhancements from collection_document_association...")
            
            # Drop index first
            result = connection.execute(text(
                """SELECT COUNT(*) FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = 'collection_document_association' 
                AND index_name = 'idx_collection_doc_status'"""
            ))
            
            if result.scalar() > 0:
                connection.execute(text("DROP INDEX idx_collection_doc_status ON collection_document_association"))
                print("   - Dropped idx_collection_doc_status index")
            
            # Remove columns
            columns_to_drop = ['indexed_at', 'indexing_status', 'indexing_progress', 'error_message', 'chromadb_doc_id']
            for column in columns_to_drop:
                result = connection.execute(text(
                    f"""SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'collection_document_association' 
                    AND column_name = '{column}'"""
                ))
                
                if result.scalar() > 0:
                    connection.execute(text(f"ALTER TABLE collection_document_association DROP COLUMN {column}"))
                    print(f"   - Removed {column} column")
            
            # 4. Remove columns from collections
            print("\n4. Removing enhancements from collections...")
            columns_to_drop = ['chromadb_collection_name', 'indexing_stats']
            for column in columns_to_drop:
                result = connection.execute(text(
                    f"""SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'collections' 
                    AND column_name = '{column}'"""
                ))
                
                if result.scalar() > 0:
                    connection.execute(text(f"ALTER TABLE collections DROP COLUMN {column}"))
                    print(f"   - Removed {column} column")
            
            connection.commit()
            print("\nRollback completed successfully!")
            return True
            
    except Exception as e:
        print(f"\nRollback error: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Collection indexing enhancements migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.rollback:
        success = rollback()
    else:
        success = migrate()
    
    sys.exit(0 if success else 1)