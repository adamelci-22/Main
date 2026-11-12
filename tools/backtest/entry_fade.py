#!/usr/bin/env python3
"""FADE entry deep dive (governor 2026-11-12). Exits fixed at live v5.2.22 (fade_setup_exits.manage default).
Part 1: entry mechanics (box length, break window, retest wait, tolerance, close-back test, minimum wait, stop placement).
Part 2: entry-time filters (13 facts known before the order), keep/skip by tercile; terciles and the kept set are chosen on
MASSIVE H1 only, then judged on MASSIVE H2 and Robinhood 2026 (never seen). Metric: total R (sum over setups, so a filter must
keep enough trades) and the FADE-alone account.
    python3 -I tools/backtest/entry_fade.py > tools/backtest/results/entry_fade_2026-11-12.txt"""
import datetime as dt, os, sys, itertools
from dataclasses import replace
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, fade_setup_exits as FS
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4


class B2:
    def __init__(self, name, ds, days, ctx, c):
        self.name, self.ds, self.days, self.ctx = name, ds, days, ctx
        def grab(ds_, p, d, b, k, side, entry, ext, c_, info, ctx_):
            s = side
            if c_.stop == 'post': stop = ext
            elif c_.stop[0] == 'atr': stop = entry - s * c_.stop[1] * ctx_['atr'][p][d][k - 1]
            else: stop = entry - s * entry * c_.stop[1] / 100
            r = (entry - stop) * s
            if r <= 0: return None
            if c_.floor_pct: r = max(r, entry * c_.floor_pct / 100)
            info.update(b=b, k=k, side=s, entry=entry, ext=entry - s * r); return info
        old = F._manage; F._manage = grab
        try: E = [t for t in F.trades(ds, days, F.LIVE, c, ctx) if not fri(t['day'])]
        finally: F._manage = old
        for t in E: t.update(AE.feat(ds, ctx, t)); t['atr'] = ctx['atr'][t['proxy']][t['day']]
        self.E = E


def blocks(c):
    out = []
    for name, ds, days, ctx in DATA: out.append(B2(name, ds, days, ctx, c))
    return out


def score(B, keep=None):
    T = [FS.manage(t, {}) for t in B.E if keep is None or keep(t)]
    a = F.account(B.ds, B.days, T); R = np.array([x['R_out'] for x in T]) if T else np.zeros(1)
    return dict(n=len(T), sumR=R.sum(), mR=R.mean(), ret=a['ret'], dd=a['mdd'], taken=len(a['taken']))


ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE)
dm = F.DS(AE.M5, F.LIVE); cm = F.context(dm, F.LIVE); dd = dm.days[21:]
DATA = [('RH 26', ds, [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14'], ctx),
        ('M H1 21-24', dm, [d for d in dd if d < '2024-04-01'], cm), ('M H2 24-26', dm, [d for d in dd if d >= '2024-04-01'], cm)]
cell = lambda s: f"n{s['n']:4d} sumR {s['sumR']:+7.1f} mR {s['mR']:+.3f} acct {s['ret']:+7.1f}% DD{s['dd']:5.1f}"


def part1():
    print('PART 1. Entry mechanics (exits = live). Each row changes one thing from the live entry.')
    V = [('LIVE (box 6, break bars 6-8, wait 12, tol 0.10%, close back inside)', F.P()),
         ('box 3 bars (9:30-9:45)', F.P(box=3, brk_end=6)), ('box 4 bars (20 min)', F.P(box=4, brk_end=7)),
         ('break window to bar 12 (10:30)', F.P(brk_end=13)), ('break window to bar 18 (11:00)', F.P(brk_end=19)),
         ('retest wait 6 bars', F.P(wait=6)), ('retest wait 18 bars', F.P(wait=18)), ('retest wait 24 bars', F.P(wait=24)),
         ('tolerance 0.00%', F.P(tol=0.0)), ('tolerance 0.05%', F.P(tol=0.05)), ('tolerance 0.20%', F.P(tol=0.20)), ('tolerance 0.30%', F.P(tol=0.30)),
         ('no close-back test (enter on any touch)', F.P(inside='any')), ('minimum wait 3 bars', F.P(minwait=3)), ('minimum wait 6 bars', F.P(minwait=6)),
         ('stop 1 ATR from entry', F.P(stop=('atr', 1.0))), ('stop 2 ATR from entry', F.P(stop=('atr', 2.0))),
         ('stop floor 0.4%', F.P(floor_pct=0.4)), ('stop floor 0.6%', F.P(floor_pct=0.6)),
         ('only fade DOWN breaks (buy bull leg)', F.P(side=1)), ('only fade UP breaks (buy bear leg)', F.P(side=-1))]
    base = None
    for name, c in V:
        res = [score(B) for B in blocks(c)]
        if base is None: base = res
        ok = name.startswith('LIVE') is False and all(r['ret'] > b['ret'] for r, b in zip(res, base))
        print(f"  {('PASS ' if ok else '     ') + name:<70} " + ' | '.join(f"{nm[0]} {cell(r)}" for (nm, *_), r in zip(DATA, res)))


def part2():
    BL = blocks(F.P())
    FX = {}
    for b, B in enumerate(BL):
        rows = []
        for t in B.E:
            f = FS.features(B, t); f['bull side (1/0)'] = 1.0 if t['side'] > 0 else 0.0
            f['day of week'] = dt.date.fromisoformat(t['day']).weekday()
            rows.append(f)
        FX[b] = rows
    feats = list(FX[0][0]); base = [score(B) for B in BL]
    print('\nPART 2. Entry-time filters. Keep set chosen on M H1 (design); PASS = account total and sum R both better on RH and M H2.')
    print(f"  {'LIVE (no filter)':<62} " + ' | '.join(f"{nm} {cell(r)}" for (nm, *_), r in zip(DATA, base)))
    out = []
    for f in feats:
        v1 = np.array([x[f] for x in FX[1]])
        cuts = sorted(set(np.percentile(v1, [33.3, 66.7]).round(6)))
        if len(cuts) < 2:
            cuts = sorted(set(v1))[:2]
        lo, hi = cuts[0], cuts[-1]
        band = lambda x, lo=lo, hi=hi: 0 if x < lo else (2 if x >= hi else 1)
        best = None
        for ks in [(0,), (1,), (2,), (0, 1), (1, 2), (0, 2)]:
            idx = [i for i, x in enumerate(FX[1]) if band(x[f]) in ks]
            if len(idx) < 0.4 * len(FX[1]): continue
            T = [FS.manage(BL[1].E[i], {}) for i in idx]; sR = sum(x['R_out'] for x in T)
            if best is None or sR > best[0]: best = (sR, ks)
        if best is None or best[1] == (0, 1, 2): continue
        ks = best[1]; res = []
        for b, B in enumerate(BL):
            keepset = {id(t) for t, x in zip(B.E, FX[b]) if band(x[f]) in ks}
            res.append(score(B, lambda t, k=keepset: id(t) in k))
        ok = all(res[b]['ret'] > base[b]['ret'] and res[b]['sumR'] > base[b]['sumR'] for b in (0, 2))
        name = f"{f}: keep {'/'.join(['low', 'mid', 'high'][i] for i in ks)} (cuts {lo:.3g} / {hi:.3g})"
        out.append((ok, res[2]['ret'] - base[2]['ret'] + res[0]['ret'] - base[0]['ret'], name, res))
    out.sort(key=lambda z: (-z[0], -z[1]))
    for ok, sc, name, res in out:
        print(f"  {('PASS ' if ok else '     ') + name:<62} " + ' | '.join(f"{nm} {cell(r)}" for (nm, *_), r in zip(DATA, res)))


if __name__ == '__main__':
    part1(); part2()
