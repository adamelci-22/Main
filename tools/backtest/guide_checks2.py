#!/usr/bin/env python3
"""Risk-size sensitivity and what the A1.13 -15% stop would have done on the 5-year FADE record (live rules, six proxies).
    /usr/bin/python3 -I tools/backtest/guide_checks2.py M5.json.gz > tools/backtest/results/guide_checks2.txt"""
import contextlib, io, os, statistics as st, sys
SRC = sys.argv[1]; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.argv = ['regime_adapt.py', SRC]
with contextlib.redirect_stdout(io.StringIO()):
    import regime_adapt as RA
F = RA.F; ds = RA.ds; T = RA.T; days = RA.days; CUT = '2026-03-01'
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]
print("FADE only (six proxies), live rules, Massive full tape; compounding account, risk per trade as shown (live = 3%)\n")
print(f"{'risk/trade':<11}{'before 2026-03: return':>24}{'max DD':>8}{'%/day':>8}{'since 2026-03: return':>26}{'max DD':>8}")
for r in (0.03, 0.02, 0.015, 0.01, 0.005):
    a = F.account(ds, pre, [t for t in T if t['day'] < CUT], risk=r); b = F.account(ds, rec, [t for t in T if t['day'] >= CUT], risk=r)
    print(f"{r*100:>5.1f}%     {a['ret']:>22.1f}% {a['mdd']:>7.1f}% {st.mean(a['daily'].values()):>+8.3f}{b['ret']:>24.1f}% {b['mdd']:>7.1f}%")
print("\nA1.13 stop (15% below the all-time high of equity, then trading stops until the governor restarts), whole five years at 3% risk, start 2021-11:")
for r in (0.03, 0.015):
    a = F.account(ds, days, T, risk=r); eq = 1.0; ath = 1.0; hit = None; path = []
    for d in days:
        eq *= 1 + a['daily'][d] / 100; ath = max(ath, eq); path.append((d, eq))
        if hit is None and eq <= 0.85 * ath: hit = (d, eq, ath)
    print(f"  risk {r*100:.1f}%: without the stop the account ends at {eq*100-100:+.1f}% (peak {ath*100-100:+.1f}%); " + (f"the stop fires on {hit[0]} at {hit[1]*100-100:+.1f}% (high was {hit[2]*100-100:+.1f}%): stopping there avoids {100*(eq/hit[1]-1):+.1f}% of further change" if hit else "the stop never fires"))
