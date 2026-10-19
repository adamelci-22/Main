"""Composite 'most plausible live' estimate on the current system (v5.2.6): late-entry rule at today's lateness mix + extra execution cost + whole-share rounding at $2,500."""
import io, contextlib, math, statistics as st, collections
with contextlib.redirect_stdout(io.StringIO()):
    import late_rule_test as R
    import scale_500k as S
    import whole_share_drag as W
L = R.L; D = S.D; days = S.days; p0 = S.p0
import twobar as TB
def acct(cs, start, whole, extra):
    by = collections.defaultdict(list)
    for c in cs: by[c['day']].append(c)
    eq = start; dl = []; pk = start; mdd = 0
    for d in days:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: c['k']); free = 0; n = 0
        while day and n < 3:
            av = [c for c in day if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq, eq * 0.03 / (c['risk'] / 100)); px = W.price(c)
            if whole and px:
                sh = math.floor(notional / px)
                if sh < 1: day.remove(c); continue
                notional = sh * px
            eq += notional * (c['pct'] - extra) / 100; free = c['xbar'] + 1; day.remove(c); n += 1
        pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100); dl.append((eq / e0 - 1) * 100)
    return st.mean(dl), (eq / start - 1) * 100, mdd
print(f"{'scenario ($2,500 start, 157 days)':<70}{'%/day':>8}{'return':>9}{'DD':>6}")
for shares, mixname in (((1.0, 0, 0), 'all on time'), ((0.93, 0.07, 0.0), "today's lateness mix")):
    vals = collections.defaultdict(list)
    for salt in range(10):
        def delays(p, d, salt=salt):
            k = R.draw(p, d, shares, salt); return None if k >= 2 else k
        fc = L.fade_cands(D, days, 0, None, band=1.0, delays=delays)
        for extra in (0.0, 0.10, 0.20):
            for whole in (False, True):
                vals[(extra, whole)].append(acct(fc + p0, 2500.0, whole, extra))
    for (extra, whole), v in sorted(vals.items()):
        print(f"{mixname + ', +%.2f%% extra cost' % extra + (', whole shares' if whole else ', continuous $'):<70}{st.mean(x[0] for x in v):>+8.3f}{st.mean(x[1] for x in v):>+8.0f}%{st.mean(x[2] for x in v):>6.1f}")
