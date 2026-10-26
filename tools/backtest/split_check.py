#!/usr/bin/env python3
"""How does paper.py cope with a forward split of a FADE proxy? Re-runs paper.py's own fade() on every SOXX FADE trade in the Robinhood bars (2026-03-03..10-14)
with the day's prices divided by 3 and volumes multiplied by 3, as on a 3-for-1 split day (SOXX splits 1:3 on 2026-11-05 per the Massive splits list).
    /usr/bin/python3 -I tools/backtest/split_check.py > tools/backtest/results/split_check.txt
Also shows the effect on paper.py's RVOL (the same-bar tie-break) when the 20-session baseline is built from unadjusted pre-split volumes.
"""
import importlib.util, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('paper', os.path.join(HERE, '..', 'live', 'paper.py')); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
from lab import get_data
D = get_data(); days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
n = same = 0
for d in days:
    b = D.bars['SOXX'][d]; a = P.fade(b, 78)
    if not a or a.get('status') != 'closed': continue
    s = [(o / 3, h / 3, l / 3, c / 3, v * 3) for (o, h, l, c, v) in b]; z = P.fade(s, 78); n += 1
    same += bool(z and z.get('status') == 'closed' and (z['k'], z['side'], z['xbar'], z['why']) == (a['k'], a['side'], a['xbar'], a['why'])
                 and abs(z['gross'] / (a['gross'] / 3) - 1) < 1e-9 and abs(z['risk_pct'] / a['risk_pct'] - 1) < 1e-9)
print(f"SOXX FADE trades re-run on a synthetic 3-for-1 split day (price/3, volume x3): {same} of {n} identical (entry bar, side, exit bar, exit reason, % gross, % risk)")
vals = []
for d0 in days[40::10]:
    i = D.days.index(d0); pri = D.days[i - 20:i]; k = 12
    base = {'SOXX': [st.mean(sum(x[4] for x in D.bars['SOXX'][q][:j]) for q in pri) for j in range(79)]}
    t = {'SOXX': [(o / 3, h / 3, l / 3, c / 3, v * 3) for (o, h, l, c, v) in D.bars['SOXX'][d0]]}
    vals.append((P.rvol({'SOXX': D.bars['SOXX'][d0]}, base, 'SOXX', k), P.rvol(t, base, 'SOXX', k)))
print(f"RVOL at bar 12 on {len(vals)} sample days: unsplit mean {st.mean(a for a, _ in vals):.2f}, split day with a pre-split baseline mean {st.mean(b for _, b in vals):.2f} (about 3x)")
