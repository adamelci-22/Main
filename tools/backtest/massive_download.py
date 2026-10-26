#!/usr/bin/env python3
"""Download Massive 5-minute bars (regular hours, split-adjusted), daily bars and the splits list for a set of tickers, into OUT/m5, OUT/d1, OUT/splits.
    MASSIVE_API_KEY=... /usr/bin/python3 -I tools/backtest/massive_download.py START OUT [TICKERS]
START is YYYY-MM-DD. TICKERS is a comma list, or LIVE (the 19 live tickers: six proxies, twelve legs, UVXY; default), or ALL (the 37-ticker research set).
The key is read from the environment and is never written to disk. Bars are fetched a quarter at a time, six tickers in parallel, 429s retried.
The data feeds tools/backtest/massive_load.py. A ticker with no bars before it existed returns fewer quarters; that is expected (LABU and LABD start in 2015-05).
If the plan does not include the date range the API answers NOT_AUTHORIZED and the script stops with that message.
"""
import csv, datetime as dt, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import requests
from zoneinfo import ZoneInfo
K = os.environ["MASSIVE_API_KEY"]; B = "https://api.massive.com"; ET = ZoneInfo("America/New_York")
LIVE = ["QQQ", "SOXX", "IWM", "XLK", "XBI", "XLF", "TQQQ", "SQQQ", "SOXL", "SOXS", "TNA", "TZA", "TECL", "TECS", "LABU", "LABD", "FAS", "FAZ", "UVXY"]
ALL = LIVE + ["SPY", "TLT", "GLD", "KRE", "VIXY", "SPXU", "SDS", "QID", "SRTY", "SDOW", "ERY", "DRIP", "DUST", "TMV", "UVIX", "SVIX", "NUGT", "TMF"]
S = requests.Session()


class NotAuthorized(Exception): pass


def get(url, params=None):
    for i in range(6):
        try:
            r = S.get(url, params=params, timeout=60)
            if r.status_code == 429: time.sleep(2 + i * 2); continue
            j = r.json()
            if j.get("status") == "NOT_AUTHORIZED": raise NotAuthorized(j.get("message"))
            r.raise_for_status(); return j
        except NotAuthorized: raise
        except Exception:
            if i == 5: raise
            time.sleep(1 + i * 2)


def pull(path, params):
    rows = []; j = get(B + path, dict(params, apiKey=K))
    while True:
        rows += j.get("results", []); n = j.get("next_url")
        if not n: break
        j = get(n, {"apiKey": K})
    return rows


def quarters(start, end):
    d = start
    while d <= end:
        m = d.month + 3; y = d.year + (m - 1) // 12; m = (m - 1) % 12 + 1
        e = min(dt.date(y, m, 1) - dt.timedelta(days=1), end); yield d, e; d = e + dt.timedelta(days=1)


def do(t, start, end, out):
    try:
        rows = []
        for a, b in quarters(start, end): rows += pull(f"/v2/aggs/ticker/{t}/range/5/minute/{a}/{b}", {"adjusted": "true", "sort": "asc", "limit": 50000})
        seen = set(); n = 0
        with open(f"{out}/m5/{t}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["ts_utc_ms", "et", "o", "h", "l", "c", "v", "vw", "n"])
            for r in rows:
                if r["t"] in seen: continue
                seen.add(r["t"]); x = dt.datetime.fromtimestamp(r["t"] / 1000, ET); hm = x.hour * 60 + x.minute
                if not (570 <= hm < 960): continue
                w.writerow([r["t"], x.strftime("%Y-%m-%d %H:%M"), r["o"], r["h"], r["l"], r["c"], r["v"], r.get("vw", ""), r.get("n", "")]); n += 1
        d = pull(f"/v2/aggs/ticker/{t}/range/1/day/{start}/{end}", {"adjusted": "true", "sort": "asc", "limit": 50000})
        with open(f"{out}/d1/{t}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["date_et", "o", "h", "l", "c", "v", "vw", "n"])
            for r in d: w.writerow([dt.datetime.fromtimestamp(r["t"] / 1000, dt.timezone.utc).astimezone(ET).strftime("%Y-%m-%d"), r["o"], r["h"], r["l"], r["c"], r["v"], r.get("vw", ""), r.get("n", "")])
        sp = pull("/v3/reference/splits", {"ticker": t, "limit": 1000}); json.dump(sp, open(f"{out}/splits/{t}.json", "w"))
        print(f"{t} m5_rth={n} d1={len(d)} splits={len(sp)}", flush=True)
    except NotAuthorized as e:
        print(f"{t} NOT_AUTHORIZED: {e}", flush=True); return 'na'
    except Exception as e:
        print(f"{t} FAIL {e}", flush=True)


if __name__ == "__main__":
    start = dt.date.fromisoformat(sys.argv[1]); out = sys.argv[2]; arg = sys.argv[3] if len(sys.argv) > 3 else "LIVE"
    tick = LIVE if arg == "LIVE" else ALL if arg == "ALL" else arg.split(",")
    for sub in ("m5", "d1", "splits"): os.makedirs(f"{out}/{sub}", exist_ok=True)
    with ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda t: do(t, start, dt.date.today(), out), tick))
    print("NOT_AUTHORIZED: the plan does not include data this far back." if 'na' in res else "DONE", flush=True)
