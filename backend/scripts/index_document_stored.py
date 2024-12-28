#!/usr/bin/env python3
"""
Index Document Stored Records Script
Fetches all records with 'DOCUMENT_STORED' status from the database and indexes them to the vector database
"""

import os
import sys
import time
import logging
import argparse
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.database import SessionLocal, SourceFiles, DocumentData
from src.utils.chromadb_util import ChromaDBUtil
from sqlalchemy import and_, or_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('index_document_stored.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DocumentIndexer:
    """Indexes all DOCUMENT_STORED records to vector database"""
    
    def __init__(self, max_workers: int = 3, batch_size: int = 10, start_from_id: Optional[int] = None):
        """
        Initialize the document indexer
        
        Args:
            max_workers: Maximum number of concurrent workers
            batch_size: Number of files to process in each batch
            start_from_id: Process files with ID greater than this value
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.start_from_id = start_from_id
        self.chromadb = ChromaDBUtil()
        self.stats = {
            'indexed': 0,
            'failed': 0,
            'skipped': 0,
            'total_documents': 0
        }
    
    def get_document_stored_files(self, db, limit: Optional[int] = None) -> List[SourceFiles]:
        """Get files with DOCUMENT_STORED status"""
        query = db.query(SourceFiles).filter(SourceFiles.status == "DOCUMENT_STORED")
        
        # Apply start_from_id filter if specified
        if self.start_from_id is not None:
            query = query.filter(SourceFiles.id > self.start_from_id)
            logger.info(f"Filtering files with ID > {self.start_from_id}")
        
        # Order by ID to ensure consistent processing order
        query = query.order_by(SourceFiles.id.asc())
        
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def index_single_file(self, file_id: int) -> Dict[str, any]:
        """
        Index a single file to the vector database
        
        Args:
            file_id: ID of the source file to index
            
        Returns:
            Dict with indexing results
        """
        db = SessionLocal()
        result = {
            'file_id': file_id,
            'success': False,
            'status': None,
            'error': None,
            'documents_indexed': 0
        }
        
        try:
            # Get the file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
            if not source_file:
                result['error'] = 'File not found'
                return result
            
            # Check if already indexed
            if source_file.status == "READY":
                logger.info(f"File {file_id} already indexed, skipping")
                result['status'] = "ALREADY_INDEXED"
                self.stats['skipped'] += 1
                return result
            
            logger.info(f"Indexing file {file_id}: {source_file.file_name}")
            
            # Update status to INDEXING
            source_file.status = "INDEXING"
            db.commit()
            
            # Get documents to index
            documents = db.query(DocumentData).filter(
                DocumentData.source_file_id == file_id
            ).all()
            
            if not documents:
                logger.warning(f"No documents found for file {file_id}")
                source_file.status = "FAILED"
                source_file.comments = "No documents found to index"
                db.commit()
                result['error'] = "No documents found"
                self.stats['failed'] += 1
                return result
            
            # Prepare documents for ChromaDB
            chromadb_documents = []
            
            for doc in documents:
                # Parse metadata with error handling
                metadata = {}
                if doc.metadata_content:
                    try:
                        if isinstance(doc.metadata_content, str):
                            metadata = json.loads(doc.metadata_content)
                        else:
                            metadata = doc.metadata_content
                    except:
                        metadata = {"raw_metadata": str(doc.metadata_content)}
                
                # Add metadata matching API endpoint format
                metadata.update({
                    "source": source_file.file_name,  # Required by ChromaDBUtil
                    "source_file_id": file_id,
                    "document_id": doc.id,
                    "file_name": source_file.file_name,
                    "file_url": source_file.file_url,  # Add file_url to metadata
                    "drug_name": source_file.drug_name or '',
                    "chunk_id": doc.id
                })
                
                # Create document in expected format
                chromadb_documents.append({
                    'page_content': doc.doc_content,
                    'metadata': metadata
                })
            
            # Add to ChromaDB
            try:
                chromadb_result = self.chromadb.add_documents(
                    documents=chromadb_documents,
                    collection_name="fda_documents",
                    use_chromadb_batching=True  # Use ChromaDB's official batching utilities
                )
                
                # Update status to READY
                source_file.status = "READY"
                source_file.comments = f"Successfully indexed {len(documents)} documents"
                db.commit()
                
                logger.info(f"Successfully indexed {len(documents)} documents for file {file_id}")
                result['success'] = True
                result['status'] = "READY"
                result['documents_indexed'] = len(documents)
                self.stats['indexed'] += 1
                self.stats['total_documents'] += len(documents)
                
            except Exception as e:
                logger.error(f"ChromaDB error for file {file_id}: {str(e)}")
                source_file.status = "FAILED"
                source_file.comments = f"Indexing error: {str(e)}"
                db.commit()
                result['error'] = str(e)
                self.stats['failed'] += 1
                
        except Exception as e:
            logger.error(f"Database error for file {file_id}: {str(e)}")
            result['error'] = str(e)
            self.stats['failed'] += 1
        finally:
            db.close()
            
        return result
    
    def index_all_document_stored(self, continuous: bool = False, limit: Optional[int] = None):
        """
        Index all files with DOCUMENT_STORED status
        
        Args:
            continuous: If True, run continuously checking for new files
            limit: Maximum number of files to process (None for all)
        """
        logger.info(f"Starting indexing of DOCUMENT_STORED files with {self.max_workers} workers")
        if self.start_from_id is not None:
            logger.info(f"Processing files with ID > {self.start_from_id}")
        
        while True:
            db = SessionLocal()
            try:
                # Get DOCUMENT_STORED files in batches
                files_to_index = self.get_document_stored_files(db, limit=self.batch_size if not limit else min(self.batch_size, limit))
                
                if not files_to_index:
                    if continuous:
                        logger.info("No DOCUMENT_STORED files found. Waiting 60 seconds...")
                        time.sleep(60)
                        continue
                    else:
                        logger.info("No DOCUMENT_STORED files found to index")
                        break
                
                logger.info(f"Found {len(files_to_index)} files to index in this batch")
                
                # Process batch concurrently
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    
                    for file in files_to_index:
                        future = executor.submit(self.index_single_file, file.id)
                        futures.append((future, file.id))
                    
                    # Process results as they complete
                    for future, file_id in futures:
                        try:
                            result = future.result(timeout=300)  # 5 minute timeout
                            if result['success']:
                                logger.info(f"Successfully indexed file {file_id} ({result['documents_indexed']} documents)")
                            elif result['status'] == 'ALREADY_INDEXED':
                                logger.info(f"File {file_id} already indexed, skipped")
                            else:
                                logger.error(f"Failed to index file {file_id}: {result['error']}")
                        except Exception as e:
                            logger.error(f"Exception during indexing file {file_id}: {str(e)}")
                            self.stats['failed'] += 1
                
                # Update limit if specified
                if limit:
                    processed_count = len(files_to_index)
                    limit -= processed_count
                    if limit <= 0:
                        logger.info("Reached indexing limit. Exiting.")
                        break
                        
            except Exception as e:
                logger.error(f"Error during batch indexing: {str(e)}")
            finally:
                db.close()
            
            if not continuous and (not limit or limit <= 0):
                break
                
            # Small delay between batches
            time.sleep(5)
        
        # Print final statistics
        self.print_stats()
    
    def print_stats(self):
        """Print indexing statistics"""
        logger.info("=" * 50)
        logger.info("Indexing Statistics:")
        logger.info(f"  Successfully Indexed: {self.stats['indexed']} files")
        logger.info(f"  Total Documents Indexed: {self.stats['total_documents']}")
        logger.info(f"  Failed: {self.stats['failed']} files")
        logger.info(f"  Skipped (Already Indexed): {self.stats['skipped']} files")
        logger.info("=" * 50)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Index all DOCUMENT_STORED records to vector database')
    parser.add_argument('--limit', type=int, help='Maximum number of files to index')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for indexing')
    parser.add_argument('--single-file', type=int, help='Index a single file by ID')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--start-from-id', type=int, help='Process files with ID greater than this value')
    
    args = parser.parse_args()
    
    indexer = DocumentIndexer(
        max_workers=args.workers,
        batch_size=args.batch_size,
        start_from_id=args.start_from_id
    )
    
    try:
        if args.single_file:
            # Index a single file
            result = indexer.index_single_file(args.single_file)
            if result['success']:
                logger.info(f"Successfully indexed file {args.single_file}")
            else:
                logger.error(f"Failed to index file {args.single_file}: {result['error']}")
        else:
            # Index all DOCUMENT_STORED files
            indexer.index_all_document_stored(
                continuous=args.continuous,
                limit=args.limit
            )
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        indexer.print_stats()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()