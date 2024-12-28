#!/usr/bin/env python3
"""
Script to verify the correct order of migrations and current database state
"""

import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb as mysql
import os
import sys
from datetime import datetime

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'fda_user'),
    'password': os.getenv('DB_PASSWORD', 'fda_password'),
    'database': os.getenv('DB_NAME', 'fda_rag')
}

def check_table_exists(cursor, table_name):
    """Check if a table exists"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
    """, (DB_CONFIG['database'], table_name))
    return cursor.fetchone()[0] > 0

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (DB_CONFIG['database'], table_name, column_name))
    return cursor.fetchone()[0] > 0

def check_constraint_exists(cursor, table_name, constraint_name):
    """Check if a constraint exists"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints
        WHERE table_schema = %s AND table_name = %s AND constraint_name = %s
    """, (DB_CONFIG['database'], table_name, constraint_name))
    return cursor.fetchone()[0] > 0

def verify_database_state():
    """Verify the current state of database migrations"""
    try:
        print(f"Connecting to {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        connection = mysql.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("\n" + "="*60)
        print("DATABASE MIGRATION STATE VERIFICATION")
        print("="*60)
        
        # Check for initial metadata tables
        print("\n1. INITIAL METADATA TABLES (add_metadata_extraction_tables.sql)")
        print("-"*50)
        
        initial_tables = {
            'metadata_groups': 'Metadata groups table',
            'metadata_group_items': 'Old junction table (should be migrated)',
            'collection_extracted_metadata': 'Extracted metadata storage',
            'collection_extraction_jobs': 'Extraction job tracking'
        }
        
        for table, desc in initial_tables.items():
            exists = check_table_exists(cursor, table)
            status = "✓ EXISTS" if exists else "✗ MISSING"
            print(f"  {table:<35} {status:<15} {desc}")
        
        # Check for consolidation changes
        print("\n2. METADATA GROUPS CONSOLIDATION (add_metadata_groups_consolidation.sql)")
        print("-"*50)
        
        # Check metadata_groups columns
        if check_table_exists(cursor, 'metadata_groups'):
            print("  metadata_groups table updates:")
            for col in ['color', 'tags', 'is_default']:
                exists = check_column_exists(cursor, 'metadata_groups', col)
                status = "✓" if exists else "✗"
                print(f"    {status} {col} column")
        
        # Check MetadataConfiguration columns
        if check_table_exists(cursor, 'MetadataConfiguration'):
            print("  MetadataConfiguration table updates:")
            for col in ['extraction_prompt_version', 'display_order']:
                exists = check_column_exists(cursor, 'MetadataConfiguration', col)
                status = "✓" if exists else "✗"
                print(f"    {status} {col} column")
        
        # Check new tables
        print("  New tables:")
        new_tables = {
            'metadata_group_configs': 'New junction table',
            'extraction_history': 'Extraction history tracking'
        }
        
        for table, desc in new_tables.items():
            exists = check_table_exists(cursor, table)
            status = "✓ EXISTS" if exists else "✗ MISSING"
            print(f"    {table:<30} {status:<15} {desc}")
        
        # Check if old table was dropped
        old_table_exists = check_table_exists(cursor, 'metadata_group_items')
        if old_table_exists and check_table_exists(cursor, 'metadata_group_configs'):
            print("\n  ⚠️  WARNING: Both old (metadata_group_items) and new (metadata_group_configs) tables exist!")
            print("     Migration may not have completed properly.")
        
        # Check for default group
        if check_table_exists(cursor, 'metadata_groups'):
            cursor.execute("SELECT COUNT(*) FROM metadata_groups WHERE is_default = TRUE")
            default_count = cursor.fetchone()[0]
            if default_count == 0:
                print("\n  ⚠️  WARNING: No default metadata group found!")
            else:
                print(f"\n  ✓ Default metadata group exists ({default_count} found)")
        
        # Check for additional columns
        print("\n3. ADDITIONAL MIGRATIONS")
        print("-"*50)
        
        # Check initiated_by column
        if check_table_exists(cursor, 'collection_extraction_jobs'):
            exists = check_column_exists(cursor, 'collection_extraction_jobs', 'initiated_by')
            status = "✓" if exists else "✗"
            print(f"  {status} initiated_by column in collection_extraction_jobs")
            
            # Check foreign key
            if exists:
                fk_exists = check_constraint_exists(cursor, 'collection_extraction_jobs', 'fk_extraction_jobs_user')
                fk_status = "✓" if fk_exists else "✗"
                print(f"    {fk_status} Foreign key constraint to Users table")
        
        # Check unique constraint
        if check_table_exists(cursor, 'collection_extracted_metadata'):
            constraint_exists = check_constraint_exists(cursor, 'collection_extracted_metadata', 'unique_metadata_entry')
            status = "✓" if constraint_exists else "✗"
            print(f"  {status} Unique constraint on collection_extracted_metadata")
        
        # Check for group-specific display_order
        if check_table_exists(cursor, 'metadata_group_configs'):
            exists = check_column_exists(cursor, 'metadata_group_configs', 'display_order')
            status = "✓" if exists else "✗"
            print(f"  {status} display_order column in metadata_group_configs (group-specific ordering)")
        
        # Check data integrity
        print("\n4. DATA INTEGRITY CHECKS")
        print("-"*50)
        
        # Check for orphaned configurations
        if check_table_exists(cursor, 'MetadataConfiguration') and check_table_exists(cursor, 'metadata_group_configs'):
            cursor.execute("""
                SELECT COUNT(*) FROM MetadataConfiguration mc
                LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
                WHERE mgc.config_id IS NULL
            """)
            orphaned = cursor.fetchone()[0]
            if orphaned > 0:
                print(f"  ⚠️  WARNING: {orphaned} orphaned metadata configurations found!")
            else:
                print("  ✓ No orphaned metadata configurations")
        
        # Summary statistics
        print("\n5. SUMMARY STATISTICS")
        print("-"*50)
        
        stats = []
        if check_table_exists(cursor, 'metadata_groups'):
            cursor.execute("SELECT COUNT(*) FROM metadata_groups")
            stats.append(f"Metadata groups: {cursor.fetchone()[0]}")
        
        if check_table_exists(cursor, 'MetadataConfiguration'):
            cursor.execute("SELECT COUNT(*) FROM MetadataConfiguration")
            stats.append(f"Metadata configurations: {cursor.fetchone()[0]}")
        
        if check_table_exists(cursor, 'metadata_group_configs'):
            cursor.execute("SELECT COUNT(*) FROM metadata_group_configs")
            stats.append(f"Group-config assignments: {cursor.fetchone()[0]}")
        
        if check_table_exists(cursor, 'collection_extraction_jobs'):
            cursor.execute("SELECT COUNT(*) FROM collection_extraction_jobs")
            stats.append(f"Extraction jobs: {cursor.fetchone()[0]}")
        
        for stat in stats:
            print(f"  {stat}")
        
        # Migration status
        print("\n6. MIGRATION STATUS")
        print("-"*50)
        
        if check_table_exists(cursor, 'schema_migrations'):
            cursor.execute("SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC LIMIT 5")
            migrations = cursor.fetchall()
            if migrations:
                print("  Recent migrations:")
                for version, applied_at in migrations:
                    print(f"    {applied_at} - {version}")
            else:
                print("  No migration records found")
        else:
            print("  ✗ schema_migrations table not found")
        
        print("\n" + "="*60)
        print("VERIFICATION COMPLETE")
        print("="*60)
        
    except mysql.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
    
    return True

def main():
    """Main function"""
    print("RAG Pipeline - Database Migration State Verification")
    print("Running verification...")
    
    if verify_database_state():
        print("\n✅ Verification completed successfully")
    else:
        print("\n❌ Verification failed")
        sys.exit(1)

if __name__ == "__main__":
    main()