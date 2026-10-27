#!/usr/bin/env python3
"""#2 (chandelier 3 ATR) vs the frozen 1R trail capped at +0.75R, and both together. FADE, no Fridays.  /usr/bin/python3 -I tools/backtest/frozen_vs_chand3.py M5.json.gz"""
import os, sys, datetime as dt, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
K = {}
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; bestc = 0.0; j = k
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o
            gross += (1 / 3) * (px - entry) * s; rem = 2 / 3; hit = True
            if (entry - stop) * s > 0: stop = entry
        bestc = max(bestc, (cl - entry) * s / r)
        if K['frozen'] and bestc >= 1.0:                      # frozen at -1R until a 5-min close at +1R, then 1R behind the best close, capped at +0.75R
            ns = entry + s * min(0.75, bestc - 1.0) * r
            if (ns - stop) * s > 0: stop = ns
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * K['k'] * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=j, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage

fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
def run(fr):
    K.update(k=2.0, frozen=fr)
    T = [t for t in F.trades(ds, days, syms, F.P(), ctx) if not fri(t['day'])]
    a = F.account(ds, days, T); return {(t['day'], t['proxy']): t for t in a['taken']}
# best close and whether 2R was hit, from the live run with extra bookkeeping
_m = F._manage
def m2(*a):
    info = _m(*a)
    if info is None: return None
    ds_, p, d, b, k, side, entry, ext = a[:8]; r = (entry - ext) * side
    closes = [(b[j][3] - entry) * side / r for j in range(k, min(info['xbar'], 47) + 1)]
    highs = [((b[j][1] if side > 0 else b[j][2]) - entry) * side / r for j in range(k, min(info['xbar'], 47) + 1)]
    info['bestc'] = max(closes) if closes else 0; info['besth'] = max(highs) if highs else 0
    return info
F._manage = m2
L = run(False); Z = run(True)
keys = [k for k in L if k in Z]
n = len(L); g = lambda t: t['acct'] > 0
print(f"DATA {'Robinhood 2026' if RH else 'Massive 5 years'}: {n} trades taken (live), FADE, no Fridays")
print(f"  green: live {sum(g(t) for t in L.values())} ({100*sum(g(t) for t in L.values())/n:.0f}%), frozen {sum(g(t) for t in Z.values())} ({100*sum(g(t) for t in Z.values())/len(Z):.0f}%)")
grp = collections.Counter()
for k in keys:
    l, z = L[k], Z[k]
    if l['besth'] < 1.0: grp['A never touched +1R (stop never moves)'] += 1
    elif l['bestc'] < 1.0: grp['B touched +1R intrabar but no 5-min CLOSE at +1R (stop never moves)'] += 1
    elif l['besth'] >= 2.0 and l['acct'] > 0 and z['acct'] > 0: grp['C closed at +1R, went on to 2R: green either way'] += 1
    elif g(l) and g(z): grp['D closed at +1R, green in both (13:30 exit / trail)'] += 1
    elif not g(l) and g(z): grp['E FLIPPED red -> green by the frozen trail'] += 1
    elif g(l) and not g(z): grp['F FLIPPED green -> red/scratch by the frozen trail'] += 1
    else: grp['G closed at +1R but red in both (stopped near breakeven, costs make it red)'] += 1
for k_, v in sorted(grp.items()): print(f"  {k_:<75} {v:4d}  ({100*v/len(keys):.0f}%)")
sc = [Z[k]['R_out'] for k in keys if L[k]['bestc'] >= 1.0 and not g(Z[k])]
if sc: print(f"  frozen-trail red trades that had closed at +1R: avg {sum(sc)/len(sc):+.2f}R (cost 0.06% round trip on the leg ~ -0.05 to -0.1R)")
