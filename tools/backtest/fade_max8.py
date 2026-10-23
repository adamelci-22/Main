#!/usr/bin/env python3
"""FADE lists capped at 8 proxies: every subset of size 1..8 of the 20-proxy pool (PULLBACK fixed at the live list), model and real-leg pricing.
    python3 tools/backtest/fade_max8.py > tools/backtest/results/fade_max8.txt
Same simulator and pricing as fade_all_subsets.py.
"""
import itertools, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_all_subsets as F, combo_search as C, final_system as FS

CAP = 8


def main():
    t0 = time.time()
    D, days, pool, model, real, pb, fc, p_live, dv = F.prep()
    h = len(days) // 2; N = len(pool)
    W = ['full', 'H1', 'H2', 'March', 'tune']
    idx = [list(range(len(days))), list(range(h)), list(range(h, len(days))),
           [i for i, d in enumerate(days) if d < '2026-04-07'], [i for i, d in enumerate(days) if d >= '2026-04-07']]
    masks = [sum(1 << i for i in c) for n in range(1, CAP + 1) for c in itertools.combinations(range(N), n)]
    with Pool(4, initializer=F.init, initargs=(days, pool, model, real, pb, idx)) as P:
        R = list(P.imap_unordered(F.score, masks, chunksize=2000))
    name = lambda mk: ', '.join(pool[i] for i in range(N) if mk >> i & 1)
    size = lambda mk: bin(mk).count('1')
    LV = dict(R)[sum(1 << pool.index(q) for q in FS.FADE)]
    liquid = sum(1 << i for i, q in enumerate(pool) if dv[q] >= C.MIN_DV)
    print(f"{len(masks):,} lists of 1..{CAP} proxies from {N}, searched in {time.time()-t0:.0f}s\n")
    for mi, mode in enumerate(('model', 'real')):
        lv = LV[mi]
        print(f"######## PRICING: {mode.upper()} ########   LIVE six: " + '  '.join(f"{w} {lv[j]:+.3f}" for j, w in enumerate(W)))
        for tag, filt in (('ALL proxies', lambda mk: True), ('LIQUID legs only', lambda mk: mk & ~liquid == 0)):
            RR = [(mk, r[mi]) for mk, r in R if filt(mk)]
            print(f"\n  [{tag}] {len(RR):,} lists; live six ranks {1 + sum(r[0] > lv[0] for _, r in RR):,}")
            print("   top 8 full sample:")
            for mk, r in sorted(RR, key=lambda x: -x[1][0])[:8]:
                print(f"     n={size(mk)} {name(mk):<48} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])))
            rob = sorted([(mk, r) for mk, r in RR if r[0] > lv[0] and r[1] >= lv[1] and r[2] >= lv[2] and r[3] >= lv[3]], key=lambda x: -x[1][0])
            print(f"   beat the live six on full AND H1 AND H2 AND March: {len(rob)}")
            for mk, r in rob[:8]:
                print(f"     n={size(mk)} {name(mk):<48} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])))
            for a_, b_ in ((4, 3), (1, 2), (2, 1)):
                mk, r = max(RR, key=lambda x: x[1][a_])
                print(f"   choose on {W[a_]:<5} -> n={size(mk)} {name(mk):<46} {W[a_]} {r[a_]:+.3f} -> {W[b_]} {r[b_]:+.3f} (live {lv[b_]:+.3f})")
        print()


if __name__ == '__main__':
    main()
