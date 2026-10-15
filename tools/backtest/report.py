#!/usr/bin/env python3
"""Sensitivity grid + breakdowns for the backtest.   python3 tools/backtest/report.py"""
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import Sim, summarize
from collections import defaultdict

def line(s):
    return (f"{s['label']:<34} trades {s['trades']:>4}  win {s['win_rate']:5.1f}%  avg/trade {s['avg_pos_pct']:+6.3f}%  PF {s['profit_factor']:5.2f}  "
            f"ret {s['ret_pct']:+7.1f}%  avg/day {s['avg_day_pct']:+6.3f}%  maxDD {s['max_dd']:5.1f}%")

if __name__ == '__main__':
    base = Sim(cost=0.0003).run()
    rows = [('BASE (0.03%/side, all rules)', base)]
    for lab, kw in [('cost 0.00%/side', dict(cost=0.0)), ('cost 0.06%/side', dict(cost=0.0006)), ('cost 0.10%/side', dict(cost=0.001)),
                    ('no throttle (always 3% risk)', dict(cost=0.0003, throttle=False)),
                    ('no ratchet (initial stop + 12:30)', dict(cost=0.0003, ratchet=False)),
                    ('no volume test', dict(cost=0.0003, vol_test=False)),
                    ('no v3.119 momentum rule', dict(cost=0.0003, momentum=False))]:
        rows.append((lab, Sim(**kw).run()))
    for lab, sim in rows:
        s = summarize(sim, lab); print(line(s))
    t = base.trades
    print('\nBy month (BASE):')
    m = defaultdict(list)
    for x in t: m[x['day'][:7]].append(x)
    eq = dict(base.day_eq); 
    for k in sorted(m):
        v = m[k]; w = sum(1 for x in v if x['pnl'] > 0)
        print(f"  {k}: trades {len(v):>3}  win {w/len(v)*100:5.1f}%  net ${sum(x['pnl'] for x in v):+8.2f}  avg/trade {st.mean(x['pct'] for x in v):+6.3f}%")
    print('\nBy exit type:')
    for why in ('stop', 'close'):
        v = [x for x in t if x['why'] == why]
        if v: print(f"  {why:>5}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
    print('\nBy side:')
    for sd, n in ((1, 'bull(long leg)'), (-1, 'bear(inverse leg)')):
        v = [x for x in t if int(x['side']) == sd]
        print(f"  {n:<18}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
    print('\nBy proxy row:')
    pr = defaultdict(list)
    for x in t: pr[x['proxy']].append(x)
    for k in sorted(pr, key=lambda k: -sum(x['pnl'] for x in pr[k])):
        v = pr[k]; print(f"  {k:<5}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
    print('\nBy entry time (checkpoint):')
    bk = [('10:00-10:25', 0, 5), ('10:30-10:55', 6, 11), ('11:00-11:25', 12, 17), ('11:30-11:55', 18, 23)]
    for n, a, b in bk:
        v = [x for x in t if a <= x['entry_chk'] <= b]
        if v: print(f"  {n}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
    print('\nBy trade # of the day:')
    byday = defaultdict(list)
    for x in t: byday[x['day']].append(x)
    for n in (1, 2, 3):
        v = [d[n-1] for d in byday.values() if len(d) >= n]
        print(f"  trade {n}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
    print('\nWhile throttled (0.5% risk) vs normal:')
    for flag in (True, False):
        v = [x for x in t if (str(x['thr']) == str(flag))]
        if v: print(f"  throttle={flag}: {len(v):>3}  win {sum(1 for x in v if x['pnl']>0)/len(v)*100:5.1f}%  avg {st.mean(x['pct'] for x in v):+6.3f}%  net ${sum(x['pnl'] for x in v):+8.2f}")
