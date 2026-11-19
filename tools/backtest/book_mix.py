#!/usr/bin/env python3
"""Is the live mix best? (governor 2026-11-19: "Is this the best mix of systems or would removing some help?"). Research only.
Live book v5.2.64: PULLBACK, IBS-LONG, MIRROR, DIP, RELVAL, overnight leg 50%. Every subset that drops 1 or 2 systems, one shared account,
Massive tape 2022-01..2026-10. Rule as always: a change QUALIFIES if it beats live on TRAIN (2022, 2024, 2026) compounded and in 2 of 3
train years; it PASSES if it also beats live in BOTH TEST years (2023, 2025). Drawdown = worst peak-to-trough of the daily account.
    python3 -I tools/backtest/book_mix.py > tools/backtest/results/book_mix_2026-11-19.txt"""
import itertools, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR, new_systems as NS
B, BA, SB, TB, dm, TR, TE, ovn = FR.B, FR.BA, FR.SB, FR.TB, FR.dm, FR.TR, FR.TE, FR.ovn
S = dict(PULLBACK=FR.P0, **{'IBS-LONG': FR.I0}, MIRROR=FR.M, DIP=FR.D, RELVAL=B.BC.new(B.ds, B.ctx, dm, NS.relval, dict(a=48, z=72, xm=1.0), 0))


def daily(names):
    ov = 0.5 if 'OVERNIGHT' in names else 0.0
    T = [t for n in names if n != 'OVERNIGHT' for t in S[n]]
    return (1 + BA.acct(dm, TB.byday(T), after_stop=False)[0]) * (1 + ov * ovn) - 1


def dd(r): eq = np.cumprod(1 + r); return float((1 - eq / np.maximum.accumulate(eq)).max() * 100)


def cm(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


ALL = ['PULLBACK', 'IBS-LONG', 'MIRROR', 'DIP', 'RELVAL', 'OVERNIGHT']
r0 = daily(ALL); y0 = SB.yret(r0)
print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | TRAIN / TEST compounded (points vs live) | avg 2022-25 | max drawdown\n')
def row(tag, names, mark=''):
    r = daily(names); y = SB.yret(r)
    q = cm(y, TR) > cm(y0, TR) and (y[TR] > y0[TR]).sum() >= 2
    v = 'PASS' if q and (y[TE] > y0[TE]).all() else 'qual' if q else mark
    print(f"   {v:<5}{tag:<36} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cm(y, TR):+7.1f} ({cm(y, TR) - cm(y0, TR):+7.1f}) TEST {cm(y, TE):+7.1f} ({cm(y, TE) - cm(y0, TE):+6.1f}) | avg {y[:4].mean():+6.1f} | DD {dd(r):4.1f}%", flush=True)
row('LIVE: all six', ALL, 'live')
print('\nDROP ONE')
for n in ALL: row(f'without {n}', [x for x in ALL if x != n])
print('\nDROP TWO')
for a, b in itertools.combinations(ALL, 2): row(f'without {a} + {b}', [x for x in ALL if x not in (a, b)])
print('\nEACH SYSTEM ALONE (overnight leg off unless named)')
for n in ALL: row(f'{n} alone', [n])
