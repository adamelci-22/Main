#!/usr/bin/env python3
"""Overnight leg on Robinhood DAILY bars (the only Robinhood history that reaches 2018). Research only.
Signal as live: close above the 20-close average (19 prior closes plus today's close) and IBS (close - low) / (high - low) below 0.10.
Buy at the close (the 15:55 price stands in), sell the next session's open (the 9:35 open stands in), 3x leg, minus 0.06%, 50% of cash.
One night a trade: the signal with the highest day volume against its 20-session average. Compares the v5.2.69 and v5.2.70 name sets.
    python3 -I ovn_daily.py ROBINHOOD_DAILY_DUMP.json"""
import json, sys, statistics as st
import numpy as np
d = json.load(open(sys.argv[1]))['data']['results']
B = {}
for r in d:
    B[r['symbol']] = {x['begins_at'][:10]: (float(x['open_price']), float(x['high_price']), float(x['low_price']), float(x['close_price']), float(x['volume'])) for x in r['bars']}
days = sorted(set.intersection(*[set(v) for v in B.values()]))
print('symbols', sorted(B), 'common sessions', len(days), days[0], days[-1])
COST, LEV, SIZE = 0.06, 3, 0.5


def legs(p):
    out = {}
    for i in range(20, len(days) - 1):
        t = days[i]; o, h, l, c, v = B[p][t]
        if h <= l: continue
        c20 = [B[p][days[j]][3] for j in range(i - 19, i)] + [c]
        if not (c > st.mean(c20) and (c - l) / (h - l) < 0.10): continue
        vv = [B[p][days[j]][4] for j in range(i - 20, i)]
        no = B[p][days[i + 1]][0]
        out[days[i + 1]] = (LEV * (no / c - 1) * 100 - COST, v / st.mean(vv))
    return out


L = {p: legs(p) for p in B}


def run(names, a, z):
    nights = []
    for d_ in days:
        if not (a <= d_ <= z): continue
        c = [L[p][d_] for p in names if d_ in L[p]]
        if c: nights.append((d_, max(c, key=lambda x: x[1])[0]))
    return nights


def pf(p):
    p = np.array(p, float)
    if len(p) == 0: return float('nan')
    gl = -p[p < 0].sum(); return p[p > 0].sum() / gl if gl else 9.99


def report(tag, a, z):
    print(f"\n{tag}: {a} to {z}")
    print(f"  {'names':<34}{'nights':>7}{'win':>5}{'mean':>8}{'PF':>6}  50% of cash by year: ")
    sets = [('v5.2.69 QQQ SOXX IWM XLK XLF', ['QQQ', 'SOXX', 'IWM', 'XLK', 'XLF']), ('v5.2.70 QQQ SOXX IWM XLK FXI', ['QQQ', 'SOXX', 'IWM', 'XLK', 'FXI']),
            ('drop XLF only', ['QQQ', 'SOXX', 'IWM', 'XLK']), ('add FXI only', ['QQQ', 'SOXX', 'IWM', 'XLK', 'XLF', 'FXI'])]
    for nm, ns in sets:
        n = run(ns, a, z); p = [x[1] for x in n]; yrs = {}
        for d_, g in n: yrs[d_[:4]] = yrs.get(d_[:4], 1.0) * (1 + SIZE * g / 100)
        print(f"  {nm:<34}{len(p):>7}{100 * np.mean(np.array(p) > 0):>4.0f}%{np.mean(p):>+7.2f}%{pf(p):>6.2f}  " + ' '.join(f"{y} {(v - 1) * 100:+.1f}" for y, v in sorted(yrs.items())) + f" | total {(np.prod([1 + SIZE * g / 100 for g in p]) - 1) * 100:+.1f}%")
    print('  single names alone: ' + ', '.join(f"{p} {len([1 for d_ in L[p] if a <= d_ <= z])} nights PF {pf([v[0] for d_, v in L[p].items() if a <= d_ <= z]):.2f}" for p in ['QQQ', 'SOXX', 'IWM', 'XLK', 'XLF', 'FXI']))


report('OUT OF SAMPLE (before the 2022 to 2026 selection)', '2018-01-01', '2021-12-31')
report('IN SAMPLE, same daily method (to check it against the Massive 5-minute result)', '2022-01-01', '2026-10-30')
