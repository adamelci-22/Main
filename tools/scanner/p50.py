#!/usr/bin/env python3
"""P50: probability that a long option returns +50% within 10 sessions. Walk-forward model + daily scorer.

    python3 tools/scanner/p50.py --study   > tools/scanner/results/p50_study.txt   # build data, walk-forward, calibration
    python3 tools/scanner/p50.py --score                                             # train on all history, score the last bar

Trade being predicted (fixed before any modelling):
  signal at the close of day i -> buy at the open of i+1 a 21-session (about 30 calendar days) 0.60-delta CALL or PUT;
  a limit sell at +50% over the fill (checked at each close, filled at exactly +50%); otherwise sell at the 10th session close.
  Label = 1 if the +50% exit filled. Realised return is +50% for a hit, else the 10th-session value.
Prices are MODELLED as in lab.py (Black-Scholes, IV = max(rv20, rv60) x 1.15, x 1.35 into earnings; ETFs from VIX), half-spread
max($0.03, 1.5%) per side plus fees. Robinhood keeps no option history, so real fills will differ; the scorer is meant to be
checked on real quotes before money is used.
Features use only data known at the close of day i. Walk-forward: retrain every 6 months on everything that ended at least
15 sessions before the test block (no label overlaps the test block).
"""
import math, os, pickle, statistics as st, sys
import numpy as np
from math import erf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lab as L
from winners import SECTOR

DTE, DELTA, HOLD, TP, VRP, EARN_PREM = 21, 0.60, 10, 0.50, 1.15, 1.35
HS_PCT, HS_MIN, FEE = 0.015, 0.03, 0.0065
SECTORS = sorted(set(SECTOR.values()))
FEATS = ['cp', 'ret1', 'ret5', 'ret10', 'ret21', 'ret63', 'rsi2', 'rsi14', 'z20', 'z50', 'z200', 'rv20', 'rv60', 'rv_ratio',
         'vol_ratio', 'pos20', 'bbw_pct', 'gap', 'range_atr', 'rs21', 'rs63', 'beta', 'days_to_earn', 'days_since_earn',
         'last_earn_move', 'earn_in_hold', 'is_etf', 'sector', 'spy_ret5', 'spy_ret21', 'spy_z200', 'spy_trend', 'vix',
         'vix_chg5', 'vix_vs20', 'hyg_z50', 'tlt_z50', 'dow']

_ncdf = np.vectorize(lambda x: 0.5 * (1 + erf(x / math.sqrt(2))))


def ncdf(x): return 0.5 * (1 + np.vectorize(erf)(x / math.sqrt(2)))


def bs_vec(S, K, T, sig, cp):
    S, K, T, sig = map(np.asarray, (S, K, T, sig))
    v = sig * np.sqrt(np.maximum(T, 1e-9))
    d1 = (np.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    call = S * ncdf(d1) - K * ncdf(d2); put = K * ncdf(-d2) - S * ncdf(-d1)
    out = np.where(cp > 0, call, put)
    intrinsic = np.maximum(0, cp * (S - K))
    return np.where(T <= 0, intrinsic, out)


def build_rows(U, reg, vix):
    spy = U['SPY']; vd = {d: v for d, v in vix.items()}
    vdates = sorted(vd)
    vix20 = {}; vix5 = {}
    for j, d in enumerate(vdates):
        if j >= 20: vix20[d] = sum(vd[x] for x in vdates[j - 19:j + 1]) / 20
        if j >= 5: vix5[d] = vd[d] / vd[vdates[j - 5]] - 1
    def z(S, k, i): return (S['c'][i] - S[k][i]) / S['atr14'][i] if S[k][i] and S['atr14'][i] else np.nan
    X, Y, R, META = [], [], [], []
    from statistics import NormalDist
    nd = NormalDist()
    for s, S in U.items():
        n = len(S['d']); c = S['c']; o = S['o']
        earn = S['earn']; band = S['earn_band']
        lr = np.diff(np.log(np.array(c)), prepend=np.nan)
        for i in range(210, n - HOLD - 1):
            d = S['d'][i]; R0 = reg.get(d)
            if not R0 or d not in spy['idx'] or d not in vd: continue
            j = spy['idx'][d]; e = i + 1
            rv20 = S['rv20'][i] or np.nan; rv60 = S['rv60'][i] or np.nan
            # IV model (same as lab.iv_of)
            earn_exp = any(k in band for k in range(e, e + DTE + 1))
            if s in L.ETFS:
                ratio = (S['rv60'][i] or 0.2) / (spy['rv60'][j] or 0.15)
                sig_at = lambda k, ee=None: (vd.get(S['d'][k], vd[d]) / 100) * max(ratio, 0.6) * 1.05
            else:
                base = max(rv20 if rv20 == rv20 else 0, rv60 if rv60 == rv60 else 0) * VRP
                if base <= 0: continue
                sig_at = lambda k, base=base: base * (EARN_PREM if any(q in band for q in range(k + 1, e + DTE + 1)) else 1.0)
            prev_e = [k for k in earn if k <= i]; next_e = [k for k in sorted(band) if k > i]
            last_move = (c[prev_e[-1]] / c[prev_e[-1] - 1] - 1) if prev_e and prev_e[-1] > 0 else np.nan
            bw = S['bbw'][i]; lo = S['bbw_lo120'][i]
            hi20 = S['hi20'][i]; lo20 = S['lo20'][i]
            beta = np.nan
            if j > 61:
                a = lr[i - 59:i + 1]; b = np.diff(np.log(np.array(spy['c'][j - 60:j + 1])))
                if len(a) == len(b) and np.var(b) > 0: beta = float(np.cov(a, b)[0, 1] / np.var(b))
            hyg = U['HYG']; tlt = U['TLT']
            feats_common = dict(
                ret1=c[i] / c[i - 1] - 1, ret5=c[i] / c[i - 5] - 1, ret10=c[i] / c[i - 10] - 1, ret21=c[i] / c[i - 21] - 1,
                ret63=c[i] / c[i - 63] - 1, rsi2=S['rsi2'][i], rsi14=S['rsi14'][i], z20=z(S, 'sma20', i), z50=z(S, 'sma50', i),
                z200=z(S, 'sma200', i), rv20=rv20, rv60=rv60, rv_ratio=rv20 / rv60 if rv60 == rv60 and rv60 else np.nan,
                vol_ratio=S['v'][i] / S['vavg50'][i] if S['vavg50'][i] else np.nan,
                pos20=(c[i] - lo20) / (hi20 - lo20) if hi20 and lo20 and hi20 > lo20 else np.nan,
                bbw_pct=bw / lo if bw and lo else np.nan, gap=o[i] / c[i - 1] - 1,
                range_atr=(S['h'][i] - S['l'][i]) / S['atr14'][i] if S['atr14'][i] else np.nan,
                rs21=(c[i] / c[i - 21]) / (spy['c'][j] / spy['c'][j - 21]) - 1, rs63=(c[i] / c[i - 63]) / (spy['c'][j] / spy['c'][j - 63]) - 1,
                beta=beta, days_to_earn=(next_e[0] - i) if next_e else 99, days_since_earn=(i - prev_e[-1]) if prev_e else 99,
                last_earn_move=last_move, earn_in_hold=float(any(k in band for k in range(e, e + HOLD + 1))),
                is_etf=float(s in L.ETFS), sector=SECTORS.index(SECTOR.get(s, 'index/macro')),
                spy_ret5=spy['c'][j] / spy['c'][j - 5] - 1, spy_ret21=spy['c'][j] / spy['c'][j - 21] - 1,
                spy_z200=spy['c'][j] / spy['sma200'][j] - 1, spy_trend=float(bool(R0['spy_trend'])), vix=vd[d],
                vix_chg5=vix5.get(d, np.nan), vix_vs20=vd[d] / vix20[d] - 1 if d in vix20 else np.nan,
                hyg_z50=(hyg['c'][hyg['idx'][d]] / hyg['sma50'][hyg['idx'][d]] - 1) if d in hyg['idx'] and hyg['sma50'][hyg['idx'][d]] else np.nan,
                tlt_z50=(tlt['c'][tlt['idx'][d]] / tlt['sma50'][tlt['idx'][d]] - 1) if d in tlt['idx'] and tlt['sma50'][tlt['idx'][d]] else np.nan,
                dow=__import__('datetime').date.fromisoformat(d).weekday())
            S0 = o[e]; T0 = DTE / 252; sg0 = sig_at(i)
            v0 = sg0 * math.sqrt(T0)
            for cp in (1, -1):
                d1 = nd.inv_cdf(DELTA) if cp > 0 else -nd.inv_cdf(DELTA)
                K = S0 * math.exp(-(d1 * v0 - 0.5 * v0 * v0))
                m0 = float(bs_vec(S0, K, T0, sg0, cp))
                if m0 < 0.10: continue
                fill = m0 + max(HS_MIN, HS_PCT * m0) + FEE
                ks = np.arange(e, e + HOLD)
                Ts = (DTE - (ks - e) - 1) / 252
                sgs = np.array([sig_at(k) for k in ks])
                vals = bs_vec(np.array([c[k] for k in ks]), K, Ts, sgs, cp)
                net = np.maximum(vals - np.maximum(HS_MIN, HS_PCT * vals) - FEE, 0) / fill - 1
                hit = np.where(net >= TP)[0]
                y = 1 if len(hit) else 0
                ret = TP if y else float(net[-1])
                f = dict(feats_common); f['cp'] = cp
                X.append([f[k] for k in FEATS]); Y.append(y); R.append(ret)
                META.append((d, s, cp, round(K, 2), round(fill, 2), round(S0, 2), int(hit[0]) + 1 if y else 0, float(net.min())))
    return np.array(X, dtype=float), np.array(Y), np.array(R), META


def load_rows():
    f = os.path.join(HERE, 'data', 'p50_rows.pkl')
    if os.path.exists(f): return pickle.load(open(f, 'rb'))
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    out = build_rows(U, reg, vix); pickle.dump(out, open(f, 'wb')); return out


def model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                          l2_regularization=1.0, categorical_features=[FEATS.index('sector')], random_state=7)


def walk_forward(X, Y, R, META):
    dates = np.array([m[0] for m in META]); udates = sorted(set(dates))
    blocks = [('2023-07-01', '2024-01-01'), ('2024-01-01', '2024-07-01'), ('2024-07-01', '2025-01-01'), ('2025-01-01', '2025-07-01'),
              ('2025-07-01', '2026-01-01'), ('2026-01-01', '2026-07-01'), ('2026-07-01', '2027-01-01')]
    P = np.full(len(Y), np.nan)
    for a, b in blocks:
        # purge: training labels end 15 sessions before the block starts
        k = next(i for i, d in enumerate(udates) if d >= a); cut = udates[max(k - 15, 0)]
        tr = dates < cut; te = (dates >= a) & (dates < b)
        if te.sum() == 0: continue
        m = model().fit(X[tr], Y[tr]); P[te] = m.predict_proba(X[te])[:, 1]
        print(f'  block {a}..{b}: trained on {tr.sum():,} rows (to {cut}), scored {te.sum():,}')
    return P


def report(X, Y, R, META, P):
    ok = ~np.isnan(P); y, r, p = Y[ok], R[ok], P[ok]; meta = [m for m, k in zip(META, ok) if k]
    dates = np.array([m[0] for m in meta]); cps = np.array([m[2] for m in meta])
    print(f'\nOUT-OF-SAMPLE (every prediction made by a model that never saw that period): {ok.sum():,} candidate trades')
    print(f'  base rate: {100*y.mean():.1f}% of all candidates hit +50% within 10 sessions; mean return {100*r.mean():+.1f}%  (calls {100*Y[ok][cps>0].mean():.1f}%, puts {100*Y[ok][cps<0].mean():.1f}%)')
    print('\nCALIBRATION (predicted probability bucket -> what actually happened)')
    print('  predicted P(+50%)   trades    hit +50%   mean return   avg loss when missed   distinct days')
    edges = [0, .05, .10, .15, .20, .25, .30, .35, .40, .50, 1.01]
    for lo, hi in zip(edges, edges[1:]):
        k = (p >= lo) & (p < hi)
        if k.sum() < 20: continue
        miss = r[k & (y == 0)]
        print(f'  {100*lo:4.0f}-{100*hi:<4.0f}%        {k.sum():7,d}    {100*y[k].mean():5.1f}%     {100*r[k].mean():+6.1f}%       {100*miss.mean() if len(miss) else 0:+6.1f}%            {len(set(dates[k])):4d}')
    print('\nTOP PICKS: the K highest-probability candidates per day (one per symbol), out of sample')
    for K_ in (1, 3, 5):
        sel = []
        byd = {}
        for idx in np.argsort(-p):
            d = dates[idx]; s = meta[idx][1]
            lst = byd.setdefault(d, [])
            if len(lst) < K_ and s not in [meta[q][1] for q in lst]: lst.append(idx)
        sel = np.array([q for v in byd.values() for q in v])
        for thr in (0.0, 0.30, 0.40, 0.50):
            k = sel[p[sel] >= thr]
            if len(k) < 20: print(f'  top {K_}/day, P >= {thr:.2f}: n {len(k)}'); continue
            rr = r[k]; yy = y[k]; dd = dates[k]
            halves = sorted(set(dd)); mid = halves[len(halves) // 2]
            h1 = rr[dd < mid].mean(); h2 = rr[dd >= mid].mean()
            print(f'  top {K_}/day, P >= {thr:.2f}: n {len(k):5d} on {len(set(dd)):3d} days | hit +50% {100*yy.mean():5.1f}% | mean {100*rr.mean():+6.1f}% '
                  f'(1st half {100*h1:+.1f}%, 2nd {100*h2:+.1f}%) | avg miss {100*rr[yy==0].mean():+6.1f}% | worst {100*rr.min():+.0f}% | calls {100*(cps[k]>0).mean():.0f}%')
    print('\nBY HALF-YEAR BLOCK: candidates with P >= 0.40')
    for a in ('2023-07', '2024-01', '2024-07', '2025-01', '2025-07', '2026-01', '2026-07'):
        y0 = a[:4]; h = a[5:]; lo_ = f'{y0}-{h}-01'; hi_ = f'{y0}-12-31' if h == '07' else f'{y0}-06-30'
        k = (p >= 0.40) & (dates >= lo_) & (dates <= hi_)
        if k.sum(): print(f'  {a}: n {k.sum():5d}  hit {100*y[k].mean():5.1f}%  mean {100*r[k].mean():+6.1f}%  days {len(set(dates[k]))}')
        else: print(f'  {a}: n 0')


def importance(X, Y, META):
    from sklearn.inspection import permutation_importance
    dates = np.array([m[0] for m in META])
    tr = dates < '2025-07-01'; te = (dates >= '2025-07-15')
    m = model().fit(X[tr], Y[tr])
    idx = np.where(te)[0]; rng = np.random.default_rng(1); idx = rng.choice(idx, min(len(idx), 20000), replace=False)
    pi = permutation_importance(m, X[idx], Y[idx], scoring='roc_auc', n_repeats=3, random_state=1)
    order = np.argsort(-pi.importances_mean)
    from sklearn.metrics import roc_auc_score
    print(f'\nWHAT DRIVES IT (permutation importance, model trained to 2025-06, tested 2025-07-15..; test AUC {roc_auc_score(Y[idx], m.predict_proba(X[idx])[:,1]):.3f})')
    for o in order[:12]: print(f'  {FEATS[o]:16s} {pi.importances_mean[o]:+.4f}')


def score_today():
    X, Y, R, META = load_rows()
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    m = model().fit(X, Y)
    pickle.dump(m, open(os.path.join(HERE, 'data', 'p50_model.pkl'), 'wb'))
    print('scored with a model trained on all history; probabilities are only as good as the out-of-sample calibration table')


if __name__ == '__main__':
    if '--study' in sys.argv:
        X, Y, R, META = load_rows()
        print(f'rows {len(Y):,} (symbol-days x call/put), features {len(FEATS)}, hit rate {100*Y.mean():.1f}%')
        P = walk_forward(X, Y, R, META)
        np.save(os.path.join(HERE, 'data', 'p50_oos.npy'), P)
        report(X, Y, R, META, P)
        importance(X, Y, META)
    elif '--score' in sys.argv:
        score_today()
