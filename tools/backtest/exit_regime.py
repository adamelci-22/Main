#!/usr/bin/env python3
"""After-2R exit study on live FADE (30-min box).  /usr/bin/python3 -I tools/backtest/exit_regime.py {rh|M5.json.gz}
Part 1: trade anatomy under the LIVE exits (how many reach 1R/2R/3R; for trades past 2R: peak vs runner exit = giveback).
Part 2: exit-regime grid (tranches + runner ratchet), halves + whole, %/day account-level, same costs/rules as the live backtest.
Ratchets on the runner (start after the first tranche):
 chand k  : best close - k x ATR(14)        lag x : stop = (best close in R) - x R
 pct f    : stop = f x (best close in R)    hi    : same as lag but on bar HIGHS (intrabar peak) instead of closes
Stops only move up, never below the stop set by the tranche."""
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
SCH = {}

def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    tr, st_, rat = SCH['tr'], SCH['st'], SCH['rat']; last = SCH.get('last', c.last)
    at = ctx_['atr'][p][d]
    rem = 1.0; gross = 0.0; i = 0; hic = entry; bestc = 0.0; besth = 0.0; mfe = 0.0; why = 'time'; xbar = last; nh = 0
    tp_bar = None; run_exit = None
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        mfe = max(mfe, (fav - entry) * s / r)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; run_exit = (px - entry) * s / r; rem = 0; why = 'stop' if nh == 0 else 'trail'; xbar = j; break
        while i < len(tr) and (fav - (entry + s * tr[i][0] * r)) * s >= 0:
            T = entry + s * tr[i][0] * r; px = T if (o - T) * s <= 0 else o
            gross += tr[i][1] * (px - entry) * s; rem -= tr[i][1]; nh += 1
            if tp_bar is None: tp_bar = j
            ns = entry + s * st_[i] * r
            if (ns - stop) * s > 0: stop = ns
            i += 1
        if rem <= 1e-9: why = 'target'; xbar = j; rem = 0; break
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        bestc = max(bestc, (cl - entry) * s / r); besth = max(besth, (fav - entry) * s / r)
        if nh and j < last:
            kind = rat[0]
            if kind == 'chand': ns = hic - s * rat[1] * at[j]
            elif kind == 'lag': ns = entry + s * (bestc - rat[1]) * r
            elif kind == 'hi': ns = entry + s * (besth - rat[1]) * r
            elif kind == 'pct': ns = entry + s * (rat[1] * bestc) * r
            else: ns = stop
            if (ns - stop) * s > 0: stop = ns
    if rem > 0:
        gross += rem * (b[last][3] - entry) * s; run_exit = (b[last][3] - entry) * s / r
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=xbar, why=why, hit=nh > 0, R_out=gross / r, mfe=mfe, run_exit=run_exit, tp_bar=tp_bar,
                pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info

F._manage = manage
base = F.P()
def trades(dd): return F.trades(ds, dd, syms, base, ctx)
def run(dd):
    T = trades(dd); a = F.account(ds, dd, T); s = F.stat(a); taken = a['taken']
    return s, (sum(t['R_out'] for t in taken) / len(taken) if taken else 0)
def setp(tr, st_, rat, last=None):
    SCH.clear(); SCH.update(tr=tr, st=st_, rat=rat)
    if last: SCH['last'] = last

print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'}: {days[0]}..{days[-1]}, {len(days)} days; halves split at {SPLIT}")
# ---------- PART 1: anatomy under LIVE exits
setp([(2.0, 1/3)], [0.0], ('chand', 2.0))
T = trades(days); a = F.account(ds, days, T); tk = a['taken']
n = len(tk); mean = lambda x: sum(x) / len(x) if x else 0
print(f"\nPART 1 - the {n} trades the account actually took, LIVE exits (1/3 at 2R, stop to breakeven, 2-ATR chandelier on closes, out 13:30)")
print("  share whose best price reached:  " + '  '.join(f">={m}R {100*sum(t['mfe']>=m for t in tk)/n:.0f}%" for m in (0.5, 1, 1.5, 2, 2.5, 3, 4, 5)))
hit = [t for t in tk if t['hit']]; miss = [t for t in tk if not t['hit']]
print(f"  reached 2R: {len(hit)} ({100*len(hit)/n:.0f}%); never reached 2R: {len(miss)} ({100*len(miss)/n:.0f}%), their avg result {mean([t['R_out'] for t in miss]):+.2f}R")
print(f"  never reached 2R but reached 1R first: {sum(t['mfe']>=1 for t in miss)} ({100*sum(t['mfe']>=1 for t in miss)/n:.0f}% of all trades); their avg result {mean([t['R_out'] for t in miss if t['mfe']>=1]):+.2f}R")
if hit:
    pk = [t['mfe'] for t in hit]; rx = [t['run_exit'] for t in hit]
    print(f"  trades past 2R ({len(hit)}): runner peak avg {mean(pk):.2f}R (median {st.median(pk):.2f}R); runner exit avg {mean(rx):+.2f}R (median {st.median(rx):+.2f}R)")
    print(f"     giveback per runner (peak - exit) avg {mean([a_-b_ for a_,b_ in zip(pk,rx)]):.2f}R; runner kept {100*mean([max(b_,0)/a_ for a_,b_ in zip(pk,rx)]):.0f}% of its peak on average")
    print(f"     runner exits: " + ', '.join(f"{w} {sum(t['why']==w for t in hit)}" for w in ('trail', 'time', 'target')))
    print(f"     runner exit buckets: " + '  '.join(f"{lo}..{hi}R: {sum(lo<=x<hi for x in rx)}" for lo, hi in ((-9, 0.01), (0.01, 1), (1, 2), (2, 3), (3, 99))))
    print(f"     whole trade result for these: avg {mean([t['R_out'] for t in hit]):+.2f}R")
print(f"  all trades avg {mean([t['R_out'] for t in tk]):+.2f}R; win {100*sum(t['pct']>0 for t in tk)/n:.0f}%")

# ---------- PART 2: grid
print("\nPART 2 - exit regimes.  each cell: %/day (all days)  avgR  win%  maxDD   | first half | second half | whole")
rows = []
def show(tag, tr, st_, rat, last=None):
    setp(tr, st_, rat, last); out = [run(dd) for dd in (H1, H2, days)]
    rows.append((tag, out))
    print(f"{tag:<46}" + ''.join(f" | {s['avg']:+.3f} {r:+.2f}R {s['win']:2.0f}% DD{s['mdd']:4.1f}" for s, r in out))
L = [(2.0, 1/3)]
show('LIVE  1/3@2R  BE  chand 2.0', L, [0.0], ('chand', 2.0))
print('-- same 1/3@2R + BE, tighter runner ratchet')
for k in (0.5, 0.75, 1.0, 1.5, 3.0): show(f'1/3@2R  BE  chand {k}', L, [0.0], ('chand', k))
for x in (0.5, 0.75, 1.0, 1.5): show(f'1/3@2R  BE  lag {x}R (closes)', L, [0.0], ('lag', x))
for x in (0.5, 1.0, 1.5): show(f'1/3@2R  BE  lag {x}R (highs)', L, [0.0], ('hi', x))
for f in (0.33, 0.5, 0.66, 0.75): show(f'1/3@2R  BE  lock {int(f*100)}% of best close', L, [0.0], ('pct', f))
print('-- 1/3@2R with the runner stop to +1R (not breakeven)')
for rat in (('chand', 1.0), ('chand', 2.0), ('lag', 1.0), ('pct', 0.5)): show(f'1/3@2R  stop+1R  {rat[0]} {rat[1]}', L, [1.0], rat)
print('-- second tranche')
for rat in (('chand', 1.0), ('chand', 2.0), ('lag', 1.0)): show(f'1/3@2R BE, 1/3@3R +1R, {rat[0]} {rat[1]}', [(2.0, 1/3), (3.0, 1/3)], [0.0, 1.0], rat)
for rat in (('chand', 1.0), ('chand', 2.0), ('lag', 1.0)): show(f'1/2@2R BE, rest {rat[0]} {rat[1]}', [(2.0, 0.5)], [0.0], rat)
print('-- single targets / no target')
for R in (2.0, 2.5, 3.0, 4.0): show(f'all out at {R}R', [(R, 1.0)], [0.0], ('fix',))
for rat in (('chand', 1.0), ('chand', 2.0), ('lag', 1.0)): show(f'no partial, after 2R: BE + {rat[0]} {rat[1]}', [(2.0, 1e-6)], [0.0], rat)
print('-- time exit with live exits')
for lb, nm in ((41, '12:55'), (53, '13:55'), (65, '14:55'), (75, '15:45')): show(f'LIVE exits, out at {nm}', L, [0.0], ('chand', 2.0), lb)

print("\nRANKING by first half -> where it lands in the second half (whole sample in brackets)")
r1 = sorted(rows, key=lambda x: -x[1][0][0]['avg'])
for tag, out in r1[:12]:
    print(f"  {tag:<46} H1 {out[0][0]['avg']:+.3f}  H2 {out[1][0]['avg']:+.3f}  [{out[2][0]['avg']:+.3f}]")
