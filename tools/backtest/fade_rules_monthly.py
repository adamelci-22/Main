#!/usr/bin/env python3
"""FADE month by month on the Robinhood 5-minute dataset, old rules (tunables v1) against the runaway skip (v2), for the scorecard.
    python3 tools/backtest/fade_rules_monthly.py OUT.json
FADE on its own (PULLBACK off), one account from $2,000, one position at a time (improve.run_cf). One row per month plus an "All" row;
old_* and new_* columns, diff_ret = new minus old return points. In-sample (the filter was found on this data). Reporting only."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'live'))
import improve as I
t = I.tun(); D = I.load_data()
V = {k: I.isolate({**I.paper.TUNABLE_DEFAULTS, **I.version_values(t, n)}, 'fade') for k, n in (('old', 1), ('new', 2))}
R = {}
for k, v in V.items():
    d, tr = I.run_cf(D, v); R[k] = (d, [x for x in tr if x[3] == 'FADE'])
def ms(k, pre):
    d, tr = R[k]; dd = [x for day, x in d if day.startswith(pre)]; tt = [x for x in tr if x[0].startswith(pre)]
    eq = peak = 1.0; mdd = 0.0
    for x in dd: eq *= 1 + x / 100; peak = max(peak, eq); mdd = max(mdd, (1 - eq / peak) * 100)
    w = [x for x in tt if x[1] > 0]; l = [x for x in tt if x[1] < 0]
    out = {'days': len(dd), f'{k}_trades': len(tt), f'{k}_win': round(100 * len(w) / len(tt), 1) if tt else None, f'{k}_r2': round(100 * sum(1 for x in tt if x[4]) / len(tt), 1) if tt else None,
           f'{k}_ret': round((eq - 1) * 100, 2), f'{k}_dd': round(mdd, 2)}
    if not pre:
        s = I.stats(d, []); out.update({f'{k}_per_day': s['mean_day'], f'{k}_sharpe': s['sharpe'], f'{k}_losers': len(l),
                                        f'{k}_avg_win': round(sum(x[2] for x in w) / len(w), 3) if w else None, f'{k}_avg_loss': round(sum(x[2] for x in l) / len(l), 3) if l else None})
    return out
import calendar
months = sorted({day[:7] for day, _ in R['old'][0]}); last = R['old'][0][-1][0]
rows = []
for m in months + ['All']:
    pre = '' if m == 'All' else m
    r = {'month': m, 'label': 'All months' if m == 'All' else calendar.month_abbr[int(m[5:])] + (f' (to {int(last[8:])})' if m == last[:7] else '')}
    r.update(ms('old', pre)); r.update(ms('new', pre)); r['diff_ret'] = round(r['new_ret'] - r['old_ret'], 2); rows.append(r)
json.dump(rows, open(sys.argv[1], 'w'), indent=1)
print(f"{len(rows)} rows, {R['old'][0][0][0]}..{last} -> {sys.argv[1]}")
