#!/usr/bin/env python3
"""
FDA RAG Pipeline V2 - Enhanced with proper status management
"""

import logging
import os
import sys
import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from config.settings import settings
from utils.pymupdf_processor import PyMuPDFProcessor
from database.database import (
    database_session, create_tables, 
    update_source_file_status, save_documents_to_db, SourceFiles
)

class FDAPipelineV2:
    """Enhanced FDA RAG Pipeline with proper status management."""
    
    def __init__(self):
        """Initialize the FDA pipeline with PyMuPDF processor."""
        self.setup_logging()
        create_tables()  # Ensure database tables exist
        
        # Use PyMuPDF processor for better PDF handling
        self.pdf_processor = PyMuPDFProcessor(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        logger.info("FDA Pipeline V2 initialized with PyMuPDF processor")
    
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_file = os.path.join(
            settings.LOG_OUTPUT_DIR, 
            f"fda_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        global logger
        logger = logging.getLogger(__name__)
        logger.info(f"Logging initialized. Log file: {log_file}")
    
    def download_pdf(self, url: str, filename: str) -> str:
        """Download a PDF from the given URL or handle local file."""
        try:
            # Handle local files
            if url.startswith("local://"):
                # Legacy format: local://filename.pdf
                local_filename = url.replace("local://", "")
                # Check in uploads directory first
                upload_path = os.path.join("uploads", local_filename)
                if os.path.exists(upload_path):
                    logger.info(f"Using local file from uploads: {upload_path}")
                    return upload_path
                # Check absolute path as fallback
                elif os.path.exists(local_filename):
                    logger.info(f"Using local file: {local_filename}")
                    return local_filename
                else:
                    raise FileNotFoundError(f"Local file not found: {local_filename} (checked uploads/{local_filename} and {local_filename})")
            elif "/uploads/" in url:
                # New format: http://localhost:8090/uploads/filename.pdf
                local_filename = url.split("/uploads/")[-1]
                upload_path = os.path.join("uploads", local_filename)
                if os.path.exists(upload_path):
                    logger.info(f"Using local file from uploads: {upload_path}")
                    return upload_path
                else:
                    raise FileNotFoundError(f"Uploaded file not found: {upload_path}")
            
            # Handle remote URLs
            filepath = os.path.join(settings.DOWNLOAD_DIR, filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                logger.info(f"File already exists: {filepath}")
                return filepath
            
            logger.info(f"Downloading PDF from: {url}")
            
            # Create download directory if it doesn't exist
            os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
            
            # Headers to avoid bot detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            # Retry logic with smart handling for rate limits
            max_retries = 3
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    # Success - save and return
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    logger.info(f"PDF downloaded successfully: {filepath}")
                    return filepath
                    
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        # Rate limited - use exponential backoff
                        wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                        logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    elif e.response.status_code in [503, 504] and attempt < max_retries - 1:
                        # Server errors - shorter retry delays
                        wait_time = 2 ** attempt  # 1, 2, 4 seconds
                        logger.warning(f"Server error {e.response.status_code}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Other HTTP errors or final attempt - raise immediately
                        raise
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Network error on attempt {attempt + 1}: {str(e)}")
                        time.sleep(2)  # Fixed 2-second delay for network errors
                        continue
                    else:
                        raise
            
            # If we get here, all retries failed - raise the last exception
            if last_exception:
                raise last_exception
            
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            raise
    
    def process_pdf(self, pdf_path: str, file_name: str, source_file_id: int, db_session=None) -> Dict[str, Any]:
        """Simplified PDF processing with summarization."""
        try:
            logger.info(f"Processing PDF: {pdf_path} (Source File ID: {source_file_id})")
            
            # Step 1: Use PyMuPDF processor to extract and process PDF
            # Get file_url from the database session
            file_url = None
            if db_session:
                source_file_obj = db_session.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
                if source_file_obj:
                    file_url = source_file_obj.file_url
            
            documents = self.pdf_processor.process_pdf(pdf_path, file_name, file_url)
            
            # Check if no documents were extracted
            if not documents:
                logger.warning(f"No content could be extracted from PDF: {file_name}")
                return {
                    "success": False,
                    "error": "No content could be extracted from PDF"
                }
            
            # Step 2: Get source file for metadata and save documents
            # Use provided session or create a new one
            if db_session:
                db = db_session
                own_session = False
            else:
                # Don't use context manager, create session directly
                from database.database import get_db_session
                db = get_db_session()
                own_session = True
            
            try:
                source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
                
                if not source_file:
                    logger.error(f"Source file not found: {source_file_id}")
                    return {
                        "success": False,
                        "error": f"Source file not found: {source_file_id}"
                    }
                
                # Step 3: Add drug_name to metadata for each document
                for doc in documents:
                    doc['metadata']['drug_name'] = source_file.drug_name or "Unknown"
                
                # Step 4: Save documents to database
                document_ids = save_documents_to_db(
                    db=db,
                    source_file_id=source_file_id,
                    file_name=file_name,
                    documents=documents
                )
                
                logger.info(f"Successfully saved {len(documents)} processed documents")
                
                # Step 5: Update source file status to DOCUMENT_STORED
                source_file.status = 'DOCUMENT_STORED'
                source_file.comments = f"Processed successfully with PyMuPDF. {len(documents)} documents created."
                
                # Always commit to ensure status is saved
                db.commit()
                logger.info(f"Updated source file status to DOCUMENT_STORED")
                
                return {
                    "success": True,
                    "document_ids": document_ids,
                    "documents_count": len(documents),
                    "source_file_id": source_file_id
                }
            finally:
                if own_session:
                    db.close()
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def save_results_to_json(self, results: Dict[str, Any], file_name: str) -> str:
        """Save processing results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"{file_name}_results_{timestamp}.json"
        json_path = os.path.join(settings.JSON_OUTPUT_DIR, json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {json_path}")
        return json_path
    
    def process_source_file(self, source_file: SourceFiles, db_session=None) -> Dict[str, Any]:
        """Process a source file from the database using simplified pipeline."""
        start_time = datetime.now()
        logger.info(f"Starting simplified FDA pipeline for: {source_file.file_name} (ID: {source_file.id})")
        
        try:
            # Step 1: Download PDF
            pdf_path = self.download_pdf(source_file.file_url, source_file.file_name)
            
            # Step 2: Process PDF with simplified approach
            processing_results = self.process_pdf(pdf_path, source_file.file_name, source_file.id, db_session)
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            processing_results["processing_time_seconds"] = processing_time
            processing_results["start_time"] = start_time.isoformat()
            processing_results["end_time"] = end_time.isoformat()
            
            logger.info(f"Simplified pipeline completed in {processing_time:.2f} seconds")
            return processing_results
            
        except Exception as e:
            logger.error(f"Simplified pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds()
            }

def process_pending_files():
    """Process all pending files from the database."""
    print("="*80)
    print("FDA DOCUMENT BATCH PROCESSOR V2")
    print("="*80)
    
    # Initialize pipeline
    pipeline = FDAPipelineV2()
    
    # Get database session and process files
    with database_session() as db:
        # Get all pending files
        pending_files = db.query(SourceFiles).filter(SourceFiles.status == "PENDING").all()
        
        if not pending_files:
            print("\nNo pending files to process.")
            return
        
        print(f"\nFound {len(pending_files)} pending files to process:")
        print("-" * 80)
        for file in pending_files:
            print(f"ID: {file.id} | File: {file.file_name}")
            print(f"   URL: {file.file_url}")
            print(f"   Category: {file.comments}")
        print("-" * 80)
        
        # Process each file
        successful = 0
        failed = 0
        
        for i, file in enumerate(pending_files, 1):
            print(f"\n[{i}/{len(pending_files)}] Processing: {file.file_name}")
            print("=" * 80)
            
            try:
                # Update status to PROCESSING
                update_source_file_status(db, file.id, "PROCESSING")
                
                # Process the source file
                results = pipeline.process_source_file(file)
                
                if results.get("success"):
                    # Update status to READY (ready for vector DB loading)
                    update_source_file_status(
                        db, 
                        file.id, 
                        "READY",
                        f"Processed successfully with PyMuPDF. {results.get('documents_count', 0)} documents created. Ready for vector DB."
                    )
                    successful += 1
                    print(f"✅ Successfully processed: {file.file_name} - Status: READY")
                else:
                    # Update status to FAILED
                    error_msg = results.get("error", "Unknown error")
                    update_source_file_status(db, file.id, "FAILED", f"Error: {error_msg}")
                    failed += 1
                    print(f"❌ Failed to process: {file.file_name} - {error_msg}")
                
            except Exception as e:
                # Update status to FAILED
                update_source_file_status(db, file.id, "FAILED", f"Exception: {str(e)}")
                failed += 1
                print(f"❌ Exception processing {file.file_name}: {e}")
        
        # Summary
        print("\n" + "=" * 80)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total files processed: {len(pending_files)}")
        print(f"✅ Successful (READY): {successful}")
        print(f"❌ Failed: {failed}")
        print("=" * 80)
        
        # Show final status
        print("\nFinal status of all files:")
        print("-" * 80)
        all_files = db.query(SourceFiles).all()
        for file in all_files:
            print(f"ID: {file.id} | File: {file.file_name} | Status: {file.status}")
            if file.comments:
                print(f"   Comments: {file.comments}")
        print("-" * 80)

def main():
    """Main function to run the FDA pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FDA RAG Pipeline V2")
    parser.add_argument(
        "--process-pending",
        action="store_true",
        help="Process all pending files from database"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="URL to download and process"
    )
    parser.add_argument(
        "--filename",
        type=str,
        help="Filename for the downloaded PDF"
    )
    
    args = parser.parse_args()
    
    if args.process_pending:
        process_pending_files()
    elif args.url and args.filename:
        # Single file processing (creates a temporary source file record)
        print("="*80)
        print("FDA RAG PIPELINE V2")
        print("="*80)
        
        pipeline = FDAPipelineV2()
        
        with database_session() as db:
            # Create temporary source file record
            source_file = SourceFiles(
                file_name=args.filename,
                file_url=args.url,
                status="PROCESSING",
                comments="Manual processing"
            )
            db.add(source_file)
            db.commit()
            db.refresh(source_file)
            
            # Process the file
            results = pipeline.process_source_file(source_file)
            
            # Update status based on results
            if results.get("success"):
                update_source_file_status(
                    db, 
                    source_file.id, 
                    "READY",
                    f"Processed successfully with PyMuPDF. {results.get('documents_count', 0)} documents created. Ready for vector DB."
                )
                print(f"✅ Pipeline completed successfully! Status: READY")
            else:
                update_source_file_status(
                    db, 
                    source_file.id, 
                    "FAILED",
                    f"Error: {results.get('error', 'Unknown error')}"
                )
                print(f"❌ Pipeline failed! Error: {results.get('error', 'Unknown error')}")
    else:
        print("Usage:")
        print("  Process pending files: python fda_pipeline_v2.py --process-pending")
        print("  Process single file: python fda_pipeline_v2.py --url <URL> --filename <filename>")

if __name__ == "__main__":
    main()