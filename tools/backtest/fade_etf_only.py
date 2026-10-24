#!/usr/bin/env python3
"""FADE with index/sector ETF proxies only (no single stocks: AMD NVDA AAPL AMZN META MSFT excluded by the governor).
    python3 tools/backtest/fade_etf_only.py > tools/backtest/results/fade_etf_only.txt
Every list of 4..8 proxies from the 14 ETF proxies; FADE alone and full system (live PULLBACK), real-leg and model pricing, walk-forward checks.
"""
import itertools, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_all_subsets as F, fade_only_max8 as O, combo_search as C, final_system as FS

ETF = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'SPY', 'SMH', 'XLV', 'XLF', 'KRE', 'GDX', 'XLE', 'XOP', 'TLT']
BASE5 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI']


def main():
    D, days, pool0, model, real, pb, fc, p_live, dv = F.prep()
    pool = [q for q in pool0 if q in ETF]; N = len(pool); h = len(days) // 2
    W = ['full', 'H1', 'H2', 'March', 'tune']
    idx = [list(range(len(days))), list(range(h)), list(range(h, len(days))),
           [i for i, d in enumerate(days) if d < '2026-04-07'], [i for i, d in enumerate(days) if d >= '2026-04-07']]
    masks = [sum(1 << i for i in c) for n in range(1, 9) for c in itertools.combinations(range(N), n)]
    name = lambda mk: ', '.join(pool[i] for i in range(N) if mk >> i & 1)
    size = lambda mk: bin(mk).count('1')
    base = sum(1 << pool.index(q) for q in BASE5)
    liquid = sum(1 << i for i, q in enumerate(pool) if dv[q] >= C.MIN_DV)
    print(f"ETF-only pool ({N}): {pool}\n{len(masks):,} lists of 1..8\n")
    for sysname, extra in (('FADE ALONE', []), ('FULL SYSTEM (with live PULLBACK)', pb)):
        with Pool(4, initializer=F.init, initargs=(days, pool, {q: model[q] for q in pool}, {q: real[q] for q in pool}, extra, idx)) as P:
            R = dict(P.imap_unordered(F.score, masks, chunksize=1000))
        for mi, mode in enumerate(('real', 'model')):
            M = real if mode == 'real' else model
            RR = {mk: r[1 - mi] if False else r[0 if mode == 'model' else 1] for mk, r in R.items()}   # score returns (model, real)
            b5 = RR[base]
            print(f"######## {sysname}, {mode.upper()} pricing ######## five core (QQQ SOXX IWM XLK XBI): " + ' '.join(f"{w} {b5[j]:+.3f}" for j, w in enumerate(W)))
            print("  Core five + ONE more:")
            for q in sorted(pool, key=lambda q: -RR[base | 1 << pool.index(q)][0]):
                if q in BASE5: continue
                r = RR[base | 1 << pool.index(q)]
                flag = ' <- beats core in H1, H2 and March' if r[1] > b5[1] and r[2] > b5[2] and r[3] > b5[3] else ''
                print(f"     +{q:<4} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])) + f"  leg $vol {dv[q]/1e3:,.0f}k{flag}")
            for tag, filt in (('ALL ETF proxies', lambda mk: True), ('LIQUID legs only', lambda mk: mk & ~liquid == 0)):
                S = [(mk, RR[mk]) for mk in masks if filt(mk)]
                print(f"  [{tag}] best 6-proxy lists:")
                for mk, r in sorted([x for x in S if size(x[0]) == 6], key=lambda x: -x[1][0])[:5]:
                    t = O.taken(days, ([] if not extra else pb) + [c for i in range(N) if mk >> i & 1 for c in M[pool[i]]]); s = O.stats(days, t)
                    print(f"     {name(mk):<38} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])) + f"  win {s['win']:.0f}% trades {s['n']} DD {s['dd']:.1f}%")
                print(f"  [{tag}] best lists up to 8:")
                for mk, r in sorted(S, key=lambda x: -x[1][0])[:3]:
                    print(f"     n={size(mk)} {name(mk):<46} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])))
                for a_, b_ in ((4, 3), (1, 2), (2, 1)):
                    mk, r = max([x for x in S if size(x[0]) == 6], key=lambda x: x[1][a_])
                    print(f"  choose best 6 on {W[a_]:<5} -> {name(mk):<38} {W[a_]} {r[a_]:+.3f} -> {W[b_]} {r[b_]:+.3f}  (core five+SPY there {RR[base | 1 << pool.index('SPY')][b_]:+.3f}, core five {b5[b_]:+.3f})")
            print()


if __name__ == '__main__':
    main()
