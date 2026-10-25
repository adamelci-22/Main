#!/usr/bin/env python3
"""Same-period PULLBACK setups, Robinhood vs Databento (2026-03-03..10-14).  /usr/bin/python3 -I tools/backtest/db_pb_compare.py DB_5M.json.gz"""
import os, sys; sys.argv = ['x', sys.argv[1]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_pb as P, manual as m, pb_final as PBF, mixed as MXD, statistics as st
R = P.load_rh(); m.rvol = PBF.rvol(R); rd = R.days[1:]
rc = {(c['day'], c['name']): c for c in P.cands(R, rd, P.LIVE)}
D = P.load_db(); m.rvol = PBF.rvol(D)
dc = {(c['day'], c['name']): c for c in P.cands(D, rd, P.LIVE)}
both = set(rc) & set(dc)
print(f"setups 2026-03-03..10-14: Robinhood {len(rc)}, Databento {len(dc)}, same day+ticker {len(both)}")
print(f"  on shared setups: RH avg {st.mean(rc[k]['pct'] for k in both):+.2f}% win {100*sum(rc[k]['pct']>0 for k in both)/len(both):.0f}% | DB avg {st.mean(dc[k]['pct'] for k in both):+.2f}% win {100*sum(dc[k]['pct']>0 for k in both)/len(both):.0f}%; same entry bar {sum(rc[k]['k']==dc[k]['k'] for k in both)}, same sign {sum((rc[k]['pct']>0)==(dc[k]['pct']>0) for k in both)}")
o = set(rc) - both; n = set(dc) - both
print(f"  only in RH: {len(o)} avg {st.mean(rc[k]['pct'] for k in o):+.2f}%   only in DB: {len(n)} avg {st.mean(dc[k]['pct'] for k in n):+.2f}%")
