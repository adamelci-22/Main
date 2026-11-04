#!/usr/bin/env python3
"""FADE runaway skip: threshold sweep and trend-band table (governor question 2026-11-04: which is better, is there something in between).
    python3 -I tools/backtest/runaway_sweep.py
Part 1: re-simulates every session (paper.simulate, one account, as improve.run_cf) with x.fade_max_trend = off, 0.30 ... 2.00 and prints the
        whole-system result, the in-sample / out-of-sample halves (improve.SPLIT) and the FADE-only trade table.
Part 2: with the rule OFF, every FADE trade bucketed by how far the proxy had already moved in the break direction at the retest bar close.
In-sample on the Robinhood 5-minute dataset (base + live sessions): a guide for a paper trial (D4), never a rule by itself.
Changes no order, rule or state."""
import os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import improve as I, paper

D = I.load_data(); t = I.tun(); base = I.champion_values(t)
THRESH = [None, 0.30, 0.45, 0.60, 0.70, 0.85, 1.00, 1.25, 1.50, 2.00]
print(f"{len(D.days)} sessions {D.days[0]}..{D.days[-1]}  (live rule in force: x.fade_max_trend {base.get('x.fade_max_trend')})\n")


def fade_line(tr):
    f = [x for x in tr if x[3] == 'FADE']
    if not f: return 'n=0'
    w = [x for x in f if x[1] > 0]
    return (f"n={len(f):3d} win {100 * len(w) / len(f):3.0f}%  +2R {100 * sum(1 for x in f if x[4]) / len(f):3.0f}%  "
            f"avg {st.mean(x[2] for x in f):+.3f}%  total {sum(x[2] for x in f):+7.2f}%")


print("PART 1  whole system re-simulated per threshold (FADE + PULLBACK, one account from $2,000)")
print(f"{'rule':>6} | {'%/day':>7} {'ret%':>8} {'dd%':>5} {'PF':>5} {'trades':>6} | {'ins %/day':>9} {'oos %/day':>9} | FADE only")
res = {}
for th in THRESH:
    v = dict(base); v['x.fade_max_trend'] = th
    daily, trades = I.run_cf(D, v); cut = int(len(daily) * I.SPLIT)
    s, a, b = I.stats(daily, trades), I.stats(daily, trades, 0, cut), I.stats(daily, trades, cut)
    res[th] = (daily, trades)
    name = 'off' if th is None else f"{th:.2f}"
    print(f"{name:>6} | {s['mean_day']:+7.4f} {s['ret']:8.1f} {s['dd']:5.2f} {s['pf']!s:>5} {s['trades']:6d} | {a['mean_day']:+9.4f} {b['mean_day']:+9.4f} | {fade_line(trades)}")

print("\nlast 40 sessions and Friday-free live window (2026-10-16 on), FADE only, per threshold")
for th in THRESH:
    daily, trades = res[th]; last = {d for d, _ in daily[-40:]}; live = {d for d, _ in daily if d >= '2026-10-16'}
    name = 'off' if th is None else f"{th:.2f}"
    print(f"{name:>6} | last40 {fade_line([x for x in trades if x[0] in last])} | live {fade_line([x for x in trades if x[0] in live])}")

# ---- Part 2: trend bands with the rule off
v = dict(base); v['x.fade_max_trend'] = None
saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = v, '0000-00-00', '0000-00-00', True
rows, eq = [], 2000.0
try:
    for i in range(1, len(D.days)):
        d, pd = D.days[i], D.days[i - 1]
        tod = {s: D.bars[s][d][:48] for s in I.WANT() if d in D.bars.get(s, {})}
        prv = {s: D.bars[s][pd] for s in I.WANT() if pd in D.bars.get(s, {})}
        taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
        for c in taken:
            if c['system'] != 'FADE' or c['status'] != 'closed': continue
            p = c['proxy']; k = c['k']; bs = -c['side']
            tr = (tod[p][k - 1][3] / prv[p][-1][3] - 1) * 100 * bs        # the runaway test: move since the prior close at the retest bar close
            rows.append(dict(day=d, tr=tr, acct=c['usd'] / eq * 100, win=c['usd'] > 0, r2=any('take profit' in e[1] for e in c['events'])))
        eq = e2
finally:
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved
print(f"\nPART 2  FADE trades with the rule OFF ({len(rows)} trades), by proxy move since the prior close in the break direction")
bands = [(-99, 0.0, 'against the day (< 0)'), (0.0, 0.30, '0.00 to 0.30'), (0.30, 0.60, '0.30 to 0.60'), (0.60, 0.85, '0.60 to 0.85'),
         (0.85, 1.25, '0.85 to 1.25'), (1.25, 2.00, '1.25 to 2.00'), (2.00, 99, '2.00 and up')]
for lo, hi, name in bands:
    r = [x for x in rows if lo <= x['tr'] < hi]
    if not r: print(f"  {name:<24} n=0"); continue
    print(f"  {name:<24} n={len(r):3d} win {100 * sum(x['win'] for x in r) / len(r):3.0f}%  +2R {100 * sum(x['r2'] for x in r) / len(r):3.0f}%  "
          f"avg {st.mean(x['acct'] for x in r):+.3f}%  total {sum(x['acct'] for x in r):+7.2f}%  worst {min(x['acct'] for x in r):+.2f}%")
rn = [x for x in rows if x['tr'] >= 0.85]
print(f"  runaways (>= 0.85): n={len(rn)}, split by half of the dataset: first half avg {st.mean([x['acct'] for x in rn[:len(rn)//2]]):+.3f}%  second half avg {st.mean([x['acct'] for x in rn[len(rn)//2:]]):+.3f}%")
