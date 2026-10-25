#!/usr/bin/env python3
"""Data checks on the Massive 5-minute bars before trusting a backtest on them.
    /usr/bin/python3 -I tools/backtest/massive_checks.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_checks.txt
1. Unadjusted splits: any bar-to-bar close change beyond 35% inside a session, or an overnight gap (first open vs prior close) beyond 45% (and its date vs the split list).
2. Session completeness: full-day count (78 bars), half days, and days with fewer than 70 bars per ticker.
3. Daily vs 5-minute: the daily close equals the last 5-minute close within 0.5%.
"""
import glob, gzip, json, os, sys
m5 = json.load(gzip.open(sys.argv[1], 'rt')); d1 = json.load(gzip.open(sys.argv[2], 'rt')); SP = sys.argv[3]
splits = {os.path.basename(f)[:-5]: [(x['execution_date'], x['split_from'], x['split_to']) for x in json.load(open(f))] for f in glob.glob(os.path.join(SP, '*.json'))}
print(f"{'sym':<5}{'days':>5}{'full78':>7}{'<70':>5}{'intraday>35%':>13}{'gap>45%':>8}{'d1 vs 5m>0.5%':>14}  splits (date from:to) / flagged gaps")
for s in sorted(m5):
    days = sorted(m5[s]); full = sum(len(m5[s][d]) == 78 for d in days); short = sum(len(m5[s][d]) < 70 for d in days)
    intr = []; gaps = []; prev = None
    for d in days:
        b = m5[s][d]
        for i in range(1, len(b)):
            r = b[i][4] / b[i - 1][4]
            if r > 1.35 or r < 1 / 1.35: intr.append((d, round(r, 2)))
        if prev:
            g = b[0][1] / prev
            if g > 1.45 or g < 1 / 1.45: gaps.append((d, round(g, 2)))
        prev = b[-1][4]
    dd = {r[0]: r[4] for r in d1.get(s, [])}
    mis = sum(1 for d in days if d in dd and abs(dd[d] / m5[s][d][-1][4] - 1) > 0.005)
    sp = ' '.join(f"{d}({a}:{b})" for d, a, b in splits.get(s, []))
    print(f"{s:<5}{len(days):>5}{full:>7}{short:>5}{len(intr):>13}{len(gaps):>8}{mis:>14}  {sp}" + (f"  GAPS {gaps}" if gaps else '') + (f"  INTRADAY {intr[:6]}" if intr else ''))
