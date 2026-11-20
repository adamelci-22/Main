#!/usr/bin/env python3
"""SPY in the 9:35 family on the CURRENT live book v5.2.66 (RELVAL with DIA in place of XBI) (governor 2026-11-20: "lets add spy ...
first show me the year by year effect"). Research only. SPY is a signal proxy like QQQ: IBS-LONG / DIP buy SPXL, MIRROR buys SPXS,
1% proxy stop, 9:35 to 15:55. Full-period view (governor: "using all of the years ignore a test period").
    python3 -I tools/backtest/spy_family.py DATA_DIR > tools/backtest/results/spy_family_2026-11-20.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import universe as U, overnight as O
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB; dm = B.dm
ds = F.DS(os.path.join(sys.argv[1], 'M5U.json.gz'), list(F.LIVE) + list(U.NEW)); F.LEV.update({p: (3, 3) for p in U.NEW}); ctx = F.context(ds, list(F.LIVE) + list(U.NEW))
N2.PX = [p for p in list(F.LIVE) + list(U.NEW) if p != 'SPY']; N2.daily_init(ds)
N2.PX = N2.PX + ['SPY']
for p in ['SPY']:
    days_ = [d for d in ds.days if d in ds.bars[p]]; b = [ds.bars[p][d] for d in days_]
    N2.D[p] = (days_, {d: i for i, d in enumerate(days_)}, [x[0][0] for x in b], [max(y[1] for y in x) for x in b], [min(y[2] for y in x) for x in b], [x[-1][3] for x in b])
S = O.signals(); ovn = np.array([max([t for t in S.get(d, []) if t['kind'] == 'long'], key=lambda t: t['rv'])['pct'] / 100 if any(t['kind'] == 'long' for t in S.get(d, [])) else 0.0 for d in dm])
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
FAM = [t for p in F.LIVE for t in U.family(ds, ctx, p, (3, 3))]; SPYT = U.family(ds, ctx, 'SPY', (3, 3))


def run(parts):
    r = BA.acct(dm, TB.byday([t for q in parts for t in q]), after_stop=False)[0]; r = (1 + r) * (1 + 0.5 * ovn) - 1
    eq = np.cumprod(1 + r); return SB.yret(r), r


y0, r0 = run([PB, REL, FAM]); y1, r1 = run([PB, REL, FAM, SPYT])
yrs = [str(d)[:4] for d in dm]
def ydd(r):
    out = []
    for Y in ('2022', '2023', '2024', '2025', '2026'):
        x = np.array([v for v, yy in zip(r, yrs) if yy == Y]); eq = np.cumprod(1 + x); out.append((1 - eq / np.maximum.accumulate(eq)).max() * 100)
    return out
d0, d1 = ydd(r0), ydd(r1)
print(__doc__.split('\n')[0]); print(f"   SPY signals: {len(SPYT)} in five years (IBS-LONG {sum(t['sys'] == 4 for t in SPYT)}, MIRROR {sum(t['sys'] == 5 for t in SPYT)}, DIP {sum(t['sys'] == 2 for t in SPYT)})\n")
print(f"   {'year':<6}{'live':>9}{'+ SPY':>9}{'change':>9}{'live DD':>10}{'+SPY DD':>10}")
for i, Y in enumerate(('2022', '2023', '2024', '2025', '2026')): print(f"   {Y:<6}{y0[i]:>+8.1f}%{y1[i]:>+8.1f}%{y1[i] - y0[i]:>+9.1f}{d0[i]:>9.1f}%{d1[i]:>9.1f}%")
t0, t1 = (np.prod(1 + y0 / 100) - 1) * 100, (np.prod(1 + y1 / 100) - 1) * 100
e0, e1 = np.cumprod(1 + r0), np.cumprod(1 + r1)
print(f"   {'total':<6}{t0:>+8.0f}%{t1:>+8.0f}%{t1 - t0:>+9.0f}{(1 - e0 / np.maximum.accumulate(e0)).max() * 100:>9.1f}%{(1 - e1 / np.maximum.accumulate(e1)).max() * 100:>9.1f}%")
print(f"   average 2022-26: live {y0.mean():+.1f}%  + SPY {y1.mean():+.1f}%")
