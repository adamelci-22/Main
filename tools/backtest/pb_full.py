#!/usr/bin/env python3
"""Pullback (List B, PULLBACK_SPEC rules) on its own, full available period 2026-03-03..10-14.
    python3 tools/backtest/pb_full.py > tools/backtest/results_pb_full.txt
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, pullback as P
from lab import get_data


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = D.days[1:]; h = len(days) // 2
    sig = PBF.run(D, days, PI.B, oco_gap=True)
    a = P.account(sig, D, days); tk = a['taken']; dl = a['daily']
    t = lambda k: f"{(570 + 5 * k) // 60}:{(570 + 5 * k) % 60:02d}"
    print(f"PULLBACK ONLY, List B {PI.B}, {days[0]}..{days[-1]} ({len(days)} days). $2,000, 3% risk capped at cash, one position, max 3/day.")
    print(f"Rules: PULLBACK_SPEC.md (stop dip low - 0.05%, room >= 0.75%, target >= 0.75x stop, $0.10 OCO gap, 100% at morning high, out 13:30).\n")
    w = [x for x in tk if x['usd'] > 0]; l = [x for x in tk if x['usd'] <= 0]
    print(f"setups {len(sig)}, trades {len(tk)}, win {100*len(w)/len(tk):.0f}%, avg win {st.mean(x['pct'] for x in w):+.2f}% / avg loss {st.mean(x['pct'] for x in l):+.2f}%")
    print(f"{st.mean(dl.values()):+.3f}%/day, return {a['ret']:+.1f}% ($2,000 -> ${2000*(1+a['ret']/100):,.0f}), max DD {a['mdd']:.1f}%, "
          f"H1 {st.mean(dl[d] for d in days[:h]):+.3f}, H2 {st.mean(dl[d] for d in days[h:]):+.3f}, Sharpe~{st.mean(dl.values())/st.pstdev(dl.values())*math.sqrt(252):.1f}")
    print(f"trade days {sum(1 for v in dl.values() if v != 0)} of {len(days)} (about {len(tk)/len(days)*5:.1f} trades a week)\n")
    print("By month:")
    mo = collections.defaultdict(lambda: [0, 0.0, 0]); eq = 2000.0
    for x in tk: mo[x['day'][:7]][0] += 1; mo[x['day'][:7]][1] += x['usd']; mo[x['day'][:7]][2] += x['usd'] > 0
    for k in sorted(mo):
        n, u, wn = mo[k]; print(f"   {k}: {n:2d} trades, {wn} won, {u:+6.0f}$ ({u/eq*100:+.1f}%)"); eq += u
    print("\nBy ticker:")
    g = collections.defaultdict(list)
    for x in tk: g[x['inst']].append(x)
    for k, v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
        v1 = [x for x in v if x['day'] < days[h]]; v2 = [x for x in v if x['day'] >= days[h]]
        print(f"   {k:<5} {len(v):2d} trades, win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}%, avg {st.mean(x['pct'] for x in v):+.2f}%, total {sum(x['usd'] for x in v):+5.0f}$  "
              f"(H1 {sum(x['usd'] for x in v1):+.0f}$ / {len(v1)}, H2 {sum(x['usd'] for x in v2):+.0f}$ / {len(v2)})")
    ex = collections.Counter('target' if x['hit'] else ('stop' if x['xbar'] < 47 else '13:30') for x in tk)
    print(f"\nExits: {dict(ex)}")
    hrs = collections.defaultdict(list)
    for x in tk: hrs[t(x['k'])[:-3] + ':00'].append(x)
    print("Entry hour: " + ', '.join(f"{k} {len(v)}tr {sum(x['usd'] for x in v):+.0f}$" for k, v in sorted(hrs.items(), key=lambda kv: int(kv[0].split(':')[0]))))
    print(f"\nUntouched window (Mar 3 - Apr 6, never used for tuning): " + (lambda v: f"{len(v)} trades, {sum(x['usd'] for x in v):+.0f}$")([x for x in tk if x['day'] < '2026-04-07']))
    print("\nAll trades:")
    for x in tk:
        print(f"   {x['day']} {x['inst']:<5} in {t(x['k'])} @ {x['entry']:.2f}  out {t(x['xbar'])} "
              f"{'target' if x['hit'] else ('stop' if x['xbar'] < 47 else '13:30')}  {x['pct']:+.2f}%  {x['usd']:+.1f}$")


if __name__ == '__main__':
    main()
