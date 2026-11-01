#!/bin/bash
# Usage: slot_run.sh HH:MM   (after fetching the three C1.2 groups with get_equity_historicals)
# Runs paper.py --live on the 3 newest historicals dumps and commits and pushes the waiter log.
cd "$(git rev-parse --show-toplevel)" || exit 1
BR=$(git rev-parse --abbrev-ref HEAD)
F=$(ls -t "$HOME"/.claude/projects/*/*/tool-results/mcp-Robinhood-get_equity_historicals-*.txt | head -3)
python3 -I tools/live/paper.py --live --now "$1" $F 2>&1 | tail -16
git add -A >/dev/null && git commit -qm "waiter log $1" >/dev/null 2>&1 && timeout 60 git push -q origin "$BR" >/dev/null 2>&1
