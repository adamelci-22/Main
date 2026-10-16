"""Capacity for FADE entries: leg dollar volume in the entry bar vs position size (min(3%/leg stop, 1x cash))."""
import statistics as st
from suggestion_tests import *
LEG = {'QQQ': ('TQQQ', 'SQQQ'), 'SOXX': ('SOXL', 'SOXS'), 'IWM': ('TNA', 'TZA'), 'XLK': ('TECL', 'TECS'), 'XBI': ('LABU', 'LABD'), 'AMD': ('AMDL', 'AMDD')}
D = get_data(); m.rvol = PBF.rvol(D)
days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
f0, p0 = FS.cands(D, days); base = stats(D, days, f0 + p0)
by = {}
for x in base['taken']:
    if x['sys'] != 'FADE': continue
    leg = LEG[x['proxy']][0 if x['name'].endswith('+') else 1]
    b = D.bars.get(leg, {}).get(x['day'])
    if not b or x['k'] >= len(b): continue
    dv = b[x['k']][3] * b[x['k']][4]; day_dv = sum(c[3] * c[4] for c in b)
    by.setdefault(leg, []).append((min(3 / x['risk'], 1.0), dv, day_dv))
print(f"FADE entries with leg bars: {sum(len(v) for v in by.values())} of {sum(1 for x in base['taken'] if x['sys']=='FADE')}")
print(f"{'leg':<7}{'trades':>7}{'med 5-min $vol':>16}{'acct at 5% of bar':>20}{'acct at 1% of day':>20}")
allp = []
for n, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    mv = st.median(a[1] for a in v); md = st.median(a[2] for a in v); pos = st.median(a[0] for a in v)
    print(f"{n:<7}{len(v):>7}{mv:>16,.0f}{0.05*mv/pos:>20,.0f}{0.01*md/pos:>20,.0f}")
    allp += [0.05 * a[1] / a[0] for a in v]
allp.sort()
print("\nAll FADE trades, account size where position = 5% of entry-bar dollar volume:")
for q in (0.1, 0.25, 0.5): print(f"  {int(q*100)}th percentile: ${allp[int(q*len(allp))]:,.0f}")
