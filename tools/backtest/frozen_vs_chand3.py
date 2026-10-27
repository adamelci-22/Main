#!/usr/bin/env python3
"""#2 (chandelier 3 ATR) vs the frozen 1R trail capped at +0.75R, and both together. FADE, no Fridays.  /usr/bin/python3 -I tools/backtest/frozen_vs_chand3.py M5.json.gz"""
import os, sys, datetime as dt
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
def summ(ds, days, T):
    a = F.account(ds, days, T); tk = a['taken']; s = F.stat(a)
    g = [t['acct'] for t in tk if t['acct'] > 0]; l = [t['acct'] for t in tk if t['acct'] <= 0]
    return dict(n=len(tk), green=100 * len(g) / len(tk), pf=sum(g) / -sum(l), day=s['avg'], dd=s['mdd'], ret=a['ret'], ag=sum(g) / len(g), al=sum(l) / len(l),
                full=100 * sum(t['R_out'] <= -0.9 for t in tk) / len(tk))
ROWS = [('LIVE now: chandelier 2', 2.0, False), ('#2: chandelier 3', 3.0, False), ('frozen trail cap +0.75R (+ chand 2)', 2.0, True), ('frozen trail cap +0.75R + chand 3', 3.0, True)]
for name, src in (('ROBINHOOD 2026-03..10', None), ('MASSIVE 5 YEARS', sys.argv[1])):
    ds = F.DS(src, F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
    days = ds.days[1:] if src is None else ds.days[21:]
    split = sorted(days)[len(days) // 2] if src is None else '2024-04-01'
    print(f"\n== {name} (FADE, no Fridays)")
    print(f"{'exit':<38} {'trades':>6} {'green':>6} {'PF':>5} {'%/day':>7} {'H1':>7} {'H2':>7} {'avg grn':>8} {'avg red':>8} {'full -1R':>8} {'maxDD':>6} {'total':>7}")
    for tag, k, fr in ROWS:
        K.update(k=k, frozen=fr)
        T = [t for t in F.trades(ds, days, syms, F.P(), ctx) if not fri(t['day'])]
        a = summ(ds, days, T)
        h = [summ(ds, [d for d in days if (d < split) == first], [t for t in T if (t['day'] < split) == first]) for first in (True, False)]
        print(f"{tag:<38} {a['n']:>6} {a['green']:>5.0f}% {a['pf']:>5.2f} {a['day']:>+6.3f}% {h[0]['day']:>+6.3f}% {h[1]['day']:>+6.3f}% {a['ag']:>+7.2f}% {a['al']:>+7.2f}% {a['full']:>7.0f}% {a['dd']:>5.1f}% {a['ret']:>+6.1f}%")
