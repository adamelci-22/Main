"""Capacity: at what account size does the position become a meaningful share of the traded volume?"""
import statistics as st
from suggestion_tests import *
D = get_data(); m.rvol = PBF.rvol(D)
days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
f0, p0 = FS.cands(D, days); base = stats(D, days, f0 + p0)
rows = []
for x in base['taken']:
    b = D.bars.get(x['name'], {}).get(x['day'])
    if not b: continue
    k = x['k']; dv = [b[j][3]*b[j][4] for j in (k, k+1, k+2) if j < len(b)]   # entry bar + next two
    day_dv = sum(c[3]*c[4] for c in b)
    rows.append((x['sys'], x['name'], x['risk'], dv[0], sum(dv)/len(dv), day_dv))
print(f"{len(rows)} trades. Position size per $1 of equity = min(3%/stop%, 1x cash) [x2 if margin used]")
by = {}
for s, n, risk, dv0, dv3, ddv in rows:
    by.setdefault(n, []).append((min(3/risk, 1.0), dv0, ddv))
print(f"{'instrument':<8}{'trades':>7}{'med 5-min $vol':>16}{'med day $vol':>16}{'acct size at 5% of bar':>24}{'acct at 1% of day':>20}")
allp = []
for n, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    mv = st.median(a[1] for a in v); md = st.median(a[2] for a in v); pos = st.median(a[0] for a in v)
    p10 = sorted(a[1]/a[0] for a in v)[len(v)//10]
    print(f"{n:<8}{len(v):>7}{mv:>16,.0f}{md:>16,.0f}{0.05*mv/pos:>24,.0f}{0.01*md/pos:>20,.0f}")
    allp += [(0.05*a[1]/a[0], 0.01*a[2]/a[0]) for a in v]
allp.sort()
print("\nAll trades: account size at which the position = 5% of the entry-bar dollar volume:")
for q in (0.1, 0.25, 0.5): print(f"  {int(q*100)}th percentile trade: ${allp[int(q*len(allp))][0]:,.0f}")
