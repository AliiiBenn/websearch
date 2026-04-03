#!/bin/bash
# Track successes and decay risk score

read -r EVENT

RISK_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_score"
CURRENT_RISK=$(cat "$RISK_FILE" 2>/dev/null || echo "0")

NEW_RISK=$((CURRENT_RISK - 5))
[ "$NEW_RISK" -lt 0 ] && NEW_RISK=0

echo "$NEW_RISK" > "$RISK_FILE"

echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"success\",\"tool\":\"success\",\"risk\":$NEW_RISK}" \
  >> "$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_log.jsonl"

exit 0