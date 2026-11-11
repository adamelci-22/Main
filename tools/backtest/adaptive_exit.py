#!/usr/bin/env python3
"""Adaptive FADE exit research (governor 2026-11-11): default = live v5.2.22 exits; a DETECTOR watches the open trade and,
when it fires, switches the remaining shares to a DEFENSIVE action set. Detectors are taken from published exit systems:
Kaufman efficiency ratio (steady move against), Dow swing structure (higher-low break), Wilder Parabolic SAR flip and RSI
divergence, Wyckoff/VSA volume distribution, session VWAP loss, market (QQQ) turning against the trade, speed to +1R, and
price structure (far box edge, prior-day high/low) as a resistance target.
    python3 -I tools/backtest/adaptive_exit.py screen   > tools/backtest/results/adaptive_exit_screen_2026-11-11.txt
    python3 -I tools/backtest/adaptive_exit.py learn    > tools/backtest/results/adaptive_exit_learn_2026-11-11.txt
    python3 -I tools/backtest/adaptive_exit.py gated    > tools/backtest/results/adaptive_exit_gated_2026-11-11.txt
Data: Robinhood cache 2026-03-03..10-14 (the live sample) and the Massive 5-minute tape 2021-11..2026-10 (two halves split
2024-04-01). FADE live 6 proxies, no Fridays. A candidate counts only if it beats the default in all three blocks."""
import datetime as dt, math, os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
M5 = '/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/m5/M5.json.gz'
LAST = 47; LOCK = (0.5, 0.15); CUT = (3, -0.5); TR2, FRAC, CHAND = 2.0, 1 / 3, 2.0
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4


# ------------------------------------------------------------------ data + cached entries
class Block:
    def __init__(self, name, ds, days, ctx):
        self.name, self.ds, self.days, self.ctx = name, ds, days, ctx
        rec = []
        def grab(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
            info.update(b=b, k=k, side=side, entry=entry, ext=ext); return info
        old = F._manage; F._manage = grab
        try: E = [t for t in F.trades(ds, days, F.LIVE, F.P(), ctx) if not fri(t['day'])]
        finally: F._manage = old
        for t in E: t.update(feat(ds, ctx, t)); t['atr'] = ctx['atr'][t['proxy']][t['day']]
        self.E = E


def load():
    out = []
    ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE)
    out.append(Block('RH 26-03..10', ds, [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14'], ctx))
    if os.path.exists(M5):
        dm = F.DS(M5, F.LIVE); cm = F.context(dm, F.LIVE); days = dm.days[21:]
        out.append(Block('MASSIVE H1 21-12..24-03', dm, [d for d in days if d < '2024-04-01'], cm))
        out.append(Block('MASSIVE H2 24-04..26-10', dm, [d for d in days if d >= '2024-04-01'], cm))
    return out


# ------------------------------------------------------------------ per-trade feature arrays (x-space: up = in the trade's favour)
def feat(ds, ctx, t):
    b, s, k, p, d = t['b'], t['side'], t['k'], t['proxy'], t['day']
    xc = [s * x[3] for x in b]; xh = [s * (x[1] if s > 0 else x[2]) for x in b]; xl = [s * (x[2] if s > 0 else x[1]) for x in b]
    v = [x[4] for x in b]
    # session VWAP
    pv = cv = 0.0; vw = []
    for x in b:
        tp = (x[1] + x[2] + x[3]) / 3; pv += tp * x[4]; cv += x[4]; vw.append(s * (pv / cv if cv else x[3]))
    # RSI(14), Wilder, on xc
    rsi = [50.0] * len(xc); ag = al = 0.0
    for j in range(1, len(xc)):
        ch = xc[j] - xc[j - 1]; g, l_ = max(ch, 0), max(-ch, 0)
        if j <= 14: ag += g / 14; al += l_ / 14
        else: ag = (ag * 13 + g) / 14; al = (al * 13 + l_) / 14
        rsi[j] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    # Parabolic SAR (long in x-space) from the entry bar
    sar = [None] * len(xc); af, ep, sv = 0.02, xh[k], xl[k - 1]
    for j in range(k, len(xc)):
        sar[j] = sv
        if xh[j] > ep: ep = xh[j]; af = min(0.2, af + 0.02)
        sv = min(sv + af * (ep - sv), xl[j], xl[j - 1])
    # market: QQQ in the trade direction (None for QQQ itself)
    q = ds.bars['QQQ'].get(d) if p != 'QQQ' else None
    mk = [s * (q[j][3] / q[k - 1][3] - 1) * 100 for j in range(len(q))] if q else None
    # structure levels in R from entry
    r = (t['entry'] - t['ext']) * s
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6]); far = H if s > 0 else L
    i = ds.idx[d]; pb = ds.bars[p].get(ds.days[i - 1]) if i else None
    pdx = (max(x[1] for x in pb) if s > 0 else min(x[2] for x in pb)) if pb else None
    lvl = lambda px: (px - t['entry']) * s / r if px is not None else None
    return dict(xc=xc, xh=xh, xl=xl, v=v, vw=vw, rsi=rsi, sar=sar, mk=mk, r=r, far_R=lvl(far), pdx_R=lvl(pdx))


# ------------------------------------------------------------------ manager
def manage(t, cfg, at):
    """cfg: None (default) or dict(det=fn(t, j, S) -> bool, arm=R, acts=[...], pre_only=True, struct=None)."""
    b, s, k, entry = t['b'], t['side'], t['k'], t['entry']; stop = t['ext']; r = t['r']
    if r <= 0: return None
    T = entry + s * TR2 * r; frac = FRAC
    rem, gross, hit = 1.0, 0.0, False; hic = entry; bestc = 0.0; pend = None; out = False; sell_next = 0.0
    S = dict(peak=k, fired=None, bars1R=None); chand_pre = None; swing = None
    if cfg and cfg.get('struct'):                       # pre-emptive structural target for the 1/3
        lv = t.get(cfg['struct'])
        if lv is not None and cfg.get('slo', 1.0) <= lv - cfg.get('buf', 0.0) < TR2: T = entry + s * (lv - cfg.get('buf', 0.0)) * r
    j = k
    for j in range(k, LAST + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: gross += rem * (o - entry) * s; rem = 0; break
        if sell_next > 0:                               # defensive partial at this bar's open
            q = min(sell_next, rem); gross += q * (o - entry) * s; rem -= q; sell_next = 0
            if rem <= 1e-9: break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o; gross += rem * (px - entry) * s; rem = 0; break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; q = min(frac, rem); gross += q * (px - entry) * s; rem -= q; hit = True
            if (entry - stop) * s > 0: stop = entry
            if rem <= 1e-9: break
        cr = (cl - entry) * s / r
        if cr > bestc: bestc = cr; S['peak'] = j
        if S['bars1R'] is None and cr >= 1.0: S['bars1R'] = j - k + 1
        lvl = None
        if bestc >= LOCK[0]: lvl = LOCK[1]
        if lvl is not None:
            ns = entry + s * lvl * r
            if (ns - stop) * s > 0: pend = ns if pend is None or (ns - pend) * s > 0 else pend
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < LAST:
            ns = hic - s * CHAND * at[j]
            if (ns - stop) * s > 0: stop = ns
        if chand_pre and j < LAST:                      # defensive tight chandelier (pre or post TP)
            ns = hic - s * chand_pre * at[j]
            if (ns - stop) * s > 0: pend = ns if pend is None or (ns - pend) * s > 0 else pend
        if swing and j < LAST:                          # defensive swing stop: lowest low of the last n bars
            ns = s * min(t['xl'][max(k, j - swing + 1):j + 1])
            if (ns - stop) * s > 0: pend = ns if pend is None or (ns - pend) * s > 0 else pend
        if j - k + 1 == CUT[0] and cr <= CUT[1] and j < LAST: out = True
        if cfg and cfg.get('det') and S['fired'] is None and bestc >= cfg['arm'] and j < LAST and j > k \
                and (not hit or not cfg.get('pre_only', True)):
            S.update(j=j, cr=cr, bestc=bestc)
            if cfg['det'](t, j, S):
                S['fired'] = j
                for a in cfg['acts']:
                    kind = a[0]
                    if kind == 'sell':                  # sell a fraction of the ORIGINAL position next open; counts as the take-profit
                        q = a[1] if hit else max(a[1], 0.0); sell_next += q
                        if not hit: hit = True; stop = entry if (entry - stop) * s > 0 else stop
                    elif kind == 'stop':                # raise the stop to +x R
                        ns = entry + s * a[1] * r
                        if (ns - stop) * s > 0: pend = ns if pend is None or (ns - pend) * s > 0 else pend
                    elif kind == 'target':              # lower the 1/3 target to y R (sell next open if already above it)
                        if not hit:
                            T = entry + s * a[1] * r
                            if cr >= a[1]: sell_next += frac; hit = True; stop = entry if (entry - stop) * s > 0 else stop
                    elif kind == 'chand': chand_pre = a[1]
                    elif kind == 'swing': swing = a[1]
                    elif kind == 'exit': out = True
    if rem > 0: gross += rem * (b[j][3] - entry) * s
    lev = F.LEV[t['proxy']][0] if s > 0 else F.LEV[t['proxy']][1]
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=gross / r, hit=hit, best=bestc, fired=S['fired'],
                pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)


def run(B, cfg):
    T = [x for x in (manage(t, cfg, B.ctx['atr'][t['proxy']][t['day']]) for t in B.E) if x]
    a = F.account(B.ds, B.days, T); tk = a['taken']
    g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
    return dict(n=len(tk), ret=a['ret'], pf=g / l if l else 99, R=st.mean(x['R_out'] for x in tk), mdd=a['mdd'],
                fired=sum(x['fired'] is not None for x in tk), tk=tk)


# ------------------------------------------------------------------ detectors (x-space; S has j, cr, bestc, peak, bars1R)
def G(S, x): return S['bestc'] - S['cr'] >= x
def ER(t, j, n):                                         # Kaufman efficiency ratio, signed (negative = steady move against)
    xc = t['xc']; d = sum(abs(xc[i] - xc[i - 1]) for i in range(j - n + 1, j + 1))
    return (xc[j] - xc[j - n]) / d if d else 0.0
def lower_n(t, j, n): xc = t['xc']; return all(xc[j - i] < xc[j - i - 1] for i in range(n))
def lower_highs(t, j, n): xh = t['xh']; return all(xh[j - i] < xh[j - i - 1] for i in range(n))
def struct_break(t, j, S, m=3):                          # close under the higher low made before the peak
    pk = S['peak']; lo = min(t['xl'][max(t['k'], pk - m):pk + 1]) if pk > t['k'] else None
    return lo is not None and j > pk and t['xc'][j] < lo
def psar_flip(t, j): return t['sar'][j] is not None and t['xl'][j] < t['sar'][j]
def rsi_div(t, j, S):                                    # peak RSI below the RSI of an earlier high in the trade, then a lower close
    pk = S['peak']; k = t['k']
    if pk < k + 4 or j <= pk: return False
    return t['rsi'][pk] < max(t['rsi'][k:pk - 2]) - 3 and t['xc'][j] < t['xc'][j - 1]   # earlier swing had stronger momentum
def vol_dist(t, j, n, m):                                # volume on falling bars >= m x volume on rising bars over n bars
    xc, v = t['xc'], t['v']; dn = sum(v[i] for i in range(j - n + 1, j + 1) if xc[i] < xc[i - 1]); up = sum(v[i] for i in range(j - n + 1, j + 1) if xc[i] > xc[i - 1])
    return dn >= m * max(up, 1)
def vwap_loss(t, j): return t['xc'][j] < t['vw'][j] and t['xc'][j - 1] >= t['vw'][j - 1]
def mkt_against(t, j, x): return t['mk'] is not None and t['mk'][j] <= -x
def slow(S, n): return S['bars1R'] is not None and S['bars1R'] >= n

DETS = {
    'ER4<=-0.6 & gave 0.4R':        lambda t, j, S: ER(t, j, 4) <= -0.6 and G(S, 0.4),
    'ER6<=-0.5 & gave 0.5R':        lambda t, j, S: ER(t, j, 6) <= -0.5 and G(S, 0.5),
    '2 lower closes & gave 0.5R':   lambda t, j, S: lower_n(t, j, 2) and G(S, 0.5),
    '3 lower highs & gave 0.3R':    lambda t, j, S: lower_highs(t, j, 3) and G(S, 0.3),
    'swing low break (Dow)':        lambda t, j, S: struct_break(t, j, S),
    'PSAR flip':                    lambda t, j, S: psar_flip(t, j),
    'RSI divergence':               lambda t, j, S: rsi_div(t, j, S),
    'volume distribution 2x, 4 bars': lambda t, j, S: vol_dist(t, j, 4, 2.0) and G(S, 0.3),
    'VWAP lost':                    lambda t, j, S: vwap_loss(t, j),
    'QQQ against 0.25%':            lambda t, j, S: mkt_against(t, j, 0.25),
    'QQQ against 0.25% & gave 0.3R': lambda t, j, S: mkt_against(t, j, 0.25) and G(S, 0.3),
    'slow to 1R (>=12 bars)':       lambda t, j, S: slow(S, 12),
    'ER4 + QQQ against':            lambda t, j, S: ER(t, j, 4) <= -0.5 and mkt_against(t, j, 0.15),
    'ER4 + volume distribution':    lambda t, j, S: ER(t, j, 4) <= -0.5 and vol_dist(t, j, 4, 1.5),
    'two of: ER4, struct, PSAR, VWAP, QQQ': lambda t, j, S: (ER(t, j, 4) <= -0.5) + struct_break(t, j, S) + psar_flip(t, j) + vwap_loss(t, j) + mkt_against(t, j, 0.15) >= 2,
}
ACTS = {
    'sell 1/3 now':                 [('sell', 1 / 3)],
    'stop to +0.5R':                [('stop', 0.5)],
    'target 1/3 to 1.25R':          [('target', 1.25)],
    'chandelier 1 ATR on all':      [('chand', 1.0)],
    'swing stop 3 bars':            [('swing', 3)],
    'sell 1/3 + stop +0.5R':        [('sell', 1 / 3), ('stop', 0.5)],
}


def fmt(base, x):
    return f"{x['ret']:+7.1f}% ({x['ret'] - base['ret']:+5.1f}) R {x['R']:+.3f} ({x['R'] - base['R']:+.3f}) PF {x['pf']:4.2f} f{x['fired']:3d}"


def screen():
    BL = load(); base = [run(B, None) for B in BL]
    print(__doc__.split('\n')[0]); print('blocks:', ' | '.join(f"{B.name}: {b['n']} trades, total {b['ret']:+.1f}%, avg R {b['R']:+.3f}, PF {b['pf']:.2f}" for B, b in zip(BL, base)))
    print(f"\ncolumns per block: total (change vs default) | avg R per trade (change) | PF | trades where the detector fired.  PASS = avg R better in every block")
    rows = []
    for arm in (1.0, 0.5):
        for dn, df in DETS.items():
            for an, ac in ACTS.items():
                cfg = dict(det=df, arm=arm, acts=ac)
                res = [run(B, cfg) for B in BL]
                ok = all(x['R'] > b['R'] + 1e-9 for x, b in zip(res, base))
                rows.append((ok, sum(x['R'] - b['R'] for x, b in zip(res, base)), f"arm {arm:g}R | {dn} -> {an}", res))
    # structural targets (no detector): the 1/3 target moves to the far box edge or the prior-day extreme when that sits between +1R and 2R
    for sn, key in (('far box edge', 'far_R'), ('prior-day high/low', 'pdx_R')):
        for buf in (0.0, 0.1, 0.25):
            for slo in (1.0, 0.75):
                cfg = dict(struct=key, buf=buf, slo=slo)
                res = [run(B, cfg) for B in BL]
                ok = all(x['R'] > b['R'] + 1e-9 for x, b in zip(res, base))
                rows.append((ok, sum(x['R'] - b['R'] for x, b in zip(res, base)), f"1/3 target at {sn} - {buf:g}R when in [{slo:g}R, 2R)", res))
    rows.sort(key=lambda z: (-z[0], -z[1]))
    print(f"\n{'rule':<70} " + ' | '.join(f"{B.name:<52}" for B in BL))
    print(f"{'DEFAULT v5.2.22':<70} " + ' | '.join(f"{fmt(b, b):<52}" for b in base))
    for ok, sc, name, res in rows:
        print(f"{('PASS ' if ok else '     ') + name:<70} " + ' | '.join(f"{fmt(b, x):<52}" for b, x in zip(base, res)))


# ------------------------------------------------------------------ learned classifier: can the state at the first +1R close predict a 2R run?
def learn():
    import numpy as np
    BL = load(); rows = {B.name: [] for B in BL}
    for B in BL:
        for t in B.E:
            at = B.ctx['atr'][t['proxy']][t['day']]; base = manage(t, None, at)
            if base is None or base['best'] < 1.0: continue
            S = {}
            def det(t_, j, S_):                           # capture the state at the first close >= +1R (pre-TP), never fire
                if not S: S.update(j=j, f=state(t_, j, S_, at))
                return False
            manage(t, dict(det=det, arm=1.0, acts=[]), at)
            if S: rows[B.name].append((S['f'], 1 if base['hit'] else 0, base['R_out']))
    names = ['speed (bars to +1R)', 'ER6', 'ER12', 'RSI', 'vol ratio last 3 vs day', 'above VWAP (R)', 'QQQ since entry %', 'far edge (R)', 'prior-day level (R)', 'ATR / R', 'bar of day']
    tr = rows['MASSIVE H1 21-12..24-03'] + rows['MASSIVE H2 24-04..26-10']
    print('Decision point: the first 5-minute close at +1R or better, before the 2R take-profit. Label: the default reaches 2R.')
    for nm, rr in rows.items(): print(f"  {nm}: {len(rr)} trades reached +1R, {sum(x[1] for x in rr)} went on to 2R ({100*sum(x[1] for x in rr)/max(1,len(rr)):.0f}%)")
    X = np.array([x[0] for x in tr], float); y = np.array([x[1] for x in tr], float)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    print('\nOne feature at a time (Massive, both halves): AUC = chance the feature ranks a 2R trade above a fade-back (0.50 = no information)')
    for i, nm in enumerate(names): print(f"  {nm:<28} AUC {auc(X[:, i], y):.3f}")
    def fit(Xa, ya):
        Z = (Xa - mu) / sd; Z = np.c_[np.ones(len(Z)), Z]; w = np.zeros(Z.shape[1])
        for _ in range(4000):
            p = 1 / (1 + np.exp(-Z @ w)); w -= 0.05 * (Z.T @ (p - ya) / len(ya) + 0.01 * np.r_[0, w[1:]])
        return w
    pred = lambda w, Xa: 1 / (1 + np.exp(-np.c_[np.ones(len(Xa)), (Xa - mu) / sd] @ w))
    h1 = np.array([x[0] for x in rows['MASSIVE H1 21-12..24-03']], float); y1 = np.array([x[1] for x in rows['MASSIVE H1 21-12..24-03']], float)
    h2 = np.array([x[0] for x in rows['MASSIVE H2 24-04..26-10']], float); y2 = np.array([x[1] for x in rows['MASSIVE H2 24-04..26-10']], float)
    rh = np.array([x[0] for x in rows['RH 26-03..10']], float); yr = np.array([x[1] for x in rows['RH 26-03..10']], float)
    w = fit(h1, y1)
    print(f"\nLogistic model, all features, trained on Massive H1 only:  AUC in-sample {auc(pred(w, h1), y1):.3f} | out-of-sample Massive H2 {auc(pred(w, h2), y2):.3f} | out-of-sample Robinhood {auc(pred(w, rh), yr):.3f}")
    print('  weights (standardised):', ', '.join(f"{nm} {wi:+.2f}" for nm, wi in zip(names, w[1:])))


def state(t, j, S, at):
    xc, v = t['xc'], t['v']; k = t['k']; r = t['r']
    dayv = sum(v[:j + 1]) / (j + 1); rec = sum(v[j - 2:j + 1]) / 3
    return [S['bars1R'] or (j - k + 1), ER(t, j, min(6, j - k + 1)) if j - k >= 1 else 0, ER(t, j, min(12, j - k + 1)) if j - k >= 1 else 0,
            t['rsi'][j], rec / dayv if dayv else 1, (xc[j] - t['vw'][j]) / r, t['mk'][j] if t['mk'] else 0.0,
            t['far_R'] if t['far_R'] is not None else 3.0, t['pdx_R'] if t['pdx_R'] is not None else 3.0, at[j] / r, j]


def auc(s, y):
    import numpy as np
    o = np.argsort(s); rk = np.empty(len(s)); rk[o] = np.arange(1, len(s) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return (rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else float('nan')



# ------------------------------------------------------------------ gated rule: decide ONCE at the first +1R close, from the two informative features
def gated():
    import numpy as np
    BL = load(); base = [run(B, None) for B in BL]
    first = lambda f: (lambda t, j, S: S['cr'] >= 1.0 and f(t, j, S))          # fires on the first close >= +1R only (arm 1R, fires once)
    atr_r = lambda t, j: t['atr'][j] / t['r']
    far = lambda t: t['far_R'] if t['far_R'] is not None else 9.0
    # logistic gate trained on Massive H1 only (all 11 features), applied out of sample to H2 and Robinhood
    rows = []
    for t in BL[1].E:
        b0 = manage(t, None, t['atr'])
        if b0 is None or b0['best'] < 1.0: continue
        S = {}
        def cap(t_, j, S_):
            if not S: S.update(f=state(t_, j, S_, t_['atr']))
            return False
        manage(t, dict(det=cap, arm=1.0, acts=[]), t['atr'])
        if S: rows.append((S['f'], 1.0 if b0['hit'] else 0.0))
    X = np.array([r_[0] for r_ in rows]); y = np.array([r_[1] for r_ in rows]); mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]; w = np.zeros(Z.shape[1])
    for _ in range(4000):
        pr = 1 / (1 + np.exp(-Z @ w)); w -= 0.05 * (Z.T @ (pr - y) / len(y) + 0.01 * np.r_[0, w[1:]])
    P = lambda t, j, S: float(1 / (1 + np.exp(-np.r_[1, (np.array(state(t, j, S, t['atr'])) - mu) / sd] @ w)))
    GATES = {}
    for fx in (1.5, 2.0, 2.5):
        GATES[f'far box edge < {fx:g}R'] = first(lambda t, j, S, fx=fx: far(t) < fx)
    for ax in (0.4, 0.6, 0.8):
        GATES[f'ATR/R < {ax:g}'] = first(lambda t, j, S, ax=ax: atr_r(t, j) < ax)
    for fx in (2.0, 2.5):
        for ax in (0.6, 0.8):
            GATES[f'far edge < {fx:g}R AND ATR/R < {ax:g}'] = first(lambda t, j, S, fx=fx, ax=ax: far(t) < fx and atr_r(t, j) < ax)
    for th in (0.4, 0.5, 0.6):
        GATES[f'logistic P(2R) < {th:g} (trained H1)'] = first(lambda t, j, S, th=th: P(t, j, S) < th)
    ACTS2 = {'target 1/3 to 1.25R': [('target', 1.25)], 'target 1/3 to 1.5R': [('target', 1.5)],
             'stop to +0.5R': [('stop', 0.5)], 'sell 1/3 now': [('sell', 1 / 3)], 'sell 1/3 now + stop +0.5R': [('sell', 1 / 3), ('stop', 0.5)],
             'target 1/3 1.5R + stop +0.5R': [('target', 1.5), ('stop', 0.5)], 'chandelier 1 ATR on all': [('chand', 1.0)]}
    print('Gated adaptive exit: one decision at the first 5-minute close at +1R (before 2R). If the gate says "unlikely to reach 2R", the remaining shares switch to the defensive action. Otherwise the default runs.')
    print('blocks:', ' | '.join(f"{B.name}: {b['n']} trades, total {b['ret']:+.1f}%, avg R {b['R']:+.3f}" for B, b in zip(BL, base)))
    print('logistic gate weights (trained on MASSIVE H1 only):', ', '.join(f"{v:+.2f}" for v in w))
    out = []
    for gn, gf in GATES.items():
        for an, ac in ACTS2.items():
            res = [run(B, dict(det=gf, arm=1.0, acts=ac)) for B in BL]
            ok = all(x['R'] > b['R'] + 1e-9 for x, b in zip(res, base))
            out.append((ok, sum(x['R'] - b['R'] for x, b in zip(res, base)), f"{gn} -> {an}", res))
    out.sort(key=lambda z: (-z[0], -z[1]))
    print(f"\n{'rule':<74} " + ' | '.join(f"{B.name:<52}" for B in BL))
    print(f"{'DEFAULT v5.2.22':<74} " + ' | '.join(f"{fmt(b, b):<52}" for b in base))
    for ok, sc, name, res in out:
        print(f"{('PASS ' if ok else '     ') + name:<74} " + ' | '.join(f"{fmt(b, x):<52}" for b, x in zip(base, res)))


if __name__ == '__main__':
    {'screen': screen, 'learn': learn, 'gated': gated}[sys.argv[1]]()
