#!/usr/bin/env python3
"""Load a Databento EQUS.MINI ohlcv-1m batch (DBN) into the backtest's 5-minute format, regular hours only, split-adjusted.
    /usr/bin/python3 tools/backtest/databento_load.py DBN_FILE OUT.json.gz
Output {sym: {day: [[hhmm_utc, o, h, l, c, v], ...]}} like data/bt_5m.json.gz (day = New York date, bar time = UTC start of the 5-minute bar).
Splits: Databento prices are raw. A split is flagged when a day's first open vs the previous close is within 15% of a standard ratio (2,3,4,5,10,15,20,25,30,40,50,100
reverse, or the inverse for forward splits). Earlier prices are scaled to match the latest share count (volume scaled the other way).
KNOWN_NOT_SPLITS lists real gaps that look like a split (a day-one VIX spike).
"""
import sys, math, json, gzip
import numpy as np, pandas as pd
import databento as db

STD = [2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 100]
KNOWN_NOT_SPLITS = {('UVIX', '2024-08-05')}


def split_factor(ratio):
    """ratio = first open / previous close. Return the price multiplier for earlier prices (e.g. 10 for 1-for-10 reverse, 1/3 for 3-for-1 forward), or None.
    The nearest standard ratio wins, and it must be within 15%."""
    if ratio >= 1.8:
        n = min(STD, key=lambda n: abs(ratio / n - 1))
        return float(n) if abs(ratio / n - 1) <= 0.15 else None
    if ratio <= 0.55:
        n = min(STD, key=lambda n: abs(ratio * n - 1))
        return 1.0 / n if abs(ratio * n - 1) <= 0.15 else None
    return None


def main(src, out):
    df = db.DBNStore.from_file(src).to_df(price_type='float', pretty_ts=True, map_symbols=True).reset_index()
    ts = df['ts_event'].dt.tz_convert('America/New_York')
    df['day'] = ts.dt.strftime('%Y-%m-%d'); df['hm'] = ts.dt.hour * 60 + ts.dt.minute
    df = df[(df.hm >= 570) & (df.hm < 960)].copy()
    df = df[df.volume > 0].copy()
    events = []
    for s, g in df.groupby('symbol'):
        g = g.sort_values('ts_event')
        daily = g.groupby('day').agg(o=('open', 'first'), c=('close', 'last')).reset_index()
        mult = {}
        cum = 1.0
        days = daily['day'].tolist(); o = daily['o'].values; c = daily['c'].values
        fac = {}
        for i in range(1, len(days)):
            r = o[i] / c[i - 1]
            f = split_factor(r) if (s, days[i]) not in KNOWN_NOT_SPLITS else None
            if f: fac[days[i]] = f; events.append((s, days[i], round(c[i - 1], 3), round(o[i], 3), f))
        adj = np.ones(len(days)); run = 1.0
        for i in range(len(days) - 1, -1, -1):          # multiplier applied to prices on day i = product of factors of all later splits
            adj[i] = run
            if days[i] in fac: run *= fac[days[i]]
        m = dict(zip(days, adj))
        df.loc[g.index, 'adj'] = g['day'].map(m).values
    for c_ in ('open', 'high', 'low', 'close'): df[c_] = df[c_] * df['adj']
    df['volume'] = df['volume'] / df['adj']
    df['b5'] = (df['hm'] // 5) * 5
    agg = df.sort_values('ts_event').groupby(['symbol', 'day', 'b5']).agg(
        o=('open', 'first'), h=('high', 'max'), l=('low', 'min'), c=('close', 'last'), v=('volume', 'sum')).reset_index()
    res = {}
    for s, g in agg.groupby('symbol'):
        res[s] = {}
        for d, gg in g.groupby('day'):
            utc_off = pd.Timestamp(d + ' 12:00', tz='America/New_York').utcoffset().total_seconds() / 3600
            rows = []
            for _, r in gg.iterrows():
                t = int(r.b5) - int(utc_off * 60) * -1 if False else int(r.b5) + int(-utc_off * 60)
                rows.append([f"{t // 60:02d}:{t % 60:02d}", round(float(r.o), 4), round(float(r.h), 4), round(float(r.l), 4), round(float(r.c), 4), int(round(r.v))])
            res[s][d] = rows
    json.dump(res, gzip.open(out, 'wt'))
    print(f"{len(res)} symbols, {sum(len(v) for v in res.values())} symbol-days -> {out}")
    for e in events: print('split', *e)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
