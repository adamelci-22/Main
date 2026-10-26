#!/usr/bin/env python3
"""Convert the Massive CSV download (data/m5/*.csv, data/d1/*.csv; 5-minute and daily bars, regular hours, split-adjusted) into the backtest's formats.
    /usr/bin/python3 -I tools/backtest/massive_load.py DATA_DIR OUT_5M.json.gz OUT_DAILY.json.gz
OUT_5M    {sym: {day: [[hhmm_utc, o, h, l, c, v], ...]}}   like data/bt_5m.json.gz (day = New York date, bar time = UTC start of the bar)
OUT_DAILY {sym: [[date, o, h, l, c, v], ...]}               like data/bt_daily.json.gz
Prices are used as delivered (adjusted=true). Split handling is checked by massive_checks.py, not re-done here.
"""
import csv, datetime as dt, glob, gzip, json, os, sys


def main(src, out5, outd):
    m5, d1 = {}, {}
    for f in sorted(glob.glob(os.path.join(src, 'm5', '*.csv'))):
        s = os.path.basename(f)[:-4]; days = {}
        for r in csv.DictReader(open(f)):
            t = dt.datetime.fromtimestamp(int(r['ts_utc_ms']) / 1000, dt.timezone.utc)
            days.setdefault(r['et'][:10], []).append([t.strftime('%H:%M'), float(r['o']), float(r['h']), float(r['l']), float(r['c']), int(float(r['v']))])
        m5[s] = days
    for f in sorted(glob.glob(os.path.join(src, 'd1', '*.csv'))):
        s = os.path.basename(f)[:-4]
        d1[s] = [[r['date_et'], float(r['o']), float(r['h']), float(r['l']), float(r['c']), int(float(r['v']))] for r in csv.DictReader(open(f))]
    json.dump(m5, gzip.open(out5, 'wt')); json.dump(d1, gzip.open(outd, 'wt'))
    print(f"{len(m5)} symbols, {sum(len(v) for v in m5.values())} symbol-days -> {out5}; {len(d1)} daily series -> {outd}")


if __name__ == '__main__':
    main(*sys.argv[1:4])
