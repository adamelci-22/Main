#!/usr/bin/env python3
"""Entry filters suggested by failure_study (box width, leg, Friday) on live FADE with live exits.  /usr/bin/python3 -I tools/backtest/entry_filters.py {rh|M5.json.gz}"""
import os, sys, datetime as dt
from dataclasses import replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'} {days[0]}..{days[-1]}; split {SPLIT}.  cell: %/day  trades  win%  maxDD   | first half | second half | all")
def show(tag, c, nofri=False):
    out = []
    for dd in (H1, H2, days):
        d2 = [d for d in dd if not (nofri and dt.date.fromisoformat(d).weekday() == 4)]
        T = F.trades(ds, d2, syms, c, ctx); a = F.account(ds, dd, T); out.append(F.stat(a))
    print(f"{tag:<36}" + ''.join(f" | {s['avg']:+.3f} {s['n']:4d}t {s['win']:2.0f}% DD{s['mdd']:4.1f}" for s in out))
b = F.P()
show('LIVE', b)
for m in (0.5, 0.6, 0.7, 0.8, 1.0): show(f'box width >= {m}%', replace(b, minbox=m))
show('bear leg only (fade up-breaks)', replace(b, side=-1))
show('bull leg only (fade down-breaks)', replace(b, side=1))
show('no Fridays', b, nofri=True)
show('box >= 0.7% + bear leg only', replace(b, minbox=0.7, side=-1))
