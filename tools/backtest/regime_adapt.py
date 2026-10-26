#!/usr/bin/env python3
"""What fails as we go back in time, and does an adaptive / machine-learning layer help?  FADE (live six proxies), Massive full-tape 5-minute bars.
    /usr/bin/python3 -I tools/backtest/regime_adapt.py M5.json.gz > tools/backtest/results/regime_adapt.txt
A. Decay: per-year anatomy of the live FADE rule; which regime variables explain good and bad months (Spearman, same month and next month).
B. Adaptive layers, all walk-forward (each decision uses only data before it): (1) trailing-performance on/off switch, (2) monthly re-choice of
   parameters from a small grid on the trailing 12 months, (3) logistic regression and gradient boosting on pre-entry features as a trade filter.
   Each is compared with the fixed live rule and with random skipping of the same share of trades (the noise floor)."""
import collections, math, os, random, statistics as st, sys
from dataclasses import replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import fade_diag as F

SRC = sys.argv[1]; LIVE = F.LIVE
ds = F.DS(SRC, F.ALL); syms = [s for s in F.ALL if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[21:]; base = F.P()
print(f"Massive 5-minute bars {ds.days[0]}..{ds.days[-1]}, {len(days)} tradable days; symbols {' '.join(syms)}\n")


def acct(T, ds_days=None):
    a = F.account(ds, ds_days or days, T); dl = a['daily']
    return a, st.mean(dl.values()) if dl else 0.0


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v)
    for pos, i in enumerate(o): r[i] = pos
    return r


def spearman(a, b):
    if len(a) < 5: return float('nan')
    ra, rb = rank(a), rank(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float('nan')


# ---------------------------------------------------------------- daily/market features (all known before the open of the trade day)
dly = {p: {} for p in syms}
for p in syms:
    for d in ds.days:
        b = ds.bars[p].get(d)
        if b: dly[p][d] = dict(o=b[0][0], h=max(x[1] for x in b), l=min(x[2] for x in b), c=b[-1][3], v=sum(x[4] for x in b), v6=sum(x[4] for x in b[:6]))
idx = {d: i for i, d in enumerate(ds.days)}


def prior(p, d, n):
    i = idx[d]; return [dly[p][x] for x in ds.days[max(0, i - n):i] if x in dly[p]]


def mkt(d):
    q = prior('QQQ', d, 21); v = prior('VIXY', d, 6)
    if len(q) < 21: return None
    r = [q[i]['c'] / q[i - 1]['c'] - 1 for i in range(1, len(q))]
    return dict(rv=st.pstdev(r) * 100, trend=q[-1]['c'] / q[0]['c'] - 1, rng=st.mean((x['h'] - x['l']) / x['c'] for x in q) * 100, ret1=r[-1] * 100,
                vix=v[-1]['c'] if v else 0, vix5=(v[-1]['c'] / v[0]['c'] - 1) if v else 0)


def feats(t):
    p, d = t['proxy'], t['day']; s = t['side']; m = mkt(d); pr = prior(p, d, 20)
    if m is None or len(pr) < 20: return None
    g = ctx['gap'][p].get(d); tr = ctx['trend'][p].get(d)
    if g is None or tr is None: return None
    adr = st.mean((x['h'] - x['l']) / x['c'] for x in pr) * 100; v6 = st.mean(x['v6'] for x in pr)
    f = dict(gap_dir=g * s * 100, trend_dir=tr * s * 100, box=t['box_pct'], risk=t['risk_pct'], depth=t['depth'], wait=t['wait'], k=t['k'], brk=t['brk'], side=s,
             risk_adr=t['risk_pct'] / adr if adr else 0, box_adr=t['box_pct'] / adr if adr else 0, vol_r=dly[p][d]['v6'] / v6 if v6 else 1, absgap=abs(g) * 100,
             mrv=m['rv'], mtrend=m['trend'] * 100, mrng=m['rng'], mret1=m['ret1'] * s, vix=m['vix'], vix5=m['vix5'] * 100, wd=__import__('datetime').date.fromisoformat(d).weekday(), adr=adr)
    return f


T0 = F.trades(ds, days, LIVE, base, ctx)
T = []
for t in T0:
    f = feats(t)
    if f: t = dict(t, f=f); T.append(t)
T.sort(key=lambda t: t['day'])
print(f"live FADE setups on the six proxies: {len(T0)}, with full features {len(T)}")
years = sorted({t['day'][:4] for t in T})


def stat_line(v):
    r = [x['R_out'] for x in v]
    if not v: return 'n 0'
    return (f"n {len(v):4d} win {100*sum(x['pct']>0 for x in v)/len(v):3.0f}% avgR {st.mean(r):+.3f} reach1R {100*sum(x['mfe']>=1 for x in v)/len(v):3.0f}% "
            f"reach2R {100*sum(x['mfe']>=2 for x in v)/len(v):3.0f}% stopped<=2bars {100*sum(x['why']=='stop' and x['xbar']-x['k']<=1 for x in v)/len(v):3.0f}% avgMAE {st.mean(x['mae'] for x in v):.2f}R")


print("\n=================== A. WHAT CHANGES YEAR BY YEAR (live FADE, six proxies, per setup) ===================")
for y in years: print(f"  {y}  {stat_line([t for t in T if t['day'].startswith(y)])}")
print("\n  by exit reason and year (share of setups, avg R)")
for y in years:
    v = [t for t in T if t['day'].startswith(y)]; c = collections.Counter(t['why'] for t in v)
    print(f"  {y}  " + '  '.join(f"{k} {100*c[k]/len(v):3.0f}% ({st.mean(t['R_out'] for t in v if t['why']==k):+.2f}R)" for k in ('stop', 'be', 'trail', 'time') if c[k]))
for name, fn in (('fade side: up-break (bear leg)', lambda t: t['side'] < 0), ('fade side: down-break (bull leg)', lambda t: t['side'] > 0),
                 ('fade against the gap', lambda t: t['f']['gap_dir'] < 0), ('fade in gap direction', lambda t: t['f']['gap_dir'] >= 0),
                 ('entry at 10:10', lambda t: t['k'] == 8), ('entry 10:15+', lambda t: t['k'] > 8),
                 ('stop dist < 0.2%', lambda t: t['risk_pct'] < 0.2), ('stop dist >= 0.35%', lambda t: t['risk_pct'] >= 0.35)):
    print(f"\n  {name}: avg R by year: " + '  '.join(f"{y} {st.mean([t['R_out'] for t in T if t['day'].startswith(y) and fn(t)] or [0]):+.2f}({sum(1 for t in T if t['day'].startswith(y) and fn(t))})" for y in years))

# monthly regime correlation
mon = collections.defaultdict(list)
for t in T: mon[t['day'][:7]].append(t)
months = sorted(mon)


def month_regime(mo):
    ds_m = [d for d in days if d.startswith(mo)]
    if len(ds_m) < 10: return None
    rv = []; er = []; hold = []; rngs = []; follow = []
    for d in ds_m:
        m = mkt(d)
        if m: rv.append(m['rv'])
        for p in LIVE:
            b = ds.bars[p].get(d)
            if not b: continue
            path = sum(abs(b[i][3] / b[i - 1][3] - 1) for i in range(1, 78)); net = abs(b[-1][3] / b[0][0] - 1)
            if path: er.append(net / path)
            rngs.append((max(x[1] for x in b) - min(x[2] for x in b)) / b[0][0] * 100)
            H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6])
            for j in range(6, 9):
                cl = b[j][3]
                if cl > H or cl < L:
                    up = cl > H; edge = H if up else L; end = b[47][3]
                    hold.append(1 if (end > edge if up else end < edge) else 0); follow.append(((end - edge) if up else (edge - end)) / edge * 100); break
    return dict(rv=st.mean(rv) if rv else 0, eff=st.mean(er), hold=st.mean(hold) if hold else 0, follow=st.mean(follow) if follow else 0, rng=st.mean(rngs), nbrk=len(hold))


reg = {mo: month_regime(mo) for mo in months}
good = [mo for mo in months if reg[mo]]
R_m = {mo: st.mean(t['R_out'] for t in mon[mo]) for mo in good}
print("\n  Month-level link between market behaviour and FADE avg R (Spearman; |rho| > 0.26 is significant at 5% with ~60 months):")
print(f"  {'variable':<44}{'same month':>11}{'next month':>12}{'prior month':>13}")
for name, key in (('QQQ 20d realized vol (prior to the day, avg)', 'rv'), ('intraday efficiency ratio (trendiness; high = trends)', 'eff'),
                  ('box-break hold rate (break still outside box at 13:30)', 'hold'), ('break follow-through to 13:30 (% beyond edge)', 'follow'),
                  ('avg daily range % of the six proxies', 'rng')):
    same = spearman([reg[m][key] for m in good], [R_m[m] for m in good])
    nxt = spearman([reg[good[i]][key] for i in range(len(good) - 1)], [R_m[good[i + 1]] for i in range(len(good) - 1)])
    prv = spearman([reg[good[i + 1]][key] for i in range(len(good) - 1)], [R_m[good[i]] for i in range(len(good) - 1)])
    print(f"  {name:<44}{same:>+11.2f}{nxt:>+12.2f}{prv:>+13.2f}")
print(f"\n  months: {len(good)}; FADE avg R positive in {sum(1 for m in good if R_m[m] > 0)} of them. Monthly regime table (avg R, hold rate, follow-through, efficiency):")
for m in good[-24:]: print(f"   {m}  n {len(mon[m]):3d} avgR {R_m[m]:+.2f}  hold {100*reg[m]['hold']:3.0f}%  follow {reg[m]['follow']:+.2f}%  eff {reg[m]['eff']:.2f}  rv {reg[m]['rv']:.2f}")

# ---------------------------------------------------------------- B. adaptive layers
print("\n=================== B. ADAPTIVE LAYERS, WALK-FORWARD (account %/day on the six proxies; decisions use only earlier data) ===================")
start_oos = '2023-01-01'; oos_days = [d for d in days if d >= start_oos]; S_oos = set(oos_days)
fixed_oos = [t for t in T if t['day'] >= start_oos]
a0, m0 = acct(fixed_oos, oos_days)
print(f"  FIXED live rule, {oos_days[0]}..{oos_days[-1]} ({len(oos_days)} days): {len(a0['taken'])} trades, {m0:+.3f}%/day, return {a0['ret']:+.1f}%, DD {a0['mdd']:.1f}%")
pre = [d for d in days if d < '2026-03-01' and d >= start_oos]; a_pre, m_pre = acct([t for t in fixed_oos if t['day'] < '2026-03-01'], pre)
print(f"  FIXED live rule, {pre[0]}..{pre[-1]} (before the rules' own window): {len(a_pre['taken'])} trades, {m_pre:+.3f}%/day, return {a_pre['ret']:+.1f}%, DD {a_pre['mdd']:.1f}%\n")


def report(tag, Tk):
    a, m_ = acct(Tk, oos_days); ap, mp = acct([t for t in Tk if t['day'] < '2026-03-01'], pre)
    print(f"  {tag:<46} all OOS: {len(a['taken']):3d} trades {m_:+.3f}%/day ret {a['ret']:+7.1f}% DD {a['mdd']:5.1f}% | before 2026-03: {len(ap['taken']):3d} trades {mp:+.3f}%/day ret {ap['ret']:+7.1f}% DD {ap['mdd']:5.1f}%")
    return m_, mp


# noise floor: random skipping of the same share
def noise(frac_keep, n=300, seed=3):
    rnd = random.Random(seed); out = []
    for _ in range(n):
        Tk = [t for t in fixed_oos if rnd.random() < frac_keep]; out.append(acct(Tk, oos_days)[1])
    out.sort(); return out[int(.05 * n)], st.mean(out), out[int(.95 * n)]


# (1) trailing on/off switch using all eleven names' setups as the tracker
allT = F.trades(ds, days, syms, base, ctx)
byday = collections.defaultdict(list)
for t in allT: byday[t['day']].append(t['R_out'])
print("(1) TRAILING-PERFORMANCE SWITCH: trade day d only if the summed R of all setups on all names over the previous N days > X")
for N in (20, 40, 60, 90):
    for X in (0, 5):
        on = set()
        for d in days:
            i = days.index(d)
            if i >= N and sum(sum(byday.get(x, [])) for x in days[i - N:i]) > X: on.add(d)
        Tk = [t for t in fixed_oos if t['day'] in on]; report(f"  switch N={N} X>{X} (on {100*len([d for d in oos_days if d in on])/len(oos_days):.0f}% of days)", Tk)

# (2) walk-forward parameter choice
print("\n(2) MONTHLY RE-CHOICE OF PARAMETERS from a small grid, scored on the trailing 12 months (min 40 trades), applied to the next month")
grid = {'live': base, 'R1.5': replace(base, R=1.5), 'R3': replace(base, R=3.0), 'frac0': replace(base, frac=0.0), 'chand3': replace(base, chand=3.0),
        'last29': replace(base, last=29), 'last77': replace(base, last=77), 'floor.3': replace(base, floor_pct=0.3), 'floor.5': replace(base, floor_pct=0.5),
        'wait3': replace(base, wait=3), 'gap_with': replace(base, gap='with'), 'side+1': replace(base, side=1), 'side-1': replace(base, side=-1),
        'brk7': replace(base, brk_end=7), 'brk12': replace(base, brk_end=12), 'box3': replace(base, box=3, brk_end=6), 'floor.4+wait3': replace(base, floor_pct=0.4, wait=3)}
GT = {k: F.trades(ds, days, LIVE, c, ctx) for k, c in grid.items()}
mo_list = sorted({d[:7] for d in oos_days}); chosen = []; Tw = []; pick = collections.Counter()
for mo in mo_list:
    first = [d for d in days if d.startswith(mo)][0]; i = days.index(first)
    tr_days = days[max(0, i - 252):i]; ts = set(tr_days); best = None
    for k, tl in GT.items():
        sub = [t for t in tl if t['day'] in ts]
        if len(sub) < 40: continue
        a, mean = acct(sub, tr_days)
        if best is None or mean > best[0]: best = (mean, k)
    k = best[1] if best else 'live'; pick[k] += 1
    Tw += [t for t in GT[k] if t['day'].startswith(mo)]
Tw = [dict(t, f=None) for t in Tw]
report("  walk-forward parameter choice", Tw)
print("     choices: " + ', '.join(f"{k} {v}" for k, v in pick.most_common()))
report("  (reference) always 'live'", [dict(t) for t in GT['live'] if t['day'] >= start_oos])

# (3) ML filters
print("\n(3) MACHINE-LEARNING TRADE FILTER (pre-entry features -> P(win)); expanding window, retrained every month, trade only if P(win) is above the training base rate")
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
keys = list(T[0]['f'].keys()); X = np.array([[t['f'][k] for k in keys] for t in T]); y = np.array([1 if t['pct'] > 0 else 0 for t in T]); Rr = np.array([t['R_out'] for t in T])
dday = np.array([t['day'] for t in T])
models = {'logistic': lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500)),
          'boosting(depth2)': lambda: GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.7, random_state=1)}
for name, mk in models.items():
    keep = np.zeros(len(T), bool); score = np.full(len(T), np.nan)
    for mo in mo_list:
        te = np.array([d.startswith(mo) for d in dday]); trn = dday < mo + '-01'
        if te.sum() == 0 or trn.sum() < 150: continue
        mdl = mk().fit(X[trn], y[trn]); pr = mdl.predict_proba(X[te])[:, 1]; score[te] = pr; keep[te] = pr > y[trn].mean()
    ev = ~np.isnan(score); auc = roc_auc_score(y[ev], score[ev]); rho = spearman(list(score[ev]), list(Rr[ev]))
    Tk = [T[i] for i in range(len(T)) if keep[i] and ev[i]]
    frac = len(Tk) / max(1, ev.sum())
    print(f"  {name}: OOS setups {ev.sum()}, AUC {auc:.3f} (0.5 = no skill), Spearman(score, R) {rho:+.3f}, keeps {100*frac:.0f}% of setups; avg R kept {np.mean([t['R_out'] for t in Tk]):+.3f} vs skipped {np.mean(Rr[ev & ~keep]):+.3f}")
    report(f"  {name} filter", Tk)
    lo, mid, hi = noise(frac); print(f"     noise floor (random skipping of the same share): 5th pct {lo:+.3f}, mean {mid:+.3f}, 95th pct {hi:+.3f} %/day")
