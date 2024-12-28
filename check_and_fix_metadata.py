#!/usr/bin/env python3
import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
DB_NAME = "fda_rag"
DB_USER = "fda_user"
DB_PASSWORD = "fda_password"
DB_HOST = "localhost"
DB_PORT = "3307"
CONTAINER_NAME = "mysql-db"

def execute_sql(sql, return_results=False):
    """Execute SQL command using docker"""
    try:
        cmd = [
            'sudo', 'docker', 'exec', '-i', CONTAINER_NAME,
            'mysql', '-u', DB_USER, f'-p{DB_PASSWORD}', DB_NAME, '-e', sql
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"SQL Error: {result.stderr}")
            return False if not return_results else []
            
        if return_results and result.stdout:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header
                return [line.split('\t') for line in lines[1:]]
            return []
        
        return True
        
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return False if not return_results else []

def main():
    logger.info("Checking table structures and fixing metadata migration issues...")
    
    # Check MetadataConfiguration columns
    logger.info("\n1. Checking MetadataConfiguration table structure...")
    sql = "SHOW COLUMNS FROM MetadataConfiguration;"
    columns = execute_sql(sql, return_results=True)
    
    if columns:
        logger.info("MetadataConfiguration columns:")
        for col in columns:
            logger.info(f"  - {col[0]} ({col[1]})")
    
    # Find the correct column name (might be 'name' instead of 'key_name')
    column_name = None
    for col in columns:
        if col[0] in ['key_name', 'name', 'config_name']:
            column_name = col[0]
            break
    
    if not column_name:
        # Use 'id' as fallback
        column_name = 'id'
        logger.info(f"Using '{column_name}' as identifier column")
    else:
        logger.info(f"Found identifier column: '{column_name}'")
    
    # Check metadata_group_configs structure
    logger.info("\n2. Checking metadata_group_configs table structure...")
    sql = "SHOW COLUMNS FROM metadata_group_configs;"
    mgc_columns = execute_sql(sql, return_results=True)
    
    if mgc_columns:
        logger.info("metadata_group_configs columns:")
        for col in mgc_columns:
            logger.info(f"  - {col[0]} ({col[1]})")
    
    # Now assign orphaned configs with correct column names
    logger.info("\n3. Assigning orphaned metadata configurations...")
    
    # First check if there are any orphaned configs
    orphan_sql = f"""
    SELECT mc.id, mc.{column_name} 
    FROM MetadataConfiguration mc
    LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
    WHERE mgc.config_id IS NULL;
    """
    orphans = execute_sql(orphan_sql, return_results=True)
    
    if orphans and len(orphans) > 0:
        logger.info(f"Found {len(orphans)} orphaned configurations")
        
        # Get default group ID
        default_group_sql = "SELECT id FROM metadata_groups WHERE is_default = 1 LIMIT 1;"
        default_group = execute_sql(default_group_sql, return_results=True)
        
        if default_group and len(default_group) > 0:
            default_group_id = default_group[0][0]
            logger.info(f"Default group ID: {default_group_id}")
            
            for config in orphans:
                config_id = config[0]
                config_identifier = config[1] if len(config) > 1 else config_id
                logger.info(f"Assigning config '{config_identifier}' (ID: {config_id}) to default group")
                assign_sql = f"""
                INSERT IGNORE INTO metadata_group_configs (group_id, config_id, display_order)
                VALUES ({default_group_id}, {config_id}, 0);
                """
                execute_sql(assign_sql)
    else:
        logger.info("No orphaned configurations found")
    
    # Initialize display orders for all groups
    logger.info("\n4. Re-initializing display orders...")
    groups_sql = "SELECT id FROM metadata_groups;"
    groups = execute_sql(groups_sql, return_results=True)
    
    if groups and len(groups) > 0:
        for group in groups:
            group_id = group[0]
            logger.info(f"Setting display order for group ID: {group_id}")
            
            # Get configs for this group
            configs_sql = f"""
            SELECT config_id FROM metadata_group_configs 
            WHERE group_id = {group_id} 
            ORDER BY config_id;
            """
            configs = execute_sql(configs_sql, return_results=True)
            
            if configs:
                for idx, config in enumerate(configs):
                    config_id = config[0]
                    display_order = (idx + 1) * 10
                    update_sql = f"""
                    UPDATE metadata_group_configs 
                    SET display_order = {display_order}
                    WHERE group_id = {group_id} AND config_id = {config_id};
                    """
                    execute_sql(update_sql)
    
    # Final verification
    logger.info("\n5. Final Verification:")
    
    # Count metadata groups
    count_sql = "SELECT COUNT(*) FROM metadata_groups;"
    result = execute_sql(count_sql, return_results=True)
    if result and len(result) > 0:
        logger.info(f"Total metadata groups: {result[0][0]}")
    
    # Count metadata configurations
    count_sql = "SELECT COUNT(*) FROM MetadataConfiguration;"
    result = execute_sql(count_sql, return_results=True)
    if result and len(result) > 0:
        logger.info(f"Total metadata configurations: {result[0][0]}")
    
    # Count assignments
    count_sql = "SELECT COUNT(*) FROM metadata_group_configs;"
    result = execute_sql(count_sql, return_results=True)
    if result and len(result) > 0:
        logger.info(f"Total assignments: {result[0][0]}")
    
    # Check for orphans with correct column
    orphan_check_sql = """
    SELECT COUNT(*) 
    FROM MetadataConfiguration mc
    LEFT JOIN metadata_group_configs mgc ON mc.id = mgc.config_id
    WHERE mgc.config_id IS NULL;
    """
    result = execute_sql(orphan_check_sql, return_results=True)
    if result and len(result) > 0:
        logger.info(f"Orphaned configurations: {result[0][0]}")
    
    logger.info("\nMetadata configuration fix completed!")

if __name__ == "__main__":
    main()