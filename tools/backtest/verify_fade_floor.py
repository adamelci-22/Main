#!/usr/bin/env python3
"""v5.2.45 check: paper.py fade() + fade_manage with FLOOR_ON and LOCKCUT_ON (live exits) against the research engine
(entry_fade floor 0.5% + fade_setup_exits.manage) on every Robinhood FADE setup 2026-03-03..10-14.
    python3 -I tools/backtest/verify_fade_floor.py > tools/backtest/results/verify_fade_floor_2026-11-12.txt"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'live'))
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS
import paper as PP
PP.FLOOR_ON = True; PP.LOCKCUT_ON = True; PP.FROZEN_ON = False; PP.apply_tunables('2026-11-12'); PP.X_MINWAIT = 1
B = EF.blocks(F.P(floor_pct=0.5))[0]; n = bad = 0; mx = 0.0
for t in B.E:
    b = B.ds.bars[t['proxy']][t['day']]; c = PP.fade(b, 78)
    if not c or c.get('gross') is None: print('paper has no closed trade for', t['day'], t['proxy']); bad += 1; continue
    r = abs(c['entry'] - c['stop0']); Rp = c['gross'] / r; Rr = FS.manage(t, {})['R_out']; n += 1; mx = max(mx, abs(Rp - Rr))
    if abs(Rp - Rr) > 1e-6 or abs(c['stop0'] - t['ext']) > 1e-9: bad += 1; print('diff', t['day'], t['proxy'], round(Rp, 4), round(Rr, 4), c['stop0'], t['ext'])
print(f"setups compared {n}, mismatches {bad}, max R difference {mx:.2e}")
