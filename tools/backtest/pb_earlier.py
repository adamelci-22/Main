#!/usr/bin/env python3
"""PULLBACK earlier entry window, FADE removed (governor 2026-11-19: "If we remove fade system and extend the pull back timing to
earlier would that increase return over 5 years"). Research only.
Live PULLBACK triggers from the 10:10 bar (j0=8) to the 12:55 bar (j1=41); a dip must start at bar 4 (9:50) or later and the breakout
bar is looked for from bar 3. Variants: j0 = 6 (10:00), 7 (10:05); and an EARLY mode that lets the dip start at bar 2 (9:40) and the
opening range be the first 2 bars, with j0 = 4 (9:50) or 5 (9:55). Also the later end j1 = 47 (13:25).
Book = the live book as of v5.2.64: PULLBACK, IBS-LONG, MIRROR, DIP, RELVAL (in FADE's old slot), overnight leg 50%, FADE removed.
Pre-set rule: QUALIFIES = beats the live book on TRAIN (2022, 2024, 2026) compounded and in 2 of 3 train years; PASSES = also beats it
in both TEST years (2023, 2025).
    python3 -I tools/backtest/pb_earlier.py > tools/backtest/results/pb_earlier_2026-11-19.txt"""
import inspect, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS
import entry_pb as EP
B, BA, SB, TB, dm, TR, TE, ovn = FR.B, FR.BA, FR.SB, FR.TB, FR.dm, FR.TR, FR.TE, FR.ovn
I0, M, D = FR.I0, FR.M, FR.D
src = inspect.getsource(EP.signal).replace('if ps[0] < 4: continue', "if ps[0] < P.get('pmin', 4): continue").replace('for i in range(3, pre)', "for i in range(P.get('bmin', 3), pre)")
ns = dict(EP.signal.__globals__); exec(src, ns); EP.signal = ns['signal']        # parametric copy; defaults reproduce the live signal
REL = B.BC.new(B.ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0)


def pbt(**ch):
    P = dict(EP.LIVE, **ch); out = []
    for t in TB.pb_entries(B.ds, dm, B.PS.LEGS_M, P):
        m = B.PS.manage(t, B.BC.RUN); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
    return out


def book(P, rel=True): return SB.yret((1 + BA.acct(dm, TB.byday(P + I0 + M + D + (REL if rel else [])), after_stop=False)[0]) * (1 + 0.5 * ovn) - 1)


def cmp_(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


def stat(T):
    p = [t['pct'] for t in T]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
    return f"n {len(p)} win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.2f}% PF {g / l if l else 99:.2f}"


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | TRAIN / TEST compounded (points vs live) | average 2022-25 | PULLBACK trades alone\n')
    P0 = pbt(); live = book(P0)
    def row(tag, y, T, mark=''):
        print(f"   {mark:<5}{tag:<46} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cmp_(y, TR):+7.1f} ({cmp_(y, TR) - cmp_(live, TR):+6.1f}) TEST {cmp_(y, TE):+6.1f} ({cmp_(y, TE) - cmp_(live, TE):+6.1f}) | avg 22-25 {y[:4].mean():+6.1f} | {stat(T)}", flush=True)
    row('LIVE v5.2.64 (no FADE, RELVAL, PB 10:10-12:55)', live, P0, 'live')
    old = FR.book(FR.F0); print(f"   {'ref':<5}{'old book WITH FADE, no RELVAL':<46} {' '.join(f'{a:+7.1f}' for a in old)} | TRAIN {cmp_(old, TR):+7.1f} TEST {cmp_(old, TE):+6.1f} | avg 22-25 {old[:4].mean():+6.1f}")
    print()
    V = [('PB from 10:00 (j0=6)', dict(j0=6)), ('PB from 10:05 (j0=7)', dict(j0=7)),
         ('EARLY: from 9:50, dip from 9:40, OR 2 bars', dict(j0=4, pmin=2, bmin=2, orh=2)), ('EARLY: from 9:55, dip from 9:40, OR 2 bars', dict(j0=5, pmin=2, bmin=2, orh=2)),
         ('EARLY: from 10:00, dip from 9:40, OR 2 bars', dict(j0=6, pmin=2, bmin=2, orh=2)),
         ('later end: to 13:25 (j1=47)', dict(j1=47)), ('from 10:00 and to 13:25', dict(j0=6, j1=47))]
    for tag, ch in V:
        T = pbt(**ch); y = book(T)
        q = cmp_(y, TR) > cmp_(live, TR) and (y[TR] > live[TR]).sum() >= 2
        v = 'PASS' if q and (y[TE] > live[TE]).all() else 'qual' if q else ''
        row(tag, y, T, v)


if __name__ == '__main__':
    main()
