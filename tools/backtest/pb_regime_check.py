#!/usr/bin/env python3
"""Did high-volatility market days hurt PULLBACK? (governor question 2026-11-05, after the two 11-04 stop-outs)
    python3 -I tools/backtest/pb_regime_check.py <the three C1.2 dump files of the 13:30 close, for today's two trades>
For each PULLBACK trade in the dataset: how wide the market's range was up to the entry bar (QQQ and SOXX, open to entry) against the median range over the
prior 60 sessions up to the same bar. ratio >= 1.5 means a day with at least 1.5x its normal range by then. Then win rate and average by regime.
In-sample, small buckets: a guide only. Changes no order, rule or state."""
import os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import improve as I, paper

D = I.load_data(); t = I.tun(); vals = I.champion_values(t)
def rng(b, k): x = b[:k + 1]; return (max(y[1] for y in x) - min(y[2] for y in x)) / x[0][0] * 100
def ratio(sym, day, k):
    i = D.days.index(day) if day in D.days else len(D.days)
    prior = [rng(D.bars[sym][d], k) for d in D.days[max(0, i - 60):i] if d in D.bars.get(sym, {}) and len(D.bars[sym][d]) > k]
    return rng(D.bars[sym][day], k) / st.median(prior) if prior and day in D.bars.get(sym, {}) else None

saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = vals, '0000-00-00', '0000-00-00', True
rows, eq = [], 2000.0
try:
    for i in range(1, len(D.days)):
        d, pd = D.days[i], D.days[i - 1]
        tod = {s: D.bars[s][d][:48] for s in I.WANT() if d in D.bars.get(s, {})}
        prv = {s: D.bars[s][pd] for s in I.WANT() if pd in D.bars.get(s, {})}
        taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
        for c in taken:
            if c['system'] != 'PB' or c['status'] != 'closed': continue
            q, x = ratio('QQQ', d, c['k']), ratio('SOXX', d, c['k'])
            if q is None or x is None: continue
            rows.append(dict(day=d, ticker=c['ticker'], q=q, x=x, acct=c['usd'] / eq * 100, win=c['usd'] > 0, stopped=c['why'] == 'stop'))
        eq = e2
finally:
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved

def line(name, r):
    if not r: return f"  {name:<34} n=0"
    return (f"  {name:<34} n={len(r):3d} win {100 * sum(x['win'] for x in r) / len(r):3.0f}%  stopped {100 * sum(x['stopped'] for x in r) / len(r):3.0f}%  "
            f"avg {st.mean(x['acct'] for x in r):+.3f}%  total {sum(x['acct'] for x in r):+7.2f}%")
print(f"{len(rows)} PULLBACK trades with regime data, {D.days[0]}..{D.days[-1]}")
print(line('all', rows))
for name, key in (('QQQ range ratio', 'q'), ('SOXX range ratio', 'x')):
    print(name)
    print(line('  below 1.0 (calm)', [r for r in rows if r[key] < 1.0])); print(line('  1.0 to 1.5', [r for r in rows if 1.0 <= r[key] < 1.5]))
    print(line('  1.5 to 2.0', [r for r in rows if 1.5 <= r[key] < 2.0])); print(line('  2.0 and up (wild)', [r for r in rows if r[key] >= 2.0]))
if len(sys.argv) > 1:
    raw = paper.load(sys.argv[1:]); day = '2026-11-04'
    def rr(sym, k):
        b = paper.grid(raw[sym][day], 78); i = D.days.index(D.days[-1]) + 1
        prior = [rng(D.bars[sym][d], k) for d in D.days[-60:] if d in D.bars.get(sym, {}) and len(D.bars[sym][d]) > k]
        return rng(b, k) / st.median(prior)
    for leg, k in (('SOXS', 23), ('MSFU', 39)):
        print(f"today {leg} at bar {k}: QQQ range ratio {rr('QQQ', k):.2f}, SOXX range ratio {rr('SOXX', k):.2f}")
