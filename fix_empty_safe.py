#!/usr/bin/env python3
"""Fix empty commits during rebase"""
import subprocess
import os
import random

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def find_files():
    """Find files to modify"""
    files, _ = run_cmd("find . -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.md' -o -name '*.yml' -o -name '*.yaml' \) -not -path './.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -path '*/.next/*' 2>/dev/null | head -100")
    return [f for f in files.split('\n') if f.strip() and os.path.exists(f.strip())]

def add_minor_change(file_path):
    """Add a minor change"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if '\x00' in content[:1000] or len(content) == 0:
            return False
        
        original = content
        
        if file_path.endswith('.py'):
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if (line.strip().startswith('def ') or line.strip().startswith('class ')) and i > 0:
                    if not lines[i-1].strip().startswith('#'):
                        lines.insert(i, '    # Minor update')
                        break
            else:
                if not content.strip().startswith('#'):
                    lines.insert(0, '# Minor update')
            content = '\n'.join(lines)
        
        elif file_path.endswith(('.ts', '.tsx', '.js')):
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if ('export ' in line or 'function ' in line) and i > 0:
                    if not lines[i-1].strip().startswith('//'):
                        lines.insert(i, '// Minor update')
                        break
            else:
                if not content.strip().startswith('//'):
                    lines.insert(0, '// Minor update')
            content = '\n'.join(lines)
        
        elif file_path.endswith('.md'):
            lines = content.split('\n')
            if len(lines) > 1:
                lines.insert(1, '')
            content = '\n'.join(lines)
        
        elif file_path.endswith(('.yml', '.yaml')):
            lines = content.split('\n')
            if lines and len(lines) > 1 and not lines[1].strip().startswith('#'):
                lines.insert(1, '# Minor update')
            content = '\n'.join(lines)
        
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except:
        return False

# Main
status, _ = run_cmd("git status")
if "rebase" in status.lower() or "edit" in status.lower():
    commit_hash, _ = run_cmd("git rev-parse HEAD")
    files, _ = run_cmd(f"git diff-tree --no-commit-id --name-only -r {commit_hash}")
    file_list = [f for f in files.split('\n') if f.strip()]
    
    if len(file_list) == 0:
        # Empty commit - fix it
        all_files = find_files()
        if all_files:
            modified = False
            for attempt in range(min(10, len(all_files))):
                file_path = random.choice(all_files)
                if add_minor_change(file_path):
                    run_cmd(f"git add '{file_path}' 2>&1")
                    date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
                    run_cmd(f"git commit --amend --no-edit --date='{date_str}' 2>&1")
                    print(f"✅ Fixed {commit_hash[:7]}")
                    modified = True
                    break
            
            if not modified:
                with open('.minor_update', 'w') as f:
                    f.write('# Update\n')
                run_cmd("git add .minor_update 2>&1")
                date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
                run_cmd(f"git commit --amend --no-edit --date='{date_str}' 2>&1")
                run_cmd("rm -f .minor_update 2>&1")
                print(f"✅ Fixed {commit_hash[:7]}")
        else:
            with open('.minor_update', 'w') as f:
                f.write('# Update\n')
            run_cmd("git add .minor_update 2>&1")
            date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
            run_cmd(f"git commit --amend --no-edit --date='{date_str}' 2>&1")
            run_cmd("rm -f .minor_update 2>&1")
            print(f"✅ Fixed {commit_hash[:7]}")
    
    # Continue rebase
    run_cmd("git rebase --continue 2>&1")
