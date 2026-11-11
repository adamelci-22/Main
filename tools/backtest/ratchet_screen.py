#!/usr/bin/env python3
"""Governor 2026-11-11: ratchet ideas for the shares not sold at 2R, on top of the live v5.2.22 exits (lock +0.15R at the first +0.5R close, 15-minute early cut, 1/3 at 2R, BE then 2-ATR chandelier, out 13:30).
    python3 tools/backtest/ratchet_screen.py > tools/backtest/results/ratchet_screen_2026-11-11.txt
Robinhood cache 2026-03-03..10-14, FADE live 6, no Fridays. TRAIL = (activation R, distance R): from the first close at activation, stop = best close - distance (effective next bar). STEP = [(best close R, stop R)]."""
import os, sys, datetime as dt, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE); days = [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14']
H1 = [d for d in days if d < '2026-06-24']; H2 = [d for d in days if d >= '2026-06-24']
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
LOCK = (0.5, 0.15); CUT = (3, -0.5); TRAIL = None; STEP = []
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; bestc = 0.0; j = k; pend = None; out = False
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: gross += rem * (o - entry) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o; gross += rem * (px - entry) * s; rem = 0; break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; gross += (1 / 3) * (px - entry) * s; rem = 2 / 3; hit = True
            if (entry - stop) * s > 0: stop = entry
        cr = (cl - entry) * s / r; bestc = max(bestc, cr)
        lv = None
        if LOCK and bestc >= LOCK[0]: lv = LOCK[1]
        if TRAIL and bestc >= TRAIL[0]: lv = max(lv if lv is not None else -9, bestc - TRAIL[1])
        for trig, lvl in STEP:
            if bestc >= trig: lv = max(lv if lv is not None else -9, lvl)
        if lv is not None: pend = entry + s * lv * r
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * 2 * at[j]
            if (ns - stop) * s > 0: stop = ns
        if CUT and j - k + 1 == CUT[0] and cr <= CUT[1] and j < last: out = True
    if rem > 0: gross += rem * (b[j][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=j, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage
def summ(dd, T):
    S = set(dd); a = F.account(ds, dd, [t for t in T if t['day'] in S]); tk = a['taken']
    g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
    gn = [t['acct'] for t in tk if t['acct'] > 0]
    return dict(n=len(tk), pf=g / l, ret=a['ret'], dd=a['mdd'], red=100 * sum(t['acct'] <= 0 for t in tk) / len(tk), r2=100 * sum(t.get('R_out', 0) >= 0.6 for t in tk) / len(tk))
print("Robinhood cache 2026-03-03..10-14, FADE live 6, no Fridays. PF all (half 1 / half 2), halves split 2026-06-24")
RUNS = [('LIVE v5.2.22 (lock +0.15R at +0.5R, cut, 2R, chandelier)', None, []),
        ('trail from +0.5R, 1.00R behind best close', (0.5, 1.0), []),
        ('trail from +0.5R, 1.25R behind best close', (0.5, 1.25), []),
        ('trail from +0.5R, 1.50R behind best close', (0.5, 1.5), []),
        ('step: +1R -> stop +0.5R, +1.5R -> stop +1R', None, [(1.0, 0.5), (1.5, 1.0)])]
for name, tr, stp in RUNS:
    TRAIL, STEP = tr, stp
    T = [t for t in F.trades(ds, days, F.LIVE, F.P(), ctx) if not fri(t['day'])]
    a, b1, b2 = summ(days, T), summ(H1, T), summ(H2, T)
    print(f"  {name:<58} trades {a['n']:3d} PF {a['pf']:4.2f} ({b1['pf']:4.2f}/{b2['pf']:4.2f}) total {a['ret']:+6.1f}% maxDD {a['dd']:4.1f}% losing {a['red']:3.0f}% avgR>=0.6 {a['r2']:3.0f}%")
