#!/usr/bin/env python3
"""How the live rules (FADE + PULLBACK, rule set in force: tunables champion values) did on news days, 5 years of Massive 5-minute bars (governor question 2026-11-05).
    python3 -I tools/backtest/event_study.py M5.json.gz CALENDAR.json
M5.json.gz = tools/backtest/massive_rest.py output (19 live tickers + SPY, 2021-11-05 on; kept outside the repo). CALENDAR.json = {fomc, cpi, nfp: [dates], election: [[date, kind]]}.
Replays every session with improve.run_cf (paper.simulate, one account from $2,000, 3% risk, no FADE Fridays), then groups the days by event class and compares them
with all other days (permutation test on the mean day return). Part 2 asks what a rule that stands aside on such days would have done.
Massive is a hypothesis feed (handoff: judge rules on Robinhood data). In-sample, many classes: expect false positives. Changes no order, rule or state."""
import contextlib, io, json, os, random, statistics as st, sys
from datetime import date, timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
M5, CAL = sys.argv[1], sys.argv[2]
import gzip
with contextlib.redirect_stdout(io.StringIO()):
    import backtest as BT, lab
    _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
    BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
    lab._DATA = None; D = lab.get_data()
import improve as I
cal = json.load(open(CAL)); vals = I.champion_values(I.tun())
daily, trades = I.run_cf(D, vals)
days = [d for d, _ in daily]; ret = dict(daily); idx = {d: i for i, d in enumerate(D.days)}
tr = {}
for d, usd, pct, sysm, r2 in trades: tr.setdefault(d, []).append((sysm, pct, usd))
print(f"{len(days)} sessions {days[0]}..{days[-1]}, {len(trades)} trades, base: mean {st.mean(ret.values()):+.3f}%/day\n")


def bars(s, d): return D.bars[s][d] if d in D.bars.get(s, {}) else None


def feat(d):
    i = idx[d]; b, p = bars('QQQ', d), bars('QQQ', D.days[i - 1])
    if not b or not p: return None
    gap = (b[0][0] / p[-1][3] - 1) * 100
    def box(day): x = bars('QQQ', day)[:6]; return (max(y[1] for y in x) - min(y[2] for y in x)) / x[0][0] * 100
    prior = [box(x) for x in D.days[max(1, i - 60):i] if bars('QQQ', x) and len(bars('QQQ', x)) >= 6]
    sx, spx = bars('SOXX', d), bars('SOXX', D.days[i - 1])
    sg = (sx[0][0] / spx[-1][3] - 1) * 100 if sx and spx else 0.0
    return dict(gap=gap, boxr=box(d) / st.median(prior) if prior else 1.0, sgap=sg)


F = {d: feat(d) for d in days}; F = {d: v for d, v in F.items() if v}
sess = sorted(days)
def nth(d, n): i = sess.index(d) + n; return sess[i] if 0 <= i < len(sess) else None


S = {}
for ed, kind in cal['election']:
    e = max(x for x in sess if x <= ed) if ed in sess or any(x <= ed for x in sess) else None
    if e in sess:
        for lab, n in (('E', 0), ('R0', 1), ('R1', 2), ('R2', 3)):
            d = nth(e, n)
            if d: S.setdefault(f"election {lab} ({kind})", set()).add(d); S.setdefault(f"election {lab} (all)", set()).add(d)
for k, name in (('fomc', 'FOMC decision day'), ('cpi', 'CPI day'), ('nfp', 'jobs report day')):
    for x in cal[k]:
        if x in sess:
            S.setdefault(name, set()).add(x)
            if k == 'fomc': S.setdefault('day before FOMC', set()).add(nth(x, -1)); S.setdefault('day after FOMC', set()).add(nth(x, 1))
            if k == 'cpi': S.setdefault('day after CPI', set()).add(nth(x, 1))
HIKE = [x for x in cal['fomc'] if '2022-03-16' <= x <= '2023-07-26' and x in sess]     # first and last rate increase of the 2022-23 cycle
S['FOMC decision day (2022-23 hike cycle)'] = set(HIKE); S['day after FOMC (2022-23 hike cycle)'] = {nth(x, 1) for x in HIKE}
S['FOMC or CPI or jobs day'] = S.get('FOMC decision day', set()) | S.get('CPI day', set()) | S.get('jobs report day', set())
for d in sess:
    dt = date.fromisoformat(d); nx = nth(d, 1)
    if dt.weekday() == 4 and 15 <= dt.day <= 21:
        S.setdefault('third Friday (opex)', set()).add(d)
        if dt.month in (3, 6, 9, 12): S.setdefault('quad witching', set()).add(d)
    if nx is None or nx[:7] != d[:7]: S.setdefault('last session of month', set()).add(d)
    if nth(d, -1) is None or nth(d, -1)[:7] != d[:7]: S.setdefault('first session of month', set()).add(d)
    f = F.get(d)
    if f:
        if abs(f['gap']) >= 1.0: S.setdefault('QQQ gap >= 1.0% either way', set()).add(d)
        if abs(f['gap']) >= 0.5: S.setdefault('QQQ gap >= 0.5% either way', set()).add(d)
        if abs(f['sgap']) >= 1.5: S.setdefault('SOXX gap >= 1.5% either way', set()).add(d)
        if f['boxr'] >= 1.5: S.setdefault('QQQ first-30-min range >= 1.5x normal', set()).add(d)
        if f['boxr'] >= 2.0: S.setdefault('QQQ first-30-min range >= 2.0x normal', set()).add(d)
        if f['boxr'] < 0.7: S.setdefault('QQQ first-30-min range < 0.7x normal (quiet)', set()).add(d)
S = {k: {x for x in v if x in ret} for k, v in S.items()}


def tline(ds, name):
    t = [x for d in ds for x in tr.get(d, [])]; fa = [x for x in t if x[0] == 'FADE']; pb = [x for x in t if x[0] != 'FADE']
    def one(l): return f"n={len(l):2d} win {100 * sum(1 for x in l if x[1] > 0) / len(l):3.0f}% avg {st.mean(x[1] for x in l):+.2f}%" if l else "n= 0"
    return f"FADE {one(fa)} | PB {one(pb)}"


def perm(sel, rest, n=10000):
    a = [ret[d] for d in sel]; b = [ret[d] for d in rest]
    if len(a) < 3: return None
    obs = st.mean(a) - st.mean(b); pool = a + b; rnd = random.Random(7); c = 0
    for _ in range(n):
        rnd.shuffle(pool); c += abs(st.mean(pool[:len(a)]) - st.mean(pool[len(a):])) >= abs(obs)
    return c / n


print("PART 1  results on event days against all other days (day return = account %, rules in force)")
print(f"{'class':<44} {'days':>4} {'%/day':>7} {'vs rest':>8} {'p':>6}  {'days up':>7}  trades")
base_all = list(ret)
for name in sorted(S, key=lambda k: (0 if k.startswith('election') else 1, k)):
    ds = sorted(S[name]); rest = [d for d in base_all if d not in S[name]]
    if not ds: continue
    p = perm(ds, rest); m = st.mean(ret[d] for d in ds); up = sum(1 for d in ds if ret[d] > 0)
    print(f"{name:<44} {len(ds):4d} {m:+7.3f} {m - st.mean(ret[d] for d in rest):+8.3f} {('%.3f' % p) if p is not None else '   n/a':>6}  {up:3d}/{len(ds):<3d}  {tline(ds, name)}")

print("\nElection and FOMC days listed (day return %, trades)")
for name in ('election R0 (all)', 'election R1 (all)', 'FOMC decision day'):
    ds = sorted(S.get(name, [])); print(f"  {name}:")
    for d in ds[-14:] if name == 'FOMC decision day' else ds:
        print(f"    {d}  {ret[d]:+6.2f}%  " + ', '.join(f"{x[0]} {x[1]:+.2f}%" for x in tr.get(d, [])) + f"   QQQ gap {F[d]['gap']:+.2f}%  box {F[d]['boxr']:.1f}x" if d in F else f"    {d}")


# ---- Part 2: stand-aside rules
def curve(skip):
    eq = peak = 1.0; dd = 0.0; r = []
    for d in days:
        x = 0.0 if d in skip else ret[d]; r.append(x); eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    h = len(r) // 2
    return (eq - 1) * 100, dd, st.mean(r), st.mean(r[:h]), st.mean(r[h:])


print("\nPART 2  stand-aside rules: the system sits out these days (all else unchanged)")
print(f"{'rule':<52} {'sat out':>7} {'ret%':>8} {'DD%':>5} {'%/day':>7} {'H1':>7} {'H2':>7}  removed trades")
b = curve(set()); print(f"{'(no rule)':<52} {0:7d} {b[0]:8.1f} {b[1]:5.2f} {b[2]:+7.3f} {b[3]:+7.3f} {b[4]:+7.3f}")
rules = {k: S[k] for k in ('election R0 (all)', 'election R1 (all)', 'FOMC decision day', 'CPI day', 'jobs report day', 'FOMC or CPI or jobs day', 'quad witching', 'third Friday (opex)',
                           'QQQ gap >= 1.0% either way', 'QQQ gap >= 0.5% either way', 'SOXX gap >= 1.5% either way', 'QQQ first-30-min range >= 1.5x normal', 'QQQ first-30-min range >= 2.0x normal') if k in S}
for name, skip in rules.items():
    c = curve(skip); rem = [x for d in skip for x in tr.get(d, [])]
    print(f"{name:<52} {len(skip):7d} {c[0]:8.1f} {c[1]:5.2f} {c[2]:+7.3f} {c[3]:+7.3f} {c[4]:+7.3f}  n={len(rem)} avg {st.mean(x[1] for x in rem) if rem else 0:+.2f}%")
for g in (0.5, 0.75, 1.0, 1.5, 2.0):
    skip = {d for d in F if abs(F[d]['gap']) >= g}; c = curve(skip); rem = [x for d in skip for x in tr.get(d, [])]
    print(f"{'QQQ gap >= %.2f%%' % g:<52} {len(skip):7d} {c[0]:8.1f} {c[1]:5.2f} {c[2]:+7.3f} {c[3]:+7.3f} {c[4]:+7.3f}  n={len(rem)} avg {st.mean(x[1] for x in rem) if rem else 0:+.2f}%")
for r in (1.25, 1.5, 2.0, 2.5, 3.0):
    skip = {d for d in F if F[d]['boxr'] >= r}; c = curve(skip); rem = [x for d in skip for x in tr.get(d, [])]
    print(f"{'QQQ first-30-min range >= %.2fx' % r:<52} {len(skip):7d} {c[0]:8.1f} {c[1]:5.2f} {c[2]:+7.3f} {c[3]:+7.3f} {c[4]:+7.3f}  n={len(rem)} avg {st.mean(x[1] for x in rem) if rem else 0:+.2f}%")


# ---- Part 3: by year, and by the market's recent volatility (a regime the system might depend on)
print("\nPART 3  by calendar year (rules in force, Massive bars)")
print(f"{'year':<8} {'days':>5} {'%/day':>7} {'ret%':>8} {'DD%':>6} {'FADE n':>7} {'win':>5} {'avg':>7} {'PB n':>5} {'win':>5} {'avg':>7}")
for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
    ds = [d for d in days if d.startswith(y)]
    if not ds: continue
    eq = peak = 1.0; dd = 0.0
    for d in ds: eq *= 1 + ret[d] / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    t = [x for d in ds for x in tr.get(d, [])]; fa = [x for x in t if x[0] == 'FADE']; pb = [x for x in t if x[0] != 'FADE']
    w = lambda l: 100 * sum(1 for x in l if x[1] > 0) / len(l) if l else 0
    m = lambda l: st.mean(x[1] for x in l) if l else 0
    print(f"{y:<8} {len(ds):5d} {st.mean(ret[d] for d in ds):+7.3f} {(eq - 1) * 100:8.1f} {dd:6.1f} {len(fa):7d} {w(fa):4.0f}% {m(fa):+6.2f}% {len(pb):5d} {w(pb):4.0f}% {m(pb):+6.2f}%")
for name, lo, hi in (('2026 Jan-Feb', '2026-01-01', '2026-02-28'), ('2026-03 to now', '2026-03-01', '2026-12-31'), ('2021-11 to 2026-02', '2021-01-01', '2026-02-28')):
    ds = [d for d in days if lo <= d <= hi]
    if ds: print(f"  {name:<20} {len(ds):4d} days  {st.mean(ret[d] for d in ds):+.3f}%/day")


def box30(d):
    x = bars('QQQ', d)[:6]; return (max(y[1] for y in x) - min(y[2] for y in x)) / x[0][0] * 100


vol = {}
for i, d in enumerate(sess):
    prev = [box30(x) for x in sess[max(0, i - 20):i] if bars('QQQ', x)]
    if len(prev) >= 15: vol[d] = st.median(prev)
vs = sorted(vol.values()); q = [vs[len(vs) * k // 4] for k in (1, 2, 3)]
print(f"\nPART 3b  by the market's recent volatility = median QQQ first-30-min range over the prior 20 sessions (quartile cuts {q[0]:.3f}% {q[1]:.3f}% {q[2]:.3f}%)")
print(f"{'quartile':<22} {'days':>5} {'%/day':>7} {'ret%':>8}  FADE n/win/avg          PB n/win/avg         share of 2026 days")
d26 = [d for d in vol if d.startswith('2026')]
for name, lo, hi in (('Q1 calm', 0, q[0]), ('Q2', q[0], q[1]), ('Q3', q[1], q[2]), ('Q4 wild', q[2], 99)):
    ds = [d for d in vol if lo <= vol[d] < hi]; t = [x for d in ds for x in tr.get(d, [])]; fa = [x for x in t if x[0] == 'FADE']; pb = [x for x in t if x[0] != 'FADE']
    eq = 1.0
    for d in sorted(ds): eq *= 1 + ret[d] / 100
    w = lambda l: 100 * sum(1 for x in l if x[1] > 0) / len(l) if l else 0
    m = lambda l: st.mean(x[1] for x in l) if l else 0
    print(f"{name:<22} {len(ds):5d} {st.mean(ret[d] for d in ds):+7.3f} {(eq - 1) * 100:8.1f}  {len(fa):3d} {w(fa):3.0f}% {m(fa):+6.2f}%   {len(pb):3d} {w(pb):3.0f}% {m(pb):+6.2f}%   {100 * sum(1 for d in d26 if lo <= vol[d] < hi) / max(len(d26), 1):3.0f}%")
last = vol[max(vol)]; print(f"current regime (as of {max(vol)}): {last:.3f}%  -> quartile {1 + sum(1 for c in q if last >= c)}; 2026 median {st.median(vol[d] for d in d26):.3f}%, 2022-2025 median {st.median(vol[d] for d in vol if d < '2026'):.3f}%")
print("\nstand-aside by volatility regime (sit out the calm days):")
for k, c in enumerate(q, 1):
    skip = {d for d in vol if vol[d] < c}; r = curve(skip); rem = [x for d in skip for x in tr.get(d, [])]
    print(f"  sit out when 20-session vol < Q{k} cut ({c:.3f}%): sat out {len(skip):4d}  ret {r[0]:8.1f}%  DD {r[1]:5.1f}%  {r[2]:+.3f}%/day  H1 {r[3]:+.3f} H2 {r[4]:+.3f}  removed trades n={len(rem)} avg {st.mean(x[1] for x in rem) if rem else 0:+.2f}%")
