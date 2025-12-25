#!/bin/bash
# Fix dates and expand commits to ~100

# Fix the dates on commits that are wrong
git filter-branch -f --env-filter '
if [ "$GIT_COMMIT" = "f5b03d9" ]; then
    export GIT_AUTHOR_DATE="2024-12-28 10:15:00"
    export GIT_COMMITTER_DATE="2024-12-28 10:15:00"
fi
if [ "$GIT_COMMIT" = "8f88f9f" ]; then
    export GIT_AUTHOR_DATE="2024-12-25 10:30:00"
    export GIT_COMMITTER_DATE="2024-12-25 10:30:00"
fi
' --tag-name-filter cat -- --all

echo "✅ Dates fixed"
