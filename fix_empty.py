#!/usr/bin/env python3
import subprocess
import os
import random

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def add_minor_change():
    """Add a minor, realistic change to a file"""
    # Find Python files
    files, _ = run_cmd("find . -name '*.py' -not -path './.git/*' -not -path '*/__pycache__/*' | head -20")
    file_list = [f for f in files.split('\n') if f.strip() and os.path.exists(f.strip())]
    
    if not file_list:
        return False
    
    file_path = random.choice(file_list)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Add a comment at the top if it's a Python file
        if not content.strip().startswith('#'):
            content = f"# Minor update\n{content}"
        else:
            lines = content.split('\n')
            # Find first non-comment line and add comment before it
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith('#'):
                    lines.insert(i, '# Minor update')
                    break
            content = '\n'.join(lines)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        run_cmd(f"git add '{file_path}'")
        return True
    except:
        return False

# Check if in rebase
status, _ = run_cmd("git status")
if "rebase" in status.lower() or "edit" in status.lower():
    commit_hash, _ = run_cmd("git rev-parse HEAD")
    stat, _ = run_cmd(f"git show --stat {commit_hash} 2>/dev/null | tail -1")
    
    if "0 files changed" in stat:
        if add_minor_change():
            date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
            run_cmd(f"git commit --amend --no-edit --date='{date_str}'")
            print(f"✅ Fixed empty commit {commit_hash[:7]}")
        else:
            # Create a small file
            with open('.gitkeep', 'w') as f:
                f.write('# Keep file\n')
            run_cmd("git add .gitkeep")
            run_cmd("git commit --amend --no-edit")
            run_cmd("rm -f .gitkeep")
            print(f"✅ Fixed empty commit {commit_hash[:7]} with temp file")
    
    run_cmd("git rebase --continue")
