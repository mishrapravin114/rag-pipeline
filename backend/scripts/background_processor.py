#!/usr/bin/env python3
"""
Background Job Processor for FDA RAG Pipeline
Processes pending source files up to DOCUMENT_STORED status: PENDING -> PROCESSING -> DOCUMENT_STORED
Indexing to READY status must be done manually
Can be run as a cron job or continuous background service
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
from src.fda_pipeline import FDAPipelineV2
from src.utils.chromadb_util import ChromaDBUtil
from sqlalchemy import and_, or_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackgroundProcessor:
    """Background processor for handling source files up to DOCUMENT_STORED status"""
    
    def __init__(self, max_workers: int = 3, batch_size: int = 10, start_from_id: Optional[int] = None):
        """
        Initialize the background processor
        
        Args:
            max_workers: Maximum number of concurrent workers
            batch_size: Number of files to process in each batch
            start_from_id: Process files with ID greater than this value
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.start_from_id = start_from_id
        self.pipeline = FDAPipelineV2()
        self.chromadb = ChromaDBUtil()
        self.stats = {
            'processed': 0,
            'indexed': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def get_pending_files(self, db, limit: Optional[int] = None) -> List[SourceFiles]:
        """Get files that need processing (PENDING status)"""
        query = db.query(SourceFiles).filter(SourceFiles.status == "PENDING")
        
        # Apply start_from_id filter if specified
        if self.start_from_id is not None:
            query = query.filter(SourceFiles.id > self.start_from_id)
            logger.info(f"Filtering files with ID > {self.start_from_id}")
        
        # Order by ID to ensure consistent processing order
        query = query.order_by(SourceFiles.id.asc())
        
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_files_for_indexing(self, db, limit: Optional[int] = None) -> List[SourceFiles]:
        """Get files that need indexing (DOCUMENT_STORED status)"""
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
    
    def process_single_file(self, file_id: int) -> Dict[str, any]:
        """
        Process a single file through the pipeline
        
        Args:
            file_id: ID of the source file to process
            
        Returns:
            Dict with processing results
        """
        db = SessionLocal()
        result = {
            'file_id': file_id,
            'success': False,
            'status': None,
            'error': None
        }
        
        try:
            # Get the file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
            if not source_file:
                result['error'] = 'File not found'
                return result
            
            logger.info(f"Processing file {file_id}: {source_file.file_name}")
            
            # Update status to PROCESSING
            source_file.status = "PROCESSING"
            db.commit()
            
            # Process the PDF
            try:
                processing_result = self.pipeline.process_source_file(source_file)
                
                if processing_result.get('success'):
                    # Update status to DOCUMENT_STORED
                    source_file.status = "DOCUMENT_STORED"
                    source_file.comments = f"Successfully processed {processing_result.get('documents_count', 0)} documents"
                    db.commit()
                    
                    logger.info(f"Successfully processed file {file_id}")
                    result['success'] = True
                    result['status'] = "DOCUMENT_STORED"
                    self.stats['processed'] += 1
                else:
                    # Mark as failed
                    source_file.status = "FAILED"
                    source_file.comments = f"Processing error: {processing_result.get('error', 'Unknown error')}"
                    db.commit()
                    
                    result['error'] = processing_result.get('error', 'Processing failed')
                    self.stats['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing file {file_id}: {str(e)}")
                source_file.status = "FAILED"
                source_file.comments = f"Processing error: {str(e)}"
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
            'error': None
        }
        
        try:
            # Get the file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == file_id).first()
            if not source_file:
                result['error'] = 'File not found'
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
                # Parse metadata with error handling (same as API endpoint)
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
                result = self.chromadb.add_documents(
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
                self.stats['indexed'] += 1
                
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
    
    def process_file_complete_pipeline(self, file_id: int) -> Dict[str, any]:
        """
        Process a file through the pipeline up to DOCUMENT_STORED status
        
        Args:
            file_id: ID of the source file
            
        Returns:
            Dict with processing results
        """
        # Process the PDF and stop at DOCUMENT_STORED
        process_result = self.process_single_file(file_id)
        return process_result
    
    def process_batch(self, continuous: bool = False, limit: Optional[int] = None):
        """
        Process files in batches (up to DOCUMENT_STORED status only)
        
        Args:
            continuous: If True, run continuously checking for new files
            limit: Maximum number of files to process (None for all)
        """
        logger.info(f"Starting batch processor with {self.max_workers} workers (processing to DOCUMENT_STORED only)")
        if self.start_from_id is not None:
            logger.info(f"Processing files with ID > {self.start_from_id}")
        
        while True:
            db = SessionLocal()
            try:
                # Get pending files only
                pending_files = self.get_pending_files(db, limit=self.batch_size if not limit else min(self.batch_size, limit))
                
                if not pending_files:
                    if continuous:
                        logger.info("No files to process. Waiting 60 seconds...")
                        time.sleep(60)
                        continue
                    else:
                        logger.info("No files to process. Exiting.")
                        break
                
                # Process files concurrently
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    
                    # Submit pending files for processing to DOCUMENT_STORED
                    for file in pending_files:
                        future = executor.submit(self.process_file_complete_pipeline, file.id)
                        futures.append((future, file.id, 'process'))
                    
                    # Process results as they complete
                    for future, file_id, operation in futures:
                        try:
                            result = future.result(timeout=300)  # 5 minute timeout
                            if result['success']:
                                logger.info(f"Successfully completed {operation} for file {file_id}")
                            else:
                                logger.error(f"Failed {operation} for file {file_id}: {result['error']}")
                        except Exception as e:
                            logger.error(f"Exception during {operation} for file {file_id}: {str(e)}")
                            self.stats['failed'] += 1
                
                # Update limit if specified
                if limit:
                    processed_count = len(pending_files)
                    limit -= processed_count
                    if limit <= 0:
                        logger.info("Reached processing limit. Exiting.")
                        break
                        
            except Exception as e:
                logger.error(f"Batch processing error: {str(e)}")
            finally:
                db.close()
            
            if not continuous and (not limit or limit <= 0):
                break
                
            # Small delay between batches
            time.sleep(5)
        
        # Print final statistics
        self.print_stats()
    
    def print_stats(self):
        """Print processing statistics"""
        logger.info("=" * 50)
        logger.info("Processing Statistics:")
        logger.info(f"  Processed: {self.stats['processed']}")
        logger.info(f"  Indexed: {self.stats['indexed']}")
        logger.info(f"  Failed: {self.stats['failed']}")
        logger.info(f"  Skipped: {self.stats['skipped']}")
        logger.info("=" * 50)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Background processor for FDA RAG pipeline')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--limit', type=int, help='Maximum number of files to process')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for processing')
    parser.add_argument('--single-file', type=int, help='Process a single file by ID')
    parser.add_argument('--start-from-id', type=int, help='Process files with ID greater than this value')
    
    args = parser.parse_args()
    
    processor = BackgroundProcessor(
        max_workers=args.workers,
        batch_size=args.batch_size,
        start_from_id=args.start_from_id
    )
    
    try:
        if args.single_file:
            # Process a single file
            result = processor.process_file_complete_pipeline(args.single_file)
            if result['success']:
                logger.info(f"Successfully processed file {args.single_file}")
            else:
                logger.error(f"Failed to process file {args.single_file}: {result['error']}")
        else:
            # Process batch
            processor.process_batch(
                continuous=args.continuous,
                limit=args.limit
            )
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        processor.print_stats()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()