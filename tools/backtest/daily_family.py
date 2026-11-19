#!/usr/bin/env python3
"""Expanded backtest 2018-2026 for the 9:35 family and the overnight leg on DAILY bars (governor 2026-11-19: "expand the back test").
Research only. The Massive plan covers about five years (NOT_AUTHORIZED before 2021-11) and Robinhood has no real 5-minute bars that far
back, so PULLBACK and RELVAL (intraday signals) cannot be tested before 2022. The IBS family and OVERNIGHT need only daily bars:
  IBS-LONG  prior close above its 20-close average (N2.up) and prior-day IBS < 0.10 -> 3x long leg
  MIRROR    prior close at or below its 20-close average and prior-day IBS > 0.95 -> 3x inverse leg
  DIP       prior close above its 50-close average and 2-day RSI < 10 -> 3x long leg
  entry at the day's OPEN (live: the 9:35 open, 5 minutes later), stop 1% of the proxy (3% on the leg) if the day's low/high reaches it,
  else out at the CLOSE (live: 15:55). One trade a day: candidates ranked by the PRIOR day's volume / its 20-day average (live: first
  5-minute relative volume, not available on daily bars). Leg = 3 x the proxy move minus 0.06%, full cash (3% risk on a 3% leg stop).
  OVERNIGHT close above its 20-close average and today's IBS < 0.10 -> long leg from the close to the next OPEN at 50% of cash
  (live: 15:55 to 9:35), highest same-day volume ratio first.
Book = (1 + family day) x (1 + 0.5 x overnight) - 1. No PULLBACK or RELVAL here. Check: the same code on 2022-2026 against the 5-minute
backtest of the same systems. 2018-2021 were never used to build or tune any rule: they are out of sample.
    python3 -I tools/backtest/daily_family.py ROBINHOOD_DAILY_DUMP.json > tools/backtest/results/daily_family_2026-11-19.txt"""
import json, os, statistics as st, sys
from collections import defaultdict
import numpy as np
COST, LEV, STOP = 0.06, 3, 0.01
import gzip
raw = json.load(gzip.open(sys.argv[1]) if sys.argv[1].endswith('.gz') else open(sys.argv[1]))['data']['results']
D = {}
for r in raw:
    D[r['symbol']] = [(b['begins_at'][:10], float(b['open_price']), float(b['high_price']), float(b['low_price']), float(b['close_price']), float(b['volume'])) for b in r['bars'] if not b.get('interpolated')]
PX = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; days = sorted({x[0] for p in PX for x in D[p]}); idx = {p: {x[0]: i for i, x in enumerate(D[p])} for p in PX}


def rsi2(c):
    ag = al = 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 2: ag += g / 2; al += lo / 2
        else: ag = (ag + g) / 2; al = (al + lo) / 2
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def ibs(x): return (x[4] - x[3]) / (x[2] - x[3]) if x[2] > x[3] else None


def family(d):
    """Candidates for day d (signals from the prior session), each with its leg %."""
    out = []
    for p in PX:
        i = idx[p].get(d)
        if i is None or i < 51: continue
        b = D[p]; pr = b[i - 1]; c = [x[4] for x in b[:i]]
        v = ibs(pr)
        if v is None: continue
        up20 = c[-1] > st.mean(c[-20:]); up50 = c[-1] > st.mean(c[-50:]); r2 = rsi2(c[-12:])
        kinds = []
        if up20 and v < 0.10: kinds.append(('IBS-LONG', 1))
        if (not up20) and v > 0.95: kinds.append(('MIRROR', -1))
        if up50 and r2 < 10: kinds.append(('DIP', 1))
        if not kinds: continue
        kind, s = kinds[0] if kinds[0][0] != 'DIP' or len(kinds) == 1 else kinds[0]
        o, h, l, cl = b[i][1], b[i][2], b[i][3], b[i][4]
        stopped = (l <= o * (1 - STOP)) if s > 0 else (h >= o * (1 + STOP))
        move = -STOP if stopped else s * (cl / o - 1)
        vr = pr[5] / st.mean(x[5] for x in b[i - 21:i - 1]) if i > 21 else 0
        out.append(dict(p=p, kind=kind, s=s, pct=LEV * move * 100 - COST, rv=vr, stopped=stopped))
    return out


def overnight(d):
    out = []
    for p in PX:
        i = idx[p].get(d)
        if i is None or i < 21 or i + 1 >= len(D[p]): continue
        b = D[p]; x = b[i]; c = [y[4] for y in b[:i + 1]]; v = ibs(x)
        if v is None or not (c[-1] > st.mean(c[-20:]) and v < 0.10): continue
        nxt = b[i + 1]; out.append(dict(p=p, pct=max(LEV * (nxt[1] / x[4] - 1) * 100, -30.0) - COST, rv=x[5] / st.mean(y[5] for y in b[i - 20:i])))
    return out


fam_r, ovn_r, trades = {}, {}, []
for d in days:
    c = family(d)
    if c:
        t = max(c, key=lambda z: z['rv']); fam_r[d] = t['pct'] / 100; trades.append(dict(t, day=d))
    o = overnight(d)
    if o: ovn_r[d] = max(o, key=lambda z: z['rv'])['pct'] / 100
YRS = [str(y) for y in range(2018, 2027)]


def yret(f): return {y: (np.prod([1 + f(d) for d in days if d[:4] == y]) - 1) * 100 for y in YRS}


def ydd(f):
    out = {}
    for y in YRS:
        eq = np.cumprod([1 + f(d) for d in days if d[:4] == y]); out[y] = float((1 - eq / np.maximum.accumulate(eq)).max() * 100) if len(eq) else 0
    return out


book = lambda d: (1 + fam_r.get(d, 0)) * (1 + 0.5 * ovn_r.get(d, 0)) - 1
print(__doc__.split('\n')[0]); print(f"   daily bars {days[0]}..{days[-1]} ({len(days)} sessions); 2018-2021 = never used to build any rule\n")
print(f"   {'':<30}" + ''.join(f"{y:>8}" for y in YRS))
for name, f in (('9:35 family alone', lambda d: fam_r.get(d, 0)), ('overnight leg alone (50%)', lambda d: 0.5 * ovn_r.get(d, 0)), ('family + overnight', book)):
    y = yret(f); dd = ydd(f)
    print(f"   {name:<30}" + ''.join(f"{y[k]:+8.1f}" for k in YRS)); print(f"   {'   max drawdown in the year':<30}" + ''.join(f"{dd[k]:8.1f}" for k in YRS))
print('\nBY SYSTEM (trades taken, win rate, average leg %, profit factor), 2018-2021 vs 2022-2026')
for k in ('IBS-LONG', 'MIRROR', 'DIP'):
    for a, b, lab in (('2018', '2021', '2018-21'), ('2022', '2026', '2022-26')):
        p = [t['pct'] for t in trades if t['kind'] == k and a <= t['day'][:4] <= b]
        if not p: continue
        g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
        print(f"   {k:<9} {lab}: n {len(p):>3}  win {100 * np.mean([x > 0 for x in p]):3.0f}%  avg {np.mean(p):+.2f}%  PF {g / l if l else 99:.2f}")
for a, b, lab in (('2018', '2021', '2018-21'), ('2022', '2026', '2022-26')):
    p = [ovn_r[d] * 100 for d in ovn_r if a <= d[:4] <= b]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
    print(f"   OVERNIGHT {lab}: n {len(p):>3}  win {100 * np.mean([x > 0 for x in p]):3.0f}%  avg {np.mean(p):+.2f}% (full leg)  PF {g / l if l else 99:.2f}")
eq = np.cumprod([1 + book(d) for d in days if d >= '2018']); print(f"\n   family + overnight, whole 2018-2026: x{eq[-1]:.1f}, max drawdown {(1 - eq / np.maximum.accumulate(eq)).max() * 100:.1f}%")
for a, b in (('2018', '2021'), ('2022', '2026')):
    e = np.cumprod([1 + book(d) for d in days if a <= d[:4] <= b]); print(f"   {a}-{b}: x{e[-1]:.2f}, max drawdown {(1 - e / np.maximum.accumulate(e)).max() * 100:.1f}%")
