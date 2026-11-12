#!/usr/bin/env python3
"""Recheck of the v5.2.19 FADE lock (+0.15R at the first +0.5R close) and early cut on all three blocks (it was adopted on the
Robinhood sample only: PF up, total down). Per-setup paired bootstrap and the FADE-alone account.
    python3 -I tools/backtest/fade_lock_recheck.py > tools/backtest/results/fade_lock_recheck_2026-11-12.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, fade_setup_exits as FS
V = [('LIVE: lock +0.15R at +0.5R, cut', dict()),
     ('no lock (cut kept)', dict(lock=False)),
     ('no lock, no cut (v5.2.17 exits)', dict(lock=False, cut=False)),
     ('lock armed at +0.75R, +0.15R', dict(lockarm=0.75)),
     ('lock armed at +1.0R, +0.15R', dict(lockarm=1.0)),
     ('lock armed at +1.0R, breakeven', dict(lockarm=1.0, locklvl=0.0)),
     ('lock armed at +1.5R, +0.5R', dict(lockarm=1.5, locklvl=0.5))]
BL = AE.load(); rng = np.random.default_rng(5)
base = [np.array([FS.manage(t, {})['R_out'] for t in B.E]) for B in BL]
print(__doc__.split('\n')[0])
print(f"{'variant':<36} " + ' | '.join(f"{B.name:<58}" for B in BL))
for name, pk in V:
    cells = []
    for b, B in enumerate(BL):
        rr = np.array([FS.manage(t, pk)['R_out'] for t in B.E]); d = rr - base[b]
        bs = np.array([rng.choice(d, len(d)).mean() for _ in range(4000)])
        a = F.account(B.ds, B.days, [FS.manage(t, pk) for t in B.E]); tk = a['taken']
        red = 100 * sum(x['acct'] <= 0 for x in tk) / len(tk)
        cells.append(f"R {rr.mean():+.3f} ({d.mean():+.3f}, {100*np.mean(bs > 0):3.0f}%) acct {a['ret']:+6.1f}% DD {a['mdd']:4.1f}% losing {red:3.0f}%")
    print(f"{name:<36} " + ' | '.join(f"{c:<58}" for c in cells))
