#!/usr/bin/env python3
"""Daily-return decay from $10k to $5B (v5.2.15 lists), same capacity/impact model as scale_500k.py.
    python3 tools/backtest/scale_decay.py > tools/backtest/results/scale_decay.txt
A: both systems on their ETFs (what we trade today). B: FADE traded on the liquid proxy itself (index/futures-style, 0.03% cost, 1x), PULLBACK on its ETFs.
For each size the best position cap (share of signal-bar dollar volume) is chosen. The impact term is an ASSUMPTION; beyond ~$50M the result is an extrapolation of that model.
"""
import io, contextlib, math
with contextlib.redirect_stdout(io.StringIO()):
    import scale_500k as S
caps = (None, 0.50, 0.30, 0.20, 0.10, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001)
A = S.base
B = [S.prep(c, direct=True) for c in S.f0] + [S.prep(c) for c in S.p0]
sizes = (10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1e6, 2.5e6, 5e6, 10e6, 25e6, 50e6, 100e6, 250e6, 500e6, 1e9, 2.5e9, 5e9)
def best(cs, a):
    r = {c: S.account(cs, a, c) for c in caps}
    c = max(r, key=lambda k: r[k]['day']); return c, r[c]
print(f"{'account':>15} | {'A: ETFs':>8} {'cap':>6} {'avg pos $':>13} {'$/day':>14} | {'B: FADE on proxy':>16} {'cap':>6} {'avg pos $':>14} {'$/day':>14}")
for a in sizes:
    ca, ra = best(A, a); cb, rb = best(B, a)
    f = lambda c: 'none' if c is None else (f"{c*100:g}%")
    print(f"{a:>15,.0f} | {ra['day']:>+7.3f}% {f(ca):>6} {ra['avgpos']:>13,.0f} {a*ra['day']/100:>14,.0f} | {rb['day']:>+15.3f}% {f(cb):>6} {rb['avgpos']:>14,.0f} {a*rb['day']/100:>14,.0f}")
