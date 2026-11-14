#!/usr/bin/env python3
"""Overnight leg, sizing and risk (governor 2026-11-13: "what is the best set up including an analysis on the overnight"). Research only.
Baseline = the live joint book v5.2.51. Overnight leg = tools/backtest/overnight.py (buy at 15:55 on the signal, sell at the next 9:35).
For each choice of signals and size: years, average 2022-25, worst year, deepest drawdown over the whole period, the worst single
night as a share of the account, how often the 15% drawdown stop (A1.13) would have fired, and the same pre-set train/test rule.
Also: FADE at full, half and zero size inside each book; cost doubled on the overnight leg.
    python3 -I tools/backtest/overnight_size.py > tools/backtest/results/overnight_size_2026-11-13.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import overnight as O
B, BA, BM, SB, N2, NS, TB = O.B, O.BA, O.BM, O.SB, O.N2, O.NS, O.TB; TR, TE = O.TR, O.TE; dm = O.dm


def dd_stats(r):
    eq = np.cumprod(1 + r); pk = np.maximum.accumulate(eq); dd = 1 - eq / pk
    halts = 0; high = 1.0; e = 1.0                      # A1.13: halt at 15% under the high; count fires, restart the high at the halt level
    for x in r:
        e *= 1 + x; high = max(high, e)
        if e <= 0.85 * high: halts += 1; high = e
    return dd.max() * 100, halts


def main():
    S = O.signals()
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
    M = B.BC.new(B.ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(B.ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    def book(fade=1.0):
        Fx = [dict(t, pct=t['pct'] * fade) for t in F0] if fade else []
        return BA.acct(dm, TB.byday(Fx + P0 + I0 + M + D), after_stop=False)[0]
    def ov(kinds, extra=0.0):
        r = np.zeros(len(dm))
        for n, d in enumerate(dm):
            c = [t for t in S.get(d, []) if t['kind'] in kinds]
            if c: r[n] = (max(c, key=lambda t: t['rv'])['pct'] - extra) / 100
        return r
    base = book(); yb = SB.yret(base)
    def line(tag, r, cmp=yb, night=None):
        y = SB.yret(r); mdd, halts = dd_stats(r); v = ''
        if cmp is not None:
            q = np.prod(1 + y[TR] / 100) > np.prod(1 + cmp[TR] / 100) and (y[TR] > cmp[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > cmp[TE]).all()) else 'qual' if q else ''
        nt = f" | worst night {night.min() * 100:+5.1f}%, nights under -3%: {int((night < -0.03).sum()):2d}" if night is not None else ''
        return f"   {v:<5}{tag:<46} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} worst yr {y[:4].min():+6.1f} | max DD {mdd:4.1f} | 15% stop fires {halts}x{nt}"
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); verdict against the v5.2.51 book\n')
    print(line('BASELINE v5.2.51 (no overnight, FADE full)', base, None))
    for tag, kinds in (('LONG signal overnight', ('long',)), ('LONG + DIP signals overnight', ('long', 'dip'))):
        print(f"\n{tag}")
        o = ov(kinds); n = int((o != 0).sum()); w = 100 * np.mean(o[o != 0] > 0)
        print(f"   {n} nights ({100 * n / len(dm):.0f}% of nights), {w:.0f}% wins, average leg {o[o != 0].mean() * 100:+.2f}%, worst leg {o.min() * 100:+.1f}%, best {o.max() * 100:+.1f}%, legs under -5%: {int((o < -0.05).sum())}, under -3%: {int((o < -0.03).sum())}")
        for f in (1.0, 0.5, 0.33, 0.25):
            print(line(f'size {int(f * 100)}% of cash', (1 + base) * (1 + f * o) - 1, night=f * o))
        o2 = ov(kinds, extra=0.06); print(line('size 50%, cost doubled (0.12%)', (1 + base) * (1 + 0.5 * o2) - 1, night=0.5 * o2))
        oy = SB.yret(o); print(f"   leg alone at full size by year: {' '.join(f'{a:+6.1f}' for a in oy)}")
    print('\nFADE SIZE inside the book (no overnight / long overnight at 50%)')
    o = ov(('long',))
    for fd in (1.0, 0.5, 0.0):
        b = book(fd); print(line(f'FADE {int(fd * 100)}%, no overnight', b)); print(line(f'FADE {int(fd * 100)}%, long overnight at 50%', (1 + b) * (1 + 0.5 * o) - 1, night=0.5 * o))
    print('\nMONTHS (v5.2.51 baseline vs + long overnight at 50%)')
    for tag, r in (('baseline', base), ('+ long overnight 50%', (1 + base) * (1 + 0.5 * o) - 1)):
        ms = SB.mstats(SB.mret(r)); print(f"   {tag:<24} winning months by year: {' '.join(f'{float(ms[y][0]):3.0f}%' for y in SB.YEARS)} | worst month by year: {' '.join(f'{float(ms[y][3]):+5.1f}' for y in SB.YEARS)}")


if __name__ == '__main__':
    main()
