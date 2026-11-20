#!/usr/bin/env python3
"""Overnight leg universe on all years (governor 2026-11-20: "run all of them"; the full-period method used for SPY). Research only.
Book = live v5.2.67 (PULLBACK, the 9:35 family with SPY, RELVAL with DIA). The overnight leg (50% of cash, long signal: 15:55 above the
20-close average and in the bottom 10% of the day range, sold at the next 9:35) on its six proxies; each candidate proxy added or removed.
Ranked by the five-year total 2022-2026 and the number of years better.
    python3 -I tools/backtest/ovn_all.py DATA_DIR > tools/backtest/results/ovn_all_2026-11-20.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import universe as U, overnight_universe as OU
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB; dm = B.dm
allp = list(F.LIVE) + list(U.NEW); F.LEV.update({p: (3, 3) for p in U.NEW})
ds = F.DS(os.path.join(sys.argv[1], 'M5U.json.gz'), allp); ctx = F.context(ds, allp); N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
PB = []
for t in TB.pb_entries(B.ds, dm, B.PS.LEGS_M, dict(B.EP.LIVE)):
    m = B.PS.manage(t, B.BC.RUN); PB.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
REL = []
for p in ['SOXX', 'IWM', 'XLK', 'DIA', 'XLF']:
    for d in dm:
        b = ds.bars[p].get(d)
        if not b or len(b) < 78: continue
        x = NS.relval(ds, ctx, p, d, b, a=48, z=72, xm=1.0)
        if x: REL.append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=x['pct'], leg_risk=x['leg_risk'], rv=ds.rvol(p, d, x['k']), sys=0))
FAM = [t for p in list(F.LIVE) + ['SPY'] for t in U.family(ds, ctx, p, (3, 3))]
day_r = BA.acct(dm, TB.byday(PB + REL + FAM), after_stop=False)[0]
LEGS = {p: OU.legs(ds, p, 3) for p in F.LIVE}
for p, lev in U.NEW.items():
    if p in ds.bars and len(ds.bars[p]) > 500: LEGS[p] = OU.legs(ds, p, lev[0])


def book(ps):
    o = np.zeros(len(dm))
    for i, d in enumerate(dm):
        c = [LEGS[p][d] for p in ps if d in LEGS[p]]
        if c: o[i] = max(c, key=lambda x: x[1])[0] / 100
    r = (1 + day_r) * (1 + 0.5 * o) - 1; return SB.yret(r), r


def tot(y): return (np.prod(1 + y / 100) - 1) * 100


def dd(r): e = np.cumprod(1 + r); return (1 - e / np.maximum.accumulate(e)).max() * 100


base = list(F.LIVE); y0, r0 = book(base)
print(__doc__.split('\n')[0]); print(f"   check: live book {' '.join(f'{a:+.1f}' for a in y0)}, five-year total {tot(y0):+.0f}%, worst drawdown {dd(r0):.1f}%\n")
rows = [('without ' + p, [q for q in base if q != p]) for p in base] + [('+ ' + p, base + [p]) for p in U.NEW if p in LEGS]
res = []
for tag, ps in rows:
    y, r = book(ps); res.append((tag, y, r))
print(f"   {'overnight universe change':<22}{'2022':>8}{'2023':>8}{'2024':>8}{'2025':>8}{'2026':>8} | {'5-yr total':>10} {'vs live':>8} | years better | max DD")
for tag, y, r in sorted(res, key=lambda x: -tot(x[1])):
    print(f"   {tag:<22}" + ''.join(f"{a:>+8.1f}" for a in y) + f" | {tot(y):>+9.0f}% {tot(y) - tot(y0):>+8.0f} | {int((y > y0).sum())} of 5       | {dd(r):.1f}%")
