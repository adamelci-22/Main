#!/usr/bin/env python3
"""Add symbols from saved get_equity_historicals dumps to the merged backtest data files WITHOUT touching existing symbols.
    python3 tools/backtest/merge_dumps.py SYMBOL[,SYMBOL..] DUMP [DUMP ..]
Same row format as build_data.py (real bars only: not interpolated, volume > 0).
"""
import gzip, json, os, sys
syms = set(sys.argv[1].split(',')); dumps = sys.argv[2:]
here = os.path.dirname(os.path.abspath(__file__)); p5 = here + '/data/bt_5m.json.gz'
F = json.load(gzip.open(p5, 'rt'))
new = {}
for f in dumps:
    for r in json.load(open(f))['data']['results']:
        s = r['symbol']
        if s not in syms or r['interval'] != '5minute': continue
        for b in r['bars']:
            if b.get('interpolated') or not b['volume']: continue
            ts = b['begins_at']
            new.setdefault(s, {}).setdefault(ts[:10], {})[ts[11:16]] = [float(b['open_price']), float(b['high_price']), float(b['low_price']), float(b['close_price']), b['volume']]
for s, days in new.items():
    F[s] = {day: [[k] + v for k, v in sorted(bars.items())] for day, bars in days.items()}
    full = sum(1 for v in F[s].values() if len(v) >= 70)
    print(s, len(F[s]), 'days;', sum(len(v) for v in F[s].values()), 'real bars; days with >=70 bars:', full, min(F[s]), max(F[s]))
json.dump(F, gzip.open(p5, 'wt'))
