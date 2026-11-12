#!/usr/bin/env python3
"""Swing-option research engine: 1-2 week long call / put holds on 80 liquid optionable symbols, 2021-11 .. 2026-11.

    python3 tools/scanner/lab.py              # full study -> stdout (tools/scanner/results/study.txt)

Data: Robinhood daily bars (tools/scanner/data/daily.json.gz), Robinhood VIX (vix_5y.csv).
Signals are evaluated at the CLOSE of day t (the scanner runs after the close). Entry = the OPEN of day t+1.
Option: about 30 calendar days to expiry (21 sessions), strike set by moneyness (default 0.60 delta: about 3% ITM).
Pricing: Black-Scholes in trading time. IV model:
    stocks:  max(rv20, rv60) x VRP (1.15 default), x 1.35 when an earnings day falls before expiry (event premium)
    ETFs:    VIX/100 x beta-vol ratio (realised rv60 / SPY rv60) x 1.05
Costs: half-spread max($0.03, 1.5% of premium) each side + $0.0065/share fees. Results are MODELLED option returns;
Robinhood keeps no history for expired contracts. The underlying move columns are real.
Exits: time (hold h sessions), option stop -50% at a close, option target +100% at a close (both optional, swept).
Split: DEV 2021-11 .. 2024-06-30, TEST 2024-07-01 .. end. Rules and parameters were written before looking at TEST.
"""
import csv, gzip, json, math, os, statistics as st, sys
from dataclasses import dataclass, replace

HERE = os.path.dirname(os.path.abspath(__file__))
ETFS = {'SPY', 'QQQ', 'IWM', 'XLF', 'XLE', 'XLK', 'XLV', 'XLI', 'XLY', 'XLP', 'XLU', 'SMH', 'XBI', 'TLT', 'GLD', 'SLV', 'USO', 'HYG', 'KRE', 'ARKK'}
MACRO_ONLY = {'TLT', 'HYG', 'USO', 'SLV'}           # used for regime features; still tradable
SPLIT = '2024-07-01'


# ------------------------------------------------------------------ data + indicators
EARN = {}


def load():
    raw = json.load(gzip.open(os.path.join(HERE, 'data', 'daily.json.gz')))
    with open(os.path.join(HERE, 'data', 'earnings.csv')) as f:
        for r in csv.DictReader(f): EARN.setdefault(r['symbol'], []).append((r['date'], r['timing']))
    vix = {}
    with open(os.path.join(HERE, 'data', 'vix_5y.csv')) as f:
        for r in csv.DictReader(f): vix[r['date']] = float(r['close'])
    return raw, vix


def sma(x, n, i): return sum(x[i - n + 1:i + 1]) / n if i >= n - 1 else None


def build(raw, vix):
    """Per symbol: dict of arrays + indicators. Returns {sym: S}, sorted SPY dates."""
    out = {}
    for s, rows in raw.items():
        d = [r[0] for r in rows]; o = [r[1] for r in rows]; h = [r[2] for r in rows]; l = [r[3] for r in rows]
        c = [r[4] for r in rows]; v = [r[5] for r in rows]; n = len(rows)
        lr = [0.0] + [math.log(c[i] / c[i - 1]) for i in range(1, n)]
        S = dict(d=d, o=o, h=h, l=l, c=c, v=v, idx={x: i for i, x in enumerate(d)})
        S['sma20'] = [sma(c, 20, i) for i in range(n)]; S['sma50'] = [sma(c, 50, i) for i in range(n)]
        S['sma200'] = [sma(c, 200, i) for i in range(n)]
        S['rv20'] = [st.pstdev(lr[i - 19:i + 1]) * math.sqrt(252) if i >= 20 else None for i in range(n)]
        S['rv60'] = [st.pstdev(lr[i - 59:i + 1]) * math.sqrt(252) if i >= 60 else None for i in range(n)]
        S['vavg50'] = [sum(v[i - 50:i]) / 50 if i >= 50 else None for i in range(n)]
        # RSI(2) and RSI(14), Wilder
        for p in (2, 14):
            ag = al = None; arr = [None] * n
            for i in range(1, n):
                g = max(c[i] - c[i - 1], 0); ls = max(c[i - 1] - c[i], 0)
                if i <= p:
                    if i == p:
                        gs = [max(c[k] - c[k - 1], 0) for k in range(1, p + 1)]; lss = [max(c[k - 1] - c[k], 0) for k in range(1, p + 1)]
                        ag, al = sum(gs) / p, sum(lss) / p
                    else: continue
                else: ag = (ag * (p - 1) + g) / p; al = (al * (p - 1) + ls) / p
                arr[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
            S[f'rsi{p}'] = arr
        tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
        S['atr14'] = [sum(tr[i - 13:i + 1]) / 14 if i >= 14 else None for i in range(n)]
        S['hi20'] = [max(h[i - 20:i]) if i >= 20 else None for i in range(n)]       # prior 20 sessions (excl. today)
        S['lo20'] = [min(l[i - 20:i]) if i >= 20 else None for i in range(n)]
        S['hi55'] = [max(c[i - 55:i]) if i >= 55 else None for i in range(n)]
        S['ret63'] = [c[i] / c[i - 63] - 1 if i >= 63 else None for i in range(n)]
        bw = [None] * n
        for i in range(19, n):
            m = S['sma20'][i]; sd = st.pstdev(c[i - 19:i + 1]); bw[i] = 4 * sd / m
        S['bbw'] = bw
        S['bbw_lo120'] = [min(x for x in bw[i - 120:i] if x is not None) if i >= 140 else None for i in range(n)]
        # earnings: real Robinhood report dates (data/earnings.csv). Reaction session = report day (am) or next session (pm).
        # 'est' dates (quarterly steps between real ones) feed only the hold-window skip, with a +-5 session band.
        ev, band = [], set()
        for dd, tm in EARN.get(s, []):
            k = next((j for j in range(len(d)) if d[j] >= dd), None)
            if k is None: continue
            if tm == 'pm' and d[k] == dd: k += 1
            if k >= n: continue
            if tm == 'est': band.update(range(max(0, k - 5), min(n, k + 6)))
            else: ev.append(k); band.add(k)
        S['earn'] = sorted(set(ev)); S['earn_band'] = band
        out[s] = S
    spy = out['SPY']
    # market regime per date
    reg = {}
    for i, d in enumerate(spy['d']):
        if i < 200: continue
        vx = vix.get(d)
        reg[d] = dict(spy_trend=spy['sma200'][i] > spy['sma200'][i - 20] if spy['sma200'][i - 20] else None,
                      spy_up=spy['c'][i] > spy['sma200'][i], spy_50=spy['c'][i] > spy['sma50'][i], vix=vx,
                      vix_20=vix_ma(vix, spy['d'], i), spy_rv60=spy['rv60'][i],
                      tlt_up=_above(out, 'TLT', d, 'sma50'), hyg_up=_above(out, 'HYG', d, 'sma50'))
    return out, reg


def vix_ma(vix, dates, i, n=20):
    xs = [vix[dates[k]] for k in range(i - n + 1, i + 1) if dates[k] in vix]
    return sum(xs) / len(xs) if xs else None


def _above(out, s, d, k):
    S = out.get(s)
    if not S or d not in S['idx']: return None
    i = S['idx'][d]; return S[k][i] is not None and S['c'][i] > S[k][i]


def check_earnings(out):
    """Proxy vs real report dates (Robinhood get_earnings_results, 2026-11-12). Reaction day = report day (am) or next session (pm)."""
    real = {'NVDA': [('2025-05-28', 'pm'), ('2025-08-27', 'pm'), ('2025-11-19', 'pm'), ('2026-02-25', 'pm'), ('2026-05-20', 'pm'), ('2026-08-26', 'pm')],
            'JPM': [('2025-04-11', 'am'), ('2025-07-15', 'am'), ('2025-10-14', 'am'), ('2026-01-13', 'am'), ('2026-04-14', 'am'), ('2026-07-14', 'am'), ('2026-10-13', 'am')]}
    lines = []
    for s, evs in real.items():
        S = out[s]; prox = {S['d'][i] for i in S['earn']}; hit = 0
        for d, t in evs:
            i = S['idx'].get(d)
            if i is None: continue
            rd = S['d'][i + 1] if t == 'pm' and i + 1 < len(S['d']) else d
            near = any(abs(S['idx'][x] - S['idx'][rd]) <= 1 for x in prox if x in S['idx'])
            hit += near
        lines.append(f'{s}: {hit}/{len(evs)} report reactions mapped')
    return lines


# ------------------------------------------------------------------ option model
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, sig, cp):
    if T <= 0 or sig <= 0: return max(0.0, cp * (S - K))
    v = sig * math.sqrt(T); d1 = (math.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    return S * ncdf(d1) - K * ncdf(d2) if cp > 0 else K * ncdf(-d2) - S * ncdf(-d1)


def strike_for_delta(S, T, sig, cp, delta):
    """K giving |delta| ~ target (BS, r=0)."""
    from statistics import NormalDist
    z = NormalDist().inv_cdf(delta if cp > 0 else delta)
    v = sig * math.sqrt(T)
    # call delta = N(d1) -> d1 = z ; put |delta| = N(-d1) -> d1 = -z
    d1 = z if cp > 0 else -z
    return S * math.exp(-(d1 * v - 0.5 * v * v))


@dataclass(frozen=True)
class OC:
    dte: int = 21                 # sessions to expiry at entry (about 30 calendar days)
    delta: float = 0.60
    vrp: float = 1.15
    earn_prem: float = 1.35
    hold: int = 10                # sessions
    stop: float = None            # e.g. 0.5 = exit at a close with the option down 50%
    target: float = None          # e.g. 1.0 = exit at a close with the option up 100%
    hs_pct: float = 0.015
    hs_min: float = 0.03
    fee: float = 0.0065
    skip_earn: bool = True        # skip a trade when an earnings day falls inside the hold
    exit_mode: str = 'time'       # 'time' | 'trail_und' (close < lowest low of the prior trail_n sessions) | 'trail_opt'
    trail_n: int = 10
    trail_arm: float = 0.5        # trail_opt: armed once the option is up this much at a close
    trail_give: float = 0.35      # trail_opt: then exit when it falls this fraction from its peak value


def iv_of(U, s, i, reg_d, spy, vixv, earn_ahead):
    if s in ETFS:
        r = (U[s]['rv60'][i] or 0.2) / (spy['rv60'][spy['idx'][U[s]['d'][i]]] or 0.15) if U[s]['d'][i] in spy['idx'] else 1.0
        base = (vixv or 20) / 100 * max(r, 0.6) * 1.05
        return base
    rv = max(U[s]['rv20'][i] or 0, U[s]['rv60'][i] or 0)
    return rv * OPT.vrp * (OPT.earn_prem if earn_ahead else 1.0)


OPT = OC()


def option_trade(U, reg, vix, s, i, cp, oc):
    """Signal at the close of i. Entry next open. Returns dict or None."""
    S_ = U[s]; n = len(S_['d'])
    if i + 1 + oc.hold >= n: return None
    e = i + 1; S0 = S_['o'][e]; d0 = S_['d'][e]
    earn_in_hold = any(k in S_['earn_band'] for k in range(e, e + oc.hold + 1))
    if oc.skip_earn and earn_in_hold: return None
    earn_before_exp = any(k in S_['earn_band'] for k in range(e, e + oc.dte + 1))
    spy = U['SPY']
    global OPT; OPT = oc
    sig0 = iv_of(U, s, i, None, spy, vix.get(S_['d'][i]), earn_before_exp)
    if not sig0: return None
    T0 = oc.dte / 252
    K = strike_for_delta(S0, T0, sig0, cp, oc.delta)
    m0 = bs(S0, K, T0, sig0, cp)
    if m0 < 0.10: return None
    hs = lambda m: max(oc.hs_min, oc.hs_pct * m)
    fill = m0 + hs(m0) + oc.fee
    xk, why = e + oc.hold - 1, 'time'
    peak = -1.0; peak_k = None; peak_val = 0.0
    for k in range(e, e + oc.hold):
        T = (oc.dte - (k - e) - 1) / 252                         # at the close of k
        eb = any(q in S_['earn_band'] for q in range(k + 1, e + oc.dte + 1))
        sg = iv_of(U, s, k, None, spy, vix.get(S_['d'][k]), eb)
        val = bs(S_['c'][k], K, T, sg, cp)
        r_k = (max(val - hs(val) - oc.fee, 0)) / fill - 1
        if r_k > peak: peak, peak_k = r_k, k - e + 1
        if oc.stop is not None and val <= fill * (1 - oc.stop): xk, why = k, 'stop'; break
        if oc.target is not None and val >= fill * (1 + oc.target): xk, why = k, 'target'; break
        if oc.exit_mode == 'trail_und' and k > e and k - oc.trail_n >= 0:
            lowest = min(S_['l'][q] for q in range(k - oc.trail_n, k)) if cp > 0 else None
            highest = max(S_['h'][q] for q in range(k - oc.trail_n, k)) if cp < 0 else None
            if (cp > 0 and S_['c'][k] < lowest) or (cp < 0 and S_['c'][k] > highest): xk, why = k, 'trail'; break
        if oc.exit_mode == 'trail_opt':
            peak_val = max(peak_val, val)
            if peak_val >= fill * (1 + oc.trail_arm) and val <= peak_val * (1 - oc.trail_give): xk, why = k, 'trail'; break
    T = (oc.dte - (xk - e) - 1) / 252
    eb = any(q in S_['earn_band'] for q in range(xk + 1, e + oc.dte + 1))
    m1 = bs(S_['c'][xk], K, T, iv_of(U, s, xk, None, spy, vix.get(S_['d'][xk]), eb), cp)
    ex = max(m1 - hs(m1) - oc.fee, 0)
    return dict(sym=s, d=S_['d'][i], cp=cp, ret=ex / fill - 1, und=(S_['c'][xk] / S0 - 1) * cp, why=why,
                prem_pct=fill / S0 * 100, iv=sig0, earn=earn_in_hold, peak=peak, peak_day=peak_k, i=i)


# ------------------------------------------------------------------ signals (evaluated at the close of i)
def g(S, k, i): return S[k][i]


SIGNALS = {}


def sig(name):
    def deco(f): SIGNALS[name] = f; return f
    return deco


@sig('C1 uptrend pullback: >200 & >50, RSI2<10 -> CALL')
def s_pb(S, i, R):
    if None in (S['sma200'][i], S['sma50'][i], S['rsi2'][i]): return 0
    return 1 if S['c'][i] > S['sma200'][i] and S['c'][i] > S['sma50'][i] * 0.97 and S['sma50'][i] > S['sma200'][i] and S['rsi2'][i] < 10 else 0


@sig('C2 breakout: close > prior 55d high, vol >1.5x, >200 -> CALL')
def s_bo(S, i, R):
    if None in (S['hi55'][i], S['vavg50'][i], S['sma200'][i]): return 0
    return 1 if S['c'][i] > S['hi55'][i] and S['v'][i] > 1.5 * S['vavg50'][i] and S['c'][i] > S['sma200'][i] else 0


@sig('C3 squeeze breakout: BB width at 6m low, close > 20d high -> CALL')
def s_sq(S, i, R):
    if None in (S['bbw_lo120'][i], S['hi20'][i], S['sma50'][i]): return 0
    return 1 if S['bbw'][i - 1] <= S['bbw_lo120'][i] * 1.1 and S['c'][i] > S['hi20'][i] and S['c'][i] > S['sma50'][i] else 0


@sig('C4 post-earnings drift UP: earnings day gap >+4%, closes top 30% -> CALL (next day)')
def s_pead_up(S, i, R):
    if i not in S['_earnset'] or i < 1: return 0
    gap = S['o'][i] / S['c'][i - 1] - 1; loc = (S['c'][i] - S['l'][i]) / max(S['h'][i] - S['l'][i], 1e-9)
    return 1 if gap > 0.04 and loc > 0.7 else 0


@sig('P4 post-earnings drift DOWN: gap <-4%, closes bottom 30% -> PUT')
def s_pead_dn(S, i, R):
    if i not in S['_earnset'] or i < 1: return 0
    gap = S['o'][i] / S['c'][i - 1] - 1; loc = (S['c'][i] - S['l'][i]) / max(S['h'][i] - S['l'][i], 1e-9)
    return -1 if gap < -0.04 and loc < 0.3 else 0


@sig('C5 relative strength leader: 3m return top 10% of universe, >50 & >200, RSI14 50-70 -> CALL')
def s_rs(S, i, R):
    return 1 if S.get('_rs_top', {}).get(i) and S['c'][i] > S['sma50'][i] > S['sma200'][i] and 50 <= S['rsi14'][i] <= 70 else 0


@sig('P1 downtrend rally fail: <200 & 50<200, RSI2>90 -> PUT')
def s_dt(S, i, R):
    if None in (S['sma200'][i], S['sma50'][i], S['rsi2'][i]): return 0
    return -1 if S['c'][i] < S['sma200'][i] and S['sma50'][i] < S['sma200'][i] and S['rsi2'][i] > 90 else 0


@sig('P2 breakdown: close < prior 20d low, vol >1.5x, <200 -> PUT')
def s_bd(S, i, R):
    if None in (S['lo20'][i], S['vavg50'][i], S['sma200'][i]): return 0
    return -1 if S['c'][i] < S['lo20'][i] and S['v'][i] > 1.5 * S['vavg50'][i] and S['c'][i] < S['sma200'][i] else 0


@sig('C6 capitulation bounce: RSI2<5, close >3 ATR below 20SMA, VIX>25 -> CALL')
def s_cap(S, i, R):
    if None in (S['rsi2'][i], S['atr14'][i], S['sma20'][i]) or not R or not R['vix']: return 0
    return 1 if S['rsi2'][i] < 5 and S['c'][i] < S['sma20'][i] - 3 * S['atr14'][i] and R['vix'] > 25 else 0


@sig('C7 breakdown reversal: close < prior 20d low on vol >1.5x -> CALL (mean reversion)')
def s_bdr(S, i, R):
    if None in (S['lo20'][i], S['vavg50'][i]): return 0
    return 1 if S['c'][i] < S['lo20'][i] and S['v'][i] > 1.5 * S['vavg50'][i] else 0


@sig('C8 deep oversold in uptrend: >200, RSI2<5, 3 down days -> CALL')
def s_os(S, i, R):
    if None in (S['sma200'][i], S['rsi2'][i]) or i < 3: return 0
    return 1 if S['c'][i] > S['sma200'][i] and S['rsi2'][i] < 5 and S['c'][i] < S['c'][i-1] < S['c'][i-2] < S['c'][i-3] else 0


FILTERS = {
    'none': lambda R, cp: True,
    'market with trade (SPY>200 calls / SPY<200 puts)': lambda R, cp: R['spy_up'] == (cp > 0),
    'VIX < 20': lambda R, cp: R['vix'] is not None and R['vix'] < 20,
    'VIX >= 20': lambda R, cp: R['vix'] is not None and R['vix'] >= 20,
    'VIX falling (VIX < 20d avg)': lambda R, cp: R['vix'] and R['vix_20'] and R['vix'] < R['vix_20'],
    'SPY 200d rising': lambda R, cp: R['spy_trend'] is True,
    'SPY 200d rising & VIX >= 20': lambda R, cp: R['spy_trend'] is True and R['vix'] is not None and R['vix'] >= 20,
    'credit risk-on (HYG>50SMA)': lambda R, cp: R['hyg_up'] == (cp > 0),
}


def prep(U):
    for s, S in U.items(): S['_earnset'] = set(S['earn'])
    # relative strength rank by date
    dates = U['SPY']['d']
    for d in dates:
        vals = [(U[s]['ret63'][U[s]['idx'][d]], s) for s in U if s not in ETFS and d in U[s]['idx'] and U[s]['ret63'][U[s]['idx'][d]] is not None]
        if len(vals) < 20: continue
        vals.sort(reverse=True); top = {s for _, s in vals[:max(1, len(vals) // 10)]}
        for s in top: U[s].setdefault('_rs_top', {})[U[s]['idx'][d]] = True


def run(U, reg, vix, name, oc, flt='none', syms=None, start=None, end=None):
    f = SIGNALS[name]; T = []
    for s, S in U.items():
        if syms and s not in syms: continue
        last = -99
        for i in range(200, len(S['d']) - 1):
            d = S['d'][i]
            if start and d < start or end and d >= end: continue
            R = reg.get(d)
            if not R: continue
            cp = f(S, i, R)
            if not cp or i - last < oc.hold: continue           # no overlapping trades per symbol
            if not FILTERS[flt](R, cp): continue
            t = option_trade(U, reg, vix, s, i, cp, oc)
            if t: T.append(t); last = i
    return T


def stats(T):
    if len(T) < 8: return dict(n=len(T))
    x = [t['ret'] for t in T]; w = [v for v in x if v > 0]; l = [v for v in x if v <= 0]
    m = st.mean(x); se = st.pstdev(x) / math.sqrt(len(x))
    return dict(n=len(x), win=len(w) / len(x), avg_w=st.mean(w) if w else 0, avg_l=st.mean(l) if l else 0, mean=m, t=m / se if se else 0,
                und=st.mean(t['und'] for t in T), med=st.median(x),
                pf=sum(w) / -sum(l) if l and sum(l) else float('inf'))


def fmt(s):
    if s['n'] < 8: return f"n {s['n']:4d}"
    return (f"n {s['n']:4d} win {100*s['win']:3.0f}% avgW {100*s['avg_w']:+5.0f}% avgL {100*s['avg_l']:+5.0f}% "
            f"EV {100*s['mean']:+5.1f}% t {s['t']:+5.2f} PF {s['pf']:4.2f} und {100*s['und']:+5.2f}%")


def by_month(T):
    m = {}
    for t in T: m.setdefault(t['d'][:7], []).append(t['ret'])
    top = sorted(m.items(), key=lambda kv: -len(kv[1]))[:5]
    return ', '.join(f"{k}:{len(v)}x{100*st.mean(v):+.0f}%" for k, v in top)


def second_pass(U, reg, vix):
    print('\n== 3. Robustness: option structure and IV assumption (DEV | TEST mean per trade) ==')
    variants = [('base 21d .60d hold10 vrp1.15', OC()), ('vrp 1.00 (IV = realised)', OC(vrp=1.0)),
                ('42-session expiry', OC(dte=42)), ('0.75 delta (ITM)', OC(delta=0.75)), ('hold 5', OC(hold=5)),
                ('42d expiry .75 delta', OC(dte=42, delta=0.75)), ('stop -50% target +100%', OC(stop=0.5, target=1.0))]
    names = [n for n in SIGNALS if not n.startswith('_')]
    for nm in names:
        print(nm[:70])
        for lab, oc in variants:
            a = stats(run(U, reg, vix, nm, oc, end=SPLIT)); b = stats(run(U, reg, vix, nm, oc, start=SPLIT))
            fa = f"{100*a['mean']:+6.1f}% t{a['t']:+5.1f} n{a['n']:4d}" if a['n'] >= 8 else f"n{a['n']}"
            fb = f"{100*b['mean']:+6.1f}% t{b['t']:+5.1f} n{b['n']:4d}" if b['n'] >= 8 else f"n{b['n']}"
            print(f"   {lab:30s} DEV {fa} | TEST {fb}")
    print('\n== 4. Filters on every call signal (base option) ==')
    for nm in names:
        for fl in FILTERS:
            if fl == 'none': continue
            a = stats(run(U, reg, vix, nm, OC(), flt=fl, end=SPLIT)); b = stats(run(U, reg, vix, nm, OC(), flt=fl, start=SPLIT))
            if a['n'] >= 8 and b['n'] >= 8:
                print(f"{nm[:34]:34s} | {fl[:34]:34s} DEV {100*a['mean']:+6.1f}% t{a['t']:+5.1f} n{a['n']:4d} | TEST {100*b['mean']:+6.1f}% t{b['t']:+5.1f} n{b['n']:4d}")
    print('\n== 5. Concentration: months with the most trades (TEST) ==')
    for nm in ('C6 capitulation bounce: RSI2<5, close >3 ATR below 20SMA, VIX>25 -> CALL', 'C7 breakdown reversal: close < prior 20d low on vol >1.5x -> CALL (mean reversion)'):
        T = run(U, reg, vix, nm, OC(), start=SPLIT); print(f"{nm[:40]}: {by_month(T)}")
        T2 = [t for t in T if not t['d'].startswith('2025-04')]; print(f"   without 2025-04: {fmt(stats(T2))}")


def third_pass(U, reg, vix):
    print('== 6. Regime rule fixed in advance: SPY 200-day SMA rising (vs 20 sessions ago) ==')
    yrs = {}
    for d, R in reg.items(): yrs.setdefault(d[:4], []).append(R['spy_trend'])
    print('share of sessions with SPY 200d rising by year:', {y: f"{100*sum(1 for x in v if x)/len(v):.0f}%" for y, v in sorted(yrs.items())})
    for nm in [n for n in SIGNALS if n.startswith('C')]:
        for fl in ('SPY 200d rising', 'SPY 200d rising & VIX >= 20'):
            for lab, oc in (('base', OC()), ('42d .75d', OC(dte=42, delta=0.75))):
                a = stats(run(U, reg, vix, nm, oc, flt=fl, end=SPLIT)); b = stats(run(U, reg, vix, nm, oc, flt=fl, start=SPLIT))
                fa = f"{100*a['mean']:+6.1f}% win{100*a['win']:3.0f}% t{a['t']:+5.1f} n{a['n']:4d}" if a['n'] >= 8 else f"n{a['n']}"
                fb = f"{100*b['mean']:+6.1f}% win{100*b['win']:3.0f}% t{b['t']:+5.1f} n{b['n']:4d}" if b['n'] >= 8 else f"n{b['n']}"
                print(f"{nm[:34]:34s} | {fl:27s} {lab:8s} DEV {fa} | TEST {fb}")


CORE = ['C1 uptrend pullback: >200 & >50, RSI2<10 -> CALL',
        'C7 breakdown reversal: close < prior 20d low on vol >1.5x -> CALL (mean reversion)',
        'C8 deep oversold in uptrend: >200, RSI2<5, 3 down days -> CALL']
CORE_OC = OC(dte=42, delta=0.75)
CORE_FLT = 'SPY 200d rising & VIX >= 20'


def episodes(reg):
    """contiguous runs of sessions where the regime filter is on (gaps of <= 5 sessions merged)."""
    ds = sorted(reg); on = [d for d in ds if FILTERS[CORE_FLT](reg[d], 1)]; ep = {}; k = 0; last = None
    idx = {d: i for i, d in enumerate(ds)}
    for d in on:
        if last is None or idx[d] - idx[last] > 5: k += 1
        ep[d] = k; last = d
    return ep


def fourth_pass(U, reg, vix):
    ep = episodes(reg)
    T = []
    for nm in CORE:
        for t in run(U, reg, vix, nm, CORE_OC, flt=CORE_FLT): t['sig'] = nm[:2]; T.append(t)
    # one trade per symbol per day across signals
    seen = set(); TT = []
    for t in sorted(T, key=lambda t: (t['d'], t['sym'])):
        if (t['sym'], t['d']) in seen: continue
        seen.add((t['sym'], t['d'])); TT.append(t)
    print(f'== 7. FEAR-DIP (C1|C7|C8, SPY 200d rising & VIX >= 20, 42-session 0.75-delta call, 10-session hold) ==')
    print('all trades:', fmt(stats(TT)))
    by = {}
    for t in TT: by.setdefault(ep.get(t['d']), []).append(t)
    print(f'{len(by)} episodes:')
    em = []
    for k in sorted(by, key=lambda x: by[x][0]['d']):
        x = by[k]; m = st.mean(t['ret'] for t in x); em.append(m)
        print(f"  ep {k:2d} {x[0]['d']} .. {x[-1]['d']}  trades {len(x):3d}  win {100*sum(t['ret']>0 for t in x)/len(x):3.0f}%  mean {100*m:+6.1f}%  stock move {100*st.mean(t['und'] for t in x):+5.2f}%")
    print(f"episode-level: {sum(m > 0 for m in em)}/{len(em)} episodes positive, mean of episode means {100*st.mean(em):+.1f}%, median {100*st.median(em):+.1f}%")
    # portfolio: each trade costs 5% of equity in premium, max 6 open, daily ordering by signal day
    for frac, mx in ((0.05, 6), (0.03, 10), (0.10, 4)):
        eq = 1.0; peak = 1.0; mdd = 0; openp = []; yr = {}
        for t in TT:
            openp = [o for o in openp if o[0] > t['d']]
            if len(openp) >= mx: continue
            stake = eq * frac; pnl = stake * t['ret']; eq += pnl
            S_ = U[t['sym']]; i = S_['idx'][t['d']]; exit_d = S_['d'][min(i + 1 + CORE_OC.hold, len(S_['d']) - 1)]
            openp.append((exit_d,)); peak = max(peak, eq); mdd = max(mdd, 1 - eq / peak)
            yr[t['d'][:4]] = yr.get(t['d'][:4], 0) + pnl
        print(f"portfolio {int(frac*100)}% premium per trade, max {mx} open: x{eq:.2f} total, max drawdown {100*mdd:.0f}%, P&L by year (fraction of start): " + ', '.join(f'{y} {v:+.2f}' for y, v in sorted(yr.items())))
    json.dump(dict(trades=len(TT), stats=stats(TT), episodes=len(by), episode_means=em,
                   per_signal={nm[:2]: stats([t for t in TT if t['sig'] == nm[:2]]) for nm in CORE}),
              open(os.path.join(HERE, 'results', 'fear_dip_stats.json'), 'w'), indent=1, default=float)


def main():
    raw, vix = load(); U, reg = build(raw, vix); prep(U)
    if '--pass4' in sys.argv: fourth_pass(U, reg, vix); return
    if '--pass2' in sys.argv: second_pass(U, reg, vix); return
    if '--pass3' in sys.argv: third_pass(U, reg, vix); return
    print('Earnings proxy check:'); [print('  ' + x) for x in check_earnings(U)]
    print(f"\nUniverse {len(U)} symbols, {U['SPY']['d'][200]} .. {U['SPY']['d'][-1]}. DEV < {SPLIT} <= TEST. Option: 21-session expiry, 0.60 delta, hold 10 sessions, no stop/target, earnings in hold skipped.\n")
    oc = OC()
    print('== 1. Every signal, no filter: DEV | TEST ==')
    for nm in SIGNALS:
        a = stats(run(U, reg, vix, nm, oc, end=SPLIT)); b = stats(run(U, reg, vix, nm, oc, start=SPLIT))
        print(f'{nm[:62]:62s}\n   DEV  {fmt(a)}\n   TEST {fmt(b)}')
    print('\n== 2. Baseline: random-ish entries (every 10th session, call / put) ==')
    for cp in (1, -1):
        SIGNALS['_base'] = (lambda cp: (lambda S, i, R: cp if i % 10 == 0 else 0))(cp)
        print(f"{'calls' if cp > 0 else 'puts':6s} DEV  {fmt(stats(run(U, reg, vix, '_base', oc, end=SPLIT)))}")
        print(f"{'':6s} TEST {fmt(stats(run(U, reg, vix, '_base', oc, start=SPLIT)))}")
    del SIGNALS['_base']


if __name__ == '__main__':
    main()
