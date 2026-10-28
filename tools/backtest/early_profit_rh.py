#!/usr/bin/env python3
"""EARLY PROFIT study (governor question 2026-10-28; research only, no rule changed). Based on v5.2.19 evidence: FADE +0.15R lock at the first +0.5R close (B) and early cut 15 min after entry at -0.5R or worse (C), Robinhood cache only.
    python3 tools/backtest/early_profit_rh.py > tools/backtest/results/early_profit_rh.txt
FADE live 6, no Fridays, v5.2.18 exits otherwise (frozen 1R trail capped at +0.75R, 1/3 at 2R, 2-ATR chandelier, out 13:30); 3% risk capped at cash, one position."""
import os, sys, datetime as dt, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE); days = [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14']
H1 = [d for d in days if d < '2026-06-24']; H2 = [d for d in days if d >= '2026-06-24']
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
LOCK = (0.5, 0.15); CUT = (3, -0.5); FROZEN = False
V = dict(full=None, part=None, hl=None, rev=None)   # full=(X R) ; part=(X R, fraction) ; hl=(trigger R) ; rev=(trigger R)
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; bestc = 0.0; j = k; pend = None; out = False; ptp = False
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: gross += rem * (o - entry) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o; gross += rem * (px - entry) * s; rem = 0; break
        if V['full'] is not None:
            Xp = entry + s * V['full'] * r
            if (fav - Xp) * s >= 0:
                px = Xp if (o - Xp) * s <= 0 else o; gross += rem * (px - entry) * s; rem = 0; break
        if V['part'] is not None and not ptp:
            Xp = entry + s * V['part'][0] * r
            if (fav - Xp) * s >= 0:
                px = Xp if (o - Xp) * s <= 0 else o; gross += V['part'][1] * (px - entry) * s; rem -= V['part'][1]; ptp = True
                if (entry - stop) * s > 0: stop = entry
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; gross += (1 / 3) * (px - entry) * s; rem = rem - (1 / 3) if rem > 1 / 3 else rem / 2; hit = True
            if (entry - stop) * s > 0: stop = entry
        cr = (cl - entry) * s / r; bestc = max(bestc, cr)
        if LOCK and bestc >= LOCK[0]: pend = entry + s * LOCK[1] * r
        if V['hl'] is not None and bestc >= V['hl']:
            ns = l if s > 0 else h                      # stop under the latest bar's low (over its high for a short): the higher-low break
            if (ns - entry) * s > 0 and (pend is None or (ns - pend) * s > 0): pend = ns
        if V['rev'] is not None and bestc >= V['rev'] and j < last:
            bar = abs(cl - o); wick = (h - cl) if s > 0 else (cl - l)
            if ((cl - o) * s < 0 and (h - l) > at[j]) : out = True      # bar closes against the trade on a range above ATR: exit next open
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
    reach = [t for t in tk]
    return dict(n=len(tk), pf=g / l if l else 99, ret=a['ret'], dd=a['mdd'], avg=sum(t['acct'] for t in tk) / len(tk))
print("Robinhood cache 2026-03-03..10-14, FADE live 6, no Fridays, v5.2.22 exits as the base. PF all (half 1 / half 2), halves split 2026-06-24")
RUNS = [('BASE v5.2.22 (live)', {}),
 ('full exit at +0.5R', dict(full=0.5)), ('full exit at +0.75R', dict(full=0.75)), ('full exit at +1R', dict(full=1.0)), ('full exit at +1.5R', dict(full=1.5)),
 ('sell 1/2 at +0.75R, rest as base', dict(part=(0.75, 0.5))), ('sell 1/2 at +1R, rest as base', dict(part=(1.0, 0.5))), ('sell 1/3 at +0.75R, rest as base', dict(part=(0.75, 1 / 3))),
 ('higher-low trail from +0.5R close', dict(hl=0.5)), ('higher-low trail from +0.75R close', dict(hl=0.75)), ('higher-low trail from +1R close', dict(hl=1.0)),
 ('reversal bar (down bar, range > ATR) exit from +0.5R', dict(rev=0.5)), ('reversal bar exit from +0.75R', dict(rev=0.75))]
for name, v in RUNS:
    V.update(dict(full=None, part=None, hl=None, rev=None)); V.update(v)
    T = [t for t in F.trades(ds, days, F.LIVE, F.P(), ctx) if not fri(t['day'])]
    a, b1, b2 = summ(days, T), summ(H1, T), summ(H2, T)
    print(f"  {name:<52} trades {a['n']:3d} PF {a['pf']:4.2f} ({b1['pf']:4.2f}/{b2['pf']:4.2f}) total {a['ret']:+6.1f}% maxDD {a['dd']:4.1f}% avg/trade {a['avg']:+5.2f}%")
