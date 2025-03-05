"""
Seed data script to read Excel file and populate SourceFiles table
"""
import pandas as pd
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from database import (
    SourceFiles, SessionLocal, create_tables,
    FDAExtractionResults, DocumentData, ChatHistory,
    SearchHistory, TrendingSearches, EntitySections
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_excel_data(file_path: str) -> pd.DataFrame:
    """Read Excel file and return DataFrame"""
    try:
        df = pd.read_excel(file_path)
        logger.info(f"Successfully read Excel file: {file_path}")
        logger.info(f"Found {len(df)} rows in Excel file")
        logger.info(f"Columns: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"Error reading Excel file {file_path}: {e}")
        return pd.DataFrame()

def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean the data"""
    required_columns = ['file_name', 'pdf_url', 'categories_or_approval_type']
    
    # Check if required columns exist
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing required columns: {missing_columns}")
        return pd.DataFrame()
    
    # Remove rows with missing file_name or pdf_url
    initial_count = len(df)
    df = df.dropna(subset=['file_name', 'pdf_url'])
    final_count = len(df)
    
    if initial_count != final_count:
        logger.warning(f"Removed {initial_count - final_count} rows with missing file_name or pdf_url")
    
    # Fill missing categories with 'Unknown'
    df['categories_or_approval_type'] = df['categories_or_approval_type'].fillna('Unknown')
    
    return df

def seed_source_files(df: pd.DataFrame, replace_existing: bool = False):
    """Seed SourceFiles table with data from DataFrame"""
    
    # Create tables if they don't exist
    create_tables()
    
    db = SessionLocal()
    added_count = 0
    updated_count = 0
    error_count = 0
    
    try:
        for index, row in df.iterrows():
            try:
                file_name = str(row['file_name']).strip()
                pdf_url = str(row['pdf_url']).strip()
                categories = str(row['categories_or_approval_type']).strip()
                
                # Check if file already exists
                existing_file = db.query(SourceFiles).filter(
                    SourceFiles.file_name == file_name
                ).first()
                
                if existing_file:
                    if replace_existing:
                        # Update existing record
                        existing_file.file_url = pdf_url
                        existing_file.status = "PENDING"
                        existing_file.comments = f"Category: {categories}"
                        updated_count += 1
                        logger.info(f"Updated existing file: {file_name}")
                    else:
                        logger.info(f"File already exists (skipping): {file_name}")
                        continue
                else:
                    # Create new record
                    source_file = SourceFiles(
                        file_name=file_name,
                        file_url=pdf_url,
                        status="PENDING",
                        comments=f"Category: {categories}"
                    )
                    db.add(source_file)
                    added_count += 1
                    logger.info(f"Added new file: {file_name}")
                
            except Exception as e:
                logger.error(f"Error processing row {index}: {e}")
                logger.error(f"Row data: {dict(row)}")
                error_count += 1
                continue
        
        # Commit all changes
        db.commit()
        
        logger.info("="*80)
        logger.info("SEEDING SUMMARY")
        logger.info("="*80)
        logger.info(f"Total rows processed: {len(df)}")
        logger.info(f"Files added: {added_count}")
        logger.info(f"Files updated: {updated_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error during database operations: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def list_seeded_files():
    """List all files that were seeded from Excel"""
    db = SessionLocal()
    try:
        files = db.query(SourceFiles).filter(
            SourceFiles.comments.like("Category:%")
        ).all()
        
        logger.info(f"\nFound {len(files)} files seeded from Excel:")
        logger.info("-" * 120)
        logger.info(f"{'ID':<5} {'File Name':<40} {'Status':<12} {'Category':<25} {'Created'}")
        logger.info("-" * 120)
        
        for file in files:
            category = file.comments.replace("Category: ", "") if file.comments else "Unknown"
            logger.info(f"{file.id:<5} {file.file_name[:40]:<40} {file.status:<12} {category[:25]:<25} {file.created_at}")
        
        logger.info("-" * 120)
        
    except Exception as e:
        logger.error(f"Error listing seeded files: {e}")
    finally:
        db.close()

def clear_seeded_files():
    """Clear all files that were seeded from Excel"""
    db = SessionLocal()
    try:
        files = db.query(SourceFiles).filter(
            SourceFiles.comments.like("Category:%")
        ).all()
        
        count = len(files)
        for file in files:
            db.delete(file)
        
        db.commit()
        logger.info(f"Cleared {count} seeded files from database")
        
    except Exception as e:
        logger.error(f"Error clearing seeded files: {e}")
        db.rollback()
    finally:
        db.close()


def reset_database():
    """Reset database: clear all tables except SourceFiles and update all SourceFiles to PENDING status"""
    
    # Create tables if they don't exist
    create_tables()
    
    db = SessionLocal()
    
    try:
        logger.info("="*80)
        logger.info("RESETTING DATABASE")
        logger.info("="*80)
        
        # Clear all tables except SourceFiles
        tables_to_clear = [
            (FDAExtractionResults, "FDAExtractionResults"),
            (DocumentData, "DocumentData"),
            (ChatHistory, "ChatHistory"),
            (SearchHistory, "SearchHistory"),
            (TrendingSearches, "TrendingSearches"),
            (EntitySections, "EntitySections")
        ]
        
        for table_class, table_name in tables_to_clear:
            try:
                count = db.query(table_class).count()
                db.query(table_class).delete()
                db.commit()
                logger.info(f"✓ Cleared {count} records from {table_name}")
            except Exception as e:
                logger.error(f"Error clearing {table_name}: {e}")
                db.rollback()
        
        # Update all SourceFiles to PENDING status
        try:
            source_files = db.query(SourceFiles).all()
            updated_count = 0
            
            for file in source_files:
                if file.status != "PENDING":
                    file.status = "PENDING"
                    updated_count += 1
            
            db.commit()
            logger.info(f"✓ Updated {updated_count} SourceFiles to PENDING status")
            logger.info(f"✓ Total SourceFiles in database: {len(source_files)}")
            
        except Exception as e:
            logger.error(f"Error updating SourceFiles status: {e}")
            db.rollback()
            raise
        
        logger.info("="*80)
        logger.info("DATABASE RESET COMPLETE")
        logger.info("="*80)
        logger.info("- All tables cleared except SourceFiles")
        logger.info("- All SourceFiles updated to PENDING status")
        logger.info("- Database ready for fresh processing")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error during database reset: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def seed_entitie_entries():
    """Seed specific entity entries with Pending status"""
    
    # Create tables if they don't exist
    create_tables()
    
    entitie_entries = [
        # Augtyro : Repotrectinib
        {
            "file_name": "augtyro_original_approved_218213s000lbl.pdf",
            "file_url": "https://www.accessdata.fda.gov/entitiesatfda_docs/label/2023/218213s000lbl.pdf",
            "comments": "Category: Original Approval - Augtyro (Repotrectinib)"
        },
        {
            "file_name": "augtyro_efficacy_approved_218213s001lbl.pdf",
            "file_url": "https://www.accessdata.fda.gov/entitiesatfda_docs/label/2024/218213s001lbl.pdf",
            "comments": "Category: Efficacy Approval - Augtyro (Repotrectinib)"
        },
        
        # Krazati : Adagrasib
        {
            "file_name": "krazati_original_approved_216340Orig1s000Corrected_lbl.pdf",
            "file_url": "http://www.accessdata.fda.gov/entitiesatfda_docs/label/2022/216340Orig1s000Corrected_lbl.pdf",
            "comments": "Category: Original Approval - Krazati (Adagrasib)"
        },
        {
            "file_name": "krazati_efficacy_approved_216340s005lbl.pdf",
            "file_url": "https://www.accessdata.fda.gov/entitiesatfda_docs/label/2024/216340s005lbl.pdf",
            "comments": "Category: Efficacy Approval - Krazati (Adagrasib)"
        },
        
        # Jemperli : Dostarlimab
        {
            "file_name": "jemperli_original_approved_761174s000lbl.pdf",
            "file_url": "http://www.accessdata.fda.gov/entitiesatfda_docs/label/2021/761174s000lbl.pdf",
            "comments": "Category: Original Approval - Jemperli (Dostarlimab)"
        },
        {
            "file_name": "jemperli_efficacy_approved_761174s009lbl.pdf",
            "file_url": "http://www.accessdata.fda.gov/entitiesatfda_docs/label/2024/761174s009lbl.pdf",
            "comments": "Category: Efficacy Approval - Jemperli (Dostarlimab)"
        },
        
        # Gavreto : Pralsetinib
        {
            "file_name": "gavreto_original_approved_213721s000lbl.pdf",
            "file_url": "http://www.accessdata.fda.gov/entitiesatfda_docs/label/2020/213721s000lbl.pdf",
            "comments": "Category: Original Approval - Gavreto (Pralsetinib)"
        },
        {
            "file_name": "gavreto_efficacy_approved_213721s009lbl.pdf",
            "file_url": "http://www.accessdata.fda.gov/entitiesatfda_docs/label/2023/213721s009lbl.pdf",
            "comments": "Category: Efficacy Approval - Gavreto (Pralsetinib)"
        }
    ]
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        for entry in entitie_entries:
            try:
                # Check if file already exists
                existing_file = db.query(SourceFiles).filter(
                    SourceFiles.file_name == entry["file_name"]
                ).first()
                
                if existing_file:
                    logger.info(f"File already exists (skipping): {entry['file_name']}")
                    skipped_count += 1
                    continue
                
                # Create new record
                source_file = SourceFiles(
                    file_name=entry["file_name"],
                    file_url=entry["file_url"],
                    status="PENDING",
                    comments=entry["comments"]
                )
                db.add(source_file)
                added_count += 1
                logger.info(f"Added new entity entry: {entry['file_name']}")
                
            except Exception as e:
                logger.error(f"Error processing entry {entry['file_name']}: {e}")
                error_count += 1
                continue
        
        # Commit all changes
        db.commit()
        
        logger.info("="*80)
        logger.info("DRUG ENTRIES SEEDING SUMMARY")
        logger.info("="*80)
        logger.info(f"Total entries processed: {len(entitie_entries)}")
        logger.info(f"Files added: {added_count}")
        logger.info(f"Files skipped (already exist): {skipped_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error during database operations: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """Main function with command options"""
    import sys
    
    excel_file_path = "data/source_details.xlsx"
    
    if not Path(excel_file_path).exists():
        logger.error(f"Excel file not found: {excel_file_path}")
        return
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "seed":
            # Read and validate Excel data
            df = read_excel_data(excel_file_path)
            if df.empty:
                logger.error("No data to seed")
                return
            
            df = validate_data(df)
            if df.empty:
                logger.error("No valid data to seed")
                return
            
            # Seed the database
            replace_existing = "--replace" in sys.argv
            seed_source_files(df, replace_existing=replace_existing)
            
        elif command == "list":
            list_seeded_files()
            
        elif command == "clear":
            clear_seeded_files()
            
        elif command == "preview":
            # Preview Excel data without seeding
            df = read_excel_data(excel_file_path)
            if not df.empty:
                logger.info("\nPreview of Excel data:")
                logger.info("-" * 80)
                logger.info(df.head(10).to_string(index=False))
                logger.info(f"\nTotal rows: {len(df)}")
                
        elif command == "seed-entities":
            # Seed specific entity entries
            seed_entitie_entries()
            
        elif command == "reset":
            # Reset database
            confirm = input("\n⚠️  WARNING: This will clear all data except SourceFiles and reset all files to PENDING status.\nAre you sure? (yes/no): ").strip().lower()
            if confirm == "yes":
                reset_database()
            else:
                print("Reset cancelled.")
            
        else:
            print("Unknown command. Available commands:")
            print("  python seed_data.py seed [--replace]  - Seed database from Excel")
            print("  python seed_data.py list              - List seeded files")
            print("  python seed_data.py clear             - Clear seeded files")
            print("  python seed_data.py preview           - Preview Excel data")
            print("  python seed_data.py seed-entities        - Seed specific entity entries")
            print("  python seed_data.py reset             - Reset database (clear all except SourceFiles, set all to PENDING)")
    else:
        print("Available commands:")
        print("  python seed_data.py seed [--replace]  - Seed database from Excel file")
        print("  python seed_data.py list              - List all seeded files")
        print("  python seed_data.py clear             - Clear all seeded files")
        print("  python seed_data.py preview           - Preview Excel data without seeding")
        print("  python seed_data.py seed-entities        - Seed specific entity entries")
        print("  python seed_data.py reset             - Reset database (clear all except SourceFiles, set all to PENDING)")
        print("")
        print("Options:")
        print("  --replace                             - Replace existing files when seeding")
        print("")
        print(f"Excel file path: {excel_file_path}")

if __name__ == "__main__":
    main() 