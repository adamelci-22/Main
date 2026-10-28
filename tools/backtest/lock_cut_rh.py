#!/usr/bin/env python3
"""v5.2.19 evidence: FADE +0.15R lock at the first +0.5R close (B) and early cut 15 min after entry at -0.5R or worse (C), Robinhood cache only.
    python3 tools/backtest/lock_cut_rh.py > tools/backtest/results/lock_cut_rh.txt
FADE live 6, no Fridays, v5.2.18 exits otherwise (frozen 1R trail capped at +0.75R, 1/3 at 2R, 2-ATR chandelier, out 13:30); 3% risk capped at cash, one position."""
import os, sys, datetime as dt, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE); days = [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14']
H1 = [d for d in days if d < '2026-06-24']; H2 = [d for d in days if d >= '2026-06-24']
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
LOCK = None; CUT = None; FROZEN = True
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
        if LOCK and bestc >= LOCK[0]: pend = entry + s * LOCK[1] * r
        if FROZEN and bestc >= 1.0:
            ns = entry + s * min(0.75, bestc - 1.0) * r
            if (ns - stop) * s > 0: stop = ns
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
    return dict(n=len(tk), pf=g / l, ret=a['ret'], dd=a['mdd'], red=100 * sum(t['acct'] <= 0 for t in tk) / len(tk))
print("Robinhood cache 2026-03-03..10-14, FADE live 6, no Fridays. PF all (half 1 / half 2), halves split 2026-06-24")
for name, fz, lk, ct in (('v5.2.17 (no frozen, no lock, no cut)', False, None, None), ('v5.2.18 (frozen trail)', True, None, None),
                         ('B: +0.5R close -> stop +0.15R', True, (0.5, 0.15), None), ('C: 15 min close <= -0.5R -> sell', True, None, (3, -0.5)),
                         ('B + C with frozen (v5.2.19)', True, (0.5, 0.15), (3, -0.5)), ('B + C, no frozen (v5.2.22)', False, (0.5, 0.15), (3, -0.5))):
    FROZEN, LOCK, CUT = fz, lk, ct
    T = [t for t in F.trades(ds, days, F.LIVE, F.P(), ctx) if not fri(t['day'])]
    a, b1, b2 = summ(days, T), summ(H1, T), summ(H2, T)
    print(f"  {name:<34} trades {a['n']:3d} PF {a['pf']:4.2f} ({b1['pf']:4.2f}/{b2['pf']:4.2f}) total {a['ret']:+6.1f}% maxDD {a['dd']:4.1f}% losing trades {a['red']:3.0f}%")
