#!/usr/bin/env python3
"""Capitalize on skipped 9:35 signals by trading the index (governor 2026-11-19: "there must be a system were we can capitalize on those
skips"). Research only. On mornings when 2+ funds give the same-side 9:35 signal (IBS-LONG and DIP long, MIRROR short), the skipped
funds are mostly the same market move (same-day outcome correlation 0.48). Variants replace the relative-volume pick on those mornings:
  INDEX   one trade in the QQQ leg (TQQQ long / SQQQ short), same 9:35 entry, 1% proxy stop, out 15:55
  BREADTH the live pick, but only on mornings with N+ same-side signals (N = 2, 3): a test of whether breadth itself is the edge
Live book v5.2.64. QUALIFIES = beats live on TRAIN (2022, 2024, 2026) compounded and in 2 of 3 train years; PASSES = also both TEST years.
    python3 -I tools/backtest/breadth_index.py > tools/backtest/results/breadth_index_2026-11-19.txt"""
import os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import slots as S, new_systems as NS
B, SB, dm, TR, TE = S.B, S.SB, S.dm, S.TR, S.TE
FAMS = (2, 4, 5); fam = [t for t in S.ALL if t['sys'] in FAMS]; other = [t for t in S.ALL if t['sys'] not in FAMS]
side = lambda t: -1 if t['sys'] == 5 else 1
by = defaultdict(list)
for t in fam: by[(t['day'], side(t))].append(t)


def qqq_trade(d, s, sys):
    b = B.ds.bars['QQQ'].get(d)
    if not b or len(b) < 78: return None
    e = b[1][0]; x, g, r = NS.mg(b, 1, s, e, e * (1 - s * 0.01), NS.END); t = NS.fin(d, 'QQQ', 1, x, e, g, r)
    t.update(rv=99.0, sys=sys); return t


def variant(mode, N=2):
    out = list(other)
    for (d, s), cs in by.items():
        if mode == 'index' and len(cs) >= N:
            q = qqq_trade(d, s, cs[0]['sys'])
            if q: out.append(q); continue
        if mode == 'breadth' and len(cs) < N: continue
        out.extend(cs)
    return out


r0, n0, _ = S.run(S.ALL); y0 = SB.yret(r0)


def cm(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


def row(tag, T):
    r, n, _ = S.run(T); y = SB.yret(r); q = cm(y, TR) > cm(y0, TR) and (y[TR] > y0[TR]).sum() >= 2
    v = 'PASS' if q and (y[TE] > y0[TE]).all() else 'qual' if q else ''
    print(f"   {v:<5}{tag:<46} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cm(y, TR) - cm(y0, TR):+7.1f} TEST {cm(y, TE) - cm(y0, TE):+6.1f} | avg 22-25 {y[:4].mean():+6.1f} | DD {S.dd(r):4.1f}% | trades {n}", flush=True)


print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | points vs live\n')
row('LIVE (relative-volume pick)', S.ALL)
for N in (2, 3, 4): row(f'INDEX: QQQ leg when {N}+ funds signal', variant('index', N))
for N in (2, 3): row(f'BREADTH: trade only mornings with {N}+ signals', variant('breadth', N))
m = {k: v for k, v in by.items() if len(v) >= 2}
q = [qqq_trade(d, s, 4) for (d, s) in m]; q = [t for t in q if t]
p = [t['pct'] for t in q]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
print(f"\n   QQQ leg on the {len(q)} multi-signal mornings alone: avg {np.mean(p):+.2f}% leg, win {100*np.mean([x>0 for x in p]):.0f}%, PF {g/l:.2f}")
