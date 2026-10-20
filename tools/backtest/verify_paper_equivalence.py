#!/usr/bin/env python3
"""Replay tools/live/paper.py's simulate() over every backtest day and compare it trade by trade with final_system.py.
    python3 tools/backtest/verify_paper_equivalence.py > tools/backtest/results/verify_paper_equivalence.txt
"""
import os, sys, statistics as st, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'live'))
import manual as m, pb_final as PBF, mixed as MXD, final_system as FS
import paper as P
from lab import get_data

D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
f, p = FS.cands(D, days)
for cap in (3, 99):
    a = MXD.account(D, days, f + p, max_entries=cap)
    print(f"backtest account, max_entries={cap}: {len(a['taken'])} trades, {st.mean(a['daily'].values()):+.4f}%/day, ret {a['ret']:+.2f}%")
bt = MXD.account(D, days, f + p)          # final_system's default (max_entries=3)
syms = set(s for s in D.bars)
eq = 2000.0; streak = 0; mism = []; ptaken = []
for d in days:
    i = D.days.index(d); pd = D.days[i - 1]
    today = {s: D.bars[s][d][:48] for s in syms if d in D.bars[s]}
    prev = {s: D.bars[s][pd] for s in syms if pd in D.bars[s]}
    pri = D.prior(d, 20)
    base = {q: [st.mean(D.cum[q][x][k] for x in pri) for k in range(79)] for q in list(P.FADE_ROWS) + ['NVDA'] if q in D.cum and all(x in D.cum[q] for x in pri)}
    P.FLOOR_TARGET = True          # the backtest (pb_final TARGET_MODE floor) applies the v5.1 rounding on every day
    taken, skipped, sig, eq2 = P.simulate(today, prev, 48, eq, base, streak)
    for c in taken: ptaken.append((d, c['system'], c['ticker'], c['k'], c['xbar'], round(c['pct'], 3), round(c['usd'], 2)))
    eq = eq2; streak = taken[-1]['streak'] if taken else streak
btk = [(x['day'], x['sys'], x['name'], x['k'], x['xbar'], round(x['pct'], 3), round(x['usd'], 2)) for x in bt['taken']]
print(f"\npaper.py replay: {len(ptaken)} trades, final equity ${eq:,.2f} ({(eq/2000-1)*100:+.2f}%)   backtest: {len(btk)} trades, ${2000*(1+bt['ret']/100):,.2f}")
# compare by (day, system, k, xbar, pct) ignoring the name format (backtest FADE name = proxy+/-; paper = leg ticker)
pk = {(x[0], x[1], x[3], x[4], x[5]) for x in ptaken}; bk = {(x[0], x[1], x[3], x[4], x[5]) for x in btk}
only_p = sorted(pk - bk); only_b = sorted(bk - pk)
print(f"trades in paper.py only: {len(only_p)}; in backtest only: {len(only_b)}")
for x in only_p[:20]: print("   paper only:   ", x)
for x in only_b[:20]: print("   backtest only:", x)
from collections import Counter
cnt = Counter(x[0] for x in ptaken); print(f"days with >3 paper entries: {[(d, n) for d, n in cnt.items() if n > 3]}")
