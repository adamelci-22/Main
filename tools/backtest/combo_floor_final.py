#!/usr/bin/env python3
"""Combined account on the v5.2.45 system: FADE (stop floor 0.5%) with the live exits or the breakeven lock (+0R at +0.5R),
PULLBACK with the live exit or the runner (1/3 at the morning high, 2/3 runner, breakeven, EMA20 close exit). Paired day bootstrap vs v5.2.45.
    python3 -I tools/backtest/combo_floor_final.py > tools/backtest/results/combo_floor_final_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PB = PS.load(); FB = EF.blocks(F.P(floor_pct=0.5)); RUN = dict(frac=1 / 3, run=('ema', 20)); BE = dict(locklvl=0.0); rng = np.random.default_rng(4)
V = [('v5.2.45 (FADE floor, live exits; PB live)', {}, {}), ('PB runner', {}, RUN), ('FADE breakeven lock', BE, {}), ('FADE breakeven lock + PB runner', BE, RUN)]
base = None; print(__doc__.split('\n')[0])
for name, fp, pp in V:
    cells = []; accs = []
    for b in range(3):
        a = F.account(PB[b].ds, PB[b].days, [FS.manage(t, fp) for t in FB[b].E] + [PS.manage(t, pp) for t in PB[b].E]); accs.append(a)
    if base is None: base = accs
    for b, (a, a0) in enumerate(zip(accs, base)):
        d = np.array([a['daily'][k] - a0['daily'][k] for k in a['daily']]); bs = np.array([rng.choice(d, len(d)).mean() for _ in range(3000)])
        tk = a['taken']; cells.append(f"{PB[b].name[:10]} {a['ret']:+7.1f}% {st.mean(a['daily'].values()):+.3f}%/d DD{a['mdd']:5.1f} win{100*sum(x['acct'] > 0 for x in tk)/len(tk):3.0f}% ({100*np.mean(bs > 0):3.0f}%)")
    print(f"  {name:<44} " + ' | '.join(cells))
