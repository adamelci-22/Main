#!/usr/bin/env python3
"""Health measures on the full five-year backtest (governor 2026-11-16: "Measure health on the full back test"). Research only.
Input: the 942 backtest trades of the live book (bt_trades.json from dash_backtest.py: day, system, ticker, acct_pct, pos_pct).
For each system, every rolling window of 30 trades (and 20) gets the live health measures (health.py bands): profit factor on account %, win rate,
average trade on position %. Reports how often a system that runs exactly to the backtest would still show WARNING or ACT, by year, plus the worst window
and 30-trading-day trade counts against the average pace. Tells the governor how loud the live alarms are on a healthy system.
    python3 -I tools/backtest/health_bt.py BT_TRADES.json > tools/backtest/results/health_bt_2026-11-16.txt"""
import json, sys
from collections import defaultdict
import numpy as np
T = json.load(open(sys.argv[1])); SYS = ['FADE', 'PULLBACK', 'IBS-LONG', 'MIRROR', 'DIP', 'OVERNIGHT']
by = defaultdict(list)
for t in T: by[t['system'].upper()].append(t)


def pf(a):
    g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 99.0


def band(v, h, w): return 'H' if v > h else 'W' if v >= w else 'A'


def stats(rows, n):
    r = []
    for i in range(0, len(rows) - n + 1):
        w = rows[i:i + n]; a = [x['acct_pct'] for x in w]; p = [x['pos_pct'] for x in w]
        r.append((w[-1]['day'], pf(a), 100 * np.mean([x > 0 for x in p]), float(np.mean(p))))
    return r


print(__doc__.split('\n')[0]); print(f"   {len(T)} trades. Bands from health.py: PF healthy >1.5, warning 1.0-1.5, ACT <1.0 | win rate >60 / 50-60 / <50 | average trade >+0.20% / 0-0.20 / <0\n")
for n in (30, 20):
    print(f"ROLLING WINDOW OF {n} TRADES (share of windows in each band; a healthy backtest system still raises these)")
    print(f"   {'system':<10}{'trades':>7}{'windows':>8} | {'PF H/W/A %':>16} {'PF min':>7} | {'win H/W/A %':>16} {'win min':>8} | {'avg H/W/A %':>16} {'avg min':>8} | any ACT {'':>2}2+ ACT")
    for s in SYSTEM if False else SYS:
        rows = sorted(by[s], key=lambda t: t['day']); w = stats(rows, n)
        if not w: print(f"   {s:<10}{len(rows):>7}  too few"); continue
        P = [band(x[1], 1.5, 1.0) for x in w]; Wn = [band(x[2], 60, 50) for x in w]; A = [band(x[3], 0.20, 0.0) for x in w]
        sh = lambda L: '/'.join(f"{100 * L.count(k) / len(L):3.0f}" for k in 'HWA')
        act = [sum(1 for m in (P[i], Wn[i], A[i]) if m == 'A') for i in range(len(w))]
        print(f"   {s:<10}{len(rows):>7}{len(w):>8} | {sh(P):>16} {min(x[1] for x in w):>7.2f} | {sh(Wn):>16} {min(x[2] for x in w):>7.0f}% | {sh(A):>16} {min(x[3] for x in w):>+7.2f}% | {100 * np.mean([a >= 1 for a in act]):>5.0f}%   {100 * np.mean([a >= 2 for a in act]):>4.0f}%")
    print()
print("BY YEAR: share of 30-trade windows (ending in that year) with profit factor under 1.0 (ACT)")
print(f"   {'system':<10}" + ''.join(f"{y:>8}" for y in range(2022, 2027)))
for s in SYS:
    rows = sorted(by[s], key=lambda t: t['day']); w = stats(rows, 30); out = []
    for y in range(2022, 2027):
        z = [x for x in w if x[0].startswith(str(y))]; out.append(f"{100 * np.mean([x[1] < 1.0 for x in z]):>7.0f}%" if z else f"{'-':>8}")
    print(f"   {s:<10}" + ''.join(out))
print("\nWORST 30-TRADE WINDOW per system (ends on, PF, win %, average trade %)")
for s in SYS:
    rows = sorted(by[s], key=lambda t: t['day']); w = stats(rows, 30)
    if w: x = min(w, key=lambda q: q[1]); print(f"   {s:<10} {x[0]}  PF {x[1]:.2f}  win {x[2]:.0f}%  avg {x[3]:+.2f}%")
print("\nLONGEST RUN OF 30-TRADE WINDOWS WITH PF UNDER 1.0 (in trades, and calendar days from first to last window end)")
import datetime as dt
for s in SYS:
    rows = sorted(by[s], key=lambda t: t['day']); w = stats(rows, 30); best = (0, None, None); run = 0; st = None
    for x in w:
        if x[1] < 1.0:
            run += 1; st = st or x[0]
            if run > best[0]: best = (run, st, x[0])
        else: run = 0; st = None
    if best[0]: print(f"   {s:<10} {best[0]} windows, {best[1]} to {best[2]} ({(dt.date.fromisoformat(best[2]) - dt.date.fromisoformat(best[1])).days} days)")
    else: print(f"   {s:<10} never")
print("\nTRADES PER 30 TRADING DAYS (frequency check, health.py grades the live count against the pace: healthy >= 60%, warning 30-60%, check < 30%)")
days = sorted({t['day'] for t in T})
for s in SYS:
    ds = defaultdict(int)
    for t in by[s]: ds[t['day']] += 1
    cnt = [sum(ds.get(d, 0) for d in days[i:i + 30]) for i in range(0, len(days) - 29)]; pace = np.mean(cnt)
    print(f"   {s:<10} pace {pace:5.1f} per 30 days | min {min(cnt):>3} ({100 * min(cnt) / pace:3.0f}% of pace) | windows under 60% of pace {100 * np.mean([c < 0.6 * pace for c in cnt]):3.0f}% | under 30% {100 * np.mean([c < 0.3 * pace for c in cnt]):3.0f}%")
print("\nBACKTEST PERCENTILES of 30-trade windows (candidate bands: WARNING below the 25th percentile, ACT below the 5th; a healthy system then alarms about 5% of the time)")
print(f"   {'system':<10} | {'PF p5':>6} {'p10':>6} {'p25':>6} {'p50':>6} | {'win% p5':>8} {'p25':>5} {'p50':>5} | {'avg% p5':>8} {'p25':>7} {'p50':>7}")
for s in SYS:
    rows = sorted(by[s], key=lambda t: t['day']); w = stats(rows, 30)
    if not w: continue
    P = [x[1] for x in w]; Wn = [x[2] for x in w]; A = [x[3] for x in w]; q = lambda L, p: float(np.percentile(L, p))
    print(f"   {s:<10} | {q(P, 5):>6.2f} {q(P, 10):>6.2f} {q(P, 25):>6.2f} {q(P, 50):>6.2f} | {q(Wn, 5):>7.0f}% {q(Wn, 25):>4.0f}% {q(Wn, 50):>4.0f}% | {q(A, 5):>+7.2f}% {q(A, 25):>+6.2f}% {q(A, 50):>+6.2f}%")
