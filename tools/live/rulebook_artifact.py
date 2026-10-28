#!/usr/bin/env python3
"""Build the Rulebook artifact page (governor request 2026-10-28): RULEBOOK.md plus the live and backtest code, as one self-contained HTML page.
    python3 tools/live/rulebook_artifact.py OUT.html
Then publish OUT.html with the Artifact tool to https://claude.ai/artifact/ (URL recorded in RULEBOOK C5), same file path, no icon.
Rerun and republish after ANY change to RULEBOOK.md or the listed code files (RULEBOOK C5, 'Rulebook artifact').
Reporting only: it changes no order, rule or state."""
import json, os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FILES = [('Live engine', 'tools/live/paper.py'), ('Health tracker', 'tools/live/health.py'), ('Drawdown stop', 'tools/live/hwm.py'),
         ('Slot waiter', 'tools/live/slot_clock.sh'), ('FADE status', 'tools/live/fade_status.py'), ('PULLBACK status', 'tools/live/pb_status.py'),
         ('Time zone helper', 'tools/live/et2utc.sh'), ('Dashboard data', 'tools/live/dash_data.py'), ('Waiter report', 'tools/live/slot_report.py'),
         ('Waiter lag', 'tools/live/slot_lag.py'), ('Rulebook page builder', 'tools/live/rulebook_artifact.py'),
         ('Backtest: final system', 'tools/backtest/final_system.py'), ('Backtest: FADE simulator', 'tools/backtest/fade_diag.py'),
         ('Backtest: PULLBACK', 'tools/backtest/pb_final.py')]
rb = open(os.path.join(ROOT, 'RULEBOOK.md')).read()
ver = re.search(r'Policy version: ([0-9.]+)\*\*', rb).group(1)
git = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout.strip()
commit, cdate = git('rev-parse', '--short', 'HEAD'), git('log', '-1', '--format=%cd', '--date=format:%Y-%m-%d %H:%M')
files = [dict(label=l, path=p, text=open(os.path.join(ROOT, p)).read()) for l, p in FILES if os.path.exists(os.path.join(ROOT, p))]
data = json.dumps(dict(version=ver, commit=commit, committed=cdate, rulebook=rb, files=files)).replace('</', '<\\/')
page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rulebook_template.html')).read().replace('/*@@DATA@@*/null', data)
open(sys.argv[1], 'w').write(page)
print(f"rulebook v{ver} @ {commit}: {len(rb):,} chars + {len(files)} code files -> {sys.argv[1]} ({len(page):,} bytes)")
