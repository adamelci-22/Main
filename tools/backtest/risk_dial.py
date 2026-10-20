#!/usr/bin/env python3
"""Risk-per-trade dial on the live FADE + PULLBACK system (same trades, size = min(cash, risk x equity / stop distance)).
    python3 tools/backtest/risk_dial.py > tools/backtest/results/risk_dial.txt
"""
import io, contextlib, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import manual as m, pb_final as PBF, mixed as MXD, final_system as FS
    from lab import get_data
D = get_data(); m.rvol = PBF.rvol(D); ALL = D.days[1:]; h = len(ALL) // 2; MAR = [d for d in ALL if d < '2026-04-07']
f, p = FS.cands(D, ALL)
print(f"Risk dial, {ALL[0]}..{ALL[-1]} ({len(ALL)} days), $2,000 start, one position, size capped at cash.\n")
print(f"{'risk':>5} {'%/day':>7} {'H1':>7} {'H2':>7} {'March':>7} {'return':>8} {'end $':>8} {'maxDD':>6} {'worst day':>9} {'worst trade':>11} {'trades not cash-capped':>23}")
for r in (0.03, 0.035, 0.04, 0.05):
    a = MXD.account(D, ALL, f + p, risk=r); dl = a['daily']
    eq = 2000.0; worst_tr = 0.0; uncapped = 0
    for x in a['taken']:
        if r / (x['risk'] / 100) < 1: uncapped += 1
        worst_tr = min(worst_tr, x['usd'] / eq * 100); eq += x['usd']
    v = lambda ds: st.mean(dl[d] for d in ds)
    print(f"{r*100:4.1f}% {v(ALL):+7.3f} {v(ALL[:h]):+7.3f} {v(ALL[h:]):+7.3f} {v(MAR):+7.3f} {a['ret']:+7.1f}% {2000*(1+a['ret']/100):8,.0f} {a['mdd']:5.1f}% "
          f"{min(dl.values()):+8.2f}% {worst_tr:+10.2f}% {uncapped:>10d} of {len(a['taken'])}")
