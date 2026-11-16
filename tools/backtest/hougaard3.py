#!/usr/bin/env python3
"""Hougaard MTWT controls (2026-11-16). MTWT at 9:35 (Monday's high above Tuesday's and Wednesday's -> Thursday: inverse leg at 9:35, stop 1% of the
proxy, out 15:55) passed the train/test rule. Controls: is it only 'Thursdays fall'? Every Thursday, Thursdays WITHOUT the pattern, the same pattern
read on other weekdays, the pattern with a random Monday, and a year-by-year / proxy-by-proxy split. Plus how many days a year it trades.
    python3 -I tools/backtest/hougaard3.py > tools/backtest/results/hougaard3_2026-11-16.txt"""
import os, sys, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hougaard as H, hougaard2 as H2
O, B, BA, BM, SB, N2, NS, TB, ds = H.O, H.B, H.BA, H.BM, H.SB, H.N2, H.NS, H.TB, H.ds; TR, TE, dm = H.TR, H.TE, H.dm


def pat(p, d, off=0):
    """Monday-high-above-Tue-and-Wed pattern, shifted by `off` weekdays (0 = Thursday signal day)."""
    if H.wd(d) != 3 + off: return None
    k = 1 + off; w = H.prev(d, k); t = H.prev(d, k + 1); m = H.prev(d, k + 2)
    if not m: return None
    return H.dly(p, m)[0] > H.dly(p, t)[0] and H.dly(p, m)[0] > H.dly(p, w)[0] if (H.wd(m) == 0 and H.wd(t) == 1 and H.wd(w) == 2) else None


def stat(T, label):
    p = [t['pct'] for t in T]
    if not p: print(f"   {label:<58} none"); return
    gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0); by = collections.defaultdict(list)
    for t in T: by[t['day'][:4]].append(t['pct'])
    print(f"   {label:<58} n {len(p):4d} win {100 * np.mean([x > 0 for x in p]):3.0f}% avg {np.mean(p):+.2f}% PF {gw / gl if gl else 9:4.2f} | avg leg % by year " + ' '.join(f"{y} {np.mean(v):+.2f}" for y, v in sorted(by.items())))


def main():
    thu = lambda p, d, b, cond=None: (H2.open_trade(p, d, b, -1) if H.wd(d) == 3 and (cond is None or pat(p, d) is cond) else None)
    print(__doc__.split('\n')[0]); print()
    T = H.gen(H2.mtwt_open, stop=1.0, last=H.END); stat(T, 'MTWT pattern Thursdays (the setup)')
    stat(H.gen(thu), 'EVERY Thursday, inverse leg 9:35 to 15:55')
    stat(H.gen(thu, cond=False), 'Thursdays WITHOUT the pattern')
    for off, nm in ((1, 'Friday'), (-1, 'Wednesday')):
        def other(p, d, b, off=off):
            if H.wd(d) != 3 + off: return None
            k = 1 + off; w = H.prev(d, k); t = H.prev(d, k + 1); m = H.prev(d, k + 2)
            if not m or not (H.dly(p, m)[0] > H.dly(p, t)[0] and H.dly(p, m)[0] > H.dly(p, w)[0]): return None
            return H2.open_trade(p, d, b, -1)
        stat(H.gen(other), f'same three-day high pattern, traded on {nm} (placebo)')
    rng = np.random.default_rng(5); days = sorted({t['day'] for t in T}); allthu = [d for d in H.days if H.wd(d) == 3 and d >= '2022-01-03']
    res = []
    for _ in range(500):
        pick = set(rng.choice(allthu, size=len(days), replace=False)); tt = H.gen(lambda p, d, b: H2.open_trade(p, d, b, -1) if d in pick else None); res.append(np.mean([t['pct'] for t in tt]))
    real = np.mean([t['pct'] for t in T]); print(f"   random Thursdays, same count ({len(days)} days): mean avg leg {np.mean(res):+.3f}%; the setup's {real:+.3f}% beats {100 * np.mean(np.array(res) < real):.0f}% of 500 draws")
    by = collections.Counter(t['proxy'] for t in T); print('   signals by proxy: ' + ', '.join(f"{p} {by[p]}" for p in H.PX)); print(f"   signal days: {len(days)} of {len(allthu)} Thursdays ({100 * len(days) / len(allthu):.0f}%), about {len(days) / 4.83:.0f} a year")
    for p in H.PX:
        stat([t for t in T if t['proxy'] == p], f'  proxy {p}')
    ib = {t['day'] for t in B.ibs_trades(sid=4)} | {t['day'] for t in B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5)} | {t['day'] for t in B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)}
    print(f"   of the {len(days)} signal days, {len(set(days) & ib)} also carry an IBS-family signal ({100 * len(set(days) & ib) / len(days):.0f}%)")


if __name__ == '__main__':
    main()
