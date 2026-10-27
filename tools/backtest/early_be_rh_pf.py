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

print(f"Robinhood data {days[0]}..{days[-1]} ({len(days)} days). Profit factor = $ won on green trades / $ lost on red trades (account-level, after costs).")
print(f"{'stop rule':<36} {'trades':>6} {'green':>6} {'PF':>5} {'%/day':>7} {'avg green':>9} {'avg red':>8} {'total':>7}")
def show(tag, steps):
    STEPS[:] = steps
    T = F.trades(ds, days, syms, base, ctx); a = F.account(ds, days, T); s = F.stat(a); tk = a['taken']
    g = [t['acct'] for t in tk if t['acct'] > 0]; l = [t['acct'] for t in tk if t['acct'] <= 0]
    pf = sum(g) / -sum(l) if l and sum(l) < 0 else float('inf')
    print(f"{tag:<36} {len(tk):>6} {100*len(g)/len(tk):>5.0f}% {pf:>5.2f} {s['avg']:>+6.3f}% {sum(g)/len(g):>+8.2f}% {sum(l)/len(l):>+7.2f}% {a['ret']:>+6.1f}%")
show('LIVE (BE only after 2R partial)', [])
show('at +0.5R -> breakeven', [(0.5, 0.0)])
show('at +1R -> breakeven', [(1.0, 0.0)])
show('at +1R -> lock +0.1R', [(1.0, 0.1)])
show('at +1R -> stop to -0.5R', [(1.0, -0.5)])
show('at +1.5R -> breakeven', [(1.5, 0.0)])
