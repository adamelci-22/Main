#!/bin/bash
# Usage: slot_run.sh HH:MM [dump files...]
# Runs paper.py --live on the three C1.2 dumps and commits and pushes the waiter log.
# With no files given it takes the 3 newest historicals dumps saved in the last 20 minutes. Fetch each C1.2 group from the
# prior trading day's 9:30 ET. If a get_equity_historicals result comes back inline (no saved file), write it to a file
# yourself and pass all three files on the command line.
cd "$(git rev-parse --show-toplevel)" || exit 1
BR=$(git rev-parse --abbrev-ref HEAD)
T="$1"; shift
if [ $# -gt 0 ]; then F="$*"
else F=$(find "$HOME"/.claude/projects/*/*/tool-results -name 'mcp-Robinhood-get_equity_historicals-*.txt' -mmin -20 -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -3 | cut -d' ' -f2-); fi
N=$(echo $F | wc -w)
if [ "$N" -ne 3 ]; then echo "ERROR: found $N dump file(s), need 3 (fresh within 20 min). Refetch the missing group(s) from the prior trading day's 9:30; if a result came back inline, save it to a file and pass the three files as arguments."; exit 2; fi
python3 -I tools/live/paper.py --live --now "$T" $F 2>&1 | tail -16
git add -A >/dev/null
git commit -qm "waiter log $T" >/dev/null 2>&1 && { git pull -q --rebase origin "$BR" >/dev/null 2>&1; timeout 60 git push -q origin "$BR" >/dev/null 2>&1; }
exit 0
