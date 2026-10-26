#!/usr/bin/env python3
"""15-minute vs 30-minute opening box for the FADE retest system, same exits, same account.   /usr/bin/python3 -I tools/backtest/box_compare.py M5.json.gz > results/box_compare.txt
Massive full-tape bars 2021-10..2026-10 plus the Robinhood cache for 2026-03..10. Box = first N bars; break window = the 3 bars after the box (live: box 30 min, breaks closing 10:00-10:10, earliest entry 10:10)."""
import collections, math, os, random, statistics as st, sys
from dataclasses import replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
SRC = sys.argv[1]; CUT = '2026-03-01'; LIVE = F.LIVE
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); days = ds.days[21:]
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]; base = F.P()
hhmm = lambda k: f"{(570 + 5 * k) // 60}:{(570 + 5 * k) % 60:02d}"


def run(c, dd=None, T=None, minK=0):
    T = T if T is not None else F.trades(ds, days, LIVE, c, ctx); T = [t for t in T if t['k'] >= minK]
    return T


def line(tag, T, dd):
    S = set(dd); sub = [t for t in T if t['day'] in S]
    if not sub: return f"  {tag:<44} no trades"
    a = F.account(ds, dd, sub); w = sum(1 for t in a['taken'] if t['pct'] > 0)
    return (f"  {tag:<44} setups {len(sub):4d} taken {len(a['taken']):4d} win {100*w/max(1,len(a['taken'])):3.0f}%  avgR {st.mean(t['R_out'] for t in sub):+.3f}  "
            f"{st.mean(a['daily'].values()):+.3f}%/day  ret {a['ret']:+7.1f}%  DD {a['mdd']:5.1f}%")


print(f"Massive 5-minute bars, {days[0]}..{days[-1]}, six live proxies, live exits (1/3 at 2R, 2-ATR chandelier, out 13:30), $2,000 account 3% risk. before = to 2026-02-27, since = 2026-03-01 on\n")
V = {'30 min box (LIVE)': base, '15 min box, breaks 9:45-10:00': F.P(box=3, brk_end=6), '15 min box, breaks to 10:15 (same cut-off as live)': F.P(box=3, brk_end=9),
     '10 min box': F.P(box=2, brk_end=5), '20 min box': F.P(box=4, brk_end=7), '25 min box': F.P(box=5, brk_end=8), '35 min box': F.P(box=7, brk_end=10), '45 min box': F.P(box=9, brk_end=12)}
TT = {k: run(c) for k, c in V.items()}
print("1. BOX LENGTH, same rules (the break window is the 3 bars after the box)")
for scope, dd in (('ALL', days), ('BEFORE 2026-03', pre), ('SINCE 2026-03', rec)):
    print(f" {scope}")
    for k in V: print(line(k, TT[k], dd))

print("\n2. WHEN DO THE 15-MINUTE ENTRIES HAPPEN? The live schedule starts at 10:00 and entries are allowed from 10:00 (A1.10)")
T15 = TT['15 min box, breaks 9:45-10:00']; c = collections.Counter(hhmm(t['k']) for t in T15)
print("   entry times: " + ', '.join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: tuple(map(int, kv[0].split(':')))) if v >= 5))
print(f"   {100*sum(1 for t in T15 if t['k'] < 6)/len(T15):.0f}% of the 15-minute setups would enter BEFORE 10:00 (9:55 is the earliest), which the live checkpoints do not cover.")
print(line('15 min box as-is (needs a 9:55 slot)', T15, days)); print(line('15 min box, drop entries before 10:00', run(None, T=T15, minK=6), days))
print(line('15 min box (to 10:15), drop entries before 10:00', run(None, T=TT['15 min box, breaks to 10:15 (same cut-off as live)'], minK=6), days))

print("\n3. PAIRED DIFFERENCE, 15-minute minus 30-minute, per day on the account (monthly block bootstrap; is the gap bigger than the noise?)")
a30 = F.account(ds, days, TT['30 min box (LIVE)'])['daily']; a15 = F.account(ds, days, T15)['daily']
for nm, dd in (('ALL', days), ('BEFORE 2026-03', pre), ('SINCE 2026-03', rec)):
    diff = collections.defaultdict(list)
    for d in dd: diff[d[:7]].append(a15[d] - a30[d])
    ms = list(diff); rnd = random.Random(7); bs = []
    for _ in range(3000):
        pick = [rnd.choice(ms) for _ in ms]; v = [x for m in pick for x in diff[m]]; bs.append(st.mean(v))
    bs.sort(); allv = [x for m in ms for x in diff[m]]
    print(f"   {nm:<15} mean difference {st.mean(allv):+.3f}%/day, 90% interval [{bs[150]:+.3f}, {bs[2850]:+.3f}]")

print("\n4. BY YEAR (account %/day and avg R per setup)")
print(f"   {'year':<6}{'30 min':>26}{'15 min':>26}")
for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
    dd = [d for d in days if d.startswith(y)]; row = ''
    for k in ('30 min box (LIVE)', '15 min box, breaks 9:45-10:00'):
        sub = [t for t in TT[k] if t['day'].startswith(y)]; a = F.account(ds, dd, sub)
        row += f"{st.mean(a['daily'].values()):>+10.3f}%/d R {st.mean(t['R_out'] for t in sub):+.2f} n{len(sub):4d}"
    print(f"   {y:<6}{row}")

print("\n5. BY PROXY, whole period (avg R per setup, 30 min vs 15 min)")
for p in LIVE:
    r30 = [t['R_out'] for t in TT['30 min box (LIVE)'] if t['proxy'] == p]; r15 = [t['R_out'] for t in T15 if t['proxy'] == p]
    print(f"   {p:<5} 30 min {st.mean(r30):+.3f} (n {len(r30)})   15 min {st.mean(r15):+.3f} (n {len(r15)})")

print("\n6. WHAT CHANGES MECHANICALLY (15 vs 30)")
for k in ('30 min box (LIVE)', '15 min box, breaks 9:45-10:00'):
    v = TT[k]; print(f"   {k:<34} median box {st.median(t['box_pct'] for t in v):.2f}% of price, median stop {st.median(t['risk_pct'] for t in v):.2f}%, stopped out {100*sum(t['why']=='stop' for t in v)/len(v):.0f}%, reach 1R {100*sum(t['mfe']>=1 for t in v)/len(v):.0f}%, reach 2R {100*sum(t['mfe']>=2 for t in v)/len(v):.0f}%, setups/day {len(v)/len(days):.2f}")

print("\n7. SAME TEST ON THE ROBINHOOD CACHE (the bars the live bot reads), 2026-03-03..10-14, the only window it covers")
rh = F.DS(None, F.ALL); rctx = F.context(rh, [s for s in F.ALL if s in rh.bars]); rdays = rh.days[1:]
for k in ('30 min box (LIVE)', '15 min box, breaks 9:45-10:00', '15 min box, breaks to 10:15 (same cut-off as live)', '20 min box', '25 min box'):
    T_ = [t for t in F.trades(rh, rdays, LIVE, V[k], rctx)]
    a = F.account(rh, rdays, T_); print(f"   {k:<50} setups {len(T_):3d} taken {len(a['taken']):3d} {st.mean(a['daily'].values()):+.3f}%/day ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}%")
