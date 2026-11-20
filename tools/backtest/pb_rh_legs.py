#!/usr/bin/env python3
"""PULLBACK fund-by-fund check on the Robinhood 5-minute cache (governor 2026-11-20: "run all of them"). Research only.
The single-stock legs NVDQ NVD MSFU SSG have no five-year bars, so the only evidence is the Robinhood cache (about 8 months, 2026-03..10)
plus the live record. Per leg: trades, win rate, average, profit factor, sum (PULLBACK alone, live rules). Then PULLBACK alone with each
leg dropped, as account return (one position at a time). Small samples: read as a screen, not a verdict.
    python3 -I tools/backtest/pb_rh_legs.py > tools/backtest/results/pb_rh_legs_2026-11-20.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tune_book as TB, pb_exit_screen as PS, entry_pb as EP, book_compare as BC
ds, days = TB.ds_r, TB.days_r; LEGS = list(PS.LEGS_RH)


def trades(legs):
    out = []
    for t in TB.pb_entries(ds, days, legs, dict(EP.LIVE)):
        m = PS.manage(t, BC.RUN); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1, proxy=t['proxy']))
    return out


def pf(a): g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 99.0


def acct(T):
    r = TB.account(days, {}, TB.byday(T)); return (np.prod(1 + r) - 1) * 100, float((1 - np.cumprod(1 + r) / np.maximum.accumulate(np.cumprod(1 + r))).max() * 100)


ALL = trades(LEGS); a0, d0 = acct(ALL)
print(__doc__.split('\n')[0]); print(f"   cache {days[0]}..{days[-1]} ({len(days)} sessions)\n")
print(f"   {'leg':<6}{'trades':>7}{'win':>6}{'avg':>8}{'PF':>6}{'sum %':>8}")
for p in LEGS:
    x = [t['pct'] for t in ALL if t['proxy'] == p]
    if x: print(f"   {p:<6}{len(x):>7}{100 * np.mean([v > 0 for v in x]):>5.0f}%{np.mean(x):>+7.2f}%{pf(x):>6.2f}{sum(x):>+8.1f}")
print(f"\n   PULLBACK alone, all 8 legs: {a0:+.1f}% over the cache, max drawdown {d0:.1f}%")
for p in LEGS:
    a, d = acct([t for t in ALL if t['proxy'] != p]); print(f"   without {p:<5} {a:+7.1f}%  ({a - a0:+5.1f})  DD {d:.1f}%")
