#!/usr/bin/env python3
"""1/3 at +0.5R, 1/3 at +2R, last 1/3 ratcheted; stop frozen at -1R until +1R, then optional 1R trail on closes (capped).
   /usr/bin/python3 -I tools/backtest/half_r_plan.py {rh|M5.json.gz}"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
C = {}
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last
    tr = C['tr']                      # [(R, fraction, stop-after-in-R or None)]
    rem = 1.0; gross = 0.0; i = 0; hic = entry; bestc = 0.0; why = 'time'; xbar = last; done_last = False
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop'; xbar = j; break
        while i < len(tr) and (fav - (entry + s * tr[i][0] * r)) * s >= 0:
            T = entry + s * tr[i][0] * r; px = T if (o - T) * s <= 0 else o
            gross += tr[i][1] * (px - entry) * s; rem -= tr[i][1]
            if tr[i][2] is not None:
                ns = entry + s * tr[i][2] * r
                if (ns - stop) * s > 0: stop = ns
            i += 1
        if rem <= 1e-9: why = 'target'; xbar = j; rem = 0; break
        bestc = max(bestc, (cl - entry) * s / r)
        if C.get('trail') and bestc >= 1.0:               # frozen until a 5-min close at +1R, then 1R behind the best close, capped
            ns = entry + s * min(C['trail'], bestc - 1.0) * r
            if (ns - stop) * s > 0: stop = ns
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if i == len(tr) and j < last:                       # all targets done: ratchet the last part
            rk = C['rat']
            if rk[0] == 'chand': ns = hic - s * rk[1] * at[j]
            elif rk[0] == 'lag': ns = entry + s * (bestc - rk[1]) * r
            else: ns = stop
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=xbar, why=why, hit=i > 0, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage
base = F.P()
print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'} {days[0]}..{days[-1]} ({len(days)} days); halves split {SPLIT}")
print(f"{'plan':<58} {'trades':>6} {'green':>6} {'PF':>5} {'%/day':>7} {'H1':>7} {'H2':>7} {'avg grn':>8} {'avg red':>8} {'maxDD':>6} {'total':>7}")
def show(tag, **cfg):
    C.clear(); C.update(cfg); res = []
    for dd in (H1, H2, days):
        a = F.account(ds, dd, F.trades(ds, dd, syms, base, ctx)); res.append((a, F.stat(a)))
    a, s = res[2]; tk = a['taken']
    g = [t['acct'] for t in tk if t['acct'] > 0]; l = [t['acct'] for t in tk if t['acct'] <= 0]
    pf = sum(g) / -sum(l) if l and sum(l) < 0 else float('inf')
    print(f"{tag:<58} {len(tk):>6} {100*len(g)/len(tk):>5.0f}% {pf:>5.2f} {s['avg']:>+6.3f}% {res[0][1]['avg']:>+6.3f}% {res[1][1]['avg']:>+6.3f}% {sum(g)/len(g):>+7.2f}% {sum(l)/len(l):>+7.2f}% {s['mdd']:>5.1f}% {a['ret']:>+6.1f}%")
LIVE = [(2.0, 1/3, 0.0)]
P = [(0.5, 1/3, None), (2.0, 1/3, 0.0)]
show('LIVE: 1/3@2R, BE, chandelier 2 ATR', tr=LIVE, rat=('chand', 2.0))
show('frozen trail cap +0.75R + live targets (last test)', tr=LIVE, rat=('chand', 2.0), trail=0.75)
print('-- YOUR PLAN: 1/3 @ +0.5R, 1/3 @ +2R (stop -> BE), last 1/3 ratcheted')
show('  frozen until +1R, then 1R trail cap +0.75R; last 1/3 chand 2', tr=P, rat=('chand', 2.0), trail=0.75)
show('  frozen until +1R, then 1R trail cap +0.75R; last 1/3 chand 3', tr=P, rat=('chand', 3.0), trail=0.75)
show('  frozen until +1R, then 1R trail cap +0.75R; last 1/3 1R lag', tr=P, rat=('lag', 1.0), trail=0.75)
show('  frozen until +1R, then 1R trail NO cap; last 1/3 chand 2', tr=P, rat=('chand', 2.0), trail=99)
show('  no early trail (stop -1R until 2R); last 1/3 chand 2', tr=P, rat=('chand', 2.0))
print('-- variations of the first slice')
show('  1/3 @ +0.5R -> stop to -0.5R, then as plan (cap +0.75R, chand 2)', tr=[(0.5, 1/3, -0.5), (2.0, 1/3, 0.0)], rat=('chand', 2.0), trail=0.75)
show('  1/4 @ +0.5R, 1/4 @ +2R, 1/2 ratcheted (cap +0.75R, chand 2)', tr=[(0.5, .25, None), (2.0, .25, 0.0)], rat=('chand', 2.0), trail=0.75)
show('  1/3 @ +1R, 1/3 @ +2R, 1/3 ratcheted (cap +0.75R, chand 2)', tr=[(1.0, 1/3, None), (2.0, 1/3, 0.0)], rat=('chand', 2.0), trail=0.75)
