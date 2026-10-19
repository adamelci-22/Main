"""Realistic-mix test of the proposed rule (1.0% leg band, up to one bar late, skip beyond) vs the current rule (0.5% band) at several lateness mixes."""
import io, contextlib, statistics as st
with contextlib.redirect_stdout(io.StringIO()):
    import late_rule_test as R
L = R.L; MXD = R.MXD; FS = R.FS
from lab import get_data
import manual as m, pb_final as PBF
D = get_data(); m.rvol = PBF.rvol(D)
days = [x for x in D.days[1:] if '2026-03-03' <= x <= '2026-10-14']
f0, p0 = FS.cands(D, days)
def run(fc):
    a = MXD.account(D, days, fc + p0); dl = list(a['daily'].values())
    return len(a['taken']), st.mean(dl), a['ret'], a['mdd'], 100 * sum(t['usd'] > 0 for t in a['taken']) / len(a['taken'])
def mix(shares, band):
    def delays(p, d):
        k = R.draw(p, d, shares)
        return None if k >= 2 else k
    return L.fade_cands(D, days, 0, None, band=band, delays=delays)
print(f"{'mix (on time / 1 bar late / 2+ bars late)':<46}{'rule':<22}{'trd':>5}{'win':>6}{'%/day':>9}{'return':>9}{'DD':>6}")
for shares, name in (((1.0, 0.0, 0.0), 'all on time'), ((0.93, 0.07, 0.0), "today's real mix 93 / 7 / 0"), ((0.80, 0.17, 0.03), 'in-between 80 / 17 / 3'), ((0.55, 0.35, 0.10), 'stress mix 55 / 35 / 10')):
    for band, rule in ((0.5, 'current (0.5% band)'), (1.0, 'proposed (1.0% band)')):
        n, d, ret, dd, w = run(mix(shares, band))
        print(f"{name:<46}{rule:<22}{n:>5}{w:>5.0f}%{d:>+8.3f}%{ret:>+8.1f}%{dd:>5.1f}%")
