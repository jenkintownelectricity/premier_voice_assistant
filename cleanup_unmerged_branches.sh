#!/bin/bash

echo "🧹 Cleaning up unmerged branches..."
echo ""

# Branches to definitely delete (superseded by main)
BRANCHES_TO_DELETE=(
  "claude/premier-voice-assistant-01SkTb9nFMC3ZXJs67hdy1QV"
  "claude/setup-modal-deployment-01X4t5xyE2XoNnP21P4CEfSM"
  "claude/setup-modal-deployment-01618vWjGa3QL9VoQQFfnLD3"
  "claude/review-markdown-files-01FJBPQQKVowLeeyGR3rNze6"
  "claude/premier-voice-assistant-phase1-01DWmgYf7QpBQRPCH7jQehPZ"
  "claude/setup-env-api-keys-012HZSsvrtMYkgDeRvRWaJGK"
)

echo "📊 Will delete ${#BRANCHES_TO_DELETE[@]} superseded branches:"
echo ""
for branch in "${BRANCHES_TO_DELETE[@]}"; do
  echo "  ❌ $branch"
done
echo ""

echo "⚠️  NOT deleting (needs review first):"
echo "  🟡 claude/deploy-modal-endpoints-01GwNLyTqiavvZvquqrGz5ex"
echo "     Reason: Contains admin dashboard & multi-skill features"
echo "     Action: Review UNMERGED_BRANCHES_ANALYSIS.md first"
echo ""

read -p "Delete the ${#BRANCHES_TO_DELETE[@]} superseded branches? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
  echo "❌ Cancelled. No branches were deleted."
  exit 0
fi

echo ""
echo "🗑️  Deleting branches..."
echo ""

SUCCESS=0
FAILED=0

for branch in "${BRANCHES_TO_DELETE[@]}"; do
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

if [[ $SUCCESS -gt 0 ]]; then
  echo "✨ Cleanup complete!"
  echo ""
fi

echo "📝 Next Steps:"
echo "  1. Review UNMERGED_BRANCHES_ANALYSIS.md"
echo "  2. Decide about claude/deploy-modal-endpoints-01GwNLyTqiavvZvquqrGz5ex"
echo "  3. Either merge features you want OR delete that branch too"
echo ""
