#!/usr/bin/env python3
"""Rough 2018-2021 estimates for PULLBACK and RELVAL (governor 2026-11-19: "can you make estimates about pull back and relval").
Research only. Neither can be simulated before 2022 (they need 5-minute bars). Method: each system's monthly account result inside the
live book 2022-2026 (bt_trades.json) is regressed on market conditions computable from DAILY bars: QQQ realized volatility (20-day stdev
of daily returns, monthly average), QQQ monthly return, and the average absolute sector-minus-QQQ daily move (dispersion, RELVAL's raw
material). The fit is applied to 2018-2021 months. Leave-one-year-out error shows how much to trust it.
    python3 -I tools/backtest/pb_rv_estimate.py BT_TRADES.json > tools/backtest/results/pb_rv_estimate_2026-11-19.txt"""
import gzip, json, statistics as st, sys
from collections import defaultdict
import numpy as np
T = json.load(open(sys.argv[1])); raw = json.load(gzip.open('tools/backtest/data/rh_daily_2017_2026.json.gz'))['data']['results']
D = {r['symbol']: [(b['begins_at'][:10], float(b['open_price']), float(b['close_price'])) for b in r['bars'] if not b.get('interpolated')] for r in raw}
q = D['QQQ']; qc = {d: c for d, o, c in q}; qo = {d: o for d, o, c in q}; days = [d for d, _, _ in q]
ret = {days[i]: qc[days[i]] / qc[days[i - 1]] - 1 for i in range(1, len(days))}
SECT = ['SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; sec = {s: {d: (o, c) for d, o, c in D[s]} for s in SECT}
feat = defaultdict(lambda: dict(vol=[], disp=[]))
for i in range(21, len(days)):
    d = days[i]; m = d[:7]
    feat[m]['vol'].append(st.pstdev([ret[days[j]] for j in range(i - 19, i + 1)]) * 100)
    feat[m]['disp'].append(np.mean([abs((sec[s][d][1] / sec[s][d][0] - 1) - (qc[d] / qo[d] - 1)) * 100 for s in SECT if d in sec[s]]))
mret = {}
for m in feat:
    dd = [d for d in days if d[:7] == m]; i0 = days.index(dd[0])
    mret[m] = (qc[dd[-1]] / qc[days[i0 - 1]] - 1) * 100 if i0 else 0
X = {m: [np.mean(feat[m]['vol']), mret[m], np.mean(feat[m]['disp'])] for m in feat}
months_live = sorted(m for m in X if '2022-01' <= m <= '2026-10'); months_old = sorted(m for m in X if '2018-01' <= m <= '2021-12')
print(__doc__.split('\n')[0])
for sysn in ('PULLBACK', 'RELVAL'):
    y = defaultdict(float)
    for t in T:
        if t['system'] == sysn: y[t['day'][:7]] = (1 + y[t['day'][:7]] / 100) * (1 + t['acct_pct'] / 100) * 100 - 100
    A = np.array([[1] + X[m] for m in months_live]); Y = np.array([y.get(m, 0.0) for m in months_live])
    b, *_ = np.linalg.lstsq(A, Y, rcond=None); pred = A @ b
    r2 = 1 - ((Y - pred) ** 2).sum() / ((Y - Y.mean()) ** 2).sum()
    # leave-one-year-out: predict each year's total from the other four
    errs = []
    for yy in ('2022', '2023', '2024', '2025', '2026'):
        tr = [i for i, m in enumerate(months_live) if m[:4] != yy]; te = [i for i, m in enumerate(months_live) if m[:4] == yy]
        bb, *_ = np.linalg.lstsq(A[tr], Y[tr], rcond=None)
        p = np.prod(1 + (A[te] @ bb) / 100) - 1; a = np.prod(1 + Y[te] / 100) - 1; errs.append((yy, a * 100, p * 100))
    print(f"\n{sysn}: monthly fit on 2022-26, R^2 {r2:.2f} (share of month-to-month variation explained); coefficients const {b[0]:+.2f}, vol {b[1]:+.2f}, QQQ month {b[2]:+.3f}, dispersion {b[3]:+.2f}")
    print("   leave-one-year-out check (actual vs predicted from the other years): " + ', '.join(f"{yy} {a:+.1f} vs {p:+.1f}" for yy, a, p in errs))
    rmse = float(np.sqrt(np.mean([(a - p) ** 2 for _, a, p in errs])))
    flat = np.prod(1 + Y / 100) ** (12 / len(Y)) * 100 - 100
    print(f"   typical yearly error {rmse:.1f} points; plain average year 2022-26 {flat:+.1f}%")
    Ao = np.array([[1] + X[m] for m in months_old]); po = Ao @ b
    for yy in ('2018', '2019', '2020', '2021'):
        p = np.prod([1 + po[i] / 100 for i, m in enumerate(months_old) if m[:4] == yy]) * 100 - 100
        print(f"   {yy}: estimate {p:+6.1f}%  (range {p - rmse:+.1f} to {p + rmse:+.1f}); QQQ vol {np.mean([X[m][0] for m in months_old if m[:4] == yy]):.2f}%, dispersion {np.mean([X[m][2] for m in months_old if m[:4] == yy]):.2f}%")
print("\n   reference 2022-26 conditions: QQQ vol " + ', '.join(f"{yy} {np.mean([X[m][0] for m in months_live if m[:4] == yy]):.2f}%" for yy in ('2022', '2023', '2024', '2025', '2026')) +
      "; dispersion " + ', '.join(f"{yy} {np.mean([X[m][2] for m in months_live if m[:4] == yy]):.2f}%" for yy in ('2022', '2023', '2024', '2025', '2026')))
