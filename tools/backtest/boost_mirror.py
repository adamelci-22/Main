#!/usr/bin/env python3
"""Boost study, part 2 (governor 2026-11-13): the IBS-TREND MIRROR. IBS-TREND buys the 3x long leg after a weak close in an uptrend.
The mirror buys the 3x INVERSE leg after a strong close in a downtrend: proxy below its n-session average close and prior-day
IBS above hi. Same clock: in at 9:35, stop 1% of the proxy, out 15:55. One IBS trade a day (long or mirror, higher first-bar RVOL).
Rule fixed before the grid was read: a setting QUALIFIES if the book (FADE + PULLBACK + IBS-TREND + mirror) beats the live book
(v5.2.48) on TRAIN compounded and in at least 2 of the 3 train years. It PASSES if it also beats the live book in BOTH test years.
    python3 -I tools/backtest/boost_mirror.py > tools/backtest/results/boost_mirror_2026-11-13.txt"""
import itertools, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boost as B
SB, N2, NS, BC = B.SB, B.N2, B.NS, B.BC; TR, TE = B.TR, B.TE


def mirror_fn(ds_, ctx_, p, d, b, hi=0.9, n=20, stop=1.0):
    v = N2.ibsv(p, d); u = N2.up(p, d, n)
    if v is None or u is None or u or v <= hi: return None
    e = b[1][0]; x, g, r = NS.mg(b, 1, -1, e, e * (1 + stop / 100), NS.END); return NS.fin(d, p, 1, x, e, g, r)


def main():
    F0, P0, I0 = B.fade_trades(), B.pb_trades(), B.ibs_trades(); base = B.book(F0, P0, I0); yb = SB.yret(base)
    print(__doc__.split('\n')[0]); print(B.HEAD); print(B.line('LIVE v5.2.48: FADE + PULLBACK + IBS-TREND', base)); print(B.line('IBS-TREND alone', B.book(I0)))
    rows = []
    for hi, n in itertools.product((0.85, 0.90, 0.95), (10, 20, 30, 50)):
        M = BC.new(B.ds, B.ctx, B.dm, mirror_fn, dict(hi=hi, n=n), 4); rb = B.book(F0, P0, I0, M); y = SB.yret(rb)
        q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; ps = q and bool((y[TE] > yb[TE]).all())
        rows.append((hi, n, M, rb, y, q, ps))
    print('\nMIRROR ALONE (inverse leg only)'); print(B.HEAD)
    for hi, n, M, rb, y, q, ps in rows: print(B.line(f'mirror IBS > {hi:.2f}, below the {n}-day average, {len(M)} signals', B.book(M)))
    print('\nBOOK: FADE + PULLBACK + IBS-TREND + MIRROR   (Q = qualifies on TRAIN, P = also passes TEST)'); print(B.HEAD)
    for hi, n, M, rb, y, q, ps in rows: print(B.line(f'+ mirror IBS > {hi:.2f}, {n}-day', rb, 'P' if ps else 'Q' if q else ''))
    nq = sum(r[5] for r in rows); npass = sum(r[6] for r in rows)
    print(f"\n   {nq} of {len(rows)} settings qualify on TRAIN; {npass} of those pass TEST. Beat the live book in both test years regardless of train: {sum(bool((r[4][TE] > yb[TE]).all()) for r in rows)} of {len(rows)}.")
    qual = [r for r in rows if r[5]]
    if qual:
        best = max(qual, key=lambda r: np.prod(1 + r[4][TR] / 100)); print(f"   TRAIN pick: mirror IBS > {best[0]:.2f}, {best[1]}-day. TEST: 2023 {best[4][1]:+.1f}% (live {yb[1]:+.1f}%), 2025 {best[4][3]:+.1f}% (live {yb[3]:+.1f}%) -> {'PASS' if best[6] else 'FAIL'}")
        M = best[2]; days = sorted({t['day'] for t in M}); print(f"   mirror signal days {len(days)} of {len(B.dm)} ({100 * len(days) / len(B.dm):.0f}%); with IBS-TREND long days the IBS family trades on {100 * len(set(days) | {t['day'] for t in I0}) / len(B.dm):.0f}% of days")


if __name__ == '__main__':
    main()
