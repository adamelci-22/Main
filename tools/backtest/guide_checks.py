#!/usr/bin/env python3
"""Checklist run: (1) why it fails earlier years: regime table, component ablation by era, cost stress, selection-bias diagnostics, and a synthetic random-walk null;
(2) ML controls (shuffled-label and planted-signal) for the walk-forward filter; (3) explicit a-priori regimes: do they behave the same in design and holdout;
(4) sample sizes per regime and forward-test status.   /usr/bin/python3 -I tools/backtest/guide_checks.py M5.json.gz > tools/backtest/results/guide_checks.txt"""
import collections, contextlib, csv, io, math, os, random, statistics as st, sys
from dataclasses import replace
SRC = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = ['regime_adapt.py', SRC]
with contextlib.redirect_stdout(io.StringIO()):
    import regime_adapt as RA
import numpy as np
F = RA.F; ds = RA.ds; T = RA.T; days = RA.days; ctx = RA.ctx; LIVE = F.LIVE; base = F.P(); CUT = '2026-03-01'
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]
rnd = random.Random(11)


def acct_mean(Tk, dd):
    a = F.account(ds, dd, Tk); return a, st.mean(a['daily'].values()) if a['daily'] else 0.0


def boot(v, n=2000, seed=5):
    r = random.Random(seed); m = [st.mean(r.choice(v) for _ in v) for _ in range(n)]; m.sort(); return m[int(.05 * n)], m[int(.95 * n)]


def avgR(Tk): return st.mean(t['R_out'] for t in Tk) if Tk else float('nan')


print(f"Massive full-tape 5-minute bars {ds.days[0]}..{ds.days[-1]}; live FADE on the six proxies; 'before' = days up to 2026-02-27, 'since' = 2026-03-01 on (the window the rules were chosen on)\n")
print("================ STEP 1. WHY IT FAILED EARLIER YEARS ================")
print("1a. Regime table by quarter (QQQ move, QQQ 20-day vol, how often an opening-box break was still outside the box at 13:30, FADE result)")
qs = collections.defaultdict(list)
for t in T: y, m_ = t['day'][:4], int(t['day'][5:7]); qs[f"{y}-Q{(m_-1)//3+1}"].append(t)
print(f"  {'quarter':<8}{'n':>4}{'win%':>6}{'avg R':>7}{'QQQ qtr %':>10}{'QQQ vol':>8}{'break-hold':>11}")
for q in sorted(qs):
    v = qs[q]; dd = [d for d in days if d[:4] == q[:4] and (int(d[5:7]) - 1) // 3 + 1 == int(q[-1])]
    qq = [RA.dly['QQQ'][d]['c'] for d in dd if d in RA.dly['QQQ']]; rv = [RA.mkt(d)['rv'] for d in dd if RA.mkt(d)]
    hold = []
    for mo in sorted({d[:7] for d in dd}):
        r_ = RA.month_regime(mo)
        if r_ and r_['nbrk']: hold.append(r_['hold'])
    print(f"  {q:<8}{len(v):>4}{100*sum(t['pct']>0 for t in v)/len(v):>6.0f}{avgR(v):>+7.2f}{(qq[-1]/qq[0]-1)*100 if len(qq)>1 else 0:>+10.1f}{st.mean(rv) if rv else 0:>8.2f}{100*st.mean(hold) if hold else 0:>10.0f}%")

print("\n1b. Component ablation: take each rule component away or change it; avg R per setup and account %/day, before vs since 2026-03 (does the component help in both?)")
abl = {'LIVE': base, 'no partial (hold all to chandelier/13:30)': replace(base, frac=0.0), 'partial 1/2': replace(base, frac=0.5), 'no breakeven after partial': replace(base, be=False),
       'target 1R': replace(base, R=1.0), 'target 3R': replace(base, R=3.0), 'no chandelier': replace(base, chand=0), 'chandelier 3 ATR': replace(base, chand=3.0),
       'time exit 12:00': replace(base, last=29), 'time exit 15:55': replace(base, last=77), 'touch tol 0.0%': replace(base, tol=0.0), 'touch tol 0.3%': replace(base, tol=0.3),
       'retest within 3 bars': replace(base, wait=3), 'break window to 10:30': replace(base, brk_end=12), 'break window to 10:00': replace(base, brk_end=7),
       'box 15 min (3 bars)': replace(base, box=3, brk_end=6), 'box 45 min (9 bars)': replace(base, box=9, brk_end=12), 'stop floor 0.3%': replace(base, floor_pct=0.3),
       'stop floor 0.5%': replace(base, floor_pct=0.5), 'only up-breaks (bear leg)': replace(base, side=-1), 'only down-breaks (bull leg)': replace(base, side=1),
       'fade only in gap direction': replace(base, gap='with'), 'skip if retest bar does not close inside (live)': base}
GT = {}
print(f"  {'variant':<46}{'n bef':>6}{'avgR bef':>9}{'acct bef':>9}{'n since':>8}{'avgR since':>11}{'acct since':>11}")
for k, c in abl.items():
    if k.startswith('skip if'): continue
    tl = F.trades(ds, days, LIVE, c, ctx); GT[k] = tl
    a = [t for t in tl if t['day'] < CUT]; b = [t for t in tl if t['day'] >= CUT]
    print(f"  {k:<46}{len(a):>6}{avgR(a):>+9.3f}{acct_mean(a, pre)[1]:>+9.3f}{len(b):>8}{avgR(b):>+11.3f}{acct_mean(b, rec)[1]:>+11.3f}")

print("\n1c. Realistic costs: the model charges 0.06% round trip on the leg. Extra cost per round trip on the leg (spread and slippage on thin leveraged funds), account %/day:")
for extra in (0.0, 0.10, 0.20, 0.30):
    F.LEGCOST = 0.06 + extra; tl = F.trades(ds, days, LIVE, base, ctx)
    print(f"  extra {extra:.2f}%: before {acct_mean([t for t in tl if t['day']<CUT], pre)[1]:+.3f}  since {acct_mean([t for t in tl if t['day']>=CUT], rec)[1]:+.3f}")
F.LEGCOST = 0.06

print("\n1d. Look-ahead audit of the simulator (code review, results in tools/backtest/fade_diag.py): entry is the OPEN of the bar after the retest bar closes; the stop uses only bars up to the retest bar;")
print("    the chandelier uses ATR through the current bar and applies from the next bar; stop and target in the same bar resolve to the STOP (conservative); relative volume uses the 20 prior sessions and bars before the entry bar.")
print("    It reproduces the live engine trade for trade (75 = 75 on Robinhood bars). The real leak is SELECTION: lists, 10:10 entry, 0.10% tolerance, box length, partial and chandelier were all chosen after looking at 2026-03..10.")

print("\n1e. Selection-bias test: 150 random parameter variants. If tuning on the recent window found a real edge, variants that did well since March 2026 should also have done well before.")
sp = dict(box=[3, 4, 6], brk_extra=[1, 2, 3, 6], wait=[1, 3, 12], tol=[0.0, 0.1, 0.3], stop=['post', ('atr', 1.0), ('atr', 2.0), ('pct', 0.4), ('pct', 0.6)], stop_buf=[0.0, 0.5, 1.0],
          R=[1.0, 1.5, 2.0, 3.0], frac=[0.0, 1 / 3, 0.5, 1.0], chand=[0, 2.0, 3.0], last=[29, 47, 77], side=[0, 1, -1], gap=['', 'with'])
rows = []
for _ in range(150):
    x = {k: rnd.choice(v) for k, v in sp.items()}
    c = F.P(box=x['box'], brk_end=x['box'] + x['brk_extra'], wait=x['wait'], tol=x['tol'], stop=x['stop'], stop_buf=x['stop_buf'], R=x['R'], frac=x['frac'], chand=x['chand'], last=x['last'], side=x['side'], gap=x['gap'])
    tl = F.trades(ds, days, LIVE, c, ctx); a = [t for t in tl if t['day'] < CUT]; b = [t for t in tl if t['day'] >= CUT]
    if len(a) >= 100 and len(b) >= 40: rows.append((avgR(a), avgR(b), len(a), len(b)))
rho = RA.spearman([r[0] for r in rows], [r[1] for r in rows])
top_rec = sorted(rows, key=lambda r: -r[1])[:15]; top_pre = sorted(rows, key=lambda r: -r[0])[:15]
print(f"  {len(rows)} variants. Spearman between 'avg R before' and 'avg R since 2026-03' across variants: {rho:+.2f}")
print(f"  the 15 best variants since 2026-03 averaged {st.mean(r[1] for r in top_rec):+.3f} R since, and only {st.mean(r[0] for r in top_rec):+.3f} R before")
print(f"  the 15 best variants before 2026-03 averaged {st.mean(r[0] for r in top_pre):+.3f} R before, and {st.mean(r[1] for r in top_pre):+.3f} R since")
print(f"  variants positive both before and since: {sum(1 for r in rows if r[0] > 0 and r[1] > 0)} of {len(rows)}; negative before: {sum(1 for r in rows if r[0] <= 0)}")

print("\n1f. Synthetic random-walk null: same six proxies, same days, same 5-minute volatility and intraday shape, NO structure. How often does the live rule show a +0.4%/day window by luck?")
sig = {}
for p in LIVE:
    r = []
    for d in days[::7]:
        b = ds.bars[p][d]; r += [math.log(b[i][3] / b[i][0]) for i in range(1, 78)]
    sig[p] = st.pstdev(r)
shape = np.array([1 + 1.5 * math.exp(-i / 30) + 0.5 * math.exp(-(389 - i) / 60) for i in range(390)]); shape /= shape.mean()


def synth(seed):
    g = np.random.default_rng(seed); o = F.DS.__new__(F.DS); o.days = ds.days; o.bars = collections.defaultdict(dict); px = {p: 100.0 for p in LIVE}
    for d in ds.days:
        dm = math.exp(g.normal(0, 0.35)); zm = g.standard_normal(390)
        for p in LIVE:
            s1 = sig[p] / math.sqrt(5) * dm; z = math.sqrt(0.7) * zm + math.sqrt(0.3) * g.standard_normal(390)
            ret = z * s1 * shape; path = px[p] * np.exp(np.cumsum(ret)); prev = np.concatenate(([px[p]], path[:-1]))
            ex = np.abs(g.standard_normal(390)) * s1 * 0.4 * shape
            hi = np.maximum(prev, path) * (1 + ex); lo = np.minimum(prev, path) * (1 - np.abs(g.standard_normal(390)) * s1 * 0.4 * shape)
            bars = []
            for i in range(78):
                a_, b_ = i * 5, i * 5 + 5
                bars.append((float(prev[a_]), float(hi[a_:b_].max()), float(lo[a_:b_].min()), float(path[b_ - 1]), float(g.lognormal(10, 0.4))))
            o.bars[p][d] = bars; px[p] = float(path[-1]) * (1 + g.normal(0, 0.004))
    o.cum = {p: {d: F._cum(v) for d, v in o.bars[p].items()} for p in LIVE}; o.idx = {d: i for i, d in enumerate(o.days)}; return o


def roll(daily, w=157):
    v = list(daily.values()); return [st.mean(v[i:i + w]) for i in range(0, len(v) - w + 1)]


real_a = F.account(ds, days, [dict(t) for t in T]); rr = roll(real_a['daily'])
print(f"  REAL data: whole-period {st.mean(real_a['daily'].values()):+.3f}%/day; 157-day rolling windows: {len(rr)}, positive {100*sum(x>0 for x in rr)/len(rr):.0f}%, >= +0.2: {100*sum(x>=0.2 for x in rr)/len(rr):.0f}%, best {max(rr):+.3f}")
nulls = []
for s in range(10):
    sd = synth(100 + s); ctxs = F.context(sd, LIVE); tl = F.trades(sd, days, LIVE, base, ctxs); a = F.account(sd, days, tl); w = roll(a['daily'])
    nulls.append((st.mean(a['daily'].values()), max(w), sum(x >= 0.4 for x in w) / len(w), sum(x >= 0.2 for x in w) / len(w), len(a['taken'])))
print("  SYNTHETIC (10 seeds): whole-period %/day: " + ' '.join(f"{n[0]:+.3f}" for n in nulls))
print(f"    best 157-day window per seed: " + ' '.join(f"{n[1]:+.2f}" for n in nulls) + f"   (real best {max(rr):+.2f})")
print(f"    share of 157-day windows >= +0.4%/day: mean {100*st.mean(n[2] for n in nulls):.1f}%; >= +0.2: {100*st.mean(n[3] for n in nulls):.1f}%; seeds with any +0.4 window: {sum(1 for n in nulls if n[2]>0)} of 10; trades per seed ~{st.mean(n[4] for n in nulls):.0f}")

print("\n================ STEP 2. ML CONTROLS (is the filter pipeline itself sound?) ================")
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
keys = list(T[0]['f'].keys()); X = np.array([[t['f'][k] for k in keys] for t in T]); y = np.array([1 if t['pct'] > 0 else 0 for t in T]); dday = np.array([t['day'] for t in T])
mo_list = sorted({d[:7] for d in days if d >= '2023-01-01'})


def wf_auc(X_, y_):
    sc = np.full(len(y_), np.nan)
    for mo in mo_list:
        te = np.array([d.startswith(mo) for d in dday]); trn = dday < mo + '-01'
        if te.sum() == 0 or trn.sum() < 150: continue
        m_ = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500)).fit(X_[trn], y_[trn]); sc[te] = m_.predict_proba(X_[te])[:, 1]
    ev = ~np.isnan(sc); return roc_auc_score(y_[ev], sc[ev])


g = np.random.default_rng(9)
print(f"  real labels, logistic walk-forward OOS AUC: {wf_auc(X, y):.3f}")
print("  NEGATIVE control (labels shuffled; honest answer is 0.5): " + ' '.join(f"{wf_auc(X, g.permutation(y)):.3f}" for _ in range(8)))
plant = y + g.normal(0, 1.6, len(y)); print("  POSITIVE control (a weak planted signal added; pipeline should find it): " + ' '.join(f"{wf_auc(np.column_stack([X, y + g.normal(0, 1.6, len(y))]), y):.3f}" for _ in range(4)))

print("\n================ STEP 3. EXPLICIT REGIMES, DECIDED BEFORE LOOKING (do they behave the same in design and holdout?) ================")
qrv = [(d, RA.mkt(d)['rv']) for d in days if RA.mkt(d)]; rvmap = dict(qrv); rvlist = [x[1] for x in qrv]; rvi = {d: i for i, (d, _) in enumerate(qrv)}


def vol_state(d):
    i = rvi.get(d)
    if i is None or i < 120: return None
    return 'high vol' if rvmap[d] > st.median(rvlist[max(0, i - 252):i]) else 'low vol'


def trend_state(d):
    q = RA.prior('QQQ', d, 50)
    return None if len(q) < 50 else ('QQQ above 50d avg' if q[-1]['c'] > st.mean(x['c'] for x in q) else 'QQQ below 50d avg')


states = {'vol (QQQ 20d vol vs its trailing-year median)': vol_state, 'trend (QQQ vs 50-day average)': trend_state,
          'gap size': lambda d: None, 'side': lambda d: None}
cuts = (('DESIGN 2021-11..2024-06', lambda d: d <= '2024-06-30'), ('HOLDOUT 2024-07..2026-02', lambda d: '2024-07-01' <= d < CUT), ('SINCE 2026-03', lambda d: d >= CUT))
print(f"  {'regime':<46}" + ''.join(f"{c[0]:>34}" for c in cuts))
for name, fn in (('vol (QQQ 20d vol vs trailing-year median)', vol_state), ('trend (QQQ vs 50-day average)', trend_state)):
    for sv in sorted({fn(t['day']) for t in T if fn(t['day'])}):
        cells = []
        for cn, cf in cuts:
            v = [t['R_out'] for t in T if cf(t['day']) and fn(t['day']) == sv]
            lo, hi = boot(v) if len(v) > 5 else (float('nan'),) * 2
            cells.append(f"n {len(v):3d} avgR {avgR([{'R_out': x} for x in v]):+.2f} [{lo:+.2f},{hi:+.2f}]")
        print(f"  {sv:<46}" + ''.join(f"{c:>34}" for c in cells))
for sv, fn in (('big gap (>0.5%)', lambda t: t['f']['absgap'] > 0.5), ('small gap', lambda t: t['f']['absgap'] <= 0.5), ('up-break faded (bear leg)', lambda t: t['side'] < 0), ('down-break faded (bull leg)', lambda t: t['side'] > 0)):
    cells = []
    for cn, cf in cuts:
        v = [t['R_out'] for t in T if cf(t['day']) and fn(t)]; lo, hi = boot(v) if len(v) > 5 else (float('nan'),) * 2
        cells.append(f"n {len(v):3d} avgR {st.mean(v) if v else float('nan'):+.2f} [{lo:+.2f},{hi:+.2f}]")
    print(f"  {sv:<46}" + ''.join(f"{c:>34}" for c in cells))
print("  (bracket = 90% bootstrap interval of the mean R; an interval that crosses zero means the data cannot tell it from no edge)")

print("\n================ STEP 4. SAMPLE SIZE AND FORWARD TEST ================")
print(f"  FADE setups on the six proxies: {len(T)} in {len(set(t['day'][:7] for t in T))} months; before 2026-03: {sum(1 for t in T if t['day']<CUT)}; since: {sum(1 for t in T if t['day']>=CUT)}")
allr = [t['R_out'] for t in T]; lo, hi = boot(allr); b_ = [t['R_out'] for t in T if t['day'] < CUT]; s_ = [t['R_out'] for t in T if t['day'] >= CUT]
print(f"  avg R all {st.mean(allr):+.3f} [{lo:+.3f},{hi:+.3f}]; before {st.mean(b_):+.3f} [{boot(b_)[0]:+.3f},{boot(b_)[1]:+.3f}]; since {st.mean(s_):+.3f} [{boot(s_)[0]:+.3f},{boot(s_)[1]:+.3f}]")
for fn, lab in (('paper_trades.csv', 'model'), ('live_trades.csv', 'real')):
    p_ = os.path.join(HERE, '..', '..', 'archive', fn)
    if os.path.exists(p_): print(f"  forward record: {lab} trades logged in archive/{fn}: {sum(1 for _ in csv.DictReader(open(p_)))}")
