#!/usr/bin/env python3
"""
Fixed Migration: Add Metadata Groups Consolidation
Date: 2025-01-29
Description: Creates and updates tables for metadata groups consolidation as per masterplan
"""

import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb as mysql
import os
import sys
from datetime import datetime

def column_exists(cursor, table_name, column_name, database):
    """Check if a column exists in a table"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (database, table_name, column_name))
    return cursor.fetchone()[0] > 0

def run_migration():
    """Execute the migration for metadata groups consolidation"""
    
    # Database configuration
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'fda_user'),
        'password': os.getenv('DB_PASSWORD', 'fda_password'),
        'database': os.getenv('DB_NAME', 'fda_rag')
    }
    
    # Connect to database
    try:
        print(f"Connecting to database {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        connection = mysql.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Start transaction
        connection.begin()
        
        # 1. Update metadata_groups table to match masterplan
        print("Updating metadata_groups table...")
        
        # Check and add color column
        if not column_exists(cursor, 'metadata_groups', 'color', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE metadata_groups ADD COLUMN color VARCHAR(7) DEFAULT '#3B82F6'")
            print("✓ Added color column")
        
        # Check and add tags column
        if not column_exists(cursor, 'metadata_groups', 'tags', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE metadata_groups ADD COLUMN tags JSON")
            print("✓ Added tags column")
        
        # Check and add is_default column
        if not column_exists(cursor, 'metadata_groups', 'is_default', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE metadata_groups ADD COLUMN is_default BOOLEAN DEFAULT FALSE")
            print("✓ Added is_default column")
        
        # 2. Update MetadataConfiguration table
        print("Updating MetadataConfiguration table...")
        
        # Check and add extraction_prompt_version
        if not column_exists(cursor, 'MetadataConfiguration', 'extraction_prompt_version', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE MetadataConfiguration ADD COLUMN extraction_prompt_version INT DEFAULT 1")
            print("✓ Added extraction_prompt_version column")
        
        # Check and add display_order
        if not column_exists(cursor, 'MetadataConfiguration', 'display_order', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE MetadataConfiguration ADD COLUMN display_order INT DEFAULT 0")
            print("✓ Added display_order column")
        
        # 3. Handle metadata_group_items to metadata_group_configs migration
        # Check if old table exists
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'metadata_group_items'
        """, (DB_CONFIG['database'],))
        
        if cursor.fetchone()[0] > 0:
            print("Migrating metadata_group_items to metadata_group_configs...")
            
            # Check if metadata_group_configs exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'metadata_group_configs'
            """, (DB_CONFIG['database'],))
            
            if cursor.fetchone()[0] == 0:
                # Create metadata_group_configs if it doesn't exist
                cursor.execute("""
                    CREATE TABLE metadata_group_configs (
                        group_id INT NOT NULL,
                        config_id INT NOT NULL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        added_by INT,
                        PRIMARY KEY (group_id, config_id),
                        FOREIGN KEY (group_id) REFERENCES metadata_groups(id) ON DELETE CASCADE,
                        FOREIGN KEY (config_id) REFERENCES MetadataConfiguration(id) ON DELETE CASCADE,
                        FOREIGN KEY (added_by) REFERENCES Users(id) ON DELETE SET NULL,
                        INDEX idx_config_groups (config_id, group_id)
                    )
                """)
                print("✓ Created metadata_group_configs table")
            
            # Migrate data
            cursor.execute("""
                INSERT IGNORE INTO metadata_group_configs (group_id, config_id)
                SELECT group_id, metadata_config_id
                FROM metadata_group_items
            """)
            print(f"✓ Migrated {cursor.rowcount} records")
            
            # Drop old table
            cursor.execute("DROP TABLE metadata_group_items")
            print("✓ Dropped metadata_group_items table")
        
        # 4. Create extraction_history table if it doesn't exist
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'extraction_history'
        """, (DB_CONFIG['database'],))
        
        if cursor.fetchone()[0] == 0:
            print("Creating extraction_history table...")
            cursor.execute("""
                CREATE TABLE extraction_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    document_id INT NOT NULL,
                    config_id INT NOT NULL,
                    prompt_version INT NOT NULL,
                    extracted_value JSON,
                    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (document_id) REFERENCES SourceFiles(id) ON DELETE CASCADE,
                    FOREIGN KEY (config_id) REFERENCES MetadataConfiguration(id),
                    INDEX idx_doc_config (document_id, config_id),
                    INDEX idx_extraction_date (extraction_date)
                )
            """)
            print("✓ Created extraction_history table")
        
        # 5. Create default "General" metadata group
        print("Ensuring default 'General' metadata group...")
        cursor.execute("""
            INSERT IGNORE INTO metadata_groups (name, description, color, is_default, created_by)
            VALUES ('General', 'Default group for uncategorized metadata configurations', '#6B7280', TRUE, 1)
        """)
        if cursor.rowcount > 0:
            print("✓ Created default 'General' group")
        else:
            print("✓ Default 'General' group already exists")
        
        # 6. Assign orphaned configurations to default group
        print("Assigning orphaned configurations to default group...")
        
        # Get default group ID
        cursor.execute("SELECT id FROM metadata_groups WHERE is_default = TRUE LIMIT 1")
        result = cursor.fetchone()
        if result:
            default_group_id = result[0]
            
            # Find and assign orphaned configurations
            cursor.execute("""
                INSERT INTO metadata_group_configs (group_id, config_id, added_by)
                SELECT %s, mc.id, 1
                FROM MetadataConfiguration mc
                LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
                WHERE mgc.config_id IS NULL
            """, (default_group_id,))
            
            if cursor.rowcount > 0:
                print(f"✓ Assigned {cursor.rowcount} orphaned configurations to default group")
            else:
                print("✓ No orphaned configurations found")
        
        # 7. Update collection_extraction_jobs table
        print("Updating collection_extraction_jobs table...")
        
        # Check and add extracted_content column
        if not column_exists(cursor, 'collection_extraction_jobs', 'extracted_content', DB_CONFIG['database']):
            cursor.execute("ALTER TABLE collection_extraction_jobs ADD COLUMN extracted_content JSON")
            print("✓ Added extracted_content column")
        
        # 8. Add indexes for performance
        print("Adding performance indexes...")
        
        # Check and add indexes
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.statistics 
            WHERE table_schema = %s AND table_name = 'metadata_groups' 
            AND index_name = 'idx_metadata_groups_name'
        """, (DB_CONFIG['database'],))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("CREATE INDEX idx_metadata_groups_name ON metadata_groups(name)")
            print("✓ Added index on metadata_groups.name")
        
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.statistics 
            WHERE table_schema = %s AND table_name = 'MetadataConfiguration' 
            AND index_name = 'idx_metadata_config_active'
        """, (DB_CONFIG['database'],))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("CREATE INDEX idx_metadata_config_active ON MetadataConfiguration(is_active, display_order)")
            print("✓ Added index on MetadataConfiguration.is_active")
        
        # 9. Record migration
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
        """, (f"add_metadata_groups_consolidation_{datetime.now().strftime('%Y%m%d')}",))
        
        # Commit transaction
        connection.commit()
        print("\n✅ Migration completed successfully!")
        
        # Verify results
        print("\nVerifying migration results:")
        
        # Count groups
        cursor.execute("SELECT COUNT(*) FROM metadata_groups")
        print(f"- Total metadata groups: {cursor.fetchone()[0]}")
        
        # Count configurations
        cursor.execute("SELECT COUNT(*) FROM MetadataConfiguration")
        total_configs = cursor.fetchone()[0]
        print(f"- Total configurations: {total_configs}")
        
        # Count assigned configurations
        cursor.execute("SELECT COUNT(DISTINCT config_id) FROM metadata_group_configs")
        assigned_configs = cursor.fetchone()[0]
        print(f"- Assigned configurations: {assigned_configs}")
        
        if total_configs == assigned_configs:
            print("✓ All configurations are assigned to groups (no orphans)")
        
    except mysql.Error as e:
        print(f"\n❌ Migration failed: {e}")
        if connection:
            connection.rollback()
            print("Transaction rolled back")
        return False
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        print("\nDatabase connection closed")
    
    return True

def check_current_state():
    """Check the current state of the database"""
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'fda_user'),
        'password': os.getenv('DB_PASSWORD', 'fda_password'),
        'database': os.getenv('DB_NAME', 'fda_rag')
    }
    
    try:
        connection = mysql.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("\nCurrent database state:")
        
        # Check existing tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name IN ('metadata_groups', 'MetadataConfiguration', 
                             'metadata_group_items', 'metadata_group_configs',
                             'extraction_history', 'collection_extraction_jobs')
        """, (DB_CONFIG['database'],))
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nExisting tables: {', '.join(tables)}")
        
        # Check for orphaned configurations
        cursor.execute("""
            SELECT COUNT(*) FROM MetadataConfiguration mc
            LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
            WHERE mgc.config_id IS NULL
        """)
        orphaned_count = cursor.fetchone()[0]
        print(f"\nOrphaned configurations that need assignment: {orphaned_count}")
        
        cursor.close()
        connection.close()
        
    except mysql.Error as e:
        print(f"\nError checking current state: {e}")

def main():
    """Main function"""
    print("=" * 60)
    print("Metadata Groups Consolidation Migration (Fixed)")
    print("=" * 60)
    
    # Check current state
    check_current_state()
    
    # Confirm before proceeding
    response = input("\nThis will update the metadata groups schema. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled")
        return
    
    # Run migration
    print("\nStarting migration...")
    if run_migration():
        print("\nMigration process completed!")
    else:
        print("\nMigration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()