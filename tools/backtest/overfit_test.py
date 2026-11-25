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


base = yr(book(LIVE)); M = {}
for s in POOL:
    for n in POOL[s]:
        if s != 'pb' and n not in T[s]: continue
        cfg = {k: list(v) for k, v in LIVE.items()}
        if n in cfg[s]: cfg[s].remove(n); M[(s, n)] = base - yr(book(cfg))
        else: cfg[s].append(n); M[(s, n)] = yr(book(cfg)) - base



def comp(r, ys):
    m = np.zeros(len(dm), bool)
    for y in ys: m |= np.array([d[:4] == y for d in dm])
    return (np.prod(1 + r[m]) - 1) * 100
def apply_edits(sel):
    cfg = {k: list(v) for k, v in LIVE.items()}
    for (s_, n), g in sel.items():
        if n in LIVE[s_]:
            if n in cfg[s_]: cfg[s_].remove(n)
        elif n not in cfg[s_]: cfg[s_].append(n)
    return cfg
def gains(s_, n):
    m = M[(s_, n)]
    return -m if n in LIVE[s_] else m
print('SELECTION PROCEDURE RUN ON TRAIN YEARS ONLY, scored on the years it never saw')
print('rule: an edit (add a name, or drop a live name) is applied if it helps the book in at least 2 of 3 train years (both of 2) and in total on the train years')
SPLITS = [('train 2022-24', ['2022', '2023', '2024'], ['2025', '2026']), ('train 2024-26', ['2024', '2025', '2026'], ['2022', '2023']),
          ('train 2022 2024 2026', ['2022', '2024', '2026'], ['2023', '2025']), ('train 2023 2025', ['2023', '2025'], ['2022', '2024', '2026'])]
res = []; baseD = book(LIVE)
for nm, tr, te in SPLITS:
    idx = [YEARS.index(y) for y in tr]; sel = {}
    for k in M:
        g = gains(*k)[idx]
        if (g > 0).sum() >= (2 if len(tr) == 3 else len(tr)) and g.sum() > 0: sel[k] = g.sum()
    cfg = apply_edits(sel); r = book(cfg)
    live_te = comp(baseD, te); new_te = comp(r, te); live_tr = comp(baseD, tr); new_tr = comp(r, tr)
    byy = ' '.join(f"{y}: {comp(r, [y]) - comp(baseD, [y]):+.1f}" for y in te)
    print(f"  {nm:<22} edits {len(sel):>2} ({sum(1 for k in sel if k[1] in LIVE[k[0]])} drops, {sum(1 for k in sel if k[1] not in LIVE[k[0]])} adds) | train: live {live_tr:+7.0f}% -> {new_tr:+7.0f}% | TEST: live {live_te:+7.0f}% -> {new_te:+7.0f}%  ({byy})")
    res.append((nm, new_te - live_te, sel))
    print('      edits: ' + ', '.join(f"{'-' if k[1] in LIVE[k[0]] else '+'}{k[1]}({k[0]})" for k in sorted(sel, key=lambda k: -sel[k])))
print('\nthe five edits I made, scored the same way:')
FIVE = {('ovn', 'XLF'): 0, ('ovn', 'FXI'): 0, ('rel', 'XLRE'): 0, ('rel', 'XLE'): 0, ('pb', 'TECL'): 0}
for k in FIVE: print('  ', k, 'by year', ' '.join(f"{v:+.1f}" for v in gains(*k)), '| rank among all', 1 + sum(1 for q in M if gains(*q).sum() > gains(*k).sum()), 'of', len(M))
