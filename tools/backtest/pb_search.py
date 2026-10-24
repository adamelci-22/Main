#!/usr/bin/env python3
"""PULLBACK list study with FADE fixed at the v5.2.13 list (QQQ SOXX IWM XLK XBI XLF).
    python3 tools/backtest/pb_search.py > tools/backtest/results/pb_search.txt
Pool = the live five + liquid ETF-type inverse/volatility tickers from the governor's table with at least a few setups. Every subset of the pool, robustness
(best-2 removed, per-ticker outliers), walk-forward, and a drop-one table. Bull-side leveraged ETFs were tested earlier (all lost) and are left out.
"""
import itertools, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, final_system as FS, combo_search as C
from lab import get_data

POOL = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD', 'SQQQ', 'SPXU', 'TZA', 'DUST', 'DRIP', 'VIXY', 'SCO', 'ERY', 'FAZ']
LIVE = FS.PB


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2
    mar = [d for d in days if d < '2026-04-07']; tune = [d for d in days if d >= '2026-04-07']
    f, p_live = FS.cands(D, days)
    PI.PROXY.update(C.PB_MAP)
    cand = {}
    for q in POOL:
        if q not in D.bars: continue
        PI.PROXY.setdefault(q, q)
        s = PBF.run(D, days, [q], oco_gap=True)
        cand[q] = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    dv = {q: EX.dollar_vol(D, q, days) for q in cand}
    pool = [q for q in POOL if q in cand and (q in LIVE or (len(cand[q]) >= 3 and dv[q] >= C.MIN_DV))]
    print(f"FADE fixed at {FS.FADE}. PULLBACK pool ({len(pool)}): {pool}\n")
    print(f"{'ticker':<6}{'live':>5}{'setups':>7}{'win%':>6}{'avg%':>7}{'sum%':>7}{'-best1':>7}{'-best2':>7}{'median':>7}{'$vol/bar':>10}")
    for q in pool:
        r = sorted(c['pct'] for c in cand[q]); w = sum(x > 0 for x in r)
        print(f"{q:<6}{'*' if q in LIVE else '':>5}{len(r):>7}{100*w/len(r):>6.0f}{st.mean(r):>+7.2f}{sum(r):>+7.1f}{sum(r[:-1]):>+7.1f}{sum(r[:-2]):>+7.1f}{st.median(r):>+7.2f}{dv[q]/1e3:>9,.0f}k")
    def ret(c): return min(1.0, 0.03 / (c['risk'] / 100)) * c['pct']
    def run(L, ds, mode='all', drop=0):
        sel = [c for q in L for c in cand[q] if c['day'] in set(ds)]
        a = MXD.account(D, ds, f_in(ds) + sel); t = a['taken']
        pb = [x for x in t if x['sys'] == 'PB']
        return a, pb
    f_in = lambda ds: [c for c in f if c['day'] in set(ds)]
    def stats(L, ds):
        a, pb = run(L, ds); dl = a['daily']
        return st.mean(dl.values()), a
    # exhaustive over all subsets
    res = {}
    for n in range(1, len(pool) + 1):
        for L in itertools.combinations(pool, n):
            res[L] = {w: stats(L, d)[0] for w, d in (('full', days), ('H1', days[:h]), ('H2', days[h:]), ('Mar', mar), ('tune', tune))}
    lv = res[tuple(q for q in pool if q in LIVE)]
    print(f"\nLIVE five {LIVE}: full {lv['full']:+.3f} H1 {lv['H1']:+.3f} H2 {lv['H2']:+.3f} March {lv['Mar']:+.3f}  (rank {1+sum(r['full']>lv['full'] for r in res.values())} of {len(res)})")
    print("\nTop 10 lists on the full sample:")
    for L, r in sorted(res.items(), key=lambda x: -x[1]['full'])[:10]:
        print(f"   {', '.join(L):<44} full {r['full']:+.3f} H1 {r['H1']:+.3f} H2 {r['H2']:+.3f} March {r['Mar']:+.3f}")
    rob = sorted([(L, r) for L, r in res.items() if r['full'] > lv['full'] and r['H1'] >= lv['H1'] and r['H2'] >= lv['H2'] and r['Mar'] >= lv['Mar']], key=lambda x: -x[1]['full'])
    print(f"\nBeat the live five on full AND H1 AND H2 AND March: {len(rob)}")
    for L, r in rob[:10]: print(f"   {', '.join(L):<44} full {r['full']:+.3f} H1 {r['H1']:+.3f} H2 {r['H2']:+.3f} March {r['Mar']:+.3f}")
    print("\nWalk-forward (choose on one window, judge on another):")
    for a_, b_ in (('tune', 'Mar'), ('H1', 'H2'), ('H2', 'H1')):
        L, r = max(res.items(), key=lambda x: x[1][a_])
        print(f"   choose on {a_:<4}: {', '.join(L):<44} {a_} {r[a_]:+.3f} -> {b_} {r[b_]:+.3f}  (live {lv[b_]:+.3f})")
    print("\nBest list of each size (full):")
    for n in range(1, len(pool) + 1):
        L, r = max([x for x in res.items() if len(x[0]) == n], key=lambda x: x[1]['full'])
        print(f"   n={n:2d} {r['full']:+.3f} (H1 {r['H1']:+.3f} H2 {r['H2']:+.3f} Mar {r['Mar']:+.3f})  {', '.join(L)}")
    print("\nDrop-one / add-one around the live five (change in %/day: full, H1, H2, March) and robustness:")
    live = tuple(q for q in pool if q in LIVE)
    for q in pool:
        L = tuple(x for x in live if x != q) if q in live else live + (q,)
        L = tuple(sorted(L, key=pool.index)); r = res[L] if L in res else res[tuple(sorted(L, key=pool.index))]
        print(f"   {'drop' if q in live else 'add '} {q:<5} {r['full']-lv['full']:+.3f} {r['H1']-lv['H1']:+.3f} {r['H2']-lv['H2']:+.3f} {r['Mar']-lv['Mar']:+.3f}")
    a, pb = run(live, days); r = sorted(ret(x) * 1 for x in [dict(pct=x['pct'], risk=x['risk']) for x in pb])
    print(f"\nLive five, PULLBACK trades taken: {len(pb)}, win {100*sum(x['pct']>0 for x in pb)/len(pb):.0f}%, account-% per trade median {st.median(r):+.2f}, "
          f"sum {sum(r):+.1f}, without best 2 {sum(sorted(r)[:-2]):+.1f}, without best 5 {sum(sorted(r)[:-5]):+.1f}")
    print("By ticker (taken trades):")
    for q in live:
        t = [x for x in pb if x['name'] == q]
        if not t: continue
        rr = sorted(x['usd'] for x in t)
        print(f"   {q:<5} {len(t):2d} trades win {100*sum(x['usd']>0 for x in t)/len(t):3.0f}% total ${sum(rr):+.0f}  without best 1 ${sum(rr[:-1]):+.0f}  without best 2 ${sum(rr[:-2]):+.0f}")


if __name__ == '__main__':
    main()
