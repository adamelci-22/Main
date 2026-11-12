#!/usr/bin/env python3
"""Combined live account with the two candidates from 2026-11-12: FADE stop floor 0.5% (entry) and the PULLBACK runner exit
(1/3 at the morning high, 2/3 runner, breakeven, EMA20 close exit). Each alone and both together, three blocks.
    python3 -I tools/backtest/combo_candidates.py > tools/backtest/results/combo_candidates_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PB = PS.load(); F0 = EF.blocks(F.P()); F5 = EF.blocks(F.P(floor_pct=0.5)); RUN = dict(frac=1 / 3, run=('ema', 20))
rng = np.random.default_rng(2); print(__doc__.split('\n')[0])
for name, FB, pc in (('LIVE', F0, {}), ('FADE floor 0.5%', F5, {}), ('PULLBACK runner', F0, RUN), ('BOTH', F5, RUN)):
    cells = []
    for b in range(3):
        T = [FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, pc) for t in PB[b].E]
        a = F.account(PB[b].ds, PB[b].days, T); dl = list(a['daily'].values()); tk = a['taken']
        cells.append(f"{PB[b].name[:10]} {a['ret']:+7.1f}% {st.mean(dl):+.3f}%/d DD{a['mdd']:5.1f} win{100*sum(x['acct'] > 0 for x in tk)/len(tk):3.0f}% n{len(tk)}")
    print(f"  {name:<18} " + ' | '.join(cells))
