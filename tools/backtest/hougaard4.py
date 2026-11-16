#!/usr/bin/env python3
"""Control follow-up (2026-11-16): the Hougaard control showed the 3x inverse leg earning from the 9:35 open to 15:55 on most weekdays. Is that
a tradable intraday-drift edge or a feature of 2022-2026 (falling intraday, rising overnight)? Inverse leg every day (stop 1%), by year and by
weekday, then the same for the 3x LONG leg (the symmetric test), alone and as an addition to the live book. Same pre-set rule.
    python3 -I tools/backtest/hougaard4.py > tools/backtest/results/hougaard4_2026-11-16.txt"""
import os, sys, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hougaard as H, hougaard2 as H2
O, B, BA, BM, SB, N2, NS, TB, ds = H.O, H.B, H.BA, H.BM, H.SB, H.N2, H.NS, H.TB, H.ds; TR, TE, dm = H.TR, H.TE, H.dm


def main():
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4); M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
    ovn = np.array([0.5 * onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm]); base = F0 + P0 + I0 + M + D
    yb = SB.yret((1 + BA.acct(dm, TB.byday(base), after_stop=False)[0]) * (1 + ovn) - 1)
    print(__doc__.split('\n')[0]); print(f"   BASELINE book {' '.join(f'{x:+7.1f}' for x in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n")
    for nm, s in (('INVERSE leg (short the proxy)', -1), ('LONG leg', 1)):
        for stop in (1.0,):
            T = H.gen(lambda p, d, b: H2.open_trade(p, d, b, s, stop))
            by = collections.defaultdict(list); wk = collections.defaultdict(list)
            for t in T: by[t['day'][:4]].append(t['pct']); wk[H.wd(t['day'])].append(t['pct'])
            p = [t['pct'] for t in T]; gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
            print(f"{nm}, every proxy every day 9:35 to 15:55, stop {stop}%: n {len(p)} win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.3f}% PF {gw / gl:.2f}")
            print('   by year ' + ' '.join(f"{y} {np.mean(v):+.2f}%" for y, v in sorted(by.items())) + ' | by weekday ' + ' '.join(f"{'MTWTF'[k]} {np.mean(v):+.2f}%" for k, v in sorted(wk.items())))
            alone = SB.yret(BA.acct(dm, TB.byday(T), after_stop=False)[0]); y = SB.yret((1 + BA.acct(dm, TB.byday(base + T), after_stop=False)[0]) * (1 + ovn) - 1)
            q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
            print(f"   {v:<5}alone {' '.join(f'{x:+7.1f}' for x in alone)} | book {' '.join(f'{x:+7.1f}' for x in y)} avg 22-25 {y[:4].mean():+.1f} ({y[:4].mean() - yb[:4].mean():+.1f})")
    # the market itself: QQQ open-to-close and close-to-open, by year
    print('\nTHE TAPE: QQQ open to 15:55, and 15:55 to the next open, mean % a day')
    oc = collections.defaultdict(list); co = collections.defaultdict(list)
    for i, d in enumerate(H.days[:-1]):
        if d < '2022-01-03': continue
        b = ds.bars['QQQ'][d]; nb = ds.bars['QQQ'][H.days[i + 1]]
        if len(b) < 78: continue
        oc[d[:4]].append((b[77][0] / b[1][0] - 1) * 100); co[d[:4]].append((nb[1][0] / b[77][0] - 1) * 100)
    for y in sorted(oc): print(f"   {y}: open to close {np.mean(oc[y]):+.3f}%  close to open {np.mean(co[y]):+.3f}%")


if __name__ == '__main__':
    main()
