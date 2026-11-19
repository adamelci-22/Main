#!/usr/bin/env python3
"""Priority pick and a two-slot account (governor 2026-11-19: "what if we set up a priorty system or a 2/3 account to leave 1/3 for a
second signal or such"). Research only. Live book v5.2.64 (PULLBACK, IBS-LONG, MIRROR, DIP, RELVAL, overnight leg 50%), Massive tape.
Account model here: each trade's size = slot share x min(1, 3% / leg risk) of the start-of-day account; up to N positions at once;
same-system loss block; 3 entries a day; no entry after an IBS-family stop-out. With one slot of 1.0 it is the live book.
  SLOTS   1.0 (live) / 2/3 + 1/3 / 1/2 + 1/2 / 0.6 + 0.4. The first open position takes the big slot, a second concurrent one the small.
  PRIORITY  same-bar candidates ranked by relative volume (live) or by each (system, fund)'s TRAIN-year profit factor (TRAIN only).
QUALIFIES = beats live on TRAIN (2022, 2024, 2026) compounded and in 2 of 3 train years; PASSES = also beats live in BOTH 2023 and 2025.
    python3 -I tools/backtest/slots.py > tools/backtest/results/slots_2026-11-19.txt"""
import os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS
B, SB, TB, dm, TR, TE, ovn = FR.B, FR.SB, FR.TB, FR.dm, FR.TR, FR.TE, FR.ovn
END = NS.END; FAM = (2, 4, 5)
REL = B.BC.new(B.ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0)
ALL = [dict(t, sys=1, proxy=t.get('proxy', 'PB')) for t in FR.P0] + FR.I0 + FR.M + FR.D + REL
TRY = ('2022', '2024', '2026')


def run(trades, slots=(1.0,), key=lambda t: -t['rv']):
    by = TB.byday(trades); out = np.zeros(len(dm)); n_tr = 0; two = 0
    for n, d in enumerate(dm):
        cs = sorted(by.get(d, []), key=lambda t: (t['k'], key(t), t['sys']))
        busy = [None] * len(slots); g = 0.0; cnt = 0; lost = set(); famstop = False
        for t in cs:
            if cnt >= 3 or famstop or t['sys'] in lost: continue
            free = [i for i in range(len(slots)) if busy[i] is None or busy[i] < t['k']]
            if not free: continue
            i = min(free)                                   # the biggest free slot (slots listed big first)
            if any(b is not None and b >= t['k'] for b in busy): two += 1
            x = slots[i] * min(1.0, 3.0 / t['leg_risk']) * t['pct'] / 100; g += x; busy[i] = t['xbar']; cnt += 1; n_tr += 1
            if x <= 0: lost.add(t['sys'])
            if t['sys'] in FAM and x < 0 and t['xbar'] < END - 1: famstop = True
        out[n] = g
    return (1 + out) * (1 + 0.5 * ovn) - 1, n_tr, two


def cm(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


def dd(r): eq = np.cumprod(1 + r); return float((1 - eq / np.maximum.accumulate(eq)).max() * 100)


def pf(a): g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 9.0


# train-only priority score per (system, fund)
grp = defaultdict(list)
for t in ALL:
    if t['day'][:4] in TRY: grp[(t['sys'], t['proxy'])].append(t['pct'])
PRI = {k: pf(v) for k, v in grp.items()}
pri_key = lambda t: -PRI.get((t['sys'], t['proxy']), 1.0)

r0, n0, _ = run(ALL); y0 = SB.yret(r0)


def row(tag, r, n, two):
    y = SB.yret(r); q = cm(y, TR) > cm(y0, TR) and (y[TR] > y0[TR]).sum() >= 2
    v = 'PASS' if q and (y[TE] > y0[TE]).all() else 'qual' if q else ''
    print(f"   {v:<5}{tag:<40} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cm(y, TR) - cm(y0, TR):+7.1f} TEST {cm(y, TE) - cm(y0, TE):+6.1f} | avg 22-25 {y[:4].mean():+6.1f} | DD {dd(r):4.1f}% | trades {n}, second-slot {two}", flush=True)


print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | TRAIN / TEST compounded, points vs live (one slot, relative-volume pick)\n')
print(f"   check: this model with one slot = live book (BA.acct): 2022-26 {' '.join(f'{a:+.1f}' for a in y0)}")
row('LIVE: one slot 1.0, relative volume', r0, n0, 0)
row('PRIORITY by train PF, one slot', *run(ALL, key=pri_key))
for sl, nm in (((2 / 3, 1 / 3), '2/3 + 1/3'), ((0.6, 0.4), '0.6 + 0.4'), ((0.5, 0.5), '1/2 + 1/2')):
    row(f'SLOTS {nm}, relative volume', *run(ALL, sl))
    row(f'SLOTS {nm}, priority by train PF', *run(ALL, sl, pri_key))
print('\n   train-year profit factor per (system, fund), the priority order:')
NAME = {0: 'RELVAL', 1: 'PULLBACK', 2: 'DIP', 4: 'IBS-LONG', 5: 'MIRROR'}
for (s, p), v in sorted(PRI.items(), key=lambda x: -x[1]): print(f"      {NAME[s]:<9}{p:<5} PF {v:.2f} (n {len(grp[(s, p)])})")
print('\n   SAME RISK REFERENCE: one slot at a smaller size (is the second slot better than simply trading smaller?)')
for f in (2 / 3, 0.6, 0.5): row(f'one slot at {f:.2f} of the account', *run(ALL, (f,)))
print('\n   SMALLER SECOND SLOT')
for sl in ((0.8, 0.2), (0.75, 0.25), (0.85, 0.15)): row(f'SLOTS {sl[0]:.2f} + {sl[1]:.2f}, relative volume', *run(ALL, sl))
