-- Migration to rename chromadb_doc_id to vector_doc_id in collection_document_association table
-- This is part of the ChromaDB to Qdrant migration effort

ALTER TABLE collection_document_association 
CHANGE COLUMN chromadb_doc_id vector_doc_id VARCHAR(255) NULL;

-- To rollback this migration, run:
-- ALTER TABLE collection_document_association CHANGE COLUMN vector_doc_id chromadb_doc_id VARCHAR(255) NULL;