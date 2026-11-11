#!/usr/bin/env python3
"""0DTE options backtest: the live FADE signal (RULEBOOK B2) on SPY / QQQ, expressed as a long 0DTE call or put.

    python3 tools/odte/odte_backtest.py            # full grid -> stdout
    python3 tools/odte/odte_backtest.py --trades   # base case trade list

Data: real Robinhood 5-minute bars for SPY/QQQ (tools/backtest/data/bt_5m + live_5m), Robinhood VIX daily (data/vix_daily.csv).
Robinhood keeps NO intraday history for expired option contracts (checked 2026-11-11: every bar of an expired XSP/SPY contract
comes back interpolated at one flat price). So option prices are MODELLED: Black-Scholes, calendar time to the 16:00 expiry,
trading time (252 x 390 min) to the 16:00 expiry, IV = VIX open / 100 x iv_mult x (1 - iv_decay x bar/78), x 1.2 for QQQ.
Calibration point 2026-11-11 15:11 ET: SPY 760.24, 760C 0.64/0.65 -> about 0.30 x VIX in trading time that late. iv_mult and
iv_decay are swept; tools/odte/recorder.py collects live quotes to pin them.

Signal (B2, same as the live FADE): box = 9:30-10:00 high/low; first 5-min close outside the box by the 10:10 bar; within 12 bars a
bar trades back to the broken edge (0.10%) and closes back inside -> buy the opposite direction at the next bar open.
Runaway skip 0.85%. Stop = the failed breakout's extreme (underlying). R = entry - stop distance on the underlying.

Option: strike = ATM (nearest $1) or 1 strike OTM. Fill = model mid + half-spread + fees. Exit priced at model mid - half-spread - fees.
Exits (on the underlying, checked on 5-min bars): stop; target at T x R; optional early cut (3rd bar close <= -0.5R);
optional option-premium target; time exit.
Account: a separate bucket, $500 start, compounding. contracts = floor(min(bucket x risk% / est_loss_per_contract, bucket x max_prem% / premium)).
"""
import csv, gzip, json, math, os, statistics as st, sys
from dataclasses import dataclass, replace

HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.join(HERE, '..', 'backtest', 'data')
NO_TRADE = {'2026-11-27', '2026-12-24'}
STOCKS = ('NVDA', 'AAPL', 'MSFT', 'AMZN', 'META', 'TSLA')     # Robinhood daily-expiry equity options (GOOGL, AVGO: no bar data)
_RV = {}


def rv_ratio(bars, sym, d, n=20):
    """IV ratio vs SPY for a stock = its realised 5-min vol / SPY's over the prior n sessions (known before the day)."""
    key = (sym, d)
    if key in _RV: return _RV[key]
    def rv(s):
        days = [x for x in sorted(bars[s]) if x < d][-n:]
        r = [math.log(b[i][3] / b[i - 1][3]) for x in days for b in [bars[s][x]] for i in range(1, len(b))]
        return st.pstdev(r) if len(r) > 50 else None
    a, b = rv(sym), rv('SPY')
    _RV[key] = a / b if a and b else None
    return _RV[key]


def load_bars():
    raw = json.load(gzip.open(os.path.join(BT, 'bt_5m.json.gz')))
    live = json.load(gzip.open(os.path.join(BT, 'live_5m.json.gz')))
    out = {}
    for s in ('SPY', 'QQQ', 'IWM') + STOCKS:
        days = dict(raw.get(s, {})); days.update(live.get(s, {}))
        out[s] = {d: [tuple(r[1:6]) for r in bars] for d, bars in days.items() if len(bars) >= 78}
    return out


def load_vix():
    with open(os.path.join(HERE, 'data', 'vix_daily.csv')) as f:
        return {r['date']: (float(r['open']), float(r['close'])) for r in csv.DictReader(f)}


# ---------- Black-Scholes ----------
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, sig, cp):
    """cp=+1 call, -1 put. T in years (calendar). r = 0 (intraday)."""
    if T <= 0 or sig <= 0: return max(0.0, cp * (S - K))
    v = sig * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    if cp > 0: return S * ncdf(d1) - K * ncdf(d2)
    return K * ncdf(-d2) - S * ncdf(-d1)


def t_left(k_end):
    """years of TRADING time from 9:30 + 5*k_end min to the 16:00 expiry (252 sessions x 390 min). VIX is an annualised
    trading-time vol, so an ATM 0DTE at 10:00 with VIX 20 on SPY 700 prices about $3.4, in line with real quotes."""
    mins = 390 - 5 * k_end
    return max(mins, 0) / (252 * 390)


def iv_at(c, base, k):
    """IV falls through the session: mult(k) = iv_mult x (1 - iv_decay x k/78). Calibration 2026-11-11 15:11 ET (k = 68):
    SPY 760C, 49 min left, mid 0.645 at S 760.24 -> trading-time IV about 0.30 x VIX, against about 0.9 x VIX at the open."""
    return base * c.iv_mult * (1 - c.iv_decay * k / 78)


# ---------- signal ----------
def fade_signal(b, prev_close, brk_last=8, wait=12, tol=0.10, runaway=0.85, K=78):
    """Returns (entry_bar k, direction, stop_level), 'watching' (setup still open at K completed bars) or None.
    b = bars 0..K-1 completed, (o,h,l,c,v)."""
    if K < 7: return 'watching'
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6])
    for j in range(6, brk_last + 1):
        if j >= K: return 'watching'
        c = b[j][3]
        side = 1 if c > H else -1 if c < L else 0
        if not side: continue
        for i in range(j + 1, min(j + 1 + wait, 77)):
            if i >= K: return 'watching'
            o, h, l, cc, v = b[i]
            touched = (l <= H * (1 + tol / 100)) if side > 0 else (h >= L * (1 - tol / 100))
            if not touched: continue
            back_in = cc < H if side > 0 else cc > L
            if not back_in: return None
            if prev_close and runaway is not None:
                move = (cc / prev_close - 1) * 100 * side
                if move >= runaway: return None
            ext = max(x[1] for x in b[j:i + 1]) if side > 0 else min(x[2] for x in b[j:i + 1])
            return i + 1, -side, ext
        return None
    return None


def orb_signal(b, m, or_bars=6, last_k=24, need_mkt=True):
    """TREND (momentum) signal: the first 5-min close outside the 9:30-10:00 range, at or after 10:00 and before bar last_k
    (24 = 11:30), in the direction the market (QQQ, m) agrees with: QQQ's close on that bar above its 9:30 open for a call,
    below for a put. Entry next bar open. Stop = the range midpoint. Returns (k, dir, stop) or None."""
    H = max(x[1] for x in b[:or_bars]); L = min(x[2] for x in b[:or_bars]); mid = (H + L) / 2
    for j in range(or_bars, last_k):
        c = b[j][3]
        side = 1 if c > H else -1 if c < L else 0
        if not side: continue
        if need_mkt and m is not None and (m[j][3] - m[0][0]) * side <= 0: return None
        return j + 1, side, mid
    return None


@dataclass(frozen=True)
class Cfg:
    syms: tuple = ('SPY', 'QQQ')
    iv_mult: float = 0.9
    iv_decay: float = 0.5
    otm: int = 0                 # strikes OTM ($1 steps)
    tgt_R: float = 2.0           # underlying target in R (None = none)
    early_cut: bool = True
    prem_tgt: float = None       # sell all at +X (fraction) on the premium, e.g. 1.0 = +100%
    time_exit: int = 48          # bar index whose open is the time exit (48 = 13:30)
    half_spread: float = 0.01    # $ per share, each side
    fee: float = 0.0004          # $ per share each side (~$0.04/contract regulatory)
    risk: float = 0.10           # bucket fraction risked to the stop
    max_prem: float = 0.60       # max bucket fraction spent on premium
    start: float = 500.0
    stock_iv_prem: float = 1.0  # stock IV = realised-vol ratio x this x SPY's IV (0DTE stock IV usually sits above realised)
    stock_hs_pct: float = 0.02  # stock half-spread: max(half_spread, 2% of premium); 0.05 ticks above $3
    gap_skip: float = 3.0       # skip a stock on a day it gaps more than this % (earnings proxy)
    bars_ref: object = None
    signal: str = 'fade'        # 'fade' | 'orb' (trend breakout with the market)
    hold_bars: int = None       # time exit this many bars after entry (24 = 2 hours), capped by time_exit
    need_mkt: bool = True
    vix_max: float = None
    vix_min: float = None
    one_pos: bool = True        # False: every signal is taken (per-trade edge study)
    iv_ratio: tuple = (('SPY', 1.0), ('QQQ', 1.2), ('IWM', 1.3))   # IV relative to VIX (VXN, RVX run above VIX)


def sim_trade(b, d, sym, vix, c, sig):
    k, dirn, stop = sig
    if k >= c.time_exit: return None
    if c.signal == 'orb' and c.early_cut: c = replace(c, early_cut=False)
    S0 = b[k][0]
    R = abs(S0 - stop)
    if R <= 0: return None
    if dirn > 0 and stop >= S0 or dirn < 0 and stop <= S0: return None
    if sym in STOCKS:
        ratio = rv_ratio(c.bars_ref, sym, d) if c.bars_ref else None
        if not ratio: return None
        ratio *= c.stock_iv_prem
    else: ratio = dict(c.iv_ratio)[sym]
    base = vix[d][0] / 100 * ratio
    sigma = iv_at(c, base, k)
    K = round(S0) + dirn * c.otm
    cp = dirn
    T0 = t_left(k)
    mid0 = bs(S0, K, T0, sigma, cp)
    hs = max(c.half_spread, c.stock_hs_pct * mid0) if sym in STOCKS else c.half_spread
    fill = mid0 + hs + c.fee
    stop_val = bs(stop, K, t_left(k + 1), iv_at(c, base, k + 1), cp)              # rough loss estimate for sizing
    est_loss = max(fill - (stop_val - hs - c.fee), 0.05)
    tgt = S0 + dirn * c.tgt_R * R if c.tgt_R else None
    xk, xS, why = None, None, None
    tx = min(c.time_exit, k + c.hold_bars) if c.hold_bars else c.time_exit
    for i in range(k, 78):
        o, h, l, cl, v = b[i]
        if i >= tx:
            xk, xS, why = i, o, 'time'; break
        adverse = l if dirn > 0 else h
        favor = h if dirn > 0 else l
        if (adverse <= stop) if dirn > 0 else (adverse >= stop):
            px = o if ((o <= stop) if dirn > 0 else (o >= stop)) else stop
            xk, xS, why = i + 1, px, 'stop'; break
        if tgt is not None and ((favor >= tgt) if dirn > 0 else (favor <= tgt)):
            xk, xS, why = i + 1, tgt, 'target'; break
        if c.prem_tgt is not None:
            pv = bs(favor, K, t_left(i + 1), iv_at(c, base, i + 1), cp)
            if pv >= fill * (1 + c.prem_tgt):
                # price the exit at the premium target level
                xk, xS, why = i + 1, None, 'prem'; xval = fill * (1 + c.prem_tgt); break
        if c.early_cut and i == k + 2:
            if (cl - S0) * dirn <= -0.5 * R:
                xk, xS, why = i + 1, cl, 'early_cut'; break
    if xk is None: xk, xS, why = 77, b[77][3], 'eod'
    if why == 'prem': exit_mid = xval
    else: exit_mid = bs(xS, K, t_left(xk), iv_at(c, base, xk), cp)
    exit_px = max(exit_mid - (max(c.half_spread, c.stock_hs_pct * exit_mid) if sym in STOCKS else c.half_spread) - c.fee, 0.0)
    return dict(day=d, sym=sym, dir='C' if dirn > 0 else 'P', k=k, S0=S0, K=K, R_pct=R / S0 * 100, iv=sigma,
                fill=fill, exit=exit_px, why=why, xk=xk, ret=exit_px / fill - 1, est_loss=est_loss,
                und_R=(xS - S0) * dirn / R if xS is not None else None)


def run(c, bars, vix, verbose=False):
    if c.bars_ref is None: c = replace(c, bars_ref=bars)
    days = sorted(set(bars['SPY']) & set(vix))
    days = [d for d in days if d not in NO_TRADE]
    eq = c.start; peak = eq; mdd = 0; trades = []; skipped_size = 0; signals = 0; daily = {}
    for n, d in enumerate(days):
        if n == 0: continue
        pd_ = days[n - 1]
        cands = []
        for s in c.syms:
            if d not in bars[s] or pd_ not in bars[s]: continue
            b = bars[s][d]; prev = bars[s][pd_][-1][3]
            if s in STOCKS and abs(b[0][0] / prev - 1) * 100 > c.gap_skip: continue
            if c.vix_max and vix[d][0] > c.vix_max or c.vix_min and vix[d][0] < c.vix_min: continue
            sig = fade_signal(b, prev) if c.signal == 'fade' else orb_signal(b, bars['QQQ'].get(d), need_mkt=c.need_mkt)
            if sig and sig != 'watching': cands.append((sig[0], s, sig))
        cands.sort()
        busy_until = -1; e0 = eq
        for k, s, sig in cands:
            if c.one_pos and k <= busy_until: continue       # one position at a time
            t = sim_trade(bars[s][d], d, s, vix, c, sig)
            if not t: continue
            signals += 1
            per = t['fill'] * 100
            n_risk = math.floor(eq * c.risk / (t['est_loss'] * 100))
            n_cash = math.floor(eq * c.max_prem / per)
            q = min(n_risk, n_cash)
            if q < 1:
                skipped_size += 1; t['qty'] = 0; t['usd'] = 0.0; trades.append(t); continue
            pnl = q * (t['exit'] - t['fill']) * 100
            eq += pnl; t['qty'] = q; t['usd'] = pnl; t['eq'] = eq
            trades.append(t); busy_until = t['xk']
            peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
        daily[d] = (eq / e0 - 1) * 100
    taken = [t for t in trades if t['qty'] > 0]
    return dict(days=days[1:], trades=trades, taken=taken, eq=eq, mdd=mdd, skipped=skipped_size, daily=daily)


def summ(c, r, label):
    tk = r['taken']; rets = [t['ret'] for t in r['trades']]
    if not rets: return f'{label:44s} no trades'
    wins = sum(x > 0 for x in rets)
    gw = sum(x for x in rets if x > 0); gl = -sum(x for x in rets if x < 0)
    pf = gw / gl if gl else float('inf')
    dl = list(r['daily'].values()); h = len(dl) // 2
    return (f"{label:44s} sig {len(rets):3d} taken {len(tk):3d} skip {r['skipped']:2d} | win {100*wins/len(rets):3.0f}% "
            f"avg {100*st.mean(rets):+6.1f}% med {100*st.median(rets):+6.1f}% PF {pf:4.2f} | $500->{r['eq']:7.0f} "
            f"DD {r['mdd']:4.1f}% H1 {st.mean(dl[:h]):+.2f} H2 {st.mean(dl[h:]):+.2f} %/day")


def edge(c, bars, vix):
    """Per-trade option return, independent of the bucket: every signal taken at 1 contract."""
    r = run(replace(c, risk=1.0, max_prem=1.0, start=1e7, one_pos=False), bars, vix)
    x = [t['ret'] for t in r['trades']]
    if len(x) < 3: return 'n<3'
    m = st.mean(x); se = st.pstdev(x) / math.sqrt(len(x))
    h = len(x) // 2
    return f"n {len(x):2d} mean {100*m:+5.1f}% t {m/se:+.2f} halves {100*st.mean(x[:h]):+5.1f}% / {100*st.mean(x[h:]):+5.1f}% worst {100*min(x):+4.0f}%"


def main():
    bars = load_bars(); vix = load_vix()
    if '--edge' in sys.argv:
        print('Per-trade option return, 1 contract every signal (no bucket). Modelled prices.\n')
        for syms in (('SPY',), ('QQQ',), ('IWM',), ('QQQ', 'IWM'), ('SPY', 'QQQ', 'IWM')) + tuple((x,) for x in STOCKS) + (STOCKS, ('QQQ',) + STOCKS):
            for lab, kw in [('base', {}), ('iv x1.05', dict(iv_mult=1.05)), ('iv x1.2', dict(iv_mult=1.2)),
                            ('hs 0.03', dict(half_spread=0.03)), ('1 OTM', dict(otm=1)), ('target 1.5R', dict(tgt_R=1.5)),
                            ('exit 12:00', dict(time_exit=30)), ('stock IV x1.3', dict(stock_iv_prem=1.3)),
                            ('stock hs 4%', dict(stock_hs_pct=0.04))]:
                print(f"{'+'.join(syms):12s} {lab:12s} {edge(replace(Cfg(syms=syms), **kw), bars, vix)}")
            print()
        return
    base = Cfg()
    if '--trades' in sys.argv:
        r = run(base, bars, vix)
        for t in r['trades']:
            print(f"{t['day']} {t['sym']} {t['dir']} k{t['k']:2d} S {t['S0']:.2f} K {t['K']} R {t['R_pct']:.2f}% iv {t['iv']:.2f} "
                  f"fill {t['fill']:.2f} exit {t['exit']:.2f} {t['why']:9s} ret {100*t['ret']:+6.1f}% qty {t['qty']} usd {t['usd']:+7.0f} "
                  f"eq {t.get('eq', 0):7.0f}")
        print(summ(base, r, 'base')); return
    days = sorted(set(bars['SPY']) & set(bars['QQQ']))
    print(f"Sessions {days[0]} .. {days[-1]} ({len(days)}). Option prices are modelled (see docstring).\n")
    print('== base: FADE SPY+QQQ, ATM, 2R target, early cut, 13:30 exit, IV x0.9 decay 0.5, spread 0.01, risk 10%, max premium 60% ==')
    print(summ(base, run(base, bars, vix), 'base'))
    print('\n== IV multiplier (the main unknown) ==')
    for m in (0.6, 0.75, 1.05, 1.2):
        cc = replace(base, iv_mult=m); print(summ(cc, run(cc, bars, vix), f'iv x{m}'))
    for dk in (0.0, 0.3, 0.7):
        cc = replace(base, iv_decay=dk); print(summ(cc, run(cc, bars, vix), f'iv decay {dk}'))
    print('\n== costs ==')
    for hs in (0.02, 0.03, 0.05):
        cc = replace(base, half_spread=hs); print(summ(cc, run(cc, bars, vix), f'half-spread ${hs}'))
    print('\n== tickers ==')
    for s in (('SPY',), ('QQQ',), ('IWM',), ('QQQ', 'IWM'), ('SPY', 'QQQ', 'IWM')):
        cc = replace(base, syms=s); print(summ(cc, run(cc, bars, vix), '+'.join(s)))
    print('\n== strike ==')
    for o in (1, 2):
        cc = replace(base, otm=o); print(summ(cc, run(cc, bars, vix), f'{o} strike OTM'))
    print('\n== exits ==')
    for lab, kw in [('target 1R', dict(tgt_R=1.0)), ('target 1.5R', dict(tgt_R=1.5)), ('target 3R', dict(tgt_R=3.0)),
                    ('no target (stop/time)', dict(tgt_R=None)), ('no early cut', dict(early_cut=False)),
                    ('premium +50%', dict(prem_tgt=0.5, tgt_R=None)), ('premium +100%', dict(prem_tgt=1.0, tgt_R=None)),
                    ('time exit 12:00', dict(time_exit=30)), ('time exit 15:00', dict(time_exit=66))]:
        cc = replace(base, **kw); print(summ(cc, run(cc, bars, vix), lab))
    print('\n== sizing ==')
    for rk, mp in ((0.05, 0.6), (0.15, 0.6), (0.20, 0.8), (0.10, 1.0)):
        cc = replace(base, risk=rk, max_prem=mp); print(summ(cc, run(cc, bars, vix), f'risk {int(rk*100)}% max prem {int(mp*100)}%'))


if __name__ == '__main__':
    main()
