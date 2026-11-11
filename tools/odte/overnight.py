#!/usr/bin/env python3
"""Day-before entries (governor 2026-11-11: "put the order in the night before or day before, not buy same day").

    python3 tools/odte/overnight.py > tools/odte/results/overnight.txt

Signals use only day D information (known at D's 15:45): D's return, where D closed in its range, VIX change on D.
  A  'close'  : buy at D 15:45 the contract expiring D+1 (1DTE), hold overnight, sell on D+1 at the exit bar.
  B  'open'   : order placed the evening of D, fills at the D+1 9:30 open, contract expiring D+1 (0DTE), sell at the exit bar.
Pricing as odte_backtest.py: Black-Scholes in trading time, IV = VIX x iv_mult x ratio (stocks: trailing realised-vol ratio).
Overnight counts as `on_w` of a session of variance (0.4 default, swept). Costs as odte_backtest.py.
Prices are MODELLED (Robinhood has no intraday history for expired contracts); the underlying move columns are real.
"""
import math, os, statistics as st, sys
from dataclasses import dataclass, replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import odte_backtest as ob

YR = 252


@dataclass(frozen=True)
class C:
    mode: str = 'close'          # 'close' (A) | 'open' (B)
    exit_k: int = 6              # D+1 bar whose open is the exit (6 = 10:00, 12 = 10:30, 30 = 12:00, 72 = 15:30)
    iv_mult: float = 0.9
    on_w: float = 0.4
    hs: float = 0.01
    stock_hs_pct: float = 0.02
    fee: float = 0.0004
    stop_pct: float = None       # underlying stop on D+1 (% from entry), None = none


def T_years(mode, k):
    """trading-time years left at D+1 bar k (k = -1 means D 15:45)."""
    return (390 - 5 * k) / 390 / YR


def price(S, K, T, sig, cp): return ob.bs(S, K, T, sig, cp)


def sigma(c, bars, vix, sym, d, k):
    if sym in ob.STOCKS:
        r = ob.rv_ratio(bars, sym, d)
        if not r: return None
    else: r = dict(ob.Cfg().iv_ratio)[sym]
    return vix[d][0] / 100 * r * c.iv_mult * (1 - 0.5 * max(k, 0) / 78)


def trade(c, bars, vix, sym, d, d1, cp):
    b0, b1 = bars[sym][d], bars[sym][d1]
    if d1 not in vix: return None
    if c.mode == 'close':
        S0 = b0[75][3]                                   # 15:45 bar close (approx. last tradeable minutes)
        sg = sigma(c, bars, vix, sym, d, 0)              # the 1DTE prices a FULL next session + overnight: no intraday decay
        if not sg: return None
        sg *= vix[d][1] / vix[d][0]                      # level from D's VIX close (known at entry), not D's open
        T0 = (15 / 390 + c.on_w + 1) / YR
        K = round(S0); mid0 = price(S0, K, T0, sg, cp)
    else:
        S0 = b1[0][0]; sg = sigma(c, bars, vix, sym, d1, 0)
        if not sg: return None
        K = round(S0); mid0 = price(S0, K, T_years('open', 0), sg, cp)
    hs = lambda m: max(c.hs, c.stock_hs_pct * m) if sym in ob.STOCKS else c.hs
    fill = mid0 + hs(mid0) + c.fee
    xk, xS = c.exit_k, b1[c.exit_k][0]
    if c.stop_pct:
        lvl = S0 * (1 - cp * c.stop_pct / 100)
        for i in range(0, c.exit_k):
            o, h, l, cl, v = b1[i]
            if (cp > 0 and l <= lvl) or (cp < 0 and h >= lvl):
                xk, xS = i + 1, (o if (cp > 0 and o <= lvl) or (cp < 0 and o >= lvl) else lvl); break
    sg1 = sigma(c, bars, vix, sym, d1, xk)
    m1 = price(xS, K, T_years(c.mode, xk), sg1, cp)
    ex = max(m1 - hs(m1) - c.fee, 0)
    return dict(ret=ex / fill - 1, und=(xS / S0 - 1) * 100 * cp, d=d, sym=sym)


SIGNALS = {
    'every day CALL': lambda f: 1,
    'every day PUT': lambda f: -1,
    'D up >1% closes top 25% -> CALL': lambda f: 1 if f['ret'] > 1 and f['loc'] > 0.75 else 0,
    'D down >1% closes bottom 25% -> PUT': lambda f: -1 if f['ret'] < -1 and f['loc'] < 0.25 else 0,
    'momentum both ways (above two)': lambda f: 1 if f['ret'] > 1 and f['loc'] > 0.75 else -1 if f['ret'] < -1 and f['loc'] < 0.25 else 0,
    'D down >1.5% -> CALL (bounce)': lambda f: 1 if f['ret'] < -1.5 else 0,
    'D up >1.5% -> PUT (fade)': lambda f: -1 if f['ret'] > 1.5 else 0,
    'VIX up >10% on D -> CALL': lambda f: 1 if f['vix_chg'] > 10 else 0,
    'VIX down >8% on D -> CALL': lambda f: 1 if f['vix_chg'] < -8 else 0,
    'VIX up >10% on D -> PUT': lambda f: -1 if f['vix_chg'] > 10 else 0,
    'QQQ trend: D up + mkt up -> CALL': lambda f: 1 if f['ret'] > 0.5 and f['mkt'] > 0.5 else 0,
}


def feats(bars, vix, sym, d, dp):
    b = bars[sym][d]; pc = bars[sym][dp][-1][3]
    H = max(x[1] for x in b); L = min(x[2] for x in b); cl = b[75][3]
    q = bars['QQQ'].get(d); qp = bars['QQQ'].get(dp)
    return dict(ret=(cl / pc - 1) * 100, loc=(cl - L) / (H - L) if H > L else 0.5,
                vix_chg=(vix[d][1] / vix[dp][1] - 1) * 100 if dp in vix and d in vix else 0,
                mkt=(q[75][3] / qp[-1][3] - 1) * 100 if q and qp else 0)


def run(c, bars, vix, syms, rule):
    days = sorted(set(bars['SPY']) & set(vix)); out = []
    for i in range(1, len(days) - 1):
        dp, d, d1 = days[i - 1], days[i], days[i + 1]
        for s in syms:
            if not all(x in bars[s] for x in (dp, d, d1)): continue
            cp = rule(feats(bars, vix, s, d, dp))
            if not cp: continue
            t = trade(c, bars, vix, s, d, d1, cp)
            if t: out.append(t)
    return out


def line(T):
    if len(T) < 5: return f'n {len(T)}'
    x = [t['ret'] for t in T]; u = [t['und'] for t in T]; m = st.mean(x); se = st.pstdev(x) / math.sqrt(len(x)); h = len(x) // 2
    return (f"n {len(x):4d} win {100*sum(v > 0 for v in x)/len(x):3.0f}% mean {100*m:+6.1f}% t {m/se:+5.2f} "
            f"halves {100*st.mean(x[:h]):+6.1f}/{100*st.mean(x[h:]):+6.1f} | underlying {st.mean(u):+.2f}% (t {st.mean(u)/(st.pstdev(u)/math.sqrt(len(u))):+.1f})")


def main():
    bars = ob.load_bars(); vix = ob.load_vix()
    groups = {'SPY': ('SPY',), 'QQQ': ('QQQ',), 'IWM': ('IWM',), '6 stocks': ob.STOCKS}
    for mode, xs in (('close', (6, 30, 72)), ('open', (6, 30, 48))):
        print(f"\n######## {'A: buy 1DTE at D close, hold overnight' if mode == 'close' else 'B: order the night before, fill at D+1 open (0DTE)'}")
        for xk in xs:
            print(f"\n== exit at D+1 {ob_t(xk)} ==")
            for rn, rule in SIGNALS.items():
                for gn, g in groups.items():
                    T = run(C(mode=mode, exit_k=xk), bars, vix, g, rule)
                    if len(T) >= 5: print(f"{rn:38s} {gn:9s} {line(T)}")
    print('\n== sensitivity on the best-looking rows: overnight weight, IV ==')


def ob_t(k): n = 570 + 5 * k; return f"{n // 60}:{n % 60:02d}"


if __name__ == '__main__':
    main()
