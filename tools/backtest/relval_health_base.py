#!/usr/bin/env python3
"""Health baseline for RELVAL (v5.2.64): the 219 five-year RELVAL trades (Massive tape 2022-01..2026-10, live setting), rolling 30-trade
windows: profit factor on account %, win rate and average trade on position %. Adds 'RELVAL' to tools/live/health_baseline.json.
    python3 -I tools/backtest/relval_health_base.py"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS
T = sorted(FR.B.BC.new(FR.B.ds, FR.B.ctx, FR.dm, NS.relval, dict(a=48, z=72, xm=1.0), 0), key=lambda t: (t['day'], t['k']))
rows = [dict(day=t['day'], pos=t['pct'], acct=t['pct'] * min(1.0, 3.0 / t['leg_risk'])) for t in T]
def pf(a): g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 99.0
W = [(pf([x['acct'] for x in rows[i:i + 30]]), 100 * np.mean([x['pos'] > 0 for x in rows[i:i + 30]]), float(np.mean([x['pos'] for x in rows[i:i + 30]]))) for i in range(len(rows) - 29)]
q = lambda k, p: float(np.percentile([w[k] for w in W], p))
out = dict(trades=len(rows), pf=round(pf([x['acct'] for x in rows]), 3), win=round(100 * np.mean([x['pos'] > 0 for x in rows]), 1), avg=round(float(np.mean([x['pos'] for x in rows])), 3),
           pace_per_day=round(len(rows) / len(FR.dm), 4), p25=dict(pf=round(q(0, 25), 3), win=round(q(1, 25), 3), avg=round(q(2, 25), 3)), p5=dict(pf=round(q(0, 5), 3), win=round(q(1, 5), 3), avg=round(q(2, 5), 3)))
p = os.path.join(os.path.dirname(HERE), 'live', 'health_baseline.json'); b = json.load(open(p)); b['systems']['RELVAL'] = out
json.dump(b, open(p, 'w'), indent=1); print('RELVAL', out)
