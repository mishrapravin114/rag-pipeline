-- Migration to rename ChromaDB-specific columns to generic vector database columns
-- This is part of the ChromaDB to Qdrant migration effort

-- 1. Rename chromadb_collection_name to vector_collection_name in collections table
ALTER TABLE collections 
CHANGE COLUMN chromadb_collection_name vector_collection_name VARCHAR(255) UNIQUE NULL;

-- 2. Rename chromadb_doc_id to vector_doc_id in collection_document_association table
ALTER TABLE collection_document_association 
CHANGE COLUMN chromadb_doc_id vector_doc_id VARCHAR(255) NULL;

-- 3. Rename chromadb_collections to vector_collections in SourceFiles table
ALTER TABLE SourceFiles 
CHANGE COLUMN chromadb_collections vector_collections JSON DEFAULT ('[]');

-- To rollback this migration, run:
-- ALTER TABLE SourceFiles CHANGE COLUMN vector_collections chromadb_collections JSON DEFAULT ('[]');
-- ALTER TABLE collection_document_association CHANGE COLUMN vector_doc_id chromadb_doc_id VARCHAR(255) NULL;
-- ALTER TABLE collections CHANGE COLUMN vector_collection_name chromadb_collection_name VARCHAR(255) UNIQUE NULL;