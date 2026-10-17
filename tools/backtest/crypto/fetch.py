"""Fetch 5-minute BTC-USD / ETH-USD candles (Coinbase public API) for 09:30-16:00 ET on every Fri/Sat/Sun, 2026-03-06..2026-10-11. Cached to crypto/bars_<coin>.json"""
import json, time, urllib.request, datetime as dt, os
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York'); UTC = ZoneInfo('UTC')
def fetch(coin, day):
    s = dt.datetime.combine(day, dt.time(9, 30), ET).astimezone(UTC); e = s + dt.timedelta(minutes=5 * 78)
    url = f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity=300&start={s.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={(e - dt.timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    for _ in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'x'}), timeout=30)); break
        except Exception: time.sleep(2)
    else: return None
    t0 = int(s.timestamp()); by = {c[0]: c for c in r}
    out = []
    for i in range(78):                                   # [open, high, low, close, volume]; fill gaps with previous close
        c = by.get(t0 + 300 * i)
        if c: out.append([c[3], c[2], c[1], c[4], c[5]])
        elif out: p = out[-1][3]; out.append([p, p, p, p, 0.0])
        else: out.append(None)
    return out
day = dt.date(2026, 3, 6); end = dt.date(2026, 10, 11)
for coin in ('BTC', 'ETH'):
    f = f'crypto/bars_{coin}.json'; data = json.load(open(f)) if os.path.exists(f) else {}
    d = day
    while d <= end:
        if d.weekday() in (4, 5, 6) and d.isoformat() not in data:
            b = fetch(coin, d)
            if b and b[0] is not None: data[d.isoformat()] = b
            time.sleep(0.15)
        d += dt.timedelta(days=1)
    json.dump(data, open(f, 'w')); print(coin, len(data), 'days')
