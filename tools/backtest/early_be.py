#!/usr/bin/env python3
"""Protect the losers: move the stop up early (no shares sold) once the trade is up X R, keep the live 1/3@2R + 2-ATR chandelier for the winners.
   /usr/bin/python3 -I tools/backtest/early_be.py {rh|M5.json.gz}
Steps = [(trigger R reached intrabar, new stop in R)], applied as soon as the bar's high reaches the trigger (stop takes effect from the next bar)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
STEPS = []
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; mfe = 0.0; why = 'time'; xbar = last
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop'; xbar = j; break
        mfe = max(mfe, (fav - entry) * s / r)
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o
            gross += (1 / 3) * (px - entry) * s; rem = 2 / 3; hit = True
            if (entry - stop) * s > 0: stop = entry
        for trig, ns_r in STEPS:
            if mfe >= trig:
                ns = entry + s * ns_r * r
                if (ns - stop) * s > 0: stop = ns
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * 2.0 * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=xbar, why=why, hit=hit, R_out=gross / r, mfe=mfe, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage
base = F.P()
print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'} {days[0]}..{days[-1]}; split {SPLIT}")
print("cell: %/day  | trades  win%  full losers (<= -0.9R)  avg loss R  avg win R  maxDD     for first half | second half | all")
def show(tag, steps):
    STEPS[:] = steps; out = []
    for dd in (H1, H2, days):
        T = F.trades(ds, dd, syms, base, ctx); a = F.account(ds, dd, T); s = F.stat(a); tk = a['taken']
        L = [t['R_out'] for t in tk if t['pct'] <= 0]; W = [t['R_out'] for t in tk if t['pct'] > 0]
        full = sum(1 for t in tk if t['R_out'] <= -0.9)
        out.append(f"{s['avg']:+.3f} {len(tk):3d}t {s['win']:2.0f}%w full-1R {100*full/len(tk):2.0f}% L{sum(L)/len(L) if L else 0:+.2f} W{sum(W)/len(W) if W else 0:+.2f} DD{s['mdd']:4.1f}")
    print(f"{tag:<40} | " + ' | '.join(out))
show('LIVE (BE only after the 2R partial)', [])
for trig in (0.5, 0.75, 1.0, 1.25, 1.5):
    show(f'at +{trig}R -> stop to breakeven', [(trig, 0.0)])
for trig, lock in ((1.0, 0.1), (1.0, 0.25), (1.5, 0.25), (1.5, 0.5)):
    show(f'at +{trig}R -> lock +{lock}R', [(trig, lock)])
for trig in (0.5, 1.0):
    show(f'at +{trig}R -> stop to -0.5R (halve the loss)', [(trig, -0.5)])
show('at +0.5R -> -0.5R, at +1R -> BE', [(0.5, -0.5), (1.0, 0.0)])
show('at +1R -> BE, at +1.5R -> +0.5R', [(1.0, 0.0), (1.5, 0.5)])
