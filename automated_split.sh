#!/bin/bash
# Semi-automated commit splitting script
# This helps automate the date setting part

set -e

echo "🚀 Automated Git History Redistribution"
echo "========================================"
echo ""

# Check if backup exists
if ! git branch | grep -q "backup-before-redistribute"; then
    echo "📦 Creating backup branch..."
    git branch backup-before-redistribute-$(date +%Y%m%d-%H%M%S)
    echo "✅ Backup created"
fi

echo ""
echo "📋 Current commit count: $(git rev-list --count HEAD)"
echo ""
echo "⚠️  IMPORTANT: This script will help you, but you need to:"
echo "   1. Manually split commits using 'git rebase -i --root'"
echo "   2. Use the date setting function below"
echo ""
echo "📖 Full instructions in SPLIT_COMMITS_GUIDE.md"
echo ""
echo "🔧 To set a commit date, use:"
echo "   GIT_AUTHOR_DATE='YYYY-MM-DD HH:MM:SS' \\"
echo "   GIT_COMMITTER_DATE='YYYY-MM-DD HH:MM:SS' \\"
echo "   git commit --amend --no-edit --date='YYYY-MM-DD HH:MM:SS'"
echo ""
echo "📅 See commit_date_schedule.txt for dates"
echo "💬 See commit_messages.txt for messages"
echo ""
echo "Ready to start? Run: git rebase -i --root"

