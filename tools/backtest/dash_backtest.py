#!/usr/bin/env python3
"""Backtest data for the scorecard dashboard (governor 2026-11-14: "add backtest sections, include all the new systems"). Research only.
    python3 -I tools/backtest/dash_backtest.py OUT_DIR
Writes bt_years.json, bt_curve.json, bt_months.json, bt_risk.json and systems.json: the live book (FADE + PULLBACK + IBS-TREND long, mirror,
dip, overnight leg at 50%) and its earlier versions on the Massive 5-minute tape 2022-01-03..2026-10-30, one shared account."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import overnight_size as OS
O, B, BA, SB, N2, NS, TB, BM = OS.O, OS.B, OS.BA, OS.SB, OS.N2, OS.NS, OS.TB, OS.BM
out = sys.argv[1]; os.makedirs(out, exist_ok=True); dm = O.dm; YEARS = SB.YEARS; r4 = lambda x: round(float(x), 3)

F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
M = B.BC.new(B.ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(B.ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
S = O.signals(); ovn = np.zeros(len(dm))
for n, d in enumerate(dm):
    c = [t for t in S.get(d, []) if t['kind'] == 'long']
    if c: ovn[n] = max(c, key=lambda t: t['rv'])['pct'] / 100
def acct(parts, after_stop=False, extra=0.0):
    return BA.acct(dm, TB.byday([t for p in parts for t in p]), after_stop=after_stop, extra_cost=extra)
old, _, _ = acct([F0, P0], True); v48, _, _ = acct([F0, P0, I0], True); v49, _, _ = acct([F0, P0, I0, M], True)
v51, tk, _ = acct([F0, P0, I0, M, D]); cur = (1 + v51) * (1 + 0.5 * ovn) - 1
BOOKS = [('b0', 'FADE + PULLBACK (rules to Nov 12)', old), ('b1', '+ IBS-TREND long (v5.2.48)', v48), ('b2', '+ mirror (v5.2.49)', v49), ('b3', '+ dip, no entry after a stop-out (v5.2.51)', v51), ('b4', '+ overnight leg at 50% (v5.2.52, live)', cur)]
ALONE = [('s0', 'FADE alone', acct([F0])[0]), ('s1', 'PULLBACK alone', acct([P0])[0]), ('s2', 'IBS-TREND long alone', acct([I0])[0]), ('s3', 'Mirror alone', acct([M])[0]), ('s4', 'Dip alone', acct([D])[0]), ('s5', 'Overnight leg alone, full size', ovn)]
years = []
for grp, items in (('Book', BOOKS), ('System', ALONE)):
    for i, nm, r in items:
        y = SB.yret(r)
        for j, yy in enumerate(YEARS): years.append(dict(id=f'{i}_{yy}', group=grp, key=i, name=nm, year=int(yy), ret=r4(y[j]), in_sample=(yy == '2026')))
json.dump(years, open(os.path.join(out, 'bt_years.json'), 'w'))
def cum(r): return (np.cumprod(1 + r) - 1) * 100
c0, c3, c4 = cum(old), cum(v51), cum(cur)
json.dump([dict(d=i, day=d, old=r4(c0[i]), current=r4(c4[i]), no_overnight=r4(c3[i])) for i, d in enumerate(dm)], open(os.path.join(out, 'bt_curve.json'), 'w'))
mo0, mo4 = SB.mret(old), SB.mret(cur)
json.dump([dict(month=m, old=r4(mo0[i]), current=r4(mo4[i])) for i, m in enumerate(SB.MONTHS)], open(os.path.join(out, 'bt_months.json'), 'w'))
# risk rows
risk = []; yb = SB.yret(v51)
for ec in (0.0, 0.06, 0.14):
    r, _, _ = acct([F0, P0, I0, M, D], extra=ec); r = (1 + r) * (1 + 0.5 * ovn) - 1; y = SB.yret(r); mdd, halts = OS.dd_stats(r)
    risk.append(dict(id=f'cost_{ec}', kind='Trading cost', label=f'{0.06 + ec:.2f}% a round trip' + (' (model)' if ec == 0 else ''), avg_22_25=r4(y[:4].mean()), worst_year=r4(y[:4].min()), max_dd=r4(mdd), stops=halts, note=''))
for f in (0.0, 0.33, 0.5, 1.0):
    o = ovn * f; r = (1 + v51) * (1 + o) - 1; y = SB.yret(r); mdd, halts = OS.dd_stats(r)
    risk.append(dict(id=f'ovn_{f}', kind='Overnight size', label='no overnight leg' if f == 0 else f'{int(f * 100)}% of cash' + (' (live)' if f == 0.5 else ''), avg_22_25=r4(y[:4].mean()), worst_year=r4(y[:4].min()),
                     max_dd=r4(mdd), stops=halts, note=('worst night ' + f'{o.min() * 100:+.1f}%' + f', {int((o < -0.03).sum())} nights under -3%') if f else ''))
json.dump(risk, open(os.path.join(out, 'bt_risk.json'), 'w'))
# systems table
names = {0: 'FADE', 1: 'PULLBACK', 4: 'IBS-TREND long', 5: 'IBS mirror', 2: 'Dip'}; nyr = len(dm) / 252; rows = []
for s, nm in names.items():
    x = [t for t in tk if t['sys'] == s]; rows.append(dict(id=nm, name=nm, trades=len(x), per_year=r4(len(x) / nyr), win_pct=r4(100 * np.mean([t['g'] > 0 for t in x])), points=r4(sum(t['g'] for t in x))))
nights = ovn[ovn != 0]; rows.append(dict(id='Overnight', name='Overnight leg (50%)', trades=len(nights), per_year=r4(len(nights) / nyr), win_pct=r4(100 * np.mean(nights > 0)), points=r4(sum(0.5 * nights * 100))))
SPEC = {'FADE': ('Failed 30-minute box break on a proxy, first retest closes back inside', 'Opposite leg, 3x', '10:10 to 12:55', 'Beyond the break extreme, at least 0.5% of the proxy', '1/3 at 2R, rest on a 2-ATR chandelier, out 13:30', 'Not on Fridays'),
        'PULLBACK': ('Breakout on volume, 2 to 5 bar dip, trigger bar above the prior high', 'Inverse and single-stock funds', '10:10 to 12:50', 'Dip low, at least 0.75%', '1/3 at the morning high, rest to a 20-EMA close, out 13:30', ''),
        'IBS-TREND long': ('Closed above its 20-day average and in the bottom 10% of its range', '3x long leg', '9:35', '1% of the proxy (3% on the leg)', 'Out 15:55', 'One IBS trade a day'),
        'IBS mirror': ('Closed at or below its 20-day average and in the top 5% of its range', '3x inverse leg', '9:35', '1% of the proxy', 'Out 15:55', 'One IBS trade a day'),
        'Dip': ('Closed above its 50-day average with a 2-day RSI under 10', '3x long leg', '9:35', '1% of the proxy', 'Out 15:55', 'One IBS trade a day'),
        'Overnight': ('At 15:55 above its 20-day average and in the bottom 10% of the day range', '3x long leg, 50% of cash', '15:55', 'Disaster stop at 90% of the fill', 'Sell at the next 9:35', 'Held overnight: the only exception to the nothing-overnight rule')}
for r in rows: r.update(zip(('signal', 'leg', 'entry', 'stop', 'exit', 'note'), SPEC[r['id']]))
json.dump(rows, open(os.path.join(out, 'systems.json'), 'w'))
print('years', [(b[1][:28], [round(v, 1) for v in SB.yret(b[2])]) for b in BOOKS])
print('systems', [(r['id'], r['trades'], r['win_pct'], r['points']) for r in rows]); print('risk', [(r['label'], r['avg_22_25'], r['max_dd'], r['stops']) for r in risk])
