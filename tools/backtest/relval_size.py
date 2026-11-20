#!/usr/bin/env python3
"""RELVAL position size (governor 2026-11-20: "run the backtest at 3% 5% and full size"). Research only.
Book = live v5.2.68 (PULLBACK, 9:35 family with SPY, RELVAL with DIA, overnight leg 50% without XBI), Massive 5-minute tape
2022-01..2026-10, one shared account. Only RELVAL's size changes; every other system keeps 3% risk (capped at 100% of cash).
  3%    live: shares = 3% of the account / leg stop (leg stop = 3 x the gap, about 4-12%), so about 25-75% of the account
  5%    5% of the account at risk on the same stop
  full  100% of cash on every RELVAL trade (risk = the full leg stop, 4-12% of the account)
    python3 -I tools/backtest/relval_size.py DATA_DIR > tools/backtest/results/relval_size_2026-11-20.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import universe as U, overnight_universe as OU
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB; dm = B.dm; YEARS = SB.YEARS
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
OVP = [p for p in F.LIVE if p != 'XBI']; LG = {p: OU.legs(ds, p, 3) for p in OVP}; ovn = np.zeros(len(dm))
for i, d in enumerate(dm):
    c = [LG[p][d] for p in OVP if d in LG[p]]
    if c: ovn[i] = max(c, key=lambda x: x[1])[0] / 100


def run(r_pct):
    """RELVAL at r_pct risk (None = full cash). acct sizes min(1, 3 / leg_risk): rescale RELVAL's leg_risk to get the wanted size."""
    rel = [dict(t, leg_risk=(1e-6 if r_pct is None else t['leg_risk'] * 3.0 / r_pct)) for t in REL]
    r, tk, _ = BA.acct(dm, TB.byday(PB + FAM + rel), after_stop=False)
    return (1 + r) * (1 + 0.5 * ovn) - 1, [t for t in tk if t['sys'] == 0]


def dd(r): e = np.cumprod(1 + r); return float((1 - e / np.maximum.accumulate(e)).max() * 100)


def tot(r): return (np.prod(1 + r) - 1) * 100


print(__doc__.split('\n')[0])
lr = np.array([t['leg_risk'] for t in REL]); print(f"   RELVAL signals {len(REL)}; leg stop median {np.median(lr):.1f}% (10th {np.percentile(lr, 10):.1f}%, 90th {np.percentile(lr, 90):.1f}%) -> 3% risk = {np.median(np.minimum(1, 3 / lr)) * 100:.0f}% of the account at the median\n")
print(f"   {'RELVAL size':<14}" + ''.join(f"{y:>8}" for y in YEARS) + f" | {'5-yr total':>10} | {'max DD':>6} | {'worst year DD':>13} | RELVAL trades, won, account pts, worst trade")
base = None
for tag, rp in (('3% (live)', 3.0), ('5%', 5.0), ('full (100%)', None)):
    r, tk = run(rp); y = SB.yret(r); g = np.array([t['g'] for t in tk])
    ydd = max(dd(r[[d[:4] == yy for d in dm]]) for yy in YEARS)
    print(f"   {tag:<14}" + ''.join(f"{v:>+8.1f}" for v in y) + f" | {tot(r):>+9.0f}% | {dd(r):>5.1f}% | {ydd:>12.1f}% | {len(g)}, {100 * np.mean(g > 0):.0f}%, {g.sum():+.1f}, {g.min():+.2f}%")
    if base is None: base = y
    else: print(f"   {'  vs 3%':<14}" + ''.join(f"{v:>+8.1f}" for v in y - base))
