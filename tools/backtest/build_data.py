#!/usr/bin/env python3
"""Merge saved get_equity_historicals dumps into compact backtest data files.
    python3 tools/backtest/build_data.py DUMP_DIR MIN_MTIME_EPOCH
Writes tools/backtest/data/bt_5m.json.gz  {sym: {day: [[hhmm, o,h,l,c,v], ...]}}  (real bars only)
       tools/backtest/data/bt_daily.json.gz {sym: [[day,o,h,l,c,v], ...]}
"""
import glob, gzip, json, os, sys
d, t0 = sys.argv[1], float(sys.argv[2])
five, daily = {}, {}
for f in glob.glob(os.path.join(d, 'mcp-Robinhood-get_equity_historicals-*.txt')):
    if os.path.getmtime(f) < t0: continue
    try: res = json.load(open(f))['data']['results']
    except Exception: continue
    for r in res:
        s = r['symbol']
        for b in r['bars']:
            if b.get('interpolated') or not b['volume']: continue
            row = [float(b['open_price']), float(b['high_price']), float(b['low_price']), float(b['close_price']), b['volume']]
            ts = b['begins_at']
            if r['interval'] == '5minute':
                five.setdefault(s, {}).setdefault(ts[:10], {})[ts[11:16]] = row
            elif r['interval'] == 'day':
                daily.setdefault(s, {})[ts[:10]] = row
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'); os.makedirs(out, exist_ok=True)
F = {s: {day: [[k] + v for k, v in sorted(bars.items())] for day, bars in days.items()} for s, days in five.items()}
D = {s: [[k] + v for k, v in sorted(days.items())] for s, days in daily.items()}
json.dump(F, gzip.open(out + '/bt_5m.json.gz', 'wt'))
json.dump(D, gzip.open(out + '/bt_daily.json.gz', 'wt'))
print('5m syms', len(F), 'daily syms', len(D))
for s in sorted(F): 
    days = F[s]; full = sum(1 for v in days.values() if len(v) == 78)
    print(s, len(days), 'days;', full, 'full;', min(days), max(days))
