#!/usr/bin/env python3
"""Confirmation of the PULLBACK exit screen (2026-11-12): (1) paired bootstrap of the per-trade R change for the top simple exits,
(2) the COMBINED live account (FADE v5.2.22 + PULLBACK) with each PULLBACK exit, since a runner held longer blocks later entries.
    python3 -I tools/backtest/pb_exit_confirm.py > tools/backtest/results/pb_exit_confirm_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, pb_exit_screen as PS, adaptive_exit as AE
CANDS = [('LIVE: 100% at the morning high', dict()),
         ('1/3 at high, runner EMA20 close', dict(frac=1 / 3, run=('ema', 20))),
         ('1/3 at high, runner chandelier 3 ATR', dict(frac=1 / 3, run=('chand', 3.0))),
         ('1/3 at high, runner hold to 13:30', dict(frac=1 / 3, run=None)),
         ('1/2 at high, runner EMA20 close', dict(frac=0.5, run=('ema', 20))),
         ('ADAPTIVE 1x vol -> EMA20 runner, else sell next open', dict(adapt=1.0, run=('ema', 20))),
         ('HYBRID 1/3 limit + rest EMA20 if close above on 1.3x vol', dict(hybrid=(1 / 3, 1.3), run=('ema', 20)))]
PB = PS.load(); FA = AE.load()
print('(1) per trade, change in R vs the live exit, PULLBACK setups (all setups, no account): mean, 95% bootstrap interval, chance > 0')
for name, c in CANDS[1:]:
    line = []
    for B in PB:
        d = np.array([PS.manage(t, c)['R_out'] - PS.manage(t, {})['R_out'] for t in B.E]); rng = np.random.default_rng(7)
        bs = np.array([rng.choice(d, len(d)).mean() for _ in range(5000)])
        line.append(f"{B.name[:10]} {d.mean():+.3f}R [{np.percentile(bs, 2.5):+.3f},{np.percentile(bs, 97.5):+.3f}] {100*np.mean(bs > 0):3.0f}%  changed {int((abs(d) > 1e-9).sum()):3d}/{len(d)}")
    print(f"  {name:<58} " + ' | '.join(line))
print('\n(2) COMBINED account, FADE live exits + PULLBACK with each exit: total %, %/day, max drawdown, trades')
fade = [[x for x in (AE.manage(t, None, t['atr']) for t in B.E) if x] for B in FA]
for name, c in CANDS:
    line = []
    for fz, B in zip(fade, PB):
        T = fz + [PS.manage(t, c) for t in B.E]
        a = F.account(B.ds, B.days, T); dl = list(a['daily'].values())
        line.append(f"{B.name[:10]} {a['ret']:+7.1f}% {st.mean(dl):+.3f}%/d DD {a['mdd']:4.1f}% n {len(a['taken'])}")
    print(f"  {name:<58} " + ' | '.join(line))
