#!/usr/bin/env python3
"""Skip-Fridays check for the LIVE combined system (FADE + PULLBACK) on Robinhood and Massive.  /usr/bin/python3 -I tools/backtest/friday_check.py M5.json.gz"""
import sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_bt as MB
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
for kind in ('rh', 'massive'):
    D = MB.load(kind); days = D.days[1:]; f, p = MB.cands(D, days)
    print(f"== {'Robinhood' if kind == 'rh' else 'Massive 5y'} {days[0]}..{days[-1]} (H1/H2 = first/second half of days)")
    for tag, cs in (('FADE + PULLBACK', f + p), ('FADE alone', f), ('PULLBACK alone', p)):
        MB.summ(f'{tag}  live', D, days, cs)
        MB.summ(f'{tag}  no FADE Fridays', D, days, [c for c in cs if not (c['sys'] == 'FADE' and fri(c['day']))])
        MB.summ(f'{tag}  no Fridays at all', D, days, [c for c in cs if not fri(c['day'])])
