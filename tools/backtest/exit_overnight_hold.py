#!/usr/bin/env python3
"""Follow-up to exit_all.py (2026-11-14): the overnight leg held past 9:35. Alone it earns more, but it then sits in the account while the
day systems trade. Book test: the leg keeps its 50% of cash until its exit; on those days the day systems use the other 50%.
Baseline here = the same account model with the live 9:35 exit (day systems at full cash every day). Train 2022/2024/2026, test 2023/2025.
    python3 -I tools/backtest/exit_overnight_hold.py > tools/backtest/results/exit_overnight_hold_2026-11-14.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import exit_all as X
O, B, BA, BM, SB, N2, NS, TB = X.O, X.B, X.BA, X.BM, X.SB, X.N2, X.NS, X.TB; TR, TE = X.TR, X.TE; dm = X.dm; ds = X.ds
F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
by = TB.byday(F0 + P0 + I0 + M + D)
def leg(xb, stop):
    r = np.zeros(len(dm))
    for i, d in enumerate(dm[:-1]):
        nd = dm[i + 1]
        if nd not in onl: continue
        p = onl[nd]['proxy']; c = ds.bars[p][d][77][0]; nb = ds.bars[p][nd]; px = None
        for j in range(0, xb):
            if stop and nb[j][2] <= c * (1 - stop / 100): px = min(nb[j][0], c * (1 - stop / 100)); break
        if px is None: px = nb[xb][0]
        r[i + 1] = (3 * (px / c - 1) * 100 - NS.COST) / 100
    return r
base = (1 + SB.acct(dm, by)) * (1 + 0.5 * leg(1, None)) - 1; yb = SB.yret(base)
print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th)\n')
def row(tag, r, cmp=True):
    y = SB.yret(r); v = ''
    if cmp:
        q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
    eq = np.cumprod(1 + r); dd = (1 - eq / np.maximum.accumulate(eq)).max() * 100
    print(f"   {v:<5}{tag:<62} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} | max DD {dd:4.1f}")
row('BASELINE: sell the overnight leg at 9:35 (live)', base, False)
hold = set(onl)
for xb, tm in ((18, '11:00'), (48, '13:30'), (77, '15:55')):
    for stop in (None, 1.0, 2.0):
        l = leg(xb, stop)
        row(f"hold to {tm}, stop {str(stop) + '%' if stop else 'none'}; day systems on the other 50% those days", SB.acct(dm, by, fmax=lambda d: 0.5 if d in hold else 1.0) + 0.5 * l)
        row(f"hold to {tm}, stop {str(stop) + '%' if stop else 'none'}; NO day trades those days", SB.acct(dm, {d: v for d, v in by.items() if d not in hold}) + 0.5 * l)
n = len(hold); both = sum(1 for d in hold if any(t['sys'] == 4 and t['day'] == d for t in I0)); print(f"\n   {n} overnight days; on {both} of them ({100 * both / n:.0f}%) IBS-LONG also signals that morning (the same weak close, seen twice).")
