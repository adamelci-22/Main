#!/usr/bin/env python3
"""FADE replacement screen (governor 2026-11-19: "Yes cut it and find a system that can replace it build it off of 2022 2024 2026 and
test off of 2023 2025"). Research only.
Base = the live joint book WITHOUT FADE (PULLBACK, IBS-LONG, MIRROR, DIP, overnight leg at 50%) on the Massive 5-minute tape
2022-01-03..2026-10-30, one shared account (3% risk capped at cash, one position at a time, 3 entries a day, same-system loss block).
Each candidate takes FADE's empty slot (sys 0) beside the other systems. Candidates: every proxy -> 3x leg intraday system already
coded in new_systems.py, new_systems2.py and new_systems3.py, at its default and a small grid. The old FADE is shown for reference.
Pre-set rule (same as every study since 2026-11-13): a candidate QUALIFIES if the book beats the base on TRAIN (2022, 2024, 2026)
compounded and in 2 of 3 train years. It PASSES if it also beats the base in BOTH test years (2023, 2025).
The PICK is the qualifier with the best train compounded return, chosen before the test years are read.
    python3 -I tools/backtest/fade_replace.py > tools/backtest/results/fade_replace_2026-11-19.txt"""
import os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pb_three_tranche as P3
import new_systems as NS, new_systems2 as N2, new_systems3 as N3
B, BA, BM, SB, TB, O = P3.B, P3.BA, P3.BM, P3.SB, P3.TB, P3.O
dm, ovn, TR, TE = P3.dm, P3.ovn, P3.TR, P3.TE
P0 = B.pb_trades(); I0, M, D, F0 = P3.I0, P3.M, P3.D, P3.F0
T0 = time.time()


def book(extra):
    return SB.yret((1 + BA.acct(dm, TB.byday(extra + P0 + I0 + M + D), after_stop=False)[0]) * (1 + 0.5 * ovn) - 1)


base = book([]); live = book(F0)


def judge(y):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + base[TR] / 100) and (y[TR] > base[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > base[TE]).all()) else 'qual' if q else ''


def stat(T):
    p = [t['pct'] for t in T]
    if not p: return 'n 0'
    g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
    return f"n {len(p)} win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.2f}% PF {g / l if l else 99:.2f}"


def trcmp(y): return (np.prod(1 + y[TR] / 100) - 1) * 100


def tecmp(y): return (np.prod(1 + y[TE] / 100) - 1) * 100


def row(tag, y, T=None, mark=''):
    print(f"   {mark:<5}{tag:<44} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {trcmp(y):+7.1f} ({trcmp(y) - trcmp(base):+6.1f}) TEST {tecmp(y):+6.1f} ({tecmp(y) - tecmp(base):+6.1f})"
          + (f" | {stat(T)}" if T is not None else ''), flush=True)


GRID = [('RELVAL', NS.relval, [dict(a=48, z=72, xm=x) for x in (0.75, 1.0, 1.25)] + [dict(a=36, z=72, xm=1.0), dict(a=48, z=60, xm=1.0)]),
        ('VWAPTREND', NS.vwaptrend, [dict(band=0.1), dict(band=0.2), dict(band=0.1, last=NS.NOON)]),
        ('VWAPPB', NS.vwappb, [dict(xm=0.5), dict(xm=1.0)]),
        ('ORB5', NS.orb5, [dict(), dict(last=NS.NOON)]),
        ('HOUR1', NS.hour1, [dict(xm=0.5), dict(xm=1.0)]),
        ('IBS-OC', NS.ibs, [dict(lo=0.2, hi=0.8), dict(lo=0.1, hi=0.9)]),
        ('MIDBOX', NS.midbox, [dict()]),
        ('FADEBOX', NS.fadebox, [dict(), dict(a=6, z=12)]),
        ('PDFADE', NS.pdfade, [dict(), dict(win=6)]),
        ('REBAL', NS.rebal, [dict(xm=1.0), dict(xm=1.5), dict(xm=1.0, fade=True)]),
        ('SWITCH', N2.switch, [dict()]),
        ('BREADTH', N2.breadth, [dict(pick='strong'), dict(pick='weak')]),
        ('GAPDN', N2.gapdn, [dict(gm=0.5), dict(gm=1.0)]),
        ('IBSC', N2.ibsc, [dict(lo=0.2), dict(lo=0.1)]),
        ('DIPDAY', N3.dipday, [dict(xm=1.0), dict(xm=1.5), dict(xm=1.0, mirror=True)]),
        ('PMFADE', N3.pmfade, [dict(k_=1.5), dict(k_=2.0)]),
        ('RELBASK', N3.relref, [dict(mode='bask'), dict(mode='pair')]),
        ('DOWNN', N3.downn, [dict(n=3), dict(n=4)])]


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th; TEST = 2nd, 4th); parentheses = points vs the base; stats = candidate trades alone\n')
    row('BASE: live book without FADE', base); row('reference: live book WITH the old FADE', live, F0, judge(live))
    res = []
    for name, fn, kws in GRID:
        print(f"\n{name}")
        for kw in kws:
            tag = f"{name} {' '.join(f'{k}={v}' for k, v in kw.items()) or 'default'}"
            try:
                T = BA_new(fn, kw)
            except Exception as e:
                print(f"   ERR  {tag}: {type(e).__name__} {e}"); continue
            y = book(T); v = judge(y); row(tag, y, T, v); res.append((tag, y, T, v))
    q = [r for r in res if r[3]]
    print(f"\n   {len(res)} candidates: {sum(r[3] == 'PASS' for r in res)} PASS, {sum(r[3] == 'qual' for r in res)} qualify on train only. ({time.time() - T0:.0f}s)")
    if q:
        pick = max(q, key=lambda r: trcmp(r[1]))
        print(f"   PICK (best TRAIN among qualifiers, chosen before reading TEST): {pick[0]} -> {pick[3] or 'fails test'}")
        row('PICK', pick[1], pick[2], pick[3])
        print('\n   qualifiers by TRAIN:')
        for r in sorted(q, key=lambda r: -trcmp(r[1])): row(r[0], r[1], r[2], r[3])
    else:
        print('   no candidate qualifies on TRAIN: the base without FADE stands')


def BA_new(fn, kw): return B.BC.new(B.ds, B.ctx, dm, fn, kw, 0)


if __name__ == '__main__':
    main()
