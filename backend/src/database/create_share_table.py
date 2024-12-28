#!/usr/bin/env python3
"""
Script to create the ShareChat table in the database
"""
import sys
import os

# Add the parent directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from database import engine, Base, ShareChat
from sqlalchemy import inspect

def create_share_chat_table():
    """Create the ShareChat table if it doesn't exist"""
    try:
        # Get the inspector
        inspector = inspect(engine)
        
        # Check if the table already exists
        if 'ShareChat' in inspector.get_table_names():
            print("ShareChat table already exists.")
            return
        
        # Create the ShareChat table
        ShareChat.__table__.create(bind=engine)
        print("ShareChat table created successfully!")
        
    except Exception as e:
        print("Error creating ShareChat table: {}".format(e))
        raise

if __name__ == "__main__":
    create_share_chat_table()