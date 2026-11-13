#!/usr/bin/env python3
"""Boost study, part 3 (governor 2026-11-13: "the entire system, all 3, IBS FADE and PULLBACK, to a joint min of 30% per year
without 2026"). The joint book is scored by its WORST year. Train = 2022, 2024, 2026 (choices are made on the worst TRAIN year, then
the train total); test = 2023, 2025. Pieces combined (every piece is one already studied, no new parameter search inside a piece):
  FADE       live | off
  PULLBACK   live | only when the underlying closed below its 10 / 20 / 50-session average
  IBS-TREND  long side as pushed (always on)
  MIRROR     off | 0.95 with the 20-session average (pushed) | 0.95 with 50 | pushed + only while QQQ is below its 50 or 100-session average
  DIP        off | on  (RSI(2) < 10 above the 50-session average, 9:35 to 15:55; yesterday's study)
  RELVAL     off | on  (afternoon relative value, parallel)
    python3 -I tools/backtest/boost_floor.py > tools/backtest/results/boost_floor_2026-11-13.txt"""
import itertools, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boost as B, boost_mirror as BM
SB, N2, NS, BC = B.SB, B.N2, B.NS, B.BC; TR, TE, PRE = B.TR, B.TE, B.PRE


def gated(M, g): return [t for t in M if N2.up('QQQ', t['day'], g) is False]


def main():
    F = {'FADE live': B.fade_trades(), 'FADE off': []}
    P = {'PB live': B.pb_trades(), 'PB und<10d': B.pb_trades('down', 10), 'PB und<20d': B.pb_trades('down', 20), 'PB und<50d': B.pb_trades('down', 50)}
    I0 = B.ibs_trades(); m20 = BC.new(B.ds, B.ctx, B.dm, BM.mirror_fn, dict(hi=0.95, n=20), 4); m50 = BC.new(B.ds, B.ctx, B.dm, BM.mirror_fn, dict(hi=0.95, n=50), 4)
    M = {'mirror off': [], 'mirror 20d (live)': m20, 'mirror 50d': m50, 'mirror 20d, QQQ<50d': gated(m20, 50), 'mirror 20d, QQQ<100d': gated(m20, 100)}
    D = {'DIP off': [], 'DIP on': BC.new(B.ds, B.ctx, B.dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)}
    R = {'RELVAL off': [], 'RELVAL on': BC.new(B.ds, B.ctx, B.dm, NS.relval, dict(a=48, z=72, xm=1.0, ksd=2.5), 3)}
    rows = []
    for f, p, m, d, r in itertools.product(F, P, M, D, R):
        y = SB.yret(B.book(F[f], P[p], I0, M[m], D[d], R[r])); rows.append((f"{f} | {p} | {m} | {d} | {r}", y))
    live = next(r for r in rows if r[0] == 'FADE live | PB live | mirror 20d (live) | DIP off | RELVAL off'); v48 = next(r for r in rows if r[0] == 'FADE live | PB live | mirror off | DIP off | RELVAL off')
    def show(tag, r):
        n, y = r; print(f"   {tag:<3}{n:<72} {' '.join(f'{v:+7.1f}' for v in y)} | worst 22-25 {y[PRE].min():+6.1f} avg {y[PRE].mean():+6.1f} | train worst {y[TR].min():+6.1f} | TEST {(np.prod(1 + y[TE] / 100) - 1) * 100:+7.1f}")
    print(__doc__.split('\n')[0]); print(f"   {len(rows)} joint books. Years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th).\n")
    show('', ('v5.2.48 (IBS long, no mirror): ' + v48[0], v48[1])); show('', ('v5.2.49 LIVE: ' + live[0], live[1]))
    order = sorted(rows, key=lambda r: (-round(r[1][TR].min(), 1), -np.prod(1 + r[1][TR] / 100)))
    print('\nTOP 12 by the worst TRAIN year (then train total). T = the train pick')
    for i, r in enumerate(order[:12]): show('T' if i == 0 else '', r)
    Y = np.array([r[1] for r in rows])
    print(f"\n   books with every year 2022-2025 at +30% or more: {int((Y[:, PRE] >= 30).all(1).sum())} of {len(rows)}; at +20% or more: {int((Y[:, PRE] >= 20).all(1).sum())}; at +10% or more: {int((Y[:, PRE] >= 10).all(1).sum())}; all five years positive: {int((Y > 0).all(1).sum())}")
    print(f"   best possible worst year 2022-2025 over all {len(rows)} books (hindsight, not a pick): {Y[:, PRE].min(1).max():+.1f}%")
    hind = rows[int(np.argmax(Y[:, PRE].min(1)))]; show('', ('hindsight best floor: ' + hind[0], hind[1]))
    print(f"   2024 across all books: best {Y[:, 2].max():+.1f}%, median {np.median(Y[:, 2]):+.1f}%.  2023: best {Y[:, 1].max():+.1f}%, median {np.median(Y[:, 1]):+.1f}%.")
    print('\nONE PIECE AT A TIME from v5.2.49 LIVE (change in each year, points)')
    base = live[1]; parts = live[0].split(' | ')
    for i, opts in enumerate((F, P, M, D, R)):
        for o in opts:
            if o == parts[i]: continue
            q = parts[:i] + [o] + parts[i + 1:]; y = next(r for r in rows if r[0] == ' | '.join(q))[1]
            print(f"      {o:<22} {' '.join(f'{v:+7.1f}' for v in y - base)} | worst 22-25 {y[PRE].min():+6.1f} avg {y[PRE].mean():+6.1f} | train years better {int((y[TR] > base[TR]).sum())}/3, test years better {int((y[TE] > base[TE]).sum())}/2")


if __name__ == '__main__':
    main()
