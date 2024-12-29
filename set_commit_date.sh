#!/bin/bash
# Helper script to set commit date easily
# Usage: ./set_commit_date.sh "2025-03-05 14:30:00"

if [ -z "$1" ]; then
    echo "Usage: ./set_commit_date.sh 'YYYY-MM-DD HH:MM:SS'"
    echo "Example: ./set_commit_date.sh '2025-03-05 14:30:00'"
    exit 1
fi

DATE="$1"
GIT_AUTHOR_DATE="$DATE" \
GIT_COMMITTER_DATE="$DATE" \
git commit --amend --no-edit --date="$DATE"

echo "✅ Commit date set to: $DATE"

