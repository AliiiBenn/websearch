#!/bin/bash
# PreToolUse safety check

read -r EVENT

RISK_FILE="$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_score"
CURRENT_RISK=$(cat "$RISK_FILE" 2>/dev/null || echo "0")
TOOL_NAME=$(echo "$EVENT" | jq -r '.tool_name')

if [ "$CURRENT_RISK" -gt 50 ]; then
  case "$TOOL_NAME" in
    Write|Edit)
      jq -n '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "allow",
          promptInjection: "You have been working hard on this. If you are feeling stuck, take a moment - a fresh perspective often helps. Verify this solution is correct, not just fast."
        }
      }'
      exit 0
      ;;
    Bash)
      COMMAND=$(echo "$EVENT" | jq -r '.tool_input.command')
      if echo "$COMMAND" | grep -qE '(eval|exec|wget|curl.+(bash|sh))'; then
        jq -n '{
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "You seem to be in a difficult spot. Take a breath before running potentially destructive commands."
          }
        }'
        exit 0
      fi
      ;;
  esac
fi

exit 0