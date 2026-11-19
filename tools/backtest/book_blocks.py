#!/usr/bin/env python3
"""Blocked and freed trades in the live book (governor 2026-11-19: "Counting what gets blocked or freed up"). Research only.
Live book v5.2.64 on the Massive tape 2022-01..2026-10, one shared account (one position at a time, 3 entries a day, same-system loss
block, no entry after an IBS-family stop-out). Part 1: per system, signals offered, taken, and lost to each other system, with what the
lost signals would have made (leg %, sized at 3% risk, as if taken alone). Part 2: drop each system: how many trades of the others it
frees, what those freed trades make, against what the dropped system made. The overnight leg runs beside the book and blocks nothing.
    python3 -I tools/backtest/book_blocks.py > tools/backtest/results/book_blocks_2026-11-19.txt"""
import os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS, book_audit as BA
B, TB, dm, NSb = FR.B, FR.TB, FR.dm, BA.NS
SYS = {1: 'PULLBACK', 4: 'IBS-LONG', 5: 'MIRROR', 2: 'DIP', 0: 'RELVAL'}
ALLT = {1: FR.P0, 4: FR.I0, 5: FR.M, 2: FR.D, 0: B.BC.new(B.ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0)}
FAM = BA.FAM
for s_, L_ in ALLT.items():
    for n_, t_ in enumerate(L_): t_['uid'] = (s_, n_)


def sim(ids):
    """Returns taken {(day, sys, k)}, lost list of (trade, reason, holder)."""
    by = TB.byday([dict(t, sys=s) for s in ids for t in ALLT[s]]); taken = set(); lost = []
    for d in dm:
        cs = sorted(by.get(d, []), key=lambda t: (t['k'], -t['rv'], t['sys'])); free = 0; cnt = 0; lostsys = set(); holder = None; famstop = False
        for t in cs:
            if cnt >= 3: lost.append((t, 'cap', None)); continue
            if t['sys'] in lostsys: lost.append((t, 'loss block', t['sys'])); continue
            if famstop: lost.append((t, 'IBS stop-out', None)); continue
            if t['k'] < free: lost.append((t, 'busy', holder)); continue
            g = min(1.0, 3.0 / t['leg_risk']) * t['pct']; taken.add(t['uid']); free = t['xbar'] + 1; cnt += 1; holder = t['sys']
            if g <= 0: lostsys.add(t['sys'])
            if t['sys'] in FAM and g < 0 and t['xbar'] < NSb.END - 1: famstop = True
    return taken, lost


def acct_pct(t): return min(1.0, 3.0 / t['leg_risk']) * t['pct']


def pf(a): g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 99.0


print(__doc__.split('\n')[0])
ids = list(SYS); taken, lost = sim(ids)
print('\nPART 1. LIVE BOOK: signals offered, taken, lost (account % = each trade sized at 3% risk, summed, not compounded)')
print(f"   {'system':<10}{'offered':>8}{'taken':>7}{'lost':>6} | taken: sum acct %, PF | lost: sum acct %, PF | lost to (count)")
for s in ids:
    off = ALLT[s]; tk = [t for t in off if t['uid'] in taken]; ls = [x for x in lost if x[0]['sys'] == s]
    why = defaultdict(int)
    for t, r, h in ls: why[(SYS.get(h) if r == 'busy' else r) or r] += 1
    lp = [acct_pct(t) for t, r, h in ls]
    print(f"   {SYS[s]:<10}{len(off):>8}{len(tk):>7}{len(ls):>6} | {sum(acct_pct(t) for t in tk):+7.1f}, PF {pf([acct_pct(t) for t in tk]):.2f} | {sum(lp):+7.1f}, PF {pf(lp):.2f} | " + ', '.join(f'{k} {v}' for k, v in sorted(why.items(), key=lambda x: -x[1])))
print('\nPART 2. DROP ONE SYSTEM: trades of the others it frees')
print(f"   {'dropped':<10} {'its trades':>10} {'its sum acct %':>15} | {'freed trades':>12} {'freed sum acct %':>17} {'freed PF':>9} | net (freed - dropped)")
for s in ids:
    rest = [x for x in ids if x != s]; tk2, _ = sim(rest)
    mine = [t for t in ALLT[s] if t['uid'] in taken]; m = sum(acct_pct(t) for t in mine)
    freed = [t for x in rest for t in ALLT[x] if t['uid'] in tk2 and t['uid'] not in taken]
    gone = [t for x in rest for t in ALLT[x] if t['uid'] in taken and t['uid'] not in tk2]
    f = sum(acct_pct(t) for t in freed) - sum(acct_pct(t) for t in gone); bys = defaultdict(int)
    for t in freed: bys[SYS[t['sys']]] += 1
    print(f"   {SYS[s]:<10} {len(mine):>10} {m:>+15.1f} | {len(freed):>12} {f:>+17.1f} {pf([acct_pct(t) for t in freed]):>9.2f} | {f - m:+7.1f}   freed: " + ', '.join(f'{k} {v}' for k, v in sorted(bys.items(), key=lambda x: -x[1])) + (f'; {len(gone)} other trades lost' if gone else ''))
