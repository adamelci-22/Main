#!/usr/bin/env python3
"""Is the 10-minute-box result real? by year, proxy, entry time, costs, z-score.  /usr/bin/python3 -I tools/backtest/box10_check.py M5.json.gz > results/box10_check.txt"""
import collections, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
SRC = sys.argv[1]; CUT = '2026-03-01'; LIVE = F.LIVE
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); days = ds.days[21:]
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]
hhmm = lambda k: f"{(570 + 5 * k) // 60}:{(570 + 5 * k) % 60:02d}"
c10 = F.P(box=2, brk_end=5); T10 = F.trades(ds, days, LIVE, c10, ctx); T30 = F.trades(ds, days, LIVE, F.P(), ctx)
def z(v): return st.mean(v) / (st.pstdev(v) / math.sqrt(len(v)))
b = [t['R_out'] for t in T10 if t['day'] < CUT]; print(f"10-min box before 2026-03: n {len(b)} avg R {st.mean(b):+.3f} std {st.pstdev(b):.2f} z {z(b):+.2f}  (about 8 box lengths were tried; a z above 3 is hard to get by luck)")
s = [t['R_out'] for t in T10 if t['day'] >= CUT]; print(f"10-min box since 2026-03:  n {len(s)} avg R {st.mean(s):+.3f} z {z(s):+.2f}")
print("\nentry times (10-minute box):", ', '.join(f"{k} {v}" for k, v in sorted(collections.Counter(hhmm(t['k']) for t in T10).items(), key=lambda kv: tuple(map(int, kv[0].split(':')))) if v >= 8))
print("share entering before 10:00: %.0f%%; before 9:55: %.0f%%" % (100 * sum(t['k'] < 6 for t in T10) / len(T10), 100 * sum(t['k'] < 5 for t in T10) / len(T10)))
print("\nby year (avg R per setup, account %/day):")
for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
    sub = [t for t in T10 if t['day'].startswith(y)]; dd = [d for d in days if d.startswith(y)]; a = F.account(ds, dd, sub)
    print(f"  {y}  n {len(sub):4d}  avgR {st.mean(t['R_out'] for t in sub):+.3f}  {st.mean(a['daily'].values()):+.3f}%/day  ret {a['ret']:+6.1f}%  (live 30-min: avgR {st.mean(t['R_out'] for t in T30 if t['day'].startswith(y)):+.3f})")
print("\nby proxy (avg R): " + '  '.join(f"{p} {st.mean(t['R_out'] for t in T10 if t['proxy']==p):+.2f}" for p in LIVE))
print("by entry time bucket (avg R, n): " + '  '.join(f"{lab} {st.mean([t['R_out'] for t in T10 if lo <= t['k'] < hi] or [0]):+.2f} ({sum(1 for t in T10 if lo <= t['k'] < hi)})" for lab, lo, hi in (('9:50', 4, 5), ('9:55', 5, 6), ('10:00-10:10', 6, 9), ('10:10+', 9, 99))))
print("\nentries from 10:00 only (what the live checkpoints could actually take):")
Tk = [t for t in T10 if t['k'] >= 6]; a = F.account(ds, days, Tk)
print(f"  setups {len(Tk)}, taken {len(a['taken'])}, avg R {st.mean(t['R_out'] for t in Tk):+.3f}, {st.mean(a['daily'].values()):+.3f}%/day, ret {a['ret']:+.1f}%, DD {a['mdd']:.1f}%")
print("\ncosts: extra round-trip cost on the leg, account %/day (early bars have wide spreads, the model charges 0.06%)")
for extra in (0.0, 0.1, 0.2, 0.3):
    F.LEGCOST = 0.06 + extra; T_ = F.trades(ds, days, LIVE, c10, ctx)
    print(f"  extra {extra:.1f}%: before {st.mean(F.account(ds, pre, [t for t in T_ if t['day']<CUT])['daily'].values()):+.3f}  since {st.mean(F.account(ds, rec, [t for t in T_ if t['day']>=CUT])['daily'].values()):+.3f}")
F.LEGCOST = 0.06
print("\nneighbours: box 5, 10, 15, 20 min (avg R before 2026-03) -> is it a smooth hill or a single spike?")
for n, nm in ((1, '5 min'), (2, '10 min'), (3, '15 min'), (4, '20 min'), (5, '25 min'), (6, '30 min (live)')):
    T_ = F.trades(ds, days, LIVE, F.P(box=n, brk_end=n + 3), ctx); v = [t['R_out'] for t in T_ if t['day'] < CUT]; v2 = [t['R_out'] for t in T_ if t['day'] >= CUT]
    print(f"  {nm:<14} before {st.mean(v):+.3f} (n {len(v)}, z {z(v):+.2f})   since {st.mean(v2):+.3f} (n {len(v2)})")
