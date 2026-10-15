#!/usr/bin/env python3
"""Inverse-list pullback: how much to sell at the morning high, and how to manage the rest (incl. the fade's ratchet).
    python3 tools/backtest/pb_inverse.py > tools/backtest/results_pb_inverse.txt
List A = inverse side of the five rows: SOXS, SQQQ, TZA, TECS, BTCZ.   List B = A + LABD + UVXY.
Entry = pullback.scan rules on each ticker's own chart. Take profit at the morning high (OCO, fills at the level).
Runner options for the part kept:  ema20      = sell after a close below the 20-EMA, original stop kept (current)
                                    be         = stop to breakeven, nothing else
                                    chand2/3   = breakeven, then chandelier (highest close - 2/3 x ATR14), never down (the fade's ratchet)
                                    chand2_ns  = chandelier from the ORIGINAL stop (no breakeven step)
Sell what's left by 13:30 (15:55 shown for reference). Costs 0.01% in / 0.03% out. $2,000, 3% risk capped at cash, one position, max 3/day.
"""
import itertools, math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, pb_etfs as E
from lab import get_data

A = ['SOXS', 'SQQQ', 'TZA', 'TECS', 'BTCZ']
B = A + ['LABD', 'UVXY']
PROXY = {'SOXS': 'SOXX', 'SQQQ': 'QQQ', 'TZA': 'IWM', 'TECS': 'XLK', 'BTCZ': 'IBIT', 'LABD': 'LABD', 'UVXY': 'UVXY'}


def manage(s, frac, runner, last):
    b, k, entry, stop = s['b'], s['k'], s['entry'], s['stop']
    if k > last: return None
    r = entry - stop; T = s['hod']
    gross = 0.0; rem = 1.0; hit = False; hic = entry; cost = 0.0001 * entry; xbar = last
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross += rem * (px - entry); cost += rem * 0.0003 * px; rem = 0; xbar = j; break
        if not hit and h >= T:
            px = max(T, o); gross += frac * (px - entry); cost += frac * 0.0003 * px; rem -= frac; hit = True
            if rem <= 1e-9: xbar = j; break
            if runner in ('be', 'chand2', 'chand3'): stop = max(stop, entry)
        hic = max(hic, c)
        if hit and j < last:
            if runner.startswith('chand'): stop = max(stop, hic - float(runner[5]) * m.atr(b, j))
            elif runner == 'ema20' and c < s['e20'][j]:
                px = b[j + 1][0]; gross += rem * (px - entry); cost += rem * 0.0003 * px; rem = 0; xbar = j + 1; break
    if rem > 1e-9: px = b[last][3]; gross += rem * (px - entry); cost += rem * 0.0003 * px
    pnl = gross - cost
    return dict(day=s['day'], inst=s['inst'], k=k, xbar=xbar, pnl=pnl, risk=r, entry=entry, pct=pnl / entry * 100, hit=hit)


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    def rv(D_, p, d, k):
        try:
            pri = D.prior(d, 20); base = st.mean(D.cum[p][x][k] for x in pri); return D.cum[p][d][k] / base
        except Exception: return 0.0
    m.rvol = rv
    S = {leg: E.setups_for(D, days, leg) for leg in B}
    print(f"Inverse-list pullback, {days[0]}..{days[-1]} ({len(days)} days). Setups: " + ', '.join(f"{k} {len(v)}" for k, v in S.items()))
    tn = {47: '13:30', 77: '15:55'}
    for lname, legs in (('A: SOXS SQQQ TZA TECS BTCZ', A), ('B: A + LABD + UVXY', B)):
        m.LEGS = {l: (PROXY[l], 1) for l in legs}
        rows = []
        for frac, runner, last in itertools.product((0.33, 0.5, 0.6, 0.75, 1.0), ('ema20', 'be', 'chand2', 'chand3', 'chand2_ns'), (47, 77)):
            if frac == 1.0 and runner != 'be': continue
            sig = [t for leg in legs for s in S[leg] for t in [manage(s, frac, runner, last)] if t]
            a = P.account(sig, D, days)
            d1 = st.mean(P.account([x for x in sig if x['day'] in set(H1)], D, H1)['daily'].values())
            d2 = st.mean(P.account([x for x in sig if x['day'] in set(H2)], D, H2)['daily'].values())
            rows.append(((frac, runner, last), st.mean(a['daily'].values()), a['ret'], a['mdd'], d1, d2, len(a['taken']),
                         100 * sum(x['usd'] > 0 for x in a['taken']) / max(len(a['taken']), 1)))
        lab = lambda c: f"{'all' if c[0] == 1 else f'{int(round(c[0]*100))}%'} at morning high, rest {c[1]:<9} by {tn[c[2]]}"
        print(f"\n== List {lname} ==")
        print(f"{'exit':<52}{'trd':>4}{'win%':>6}{'%/day':>8}{'ret%':>8}{'DD':>6}{'H1':>8}{'H2':>8}")
        for c, dd, ret, mdd, a1, a2, n, w in sorted(rows, key=lambda r: -r[1]):
            tag = '  <- current' if c == (0.6, 'ema20', 47) else ('  <- 60/40 + fade ratchet' if c == (0.6, 'chand2', 47) else '')
            print(f"{lab(c):<52}{n:>4}{w:>6.0f}{dd:>+8.3f}{ret:>+8.1f}{mdd:>6.1f}{a1:>+8.3f}{a2:>+8.3f}{tag}")
        print(f"   positive in both halves: {sum(r[4] > 0 and r[5] > 0 for r in rows)} of {len(rows)}")
        for i, name in enumerate(('fraction at high', 'runner', 'sell-by')):
            g = collections.defaultdict(list)
            for r in rows: g[r[0][i]].append(r)
            print(f"   avg by {name:<17}" + '  '.join(f"{(tn[k] if i == 2 else k)}: {st.mean(x[1] for x in v):+.3f}/{st.mean(x[5] for x in v):+.3f}" for k, v in g.items()))
        best = max(rows, key=lambda r: r[4])
        print(f"   WALK-FORWARD: best on H1 = {lab(best[0])} (H1 {best[4]:+.3f}) -> H2 {best[5]:+.3f}")


if __name__ == '__main__':
    main()
