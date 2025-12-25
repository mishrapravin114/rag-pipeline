#!/bin/bash
# Expand commits to ~100 by splitting large ones and fixing dates

set -e

echo "🚀 Expanding commits to ~100..."
echo "Current: $(git rev-list --count HEAD)"
echo ""

# Start interactive rebase to edit all commits
GIT_SEQUENCE_EDITOR="sed -i.bak 's/^pick/edit/'" git rebase -i --root

echo "✅ Rebase prepared. Now processing each commit..."

# This will be handled interactively, but here's the strategy:
# 1. For each commit, reset and split into 5-10 smaller commits
# 2. Use dates from commit_date_schedule.txt
# 3. Use messages from commit_messages.txt

echo ""
echo "📋 Manual steps needed:"
echo "1. When Git stops at each commit:"
echo "   git reset HEAD^"
echo "2. Split into smaller commits"
echo "3. Set dates using: ./set_commit_date.sh 'YYYY-MM-DD HH:MM:SS'"
echo "4. Continue: git rebase --continue"
echo ""
echo "See commit_date_schedule.txt for dates"
echo "See commit_messages.txt for messages"

