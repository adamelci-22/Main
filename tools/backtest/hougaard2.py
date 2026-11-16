#!/usr/bin/env python3
"""Hougaard follow-up (2026-11-16): the day patterns are real in frequency (TFM: Monday trades below Friday's low 54% of the time after a Friday
that failed to beat Thursday's high, 35% after one that did). First test entered on a close below the level and did not pay. This tests the
signal as a 9:35 open trade, the clock of the live IBS systems: pattern day -> inverse leg at 9:35, stop x% of the proxy, out 15:55 or 13:30.
Same pre-set rule (train 2022/2024/2026, test 2023/2025), judged alone and added to the live book. Also the Monday-based open trade.
    python3 -I tools/backtest/hougaard2.py > tools/backtest/results/hougaard2_2026-11-16.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hougaard as H
O, B, BA, BM, SB, N2, NS, TB, ds = H.O, H.B, H.BA, H.BM, H.SB, H.N2, H.NS, H.TB, H.ds; TR, TE, dm = H.TR, H.TE, H.dm; mg, fin = H.mg, H.fin


def open_trade(p, d, b, s, stop=1.0, last=H.END):
    e = b[1][0]; x, g, r = mg(b, 1, s, e, e * (1 - s * stop / 100), last); t = fin(d, p, 1, x, e, g, r); t['rv'] = ds.rvol(p, d, 1); t['sys'] = 7; t['proxy'] = p; return t


def tfm_open(p, d, b, stop=1.0, last=H.END, filt=None):
    f = H.prev(d); th = H.prev(d, 2) if f else None
    if not th or H.wd(f) != 4 or H.wd(th) != 3 or not H.cons(th, f) or not H.cons(f, d): return None
    if H.dly(p, f)[0] > H.dly(p, th)[0]: return None
    if filt == 'below' and b[0][0] >= H.dly(p, f)[1]: return None            # only when the open is already under Friday's low
    return open_trade(p, d, b, -1, stop, last)


def mtwt_open(p, d, b, stop=1.0, last=H.END):
    if H.wd(d) != 3: return None
    w = H.prev(d); t = H.prev(d, 2); m = H.prev(d, 3)
    if not m or H.wd(w) != 2 or H.wd(t) != 1 or H.wd(m) != 0 or not (H.cons(m, t) and H.cons(t, w) and H.cons(w, d)): return None
    if not (H.dly(p, m)[0] > H.dly(p, t)[0] and H.dly(p, m)[0] > H.dly(p, w)[0]): return None
    return open_trade(p, d, b, -1, stop, last)


def main():
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4); M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
    ovn = np.array([0.5 * onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm]); base = F0 + P0 + I0 + M + D
    yb = SB.yret((1 + BA.acct(dm, TB.byday(base), after_stop=False)[0]) * (1 + ovn) - 1)
    print(__doc__.split('\n')[0]); print(f"   BASELINE book {' '.join(f'{x:+7.1f}' for x in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n")
    npass = 0
    for name, fn in (('TFM at 9:35', tfm_open), ('TFM at 9:35, open already under Friday low', lambda p, d, b, **k: tfm_open(p, d, b, filt='below', **k)), ('MTWT at 9:35', mtwt_open)):
        print(name)
        for stop in (0.5, 1.0, 1.5):
            for last in (48, 77):
                T = H.gen(fn, stop=stop, last=last)
                if not T: continue
                alone = SB.yret(BA.acct(dm, TB.byday(T), after_stop=False)[0]); y = SB.yret((1 + BA.acct(dm, TB.byday(base + T), after_stop=False)[0]) * (1 + ovn) - 1)
                p = [t['pct'] for t in T]; gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
                q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
                npass += v == 'PASS'
                print(f"   {v:<5}stop {stop}% out {'13:30' if last == 48 else '15:55'}  n {len(T):4d} win {100 * np.mean([x > 0 for x in p]):3.0f}% avg {np.mean(p):+.2f}% PF {gw / gl if gl else 9:4.2f} | alone {' '.join(f'{x:+6.1f}' for x in alone)} | book avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) test {y[TE[0]] - yb[TE[0]]:+5.1f} {y[TE[1]] - yb[TE[1]]:+5.1f}")
        print()
    print(f"   PASS count: {npass}")


if __name__ == '__main__':
    main()
