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


def keep(s, n, years):
    idx = [YEARS.index(y) for y in years]; m = M[(s, n)][idx]; o = own(s, n); allp_ = [v for y in years for v in o[y]]
    need = len(years) - 1
    return (m > 0).sum() >= need and m.mean() > 0 and pf(allp_) > 1 and len(allp_) >= 5


br = book(LIVE)
print(f"LIVE BOOK v5.2.69: years " + ' '.join(f"{v:+.1f}" for v in base) + f" | 5-yr {tot(br):+.0f}% | max DD {dd(br):.1f}%\n")
for s in POOL:
    print(f"== {NAME[s]} ==   (* = live now)")
    print(f"  {'name':<6} {'trades':>6} {'PF':>5} {'mean':>7} | own PF by year 22 23 24 25 26      | book points by year 22 23 24 25 26        | avg/yr | yrs+ | rule")
    rows = []
    for n in POOL[s]:
        if (s, n) not in M: continue
        o = own(s, n); a = [v for y in YEARS for v in o[y]]; m = M[(s, n)]
        rows.append((m.mean(), n, a, o, m))
    for mean, n, a, o, m in sorted(rows, key=lambda x: -x[0]):
        star = '*' if n in LIVE[s] else ' '
        pfy = ' '.join(f"{pf(o[y]):4.2f}" if o[y] else '  - ' for y in YEARS)
        my = ' '.join(f"{v:+6.1f}" for v in m)
        ok = 'KEEP' if keep(s, n, YEARS) else '-'
        print(f" {star}{n:<6} {len(a):>6} {pf(a):>5.2f} {np.mean(a) if a else 0:>+6.2f}% | {pfy} | {my} | {mean:+6.1f} | {(m > 0).sum()}/5  | {ok}")
    print()
PICK = {s: [n for n in POOL[s] if (s, n) in M and keep(s, n, YEARS)] for s in POOL}
print('RULE PICK on all five years: ' + ' | '.join(f"{NAME[s].split()[0]} {PICK[s]}" for s in POOL))
rp = book(PICK)
print(f"  picked book: years " + ' '.join(f"{v:+.1f}" for v in yr(rp)) + f" | 5-yr {tot(rp):+.0f}% | max DD {dd(rp):.1f}%   (in sample)")
print('\nLEAVE ONE YEAR OUT: the rule picks names on the other four years, the held-out year is scored (account return %)')
oos_p, oos_l = [], []
for y in YEARS:
    tr = [x for x in YEARS if x != y]; pk = {s: [n for n in POOL[s] if (s, n) in M and keep(s, n, tr)] for s in POOL}
    for s in pk:
        if not pk[s]: pk[s] = list(LIVE[s])
    a = yr(book(pk))[YEARS.index(y)]; l = base[YEARS.index(y)]; oos_p.append(a); oos_l.append(l)
    print(f"  {y}: rule {a:+7.1f} | live {l:+7.1f} | picks " + ' | '.join(f"{s} {sorted(pk[s])}" for s in pk))
c = lambda v: (np.prod([1 + x / 100 for x in v]) - 1) * 100
print(f"  compounded held-out years: rule {c(oos_p):+.0f}% | live {c(oos_l):+.0f}% | rule better in {sum(a > b for a, b in zip(oos_p, oos_l))} of 5 years")
