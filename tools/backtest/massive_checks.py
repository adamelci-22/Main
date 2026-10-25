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

# 4. Is the early data different from the 2026 data? Per year for QQQ, SOXX, XBI: first-bar start (UTC), full sessions, 5-minute range, flat bars, volume, and the 5-minute day high/low against the daily bar.
print("\n4. Per-year consistency (QQQ, SOXX, XBI). First bar must be 9:30 ET = 13:30 UTC in summer, 14:30 UTC in winter.")
for s in ('QQQ', 'SOXX', 'XBI'):
    dd = {r[0]: r for r in d1[s]}; yy = {}
    for d, b in m5[s].items():
        r = yy.setdefault(d[:4], dict(days=0, full=0, first={}, rng=[], flat=0, bars=0, vol=[], mis=0, n=0))
        r['days'] += 1; r['full'] += len(b) == 78; r['first'][b[0][0]] = r['first'].get(b[0][0], 0) + 1
        for x in b: r['rng'].append((x[2] - x[3]) / x[4] * 1e4); r['flat'] += x[1] == x[2] == x[3] == x[4]; r['bars'] += 1; r['vol'].append(x[5])
        if d in dd and len(b) == 78:
            r['n'] += 1; r['mis'] += abs(max(x[2] for x in b) / dd[d][2] - 1) > 0.002 or abs(min(x[3] for x in b) / dd[d][3] - 1) > 0.002
    for y in sorted(yy):
        r = yy[y]; f2 = dict(sorted(r['first'].items(), key=lambda kv: -kv[1])[:2])
        print(f"   {s} {y} days {r['days']:>3} full78 {r['full']:>3} first bars {f2} avg 5m range {sum(r['rng'])/len(r['rng']):.1f}bp flat bars {100*r['flat']/r['bars']:.2f}% median volume {sorted(r['vol'])[len(r['vol'])//2]:,} H/L vs daily mismatches {r['mis']}/{r['n']}")
