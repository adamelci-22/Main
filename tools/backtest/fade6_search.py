#!/usr/bin/env python3
"""Exhaustive search: best set of exactly 6 FADE proxies (PULLBACK fixed at the live list).
    python3 tools/backtest/fade6_search.py [all] > tools/backtest/results/fade6_search.txt
Pool = combo_search.FADE_POOL (live 6 + the governor's table, measured leverage). Default: liquid pool only (legs >= $100k/bar); 'all' = every proxy.
Every 6-proxy combination is scored on the full sample, both halves and the untouched March window.
Overfitting checks: best 6 chosen on the tuning window (04-07..10-14) judged on March; best 6 chosen on H1 judged on H2 and vice versa.
"""
import itertools, os, statistics as st, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combo_search as C, manual as m, pb_final as PBF, mixed as MXD, expand_lists as EX, final_system as FS
from lab import get_data


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    _, p_live = FS.cands(D, days)
    fc = {q: MXD.norm_px(EX.fade_trades(D, days, q, C.FADE_ROWS[q]), 'FADE') for q in C.FADE_POOL}
    dv = {q: min(EX.dollar_vol(D, C.FADE_ROWS[q][0], days), EX.dollar_vol(D, C.FADE_ROWS[q][2], days)) for q in fc}
    pool = sorted(fc) if 'all' in sys.argv else [q for q in C.FADE_POOL if dv[q] >= C.MIN_DV]
    h = len(days) // 2
    W = {'full': days, 'H1': days[:h], 'H2': days[h:], 'Mar': [d for d in days if d < '2026-04-07'], 'tune': [d for d in days if d >= '2026-04-07']}
    Ws = {k: set(v) for k, v in W.items()}
    pw = {k: [c for c in p_live if c['day'] in Ws[k]] for k in W}
    fw = {k: {q: [c for c in fc[q] if c['day'] in Ws[k]] for q in pool} for k in W}
    def score(L, k): return st.mean(MXD.account(D, W[k], pw[k] + [c for q in L for c in fw[k][q]])['daily'].values())
    combos = list(itertools.combinations(pool, 6)); t0 = time.time()
    print(f"Pool ({len(pool)}): {pool}\n{len(combos)} combinations of 6\n")
    R = []
    for L in combos:
        R.append((L, {k: score(L, k) for k in W}))
    live = tuple(FS.FADE); lv = {k: score(live, k) for k in W}
    print(f"(scored in {time.time()-t0:.0f}s)\nLIVE {list(live)}: full {lv['full']:+.3f} H1 {lv['H1']:+.3f} H2 {lv['H2']:+.3f} March {lv['Mar']:+.3f}")
    rank_live = 1 + sum(r['full'] > lv['full'] for _, r in R)
    print(f"Live list ranks {rank_live} of {len(R)} on the full sample\n")
    print("Top 15 on the full sample:")
    for L, r in sorted(R, key=lambda x: -x[1]['full'])[:15]:
        both = 'both halves >= live' if r['H1'] >= lv['H1'] and r['H2'] >= lv['H2'] else ''
        print(f"   {', '.join(L):<38} full {r['full']:+.3f} H1 {r['H1']:+.3f} H2 {r['H2']:+.3f} March {r['Mar']:+.3f}  {both}")
    rob = [(L, r) for L, r in R if r['H1'] >= lv['H1'] and r['H2'] >= lv['H2'] and r['Mar'] >= lv['Mar']]
    print(f"\nCombinations at least as good as the live list on H1, H2 AND March: {len(rob)}")
    for L, r in sorted(rob, key=lambda x: -x[1]['full'])[:10]:
        print(f"   {', '.join(L):<38} full {r['full']:+.3f} H1 {r['H1']:+.3f} H2 {r['H2']:+.3f} March {r['Mar']:+.3f}")
    print("\nOut-of-sample checks (pick the best 6 on one window, judge on another):")
    for a, b in (('tune', 'Mar'), ('H1', 'H2'), ('H2', 'H1')):
        L, r = max(R, key=lambda x: x[1][a])
        pct = 100 * sum(x[1][b] <= r[b] for x in R) / len(R)
        print(f"   best on {a:<4} = {', '.join(L):<38} on {a} {r[a]:+.3f} -> on {b} {r[b]:+.3f} (live {lv[b]:+.3f}; beats {pct:.0f}% of combos on {b})")
    print("\nHow often each proxy appears in the top 50 (full sample):")
    top = sorted(R, key=lambda x: -x[1]['full'])[:50]
    for q in sorted(pool, key=lambda q: -sum(q in L for L, _ in top)):
        print(f"   {q:<5} {sum(q in L for L, _ in top):3d}/50   $vol {dv[q]/1e3:,.0f}k")


if __name__ == '__main__':
    main()
