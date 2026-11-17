#!/usr/bin/env python3
"""PULLBACK three-tranche exit (governor 2026-11-17: "what if 1/3 sold at the morning high and 1/3 sold at a certain point over the high and 1/3 ran"). Research only.
Live PULLBACK: 1/3 at the morning high (limit), stop to breakeven, 2/3 runner out on the first 5-minute close under the 20-EMA, all out at 13:30.
Test: 1/3 at the morning high, 1/3 at a SECOND level above it, 1/3 runner (20-EMA close). Second level: the high + x R (x = 0.5 1 1.5 2 3), or entry + y R (y = 3 4 5 6),
or the high + z % of the entry (1 2 3 %). After the second sale the stop stays at breakeven, or moves up to the morning high ('lock').
Judged inside the live joint book v5.2.59 (FADE, PULLBACK, IBS-LONG, MIRROR, DIP, overnight leg 50%), one change at a time. Train 2022/2024/2026, test 2023/2025.
Pre-set rule: QUALIFIES = beats the live book on train compounded and in 2 of 3 train years; PASSES = also beats it in both test years.
    python3 -I tools/backtest/pb_three_tranche.py > tools/backtest/results/pb_three_tranche_2026-11-17.txt"""
import itertools, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import exit_all as X
O, B, BA, BM, SB, N2, NS, TB = X.O, X.B, X.BA, X.BM, X.SB, X.N2, X.NS, X.TB; TR, TE = X.TR, X.TE; dm = X.dm; ds = X.ds; PS = B.PS; EP = B.EP
F0 = B.fade_trades(); I0 = B.ibs_trades(sid=4)
M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
ovn = np.array([onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm])
ENT = TB.pb_entries(B.ds, B.dm, PS.LEGS_M, dict(EP.LIVE))


def manage3(t, c):
    """c: f1 (share at the morning high), f2 (share at the second level), t2 = ('hr', x) | ('er', y) | ('hp', z), s2 ('be' | 'hi'), run = ('ema', 20)."""
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']; T = t['T']
    T2 = None
    if c.get('t2'):
        kind, v = c['t2']; T2 = T + v * r if kind == 'hr' else e + v * r if kind == 'er' else T + e * v / 100
    f1, f2 = c.get('f1', 1 / 3), c.get('f2', 1 / 3); rem, g, hit, hit2, pend, out = 1.0, 0.0, False, False, None, False; j = k
    for j in range(k, PS.LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if pend is not None: stop = max(stop, pend); pend = None
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if T is not None and not hit and h >= T:
            px = max(T, o); q = min(f1, rem); g += q * (px - e); rem -= q; hit = True
            if rem <= 1e-9: break
            stop = max(stop, e)
        if hit and T2 is not None and not hit2 and h >= T2:
            px = max(T2, o); q = min(f2, rem); g += q * (px - e); rem -= q; hit2 = True
            if rem <= 1e-9: break
            if c.get('s2') == 'hi': pend = max(pend or -1e9, T)
        if hit and j < PS.LAST and cl < t['e20'][j]: out = True
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, rv=t['rv'], sys=1, hit2=hit2)


def pbt(c): return [dict(manage3(t, c), sys=1) for t in ENT]


def book(P): return SB.yret((1 + BA.acct(dm, TB.byday(F0 + P + I0 + M + D), after_stop=False)[0]) * (1 + 0.5 * ovn) - 1)


base = pbt(dict(f1=1 / 3, f2=0.0)); yb = book(base)


def verdict(y):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''


def stat(T):
    p = [t['pct'] for t in T]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0); return f"n {len(p)} win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.2f}% PF {g / l if l else 99:.2f}"


def row(tag, T, y=None, mark=True):
    y = book(T) if y is None else y
    print(f"   {verdict(y) if mark else '':<5}{tag:<52} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) | {stat(T)}")
    return y


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); parentheses = points vs the live book; stats = the PULLBACK trades alone\n')
    row('LIVE: 1/3 at the high, 2/3 runner EMA20 close', base, yb, False)
    print('\nTHREE TRANCHES: 1/3 high, 1/3 second level, 1/3 runner')
    grid = [(f'second level = high + {x:g}R', dict(t2=('hr', x))) for x in (0.5, 1.0, 1.5, 2.0, 3.0)] + [(f'second level = entry + {y:g}R', dict(t2=('er', y))) for y in (3, 4, 5, 6)] + \
           [(f'second level = high + {z:g}% of entry', dict(t2=('hp', z))) for z in (1, 2, 3)]
    res = []
    for nm, c in grid:
        for s2 in ('be', 'hi'):
            cc = dict(c, s2=s2); T = pbt(cc); y = row(f"{nm}, stop after sale 2: {'breakeven' if s2 == 'be' else 'the high'}", T); res.append((nm, s2, y, T))
    print(f"\n   hit rate of the second level among trades that reached the high: {100 * np.mean([t['hit2'] for t in pbt(dict(t2=('hr', 1.0), s2='be')) if t['pct'] is not None]):.0f}% of all trades (sample: high + 1R)")
    np_, nq = sum(verdict(r[2]) == 'PASS' for r in res), sum(verdict(r[2]) == 'qual' for r in res)
    print(f"\n   {len(res)} variants: {np_} PASS, {nq} qualify on train only. Best by average 2022-25: {max(res, key=lambda r: r[2][:4].mean())[0]} / {max(res, key=lambda r: r[2][:4].mean())[1]} {max(r[2][:4].mean() for r in res):+.1f} vs live {yb[:4].mean():+.1f}")
    print('\nHALF AND HALF (reference): 1/2 at the high, 1/2 runner'); row('1/2 at the high, 1/2 runner EMA20', pbt(dict(f1=0.5, f2=0.0)))
    print('\nTWO TRANCHES + RUNNER with the first sale smaller: 1/4 at the high, 1/4 second level (high + 1R), 1/2 runner'); row('1/4 + 1/4 + 1/2', pbt(dict(f1=0.25, f2=0.25, t2=('hr', 1.0), s2='be')))


if __name__ == '__main__':
    main()
