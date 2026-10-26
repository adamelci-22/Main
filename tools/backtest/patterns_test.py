#!/usr/bin/env python3
"""Do calendar and market-state patterns exist in FADE results, and do they REPEAT?  /usr/bin/python3 -I tools/backtest/patterns_test.py M5.json.gz > results/patterns_test.txt
Features known before the trade: weekday, turn of month, options-expiration week, month of year, holiday adjacency, Fed decision day, prior-day and 5-day QQQ move, volatility trend,
opening gap, opening volume. For each category: average R per setup (day-clustered t). Discovery = first half (to 2024-03), confirmation = second half.
Setups = live FADE setups on the six proxies for two box lengths (30-min live, 10-min box with the same break deadline)."""
import collections, datetime as dt, math, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
SRC = sys.argv[1]; LIVE = F.LIVE; SPLIT = '2024-04-01'
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); days = ds.days[21:]; alld = ds.days
FOMC = ['2021-12-15', '2022-01-26', '2022-03-16', '2022-05-04', '2022-06-15', '2022-07-27', '2022-09-21', '2022-11-02', '2022-12-14', '2023-02-01', '2023-03-22', '2023-05-03', '2023-06-14', '2023-07-26',
        '2023-09-20', '2023-11-01', '2023-12-13', '2024-01-31', '2024-03-20', '2024-05-01', '2024-06-12', '2024-07-31', '2024-09-18', '2024-11-07', '2024-12-18', '2025-01-29', '2025-03-19', '2025-05-07',
        '2025-06-18', '2025-07-30', '2025-09-17', '2025-10-29', '2025-12-10', '2026-01-28', '2026-03-18', '2026-04-29', '2026-06-17', '2026-07-29', '2026-09-16']
fomc = set(FOMC); idx = {d: i for i, d in enumerate(alld)}
wd = lambda d: dt.date.fromisoformat(d).weekday()


def third_friday(y, m):
    d = dt.date(y, m, 1); fr = [d + dt.timedelta(i) for i in range(31) if (d + dt.timedelta(i)).month == m and (d + dt.timedelta(i)).weekday() == 4]; return fr[2]


opex = {}
for d in alld:
    y, m = int(d[:4]), int(d[5:7])
    if (y, m) not in opex:
        t3 = third_friday(y, m); cand = [x for x in alld if x <= t3.isoformat() and x[:7] == d[:7]]; opex[(y, m)] = cand[-1] if cand else None
mdays = collections.defaultdict(list)
for d in alld: mdays[d[:7]].append(d)
qqq = {d: ds.bars['QQQ'][d][-1][3] for d in alld if d in ds.bars['QQQ']}
open6 = {p: {d: sum(x[4] for x in ds.bars[p][d][:6]) for d in ds.bars[p]} for p in LIVE}


def cats(t):
    d = t['day']; i = idx[d]; out = {}; p = t['proxy']
    out['weekday'] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][wd(d)]
    ml = mdays[d[:7]]; k = ml.index(d); out['turn of month'] = 'turn (last 2 / first 3 days)' if (k < 3 or k >= len(ml) - 2) else 'mid-month'
    ox = opex[(int(d[:4]), int(d[5:7]))]
    out['options expiration'] = 'OpEx day' if d == ox else ('OpEx week (Mon-Thu)' if ox and dt.date.fromisoformat(ox) - dt.date.fromisoformat(d) < dt.timedelta(days=5) and d < ox and d[:7] == ox[:7] else 'other')
    out['month'] = d[5:7]
    prev = alld[i - 1]; nxt = alld[i + 1] if i + 1 < len(alld) else None
    gap_prev = (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev)).days; gap_next = (dt.date.fromisoformat(nxt) - dt.date.fromisoformat(d)).days if nxt else 1
    post = gap_prev > (3 if wd(d) == 0 else 1); pre = gap_next > (3 if wd(d) == 4 else 1)
    out['holiday adjacency'] = 'day after a holiday' if post else ('day before a holiday' if pre else 'normal')
    out['Fed decision'] = 'decision day' if d in fomc else ('day before' if nxt in fomc else 'other')
    r1 = qqq[prev] / qqq[alld[i - 2]] - 1; out['QQQ prior day'] = 'down >0.5%' if r1 < -0.005 else ('up >0.5%' if r1 > 0.005 else 'flat')
    r5 = qqq[prev] / qqq[alld[i - 6]] - 1; out['QQQ prior 5 days'] = 'down >2%' if r5 < -0.02 else ('up >2%' if r5 > 0.02 else 'flat')
    rr = [qqq[alld[j]] / qqq[alld[j - 1]] - 1 for j in range(i - 60, i)]; out['volatility trend'] = 'rising (5d > 60d vol)' if st.pstdev(rr[-5:]) > st.pstdev(rr) else 'falling'
    g = ctx['gap'][p].get(d)
    out['gap vs fade direction'] = 'none' if g is None else ('fading against the gap' if g * t['side'] < 0 else 'fading with the gap')
    out['gap size'] = 'none' if g is None else ('big (>0.7%)' if abs(g) > 0.007 else ('small (<0.25%)' if abs(g) < 0.0025 else 'medium'))
    pri = [open6[p][alld[j]] for j in range(i - 20, i) if alld[j] in open6[p]]; v = open6[p][d] / st.mean(pri) if pri else 1
    out['opening volume'] = 'heavy (>1.3x)' if v > 1.3 else ('light (<0.8x)' if v < 0.8 else 'normal')
    return out


def clus(T):
    g = collections.defaultdict(list)
    for t in T: g[t['day']].append(t['R_out'])
    n = sum(len(v) for v in g.values()); m = sum(sum(v) for v in g.values()) / n
    se = math.sqrt(sum(sum(r - m for r in v) ** 2 for v in g.values())) / n if n else 0
    return m, (m / se if se else 0.0), n


print(f"Massive bars {days[0]}..{days[-1]}; discovery half to 2024-03-31, confirmation half from 2024-04-01.  'rep' = replicated: same sign and |t| >= 1 in the confirmation half\n")
box_runs = {'30-min box (LIVE)': F.trades(ds, days, LIVE, F.P(), ctx), '10-min box': F.trades(ds, days, LIVE, F.P(box=2, brk_end=9), ctx)}
rnd = random.Random(1)
for bname, T in box_runs.items():
    for t in T: t['c'] = cats(t)
    print("=" * 14, bname, f"({len(T)} setups, avg R {st.mean(t['R_out'] for t in T):+.3f}) ", "=" * 14)
    feats = list(T[0]['c'].keys()); rows = []
    for f in feats:
        for cv in sorted({t['c'][f] for t in T}):
            if cv == 'none': continue
            sub = [t for t in T if t['c'][f] == cv]; a = [t for t in sub if t['day'] < SPLIT]; b = [t for t in sub if t['day'] >= SPLIT]
            if len(a) < 25 or len(b) < 25: continue
            m1, t1, n1 = clus(a); m2, t2, n2 = clus(b); m, tt, n = clus(sub); rows.append((f, cv, n, m, tt, m1, t1, n1, m2, t2, n2))
    print(f"  {'feature':<24}{'category':<28}{'n':>5}{'avg R':>8}{'t':>6} | {'half1 R':>8}{'t':>6} | {'half2 R':>8}{'t':>6}  rep")
    last = None
    for r in rows:
        rep = ''
        if abs(r[6]) >= 2: rep = 'REP' if (math.copysign(1, r[5]) == math.copysign(1, r[8]) and abs(r[9]) >= 1) else 'FAIL'
        print(f"  {r[0] if r[0] != last else '':<24}{r[1]:<28}{r[2]:>5}{r[3]:>+8.2f}{r[4]:>+6.1f} | {r[5]:>+8.2f}{r[6]:>+6.1f} | {r[8]:>+8.2f}{r[9]:>+6.1f}  {rep}"); last = r[0]
    n_all = len(rows); sig_all = [r for r in rows if abs(r[4]) >= 2]; disc = [r for r in rows if abs(r[6]) >= 2]
    rep = [r for r in disc if math.copysign(1, r[5]) == math.copysign(1, r[8]) and abs(r[9]) >= 1]
    print(f"\n  categories tested {n_all}; whole-sample |t|>=2: {len(sig_all)} (chance alone gives about {0.05*n_all:.0f}); discovery-half |t|>=2: {len(disc)}; of those replicated in the confirmation half: {len(rep)} ({100*len(rep)/max(1,len(disc)):.0f}%; pure chance would give about 16%)")
    # cross-half agreement of category profiles
    print("  agreement of category means between halves (Spearman, only features with >=4 categories):")
    for f in feats:
        rr = [r for r in rows if r[0] == f]
        if len(rr) >= 4:
            def rk(v): o = sorted(range(len(v)), key=lambda i: v[i]); x = [0] * len(v); [x.__setitem__(i, p) for p, i in enumerate(o)]; return x
            a_, b_ = rk([r[5] for r in rr]), rk([r[8] for r in rr]); ma, mb = st.mean(a_), st.mean(b_)
            den = math.sqrt(sum((x - ma) ** 2 for x in a_) * sum((y - mb) ** 2 for y in b_)); print(f"    {f:<24} {sum((x-ma)*(y-mb) for x,y in zip(a_,b_))/den:+.2f}  ({len(rr)} categories)")
    print("  WALK-FORWARD 'skip the worst category' rule: per feature pick the category with the lowest discovery-half avg R (n >= 60), skip it in the confirmation half; account %/day in the confirmation half:")
    half2 = [d for d in days if d >= SPLIT]; base_a = F.account(ds, half2, [t for t in T if t['day'] >= SPLIT]); bm = st.mean(base_a['daily'].values())
    print(f"    no skipping: {bm:+.3f}%/day, {len(base_a['taken'])} trades")
    gains = []
    for f in feats:
        rr = [r for r in rows if r[0] == f and r[7] >= 60]
        if not rr: continue
        worst = min(rr, key=lambda r: r[5]); keep = [t for t in T if t['day'] >= SPLIT and t['c'][f] != worst[1]]; a = F.account(ds, half2, keep); mm = st.mean(a['daily'].values()); gains.append(mm - bm)
        print(f"    skip {f}={worst[1]:<26} (half-1 R {worst[5]:+.2f}, half-2 R {worst[8]:+.2f}): {mm:+.3f}%/day  ({mm-bm:+.3f})")
    print(f"    average change from such a rule: {st.mean(gains):+.3f}%/day; improved in {sum(1 for g in gains if g>0)} of {len(gains)}\n")
