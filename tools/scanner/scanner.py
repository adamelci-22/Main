#!/usr/bin/env python3
"""Swing-option scanner (1-2 week holds). Run after the close. Places no orders.

    python3 tools/scanner/scanner.py                                   # full scan on the latest stored bars
    python3 tools/scanner/scanner.py --contract NVDA 170 9.40 0.48 42  # score a live contract: SYM STRIKE ASK IV SESSIONS_TO_EXPIRY

What it does (evidence: tools/scanner/SCANNER_SPEC.md, results/study*.txt):
 1. MACRO / REGIME: SPY trend (price vs 200d, 200d slope), VIX level and trend, credit (HYG), rates (TLT), sector leadership.
 2. FEAR-DIP (the only rule that held up in testing): when SPY's 200-day average is rising AND VIX >= 20, buy a ~60-day
    0.75-delta CALL on a stock that just dipped (C1 uptrend pullback, C7 high-volume breakdown, C8 3-day oversold in uptrend),
    hold 10 sessions. Backtest 2023-2026: 654 trades, 19 fear episodes (15 positive), win 60%, avg win +35%, avg loss -19%,
    +13.4% per trade (+8.5% with IV 30% richer and spreads doubled). No trades in 2022 (filter off).
 3. Earnings: skips any name reporting inside the hold (real Robinhood dates, data/earnings.csv).
 4. News veto: the session pulls Massive news for every candidate and drops names whose dip has a company-specific cause
    (CEO exit, fraud, probe, guidance cut, downgrade wave). The rule buys market-wide fear, not broken companies.
 5. Contract scoring: --contract prices a real quote against the historical distribution of the signal's 10-session moves:
    probability of profit, average win / loss, expected return per dollar.
Everything else tested (breakouts, squeezes, relative strength, earnings drift, all put signals) lost money as long options.
"""
import csv, json, math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lab as L

SECTORS = ['XLK', 'SMH', 'XLF', 'KRE', 'XLE', 'XLV', 'XBI', 'XLI', 'XLY', 'XLP', 'XLU', 'GLD', 'TLT', 'ARKK']
HOLD = 10


def pct(a, b): return (a / b - 1) * 100 if a and b else float('nan')


def regime_panel(U, reg, vix):
    spy = U['SPY']; i = len(spy['d']) - 1; d = spy['d'][i]
    vd = sorted(vix); vlast = vd[-1]; vx = vix[vlast]; v20 = sum(vix[x] for x in vd[-20:]) / 20
    s200 = spy['sma200'][i]; s200_20 = spy['sma200'][i - 20]
    rising = s200 > s200_20
    hyg = U['HYG']; tlt = U['TLT']; h = len(hyg['d']) - 1; t = len(tlt['d']) - 1
    on = rising and vx >= 20
    print(f"MACRO / REGIME  (bars through {d}, VIX close {vlast})")
    print(f"  SPY {spy['c'][i]:.2f}: {pct(spy['c'][i], s200):+.1f}% vs 200d, 200d {'RISING' if rising else 'FALLING'} ({pct(s200, s200_20):+.2f}% in 20 sessions), {pct(spy['c'][i], spy['sma50'][i]):+.1f}% vs 50d")
    print(f"  VIX {vx:.2f} (20d avg {v20:.2f}, {'falling' if vx < v20 else 'rising'}). Fear threshold 20: {'MET' if vx >= 20 else 'NOT MET'}")
    print(f"  Credit HYG {pct(hyg['c'][h], hyg['sma50'][h]):+.1f}% vs 50d ({'risk-on' if hyg['c'][h] > hyg['sma50'][h] else 'risk-off'}). "
          f"Rates TLT {pct(tlt['c'][t], tlt['sma50'][t]):+.1f}% vs 50d ({'yields falling' if tlt['c'][t] > tlt['sma50'][t] else 'yields rising'})")
    rows = []
    for s in SECTORS:
        S = U.get(s)
        if not S: continue
        k = len(S['d']) - 1; rows.append((pct(S['c'][k], S['c'][k - 21]), s, S['c'][k] > (S['sma50'][k] or 0)))
    rows.sort(reverse=True)
    print('  1-month leaders: ' + ', '.join(f"{s} {r:+.1f}%" for r, s, up in rows[:4]) + ' | laggards: ' + ', '.join(f"{s} {r:+.1f}%" for r, s, up in rows[-3:]))
    print(f"  FEAR-DIP RULE: {'ON: buy qualified dips' if on else 'OFF: no new swing calls' + (' (VIX below 20)' if rising else ' (SPY 200d falling: bear regime)')}")
    return on, rising, vx


def next_earn(sym, after):
    out = [(d, t) for d, t in L.EARN.get(sym, []) if d > after]
    return min(out) if out else None


def scan(U, reg, vix, on, rising, vx):
    stats = json.load(open(os.path.join(HERE, 'results', 'fear_dip_stats.json')))
    names = {'C1': L.CORE[0], 'C7': L.CORE[1], 'C8': L.CORE[2]}
    hits, near = [], []
    for s, S in U.items():
        if s in L.ETFS and s not in ('QQQ', 'IWM', 'SMH', 'XLK', 'XLF', 'XLE', 'XBI'): continue
        i = len(S['d']) - 1
        fired = [k for k, nm in names.items() if L.SIGNALS[nm](S, i, reg.get(S['d'][i]))]
        ne = next_earn(s, S['d'][i])
        # sessions until earnings (approx: business days)
        if ne:
            import datetime as dt
            a = dt.date.fromisoformat(S['d'][i]); b = dt.date.fromisoformat(ne[0]); bd = sum(1 for x in range((b - a).days) if (a + dt.timedelta(days=x + 1)).weekday() < 5)
        else: bd = None
        row = dict(sym=s, px=S['c'][i], d=S['d'][i], sig=fired, rsi2=S['rsi2'][i], v200=pct(S['c'][i], S['sma200'][i]), earn=ne, earn_bd=bd,
                   rv=max(S['rv20'][i] or 0, S['rv60'][i] or 0), chg5=pct(S['c'][i], S['c'][i - 5]))
        if fired: hits.append(row)
        elif S['sma200'][i] and S['c'][i] > S['sma200'][i] and S['rsi2'][i] is not None and S['rsi2'][i] < 20: near.append(row)
    import p50
    sc = p50.score_last(U, reg, vix, [r['sym'] for r in hits])
    for r in hits: r['p50'] = sc.get(r['sym'], float('nan'))
    hits.sort(key=lambda r: -(r['p50'] if r['p50'] == r['p50'] else -1))
    print(f"\nFEAR-DIP SIGNALS ON THE LAST BAR ({len(hits)}), ranked by the P50 model. TRADE THE TOP 2 that pass earnings + news."
          + ('' if on else '  [regime OFF: watchlist only, do not trade]'))
    rank = 0
    for r in hits:
        ok = not (r['earn_bd'] is not None and r['earn_bd'] <= HOLD + 1)
        rank += ok
        tag = f"#{rank} {'TOP-2' if ok and rank <= 2 else ''}" if ok else 'SKIP'
        print(f"  {tag:9s} P50 {100*r['p50']:4.0f}% (a ranking; out-of-sample calibration in results/p50_study.txt)")
        e = f"earnings {r['earn'][0]} ({r['earn_bd']} sessions){' SKIP: inside hold' if r['earn_bd'] is not None and r['earn_bd'] <= HOLD + 1 else ''}" if r['earn'] else 'no earnings inside 60 days on file'
        K, prem = plan(r['px'], r['rv'])
        print(f"  {r['sym']:5s} {r['px']:9.2f} [{'+'.join(r['sig'])}] RSI2 {r['rsi2']:4.1f}  5d {r['chg5']:+5.1f}%  vs200d {r['v200']:+5.1f}%  | {e}")
        print(f"        plan: ~60-day CALL, strike about {K:.0f} (0.75 delta), model premium about {prem:.2f} ({100*prem/r['px']:.1f}% of stock). Hold 10 sessions.")
    print(f"\nWATCHLIST: uptrend names near a dip (above 200d, RSI2 < 20), {len(near)}: " +
          ', '.join(f"{r['sym']}({r['rsi2']:.0f})" for r in sorted(near, key=lambda r: r['rsi2'])[:20]))
    st_ = stats['stats']
    print(f"\nRULE STATS (backtest 2023-2026, modelled option prices): {stats['trades']} trades, {stats['episodes']} episodes, "
          f"win {100*st_['win']:.0f}%, avg win {100*st_['avg_w']:+.0f}%, avg loss {100*st_['avg_l']:+.0f}%, EV {100*st_['mean']:+.1f}% per trade")
    for k, v in stats['per_signal'].items():
        print(f"   {k}: n {v['n']}, win {100*v['win']:.0f}%, EV {100*v['mean']:+.1f}%")
    print('\nSYSTEM (results/bigwin.txt): top 2 names per signal day by P50, 42-session 0.75-delta call, sell at the 10th session close.'
          '\n  Backtest 2023-07..2026-11: +16.4% per trade vs +11.9% for 2 random picks, 17 of 17 fear episodes positive; few-trades book'
          '\n  (10% of equity per trade, max 3 open): ~17 trades a year, x3.48, max drawdown 18%. Longer holds and trailing exits tested worse.')
    print('\nNEXT STEPS FOR THE SESSION: (1) Massive /v2/reference/news for each signal name: veto company-specific bad news.'
          '\n (2) get_option_chains + get_option_instruments for the ~55-65 DTE expiry, strike nearest the plan; get_option_quotes.'
          '\n (3) score each quote: scanner.py --contract SYM STRIKE ASK IV SESSIONS. Take EV > +5% and P(profit) > 50% only.'
          '\n (4) size: premium <= 10% of the account per trade, max 3 open. Exit at the 10th session close, or earlier on a news veto.')
    return hits


def plan(S, rv, dte=42, delta=0.75, vrp=1.15):
    sig = rv * vrp; T = dte / 252
    K = L.strike_for_delta(S, T, sig, 1, delta)
    return K, L.bs(S, K, T, sig, 1)


def contract(sym, K, ask, iv, sess):
    """Score a real quote: reprice at the 10th session across the historical FEAR-DIP 10-session move distribution."""
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    moves = []
    for nm in L.CORE:                                   # each move scaled to this contract's vol: move x (iv_now / iv_then)
        moves += [t['und'] * iv / t['iv'] for t in L.run(U, reg, vix, nm, L.CORE_OC, flt=L.CORE_FLT) if t['iv']]
    spy = U['SPY']; i = len(spy['d']) - 1; vlast = sorted(vix)[-1]
    on = spy['sma200'][i] > spy['sma200'][i - 20] and vix[vlast] >= 20
    S = U[sym]['c'][-1]
    hs = max(0.03, 0.015 * ask)
    T1 = max(sess - HOLD, 1) / 252
    rets = [(max(L.bs(S * (1 + m), K, T1, iv * 0.95, 1) - hs, 0) - ask) / ask for m in moves]
    w = [r for r in rets if r > 0]; l = [r for r in rets if r <= 0]
    be = next((m for m in sorted(moves) if L.bs(S * (1 + m), K, T1, iv * 0.95, 1) - hs >= ask), None)
    print(f"{sym} {K} call, ask {ask:.2f}, IV {iv:.2f}, {sess} sessions to expiry, spot {S:.2f} (last stored close)")
    print(f"  across {len(moves)} historical FEAR-DIP 10-session moves, scaled to this IV (IV assumed to ease 5%):")
    print(f"  P(profit) {100*len(w)/len(rets):.0f}%  avg win {100*st.mean(w) if w else 0:+.0f}%  avg loss {100*st.mean(l) if l else 0:+.0f}%  "
          f"EV {100*st.mean(rets):+.1f}% per dollar  | stock move needed to break even after 10 sessions: {100*be:+.2f}%" if be is not None else '')
    print(f"  max loss ${ask*100:.0f} per contract. Verdict: {'TAKE' if on and st.mean(rets) > 0.05 and len(w)/len(rets) > 0.5 else 'PASS'} (rule: regime ON, EV > +5%, P(profit) > 50%; regime is {'ON' if on else 'OFF'})")


def main():
    if '--contract' in sys.argv:
        a = sys.argv[sys.argv.index('--contract') + 1:]
        contract(a[0], float(a[1]), float(a[2]), float(a[3]), int(a[4])); return
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    on, rising, vx = regime_panel(U, reg, vix)
    scan(U, reg, vix, on, rising, vx)


if __name__ == '__main__':
    main()
