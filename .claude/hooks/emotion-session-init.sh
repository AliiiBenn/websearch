#!/bin/bash
# Initialize risk tracking at session start

# Initialize fresh baseline
echo "0" > "$CLAUDE_PROJECT_DIR/.claude/hooks/.risk_score"

exit 0