#!/usr/bin/env python3
"""PULLBACK: sell more at the morning high, or cash out the runner at a fixed gain (governor 2026-11-17: "when the account is up over 4% on the day ... not to just
cash out ... what about selling more than 1/3 at the high"). Research only. Same harness and rule as pb_fade_exit.py (live joint book v5.2.61 without the giveback).
  A  share sold at the morning high: 1/3 (live), 1/2, 2/3, all
  B  1/3 at the high + the runner sold by a limit at +x % above entry (x = 2 3 4 5 6), the 20-EMA exit and breakeven stop still apply
  C  1/2 at the high + runner limit at +x %
    python3 -I tools/backtest/pb_cashout.py > tools/backtest/results/pb_cashout_2026-11-17.txt"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pb_three_tranche as P3
PS, ENT, book, yb, verdict, stat = P3.PS, P3.ENT, P3.book, P3.yb, P3.verdict, P3.stat


def manage(t, f1=1 / 3, cap=None):
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']; T = t['T']; C = e * (1 + cap / 100) if cap else None
    rem, g, hit, out = 1.0, 0.0, False, False; j = k
    for j in range(k, PS.LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if T is not None and not hit and h >= T:
            px = max(T, o); q = min(f1, rem); g += q * (px - e); rem -= q; hit = True; stop = max(stop, e)
            if rem <= 1e-9: break
        if hit and C is not None and h >= C: px = max(C, o); g += rem * (px - e); rem = 0; break
        if hit and j < PS.LAST and cl < t['e20'][j]: out = True
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, rv=t['rv'], sys=1)


def row(tag, T):
    y = book(T)
    print(f"   {verdict(y):<5}{tag:<46} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) | {stat(T)}")


print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026; parentheses = points a year vs the live exit\n')
print('A. SHARE SOLD AT THE MORNING HIGH (rest = runner)')
for f, nm in ((1 / 3, '1/3 (live)'), (0.5, '1/2'), (2 / 3, '2/3'), (1.0, 'all of it (the pre-11-12 rule)')): row(f'sell {nm} at the high', [manage(t, f) for t in ENT])
print('\nB. 1/3 AT THE HIGH + RUNNER CASHED OUT AT +x % ABOVE ENTRY')
for x in (2, 3, 4, 5, 6): row(f'runner sold at +{x}%', [manage(t, 1 / 3, x) for t in ENT])
print('\nC. 1/2 AT THE HIGH + RUNNER CASHED OUT AT +x %')
for x in (3, 4, 5): row(f'1/2 at high, runner sold at +{x}%', [manage(t, 0.5, x) for t in ENT])
