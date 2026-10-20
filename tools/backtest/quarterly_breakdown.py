#!/usr/bin/env python3
"""Quarter-by-quarter breakdown of final_system (on time, $2,000 start, compounding).
    python3 tools/backtest/quarterly_breakdown.py > tools/backtest/results/quarterly_breakdown.txt
"""
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, final_system as FS
from lab import get_data

def q(day):
    y, mo = day[:4], int(day[5:7]); return f"{y}-Q{(mo-1)//3+1}"

D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
f, p = FS.cands(D, days)
a = MXD.account(D, days, f + p); tk = a['taken']; dl = a['daily']
daypct = dl
qs = sorted({q(d) for d in days}); eq = 2000.0
print("Quarters, on time, $2,000 start, compounding. Q1 = Mar 3-31 only, Q4 = Oct 1-14 only (partial).\n")
print("quarter    days  trades(FADE/PB)  win%   quarter %   avg day %  winning/losing days   FADE $   PB $    equity end")
for Q in qs:
    ds = [d for d in days if q(d) == Q]; t = [x for x in tk if q(x['day']) == Q]
    fa = [x for x in t if x['sys'] == 'FADE']; pb = [x for x in t if x['sys'] != 'FADE']
    start = eq; usd = sum(x['usd'] for x in t); eq += usd
    wn = sum(1 for d in ds if daypct[d] > 1e-9); ls = sum(1 for d in ds if daypct[d] < -1e-9)
    print(f"{Q}   {len(ds):3d}   {len(t):3d} ({len(fa)}/{len(pb)})     {100*sum(x['usd']>0 for x in t)/max(1,len(t)):3.0f}%   {usd/start*100:+7.1f}%    {st.mean(daypct[d] for d in ds):+.3f}%      {wn}/{ls}            {sum(x['usd'] for x in fa):+6.0f}  {sum(x['usd'] for x in pb):+6.0f}   ${eq:,.0f}")
full = [Q for Q in qs if Q in ('2026-Q2', '2026-Q3')]
ds = [d for d in days if q(d) in full]
print(f"\nFull quarters only (Q2+Q3, {len(ds)} days): average day {st.mean(daypct[d] for d in ds):+.3f}%")
