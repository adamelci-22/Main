#!/usr/bin/env python3
"""Late-entry band study (A1.6) with the D3 split: whole window, H1, H2 and the untouched MARCH window.
    python3 tools/backtest/band_study.py > tools/backtest/results/band_study.txt
FADE signal arrives ONE bar late (5-6 min), or in the 55/35/10 on-time / 1-bar / 2+-bar mix (2+ skipped), band = max leg move vs the model price."""
import io, contextlib, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import late_entry_tests as L, final_system as FS, mixed as MXD, manual as m, pb_final as PBF
    from late_rule_test import draw
    from lab import get_data
D = get_data(); m.rvol = PBF.rvol(D)
days = [x for x in D.days[1:] if '2026-03-03' <= x <= '2026-10-14']
MAR = [d for d in days if d < '2026-04-07']; TUNE = [d for d in days if d >= '2026-04-07']; h = len(TUNE) // 2; H1, H2 = TUNE[:h], TUNE[h:]
f0, p0 = FS.cands(D, days)
def run(fc):
    a = MXD.account(D, days, fc + p0); dl = a['daily']; v = lambda ds: st.mean(dl[d] for d in ds)
    return dict(all=v(days), h1=v(H1), h2=v(H2), mar=v(MAR), ret=a['ret'], dd=a['mdd'], n=len(a['taken']), fade=sum(t['sys'] == 'FADE' for t in a['taken']))
def show(tag, r, ref):
    print(f"  {tag:<40} {r['all']:+.3f}%/day (H1 {r['h1']:+.3f} H2 {r['h2']:+.3f} Mar {r['mar']:+.3f}) ret {r['ret']:+6.1f}% DD {r['dd']:3.1f}% trades {r['n']:3d} (FADE {r['fade']:2d})   vs on-time {r['all']-ref['all']:+.3f}")
ON = run(L.fade_cands(D, days, 0, None))
print(f"BAND STUDY {days[0]}..{days[-1]} ({len(days)} d) | H1 {H1[0]}..{H1[-1]} | H2 {H2[0]}..{H2[-1]} | MARCH {MAR[0]}..{MAR[-1]}\n")
show('on time (live backtest)', ON, ON)
print("\n-- every FADE signal one bar (5-6 min) late --")
for band in (0.5, 1.0, 1.5, 2.0, 3.0, None):
    show(f"band {band}%" if band else 'no band (always enter)', run(L.fade_cands(D, days, 1, None, band=band)), ON)
print("\n-- mix 55% on time / 35% one bar late / 10% 2+ bars late (skipped) --")
def mix(band):
    def delays(p, d):
        k = draw(p, d, (0.55, 0.35, 0.10)); return None if k >= 2 else k
    return L.fade_cands(D, days, 0, None, band=band, delays=delays)
for band in (0.5, 1.0, 1.5, 2.0, None):
    show(f"band {band}%" if band else 'no band', run(mix(band)), ON)
