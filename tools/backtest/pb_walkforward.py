#!/usr/bin/env python3
"""Full-book backtest by PULLBACK leg set. Research only. Book = live v5.2.69 (RELVAL full size with DIA, 9:35 family with SPY,
overnight leg 50% without XBI), Massive 5-minute tape 2022-01..2026-10, one shared account. Only the PULLBACK leg set changes."""
import os, sys
import numpy as np
BT = '/home/user/Main/tools/backtest'; sys.path.insert(0, BT)
import universe as U, overnight_universe as OU
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB; dm = B.dm; YEARS = SB.YEARS
PBLEGS = ['SOXS', 'TECS', 'LABD', 'UVXY', 'TNA', 'TZA', 'TECL', 'SQQQ', 'LABU', 'FAS', 'FAZ', 'TQQQ', 'SOXL']
allp = list(F.LIVE) + list(U.NEW); F.LEV.update({p: (3, 3) for p in U.NEW})
ds = F.DS(os.path.join(sys.argv[1], 'M5U.json.gz'), allp + PBLEGS); ctx = F.context(ds, allp); N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
PBT = {}
for leg in PBLEGS:
    PBT[leg] = []
    for t in TB.pb_entries(ds, dm, [leg], dict(B.EP.LIVE)):
        m = B.PS.manage(t, B.BC.RUN); PBT[leg].append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
REL = []
for p in ['SOXX', 'IWM', 'XLK', 'DIA', 'XLF']:
    for d in dm:
        b = ds.bars[p].get(d)
        if not b or len(b) < 78: continue
        x = NS.relval(ds, ctx, p, d, b, a=48, z=72, xm=1.0)
        if x: REL.append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=x['pct'], leg_risk=1e-6, rv=ds.rvol(p, d, x['k']), sys=0))
FAM = [t for p in list(F.LIVE) + ['SPY'] for t in U.family(ds, ctx, p, (3, 3))]
OVP = [p for p in F.LIVE if p != 'XBI']; LG = {p: OU.legs(ds, p, 3) for p in OVP}; ovn = np.zeros(len(dm))
for i, d in enumerate(dm):
    c = [LG[p][d] for p in OVP if d in LG[p]]
    if c: ovn[i] = max(c, key=lambda x: x[1])[0] / 100


def run(legs):
    pb = [t for l in legs for t in PBT[l]]
    r, tk, _ = BA.acct(dm, TB.byday(pb + FAM + REL), after_stop=False)
    return (1 + r) * (1 + 0.5 * ovn) - 1, [t for t in tk if t['sys'] == 1]



def dd(r): e = np.cumprod(1 + r); return float((1 - e / np.maximum.accumulate(e)).max() * 100)
YM = {y: np.array([d[:4] == y for d in dm]) for y in YEARS}
CACHE = {}
def R(legs):
    k = tuple(sorted(legs))
    if k not in CACHE: CACHE[k] = run(list(k))[0]
    return CACHE[k]
def comp(r, ys):
    m = np.zeros(len(dm), bool)
    for y in ys: m |= YM[y]
    return (np.prod(1 + r[m]) - 1) * 100
def greedy(train, maxn=6):
    cur = []; best = comp(R([]), train); pool = list(PBLEGS)
    while pool and len(cur) < maxn:
        c = max((comp(R(cur + [l]), train), l) for l in pool)
        if c[0] <= best * 1.0 + 1: break
        best = c[0]; cur.append(c[1]); pool.remove(c[1])
    return cur
FIX = {'live four': ['SOXS', 'LABD', 'TECS', 'UVXY'], 'SOXS TECS': ['SOXS', 'TECS'], 'SOXS TECS UVXY': ['SOXS', 'TECS', 'UVXY'], 'no PULLBACK': []}
print('Leave one year out: greedy picks on the other four years, scored on the held-out year (account return that year, %)')
print(f"{'held out':<9}{'greedy':>9}" + ''.join(f"{n:>17}" for n in FIX) + '  | greedy legs chosen')
cnt = {}; rows = []
for y in YEARS:
    tr = [x for x in YEARS if x != y]; g = greedy(tr)
    for l in g: cnt[l] = cnt.get(l, 0) + 1
    vals = [comp(R(g), [y])] + [comp(R(l), [y]) for l in FIX.values()]
    rows.append(vals)
    print(f"{y:<9}{vals[0]:>+9.1f}" + ''.join(f"{v:>+17.1f}" for v in vals[1:]) + '  | ' + ' '.join(g), flush=True)
tot = [np.prod([1 + r[i] / 100 for r in rows]) * 100 - 100 for i in range(len(rows[0]))]
print(f"{'compound':<9}{tot[0]:>+9.0f}" + ''.join(f"{v:>+17.0f}" for v in tot[1:]) + '  (out-of-sample years compounded)')
print('legs chosen in how many of the 5 folds: ' + ', '.join(f"{l} {n}" for l, n in sorted(cnt.items(), key=lambda x: -x[1])))
print('\nSeparate-years test (rulebook): train 2022 2024 2026 -> test 2023 2025, and train 2023 2025 -> test 2022 2024 2026')
for tr, te in ((('2022', '2024', '2026'), ('2023', '2025')), (('2023', '2025'), ('2022', '2024', '2026'))):
    g = greedy(list(tr))
    print(f"  train {tr}: greedy {g}")
    print(f"     test {te}: greedy {comp(R(g), te):+.0f}% | " + ' | '.join(f"{n} {comp(R(l), te):+.0f}%" for n, l in FIX.items()))
