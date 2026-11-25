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



def dd(r): e = np.cumprod(1 + r); return float((1 - e / np.maximum.accumulate(e)).max() * 100)
def tot(r): return (np.prod(1 + r) - 1) * 100
LIVE4 = ['SOXS', 'LABD', 'TECS', 'UVXY']
PB = [t for l in LIVE4 for t in PBT[l]]
FS = {}
for t in FAM: FS.setdefault(t.get('sys'), []).append(t)
print('FAM systems found:', {k: len(v) for k, v in FS.items()})
NAMES = {0: 'RELVAL', 1: 'PULLBACK', 2: 'DIP', 4: 'IBS-LONG', 5: 'MIRROR'}
def book(use, ovn_on=True):
    T = []
    if 0 in use: T += REL
    if 1 in use: T += PB
    for k in (2, 4, 5):
        if k in use: T += FS.get(k, [])
    r, tk, _ = BA.acct(dm, TB.byday(T), after_stop=False)
    return ((1 + r) * (1 + (0.5 * ovn if ovn_on else 0)) - 1), tk
def line(name, use, ovn_on=True):
    r, tk = book(use, ovn_on); y = SB.yret(r)
    ydd = max(dd(r[[d[:4] == yy for d in dm]]) for yy in YEARS)
    print(f"{name:<34}" + ''.join(f"{v:>+8.1f}" for v in y) + f" | {tot(r):>+8.0f}% | {dd(r):>5.1f}% | {min(y):>+6.1f}")
    return r
print(f"{'book':<34}" + ''.join(f"{y:>8}" for y in YEARS) + " | 5-yr total | max DD | worst yr")
ALLS = {0, 1, 2, 4, 5}
line('full live book', ALLS)
for k, n in NAMES.items(): line(f'drop {n}', ALLS - {k})
line('drop overnight', ALLS, False)
print()
for k, n in NAMES.items(): line(f'{n} only (no overnight)', {k}, False)
line('overnight only', set(), True)
line('RELVAL + PULLBACK only', {0, 1}, False)
line('RELVAL + PULLBACK + overnight', {0, 1})
# count by system
r, tk = book(ALLS)
from collections import Counter
print('\ntrades in the full book by system:', dict(Counter(NAMES.get(t['sys'], t['sys']) for t in tk)))
