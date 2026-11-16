#!/usr/bin/env python3
"""Hougaard as a FILTER on the live systems (2026-11-16). The Thursday-Friday-Monday condition (Friday did not beat Thursday's high) is real in
frequency: Monday trades below Friday's low 54% of the time against 35% otherwise. If that is a bearish tilt, the long trades should do worse
on those Mondays and the inverse-leg trades better. Pre-set tests: (A) each system's trades split by the condition on the signal day, by proxy;
(B) the book with the long-side 9:35 trades (IBS-LONG, DIP) skipped on pattern Mondays; (C) the book with the mirror skipped on NON-pattern Mondays.
Same train/test rule against the live book.
    python3 -I tools/backtest/hougaard5.py > tools/backtest/results/hougaard5_2026-11-16.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hougaard as H
O, B, BA, BM, SB, N2, NS, TB, ds = H.O, H.B, H.BA, H.BM, H.SB, H.N2, H.NS, H.TB, H.ds; TR, TE, dm = H.TR, H.TE, H.dm


def tfm_day(p, d):
    f = H.prev(d); th = H.prev(d, 2) if f else None
    if not th or H.wd(f) != 4 or H.wd(th) != 3 or not H.cons(th, f) or not H.cons(f, d): return None
    return H.dly(p, f)[0] <= H.dly(p, th)[0]            # True = pattern, False = Friday made a higher high, None = not a Monday after Thu-Fri


def main():
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4); M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
    ovn = np.array([0.5 * onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm])
    def book(parts): return SB.yret((1 + BA.acct(dm, TB.byday([t for p in parts for t in p]), after_stop=False)[0]) * (1 + ovn) - 1)
    yb = book([F0, P0, I0, M, D]); print(__doc__.split('\n')[0]); print(f"   BASELINE book {' '.join(f'{x:+7.1f}' for x in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n")
    print('A. each system on Mondays after Thursday-Friday: pattern (Friday failed to beat Thursday) against no pattern. avg leg %, trades')
    for nm, T in (('IBS-LONG', I0), ('DIP', D), ('MIRROR', M), ('FADE', F0), ('PULLBACK', P0)):
        a = [t['pct'] for t in T if t.get('proxy') and tfm_day(t['proxy'], t['day']) is True]; b = [t['pct'] for t in T if t.get('proxy') and tfm_day(t['proxy'], t['day']) is False]
        print(f"   {nm:<9} pattern {np.mean(a) if a else float('nan'):+.2f}% (n {len(a)}) | no pattern {np.mean(b) if b else float('nan'):+.2f}% (n {len(b)})" if a or b else f"   {nm:<9} no proxy tag on its trades")
    def row(tag, y):
        q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
        print(f"   {v:<5}{tag:<62} {' '.join(f'{x:+7.1f}' for x in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f})")
    print('\nB and C. the book with a Hougaard filter')
    drop = lambda T, f: [t for t in T if not f(t)]
    pat = lambda t: tfm_day(t['proxy'], t['day']) is True; nopat = lambda t: tfm_day(t['proxy'], t['day']) is False
    row('skip IBS-LONG and DIP on pattern Mondays', book([F0, P0, drop(I0, pat), M, drop(D, pat)]))
    row('skip IBS-LONG and DIP on EVERY Monday (day-of-week control)', book([F0, P0, drop(I0, lambda t: H.wd(t['day']) == 0), M, drop(D, lambda t: H.wd(t['day']) == 0)]))
    row('skip the MIRROR on non-pattern Mondays', book([F0, P0, I0, drop(M, nopat), D]))
    row('skip IBS-LONG, DIP on pattern Mondays and the MIRROR on non-pattern Mondays', book([F0, P0, drop(I0, pat), drop(M, nopat), drop(D, pat)]))
    print(f"   pattern Mondays in the sample: {len({t['day'] for t in I0 + D + M if t.get('proxy') and tfm_day(t['proxy'], t['day']) is True})} days carry an IBS-family signal")


if __name__ == '__main__':
    main()
