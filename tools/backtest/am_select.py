#!/usr/bin/env python3
"""9:35 family: filter the bad, keep the good (governor 2026-11-19: "why are the losers cut only pullback has good filters can you fix
this on the other systems to make sure the bad is filtered out not the good use anything you want to make sure the edge is resiliant over
the same build and test period"). Research only.
The 9:35 family (IBS-LONG sys 4, MIRROR sys 5, DIP sys 2) loses most signals to OTHER FUNDS ON THE SAME 9:35 BAR (only one position;
the live pick is the highest first-5-minute relative volume). Three levers, each judged inside the live book v5.2.64 (PULLBACK, the
family, RELVAL, overnight leg 50%), TRAIN 2022/2024/2026 picks, TEST 2023/2025 judges:
  A  PICK: rank same-bar candidates by another feature instead of relative volume
  B  FILTER: drop a system's trades whose feature is in its worst tail (cut 20/30/40% by a TRAIN quantile). A filter must remove
     trades that lose on TRAIN *and* on TEST (removed-trade PF < 1 in both) to count as 'bad filtered out, good kept'
  C  SPLIT: take the top 2 or 3 same-bar candidates with cash split equally (each its own 1% proxy stop, out 15:55)
Features (all known at 9:35): ibs (prior-day internal bar strength), rsi2, dist20 (prior close vs 20-day average), dist50, rng (prior-day
range %), gap (9:30 open vs prior close %), bar1 (first 5-minute bar return %), ret5 (prior 5-day return %), vol20 (20-day stdev of daily
returns %), rv (relative volume, live pick).
QUALIFIES = beats live on TRAIN compounded and in 2 of 3 train years; PASSES = also beats live in BOTH test years.
    python3 -I tools/backtest/am_select.py > tools/backtest/results/am_select_2026-11-19.txt"""
import itertools, os, statistics as st, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS, new_systems2 as N2
B, BA, SB, TB, dm, TR, TE, ovn = FR.B, FR.BA, FR.SB, FR.TB, FR.dm, FR.TR, FR.TE, FR.ovn
ds = B.ds; END = NS.END
P0 = FR.P0; REL = B.BC.new(ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0)
FAM = {4: FR.I0, 5: FR.M, 2: FR.D}; NAME = {4: 'IBS-LONG', 5: 'MIRROR', 2: 'DIP'}
TRY = {'2022', '2024', '2026'}; TEY = {'2023', '2025'}


def feats(t):
    p, d = t['proxy'], t['day']; f = {}
    f['ibs'] = N2.ibsv(p, d); f['rsi2'] = N2.rsi2(p, d); f['rv'] = t['rv']
    h = N2.hist(p, d, 50)
    if h:
        c = h[2]; f['dist20'] = (c[-1] / st.mean(c[-20:]) - 1) * 100; f['dist50'] = (c[-1] / st.mean(c) - 1) * 100
        f['rng'] = (h[0][-1] - h[1][-1]) / c[-1] * 100; f['ret5'] = (c[-1] / c[-6] - 1) * 100
        r = [c[i] / c[i - 1] - 1 for i in range(len(c) - 20, len(c))]; f['vol20'] = st.pstdev(r) * 100
        b = ds.bars[p][d]; f['gap'] = (b[0][0] / c[-1] - 1) * 100; f['bar1'] = (b[0][3] / b[0][0] - 1) * 100
    return f


for s, L in FAM.items():
    for t in L: t['f'] = feats(t); t['sysf'] = s
FEATS = ['ibs', 'rsi2', 'dist20', 'dist50', 'rng', 'gap', 'bar1', 'ret5', 'vol20', 'rv']


def daily_book(fam):
    return (1 + BA.acct(dm, TB.byday(P0 + REL + fam), after_stop=False)[0]) * (1 + 0.5 * ovn) - 1


def cm(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


def dd(r): eq = np.cumprod(1 + r); return float((1 - eq / np.maximum.accumulate(eq)).max() * 100)


def pf(a): g = sum(x for x in a if x > 0); l = -sum(x for x in a if x <= 0); return g / l if l else 99.0


def acctp(t): return min(1.0, 3.0 / t['leg_risk']) * t['pct']


LIVE = [t for L in FAM.values() for t in L]; r0 = daily_book(LIVE); y0 = SB.yret(r0)


def verdict(y):
    q = cm(y, TR) > cm(y0, TR) and (y[TR] > y0[TR]).sum() >= 2
    return 'PASS' if q and (y[TE] > y0[TE]).all() else 'qual' if q else ''


def row(tag, r, extra=''):
    y = SB.yret(r); v = verdict(y)
    print(f"   {v:<5}{tag:<44} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cm(y, TR) - cm(y0, TR):+7.1f} TEST {cm(y, TE) - cm(y0, TE):+6.1f} (vs live) | DD {dd(r):4.1f}% {extra}", flush=True)
    return y, v


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | TRAIN / TEST compounded, points vs live | max drawdown\n')
    row('LIVE v5.2.64 (pick = relative volume)', r0)
    # ---------------- A: pick
    print('\nA. PICK among same-bar 9:35 candidates (rank replaces relative volume; asc = lowest first)')
    resA = []
    for fe, sign in itertools.product(FEATS[:-1], (1, -1)):
        fam = [dict(t, rv=sign * t['f'].get(fe, 0) if t['f'].get(fe) is not None else -1e9) for t in LIVE]
        y, v = row(f"pick by {fe} {'desc' if sign > 0 else 'asc'}", daily_book(fam)); resA.append((fe, sign, y, v))
    # ---------------- B: filters
    print('\nB. FILTER each system: drop its worst tail on one feature (thresholds from TRAIN trades). removed = trades the filter drops, alone')
    resB = []
    for s, L in FAM.items():
        trn = [t for t in L if t['day'][:4] in TRY]
        for fe in FEATS:
            vals = [t['f'][fe] for t in trn if t['f'].get(fe) is not None]
            if len(vals) < 30: continue
            for q, side in itertools.product((20, 30, 40), ('low', 'high')):
                th = np.percentile(vals, q if side == 'low' else 100 - q)
                drop = lambda t: t['f'].get(fe) is not None and (t['f'][fe] < th if side == 'low' else t['f'][fe] > th)
                rem = [t for t in L if drop(t)]; keepL = [t for t in L if not drop(t)]
                rtr = [acctp(t) for t in rem if t['day'][:4] in TRY]; rte = [acctp(t) for t in rem if t['day'][:4] in TEY]
                fam = keepL + [t for s2, L2 in FAM.items() if s2 != s for t in L2]
                tag = f"{NAME[s]}: drop {fe} {'<' if side == 'low' else '>'} {th:.2f} ({q}%)"
                bad_out = pf(rtr) < 1 and pf(rte) < 1
                y, v = row(tag, daily_book(fam), f"| removed TRAIN n {len(rtr)} PF {pf(rtr):.2f}, TEST n {len(rte)} PF {pf(rte):.2f}{'  <- bad out, good kept' if bad_out else ''}")
                resB.append((tag, y, v, bad_out, s, fe, side, q))
    # ---------------- C: split cash
    print('\nC. SPLIT cash across the top same-bar candidates (rank by relative volume), each its own stop, out 15:55')
    for n in (2, 3):
        by = defaultdict(list)
        for t in LIVE: by[t['day']].append(t)
        fam = []
        for d, cs in by.items():
            cs = sorted(cs, key=lambda t: -t['rv'])[:n]; m = len(cs)
            pct = sum(min(1.0, 3.0 / t['leg_risk']) * t['pct'] for t in cs) / m
            fam.append(dict(day=d, k=1, xbar=max(t['xbar'] for t in cs), pct=pct, leg_risk=3.0, rv=max(t['rv'] for t in cs), sys=cs[0]['sys'],
                            early=any(t['xbar'] < END - 1 for t in cs)))
        row(f'split cash across top {n}', daily_book(fam))
    # ---------------- picks
    print('\nPRE-SET PICKS (best TRAIN among qualifiers, read against TEST after)')
    qa = [r for r in resA if r[3]]
    if qa: a = max(qa, key=lambda r: cm(r[2], TR)); print(f"   A: pick by {a[0]} {'desc' if a[1] > 0 else 'asc'} -> {a[3]}")
    else: print('   A: no pick qualifies; relative volume stays')
    for s in FAM:
        qb = [r for r in resB if r[2] and r[4] == s]
        if qb: b = max(qb, key=lambda r: cm(r[1], TR)); print(f"   B {NAME[s]}: {b[0]} -> {b[2]}; removed trades lose on train and test: {'yes' if b[3] else 'NO'}")
        else: print(f"   B {NAME[s]}: no filter qualifies")
    good = [r for r in resB if r[2] == 'PASS' and r[3]]
    print(f"\n   filters that PASS and remove losers in both periods: {len(good)}")
    for r in good: print(f"      {r[0]}")


if __name__ == '__main__':
    main()
