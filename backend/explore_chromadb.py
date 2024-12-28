#!/usr/bin/env python3
"""
Explore ChromaDB directory structure and collections.
"""

import os
import sqlite3

def explore_chromadb_directory():
    """Explore ChromaDB directory structure."""
    
    # Check possible ChromaDB locations
    possible_paths = [
        "/app/data/chromadb",
        "/home/pravin/Documents/rag-pipeline/backend/data/chromadb",
        "./data/chromadb",
        "../data/chromadb"
    ]
    
    print("🔍 EXPLORING CHROMADB LOCATIONS")
    print("="*50)
    
    for path in possible_paths:
        print(f"\n📁 Checking: {path}")
        if os.path.exists(path):
            print(f"   ✅ EXISTS")
            
            # List contents
            try:
                contents = os.listdir(path)
                print(f"   📄 Contents ({len(contents)} items):")
                for item in contents[:10]:  # Show first 10 items
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        print(f"      📁 {item}/")
                    else:
                        print(f"      📄 {item}")
                if len(contents) > 10:
                    print(f"      ... and {len(contents) - 10} more items")
                
                # Check for SQLite database
                sqlite_path = os.path.join(path, "chroma.sqlite3")
                if os.path.exists(sqlite_path):
                    print(f"   📊 SQLite database found: chroma.sqlite3")
                    try:
                        conn = sqlite3.connect(sqlite_path)
                        cursor = conn.cursor()
                        
                        # Get tables
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = cursor.fetchall()
                        print(f"      📋 Tables: {[t[0] for t in tables]}")
                        
                        # Check collections table
                        try:
                            cursor.execute("SELECT name, id FROM collections;")
                            collections = cursor.fetchall()
                            print(f"      🗂️  Collections in DB: {len(collections)}")
                            for name, id_ in collections:
                                print(f"         - {name} (ID: {id_})")
                                
                                # Check if collection has documents
                                try:
                                    cursor.execute("SELECT COUNT(*) FROM embeddings WHERE collection_id = ?", (id_,))
                                    count = cursor.fetchone()[0]
                                    print(f"           📊 Documents: {count}")
                                except Exception as e:
                                    print(f"           ❌ Error counting documents: {e}")
                        except Exception as e:
                            print(f"      ❌ Error reading collections: {e}")
                        
                        conn.close()
                    except Exception as e:
                        print(f"      ❌ Error accessing SQLite: {e}")
                else:
                    print(f"   ❌ No chroma.sqlite3 found")
                    
            except Exception as e:
                print(f"   ❌ Error listing contents: {e}")
        else:
            print(f"   ❌ DOES NOT EXIST")

def test_chromadb_connection():
    """Test direct ChromaDB connection."""
    print(f"\n🧪 TESTING CHROMADB CONNECTION")
    print("="*50)
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Try the path that was found
        chromadb_path = "/app/data/chromadb"
        print(f"📁 Connecting to: {chromadb_path}")
        
        client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )
        
        collections = client.list_collections()
        print(f"✅ Connected successfully!")
        print(f"📊 Found {len(collections)} collections:")
        
        for i, col in enumerate(collections, 1):
            try:
                count = col.count()
                print(f"   {i}. {col.name} ({count} documents)")
                
                # Get a sample document
                if count > 0:
                    sample = col.peek(limit=1)
                    if sample['ids']:
                        print(f"      📄 Sample ID: {sample['ids'][0]}")
                        if sample['metadatas'] and sample['metadatas'][0]:
                            print(f"      🏷️  Metadata keys: {list(sample['metadatas'][0].keys())}")
                    
            except Exception as e:
                print(f"   {i}. {col.name} (error getting info: {e})")
        
        if not collections:
            print("   📭 No collections found")
            
            # Try to create a test collection to see if it works
            print("\n🧪 Testing collection creation...")
            try:
                test_col = client.create_collection("test_migration_check")
                print("   ✅ Collection creation works")
                client.delete_collection("test_migration_check")
                print("   ✅ Collection deletion works")
            except Exception as e:
                print(f"   ❌ Collection operations failed: {e}")
        
    except ImportError:
        print("❌ ChromaDB not installed")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    explore_chromadb_directory()
    test_chromadb_connection()