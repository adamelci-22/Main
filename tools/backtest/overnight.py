#!/usr/bin/env python3
"""Overnight study (governor 2026-11-13: "can we add another subsystem ... can we change anything fundamentally"). Research only.
The 9:35 family (IBS-TREND long, mirror, dip) uses a signal known at the prior close and enters the next morning. The classic form of
that trade is entered AT the close and held overnight. Rule A1.8 forbids overnight holds, so this is a test, not a change.
OVERNIGHT leg: at 15:55 compute the same three signals from the day so far (price at 15:55 as the close), buy the leg at 15:55,
sell at the next session's 9:35 open. No stop is possible overnight. One position a night (highest relative volume that day).
Baseline = the live joint book v5.2.51. Train 2022/2024/2026, test 2023/2025, same pre-set rule as before.
    python3 -I tools/backtest/overnight.py > tools/backtest/results/overnight_2026-11-13.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boost as B, boost_mirror as BM, book_audit as BA, fade_diag as F
SB, N2, NS, TB = B.SB, B.N2, B.NS, B.TB; TR, TE = B.TR, B.TE; YEARS = SB.YEARS; dm = B.dm; ds = B.ds


def rsi2(c):
    ag = al = 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 2: ag += g / 2; al += lo / 2
        else: ag = (ag + g) / 2; al = (al + lo) / 2
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def signals():
    """{next day: [dict(kind, proxy, pct, rv)]}: overnight trades entered at 15:55 on day d, sold at 9:35 on the next day."""
    out = {}
    for i, d in enumerate(dm[:-1]):
        nd = dm[i + 1]
        for p in F.LIVE:
            b = ds.bars[p].get(d); nb = ds.bars[p].get(nd); h = N2.hist(p, d, 49)
            if not b or not nb or len(b) < 78 or h is None: continue
            c = b[77][0]; H = max(x[1] for x in b[:77]); L = min(x[2] for x in b[:77])
            if H <= L: continue
            ibs = (c - L) / (H - L); c20 = h[2][-19:] + [c]; c50 = h[2] + [c]; up20 = c > st.mean(c20)
            kind = 'long' if (up20 and ibs < 0.10) else 'mirror' if ((not up20) and ibs > 0.95) else None
            if kind != 'long' and c > st.mean(c50) and rsi2(h[2][-11:] + [c]) < 10: kind = 'dip'
            if not kind: continue
            side = -1 if kind == 'mirror' else 1; pct = side * 3 * (nb[1][0] / c - 1) * 100 - NS.COST
            out.setdefault(nd, []).append(dict(kind=kind, proxy=p, pct=pct, rv=ds.rvol(p, d, 77)))
    return out


def main():
    S = signals(); allt = [t for v in S.values() for t in v]
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
    M = B.BC.new(B.ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(B.ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    base = BA.acct(dm, TB.byday(F0 + P0 + I0 + M + D), after_stop=False)[0]; yb = SB.yret(base)
    def ov(kinds=None, top=True):
        r = np.zeros(len(dm))
        for n, d in enumerate(dm):
            c = [t for t in S.get(d, []) if kinds is None or t['kind'] in kinds]
            if c: r[n] = (max(c, key=lambda t: t['rv'])['pct'] if top else st.mean(t['pct'] for t in c)) / 100
        return r
    def line(tag, r, cmp=None):
        y = SB.yret(r); dd = SB.ydd(r); v = ''
        if cmp is not None:
            q = np.prod(1 + y[TR] / 100) > np.prod(1 + cmp[TR] / 100) and (y[TR] > cmp[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > cmp[TE]).all()) else 'qual' if q else ''
        return f"   {v:<5}{tag:<52} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} worst {y[:4].min():+6.1f} DD {dd.max():4.1f}"
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th). Full cash on a 3x leg, cost 0.06%.\n')
    print(line('BASELINE v5.2.51 joint book (no overnight)', base))
    print('\nOVERNIGHT LEG ALONE (15:55 to the next 9:35)')
    for tag, k in (('all three signals, one a night', None), ('long signals only', ('long',)), ('dip signals only', ('dip',)), ('mirror signals only', ('mirror',))):
        x = [t for t in allt if k is None or t['kind'] in k]; p = [t['pct'] for t in x]
        print(line(tag, ov(k)) + f" | {len(x)} signals, win {100 * np.mean([q > 0 for q in p]):.0f}%, avg leg {np.mean(p):+.2f}%, worst {min(p):+.1f}%")
    print(line('every signal, equal weight (not one a night)', ov(None, top=False)))
    print('\nJOINT BOOK + OVERNIGHT LEG (compounded with the next day)')
    for tag, k in (('+ overnight, all three signals', None), ('+ overnight, long + dip only', ('long', 'dip')), ('+ overnight, long only', ('long',)), ('+ overnight, mirror only', ('mirror',))):
        r = (1 + base) * (1 + ov(k)) - 1; print(line(tag, r, yb))
    p = sorted(t['pct'] for t in allt); nights = len(S)
    print(f"\nTAIL (no stop is possible overnight): {len(p)} signals on {nights} nights ({100 * nights / len(dm):.0f}% of nights). Worst five legs: {' '.join(f'{x:+.1f}%' for x in p[:5])}. Legs worse than -5%: {sum(x < -5 for x in p)}; worse than -3%: {sum(x < -3 for x in p)}; better than +5%: {sum(x > 5 for x in p)}.")


if __name__ == '__main__':
    main()
