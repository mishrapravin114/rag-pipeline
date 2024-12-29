#!/bin/bash
# Automated Git History Redistribution
# This script automates the commit splitting and dating process

set -e

echo "🚀 Automated Git History Redistribution"
echo "========================================"
echo ""

# Create backup if not exists
if ! git branch | grep -q "backup-before-redistribute"; then
    echo "📦 Creating backup branch..."
    git branch backup-before-redistribute-$(date +%Y%m%d-%H%M%S)
    echo "✅ Backup created"
fi

echo "📋 Current commits: $(git rev-list --count HEAD)"
echo ""

# Prepare the rebase todo list automatically
echo "🔧 Preparing automated rebase..."
cat > /tmp/rebase_todo << 'EOF'
edit 7dd71eb Initial commit
edit 8f49cbf feat(SG-01) - add initial commit
edit f5b03d9 add documentation, fix dependencies
edit a898079 refactor to make th knowledge terms generic
edit 4ff8eb3 refactor to make th knowledge terms generic
edit aa5bb04 Fix - Readme year
edit f2ca7f9 Add README.md
edit e316c47 Merge branch 'main'
edit 92f8156 Fix database schema migration
edit e6dc0fa remove unrequired symbols
EOF

echo "✅ Rebase todo prepared"
echo ""
echo "⚠️  This will start an interactive rebase."
echo "    The script has prepared all commits to be edited."
echo ""
echo "📖 You'll need to manually split each commit when Git stops."
echo "   Follow the instructions in SPLIT_COMMITS_GUIDE.md"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 1
fi

# Set GIT_SEQUENCE_EDITOR to use our prepared todo
export GIT_SEQUENCE_EDITOR="cp /tmp/rebase_todo"

# Start rebase
echo "🚀 Starting rebase..."
git rebase -i --root

echo ""
echo "✅ Rebase started!"
echo "📝 When Git stops at each commit:"
echo "   1. Run: git reset HEAD^"
echo "   2. Split into smaller commits"
echo "   3. Set dates using dates from commit_date_schedule.txt"
echo "   4. Run: git rebase --continue"
echo ""
echo "📅 Use this format to set dates:"
echo "   GIT_AUTHOR_DATE='2025-03-05 14:30:00' \\"
echo "   GIT_COMMITTER_DATE='2025-03-05 14:30:00' \\"
echo "   git commit --amend --no-edit --date='2025-03-05 14:30:00'"

