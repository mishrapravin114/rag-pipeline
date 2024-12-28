-- Migration to fix vector collection name column naming
-- The code expects 'vector_db_collection_name' and 'vector_db_collections' but the migration created different names
-- This fixes the naming mismatch

-- Fix collections table - rename to vector_db_collection_name
ALTER TABLE collections 
CHANGE COLUMN chromadb_collection_name vector_db_collection_name VARCHAR(255) UNIQUE NULL;

-- Fix SourceFiles table - rename to vector_db_collections  
ALTER TABLE SourceFiles 
CHANGE COLUMN chromadb_collections vector_db_collections JSON DEFAULT ('[]');

-- If other column names exist instead, use these (comment out the above and uncomment below):
-- ALTER TABLE collections 
-- CHANGE COLUMN vector_collection_name vector_db_collection_name VARCHAR(255) UNIQUE NULL;

-- ALTER TABLE SourceFiles 
-- CHANGE COLUMN vector_collections vector_db_collections JSON DEFAULT ('[]');