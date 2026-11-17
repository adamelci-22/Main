#!/usr/bin/env python3
"""PULLBACK: lock the runner's stop at the morning high (or part of the way) once price clears it (governor 2026-11-17: "What about gain cuts past the high").
Research only. Base = live v5.2.61. Once the leg trades x R above the morning high (x = 0, 0.5, 1, 2) the runner stop rises from breakeven to the morning high (or to
halfway between entry and the high). Same book and train/test rule as pb_signals.py.
    python3 -I tools/backtest/pb_lock_high.py > tools/backtest/results/pb_lock_high_2026-11-17.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pb_signals as SG
PS, ENT, book, yb, verdict, stat = SG.PS, SG.ENT, SG.book, SG.yb, SG.verdict, SG.stat


def manage(t, x, lvl):
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']; T = t['T']
    rem, g, hit, out, bestc, pend = 1.0, 0.0, False, False, e, None; j = k
    for j in range(k, PS.LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if pend is not None: stop = max(stop, pend); pend = None
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if not hit and h >= T: px = max(T, o); q = min(1 / 3, rem); g += q * (px - e); rem -= q; hit = True; stop = max(stop, e)
        bestc = max(bestc, cl)
        if hit and h >= T + x * r: pend = max(pend or -1e9, e + lvl * (T - e))
        if hit and j < PS.LAST:
            if cl < t['e20'][j]: out = True
            if (bestc - e) / r >= 3 and cl < e + 0.6 * (bestc - e): out = True
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, rv=t['rv'], sys=1)


print(__doc__.split('\n')[0]); print(f"   years 2022 2023 2024 2025 2026; parentheses = points a year vs live v5.2.61 (avg 22-25 {yb[:4].mean():+.1f})\n")
for lvl, nm in ((1.0, 'the morning high'), (0.5, 'halfway entry-to-high')):
    for x in (0, 0.5, 1, 2):
        T = [manage(t, x, lvl) for t in ENT]; y = book(T)
        print(f"   {verdict(y):<5}{'stop to ' + nm + f' once {x:g}R past the high':<54} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) | {stat(T)}")
