#!/usr/bin/env python3
"""Best PULLBACK list of 4 to 10 funds. Massive bars, live PULLBACK rules (PULLBACK_SPEC / RULEBOOK B3), each fund on its own chart.
    /usr/bin/python3 -I tools/backtest/massive_pb_best.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_pb_best.txt
Pool: thirteen funds with at least 22 signals in the five years (SOXS LABD TECS UVXY SRTY DRIP DUST UVIX TZA SQQQ NUGT FAZ ERY). All 7,722 lists of 4 to 10.
Account: $2,000, 3% risk capped at cash, one position at a time, 3 entries a day (mixed.account). PULLBACK alone, then with the live FADE.
Three ways to choose, so the window the rules came from is not the only judge:
  1. best on B = 2026-03-03..10-14 (the window the live list came from)
  2. best on A = 2021-11..2026-02-27, then shown on B (selection before 2026, test in 2026)
  3. best on the weaker of A and B (both must be positive)
Null: lists drawn at random of the same size give the spread to compare against.
"""
import itertools, os, statistics as st, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_live_rules as LR
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD
import final_system as FS
from lab import get_data
POOL = ['SOXS', 'LABD', 'TECS', 'UVXY', 'SRTY', 'DRIP', 'DUST', 'UVIX', 'TZA', 'SQQQ', 'NUGT', 'FAZ', 'ERY']
LIVE = ['SOXS', 'LABD', 'TECS', 'UVXY']
A_END, B0, B1 = '2026-02-27', '2026-03-03', '2026-10-14'


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    for f in POOL: PI.PROXY.setdefault(f, f)
    S = PBF.run(D, days, [f for f in POOL if f in D.bars], oco_gap=True)
    cand = {f: [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S if x['inst'] == f] for f in POOL}
    DA = [d for d in days if d <= A_END]; DB = [d for d in days if B0 <= d <= B1]; SA, SB = set(DA), set(DB)
    def acct(ds, S_, cs):
        a = MXD.account(D, ds, [c for c in cs if c['day'] in S_]); t = a['taken']
        return dict(pd=st.mean(a['daily'].values()), ret=a['ret'], dd=a['mdd'], n=len(t), win=100 * sum(x['usd'] > 0 for x in t) / len(t) if t else 0)
    combos = [c for k in range(4, 11) for c in itertools.combinations(POOL, k)]; out = []
    for c in combos:
        cs = [x for f in c for x in cand[f]]; out.append((c, acct(DB, SB, cs), acct(DA, SA, cs)))
    f_ = lambda r: f"{r['pd']:+.3f}%/d ret {r['ret']:+6.0f}% DD {r['dd']:>4.1f}% n={r['n']:>3} win {r['win']:>3.0f}%"
    print(f"Pool ({len(POOL)}): " + ', '.join(f"{f} {len(cand[f])}" for f in POOL) + f" signals.  {len(combos)} lists of 4 to 10. PULLBACK alone.\n")
    print("== 1. Best list of each size, chosen on B ==")
    for k in range(4, 11):
        r = max((r for r in out if len(r[0]) == k), key=lambda r: r[1]['pd']); print(f"{k:<3}{' '.join(r[0]):<62}B {f_(r[1])}   A {r[2]['pd']:+.3f}%/d DD {r[2]['dd']:.0f}%")
    print("\n== 2. Best list of each size, chosen on A (before 2026), then shown on B ==")
    for k in range(4, 11):
        r = max((r for r in out if len(r[0]) == k), key=lambda r: r[2]['pd']); print(f"{k:<3}{' '.join(r[0]):<62}A {f_(r[2])}   B {r[1]['pd']:+.3f}%/d DD {r[1]['dd']:.0f}% n={r[1]['n']}")
    print("\n== 3. Top 8 by the weaker of A and B ==")
    for r in sorted(out, key=lambda r: -min(r[1]['pd'], r[2]['pd']))[:8]: print(f"{len(r[0]):<3}{' '.join(r[0]):<62}A {r[2]['pd']:+.3f}%/d DD {r[2]['dd']:>4.1f}% n={r[2]['n']:>3} win {r[2]['win']:>3.0f}%   B {r[1]['pd']:+.3f}%/d DD {r[1]['dd']:>4.1f}% n={r[1]['n']:>3} win {r[1]['win']:>3.0f}%")
    lv = next(r for r in out if set(r[0]) == set(LIVE))
    print(f"\nLive list ({' '.join(LIVE)}): B {f_(lv[1])}   A {f_(lv[2])}   rank on B {1 + sum(r[1]['pd'] > lv[1]['pd'] for r in out)} of {len(out)}, rank on A {1 + sum(r[2]['pd'] > lv[2]['pd'] for r in out)}")
    print(f"A: best {max(r[2]['pd'] for r in out):+.3f}%/d, median {st.median(r[2]['pd'] for r in out):+.3f}%/d, share above zero {100*sum(r[2]['pd'] > 0 for r in out)/len(out):.0f}%.   B: best {max(r[1]['pd'] for r in out):+.3f}%/d, median {st.median(r[1]['pd'] for r in out):+.3f}%/d, share above zero {100*sum(r[1]['pd'] > 0 for r in out)/len(out):.0f}%.")
    both = [r for r in out if r[1]['pd'] > 0 and r[2]['pd'] > 0]
    print(f"Lists positive in both A and B: {len(both)} of {len(out)}.  Rank correlation of A and B over all lists: {np.corrcoef(np.argsort(np.argsort([r[1]['pd'] for r in out])), np.argsort(np.argsort([r[2]['pd'] for r in out])))[0, 1]:+.2f}")
    best_b = max(out, key=lambda r: r[1]['pd']); best_a = max(out, key=lambda r: r[2]['pd']); robust = max(out, key=lambda r: min(r[1]['pd'], r[2]['pd']))
    fade = FS.cands(D, days)[0]
    print("\n== 4. With the live FADE (six proxies), combined account ==")
    for nm, r in (('live list', lv), ('best on B', best_b), ('best on A', best_a), ('best on weaker of A and B', robust)):
        cs = [x for f in r[0] for x in cand[f]] + fade
        print(f"   {nm:<26}{' '.join(r[0]):<54}B {f_(acct(DB, SB, cs))}   A {acct(DA, SA, cs)['pd']:+.3f}%/d DD {acct(DA, SA, cs)['dd']:.0f}%")


if __name__ == '__main__':
    main()
