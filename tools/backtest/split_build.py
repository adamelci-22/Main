#!/usr/bin/env python3
"""Four-system build, second pass (governor 2026-11-12 evening): TRAIN = calendar 2022, 2024, 2026. TEST = 2023 and 2025.
Every setting is chosen on the TRAIN years only and judged on the TEST years only. Massive 5-minute tape (6 proxies, 4 PULLBACK legs).
  SYSTEM 1  robust over time: the live FADE + PULLBACK knobs scored by the WORST train year, averaged over the setting and its
            one-step neighbours on the grid (a pick must sit on a plateau), all three train years positive, ties to lower drawdown.
  SYSTEM 2  most consistent months: every year scored ALONE. Per year: share of winning months and the median month. The score is
            the WORST train year's figure (rank of the worst-year winning share + rank of the worst-year median month, both
            neighbour-averaged). One strong year cannot lift it.
  SYSTEM 3  RELVAL, DIP, IBS-TREND re-chosen on the train years (best worst-train-year, alone), judged on 2023 and 2025. Then:
            parallel or replacement? Time overlap, blocked days, and the book with and without each one.
Account: 3% risk a trade capped at cash, one position at a time, 3 entries a day, same-system loss block.
    python3 -I tools/backtest/split_build.py > tools/backtest/results/split_build_2026-11-13.txt"""
import itertools, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tune_book as TB, book_compare as BC, new_systems as NS, new_systems2 as N2
TRAIN = ('2022', '2024', '2026'); TEST = ('2023', '2025'); YEARS = ('2022', '2023', '2024', '2025', '2026')
dm = [d for d in TB.days_m if d >= '2022-01-01']; yr = np.array([d[:4] for d in dm]); ym = np.array([d[:7] for d in dm]); MONTHS = sorted(set(ym))
YM = {y: yr == y for y in YEARS}; T0 = time.time()


def acct(days, by, fmax=None, lossblock=True, risk=3.0, cap=3):
    """Daily account returns. by: {day: [trades]}. fmax(day) caps the position as a share of cash (default 1.0)."""
    out = np.zeros(len(days))
    for n, d in enumerate(days):
        cs = by.get(d)
        if not cs: continue
        cs = sorted(cs, key=lambda t: (t['k'], -t['rv'], t['sys'])); free = 0; eq = 0.0; cnt = 0; blocked = set(); fm = fmax(d) if fmax else 1.0
        for t in cs:
            if cnt >= cap: break
            if t['k'] < free or t['sys'] in blocked: continue
            g = min(fm, risk / t['leg_risk']) * t['pct'] / 100; eq = (1 + eq) * (1 + g) - 1; free = t['xbar'] + 1; cnt += 1
            if lossblock and g <= 0: blocked.add(t['sys'])
        out[n] = eq
    return out


def yret(R): return np.stack([np.expm1(np.log1p(R[..., YM[y]]).sum(-1)) for y in YEARS], -1) * 100


def ydd(R):
    out = []
    for y in YEARS:
        cum = np.cumsum(np.log1p(R[..., YM[y]]), -1); pk = np.maximum.accumulate(np.maximum(cum, 0), -1); out.append((1 - np.exp(cum - pk)).max(-1) * 100)
    return np.stack(out, -1)


def mret(R): return np.stack([np.expm1(np.log1p(R[..., ym == m]).sum(-1)) for m in MONTHS], -1) * 100


def mstats(mo):
    """mo: (..., months). Per year: winning share %, mean, median, worst."""
    out = {}
    for y in YEARS:
        x = mo[..., [i for i, m in enumerate(MONTHS) if m[:4] == y]]; out[y] = (100 * (x > 0).mean(-1), x.mean(-1), np.median(x, -1), x.min(-1))
    return out


def table(r):
    y = yret(r); dd = ydd(r); ms = mstats(mret(r))
    print(f"      {'year':<12} {'return':>8} {'max DD':>7} | months: {'win %':>6} {'mean':>7} {'median':>7} {'worst':>7}")
    for i, yy in enumerate(YEARS):
        w, mn, md, wo = ms[yy]; print(f"      {yy} {'TRAIN' if yy in TRAIN else 'TEST ':<6} {y[i]:+8.1f} {dd[i]:7.1f} | {w:14.0f} {mn:+7.2f} {md:+7.2f} {wo:+7.1f}")
    te = [YEARS.index(x) for x in TEST]; tr = [YEARS.index(x) for x in TRAIN]
    print(f"      TEST 2023+2025 compounded {(np.prod(1 + y[te] / 100) - 1) * 100:+.1f}%, worst test DD {dd[te].max():.1f} | TRAIN compounded {(np.prod(1 + y[tr] / 100) - 1) * 100:+.1f}%")


def votes(keys, top):
    v = {}
    for i in top:
        for part in (keys[i][0] + '|' + keys[i][1]).split('|'): v[part] = v.get(part, 0) + 1
    return ', '.join(f"{k} {100 * n / len(top):.0f}%" for k, n in sorted(v.items(), key=lambda z: -z[1])[:12])


def rank(v): return np.argsort(np.argsort(v))


def tune():
    FC, PC = TB.build(); fk = list(FC['M']); pk = list(PC['M']); keys = [(a, b) for a in fk for b in pk if not (a == 'FADE off' and b == 'PB off')]
    R = np.zeros((len(keys), len(dm)), dtype=np.float32)
    for i, (a, b) in enumerate(keys): R[i] = acct(dm, {d: FC['M'][a].get(d, []) + PC['M'][b].get(d, []) for d in set(FC['M'][a]) | set(PC['M'][b])})
    print(f"# tuned {len(keys)} ({time.time() - T0:.0f}s)", file=sys.stderr, flush=True)
    Y = yret(R); DD = ydd(R); MS = mstats(mret(R)); ix = {k: i for i, k in enumerate(keys)}
    alt = [sorted({a.split('|')[j] for a in fk if a != 'FADE off'}) for j in range(7)], [sorted({b.split('|')[j] for b in pk if b != 'PB off'}) for j in range(4)]

    def neigh(k):
        a, b = k; out = []
        if a != 'FADE off':
            ta = a.split('|')
            for j in range(7): out += [('|'.join(ta[:j] + [v] + ta[j + 1:]), b) for v in alt[0][j] if v != ta[j]]
        if b != 'PB off':
            tb = b.split('|')
            for j in range(4): out += [(a, '|'.join(tb[:j] + [v] + tb[j + 1:])) for v in alt[1][j] if v != tb[j]]
        return [ix[x] for x in out if x in ix]
    NB = [neigh(k) for k in keys]

    def smooth(v): return np.array([(v[i] + v[NB[i]].sum()) / (1 + len(NB[i])) for i in range(len(keys))])
    tr = [YEARS.index(x) for x in TRAIN]; te = [YEARS.index(x) for x in TEST]; li = ix[(TB.LIVE_F, TB.LIVE_P)]
    testc = (np.prod(1 + Y[:, te] / 100, 1) - 1) * 100
    print(__doc__.split('\n')[0]); print(f"Massive tape {dm[0]}..{dm[-1]}; {len(keys)} combinations of the live knobs; TRAIN {', '.join(TRAIN)}; TEST {', '.join(TEST)}\n")
    print('LIVE v5.2.46'); print(f"   FADE: {TB.LIVE_F}\n   PULLBACK: {TB.LIVE_P}"); table(R[li])
    # ---- SYSTEM 1
    raw1 = Y[:, tr].min(1); s1 = smooth(raw1); ok = (Y[:, tr] > 0).all(1); order1 = np.lexsort((DD[:, tr].max(1), -np.round(np.where(ok, s1, -1e9), 1)))
    print(f"\nSYSTEM 1: robust over time (score = worst TRAIN year, averaged with the one-step neighbours; all three train years positive: {int(ok.sum())} of {len(keys)} qualify)")
    p1 = int(order1[0]); print(f"   FADE: {keys[p1][0]}\n   PULLBACK: {keys[p1][1]}\n   score {s1[p1]:+.1f} (own worst train year {raw1[p1]:+.1f}); live score {s1[li]:+.1f} (own {raw1[li]:+.1f})"); table(R[p1])
    print('   next five:')
    for i in order1[1:6]: print(f"      score {s1[i]:+5.1f} train {' '.join(f'{v:+6.1f}' for v in Y[i, tr])} | test 2023 {Y[i, 1]:+6.1f} 2025 {Y[i, 3]:+6.1f} | {keys[i][0]} || {keys[i][1]}")
    top = order1[:max(50, len(keys) // 100)]
    print(f"   top 1% ({len(top)}): common settings: " + votes(keys, top))
    print(f"   does the score transfer? top 1% on TEST: 2023 median {np.median(Y[top, 1]):+.1f}% (live {Y[li, 1]:+.1f}%), 2025 median {np.median(Y[top, 3]):+.1f}% (live {Y[li, 3]:+.1f}%); beat live in 2023 {100 * np.mean(Y[top, 1] > Y[li, 1]):.0f}%, in 2025 {100 * np.mean(Y[top, 3] > Y[li, 3]):.0f}%, in both {100 * np.mean((Y[top, 1] > Y[li, 1]) & (Y[top, 3] > Y[li, 3])):.0f}%")
    print(f"   all {len(keys)}: test 2023+2025 compounded median {np.median(testc):+.1f}%, live {testc[li]:+.1f}% ({100 * np.mean(testc < testc[li]):.0f}th percentile), pick {testc[p1]:+.1f}% ({100 * np.mean(testc < testc[p1]):.0f}th); rank correlation of the score with the test result {np.corrcoef(rank(s1), rank(testc))[0, 1]:+.2f}")
    # ---- SYSTEM 2
    wmin = np.min([MS[y][0] for y in TRAIN], 0); mmin = np.min([MS[y][2] for y in TRAIN], 0); sw = smooth(wmin); sm = smooth(mmin)
    rk = rank(-sw) + rank(-sm); order2 = np.argsort(rk, kind='stable'); p2 = int(order2[0])
    print("\nSYSTEM 2: most consistent months (each year alone; score = the WORST train year's winning-month share and median month, neighbour-averaged, ranks summed)")
    print(f"   FADE: {keys[p2][0]}\n   PULLBACK: {keys[p2][1]}\n   worst train year: winning months {wmin[p2]:.0f}% (live {wmin[li]:.0f}%), median month {mmin[p2]:+.2f}% (live {mmin[li]:+.2f}%)"); table(R[p2])
    print('   next five:')
    for i in order2[1:6]: print(f"      worst-year win {wmin[i]:3.0f}% median {mmin[i]:+5.2f} | test 2023 win {MS['2023'][0][i]:3.0f}% med {MS['2023'][2][i]:+5.2f}, 2025 win {MS['2025'][0][i]:3.0f}% med {MS['2025'][2][i]:+5.2f} | {keys[i][0]} || {keys[i][1]}")
    top2 = order2[:max(50, len(keys) // 100)]
    print(f"   top 1% ({len(top2)}): common settings: " + votes(keys, top2))
    tw = np.min([MS[y][0] for y in TEST], 0); tmd = np.min([MS[y][2] for y in TEST], 0)
    print(f"   does it transfer? top 1% on TEST: worst test-year winning share median {np.median(tw[top2]):.0f}% (live {tw[li]:.0f}%), worst test-year median month {np.median(tmd[top2]):+.2f}% (live {tmd[li]:+.2f}%); beat live on both figures {100 * np.mean((tw[top2] > tw[li]) & (tmd[top2] > tmd[li])):.0f}%")
    print(f"   all {len(keys)}: live sits at the {100 * np.mean(tw < tw[li]):.0f}th percentile on test winning share and the {100 * np.mean(tmd < tmd[li]):.0f}th on test median month; pick {100 * np.mean(tw < tw[p2]):.0f}th and {100 * np.mean(tmd < tmd[p2]):.0f}th")
    return keys[p1], keys[p2], FC, PC


def system3(p1, p2, FC, PC):
    ds, ctx = TB.ds_m, TB.cx_m; tr = [YEARS.index(x) for x in TRAIN]; te = [YEARS.index(x) for x in TEST]
    G = [('RELVAL', NS.relval, 3, [dict(a=48, z=72, xm=x, ksd=k) for x, k in itertools.product((0.75, 1.0, 1.25), (2.0, 2.5, 3.0))]),
         ('DIP', N2.rsi2d, 2, [dict(th=t, n=n, last=l) for t, n, l in itertools.product((5, 10, 15, 20), (20, 50, 100), (NS.NOON, NS.END))]),
         ('IBS-TREND', N2.ibsf, 4, [dict(lo=t, n=n, last=l) for t, n, l in itertools.product((0.1, 0.2, 0.3), (20, 50, 100), (NS.NOON, NS.END))])]
    print('\nSYSTEM 3: the three new systems re-chosen on the TRAIN years (alone, best worst-train-year), judged on 2023 and 2025')
    pick = {}
    for name, fn, sid, grid in G:
        rows = []
        for kw in grid:
            T = BC.new(ds, ctx, dm, fn, kw, sid); r = acct(dm, TB.byday(T)); y = yret(r); rows.append((kw, T, r, y, ydd(r)))
        b = max(range(len(rows)), key=lambda i: (rows[i][3][tr].min(), rows[i][3][tr].sum()))
        print(f"   {name}: {len(grid)} settings. Years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th). * = TRAIN pick")
        for i, (kw, T, r, y, dd) in enumerate(rows):
            lab = str({k: (('13:30' if v == NS.NOON else '15:55') if k == 'last' else v) for k, v in kw.items() if k not in ('a', 'z')})[1:-1].replace(chr(39), '')
            print(f"     {'*' if i == b else ' '} {lab:<34} {' '.join(f'{v:+6.1f}' for v in y)} | worst train {y[tr].min():+6.1f} | test 2023 {y[1]:+6.1f} 2025 {y[3]:+6.1f} | trades {len(T)} DD {dd.max():.1f}")
        pos = sum(bool((rows[i][3][te] > 0).all()) for i in range(len(rows)))
        print(f"       settings positive in BOTH test years: {pos} of {len(rows)}; train pick test: 2023 {rows[b][3][1]:+.1f}%, 2025 {rows[b][3][3]:+.1f}%")
        pick[name] = rows[b]
    # ---- parallel or replacement
    fd = BC.fade(ds, ctx, dm, 0.5, {}); pb = BC.pb(ds, dm, BC.PS.LEGS_M, {}, BC.RUN); live = fd + pb

    def book(key): return [t for d, v in FC['M'][key[0]].items() for t in v if d >= '2022'] + [t for d, v in PC['M'][key[1]].items() for t in v if d >= '2022']
    S1 = book(p1); S2 = book(p2)
    REL, DIP, IBS = pick['RELVAL'][1], pick['DIP'][1], pick['IBS-TREND'][1]
    dd_ = {(t['day'], t['proxy']) for t in DIP}; DOI = DIP + [dict(t, sys=2) for t in IBS if (t['day'], t['proxy']) not in dd_]
    print('\nPARALLEL OR REPLACEMENT? (one position at a time, earliest signal first)')
    print('   clock: entry time (median, 10th-90th percentile) and exit')
    hhmm = lambda k: f"{9 + (30 + 5 * int(k)) // 60}:{(30 + 5 * int(k)) % 60:02d}"
    for nm, T in (('FADE', fd), ('PULLBACK', pb), ('RELVAL', REL), ('DIP', DIP), ('IBS-TREND', IBS)):
        k = np.array([t['k'] for t in T]); x = np.array([t['xbar'] for t in T])
        print(f"      {nm:<10} n {len(T):4d} | entry {hhmm(np.median(k))} ({hhmm(np.percentile(k, 10))}-{hhmm(np.percentile(k, 90))}) | exit median {hhmm(np.median(x) + 1)}, latest {hhmm(x.max() + 1)} | signal days {len({t['day'] for t in T})} of {len(dm)}")
    liveby = TB.byday(live); rl = acct(dm, liveby); di = {d: i for i, d in enumerate(dm)}
    print('   signal days: what the live book did on them, what the new system did alone, and both in one account')
    for nm, T in (('RELVAL', REL), ('DIP', DIP), ('IBS-TREND', IBS)):
        days = sorted({t['day'] for t in T}); own = acct(dm, TB.byday(T)); both = acct(dm, TB.byday(live + T))
        lv = np.array([rl[di[d]] for d in days]) * 100; nw = np.array([own[di[d]] for d in days]) * 100; cb = np.array([both[di[d]] for d in days]) * 100; has = np.array([d in liveby for d in days])
        for tag, sel in (('TRAIN', TRAIN), ('TEST', TEST)):
            m = np.array([d[:4] in sel for d in days])
            print(f"      {nm:<10} {tag}: {int(m.sum()):3d} signal days | live also had a trade on {100 * has[m].mean():3.0f}% | per signal day: live alone {lv[m].mean():+.2f}%, {nm} alone {nw[m].mean():+.2f}%, both in one account {cb[m].mean():+.2f}%, sum of the two {lv[m].mean() + nw[m].mean():+.2f}%")

    def split(A, Bk):                               # days lane A has a signal: half the cash each lane; other days lane B has all of it
        S = {t['day'] for t in A}; return acct(dm, TB.byday(A), fmax=lambda d: 0.5) + acct(dm, TB.byday(Bk), fmax=lambda d: 0.5 if d in S else 1.0)
    BOOKS = [('LIVE (FADE + PULLBACK)', acct(dm, TB.byday(live))), ('LIVE + RELVAL', acct(dm, TB.byday(live + REL))), ('LIVE + DIP (one position, DIP first)', acct(dm, TB.byday(live + DIP))),
             ('LIVE + DIP (split cash 50/50 on DIP days)', split(DIP, live)), ('LIVE + IBS-TREND (one position)', acct(dm, TB.byday(live + IBS))), ('LIVE + IBS-TREND (split cash)', split(IBS, live)),
             ('LIVE + DIP + RELVAL', acct(dm, TB.byday(live + DIP + REL))), ('LIVE + DIP + RELVAL (split cash)', split(DIP, live + REL)), ('LIVE + DIP-or-IBS + RELVAL', acct(dm, TB.byday(live + DOI + REL))),
             ('LIVE + DIP-or-IBS + RELVAL (split cash)', split(DOI, live + REL)), None, ('NEW ONLY: DIP + RELVAL', acct(dm, TB.byday(DIP + REL))), ('NEW ONLY: DIP-or-IBS + RELVAL', acct(dm, TB.byday(DOI + REL))),
             ('RELVAL alone', acct(dm, TB.byday(REL))), ('DIP alone', acct(dm, TB.byday(DIP))), ('IBS-TREND alone', acct(dm, TB.byday(IBS))), None,
             ('SYSTEM 1 (train pick)', acct(dm, TB.byday(S1))), ('SYSTEM 1 + RELVAL', acct(dm, TB.byday(S1 + REL))), ('SYSTEM 1 + DIP + RELVAL', acct(dm, TB.byday(S1 + DIP + REL))), ('SYSTEM 1 + DIP + RELVAL (split cash)', split(DIP, S1 + REL)),
             ('SYSTEM 2 (train pick)', acct(dm, TB.byday(S2))), ('SYSTEM 2 + RELVAL', acct(dm, TB.byday(S2 + REL))), ('SYSTEM 2 + DIP + RELVAL', acct(dm, TB.byday(S2 + DIP + REL)))]
    print(f"\n   {'book':<42} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7} {'2026':>7} | TRAIN cmpd  TEST cmpd | max DD | months win% avg (worst year)")
    for bk in BOOKS:
        if bk is None: print(); continue
        nm, r = bk; y = yret(r); dd = ydd(r); ms = mstats(mret(r)); w = [float(ms[yy][0]) for yy in YEARS]
        print(f"   {nm:<42} {' '.join(f'{v:+7.1f}' for v in y)} | {(np.prod(1 + y[tr] / 100) - 1) * 100:+9.1f}% {(np.prod(1 + y[te] / 100) - 1) * 100:+9.1f}% | {dd.max():6.1f} | {np.mean(w):3.0f}% ({min(w):.0f}%)")


if __name__ == '__main__':
    p1, p2, FC, PC = tune(); system3(p1, p2, FC, PC)
