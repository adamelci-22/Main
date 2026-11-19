#!/usr/bin/env python3
"""Equivalence check: tools/live/relval.py (first_trigger, model_exit) against the backtest's NS.relval on the Massive 5-minute tape.
Every RELVAL trade 2022-2026 must match: same day, proxy, entry bar, exit bar and leg % (RULEBOOK D3: live code replays the backtest).
    python3 -I tools/backtest/relval_check.py > tools/backtest/results/relval_check_2026-11-19.txt"""
import os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'live'))
import fade_replace as FR, new_systems as NS
import relval as R
B = FR.B; ds = B.ds; dm = FR.dm
bt = {(t['day'], t['proxy']): t for t in B.BC.new(ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0)}
mine = {}
rel = {p: {x: ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0] for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']} for p in R.PROXIES}
for p in R.PROXIES:
    for d in dm:
        b = ds.bars[p].get(d); q = ds.bars['QQQ'].get(d)
        if not b or len(b) < 78 or not q or len(q) < 78: continue
        i = ds.idx[d]; hist = [rel[p][x] for x in ds.days[max(0, i - 20):i] if x in rel[p]]
        ft = R.first_trigger(b, q, R.rel_sd(hist), 77)
        if not ft: continue
        j, rp = ft; k = j + 1; xb, px, why = R.model_exit(b, k, rp, 77); e = b[k][0]; s = -1 if rp > 0 else 1
        mine[(d, p)] = dict(k=k, xbar=xb, pct=3 * s * (px / e - 1) * 100 - NS.COST, why=why)
keys = set(bt) | set(mine); bad = 0
for key in sorted(keys):
    a, m = bt.get(key), mine.get(key)
    if not a or not m or a['k'] != m['k'] or abs(a['pct'] - m['pct']) > 1e-6 or (a['xbar'] != m['xbar'] and not (m['why'] == 'time 15:55')):
        bad += 1
        if bad <= 15: print('MISMATCH', key, a and (a['k'], a['xbar'], round(a['pct'], 4)), m and (m['k'], m['xbar'], round(m['pct'], 4), m['why']))
print(f"backtest {len(bt)} trades, live code {len(mine)} trades, mismatches {bad}")
