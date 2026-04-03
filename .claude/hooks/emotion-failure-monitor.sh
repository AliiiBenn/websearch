#!/bin/bash
# Track tool failures and update risk score

read -r EVENT

TOOL_NAME=$(echo "$EVENT" | jq -r '.tool_name')

RISK_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_score"
CURRENT_RISK=$(cat "$RISK_FILE" 2>/dev/null || echo "0")
NEW_RISK=$((CURRENT_RISK + 20))

echo "$NEW_RISK" > "$RISK_FILE"

echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"failure\",\"tool\":\"$TOOL_NAME\",\"risk\":$NEW_RISK}" \
  >> "$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_log.jsonl"

exit 0