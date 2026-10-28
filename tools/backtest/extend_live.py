#!/usr/bin/env python3
"""Append live sessions to the research dataset (governor instruction 2026-10-28).
    python3 tools/backtest/extend_live.py DUMP [DUMP ...]
Reads saved get_equity_historicals dumps (interval 5minute) and merges every COMPLETE session in them (QQQ has all 78 regular-hours bars) into
tools/backtest/data/live_5m.json.gz, same layout as bt_5m.json.gz: {sym: {day: [[hhmm, o, h, l, c, v], ...]}} (real bars only).
The base file bt_5m.json.gz is never touched (19 MB); the live file grows by about 0.3 MB a month. Dumps without QQQ (watchlist symbols) are merged into sessions the live file already holds (supplement mode). Days already COMPLETE in bt_5m.json.gz are skipped; a partial base day is completed here (the loader prefers the live file for a day it holds).
Loaded only on request: backtest.load(live=True) / lab.get_data(live=True), which tools/live/improve.py uses. Old research scripts keep the base file only,
so their stored results stay reproducible. A session is added once it is complete, so at each 13:30 close the dumps of that day add the PRIOR day
(the dumps start at the prior day's 9:30). Reporting/research only: it changes no order, rule or state."""
import glob, gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BASE, LIVE = f'{HERE}/data/bt_5m.json.gz', f'{HERE}/data/live_5m.json.gz'
files = [f for g in sys.argv[1:] for f in glob.glob(g)]
if not files: sys.exit(__doc__)
five = {}
for f in files:
    try: res = json.load(open(f))['data']['results']
    except Exception as e: print(f'skip {os.path.basename(f)}: {e}'); continue
    for r in res:
        if r.get('interval') != '5minute': continue
        for b in r['bars']:
            if b.get('interpolated') or not b['volume']: continue
            ts = b['begins_at']
            five.setdefault(r['symbol'], {}).setdefault(ts[:10], {})[ts[11:16]] = [float(b['open_price']), float(b['high_price']), float(b['low_price']), float(b['close_price']), b['volume']]
have = json.load(gzip.open(LIVE)) if os.path.exists(LIVE) else {}
if 'QQQ' not in five:      # supplement mode (v5.2.32): dumps of watchlist symbols only add their bars to sessions the live file already holds
    if not have: sys.exit('no QQQ 5-minute bars in the dumps')
    held, n = set(have['QQQ']), 0
    for s_, days in five.items():
        for d, bars in days.items():
            if d in held and len(bars) >= 70: have.setdefault(s_, {})[d] = [[k] + v for k, v in sorted(bars.items())]; n += 1
    have = {s_: dict(sorted(d_.items())) for s_, d_ in have.items()}
    json.dump(have, gzip.open(LIVE, 'wt'))
    sys.exit(f'supplement mode: {n} symbol-sessions added; symbols now {len(have)}')
base_days = {d for d, b in json.load(gzip.open(BASE))['QQQ'].items() if len(b) >= 78}      # a partial base day (e.g. 10-15) is not covered: the live file completes it
complete = sorted(d for d, bars in five['QQQ'].items() if len(bars) >= 78 and d not in base_days)
added = []
for d in complete:
    for s, days in five.items():
        if d in days: have.setdefault(s, {})[d] = [[k] + v for k, v in sorted(days[d].items())]
    if d not in {x for x in have.get('QQQ', {}) if x in added}: added.append(d)
have = {s: dict(sorted(days.items())) for s, days in have.items()}
json.dump(have, gzip.open(LIVE, 'wt'))
alld = sorted(have['QQQ'])
print(f"live sessions in {os.path.relpath(LIVE)}: {len(alld)} ({alld[0]} .. {alld[-1]}); this run touched {len(complete)} complete day(s): {', '.join(complete) or 'none'}; "
      f"skipped incomplete: {', '.join(sorted(d for d in five['QQQ'] if d not in complete and d not in base_days)) or 'none'}; symbols {len(have)}")
