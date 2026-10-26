#!/usr/bin/env python3
"""10-minute box, three honest checks on the 5 years we own.  /usr/bin/python3 -I tools/backtest/box10_risk.py M5.json.gz > results/box10_risk.txt
1. day-clustered significance (the six proxies share each day, so setups are not independent); 2. break-even extra cost; 3. Monte Carlo drawdown at 1% / 0.5% risk."""
import collections, math, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
SRC = sys.argv[1]; CUT = '2026-03-01'; LIVE = F.LIVE; rnd = random.Random(4)
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); days = ds.days[21:]
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]


def clustered(T, key):
    g = collections.defaultdict(list)
    for t in T: g[key(t)].append(t['R_out'])
    cm = [st.mean(v) for v in g.values()]; w = [len(v) for v in g.values()]
    m = sum(c * x for c, x in zip(w, cm)) / sum(w)
    # cluster-robust SE of the mean of R: sum of (cluster sum of residuals)^2
    n = sum(w); se = math.sqrt(sum((sum(r - m for r in v)) ** 2 for v in g.values())) / n
    return m, se, m / se, len(g)


print("1. SIGNIFICANCE BEFORE 2026-03, setup-level vs clustered by day vs clustered by month (avg R per setup)")
print(f"   {'box':<14}{'avg R':>8}{'z (setups)':>12}{'z (by day)':>12}{'z (by month)':>14}{'days':>7}")
for n, nm in ((1, '5 min'), (2, '10 min'), (3, '15 min'), (6, '30 min (live)')):
    T = [t for t in F.trades(ds, days, LIVE, F.P(box=n, brk_end=n + 3), ctx) if t['day'] < CUT]
    v = [t['R_out'] for t in T]; z0 = st.mean(v) / (st.pstdev(v) / math.sqrt(len(v)))
    m, se, zd, nd = clustered(T, lambda t: t['day']); _, _, zm, nm_ = clustered(T, lambda t: t['day'][:7])
    print(f"   {nm:<14}{m:>+8.3f}{z0:>+12.2f}{zd:>+12.2f}{zm:>+14.2f}{nd:>7}")

print("\n2. BREAK-EVEN COST: extra round-trip cost on the leg (model charges 0.06%) at which the account %/day reaches zero (before 2026-03, 10-minute box)")
res = []
for extra in (0.0, 0.025, 0.05, 0.075, 0.10, 0.15):
    F.LEGCOST = 0.06 + extra; T = [t for t in F.trades(ds, days, LIVE, F.P(box=2, brk_end=5), ctx) if t['day'] < CUT]
    a = F.account(ds, pre, T); res.append((extra, st.mean(a['daily'].values()))); print(f"   extra {extra:.3f}%: {res[-1][1]:+.3f}%/day, return {a['ret']:+.1f}%")
F.LEGCOST = 0.06
for (e0, v0), (e1, v1) in zip(res, res[1:]):
    if v0 > 0 >= v1: print(f"   crosses zero at about {e0 + (e1-e0)*v0/(v0-v1):.3f}% extra round-trip cost (the whole edge before 2026 is smaller than a typical half-spread on thin funds)")

print("\n3. MONTE CARLO on the 10-minute box trades actually taken (resample trades with replacement, 250 trades = about one year, 3000 runs)")
T = F.trades(ds, days, LIVE, F.P(box=2, brk_end=5), ctx)
for risk in (0.03, 0.01, 0.005):
    a = F.account(ds, pre, [t for t in T if t['day'] < CUT], risk=risk); pool = [x['acct'] for x in a['taken']]
    rets = []; dds = []
    for _ in range(3000):
        eq = 1.0; pk = 1.0; mdd = 0.0
        for _ in range(250):
            eq *= 1 + rnd.choice(pool) / 100; pk = max(pk, eq); mdd = max(mdd, 1 - eq / pk)
        rets.append(eq - 1); dds.append(mdd)
    rets.sort(); dds.sort()
    print(f"   risk {risk*100:.1f}%: median year {100*rets[1500]:+.0f}%, 5th pct {100*rets[150]:+.0f}%, 95th {100*rets[2850]:+.0f}%; P(losing year) {100*sum(r<0 for r in rets)/3000:.0f}%; median max drawdown {100*dds[1500]:.0f}%, 95th pct {100*dds[2850]:.0f}%, P(drawdown >15%) {100*sum(d>0.15 for d in dds)/3000:.0f}%")
print("   (resampling pre-2026 trades only, so it describes the no-edge-regime world; trade order shuffles do not test the edge, only the drawdown)")
