#!/usr/bin/env python3
"""1R trailing stop that only moves up and stops rising at a cap (locks +cap R), on top of the live exits (1/3 at 2R, BE, 2-ATR chandelier).
   /usr/bin/python3 -I tools/backtest/trail_cap.py {rh|M5.json.gz}
stop = max(stop, min(entry + cap R, best - dist R)); best = best HIGH (intrabar) or best CLOSE, updated at each 5-min bar (effective next bar)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
TR = {}
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; besth = 0.0; bestc = 0.0; why = 'time'; xbar = last
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop'; xbar = j; break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o
            gross += (1 / 3) * (px - entry) * s; rem = 2 / 3; hit = True
            if (entry - stop) * s > 0: stop = entry
        besth = max(besth, (fav - entry) * s / r); bestc = max(bestc, (cl - entry) * s / r)
        if TR:
            best = besth if TR['on'] == 'high' else bestc
            act = (besth if TR.get('act', 'none') == 'high' else bestc) >= TR.get('at', -99)
            if act:
                lvl = min(TR['cap'], best - TR['dist'])
                ns = entry + s * lvl * r
                if (ns - stop) * s > 0: stop = ns
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * 2.0 * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=xbar, why=why, hit=hit, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage
base = F.P()
print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'} {days[0]}..{days[-1]} ({len(days)} days); halves split {SPLIT}")
print(f"{'rule':<44} {'trades':>6} {'green':>6} {'PF':>5} {'%/day':>7} {'H1':>7} {'H2':>7} {'avg grn':>8} {'avg red':>8} {'maxDD':>6} {'total':>7}")
def show(tag, tr):
    TR.clear(); TR.update(tr)
    res = []
    for dd in (H1, H2, days):
        a = F.account(ds, dd, F.trades(ds, dd, syms, base, ctx)); res.append((a, F.stat(a)))
    a, s = res[2]; tk = a['taken']
    g = [t['acct'] for t in tk if t['acct'] > 0]; l = [t['acct'] for t in tk if t['acct'] <= 0]
    pf = sum(g) / -sum(l) if l and sum(l) < 0 else float('inf')
    print(f"{tag:<44} {len(tk):>6} {100*len(g)/len(tk):>5.0f}% {pf:>5.2f} {s['avg']:>+6.3f}% {res[0][1]['avg']:>+6.3f}% {res[1][1]['avg']:>+6.3f}% {sum(g)/len(g):>+7.2f}% {sum(l)/len(l):>+7.2f}% {s['mdd']:>5.1f}% {a['ret']:>+6.1f}%")
show('LIVE (no early trail)', {})
show('previous: trail on closes from the start, lock +0.75R', dict(dist=1.0, cap=0.75, on='close'))
for act in ('close', 'high'):
    print(f"-- stop frozen at -1R until the {'5-min CLOSE' if act == 'close' else 'price (any tick / bar high)'} reaches +1R; then 1R behind the best CLOSE, up only, capped at:")
    for cap in (0.25, 0.5, 0.75, 1.0, 99):
        show(f"   {'no cap' if cap == 99 else f'lock +{cap:.2f}R'}", dict(dist=1.0, cap=cap, on='close', act=act, at=1.0))
print("-- same, but trailing 1R behind the best HIGH (tick-level trail) after activation")
for cap in (0.5, 99):
    show(f"   {'no cap' if cap == 99 else f'lock +{cap:.2f}R'}", dict(dist=1.0, cap=cap, on='high', act='high', at=1.0))
