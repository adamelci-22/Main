"""Fetch full-day (UTC) 5-minute candles, Fri/Sat/Sun of each weekend 2026-03-06..2026-10-11, for BTC ETH SOL DOGE PEPE (Coinbase public API). Cache: crypto/full_<coin>.json  {date: [[o,h,l,c,v]*288]}"""
import json, time, urllib.request, datetime as dt, os, sys
def fetch(coin, day):
    s = dt.datetime.combine(day, dt.time(0, 0), dt.timezone.utc); e = s + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    url = f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity=300&start={s.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={e.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    for _ in range(4):
        try: r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'x'}), timeout=30)); break
        except Exception as ex: err = ex; time.sleep(1.5)
    else: return None
    if not isinstance(r, list) or not r: return None
    t0 = int(s.timestamp()); by = {c[0]: c for c in r}; out = []
    for i in range(288):
        c = by.get(t0 + 300 * i)
        if c: out.append([c[3], c[2], c[1], c[4], c[5]])
        elif out: p = out[-1][3]; out.append([p, p, p, p, 0.0])
        else: out.append(None)
    # backfill leading gaps
    first = next((x for x in out if x), None)
    if first is None: return None
    out = [x if x else [first[0]] * 4 + [0.0] for x in out]
    return out
for coin in sys.argv[1:]:
    f = f'crypto/full_{coin}.json'; data = json.load(open(f)) if os.path.exists(f) else {}
    d = dt.date(2026, 3, 6); end = dt.date(2026, 10, 11); miss = 0
    while d <= end:
        if d.weekday() in (4, 5, 6) and d.isoformat() not in data:
            b = fetch(coin, d)
            if b: data[d.isoformat()] = b
            else: miss += 1
            time.sleep(0.12)
        d += dt.timedelta(days=1)
    json.dump(data, open(f, 'w')); print(coin, len(data), 'days, missing', miss, flush=True)
