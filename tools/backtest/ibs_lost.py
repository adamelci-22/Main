#!/usr/bin/env python3
"""Why IBS-LONG loses winning signals (governor 2026-11-19: "why are these stocks losing gainers identify that focus on ibs first").
Research only. Live book v5.2.64, Massive tape 2022-01..2026-10. For every IBS-LONG signal: taken or lost, and why; on days with several
IBS-LONG signals: the taken trade against the lost ones (same day), their correlation, and what a perfect pick would have made.
    python3 -I tools/backtest/ibs_lost.py > tools/backtest/results/ibs_lost_2026-11-19.txt"""
import os, sys
from collections import defaultdict, Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import book_blocks as BB
taken, lost = BB.sim(list(BB.SYS)); I = BB.ALLT[4]; acc = BB.acct_pct
byday = defaultdict(list)
for t in I: byday[t['day']].append(t)
why = {}
for t, r, h in lost:
    if t['sys'] == 4: why[t['uid']] = r if r != 'busy' else f"busy ({BB.SYS.get(h)})"
print(__doc__.split('\n')[0])
nd = Counter(len(v) for v in byday.values())
print(f"\n1. HOW MANY IBS-LONG SIGNALS FIRE ON ONE MORNING: {len(I)} signals on {len(byday)} days. Days by count: " + ', '.join(f'{k} fund(s) {v} days' for k, v in sorted(nd.items())))
print("\n2. WHY EACH LOST SIGNAL WAS LOST")
c = Counter()
for t in I:
    if t['uid'] in taken: continue
    d = t['day']; others = [x for x in byday[d] if x['uid'] in taken]
    if others: c['another IBS-LONG fund taken the same 9:35 bar'] += 1
    else: c[why.get(t['uid'], '?')] += 1
for k, v in c.most_common(): print(f"   {v:>4}  {k}")
multi = {d: v for d, v in byday.items() if len(v) > 1}
tk, ls, best, avg_all, same_sign, cors = [], [], [], [], 0, []
for d, v in multi.items():
    T = [x for x in v if x['uid'] in taken]
    if not T: continue
    a = acc(T[0]); L = [acc(x) for x in v if x['uid'] not in taken]
    tk.append(a); ls.extend(L); best.append(max(acc(x) for x in v)); avg_all.append(np.mean([acc(x) for x in v]))
    if all((x > 0) == (a > 0) for x in L): same_sign += 1
def pf(z): g = sum(x for x in z if x > 0); l = -sum(x for x in z if x <= 0); return g / l if l else 99
print(f"\n3. DAYS WITH 2+ IBS-LONG SIGNALS WHERE ONE WAS TAKEN: {len(tk)} days")
print(f"   taken trade:         sum {sum(tk):+7.1f} acct %, avg {np.mean(tk):+.2f}, win {100*np.mean([x>0 for x in tk]):.0f}%, PF {pf(tk):.2f}")
print(f"   lost same-day ones:  sum {sum(ls):+7.1f} acct % over {len(ls)} trades, avg {np.mean(ls):+.2f}, win {100*np.mean([x>0 for x in ls]):.0f}%, PF {pf(ls):.2f}")
print(f"   equal split of all:  avg {np.mean(avg_all):+.2f} a day (what splitting cash would earn)")
print(f"   perfect hindsight:   avg {np.mean(best):+.2f} a day (best fund each day; not reachable)")
print(f"   days where every lost fund ended on the same side (win/lose) as the taken one: {same_sign} of {len(tk)} ({100*same_sign/len(tk):.0f}%)")
# correlation of same-day outcomes
pairs = []
for d, v in multi.items():
    a = [acc(x) for x in v]
    for i in range(len(a)):
        for j in range(i + 1, len(a)): pairs.append((a[i], a[j]))
x, y = zip(*pairs); print(f"   correlation of same-day outcomes between funds: {np.corrcoef(x, y)[0, 1]:.2f} over {len(pairs)} pairs")
print("\n4. WHICH FUNDS GET TAKEN AND WHICH GET LOST (relative-volume pick)")
for p in sorted({t['proxy'] for t in I}):
    a = [t for t in I if t['proxy'] == p]; tt = [acc(t) for t in a if t['uid'] in taken]; ll = [acc(t) for t in a if t['uid'] not in taken]
    print(f"   {p:<5} signals {len(a):>3} | taken {len(tt):>3} sum {sum(tt):+6.1f} PF {pf(tt):.2f} | lost {len(ll):>3} sum {sum(ll):+6.1f} PF {pf(ll):.2f}")
