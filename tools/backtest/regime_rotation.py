#!/usr/bin/env python3
"""Regime rotation between the live mean-reversion book (FADE + PULLBACK) and first-hour momentum (HOUR1 >= 0.5%).
Each system's standalone daily account return is known only after the day; the rotation trades tomorrow the system whose trailing
N-day paper return is higher (ties -> live book). Also a 50/50 capital split. Massive halves and Robinhood 2026.
    python3 -I tools/backtest/regime_rotation.py > tools/backtest/results/regime_rotation_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, fade_setup_exits as FS, pb_exit_screen as PS, other_systems as OS
FA = AE.load(); PB = PS.load()
PX = OS.PX; ds = F.DS(None, PX); ctx = F.context(ds, PX); dm = F.DS(AE.M5, PX); cm = F.context(dm, PX)
H = [(ds, ctx), (dm, cm), (dm, cm)]
def curve(d):
    eq = 1.0; pk = 1.0; mdd = 0.0
    for x in d: eq *= 1 + x / 100; pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100)
    return (eq - 1) * 100, mdd, st.mean(d)
print(__doc__.split('\n')[0])
for b, (B, P) in enumerate(zip(FA, PB)):
    days = B.days
    live = F.account(P.ds, days, [x for x in (FS.manage(t, {}) for t in B.E) if x] + [PS.manage(t, {}) for t in P.E])['daily']
    d_, c_ = H[b]
    hT = [x for p in PX if p in d_.bars for d in days if d in d_.bars[p] for x in [OS.hour1(d_, c_, p, d, d_.bars[p][d], xm=0.5)] if x]
    mom = F.account(d_, days, hT)['daily']
    L = np.array([live.get(d, 0.0) for d in days]); M = np.array([mom.get(d, 0.0) for d in days])
    rows = [('live book (FADE + PULLBACK)', L), ('HOUR1 momentum alone', M), ('50/50 split', (L + M) / 2)]
    for N in (10, 20, 40, 60):
        pick = np.array([L[i] if i < N or L[i - N:i].sum() >= M[i - N:i].sum() else M[i] for i in range(len(days))])
        share = 100 * np.mean([not (i < N or L[i - N:i].sum() >= M[i - N:i].sum()) for i in range(len(days))])
        rows.append((f'rotation, trailing {N} days (momentum {share:.0f}% of days)', pick))
    print(f"\n{B.name} ({len(days)} days)")
    for name, d in rows:
        tot, dd, avg = curve(d); print(f"  {name:<52} total {tot:+8.1f}%  {avg:+.3f}%/day  max DD {dd:5.1f}%")
