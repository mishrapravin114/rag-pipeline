#!/usr/bin/env python3
"""
Migration: Add Metadata Extraction Tables
Date: 2024-11-28
Description: Creates tables for metadata groups, extraction jobs, and extracted metadata
"""

import mysql.connector
import os
import sys
from datetime import datetime

def run_migration():
    """Execute the migration to add metadata extraction tables"""
    
    # Database configuration
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'fda_user'),
        'password': os.getenv('DB_PASSWORD', 'fda_password'),
        'database': os.getenv('DB_NAME', 'fda_rag')
    }
    
    connection = None
    cursor = None
    
    try:
        # Connect to database
        print(f"Connecting to database {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Start transaction
        connection.start_transaction()
        
        # 1. Create metadata_groups table
        print("Creating metadata_groups table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata_groups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES Users(id)
            )
        """)
        print("✓ metadata_groups table created")
        
        # 2. Create metadata_group_items table
        print("Creating metadata_group_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata_group_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                group_id INT NOT NULL,
                metadata_config_id INT NOT NULL,
                display_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
                FOREIGN KEY (metadata_config_id) REFERENCES MetadataConfiguration(id),
                UNIQUE KEY unique_group_metadata (group_id, metadata_config_id)
            )
        """)
        print("✓ metadata_group_items table created")
        
        # 3. Create collection_extracted_metadata table
        print("Creating collection_extracted_metadata table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_extracted_metadata (
                id INT AUTO_INCREMENT PRIMARY KEY,
                collection_id INT NOT NULL,
                document_id INT NOT NULL,
                group_id INT NOT NULL,
                metadata_name VARCHAR(255) NOT NULL,
                extracted_value TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES SourceFiles(id),
                FOREIGN KEY (group_id) REFERENCES metadata_groups(id),
                INDEX idx_collection_group (collection_id, group_id),
                INDEX idx_document_metadata (document_id, metadata_name)
            )
        """)
        print("✓ collection_extracted_metadata table created")
        
        # 4. Create collection_extraction_jobs table
        print("Creating collection_extraction_jobs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_extraction_jobs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                collection_id INT NOT NULL,
                group_id INT NOT NULL,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                total_documents INT DEFAULT 0,
                processed_documents INT DEFAULT 0,
                failed_documents INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                created_by INT,
                error_details JSON,
                FOREIGN KEY (collection_id) REFERENCES collections(id),
                FOREIGN KEY (group_id) REFERENCES metadata_groups(id),
                FOREIGN KEY (created_by) REFERENCES Users(id),
                INDEX idx_status (status),
                INDEX idx_collection_status (collection_id, status)
            )
        """)
        print("✓ collection_extraction_jobs table created")
        
        # 5. Add any missing indexes (safety check)
        print("Verifying indexes...")
        
        # Check and add indexes if they don't exist
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.statistics 
            WHERE table_schema = %s 
            AND table_name = 'collection_extracted_metadata' 
            AND index_name = 'idx_collection_group'
        """, (DB_CONFIG['database'],))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE collection_extracted_metadata 
                ADD INDEX idx_collection_group (collection_id, group_id)
            """)
            print("✓ Added missing index idx_collection_group")
        
        # 6. Record migration
        print("Recording migration...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO schema_migrations (version) 
            VALUES (%s)
            ON DUPLICATE KEY UPDATE applied_at = CURRENT_TIMESTAMP
        """, (f"add_metadata_extraction_tables_{datetime.now().strftime('%Y%m%d')}",))
        
        # Commit transaction
        connection.commit()
        print("\n✅ Migration completed successfully!")
        
        # Verify tables
        print("\nVerifying tables created:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name IN ('metadata_groups', 'metadata_group_items', 
                               'collection_extracted_metadata', 'collection_extraction_jobs')
        """, (DB_CONFIG['database'],))
        
        tables = cursor.fetchall()
        for table in tables:
            print(f"  ✓ {table[0]}")
        
        return True
        
    except mysql.connector.Error as e:
        print(f"\n❌ Migration failed: {str(e)}")
        if connection:
            connection.rollback()
            print("Transaction rolled back")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        print("\nDatabase connection closed")

def main():
    """Main function to run the migration"""
    print("=" * 60)
    print("Metadata Extraction Tables Migration")
    print("=" * 60)
    
    # Check if we should proceed
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        print("Running in CHECK mode - no changes will be made")
        return
    
    # Confirm before proceeding
    response = input("\nThis will create new tables for metadata extraction. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled")
        return
    
    # Run the migration
    success = run_migration()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart the backend service: docker-compose restart backend")
        print("2. Build and restart the frontend: docker-compose exec frontend npm run build && docker-compose restart frontend")
        print("3. Test the new metadata extraction features in the UI")
    else:
        print("\n⚠️  Migration failed. Please check the error messages above.")
        print("No changes have been made to your database.")

if __name__ == "__main__":
    main()