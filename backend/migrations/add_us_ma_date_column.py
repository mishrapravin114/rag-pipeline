#!/usr/bin/env python
"""
Migration script to add us_ma_date column to source_files table
"""

import sqlite3
import os
import sys

def migrate():
    """Add us_ma_date column to source_files table"""
    
    # Define database name directly
    DATABASE_NAME = "fda_rag.db"
    
    # Connect to the database
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', DATABASE_NAME)
    
    if not os.path.exists(db_path):
        print("Error: Database file not found at {}".format(db_path))
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(SourceFiles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'us_ma_date' in columns:
            print("Column 'us_ma_date' already exists in SourceFiles table")
            return True
        
        # Add the column
        print("Adding 'us_ma_date' column to SourceFiles table...")
        cursor.execute("ALTER TABLE SourceFiles ADD COLUMN us_ma_date VARCHAR(10)")
        
        conn.commit()
        print("Successfully added 'us_ma_date' column")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(SourceFiles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'us_ma_date' in columns:
            print("Verification: Column successfully added")
            return True
        else:
            print("Error: Column was not added successfully")
            return False
            
    except sqlite3.Error as e:
        print("SQLite error: {}".format(e))
        return False
    except Exception as e:
        print("Unexpected error: {}".format(e))
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)