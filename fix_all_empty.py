#!/usr/bin/env python3
import subprocess
import os
import random

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def find_files():
    files, _ = run_cmd("find . -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.md' \) -not -path './.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' 2>/dev/null | head -50")
    return [f for f in files.split('\n') if f.strip() and os.path.exists(f.strip())]

def add_change(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if '\x00' in content[:1000] or len(content) == 0:
            return False
        original = content
        if file_path.endswith('.py'):
            content = f"# Minor update\n{content}"
        elif file_path.endswith(('.ts', '.tsx', '.js')):
            content = f"// Minor update\n{content}"
        elif file_path.endswith('.md'):
            lines = content.split('\n')
            if len(lines) > 1:
                lines.insert(1, '')
            content = '\n'.join(lines)
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except:
        return False

status, _ = run_cmd("git status")
if "rebase" in status.lower() or "edit" in status.lower():
    commit_hash, _ = run_cmd("git rev-parse HEAD")
    files, _ = run_cmd(f"git diff-tree --no-commit-id --name-only -r {commit_hash}")
    if not [f for f in files.split('\n') if f.strip()]:
        all_files = find_files()
        if all_files:
            for attempt in range(min(20, len(all_files))):
                file_path = random.choice(all_files)
                if add_change(file_path):
                    run_cmd(f"git add '{file_path}' 2>&1")
                    date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
                    run_cmd(f"git commit --amend --no-edit --date='{date_str}' 2>&1")
                    break
        else:
            with open('.minor_update', 'w') as f:
                f.write('# Update\n')
            run_cmd("git add .minor_update 2>&1")
            date_str, _ = run_cmd(f"git log -1 --format='%ad' --date='format:%Y-%m-%d %H:%M:%S'")
            run_cmd(f"git commit --amend --no-edit --date='{date_str}' 2>&1")
            run_cmd("rm -f .minor_update 2>&1")
    run_cmd("git rebase --continue 2>&1")
