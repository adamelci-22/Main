#!/usr/bin/env python3
"""BIG-WIN study: few, high-conviction FEAR-DIP calls that let winners run (governor 2026-11-12: "a couple consistent big
winners rather than trying forever", no +50% cap).

    python3 tools/scanner/bigwin.py > tools/scanner/results/bigwin.txt

A. Exit structures, all FEAR-DIP signals (fixed before running):
   S1 base: 42-session 0.75-delta, sell at session 10
   S2 63-session 0.70-delta, sell at session 20
   S3 63-session 0.70-delta, hold up to 30, exit when the stock closes under its prior 10-session low
   S4 63-session 0.70-delta, hold up to 30, once up +50% exit on a 35% give-back from the option's peak
B. Concentration: per signal day keep only the top K names, ranked by (a) the P50 model's out-of-sample score,
   (b) beta, (c) deepest 5-day drop, against (d) all and (e) random K (mean of 200 draws).
C. A few-trades portfolio: at most 3 open, 10% of equity in premium each.
"""
import math, os, pickle, random, statistics as st, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lab as L
from winners import beta

STRUCTS = [('S1 42s .75d hold 10', L.OC(dte=42, delta=0.75, hold=10)),
           ('S2 63s .70d hold 20', L.OC(dte=63, delta=0.70, hold=20)),
           ('S3 63s .70d trail stock 10d low, max 30', L.OC(dte=63, delta=0.70, hold=30, exit_mode='trail_und', trail_n=10)),
           ('S4 63s .70d trail option +50%/-35%, max 30', L.OC(dte=63, delta=0.70, hold=30, exit_mode='trail_opt'))]


def trades(U, reg, vix, oc):
    T = []; seen = set()
    for nm in L.CORE:
        for t in L.run(U, reg, vix, nm, oc, flt=L.CORE_FLT):
            if (t['sym'], t['d']) in seen: continue
            seen.add((t['sym'], t['d'])); t['sig'] = nm[:2]; T.append(t)
    return T


def line(T, ep):
    if len(T) < 5: return f'n {len(T)}'
    r = [t['ret'] for t in T]; tot = sum(r); top = sorted(r, reverse=True)
    eps = defaultdict(list)
    for t in T: eps[ep.get(t['d'])].append(t['ret'])
    pos = sum(st.mean(v) > 0 for v in eps.values())
    return (f"n {len(r):4d} | win {100*st.mean(x > 0 for x in r):3.0f}% | >=+50% {100*st.mean(x >= .5 for x in r):3.0f}% | >=+100% {100*st.mean(x >= 1 for x in r):3.0f}% "
            f"| mean {100*st.mean(r):+6.1f}% median {100*st.median(r):+5.1f}% | avg loss {100*st.mean([x for x in r if x <= 0] or [0]):+5.0f}% "
            f"| best {100*top[0]:+4.0f}% | top 10% of trades = {100*sum(top[:max(1, len(r)//10)])/tot if tot > 0 else float('nan'):3.0f}% of profit | episodes + {pos}/{len(eps)}")


def main():
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    ep = L.episodes(reg)
    print('A. EXIT STRUCTURES (all FEAR-DIP signals, 2023-2026, modelled prices)')
    res = {}
    for nm, oc in STRUCTS:
        T = trades(U, reg, vix, oc); res[nm] = T
        dv = [t for t in T if t['d'] < L.SPLIT]; ts = [t for t in T if t['d'] >= L.SPLIT]
        print(f'  {nm}\n     ALL  {line(T, ep)}\n     DEV  {line(dv, ep)}\n     TEST {line(ts, ep)}')
    # stress the best-looking structures
    print('\n   stress (IV 30% richer + spread 3%):')
    for nm, oc in STRUCTS:
        from dataclasses import replace
        T = trades(U, reg, vix, replace(oc, vrp=1.3, hs_pct=0.03))
        print(f'  {nm:42s} {line(T, ep)}')

    # P50 out-of-sample scores keyed by (date, sym, call)
    X, Y, R, META = pickle.load(open(os.path.join(HERE, 'data', 'p50_rows.pkl'), 'rb'))
    P = np.load(os.path.join(HERE, 'data', 'p50_oos.npy'))
    score = {(m[0], m[1]): P[i] for i, m in enumerate(META) if m[2] > 0 and not np.isnan(P[i])}
    print('\nB. CONCENTRATION: keep only the top K names per signal day (P50 scores exist from 2023-07)')
    for nm, _ in STRUCTS:
        T = [t for t in res[nm] if (t['d'], t['sym']) in score]
        for t in T:
            S = U[t['sym']]; i = t['i']
            t['p50'] = score[(t['d'], t['sym'])]; t['beta'] = beta(U, t['sym'], i) or 0; t['drop5'] = S['c'][i] / S['c'][i - 5] - 1
        byd = defaultdict(list)
        for t in T: byd[t['d']].append(t)
        print(f'  {nm}  (scored trades {len(T)} on {len(byd)} days)')
        print(f'     all            {line(T, ep)}')
        for K in (1, 2, 3):
            for key, rev, lab in (('p50', True, 'P50 model'), ('beta', True, 'highest beta'), ('drop5', False, 'deepest 5d drop')):
                pick = [t for v in byd.values() for t in sorted(v, key=lambda t: t[key], reverse=rev)[:K]]
                print(f'     top {K} {lab:15s} {line(pick, ep)}')
            rnd = []
            for sd in range(200):
                rng = random.Random(sd); pick = [t for v in byd.values() for t in rng.sample(v, min(K, len(v)))]
                rnd.append(st.mean(t['ret'] for t in pick))
            print(f'     top {K} random          mean {100*st.mean(rnd):+6.1f}% (5th-95th pct of 200 draws {100*sorted(rnd)[10]:+.1f}% .. {100*sorted(rnd)[190]:+.1f}%)')

    print('\nC. FEW-TRADES PORTFOLIO: max 3 open, 10% of equity in premium each, P50-ranked within each signal day')
    for nm, oc in STRUCTS:
        T = sorted([t for t in res[nm] if 'p50' in t], key=lambda t: (t['d'], -t['p50']))
        eq = 1.0; peak = 1.0; mdd = 0; opn = []; n = 0; yr = defaultdict(float); bigs = 0
        for t in T:
            S = U[t['sym']]; i = t['i']; xd = S['d'][min(i + 1 + oc.hold, len(S['d']) - 1)]
            opn = [x for x in opn if x > t['d']]
            if len(opn) >= 3: continue
            pnl = eq * 0.10 * t['ret']; eq += pnl; n += 1; bigs += t['ret'] >= 1; opn.append(xd)
            peak = max(peak, eq); mdd = max(mdd, 1 - eq / peak); yr[t['d'][:4]] += pnl
        print(f"  {nm:42s} trades {n:3d} (doublers {bigs}) | x{eq:.2f} | max DD {100*mdd:.0f}% | " + ', '.join(f'{y} {v:+.2f}' for y, v in sorted(yr.items())))


if __name__ == '__main__':
    main()
