#!/usr/bin/env python3
"""Compact Robinhood get_equity_historicals / get_index_historicals day dumps into tools/scanner/data.
    python3 tools/scanner/build_data.py EQUITY_DUMP... --vix VIX_DUMP...
Writes daily.json.gz {sym: [[date, o, h, l, c, v], ...]} (merged with the existing file) and vix_5y.csv."""
import gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'data')
args = sys.argv[1:]; vi = args.index('--vix') if '--vix' in args else len(args)
eq, vx = args[:vi], args[vi + 1:]
f = os.path.join(OUT, 'daily.json.gz')
data = json.load(gzip.open(f)) if os.path.exists(f) else {}
for p in eq:
    for r in json.load(open(p))['data']['results']:
        rows = {b['begins_at'][:10]: [b['begins_at'][:10], float(b['open_price']), float(b['high_price']), float(b['low_price']),
                                      float(b['close_price']), int(b['volume'] or 0)] for b in r['bars'] if not b.get('interpolated')}
        old = {x[0]: x for x in data.get(r['symbol'], [])}; old.update(rows)
        data[r['symbol']] = [old[d] for d in sorted(old)]
json.dump(data, gzip.open(f, 'wt'))
if vx:
    vf = os.path.join(OUT, 'vix_5y.csv'); rows = {}
    if os.path.exists(vf):
        for line in open(vf).read().split('\n')[1:]:
            if line: rows[line.split(',')[0]] = line
    for p in vx:
        for r in json.load(open(p))['data']['results']:
            for b in r['bars']:
                if b.get('interpolated'): continue
                d = b['begins_at'][:10]; rows[d] = f"{d},{b['open_value']},{b['high_value']},{b['low_value']},{b['close_value']}"
    open(vf, 'w').write('date,open,high,low,close\n' + '\n'.join(rows[d] for d in sorted(rows)) + '\n')
print(len(data), 'symbols;', min(len(v) for v in data.values()), '-', max(len(v) for v in data.values()), 'bars')
