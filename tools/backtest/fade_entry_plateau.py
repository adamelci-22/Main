#!/usr/bin/env python3
"""Plateau check around the live FADE entry settings (full system FADE + PULLBACK, one account): break deadline x retest window x tolerance.
    python3 tools/backtest/fade_entry_plateau.py > tools/backtest/results/fade_entry_plateau.txt
Live: break closes by the 10:10 bar (brk_end 9), retest within 12 bars, touch within 0.10%.
"""
import itertools, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, retest as RT, fade_combo as FC, final_system as FS
from lab import get_data

D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2; mar = [d for d in days if d < '2026-04-07']
_, p = FS.cands(D, days)
def run(brk, wait, tol):
    FC.FADE = RT.RC(fade=True, brk_end=brk, max_wait=wait, tol=tol)
    f, _ = FS.cands(D, days)
    a = MXD.account(D, days, f + p); dl = a['daily']; fa = MXD.account(D, days, f)
    v = lambda ds: st.mean(dl[d] for d in ds)
    return v(days), v(days[:h]), v(days[h:]), v(mar), st.mean(fa['daily'].values()), len(f), a['mdd']
print("FADE entry plateau (combined FADE+PB %/day; live = break by 10:10, retest 12 bars, tol 0.10%)\n")
print(f"{'break by':<9}{'wait':>5}{'tol':>6} | {'all':>7}{'H1':>7}{'H2':>7}{'March':>7} | {'FADE alone':>10}{'setups':>7}{'DD':>6}")
TN = {8: '10:05', 9: '10:10', 10: '10:15', 12: '10:25'}
rows = []
for brk, wait, tol in itertools.product((8, 9, 10, 12), (6, 9, 12, 18), (0.05, 0.10, 0.20)):
    r = run(brk, wait, tol); rows.append(((brk, wait, tol), r))
    live = '  <- LIVE' if (brk, wait, tol) == (9, 12, 0.10) else ''
    print(f"{TN[brk]:<9}{wait:>5}{tol:>6.2f} | {r[0]:+7.3f}{r[1]:+7.3f}{r[2]:+7.3f}{r[3]:+7.3f} | {r[4]:+10.3f}{r[5]:7d}{r[6]:6.1f}{live}")
FC.FADE = RT.RC(fade=True)
better = [k for k, r in rows if all(r[i] > rr for i, rr in zip(range(4), dict(rows)[(9, 12, 0.10)][:4]))]
print(f"\nsettings beating LIVE in all four windows (all, H1, H2, March): {better}")
