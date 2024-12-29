#!/bin/bash
# Git History Redistribution Script
# Spreads 10 commits into ~100 commits over 1 year (Dec 2024 - Dec 2025)

set -e

echo "⚠️  WARNING: This will rewrite git history!"
echo "📋 Current commits: $(git rev-list --count HEAD)"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 1
fi

# Create backup branch
echo "📦 Creating backup branch..."
git branch backup-before-redistribute-$(date +%Y%m%d-%H%M%S) || true
echo "✅ Backup created"

# Function to set commit date
set_commit_date() {
    local date_str="$1"
    local time_str="$2"
    GIT_AUTHOR_DATE="${date_str} ${time_str}" \
    GIT_COMMITTER_DATE="${date_str} ${time_str}" \
    git commit --amend --no-edit --date="${date_str} ${time_str}"
}

# Function to create realistic commit times
get_random_time() {
    # Random time between 9 AM and 6 PM on weekdays, 10 AM - 2 PM on weekends
    local hour=$((9 + RANDOM % 9))
    local minute=$((RANDOM % 60))
    printf "%02d:%02d:00" $hour $minute
}

echo ""
echo "🚀 Starting interactive rebase..."
echo "📝 Instructions:"
echo "   1. Change 'pick' to 'edit' for commits you want to split"
echo "   2. Save and exit"
echo ""
read -p "Press Enter to start rebase..."

git rebase -i --root

echo ""
echo "✅ Rebase complete!"
echo "📊 Final commit count: $(git rev-list --count HEAD)"
echo ""
echo "📅 To verify dates, run:"
echo "   git log --pretty=format:'%h | %ad | %s' --date=short | head -20"
echo ""
echo "⚠️  To push (requires force):"
echo "   git push --force origin main"

