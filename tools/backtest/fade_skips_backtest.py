#!/usr/bin/env python3
"""Backtest reference for the scorecard's skipped-trades card: every FADE trade the runaway skip passes on in the Robinhood dataset
(base + live sessions), each day on a fresh $1,000 account (as tools/live/fade_skips.py measures live days).
    python3 tools/backtest/fade_skips_backtest.py OUT.csv
Same columns as archive/fade_skips.csv. Reporting only."""
import csv, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'live'))
import improve as I, fade_skips as S, paper
D = I.load_data(); t = I.tun(); cur = I.champion_values(t); rows = []
for i in range(1, len(D.days)):
    d, pd = D.days[i], D.days[i - 1]
    tod = {s: paper.grid(D.bars[s][d], 48) if False else D.bars[s][d][:48] for s in I.WANT() if d in D.bars.get(s, {})}
    prv = {s: D.bars[s][pd] for s in I.WANT() if pd in D.bars.get(s, {})}
    a, apct = S.run(d, tod, prv, cur); b, _ = S.run(d, tod, prv, {**cur, 'x.fade_max_trend': None})
    keep = {(c['proxy'], c['k']) for c in a if c['system'] == 'FADE'}
    for c in b:
        if c['system'] != 'FADE' or (c['proxy'], c['k']) in keep or c['status'] != 'closed': continue
        p = c['proxy']; tr = (tod[p][c['k'] - 1][3] / prv[p][-1][3] - 1) * 100 * -c['side']
        rows.append(dict(day=d, proxy=p, ticker=c['ticker'], entry_time=paper.k2t(c['k']), trend_pct=f"{tr:.2f}", skipped_acct_pct=f"{c['usd'] / 10:.3f}",
                         skipped_reached_2R='yes' if any('take profit' in e[1] for e in c['events']) else 'no', exit_reason=c.get('why') or '', day_acct_pct_in_force=f"{apct:.3f}", note='backtest'))
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=S.HDR, lineterminator='\n'); w.writeheader(); w.writerows(rows)
x = [float(r['skipped_acct_pct']) for r in rows]
print(f"{len(rows)} skipped FADE trades, {sum(v > 0 for v in x)} would have won, total {sum(x):+.2f}% (fresh $1,000 each day) -> {sys.argv[1]}")
