#!/usr/bin/env python3
"""FADE ALONE (no PULLBACK in the account): every FADE list of 1..8 proxies from the 20-proxy pool, model and real-leg pricing,
plus win rates for the main candidate lists.
    python3 tools/backtest/fade_only_max8.py > tools/backtest/results/fade_only_max8.txt
"""
import itertools, os, statistics as st, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_all_subsets as F, combo_search as C, final_system as FS

CAP = 8
LIVE = FS.FADE


def taken(days, cands):
    by = {}
    for c in cands: by.setdefault(c[0], []).append(c)
    out = []
    for d in days:
        cs = sorted(by.get(d, []), key=lambda c: c[1]); free = 0; n = 0
        while cs and n < F.MAXE:
            av = [c for c in cs if c[1] >= free]
            if not av: break
            same = [c for c in av if c[1] == av[0][1]]; c = max(same, key=lambda c: c[5])
            out.append(c); free = c[2] + 1; cs.remove(c); n += 1
    return out


def stats(days, t):
    daily = {}
    for c in t: daily[c[0]] = daily.get(c[0], 1) * (1 + min(1, F.RISK / (c[4] / 100)) * c[3] / 100)
    eq = pk = 1; dd = 0; streak = worst = 0
    for d in days:
        eq *= daily.get(d, 1); pk = max(pk, eq); dd = max(dd, (pk - eq) / pk * 100)
    for c in t:
        streak = streak + 1 if c[3] <= 0 else 0; worst = max(worst, streak)
    w = [c[3] for c in t if c[3] > 0]; l = [c[3] for c in t if c[3] <= 0]
    return dict(n=len(t), win=100 * len(w) / len(t), aw=st.mean(w), al=st.mean(l), day=sum(daily.get(d, 1) * 100 - 100 for d in days) / len(days),
                dd=dd, streak=worst, pf=sum(w) / -sum(l) if l else 99, tdays=len(daily))


def main():
    t0 = time.time()
    D, days, pool, model, real, pb, fc, p_live, dv = F.prep()
    h = len(days) // 2; N = len(pool)
    W = ['full', 'H1', 'H2', 'March', 'tune']
    idx = [list(range(len(days))), list(range(h)), list(range(h, len(days))),
           [i for i, d in enumerate(days) if d < '2026-04-07'], [i for i, d in enumerate(days) if d >= '2026-04-07']]
    masks = [sum(1 << i for i in c) for n in range(1, CAP + 1) for c in itertools.combinations(range(N), n)]
    with Pool(4, initializer=F.init, initargs=(days, pool, model, real, [], idx)) as P:     # [] = no PULLBACK
        R = list(P.imap_unordered(F.score, masks, chunksize=2000))
    name = lambda mk: ', '.join(pool[i] for i in range(N) if mk >> i & 1)
    size = lambda mk: bin(mk).count('1')
    LV = dict(R)[sum(1 << pool.index(q) for q in LIVE)]
    liquid = sum(1 << i for i, q in enumerate(pool) if dv[q] >= C.MIN_DV)
    print(f"FADE ALONE. {len(masks):,} lists of 1..{CAP} proxies from {N}, {time.time()-t0:.0f}s\n")
    for mi, mode in enumerate(('model', 'real')):
        M = model if mode == 'model' else real; lv = LV[mi]
        print(f"######## PRICING: {mode.upper()} ########   LIVE six: " + '  '.join(f"{w} {lv[j]:+.3f}" for j, w in enumerate(W)))
        for tag, filt in (('ALL proxies', lambda mk: True), ('LIQUID legs only', lambda mk: mk & ~liquid == 0)):
            RR = [(mk, r[mi]) for mk, r in R if filt(mk)]
            print(f"\n  [{tag}] {len(RR):,} lists; live six ranks {1 + sum(r[0] > lv[0] for _, r in RR):,}")
            print("   top 8 full sample:")
            for mk, r in sorted(RR, key=lambda x: -x[1][0])[:8]:
                s = stats(days, taken(days, [c for i in range(N) if mk >> i & 1 for c in M[pool[i]]]))
                print(f"     n={size(mk)} {name(mk):<46} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])) + f"  win {s['win']:.0f}% trades {s['n']} DD {s['dd']:.1f}%")
            rob = sorted([(mk, r) for mk, r in RR if r[0] > lv[0] and r[1] >= lv[1] and r[2] >= lv[2] and r[3] >= lv[3]], key=lambda x: -x[1][0])
            print(f"   beat the live six on full AND H1 AND H2 AND March: {len(rob)}")
            for mk, r in rob[:8]:
                s = stats(days, taken(days, [c for i in range(N) if mk >> i & 1 for c in M[pool[i]]]))
                print(f"     n={size(mk)} {name(mk):<46} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])) + f"  win {s['win']:.0f}% trades {s['n']} DD {s['dd']:.1f}%")
            for a_, b_ in ((4, 3), (1, 2), (2, 1)):
                mk, r = max(RR, key=lambda x: x[1][a_])
                print(f"   choose on {W[a_]:<5} -> n={size(mk)} {name(mk):<46} {W[a_]} {r[a_]:+.3f} -> {W[b_]} {r[b_]:+.3f} (live {lv[b_]:+.3f})")
        print(f"\n  Win rates, FADE alone ({mode}):")
        print(f"   {'list':<22}{'trades':>7}{'tradedays':>10}{'win%':>6}{'avg win':>9}{'avg loss':>9}{'PF':>6}{'%/day':>8}{'maxDD':>7}{'worst streak':>13}  added tickers (trades, win%)")
        for nm, L in (('live six', LIVE), ('live + SPY', LIVE + ['SPY']), ('live + KRE', LIVE + ['KRE']), ('live + XLF + KRE', LIVE + ['XLF', 'KRE']),
                      ('live + GDX', LIVE + ['GDX']), ('live + SPY + GDX', LIVE + ['SPY', 'GDX']), ('live + KRE + GDX', LIVE + ['KRE', 'GDX']),
                      ('live + SMH', LIVE + ['SMH']), ('live + TLT', LIVE + ['TLT'])):
            t = taken(days, [c for q in L for c in M[q]]); s = stats(days, t)
            ex = ' '.join(f"{q} {len([c for c in t if c[6]==pool.index(q)])} ({100*sum(c[3]>0 for c in t if c[6]==pool.index(q))/max(1,len([c for c in t if c[6]==pool.index(q)])):.0f}%)" for q in L if q not in LIVE)
            print(f"   {nm:<22}{s['n']:>7}{s['tdays']:>10}{s['win']:>6.0f}{s['aw']:>+9.2f}{s['al']:>+9.2f}{s['pf']:>6.2f}{s['day']:>+8.3f}{s['dd']:>7.1f}{s['streak']:>13}  {ex}")
        print(f"\n  Each proxy on its own, FADE alone ({mode}): trades, win%, avg%, sum%")
        for q in pool:
            t = M[q]; w = sum(c[3] > 0 for c in t)
            print(f"   {q:<5}{'*' if q in LIVE else ' '} {len(t):3d} trades  win {100*w/len(t):3.0f}%  avg {st.mean(c[3] for c in t):+.2f}%  sum {sum(c[3] for c in t):+6.1f}%  leg $vol {dv[q]/1e3:,.0f}k")
        print()


if __name__ == '__main__':
    main()
