#!/usr/bin/env python3
"""Merge Robinhood get_earnings_calendar / get_earnings_results dumps + earnings_manual.csv into data/earnings.csv
(symbol, date, timing) for the scanner universe.  python3 tools/scanner/build_earnings.py DUMP..."""
import csv, gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'data')
U = set(json.load(gzip.open(os.path.join(D, 'daily.json.gz'))))
rows = {}
out = os.path.join(D, 'earnings.csv')
for src in [out, os.path.join(D, 'earnings_manual.csv')]:
    if os.path.exists(src):
        for r in csv.DictReader(open(src)): rows[(r['symbol'], r['date'])] = r['timing']
for p in sys.argv[1:]:
    try: res = json.load(open(p))['data']['results']
    except Exception: continue
    for r in res:
        s = r.get('symbol'); rep = r.get('report') or {}
        if s in U and rep.get('date') and rep.get('verified') is not False:
            rows[(s, rep['date'])] = rep.get('timing') or 'pm'
with open(out, 'w') as f:
    f.write('symbol,date,timing\n')
    for (s, d) in sorted(rows): f.write(f'{s},{d},{rows[(s, d)]}\n')
by = {}
for (s, d) in rows: by.setdefault(s, []).append(d)
print(len(rows), 'events;', len(by), 'symbols')
for s in sorted(by): print(f'{s}:{len(by[s])}:{min(by[s])}..{max(by[s])}', end='  ')
print()
