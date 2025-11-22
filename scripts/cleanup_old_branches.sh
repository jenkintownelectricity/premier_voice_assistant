#!/bin/bash

# Branch Cleanup Script
# Date: 2025-11-22
# Purpose: Delete old merged Claude Code branches

echo "🧹 Premier Voice Assistant - Branch Cleanup"
echo "==========================================="
echo ""

# Backup current branch state
echo "📋 Creating backup of all branches..."
git branch -r --format='%(refname:short)|%(committerdate:short)|%(subject)' > "ARCHIVED_BRANCHES_$(date +%Y%m%d_%H%M%S).txt"
echo "✅ Backup saved to ARCHIVED_BRANCHES_$(date +%Y%m%d_%H%M%S).txt"
echo ""

# List of fully merged branches to delete (0 commits ahead of main)
MERGED_BRANCHES=(
  "claude/add-modal-web-endpoints-01RBF6A5NtAHZ6oiXrnmtftt"
  "claude/clean-web-ui-01NobBNSoHwFfoqbnm3SQk19"
  "claude/deploy-voice-assistant-01THwxecYstERmee53ZNjr37"
  "claude/fix-modal-deployment-019GxVFx5UNGhJpxhKGKfoRw"
  "claude/implement-database-feature-gates-011DnUS2PuaM7UZ7QyWsV5dF"
  "claude/review-all-branches-015Lqsv5sYDL6WyHYGpzF9JN"
  "claude/teleport-session-setup-016eUFyiHmqa7YtihKkDL7a4"
  "claude/teleport-session-setup-01BYLePx4EVZ7eiGZHAgq4Tz"
  "claude/teleport-session-setup-01NobBNSoHwFfoqbnm3SQk19"
)

echo "📊 Summary:"
echo "  - Branches to delete: ${#MERGED_BRANCHES[@]}"
echo "  - All branches are fully merged into main"
echo ""

# Confirm before deletion
read -p "⚠️  Do you want to delete these ${#MERGED_BRANCHES[@]} merged branches? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
  echo "❌ Cancelled. No branches were deleted."
  exit 0
fi

echo ""
echo "🗑️  Deleting merged branches..."
echo ""

SUCCESS=0
FAILED=0

for branch in "${MERGED_BRANCHES[@]}"; do
  echo "Deleting: $branch"
  if git push origin --delete "$branch" 2>&1; then
    echo "  ✅ Deleted successfully"
    ((SUCCESS++))
  else
    echo "  ❌ Failed to delete"
    ((FAILED++))
  fi
  echo ""
done

echo "==========================================="
echo "📈 Results:"
echo "  ✅ Deleted: $SUCCESS"
echo "  ❌ Failed: $FAILED"
echo ""

if [[ $FAILED -gt 0 ]]; then
  echo "⚠️  Some branches could not be deleted."
  echo "   You may need to delete them manually in GitHub:"
  echo "   Settings > Branches > View all branches > Delete"
  echo ""
fi

echo "✨ Cleanup complete!"
echo ""
echo "📝 Note: The backup file contains all branch information"
echo "   in case you need to reference them later."
