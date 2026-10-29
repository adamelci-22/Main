#!/usr/bin/env python3
"""FADE setup quality study (governor question 2026-10-29: "can we do something that is a bit more sure?").
    python3 tools/backtest/fade_quality_study.py
Every FADE trade of the current rules (one account, one position at a time, as improve.run_cf) on the Robinhood 5-minute dataset
(base + live sessions), with what the proxy's chart looked like at the signal:
  gap_with   = the opening gap in the direction of the failed break, % (positive: the break went the way the day gapped)
  trend_with = proxy move from the prior close to the signal close, in the break direction, %
  rel_with   = that move minus the median move of the other five proxies (positive: the faded proxy was the day's leader that way)
  depth      = how far the retest bar closed back inside the box, as a share of the box width
  box        = box width, % of price
Each feature is split into thirds; the table shows trades, win rate, +2R rate, average and total account %. In-sample: a guide to
which filter to put on paper trial (D4), never a rule by itself. Robinhood data only. Changes no order, rule or state."""
import os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import io, contextlib
import improve as I, paper
with contextlib.redirect_stdout(io.StringIO()):
    from lab import get_data
    D = get_data(live=True)
t = I.tun(); vals = I.champion_values(t); P6 = list(paper.FADE_ROWS)
saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = vals, '0000-00-00', '0000-00-00', True
rows, eq = [], 2000.0
for i in range(1, len(D.days)):
    d, pd = D.days[i], D.days[i - 1]
    tod = {s: D.bars[s][d][:48] for s in I.WANT() if d in D.bars.get(s, {})}
    prv = {s: D.bars[s][pd] for s in I.WANT() if pd in D.bars.get(s, {})}
    taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
    for c in taken:
        if c['system'] != 'FADE' or c['status'] != 'closed': continue
        p = c['proxy']; b = tod[p]; pc = prv[p][-1][3]; bs = -c['side']; k = c['k']
        H, L = max(x[1] for x in b[:6]), min(x[2] for x in b[:6]); E = H if bs > 0 else L
        mv = lambda s: (tod[s][k - 1][3] / prv[s][-1][3] - 1) * 100 if s in tod and s in prv and len(tod[s]) >= k else None
        others = [m for m in (mv(s) for s in P6 if s != p) if m is not None]
        rows.append(dict(day=d, proxy=p, acct=c['usd'] / eq * 100, win=c['usd'] > 0, r2=any('take profit' in e[1] for e in c['events']),
                         gap_with=(b[0][0] / pc - 1) * 100 * bs, trend_with=mv(p) * bs, rel_with=(mv(p) - st.median(others)) * bs if others else 0.0,
                         depth=(E - b[k - 1][3]) * bs / (H - L), box=(H - L) / b[0][0] * 100))
    eq = e2
paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved
def line(name, rs):
    if not rs: return f"  {name:<34} n=0"
    return (f"  {name:<34} n={len(rs):3d}  win {100*sum(r['win'] for r in rs)/len(rs):3.0f}%  +2R {100*sum(r['r2'] for r in rs)/len(rs):3.0f}%  "
            f"avg {st.mean(r['acct'] for r in rs):+.3f}%  total {sum(r['acct'] for r in rs):+6.2f}%")
print(f"FADE trades of the current rules on {len(D.days)} Robinhood sessions ({D.days[0]}..{D.days[-1]}), in-sample")
print(line('all', rows))
for f in ('gap_with', 'trend_with', 'rel_with', 'depth', 'box'):
    v = sorted(r[f] for r in rows); a, b2 = v[len(v) // 3], v[2 * len(v) // 3]
    print(f"{f}: thirds split at {a:+.3f} / {b2:+.3f}")
    print(line('  low third', [r for r in rows if r[f] < a])); print(line('  middle third', [r for r in rows if a <= r[f] < b2])); print(line('  high third', [r for r in rows if r[f] >= b2]))
for name, cond in (('rel_with <= 0 (not the leader)', lambda r: r['rel_with'] <= 0), ('rel_with > 0 (faded the leader)', lambda r: r['rel_with'] > 0),
                   ('trend_with <= 0 (break against the day)', lambda r: r['trend_with'] <= 0), ('trend_with > 0 (break with the day)', lambda r: r['trend_with'] > 0)):
    print(line(name, [r for r in rows if cond(r)]))
today = [r for r in rows if r['day'] == '2026-10-29']
for r in today: print(f"today {r['proxy']}: gap_with {r['gap_with']:+.2f} trend_with {r['trend_with']:+.2f} rel_with {r['rel_with']:+.2f} depth {r['depth']:.2f} box {r['box']:.2f} -> {r['acct']:+.2f}%")
