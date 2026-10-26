#!/usr/bin/env python3
"""Massive (Polygon) REST -> 5-minute regular-hours bars in bt_5m.json.gz format (split-adjusted, UTC bar-start 'HH:MM').
    /usr/bin/python3 -I tools/backtest/massive_rest.py OUT.json.gz START END SYM [SYM ...]      # key from env MASSIVE_API_KEY (never printed)
Starter plan reaches back about 5 years; older requests return 403 NOT_AUTHORIZED. Data stay out of the repo."""
import collections, gzip, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
K = os.environ['MASSIVE_API_KEY']; ET = ZoneInfo('America/New_York')


def get(url):
    for i in range(5):
        try: return json.loads(urllib.request.urlopen(url + ('&' if '?' in url else '?') + 'apiKey=' + K, timeout=60).read())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 ** i); continue
            return {'status': 'ERR', 'code': e.code}
        except Exception: time.sleep(2 ** i)
    return {'status': 'ERR', 'code': -1}


def bars(sym, a, b):
    out = collections.defaultdict(list); url = f"https://api.massive.com/v2/aggs/ticker/{sym}/range/5/minute/{a}/{b}?adjusted=true&sort=asc&limit=50000"
    while url:
        j = get(url)
        if j.get('status') not in ('OK', 'DELAYED'): return out, j
        for r in j.get('results', []):
            t = datetime.fromtimestamp(r['t'] / 1000, timezone.utc); e = t.astimezone(ET)
            if e.weekday() > 4 or not (570 <= e.hour * 60 + e.minute < 960): continue
            out[e.strftime('%Y-%m-%d')].append([t.strftime('%H:%M'), r['o'], r['h'], r['l'], r['c'], r['v']])
        url = j.get('next_url')
    return out, {'status': 'OK'}


if __name__ == '__main__':
    out_path, a, b, *syms = sys.argv[1:]; res = {}
    for s in syms:
        d, st = bars(s, a, b)
        if st.get('status') != 'OK': print(f"{s}: {st}"); continue
        res[s] = dict(d); print(f"{s}: {len(d)} days, {sum(len(v) for v in d.values())} bars, {min(d) if d else '-'}..{max(d) if d else '-'}", flush=True)
    json.dump(res, gzip.open(out_path, 'wt'))
