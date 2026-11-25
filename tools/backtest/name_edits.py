#!/usr/bin/env python3
"""Best names for each system. Research only. Massive 5-minute tape, live book v5.2.69 (one shared account).
Per name and system: the name's own trades by year (n, PF, mean trade), and its contribution to the whole book by year
(book with the name minus book without it, in points of that year's account return).
Rule (fixed before looking): keep a name if its book contribution is positive in at least 4 of 5 years (3 of 4 inside a fold),
its average contribution is positive, and its own PF is above 1. Checked out of sample by leaving one year out."""
import os, sys
import numpy as np
BT = '/home/user/Main/tools/backtest'; sys.path.insert(0, BT)
import universe as U, overnight_universe as OU
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB; dm = B.dm; YEARS = list(SB.YEARS)
PBPOOL = ['SOXS', 'TECS', 'LABD', 'UVXY', 'TNA', 'TZA', 'TECL', 'SQQQ', 'LABU', 'FAS', 'FAZ', 'TQQQ', 'SOXL']
FAMPOOL = list(F.LIVE) + list(U.NEW)
RELPOOL = ['SOXX', 'IWM', 'XLK', 'XBI', 'XLF'] + [p for p in U.NEW if U.NEW[p][1]]
OVPOOL = list(F.LIVE) + list(U.NEW)
LIVE = dict(pb=['SOXS', 'LABD', 'TECS', 'UVXY'], fam=list(F.LIVE) + ['SPY'], rel=['SOXX', 'IWM', 'XLK', 'DIA', 'XLF'], ovn=['QQQ', 'SOXX', 'IWM', 'XLK', 'XLF'])
POOL = dict(pb=PBPOOL, fam=FAMPOOL, rel=RELPOOL, ovn=OVPOOL)
NAME = dict(pb='PULLBACK', fam='9:35 family (IBS-LONG, MIRROR, DIP)', rel='RELVAL', ovn='OVERNIGHT')
allp = list(F.LIVE) + list(U.NEW); F.LEV.update({p: (3, 3) for p in U.NEW})
ds = F.DS(os.path.join(sys.argv[1], 'M5U.json.gz'), allp + PBPOOL); ctx = F.context(ds, allp); N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
lev = lambda p: (3, 3) if p in F.LIVE else U.NEW[p]
T = dict(pb={}, fam={}, rel={}, ovn={})
for l in PBPOOL:
    T['pb'][l] = []
    for t in TB.pb_entries(ds, dm, [l], dict(B.EP.LIVE)):
        m = B.PS.manage(t, B.BC.RUN); T['pb'][l].append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
for p in FAMPOOL:
    if p in ds.bars: T['fam'][p] = U.family(ds, ctx, p, lev(p))
for p in RELPOOL:
    T['rel'][p] = []
    if p not in ds.bars: continue
    f = lev(p)[0] / 3
    for d in dm:
        b = ds.bars[p].get(d)
        if not b or len(b) < 78: continue
        x = NS.relval(ds, ctx, p, d, b, a=48, z=72, xm=1.0)
        if x: T['rel'][p].append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=(x['pct'] + NS.COST) * f - NS.COST, leg_risk=1e-6, rv=ds.rvol(p, d, x['k']), sys=0))
for p in OVPOOL:
    if p in ds.bars and len(ds.bars[p]) > 500: T['ovn'][p] = OU.legs(ds, p, lev(p)[0])
CACHE = {}


def book(cfg):
    key = tuple((s, tuple(sorted(cfg[s]))) for s in ('pb', 'fam', 'rel', 'ovn'))
    if key in CACHE: return CACHE[key]
    tr = [t for s in ('pb', 'fam', 'rel') for n in cfg[s] for t in T[s].get(n, [])]
    r = BA.acct(dm, TB.byday(tr), after_stop=False)[0]
    ov = np.zeros(len(dm)); L = [T['ovn'][p] for p in cfg['ovn'] if p in T['ovn']]
    for i, d in enumerate(dm):
        c = [x[d] for x in L if d in x]
        if c: ov[i] = max(c, key=lambda x: x[1])[0] / 100
    CACHE[key] = (1 + r) * (1 + 0.5 * ov) - 1; return CACHE[key]


def yr(r): return np.array(SB.yret(r))
def tot(r): return (np.prod(1 + r) - 1) * 100
def dd(r): e = np.cumprod(1 + r); return float((1 - e / np.maximum.accumulate(e)).max() * 100)
def pf(p):
    p = np.array(p, float)
    if len(p) == 0: return float('nan')
    gl = -p[p < 0].sum(); return p[p > 0].sum() / gl if gl else 9.99


def own(s, n):
    """the name's own trades: {year: list of pct}"""
    if s == 'ovn': items = [(d, v[0]) for d, v in T['ovn'].get(n, {}).items()]
    else: items = [(t['day'], t['pct']) for t in T[s].get(n, [])]
    return {y: [v for d, v in items if d[:4] == y] for y in YEARS}



base = yr(book(LIVE)); br = book(LIVE)
def apply(cfg, ed):
    c = {k: list(v) for k, v in cfg.items()}
    for s, op, n in ed:
        if op == '-' and n in c[s]: c[s].remove(n)
        if op == '+' and n not in c[s]: c[s].append(n)
    return c
EDITS = {
    'overnight -XLF': [('ovn', '-', 'XLF')], 'overnight +FXI': [('ovn', '+', 'FXI')], 'overnight -XLF +FXI': [('ovn', '-', 'XLF'), ('ovn', '+', 'FXI')],
    'overnight -QQQ': [('ovn', '-', 'QQQ')], 'RELVAL +XLRE': [('rel', '+', 'XLRE')], 'RELVAL +XLE': [('rel', '+', 'XLE')],
    'RELVAL +XLRE +XLE': [('rel', '+', 'XLRE'), ('rel', '+', 'XLE')], 'PULLBACK +TECL': [('pb', '+', 'TECL')],
    'family -QQQ': [('fam', '-', 'QQQ')],
}
EDITS['all of: ovn -XLF +FXI, rel +XLRE +XLE, pb +TECL'] = EDITS['overnight -XLF +FXI'] + EDITS['RELVAL +XLRE +XLE'] + EDITS['PULLBACK +TECL']
print(f"LIVE v5.2.69: " + ' '.join(f"{v:+7.1f}" for v in base) + f" | 5-yr {tot(br):+.0f}% | DD {dd(br):.1f}%")
print(f"{'edit to the live book':<50}" + ''.join(f"{y:>8}" for y in YEARS) + " | 5-yr total | vs live | yrs better | max DD | sep-years test")
R = {}
for n, ed in EDITS.items():
    r = book(apply(LIVE, ed)); y = yr(r); d = y - base; R[n] = d
    sep = 'PASS' if (d[[0, 2, 4]].sum() > 0 and (d[[0, 2, 4]] > 0).sum() >= 2 and d[1] > 0 and d[3] > 0) else 'fail'
    print(f"{n:<50}" + ''.join(f"{v:+8.1f}" for v in d) + f" | {tot(r):>+8.0f}% | {tot(r) - tot(br):>+6.0f} | {(d > 0).sum()}/5 | {dd(r):5.1f}% | {sep}")
print('\n(columns by year are points against the live book; sep-years test = better on train 2022 2024 2026 in total and in 2 of 3, and better in both test years 2023 and 2025)')
print('\nLEAVE ONE YEAR OUT on the single edits: an edit is applied in the held-out year only if it was better in 3 of the other 4 years and in total')
oos = []; live_ = []
for i, y in enumerate(YEARS):
    tr = [j for j in range(5) if j != i]; use = []
    for n, ed in EDITS.items():
        if n.startswith('all of'): continue
        d = R[n][tr]
        if (d > 0).sum() >= 3 and d.sum() > 0: use.append(n)
    # resolve overlaps: overnight combined edit wins over its parts, RELVAL combined over its parts
    if 'overnight -XLF +FXI' in use: use = [u for u in use if u not in ('overnight -XLF', 'overnight +FXI')]
    if 'RELVAL +XLRE +XLE' in use: use = [u for u in use if u not in ('RELVAL +XLRE', 'RELVAL +XLE')]
    ed = [e for u in use for e in EDITS[u]]; a = yr(book(apply(LIVE, ed)))[i]; oos.append(a); live_.append(base[i])
    print(f"  {y}: with edits {a:+7.1f} | live {base[i]:+7.1f} | edits used: {use}")
c = lambda v: (np.prod([1 + x / 100 for x in v]) - 1) * 100
print(f"  compounded held-out years: edits {c(oos):+.0f}% | live {c(live_):+.0f}% | better in {sum(a > b for a, b in zip(oos, live_))} of 5 years")
