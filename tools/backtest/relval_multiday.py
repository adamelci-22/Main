#!/usr/bin/env python3
"""RELVAL held longer than one day (governor 2026-11-19: "What about relval held over more than 1 day?"). Research only.
Same signal (a=48 z=72 xm=1.0); exit variants: out 15:55 (live), next 9:35, next close, close of day 2 / 3 / 5. Target half the gap
(live) or none; stop one gap (live) or none, checked on 5-minute bars every day held. Trades alone (no shared account, since a
multi-day hold would block the intraday book; that cost is shown as days held). Per year: total of leg % x size (3% risk, cash cap).
TRAIN 2022/2024/2026, TEST 2023/2025.
    python3 -I tools/backtest/relval_multiday.py > tools/backtest/results/relval_multiday_2026-11-19.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS
B = FR.B; ds = B.ds; dm = FR.dm; COST = NS.COST
sig = []
rel = {p: {x: ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0] for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']} for p in ['SOXX', 'IWM', 'XLK', 'XBI', 'XLF']}
for p in rel:
    for d in dm:
        b = ds.bars[p].get(d); q = ds.bars['QQQ'].get(d)
        if not b or len(b) < 78 or not q or len(q) < 78: continue
        i = ds.idx[d]; h = [rel[p][x] for x in ds.days[max(0, i - 20):i] if x in rel[p]]
        if len(h) < 15: continue
        sd = st.pstdev(h) or 1e-9
        for j in range(48, 72):
            rp = b[j][3] / b[0][0] - q[j][3] / q[0][0]
            if abs(rp) * 100 >= 1.0 and abs(rp) >= 2.5 * sd: sig.append((p, d, j + 1, rp)); break


def run(p, d, k, rp, ndays, at, tg, sm):
    """Hold through `ndays` extra sessions; exit at bar `at` (1 = 9:35 open, 77 = 15:55 open) of the last day."""
    s = -1 if rp > 0 else 1; b = ds.bars[p][d]; e = b[k][0]; gap = abs(rp) * e
    stop = e - s * sm * gap if sm else None; T = e + s * tg * gap if tg else None; i = ds.idx[d]; held = 0
    for n in range(ndays + 1):
        if i + n >= len(ds.days): return None
        dd = ds.days[i + n]; bb = ds.bars[p].get(dd)
        if not bb or len(bb) < 78: return None
        j0 = k if n == 0 else 0; j1 = at if n == ndays else 77
        for j in range(j0, j1 + 1):
            o, h, l, c, v = bb[j]
            if n == ndays and j == j1: return 3 * s * (o - e) / e * 100 - COST, n
            fav, adv = (h, l) if s > 0 else (l, h)
            if stop is not None and (adv - stop) * s <= 0: return 3 * s * ((stop if (o - stop) * s >= 0 else o) - e) / e * 100 - COST, n
            if T is not None and (fav - T) * s >= 0: return 3 * s * ((T if (o - T) * s <= 0 else o) - e) / e * 100 - COST, n
        if n < ndays and j1 == 77: pass


YRS = ['2022', '2023', '2024', '2025', '2026']; TR = ['2022', '2024', '2026']; TE = ['2023', '2025']
print(__doc__.split('\n')[0]); print(f"   {len(sig)} signals. Columns: account % per year (sum of trades sized at 3% risk, cash cap) | TRAIN / TEST sums | PF, win, avg leg %, average days held\n")
for tg, sm, lab in ((0.5, 1.0, 'target 0.5 gap, stop 1 gap'), (None, 1.0, 'no target, stop 1 gap'), (None, None, 'no target, no stop')):
    print(lab)
    for ndays, at, name in ((0, 77, 'out 15:55 same day (LIVE)'), (1, 1, 'out next 9:35'), (1, 77, 'out next 15:55'), (2, 77, 'out day 2 15:55'), (3, 77, 'out day 3 15:55'), (5, 77, 'out day 5 15:55')):
        if ndays == 0 and not (tg == 0.5 and sm == 1.0) and lab != 'no target, stop 1 gap': pass
        R = []
        for p, d, k, rp in sig:
            x = run(p, d, k, rp, ndays, at, tg, sm)
            if x is None: continue
            frac = min(1.0, 3.0 / max(3 * (sm or 1.0) * abs(rp) * 100, 0.3)); R.append((d[:4], x[0], x[0] * frac, x[1]))
        y = {Y: sum(r[2] for r in R if r[0] == Y) for Y in YRS}; pcts = [r[1] for r in R]
        g = sum(v for v in pcts if v > 0); l = -sum(v for v in pcts if v <= 0)
        print(f"   {name:<28} {' '.join(f'{y[Y]:+7.1f}' for Y in YRS)} | TRAIN {sum(y[Y] for Y in TR):+7.1f} TEST {sum(y[Y] for Y in TE):+6.1f} | PF {g / l if l else 99:.2f} win {100 * np.mean([v > 0 for v in pcts]):.0f}% avg {np.mean(pcts):+.2f}% held {np.mean([r[3] for r in R]):.1f}d", flush=True)
    print()
