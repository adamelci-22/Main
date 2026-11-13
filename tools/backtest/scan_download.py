#!/usr/bin/env python3
"""Data for the stock-scanner research (governor 2026-11-13). Massive REST, key from env MASSIVE_API_KEY (never printed).
    python3 -I tools/backtest/scan_download.py OUT_DIR START END
1. all-stock daily bars per day (grouped), 2. ticker types (common stock / ADR only), 3. each day's candidates known at 9:30:
prior close >= $5, 20-day average dollar volume >= $30M, top 12 gap-ups (>= +2%) and top 6 gap-downs (<= -3%) by gap / ATR%,
4. their 5-minute bars (regular hours + premarket volume/high) and 5. news published since the prior close (titles + sentiment).
Tickers no longer listed today are missing from the type map and are skipped (mild survivorship bias). Data stay out of the repo."""
import concurrent.futures as cf, gzip, json, os, re, statistics as st, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
K = os.environ['MASSIVE_API_KEY']; ET = ZoneInfo('America/New_York'); B = 'https://api.massive.com'
OUT, START, END = sys.argv[1], sys.argv[2], sys.argv[3]


def get(url):
    for i in range(6):
        try: return json.loads(urllib.request.urlopen(url + ('&' if '?' in url else '?') + 'apiKey=' + K, timeout=60).read())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(1.5 * 2 ** i); continue
            return {'status': 'ERR', 'code': e.code}
        except Exception: time.sleep(2 ** i)
    return {'status': 'ERR', 'code': -1}


def daily(d):
    j = get(f"{B}/v2/aggs/grouped/locale/us/market/stocks/{d}?adjusted=true")
    return d, {r['T']: (r['o'], r['h'], r['l'], r['c'], r['v']) for r in j.get('results', []) if re.fullmatch(r'[A-Z]{1,5}', r['T']) and r.get('c', 0) >= 3}


def intraday(T, d):
    j = get(f"{B}/v2/aggs/ticker/{T}/range/5/minute/{d}/{d}?adjusted=true&sort=asc&limit=5000"); bars = []; pv = 0.0; ph = 0.0; pl = 1e18; plast = None
    for r in j.get('results', []) or []:
        e = datetime.fromtimestamp(r['t'] / 1000, timezone.utc).astimezone(ET); m = e.hour * 60 + e.minute
        if 240 <= m < 570: pv += r['v']; ph = max(ph, r['h']); pl = min(pl, r['l']); plast = r['c']
        elif 570 <= m < 960: bars.append([m, r['o'], r['h'], r['l'], r['c'], r['v']])
    return bars, (pv, ph, pl if pl < 1e17 else None, plast)


def news(T, d, prev):
    a = datetime.fromisoformat(prev + 'T16:00:00').replace(tzinfo=ET).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    b = datetime.fromisoformat(d + 'T09:30:00').replace(tzinfo=ET).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    j = get(f"{B}/v2/reference/news?ticker={T}&published_utc.gte={a}&published_utc.lte={b}&limit=20&order=asc"); out = []
    for x in j.get('results', []) or []:
        s = next((i.get('sentiment') for i in x.get('insights', []) or [] if i.get('ticker') == T), None)
        out.append([x.get('published_utc'), (x.get('title') or '')[:140], s, len(x.get('tickers') or [])])
    return out


def main():
    os.makedirs(OUT, exist_ok=True); t0 = time.time()
    types = {}; url = f"{B}/v3/reference/tickers?market=stocks&active=true&limit=1000"
    while url:
        j = get(url)
        for r in j.get('results', []) or []: types[r['ticker']] = r.get('type')
        url = j.get('next_url')
    print(f"types {len(types)} ({time.time() - t0:.0f}s)", flush=True)
    ds = []; d = date.fromisoformat(START)
    while d <= date.fromisoformat(END):
        if d.weekday() < 5: ds.append(d.isoformat())
        d += timedelta(days=1)
    D = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for dd, m in ex.map(daily, ds):
            if len(m) > 2000: D[dd] = m
    days = sorted(D); print(f"daily {len(days)} days {days[0]}..{days[-1]} ({time.time() - t0:.0f}s)", flush=True)
    jobs = []; meta = {}
    for i in range(21, len(days)):
        d = days[i]; prev = days[i - 1]; cands = []
        for T, (o, h, l, c, v) in D[d].items():
            if types.get(T) not in ('CS', 'ADRC') or T not in D[prev]: continue
            pc = D[prev][T][3]
            if pc < 5: continue
            hist = [D[x][T] for x in days[i - 20:i] if T in D[x]]
            if len(hist) < 18: continue
            adv = st.mean(x[3] * x[4] for x in hist)
            if adv < 30e6: continue
            atrp = st.mean((x[1] - x[2]) / x[3] for x in hist[-14:]) * 100; gap = (o / pc - 1) * 100
            if atrp <= 0: continue
            cands.append(dict(T=T, pc=pc, o=o, gap=gap, atrp=atrp, adv=adv, advsh=st.mean(x[4] for x in hist), dh=h, dl=l, dc=c, dv=v))
        up = sorted([c for c in cands if c['gap'] >= 2.0], key=lambda c: -c['gap'] / c['atrp'])[:12]
        dn = sorted([c for c in cands if c['gap'] <= -3.0], key=lambda c: c['gap'] / c['atrp'])[:6]
        meta[d] = dict(prev=prev, n_liquid=len(cands), spy=D[d].get('SPY'), spy_prev=D[prev].get('SPY'), qqq=D[d].get('QQQ'), qqq_prev=D[prev].get('QQQ'))
        for c in up + dn: jobs.append((d, prev, c))
    print(f"candidate ticker-days {len(jobs)} ({time.time() - t0:.0f}s)", flush=True)
    def work(job):
        d, prev, c = job; bars, pm = intraday(c['T'], d); nw = news(c['T'], d, prev); return d, dict(c, bars=bars, pm=pm, news=nw)
    res = {d: [] for d in meta}; n = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for d, c in ex.map(work, jobs):
            res[d].append(c); n += 1
            if n % 500 == 0: print(f"  {n}/{len(jobs)} ({time.time() - t0:.0f}s)", flush=True)
    json.dump(dict(days=sorted(meta), meta=meta, cands=res), gzip.open(os.path.join(OUT, 'scan.json.gz'), 'wt'))
    ok = sum(len(c['bars']) >= 70 for v in res.values() for c in v); nn = sum(bool(c['news']) for v in res.values() for c in v)
    print(f"done: {len(meta)} days, {n} ticker-days, {ok} with full bars, {nn} with news ({time.time() - t0:.0f}s)", flush=True)


if __name__ == '__main__':
    main()
