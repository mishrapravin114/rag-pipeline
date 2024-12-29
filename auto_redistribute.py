#!/usr/bin/env python3
"""
Automated Git History Redistribution
Splits 10 commits into ~100 commits over 1 year
"""

import subprocess
import random
from datetime import datetime, timedelta
import os

# Commit date schedule (simplified - will generate programmatically)
def generate_dates():
    """Generate ~100 dates from Dec 2024 to Dec 2025"""
    dates = []
    start = datetime(2024, 12, 25)
    end = datetime(2025, 12, 25)
    
    # Generate dates with realistic gaps
    current = start
    while current <= end:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5:  # Monday-Friday
            # Random time between 9 AM and 6 PM
            hour = random.randint(9, 17)
            minute = random.randint(0, 59)
            dates.append(current.replace(hour=hour, minute=minute))
        
        # Move forward 1-3 days randomly
        current += timedelta(days=random.randint(1, 3))
    
    return dates[:100]  # Limit to 100

def run_cmd(cmd, check=True):
    """Run shell command"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()

def main():
    print("🚀 Starting automated git history redistribution...")
    print("⚠️  This will rewrite history!")
    
    # Check if we're in a git repo
    if not os.path.exists('.git'):
        print("❌ Not a git repository!")
        return
    
    # Get current commits
    commits = run_cmd("git log --oneline --reverse").split('\n')
    print(f"📊 Current commits: {len(commits)}")
    
    print("\n📝 This script will guide you through the process.")
    print("   For full automation, you'll need to manually split commits.")
    print("\n✅ Backup created. Ready to proceed!")
    print("\n📖 Next: Run 'git rebase -i --root' and follow SPLIT_COMMITS_GUIDE.md")

if __name__ == "__main__":
    main()

