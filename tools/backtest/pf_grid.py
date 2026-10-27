#!/usr/bin/env python3
"""Every FADE entry filter x exit rule discussed on 2026-10-27, ranked by profit factor.  /usr/bin/python3 -I tools/backtest/pf_grid.py M5.json.gz
Entry filters (applied to the setups): skip Fridays; min opening-box width; bear leg only.
Exits: live and the variants tested today. Profit factor = $ won on green trades / $ lost on red trades, account-level after costs (3% risk sizing, one position)."""
import os, sys, datetime as dt, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
X = {}
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; tr = X['tr']; rk = X['rat']; tl = X.get('trail'); st = X.get('steps', [])
    rem = 1.0; gross = 0.0; i = 0; hic = entry; bestc = 0.0; besth = 0.0
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; break
        while i < len(tr) and (fav - (entry + s * tr[i][0] * r)) * s >= 0:
            T = entry + s * tr[i][0] * r; px = T if (o - T) * s <= 0 else o
            gross += tr[i][1] * (px - entry) * s; rem -= tr[i][1]
            ns = entry + s * tr[i][2] * r
            if (ns - stop) * s > 0: stop = ns
            i += 1
        if rem <= 1e-9: rem = 0; break
        besth = max(besth, (fav - entry) * s / r); bestc = max(bestc, (cl - entry) * s / r)
        for trig, lock in st:
            if besth >= trig:
                ns = entry + s * lock * r
                if (ns - stop) * s > 0: stop = ns
        if tl and bestc >= tl[0]:
            ns = entry + s * min(tl[2], bestc - tl[1]) * r
            if (ns - stop) * s > 0: stop = ns
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if tr and i == len(tr) and j < last and rk[0] == 'chand':
            ns = hic - s * rk[1] * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    # keep the xbar the account needs: approximate with the bar where the loop stopped
    info['xbar'] = j
    return info
F._manage = manage
B13 = [(2.0, 1/3, 0.0)]
EXITS = {
 'LIVE exits (1/3@2R, BE, chand 2)':          dict(tr=B13, rat=('chand', 2.0)),
 'chandelier 3 after 2R':                    dict(tr=B13, rat=('chand', 3.0)),
 '1/2@2R, rest chand 2':                     dict(tr=[(2.0, .5, 0.0)], rat=('chand', 2.0)),
 'all out at 2R':                            dict(tr=[(2.0, 1.0, 0.0)], rat=('none',)),
 'no partial; after 2R BE + chand 2':        dict(tr=[(2.0, 1e-6, 0.0)], rat=('chand', 2.0)),
 'at +1R stop to BE (+live)':                dict(tr=B13, rat=('chand', 2.0), steps=[(1.0, 0.0)]),
 'at +1R lock +0.1R (+live)':                dict(tr=B13, rat=('chand', 2.0), steps=[(1.0, 0.1)]),
 'at +1R stop to -0.5R (+live)':             dict(tr=B13, rat=('chand', 2.0), steps=[(1.0, -0.5)]),
 '1R trail on closes from start, cap +0.75R':dict(tr=B13, rat=('chand', 2.0), trail=(-99, 1.0, 0.75)),
 '1R trail on closes from start, cap 0 (BE)':dict(tr=B13, rat=('chand', 2.0), trail=(-99, 1.0, 0.0)),
 'frozen to +1R close, 1R trail cap +0.75R': dict(tr=B13, rat=('chand', 2.0), trail=(1.0, 1.0, 0.75)),
}
FILTERS = [(fri, mb, bear) for fri in (False, True) for mb in (0.0, 0.5, 0.7, 0.8, 1.0) for bear in (False, True)]
def ftag(fri, mb, bear):
    t = []
    if fri: t.append('no Fri')
    if mb: t.append(f'box>={mb}%')
    if bear: t.append('bear leg only')
    return ', '.join(t) if t else 'no filter'
isfri = lambda d: dt.date.fromisoformat(d).weekday() == 4
def stats(ds, days, T):
    a = F.account(ds, days, T); tk = a['taken']; s = F.stat(a)
    g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
    return dict(n=len(tk), pf=(g / l if l > 0 else 99.0), green=100 * sum(t['acct'] > 0 for t in tk) / max(1, len(tk)), day=s['avg'], dd=s['mdd'], ret=a['ret'])
DATA = {}
for name, src in (('RH', None), ('5Y', sys.argv[1])):
    ds = F.DS(src, F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
    days = ds.days[1:] if src is None else ds.days[21:]
    split = sorted(days)[len(days) // 2] if src is None else '2024-04-01'
    DATA[name] = (ds, syms, ctx, days, [d for d in days if d < split], [d for d in days if d >= split])
rows = []
for en, ex in EXITS.items():
    X.clear(); X.update(ex); base = {}
    for name, (ds, syms, ctx, days, h1, h2) in DATA.items():
        base[name] = F.trades(ds, days, syms, F.P(), ctx)
    for fl in FILTERS:
        fri, mb, bear = fl; rec = dict(exit=en, filt=ftag(*fl))
        for name, (ds, syms, ctx, days, h1, h2) in DATA.items():
            T = [t for t in base[name] if not (fri and isfri(t['day'])) and t['box_pct'] >= mb and not (bear and t['side'] > 0)]
            for part, dd in (('all', days), ('h1', h1), ('h2', h2)):
                S = set(dd); rec[f'{name}_{part}'] = stats(ds, dd, [t for t in T if t['day'] in S])
        rows.append(rec)
def line(r):
    a, b1, b2, y, y1, y2 = r['RH_all'], r['RH_h1'], r['RH_h2'], r['5Y_all'], r['5Y_h1'], r['5Y_h2']
    return (f"{r['filt']:<30} {r['exit']:<42} | RH n{a['n']:3d} PF {a['pf']:4.2f} (H1 {b1['pf']:4.2f} H2 {b2['pf']:4.2f}) green {a['green']:3.0f}% {a['day']:+.3f}%/d DD{a['dd']:4.1f} "
            f"| 5y n{y['n']:3d} PF {y['pf']:4.2f} (H1 {y1['pf']:4.2f} H2 {y2['pf']:4.2f}) {y['day']:+.3f}%/d DD{y['dd']:4.1f}")
print(f"{len(rows)} systems = {len(FILTERS)} entry-filter sets x {len(EXITS)} exits.  RH = Robinhood 2026-03..10 (157 days), 5y = Massive 2021-11..2026-10.\n")
live = [r for r in rows if r['filt'] == 'no filter' and r['exit'].startswith('LIVE')][0]
print("CURRENT LIVE SYSTEM (FADE part)\n  " + line(live))
ok = [r for r in rows if r['RH_all']['n'] >= 35 and r['RH_h1']['n'] >= 12 and r['RH_h2']['n'] >= 12]
print(f"\nTOP 15 BY ROBINHOOD PROFIT FACTOR (at least 35 trades, 12 in each half; {len(ok)} qualify)")
for r in sorted(ok, key=lambda r: -r['RH_all']['pf'])[:15]: print("  " + line(r))
rob = [r for r in ok if min(r['RH_h1']['pf'], r['RH_h2']['pf']) > 1.5]
print(f"\nTOP 15 BY THE WORSE OF THE TWO DATASETS' PROFIT FACTOR (robust ranking; same trade minimums)")
for r in sorted(ok, key=lambda r: -min(r['RH_all']['pf'], r['5Y_all']['pf']))[:15]: print("  " + line(r))
print(f"\nTOP 10 BY 5-YEAR PROFIT FACTOR (at least 150 trades over 5 years)")
for r in sorted([r for r in rows if r['5Y_all']['n'] >= 150], key=lambda r: -r['5Y_all']['pf'])[:10]: print("  " + line(r))
both = [r for r in rows if r['RH_all']['n'] >= 40 and min(r['RH_h1']['pf'], r['RH_h2']['pf'], r['5Y_h1']['pf'], r['5Y_h2']['pf']) > 1.0]
print(f"\nTOP 10 BY ROBINHOOD PROFIT FACTOR THAT ALSO MAKE MONEY IN ALL FOUR HALVES (RH H1/H2, 5y H1/H2) with >= 40 RH trades ({len(both)} qualify)")
for r in sorted(both, key=lambda r: -r['RH_all']['pf'])[:10]: print("  " + line(r))
