#!/usr/bin/env python3
"""Giveback gaps in the other systems (governor 2026-11-17: "What about for the other system are there any gaps like this we can make before I lose out on a 60$ gain").
Research only. For FADE and the 9:35 family (IBS-LONG, MIRROR, DIP): how often a trade was well up and ended near zero, and whether a giveback rule (once the best close
is m R up, sell the rest on a close that gives back f of that gain) beats the live exit. Book = live v5.2.61 (PULLBACK with its 3R giveback). Train 2022/2024/2026,
test 2023/2025; QUALIFIES / PASSES as in the other studies. OVERNIGHT has no intraday hold (bought 15:55, sold 9:35), so it has no giveback to cut.
    python3 -I tools/backtest/giveback_all.py > tools/backtest/results/giveback_all_2026-11-17.txt"""
import os, sys, io, contextlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()): import pb_signals as SG
P3 = SG.P3; X = P3.X; B, BA, SB, TB, NS, F = P3.B, P3.BA, P3.SB, P3.TB, P3.NS, P3.B.F if hasattr(P3.B, 'F') else None
import fade_diag as FD
dm, ds, ovn = P3.dm, P3.ds, P3.ovn; TR, TE = P3.TR, P3.TE; PB = SG.base; F0, I0, M, D = P3.F0, P3.I0, P3.M, P3.D
FE = [t for t in TB.fade_entries(B.ds, B.ctx, dm, 0.5) if not t['fri'] and not t['run']]
LAST = B.FS.LAST


def bk(F=F0, I=I0, Mi=M, Di=D): return SB.yret((1 + BA.acct(dm, TB.byday(F + PB + I + Mi + Di), after_stop=False)[0]) * (1 + 0.5 * ovn) - 1)


yb = bk()


def verdict(y):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''


def fade(t, give=None):
    """Live FADE manage (fade_setup_exits.manage, default keys) plus an optional giveback (f, m). Returns the trade and its best close in R."""
    b, s, k, e = t['b'], t['side'], t['k'], t['entry']; stop = t['ext']; r = t['r']; T = e + s * 2.0 * r
    rem, g, hit, hic, bestc, pend, out = 1.0, 0.0, False, e, 0.0, None, False; at = t['atr']; j = k; mfe = 0.0
    for j in range(k, LAST + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: g += rem * (o - e) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; g += rem * (px - e) * s; rem = 0; break
        mfe = max(mfe, (fav - e) * s / r)
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; q = min(1 / 3, rem); g += q * (px - e) * s; rem -= q; hit = True
            if (e - stop) * s > 0: stop = e
            if rem <= 1e-9: break
        cr = (cl - e) * s / r; bestc = max(bestc, cr); hic = max(hic, cl) if s > 0 else min(hic, cl)
        if bestc >= 0.5:
            ns = e + s * 0.15 * r
            if (ns - stop) * s > 0: pend = ns
        if j < LAST and hit:
            ns = hic - s * 2.0 * at[j]
            if (ns - stop) * s > 0: stop = ns
        if j - k + 1 == 3 and cr <= -0.5 and j < LAST: out = True
        if give and j < LAST and bestc >= give[1] and cr < (1 - give[0]) * bestc: out = True
    if rem > 0: g += rem * (b[j][3] - e) * s
    lev = FD.LEV[t['proxy']][0] if s > 0 else FD.LEV[t['proxy']][1]
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=lev * g / e * 100 - FD.LEGCOST, leg_risk=lev * r / e * 100, rv=t['rv'], sys=0, mfe=mfe, R=g / r)


def fam(base, side, sid, give=None):
    """9:35 family: entry at the 9:35 open, stop 1% of the proxy, out 15:55 (exit_all.mgx), plus an optional giveback (f, m) in R = 1% of the proxy."""
    out = []
    for t in base:
        b = ds.bars[t['proxy']][t['day']]; e = b[1][0]; sp = e * (1 - side * 0.01); r = e * 0.01; g = None; bestc = 0.0; mfe = 0.0; xj = NS.END - 1; leave = False
        for j in range(1, NS.END):
            o, h, l, c, v = b[j]; fav, adv = (h, l) if side > 0 else (l, h)
            if leave: g = (o - e) * side; xj = j; break
            if (adv - sp) * side <= 0: g = ((sp if (o - sp) * side >= 0 else o) - e) * side; xj = j; break
            mfe = max(mfe, (fav - e) * side / r); cr = (c - e) * side / r; bestc = max(bestc, cr)
            if give and bestc >= give[1] and cr < (1 - give[0]) * bestc: leave = True
        if g is None: g = (b[NS.END][0] - e) * side
        out.append(dict(day=t['day'], k=1, xbar=xj, pct=3 * g / e * 100 - NS.COST, leg_risk=3.0, rv=t['rv'], sys=sid, proxy=t['proxy'], mfe=mfe, R=g / r))
    return out


def rtrip(name, T):
    m = np.array([t['mfe'] for t in T]); R = np.array([t['R'] for t in T])
    s = ' | '.join(f"reached {x}R: {int((m >= x).sum())}, ended under +0.2R: {int(((m >= x) & (R < 0.2)).sum())}" for x in (1, 2, 3))
    print(f"   {name:<9} {len(T)} trades | {s}")


def row(tag, **kw):
    y = bk(**kw); print(f"   {verdict(y):<5}{tag:<52} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f})")


print(__doc__.split('\n')[0]); print(f"   live book v5.2.61: {' '.join(f'{a:+7.1f}' for a in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n")
Fl = [fade(t) for t in FE]; Il, Ml, Dl = fam(I0, 1, 4), fam(M, -1, 5), fam(D, 1, 2)
print('ROUND TRIPS (open gain on the proxy in R; R = FADE stop distance, 1% of the proxy for the 9:35 family = 3% on the leg)')
for n, T in (('FADE', Fl), ('IBS-LONG', Il), ('MIRROR', Ml), ('DIP', Dl)): rtrip(n, T)
print('\nFADE + giveback (on top of the +0.15R lock, 2R third and chandelier)')
for m in (1, 1.5, 2):
    for f in (0.4, 0.5): row(f'FADE: give back {f:.0%} once {m:g}R up', F=[fade(t, (f, m)) for t in FE])
print('\n9:35 FAMILY + giveback (IBS-LONG, MIRROR, DIP together)')
for m in (1, 1.5, 2, 3):
    for f in (0.4, 0.5): row(f'9:35 family: give back {f:.0%} once {m:g}R up', I=fam(I0, 1, 4, (f, m)), Mi=fam(M, -1, 5, (f, m)), Di=fam(D, 1, 2, (f, m)))
