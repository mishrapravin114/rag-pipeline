#!/bin/bash
# Script to remove empty commits from git history

echo "🔍 Finding empty commits..."

# Get list of commits
git log --oneline --reverse > /tmp/commits.txt

empty_count=0
while IFS= read -r line; do
    commit=$(echo "$line" | awk '{print $1}')
    # Check if commit has 0 files changed
    if git show --stat "$commit" 2>/dev/null | grep -q "0 files changed"; then
        echo "Empty: $commit"
        empty_count=$((empty_count + 1))
    fi
done < /tmp/commits.txt

echo ""
echo "Found $empty_count empty commits"
echo ""
echo "To remove them, use interactive rebase:"
echo "  git rebase -i --root"
echo "Then mark empty commits as 'drop' or 'd'"
