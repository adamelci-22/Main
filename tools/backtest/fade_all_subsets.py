#!/usr/bin/env python3
"""EVERY subset (any size) of the FADE proxy pool, PULLBACK fixed at the live list. Two pricing modes:
   model : leg return = leverage x proxy return - cost (the engine's assumption, as in final_system.py)
   real  : same trades re-priced with the leveraged ETF's real 5-min prices (entry-bar open -> exit-bar close), the double check
    python3 tools/backtest/fade_all_subsets.py > tools/backtest/results/fade_all_subsets.txt
Fast simulator = mixed.account(mode='one', 3% risk, max 3 entries/day, earliest trigger first, ties by proxy RVOL); daily % does not depend on
equity, so each window's mean is the mean of that window's days. Verified against mixed.account before the search (printed).
"""
import itertools, os, statistics as st, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combo_search as C, manual as m, pb_final as PBF, mixed as MXD, expand_lists as EX, final_system as FS, twobar as TB
import retest as RT
from lab import get_data

RISK, MAXE = 0.03, 3
G = {}


def prep():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    _, p_live = FS.cands(D, days)
    fc = {q: MXD.norm_px(EX.fade_trades(D, days, q, C.FADE_ROWS[q]), 'FADE') for q in C.FADE_POOL}
    # real-leg adjustment per trade: real leg return (entry-bar open -> exit-bar close) minus the model's lev x proxy over the same bars
    adj = {}
    for q in C.FADE_POOL:
        bull, lb, bear, lbe = C.FADE_ROWS[q]
        for c in fc[q]:
            d = c['day']; P = D.bars[q][d]; side = 1 if c['name'].endswith('+') else -1
            leg, lev = (bull, lb) if side > 0 else (bear, lbe)
            L = D.bars.get(leg, {}).get(d)
            if not L: adj[(q, d)] = None; continue
            k, x = c['k'], c['xbar']
            real = (L[x][3] / L[k][0] - 1) * 100; est = lev * side * (P[x][3] / P[k][0] - 1) * 100
            adj[(q, d)] = real - est
    rv = lambda c: TB.rvol(D, c['proxy'], c['day'], c['k'])
    pool = [q for q in C.FADE_POOL]
    dv = {q: min(EX.dollar_vol(D, C.FADE_ROWS[q][0], days), EX.dollar_vol(D, C.FADE_ROWS[q][2], days)) for q in pool}
    def pack(c, tag, pct): return (c['day'], c['k'], c['xbar'], pct, c['risk'], rv(c), tag)
    model = {q: [pack(c, i, c['pct']) for c in fc[q]] for i, q in enumerate(pool)}
    real = {q: [pack(c, i, c['pct'] + adj[(q, c['day'])]) for c in fc[q] if adj[(q, c['day'])] is not None] for i, q in enumerate(pool)}
    pb = [pack(c, -1, c['pct']) for c in p_live]
    return D, days, pool, model, real, pb, fc, p_live, dv


def sim(days, cands):
    by = {}
    for c in cands: by.setdefault(c[0], []).append(c)
    out = []
    for d in days:
        cs = by.get(d)
        if not cs: out.append(0.0); continue
        cs = sorted(cs, key=lambda c: c[1]); free = 0; n = 0; r = 1.0
        while cs and n < MAXE:
            av = [c for c in cs if c[1] >= free]
            if not av: break
            k0 = av[0][1]; same = [c for c in av if c[1] == k0]
            c = max(same, key=lambda c: c[5]) if len(same) > 1 else same[0]
            r *= 1 + min(1.0, RISK / (c[4] / 100)) * c[3] / 100
            free = c[2] + 1; cs.remove(c); n += 1
        out.append((r - 1) * 100)
    return out


def init(days, pool, model, real, pb, idx):
    G.update(days=days, pool=pool, model=model, real=real, pb=pb, idx=idx)


def score(mask):
    days, pool, idx = G['days'], G['pool'], G['idx']
    L = [pool[i] for i in range(len(pool)) if mask >> i & 1]
    res = []
    for mode in ('model', 'real'):
        dl = sim(days, G['pb'] + [c for q in L for c in G[mode][q]])
        res.append(tuple(sum(dl[i] for i in ix) / len(ix) for ix in idx))
    return mask, res


def main():
    t0 = time.time()
    D, days, pool, model, real, pb, fc, p_live, dv = prep()
    h = len(days) // 2
    W = ['full', 'H1', 'H2', 'March', 'tune']
    idx = [list(range(len(days))), list(range(h)), list(range(h, len(days))),
           [i for i, d in enumerate(days) if d < '2026-04-07'], [i for i, d in enumerate(days) if d >= '2026-04-07']]
    # verification against the engine
    live_f = [c for q in FS.FADE for c in fc[q]]
    a = MXD.account(D, days, p_live + live_f); fast = sim(days, pb + [c for q in FS.FADE for c in model[q]])
    print(f"VERIFY live list: engine {st.mean(a['daily'].values()):+.4f}%/day, fast sim {sum(fast)/len(fast):+.4f}%/day, "
          f"max daily diff {max(abs(a['daily'][d]-fast[i]) for i, d in enumerate(days)):.2e}")
    for L in (['SOXX', 'XBI'], ['KRE', 'GDX', 'NVDA', 'TLT'], pool):
        a = MXD.account(D, days, p_live + [c for q in L for c in fc[q]]); fast = sim(days, pb + [c for q in L for c in model[q]])
        print(f"VERIFY {L if len(L) < 6 else 'all 20'}: engine {st.mean(a['daily'].values()):+.4f} fast {sum(fast)/len(fast):+.4f}")
    print("\nReal-leg check per proxy (FADE trades re-priced on the real leveraged ETF; model vs real, sum of trade %):")
    for q in pool:
        ms = sum(c[3] for c in model[q]); rs = sum(c[3] for c in real[q])
        print(f"   {q:<5} {C.FADE_ROWS[q][0]}/{C.FADE_ROWS[q][2]:<5} trades {len(model[q]):2d}  model {ms:+6.1f}%  real {rs:+6.1f}%  gap {rs-ms:+5.1f}  leg $vol {dv[q]/1e3:,.0f}k")
    N = len(pool); masks = range(1, 1 << N)
    print(f"\nSearching all {len(masks):,} non-empty subsets of {N} proxies, 2 pricing modes, 4 processes...", flush=True)
    with Pool(4, initializer=init, initargs=(days, pool, model, real, pb, idx)) as P:
        R = list(P.imap_unordered(score, masks, chunksize=2000))
    print(f"(done in {time.time()-t0:.0f}s)\n")
    name = lambda mk: ', '.join(pool[i] for i in range(N) if mk >> i & 1)
    size = lambda mk: bin(mk).count('1')
    live_mask = sum(1 << pool.index(q) for q in FS.FADE)
    LV = dict(R)[live_mask]
    liquid = sum(1 << i for i, q in enumerate(pool) if dv[q] >= C.MIN_DV)
    for mi, mode in enumerate(('model', 'real')):
        lv = LV[mi]
        print(f"######## PRICING: {mode.upper()} ########")
        print(f"LIVE {FS.FADE}: " + '  '.join(f"{w} {lv[j]:+.3f}" for j, w in enumerate(W)))
        for tag, filt in (('ALL proxies', lambda mk: True), (f'LIQUID legs only (>= ${C.MIN_DV/1e3:.0f}k/bar)', lambda mk: mk & ~liquid == 0)):
            RR = [(mk, r[mi]) for mk, r in R if filt(mk)]
            rank = 1 + sum(r[0] > lv[0] for _, r in RR)
            print(f"\n  [{tag}] {len(RR):,} subsets; live list ranks {rank:,} on the full sample")
            print("   top 10 full sample:")
            for mk, r in sorted(RR, key=lambda x: -x[1][0])[:10]:
                print(f"     n={size(mk):2d} {name(mk):<60} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])))
            rob = [(mk, r) for mk, r in RR if r[1] >= lv[1] and r[2] >= lv[2] and r[3] >= lv[3] and r[0] > lv[0]]
            print(f"   beat the live list on full AND H1 AND H2 AND March: {len(rob):,}")
            for mk, r in sorted(rob, key=lambda x: -x[1][0])[:10]:
                print(f"     n={size(mk):2d} {name(mk):<60} " + ' '.join(f"{w} {r[j]:+.3f}" for j, w in enumerate(W[:4])))
            for a_, b_ in ((4, 3), (1, 2), (2, 1)):
                mk, r = max(RR, key=lambda x: x[1][a_])
                print(f"   choose on {W[a_]:<5} -> n={size(mk):2d} {name(mk):<55} {W[a_]} {r[a_]:+.3f} -> {W[b_]} {r[b_]:+.3f} (live {lv[b_]:+.3f})")
            print("   best list of each size (full sample):")
            for n in range(1, N + 1):
                S = [(mk, r) for mk, r in RR if size(mk) == n]
                if not S: continue
                mk, r = max(S, key=lambda x: x[1][0])
                print(f"     n={n:2d} {r[0]:+.3f} (H1 {r[1]:+.3f} H2 {r[2]:+.3f} Mar {r[3]:+.3f})  {name(mk)}")
        print()


if __name__ == '__main__':
    main()
