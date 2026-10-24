#!/usr/bin/env python3
"""PULLBACK ALONE (no FADE in the account): best combination of tickers from the live list + every tradable ticker in the governor's 22-row table.
    python3 tools/backtest/pb_alone_search.py > tools/backtest/results/pb_alone_search.txt
Pool = every ticker that formed at least one setup in 157 days. Every subset is scored (bitmask search, 4 processes) on the full sample,
both halves, the untouched March window and the tuning window. Account rules = mixed.account('one'): 3% risk capped at cash, one position,
max 3 entries/day, earliest trigger first, ties by proxy RVOL. Daily % does not depend on equity, so window means are exact.
"""
import heapq, os, statistics as st, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, final_system as FS, combo_search as C, twobar as TB
from lab import get_data

TABLE = ['NVDU', 'NVDD', 'AAPU', 'AAPD', 'AMZU', 'AMZD', 'METU', 'METD', 'MSFU', 'MSFD', 'NFLU', 'TQQQ', 'SQQQ', 'UPRO', 'SPXU', 'TNA', 'TZA',
         'SOXL', 'SOXS', 'TECL', 'TECS', 'LABU', 'LABD', 'CURE', 'RXD', 'FAS', 'FAZ', 'NUGT', 'DUST', 'ERX', 'ERY', 'GUSH', 'DRIP', 'TMF', 'TMV']
LIVE = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD']
SINGLE = {'NVD', 'NVDU', 'NVDD', 'AAPU', 'AAPD', 'AMZU', 'AMZD', 'METU', 'METD', 'MSFU', 'MSFD', 'NFLU'}
G = {}


def init(days_by, idx):
    G['days_by'] = days_by; G['idx'] = idx


def score(mask):
    out = []
    for cs in G['days_by']:
        if not cs: out.append(0.0); continue
        av0 = [c for c in cs if mask >> c[6] & 1]
        if not av0: out.append(0.0); continue
        free = 0; n = 0; r = 1.0
        while av0 and n < 3:
            av = [c for c in av0 if c[1] >= free]
            if not av: break
            k0 = av[0][1]; same = [c for c in av if c[1] == k0]
            c = max(same, key=lambda c: c[5]) if len(same) > 1 else same[0]
            r *= 1 + min(1.0, 0.03 / (c[4] / 100)) * c[3] / 100
            free = c[2] + 1; av0.remove(c); n += 1
        out.append((r - 1) * 100)
    return mask, tuple(sum(out[i] for i in ix) / len(ix) for ix in G['idx'])


def main():
    t0 = time.time()
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    PI.PROXY.update(C.PB_MAP)
    allt = LIVE + [t for t in TABLE if t not in LIVE]
    cand = {}
    for q in allt:
        if q not in D.bars: continue
        PI.PROXY.setdefault(q, q)
        s = PBF.run(D, days, [q], oco_gap=True)
        cand[q] = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    dv = {q: EX.dollar_vol(D, q, days) for q in cand}
    pool = [q for q in allt if cand.get(q)]
    print(f"PULLBACK ALONE, 157 days 2026-03-03..10-14. Tickers with no setup at all: {[q for q in allt if q in cand and not cand[q]]}; not testable: GOOU AVGL AVGD NFLD QCL QCD SICK (no such ETF), GOOD (a REIT)\n")
    print(f"{'ticker':<6}{'live':>5}{'single':>7}{'setups':>7}{'win%':>6}{'avg%':>7}{'sum%':>7}{'-best2':>7}{'median':>8}{'$vol/bar':>10}")
    for q in pool:
        r = sorted(c['pct'] for c in cand[q])
        print(f"{q:<6}{'*' if q in LIVE else '':>5}{'yes' if q in SINGLE else '':>7}{len(r):>7}{100*sum(x>0 for x in r)/len(r):>6.0f}{st.mean(r):>+7.2f}{sum(r):>+7.1f}{sum(r[:-2]):>+7.1f}{st.median(r):>+8.2f}{dv[q]/1e3:>9,.0f}k")
    # verify the fast scorer against the engine on the live list
    a = MXD.account(D, days, [c for q in LIVE for c in cand[q]])
    pack = lambda c, i: (c['day'], c['k'], c['xbar'], c['pct'], c['risk'], TB.rvol(D, c['proxy'], c['day'], c['k']), i)
    by = {d: [] for d in days}
    for i, q in enumerate(pool):
        for c in cand[q]: by[c['day']].append(pack(c, i))
    days_by = [sorted(by[d], key=lambda c: c[1]) for d in days]
    h = len(days) // 2; W = ['full', 'H1', 'H2', 'March', 'tune']
    idx = [list(range(len(days))), list(range(h)), list(range(h, len(days))), [i for i, d in enumerate(days) if d < '2026-04-07'], [i for i, d in enumerate(days) if d >= '2026-04-07']]
    init(days_by, idx)
    lm = sum(1 << pool.index(q) for q in LIVE)
    print(f"\nVERIFY live list: engine {st.mean(a['daily'].values()):+.4f}%/day, fast scorer {score(lm)[1][0]:+.4f}%/day")
    N = len(pool); print(f"\nSearching all {2**N-1:,} subsets of {N} tickers (streaming: only the leaders are kept)...", flush=True)
    name = lambda mk: ', '.join(pool[i] for i in range(N) if mk >> i & 1)
    size = lambda mk: bin(mk).count('1')
    liquid = sum(1 << i for i, q in enumerate(pool) if dv[q] >= C.MIN_DV)
    etf = sum(1 << i for i, q in enumerate(pool) if q not in SINGLE)
    lv = score(lm)[1]
    FILT = [('ALL tickers', (1 << N) - 1), ('LIQUID (>= $100k/bar)', liquid), ('LIQUID + NO single stocks', liquid & etf)]
    step = 1 << 14; chunks = [(a, min(a + step, 1 << N)) for a in range(1, 1 << N, step)]
    with Pool(4, initializer=init2, initargs=(days_by, idx, lv, [f for _, f in FILT], N)) as P:
        parts = list(P.imap_unordered(work, chunks))
    print(f"(done in {time.time()-t0:.0f}s)\n")
    def trades(mk):
        a = MXD.account(D, days, [c for i in range(N) if mk >> i & 1 for c in cand[pool[i]]]); t = a['taken']
        r = sorted(min(1, 0.03 / (x['risk'] / 100)) * x['pct'] for x in t)
        return len(t), 100 * sum(x > 0 for x in r) / max(1, len(r)), sum(r), sum(r[:-2]), a['mdd']
    print(f"LIVE {LIVE}: " + ' '.join(f"{w} {lv[j]:+.3f}" for j, w in enumerate(W)) + "  (trades %d, win %.0f%%, sum acct%% %+.1f, without best 2 %+.1f, DD %.1f%%)" % trades(lm))
    for fi, (tag, fm) in enumerate(FILT):
        top = heapq.nlargest(10, (x for pt in parts for x in pt[fi]['top']))
        cnt = sum(pt[fi]['n'] for pt in parts); better = sum(pt[fi]['better'] for pt in parts); nrob = sum(pt[fi]['nrob'] for pt in parts)
        rob = heapq.nlargest(10, (x for pt in parts for x in pt[fi]['rob']))
        print(f"\n======== [{tag}] {cnt:,} lists; live list ranks {better+1:,} ========")
        print("  Top 10 full sample:")
        for v, mk, r in top:
            n, w, s_, s2, dd = trades(mk)
            print(f"    n={size(mk):2d} {name(mk):<56} " + ' '.join(f"{w_} {r[j]:+.3f}" for j, w_ in enumerate(W[:4])) + f"  trades {n} win {w:.0f}% -best2 {s2:+.1f} DD {dd:.1f}%")
        print(f"  Beat the live list on full AND H1 AND H2 AND March: {nrob:,}")
        for v, mk, r in rob:
            n, w, s_, s2, dd = trades(mk)
            print(f"    n={size(mk):2d} {name(mk):<56} " + ' '.join(f"{w_} {r[j]:+.3f}" for j, w_ in enumerate(W[:4])) + f"  trades {n} win {w:.0f}% -best2 {s2:+.1f} DD {dd:.1f}%")
        print("  Walk-forward (choose the best list on one window, judge on another):")
        for a_, b_ in ((4, 3), (1, 2), (2, 1)):
            v, mk, r = max(pt[fi]['best'][a_] for pt in parts if pt[fi]['best'][a_])
            print(f"    choose on {W[a_]:<5} -> n={size(mk):2d} {name(mk):<52} {W[a_]} {r[a_]:+.3f} -> {W[b_]} {r[b_]:+.3f}  (live {lv[b_]:+.3f})")
        print("  Best list of each size (full sample):")
        for k in range(1, N + 1):
            c = [pt[fi]['size'].get(k) for pt in parts if pt[fi]['size'].get(k)]
            if not c: continue
            v, mk, r = max(c)
            print(f"    n={k:2d} {r[0]:+.3f} (H1 {r[1]:+.3f} H2 {r[2]:+.3f} Mar {r[3]:+.3f})  {name(mk)}")


def init2(days_by, idx, lv, fms, N):
    G.update(days_by=days_by, idx=idx, lv=lv, fms=fms, N=N)


def work(rng):
    lv = G['lv']; out = []
    acc = [dict(top=[], rob=[], n=0, better=0, nrob=0, best=[None] * 5, size={}) for _ in G['fms']]
    for mk in range(*rng):
        _, r = score(mk); sz = bin(mk).count('1')
        for fi, fm in enumerate(G['fms']):
            if mk & ~fm: continue
            a = acc[fi]; a['n'] += 1; e = (r[0], mk, r)
            if r[0] > lv[0]: a['better'] += 1
            if len(a['top']) < 10: heapq.heappush(a['top'], e)
            elif r[0] > a['top'][0][0]: heapq.heapreplace(a['top'], e)
            if r[0] > lv[0] and r[1] >= lv[1] and r[2] >= lv[2] and r[3] >= lv[3]:
                a['nrob'] += 1
                if len(a['rob']) < 10: heapq.heappush(a['rob'], e)
                elif r[0] > a['rob'][0][0]: heapq.heapreplace(a['rob'], e)
            for j in (1, 2, 4):
                if a['best'][j] is None or r[j] > a['best'][j][0]: a['best'][j] = (r[j], mk, r)
            if sz not in a['size'] or r[0] > a['size'][sz][0]: a['size'][sz] = e
    return acc


if __name__ == '__main__':
    main()
