#!/usr/bin/env python3
"""
Production Deployment Script for Metadata Groups Feature
Deploys changes from commit 6ddd76fc to latest metadata groups changes
"""

import subprocess
import sys
import time
import os
from datetime import datetime
from typing import Tuple, List
import json

class DeploymentScript:
    def __init__(self):
        self.backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        self.errors = []
        self.completed_steps = []
        
    def run_command(self, command: str, description: str, critical: bool = True) -> Tuple[bool, str]:
        """Execute a shell command and return success status and output"""
        print(f"\n{'='*60}")
        print(f"🔄 {description}")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print(f"✅ SUCCESS: {description}")
                self.completed_steps.append(description)
                return True, result.stdout
            else:
                error_msg = f"❌ FAILED: {description}\nError: {result.stderr}"
                print(error_msg)
                self.errors.append(error_msg)
                
                if critical:
                    self.rollback()
                    sys.exit(1)
                    
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            error_msg = f"⏱️ TIMEOUT: {description} (exceeded 5 minutes)"
            print(error_msg)
            self.errors.append(error_msg)
            
            if critical:
                self.rollback()
                sys.exit(1)
                
            return False, "Command timed out"
            
        except Exception as e:
            error_msg = f"💥 EXCEPTION: {description}\nError: {str(e)}"
            print(error_msg)
            self.errors.append(error_msg)
            
            if critical:
                self.rollback()
                sys.exit(1)
                
            return False, str(e)
    
    def confirm_step(self, message: str) -> bool:
        """Ask for user confirmation before proceeding"""
        response = input(f"\n❓ {message} (yes/no): ").lower().strip()
        return response in ['yes', 'y']
    
    def backup_database(self):
        """Create database backup"""
        success, _ = self.run_command(
            f"docker-compose exec -T mysql mysqldump -u fda_user -pfda_password fda_rag > {self.backup_file}",
            "Creating database backup"
        )
        
        if success:
            # Verify backup file
            if os.path.exists(self.backup_file):
                size = os.path.getsize(self.backup_file)
                print(f"📁 Backup file created: {self.backup_file} ({size:,} bytes)")
            else:
                print("⚠️ Warning: Backup file not found!")
    
    def run_migrations(self):
        """Run all database migrations in order"""
        
        # Migration 1: Create metadata extraction tables
        migration1_sql = '''
from src.database.database import engine
from sqlalchemy import text

print("Creating metadata extraction tables...")

with engine.connect() as conn:
    # Create metadata_extraction_jobs table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS metadata_extraction_jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            collection_id INT NOT NULL,
            status VARCHAR(50) NOT NULL,
            total_documents INT DEFAULT 0,
            processed_documents INT DEFAULT 0,
            failed_documents INT DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            error_message TEXT,
            initiated_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            FOREIGN KEY (initiated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """))
    
    # Create document_metadata_extractions table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS document_metadata_extractions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            document_id INT NOT NULL,
            metadata_config_id INT NOT NULL,
            extracted_value TEXT,
            confidence_score FLOAT,
            status VARCHAR(50) NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES metadata_extraction_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (metadata_config_id) REFERENCES metadata_configurations(id) ON DELETE CASCADE,
            UNIQUE KEY unique_extraction (job_id, document_id, metadata_config_id)
        )
    """))
    
    conn.commit()
    print("✅ Metadata extraction tables created successfully!")
'''
        
        self.run_command(
            f'docker-compose exec backend python -c "{migration1_sql}"',
            "Migration 1: Creating metadata extraction tables"
        )
        
        # Migration 2: Metadata groups consolidation
        self.run_command(
            'docker-compose exec backend bash -c "cd /app && python backend/migrations/add_metadata_groups_consolidation_fixed.py"',
            "Migration 2: Metadata groups consolidation"
        )
        
        # Migration 3: Add group-specific display order
        self.run_command(
            'docker-compose exec backend bash -c "cd /app && python backend/migrations/add_group_specific_display_order.py"',
            "Migration 3: Adding group-specific display order"
        )
        
        # Verify migrations
        self.run_command(
            'docker-compose exec backend bash -c "cd /app && python backend/migrations/verify_migration_order.py"',
            "Verifying all migrations",
            critical=False
        )
    
    def deploy_code(self):
        """Pull latest code and rebuild containers"""
        # Git pull
        self.run_command(
            "git pull origin master",
            "Pulling latest code from repository"
        )
        
        # Build containers
        self.run_command(
            "docker-compose build --no-cache backend frontend",
            "Building backend and frontend containers"
        )
        
        # Restart services
        self.run_command(
            "docker-compose up -d",
            "Starting services"
        )
        
        # Wait for services to be ready
        print("\n⏳ Waiting for services to start...")
        time.sleep(10)
    
    def verify_deployment(self):
        """Verify the deployment was successful"""
        print("\n🔍 Running deployment verification...")
        
        # Check backend health
        success, _ = self.run_command(
            "curl -f http://localhost:8090/health",
            "Checking backend health",
            critical=False
        )
        
        # Check frontend
        success, _ = self.run_command(
            "curl -f -s -o /dev/null -w '%{http_code}' http://localhost:3001",
            "Checking frontend availability",
            critical=False
        )
        
        # Check for errors in logs
        self.run_command(
            "docker-compose logs --tail=50 backend 2>&1 | grep -i error || true",
            "Checking backend logs for errors",
            critical=False
        )
        
        self.run_command(
            "docker-compose logs --tail=50 frontend 2>&1 | grep -i error || true",
            "Checking frontend logs for errors",
            critical=False
        )
    
    def rollback(self):
        """Rollback procedure in case of failure"""
        print("\n🔄 INITIATING ROLLBACK PROCEDURE...")
        
        if not self.confirm_step("Do you want to perform rollback?"):
            return
            
        # Restore database
        if os.path.exists(self.backup_file):
            print(f"📥 Restoring database from {self.backup_file}")
            self.run_command(
                f"docker-compose exec -T mysql mysql -u fda_user -pfda_password fda_rag < {self.backup_file}",
                "Restoring database backup",
                critical=False
            )
        
        # Revert code
        self.run_command(
            "git reset --hard 6ddd76fc582e048d39d4e6c674e26438b70e43c2",
            "Reverting to previous code version",
            critical=False
        )
        
        # Rebuild and restart
        self.run_command(
            "docker-compose build --no-cache backend frontend && docker-compose up -d",
            "Rebuilding and restarting services",
            critical=False
        )
    
    def generate_report(self):
        """Generate deployment report"""
        print("\n" + "="*60)
        print("📊 DEPLOYMENT REPORT")
        print("="*60)
        
        print(f"\n✅ Completed Steps ({len(self.completed_steps)}):")
        for step in self.completed_steps:
            print(f"  - {step}")
        
        if self.errors:
            print(f"\n❌ Errors Encountered ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n🎉 No errors encountered!")
        
        print(f"\n💾 Backup File: {self.backup_file}")
        print(f"🕐 Deployment Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def run(self):
        """Main deployment execution"""
        print("🚀 METADATA GROUPS PRODUCTION DEPLOYMENT SCRIPT")
        print("="*60)
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💾 Backup will be saved as: {self.backup_file}")
        print("="*60)
        
        if not self.confirm_step("This script will deploy metadata groups changes to production. Continue?"):
            print("❌ Deployment cancelled by user")
            sys.exit(0)
        
        try:
            # Step 1: Backup
            self.backup_database()
            
            # Step 2: Optional - Stop services
            if self.confirm_step("Do you want to stop services during migration (recommended for data consistency)?"):
                self.run_command(
                    "docker-compose stop backend frontend",
                    "Stopping application services"
                )
            
            # Step 3: Run migrations
            self.run_migrations()
            
            # Step 4: Deploy code
            self.deploy_code()
            
            # Step 5: Verify deployment
            self.verify_deployment()
            
            # Generate report
            self.generate_report()
            
            print("\n✅ DEPLOYMENT COMPLETED SUCCESSFULLY!")
            print("📝 Please perform manual testing to ensure everything works correctly.")
            print("🔄 If issues arise, you can rollback using: python deploy_metadata_groups.py --rollback")
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Deployment interrupted by user!")
            if self.confirm_step("Do you want to rollback?"):
                self.rollback()
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            if self.confirm_step("Do you want to rollback?"):
                self.rollback()

if __name__ == "__main__":
    # Check for rollback flag
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        script = DeploymentScript()
        script.rollback()
    else:
        script = DeploymentScript()
        script.run()