#!/usr/bin/env python3
"""PULLBACK: signals for more room, less room, or an early loss cut, and an audit of the v5.2.61 3R giveback rule (governor 2026-11-17: "are there any signals
that suggest to give more room or less or cut losses and did the rule we just add help or hinder are there better alternatives"). Research only.
Base = live v5.2.61 (1/3 at the morning high, runner on the 20-EMA close, breakeven stop, 3R/40% giveback). One change at a time inside the live joint book.
Train 2022/2024/2026, test 2023/2025. QUALIFIES = beats base on train compounded and in 2 of 3 train years; PASSES = also both test years.
  LESS ROOM  runner out on a close under the leg's VWAP | on a 9-EMA close after 12:00 | on a 9-EMA close when that bar's volume is 1.5x the last 6
  MORE ROOM  runner holds the 20-EMA break while the leg is above VWAP (out on the 20-EMA only below VWAP) | 20-EMA exit needs 2 closes under it
  LOSS CUT   before the 1/3 fills: out if not +0.5R after 30 / 60 min | out on a close at -0.5R after 15 min (like FADE) | out on a close under VWAP
    python3 -I tools/backtest/pb_signals.py > tools/backtest/results/pb_signals_2026-11-17.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pb_three_tranche as P3
PS, ENT, book, verdict0, stat = P3.PS, P3.ENT, P3.book, P3.verdict, P3.stat
TR, TE = P3.TR, P3.TE


def vwap(b):
    pv = cv = 0.0; out = []
    for x in b: pv += (x[1] + x[2] + x[3]) / 3 * x[4]; cv += x[4]; out.append(pv / cv if cv else x[3])
    return out


def manage(t, c):
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']; T = t['T']; vw = vwap(b)
    rem, g, hit, out, bestc, below = 1.0, 0.0, False, False, e, 0; j = k; fired = None
    for j in range(k, PS.LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if not hit and h >= T: px = max(T, o); q = min(1 / 3, rem); g += q * (px - e); rem -= q; hit = True; stop = max(stop, e)
        bestc = max(bestc, cl); n = j - k + 1
        if not hit and j < PS.LAST:                                  # loss cuts before the 1/3
            if c.get('cut_time') and n >= c['cut_time'] and (bestc - e) / r < 0.5: out = True; fired = 'cut'
            if c.get('cut_r') and n >= 3 and cl <= e - 0.5 * r: out = True; fired = 'cut'
            if c.get('cut_vwap') and cl < vw[j]: out = True; fired = 'cut'
        if hit and j < PS.LAST:
            ema_break = cl < t['e20'][j]
            if c.get('two_closes'): below = below + 1 if ema_break else 0; ema_break = below >= 2
            if c.get('vwap_room') and cl >= vw[j]: ema_break = False
            if ema_break: out = True
            if c.get('vwap_out') and cl < vw[j]: out = True
            if c.get('late9') and j >= 30 and cl < t['e9'][j]: out = True                   # bar 30 = 12:00
            if c.get('vol9') and cl < t['e9'][j]:
                av = np.mean([x[4] for x in b[max(0, j - 6):j]]) or 1
                if v >= 1.5 * av: out = True
            if c.get('give', True) and (bestc - e) / r >= 3 and cl < e + 0.6 * (bestc - e) and not out: out = True; fired = 'give'
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, rv=t['rv'], sys=1, fired=fired)


base = [manage(t, {}) for t in ENT]; yb = book(base)


def verdict(y):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''


def row(tag, c):
    T = [manage(t, c) for t in ENT]; y = book(T)
    print(f"   {verdict(y):<5}{tag:<62} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) | {stat(T)}")
    return y


print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026; parentheses = points a year vs live v5.2.61\n')
print(f"   LIVE v5.2.61 (with the 3R giveback)                             {' '.join(f'{a:+7.1f}' for a in yb)} | avg 22-25 {yb[:4].mean():+6.1f} | {stat(base)}")
nog = [manage(t, dict(give=False)) for t in ENT]; fired = [(a, b) for a, b in zip(base, nog) if a['fired'] == 'give']
d = [a['pct'] - b['pct'] for a, b in fired]
print(f"\nAUDIT OF THE 3R GIVEBACK: fired on {len(fired)} of {len(base)} trades ({100 * len(fired) / len(base):.1f}%). Helped {sum(x > 0 for x in d)}, hurt {sum(x < 0 for x in d)}; "
      f"average change {np.mean(d) if d else 0:+.2f}% of the position per firing, total {sum(d):+.1f}%; best {max(d) if d else 0:+.2f}%, worst {min(d) if d else 0:+.2f}%")
row('without the 3R giveback (v5.2.60)', dict(give=False))
print('\nLESS ROOM for the runner')
row('runner out on a close under VWAP', dict(vwap_out=True)); row('runner on the 9-EMA after 12:00', dict(late9=True)); row('9-EMA close on 1.5x volume', dict(vol9=True))
print('\nMORE ROOM for the runner')
row('ignore the 20-EMA break while above VWAP', dict(vwap_room=True)); row('20-EMA exit needs 2 closes under it', dict(two_closes=True))
print('\nLOSS CUTS before the 1/3 fills')
row('out if not +0.5R after 30 min', dict(cut_time=6)); row('out if not +0.5R after 60 min', dict(cut_time=12)); row('out on a close at -0.5R after 15 min', dict(cut_r=True)); row('out on a close under VWAP', dict(cut_vwap=True))
