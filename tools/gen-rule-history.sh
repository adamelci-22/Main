#!/usr/bin/env bash
# Regenerates RULE_HISTORY.md from git history.
#
# RULE_HISTORY.md is a GENERATED VIEW, never hand-edited. The commit log is the
# single source of truth for why a rule changed; this script only renders it in a
# readable form. If the two ever disagree, the git log is right and this file is
# stale -- rerun the script.
#
# Usage: tools/gen-rule-history.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=RULE_HISTORY.md

{
  echo "# Rule history"
  echo
  echo "**Generated file — do not edit.** Regenerate with \`tools/gen-rule-history.sh\`."
  echo
  echo "Every change to \`RULEBOOK.md\`, newest first, with the reasoning recorded at the time."
  echo "The git log is authoritative; this is a rendering of it."
  echo
  echo "Generated $(date -u '+%Y-%m-%d %H:%M UTC') · $(git rev-list --count HEAD -- RULEBOOK.md) changes to the rulebook."
  echo
  echo "---"
  echo

  # git log is newest-first by default, which is the order we want.
  # Trailers (Co-Authored-By, Claude-Session) are stripped -- they are provenance,
  # not reasoning, and they bury the explanation we actually want to read.
  git log --follow --date=short \
    --format='## %ad · `%h`%n%n**%s**%n%n%b%n---%n' -- RULEBOOK.md \
    | grep -v -E '^(Co-Authored-By|Claude-Session):' \
    | cat -s
} > "$OUT"

echo "wrote $OUT ($(wc -l < "$OUT") lines)"
