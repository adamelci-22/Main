#!/usr/bin/env python3
"""Exit/size study on live FADE (30-min box), Massive 5y tape. /usr/bin/python3 -I tools/backtest/exit_study.py M5.json.gz > results/exit_study.txt
Part 1: anatomy (do trades lose fast? do winners give profit back?). Part 2: exit grid, discovery (<2024-04) vs confirmation (>=2024-04), %/day. Part 3: risk % vs drawdown."""
import os, sys, statistics as st, collections
from dataclasses import replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms); days = ds.days[21:]
H1 = [d for d in days if d < '2024-04-01']; H2 = [d for d in days if d >= '2024-04-01']
base = F.P()
def run(c, dd):
    T = F.trades(ds, dd, syms, c, ctx); a = F.account(ds, dd, T, max_entries=c.max_entries); s = F.stat(a)
    return s, T
T0 = F.trades(ds, days, syms, base, ctx)
print(f"LIVE rules, {len(T0)} setups, {len(days)} days")
mean = lambda x: sum(x) / len(x) if x else 0
print(f"avg R {mean([t['R_out'] for t in T0]):+.3f}; win {100*sum(t['R_out']>0 for t in T0)/len(T0):.0f}%")
by = collections.defaultdict(list)
for t in T0: by[t['why']].append(t)
print("\nPART 1 exit reasons: n, avg R, avg bars held (5-min), avg MFE R, avg MAE R")
for w, v in sorted(by.items(), key=lambda x: -len(x[1])):
    print(f"  {w:<7} n={len(v):4d} avgR={mean([t['R_out'] for t in v]):+.2f} held={mean([t['xbar']-t['k'] for t in v]):4.1f} MFE={mean([t['mfe'] for t in v]):.2f} MAE={mean([t['mae'] for t in v]):.2f}")
L = [t for t in T0 if t['why'] == 'stop']
print(f"\nstopped-out trades: {len(L)} ({100*len(L)/len(T0):.0f}% of trades); stopped within 6 bars (30 min): {100*sum(t['xbar']-t['k']<=6 for t in L)/len(L):.0f}%; of these, ever reached +1R first: {100*sum(t['mfe']>=1 for t in L)/len(L):.0f}%")
W = [t for t in T0 if t['hit']]
print(f"trades that hit 2R partial: {len(W)}; their avg MFE {mean([t['mfe'] for t in W]):.2f}R, avg final R {mean([t['R_out'] for t in W]):+.2f}R -> giveback {mean([t['mfe'] for t in W])-mean([t['R_out'] for t in W]):.2f}R")
print("MFE distribution of ALL trades (share reaching): " + ' '.join(f">={m}R {100*sum(t['mfe']>=m for t in T0)/len(T0):.0f}%" for m in (0.5,1,1.5,2,3,4)))
print("final R of trades by time held: " + ' '.join(f"{a}-{b}: {mean([t['R_out'] for t in T0 if a<=t['xbar']-t['k']<b]):+.2f}(n{sum(a<=t['xbar']-t['k']<b for t in T0)})" for a,b in ((0,3),(3,6),(6,12),(12,24),(24,99))))
print("\nPART 2 exit grid (change one thing). %/day  trades  win%  maxDD  | H1 discovery | H2 confirmation | whole")
def show(tag, c):
    r = [run(c, d)[0] for d in (H1, H2, days)]
    print(f"{tag:<34}" + ''.join(f" | {s['avg']:+.3f} {s['n']:4d}t {s['win']:2.0f}% DD{s['mdd']:4.1f}" for s in r))
show('LIVE', base)
for R in (1.0, 1.5, 2.5, 3.0): show(f'target R={R}', replace(base, R=R))
for f in (0.0, 0.5, 2/3, 1.0): show(f'partial frac={f:.2f}', replace(base, frac=f))
show('no breakeven', replace(base, be=False))
for c in (0, 1.0, 1.5, 3.0): show(f'chandelier {c}ATR', replace(base, chand=c))
for l, n in ((29,'11:55'),(35,'12:25'),(41,'12:55'),(59,'14:25'),(71,'15:25')): show(f'time exit {n}', replace(base, last=l))
for v in (0.25, 0.5): show(f'stop wider +{v}R', replace(base, stop_buf=v))
for v in (0.5, 1.0): show(f'stop floor {v}ATR', replace(base, floor_atr=v))
show('R1.5 frac.5 chand1.5', replace(base, R=1.5, frac=0.5, chand=1.5))
show('R1.0 frac.5 chand1.5 last41', replace(base, R=1.0, frac=0.5, chand=1.5, last=41))
show('R3 frac.33 chand3', replace(base, R=3.0, chand=3.0))
print("\nPART 3 risk % per trade (live exits), whole sample, account-level: return%, maxDD%, ")
T = F.trades(ds, days, syms, base, ctx)
for r in (0.01, 0.02, 0.03, 0.05):
    a = F.account(ds, days, T, risk=r); print(f"  risk {r*100:.0f}%: total return {a['ret']:+.1f}%  max drawdown {a['mdd']:.1f}%")
