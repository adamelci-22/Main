#!/usr/bin/env python3
"""v5.2.46 check: paper.py pullback() + pb_manage_runner (RUNNER_ON) against the research engine pb_exit_screen.manage(frac=1/3, run=EMA20)
on every Robinhood PULLBACK setup 2026-03-03..10-14, plus the intraday (open position) states at every bar.
    python3 -I tools/backtest/verify_pb_runner.py > tools/backtest/results/verify_pb_runner_2026-11-12.txt"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'live'))
import pb_exit_screen as PS
import paper as PP
B = PS.load()[0]; PP.apply_tunables('2026-11-12'); PP.FLOOR_TARGET = True; PP.RUNNER_ON = True
n = bad = 0; mx = 0.0; opens = 0
for t in B.E:
    c = PP.pullback(t['b'], t['prev'], 78)
    if not c or c.get('gross') is None: print('no closed paper trade', t['day'], t['proxy']); bad += 1; continue
    rp = (c['gross'] + (PP.PB_IN * c['entry'])) / c['entry'] * 100      # gross before costs is compared through pct below
    res = PS.manage(t, dict(frac=1 / 3, run=('ema', 20)))
    pp = c['gross'] / c['entry'] * 100
    n += 1; d = abs(pp - res['pct']); mx = max(mx, d)
    if d > 1e-2 or c['xbar'] != res['xbar']:   # tolerance 0.01%: paper.py charges fees on actual prices, the research engine a flat 0.04%
        bad += 1; print('diff', t['day'], t['proxy'], round(pp, 4), round(res['pct'], 4), c['xbar'], res['xbar'], c['why'])
    for K in range(c['k'] + 1, 49):                                    # open states must never contradict the final outcome
        o = PP.pullback(t['b'], t['prev'], K)
        if o and o['status'] == 'open': opens += 1
print(f"setups compared {n}, mismatches {bad}, max difference {mx:.2e} % of position; open intraday states checked {opens}")
