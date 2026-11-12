#!/usr/bin/env python3
"""FADE stop-floor grid under the live exits (lock, cut, 1/3 at 2R, chandelier): stop = max(post-break extreme, floor % of the proxy).
Account: FADE alone, then combined with PULLBACK (live exit). Paired day bootstrap of the account daily return difference.
    python3 -I tools/backtest/entry_fade_floor.py > tools/backtest/results/entry_fade_floor_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PB = PS.load(); rng = np.random.default_rng(11)
base = None
print(__doc__.split('\n')[0])
for fl in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
    BL = EF.blocks(F.P(floor_pct=fl)); cells = []
    for b, B in enumerate(BL):
        T = [FS.manage(t, {}) for t in B.E]
        a = F.account(B.ds, B.days, T); tk = a['taken']
        c = F.account(PB[b].ds, PB[b].days, T + [PS.manage(t, {}) for t in PB[b].E])
        win = 100 * sum(x['acct'] > 0 for x in tk) / len(tk)
        cells.append((a, c, win, len(tk)))
    if base is None: base = cells
    out = []
    for (a, c, win, n), (a0, c0, *_ ) in zip(cells, base):
        d = np.array([c['daily'][k] - c0['daily'][k] for k in c['daily']]); bs = np.array([rng.choice(d, len(d)).mean() for _ in range(3000)])
        out.append(f"FADE {a['ret']:+7.1f}% DD{a['mdd']:5.1f} win{win:3.0f}% n{n:4d} | COMB {c['ret']:+7.1f}% DD{c['mdd']:5.1f} ({100*np.mean(bs > 0):3.0f}%)")
    print(f"floor {fl:.1f}%  " + ' || '.join(f"{nm}: {o}" for (nm, *_), o in zip(EF.DATA, out)))
