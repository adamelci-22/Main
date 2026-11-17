#!/usr/bin/env python3
"""PULLBACK runner fade-sell rules (governor 2026-11-17: "How was I up 4.4 percent today and ended at break even there must be a better way like a fade sell rule if
the trend is fading"). Research only. Today: UVXY 1/3 sold at the morning high 22.52, runner peaked 23.24, gave it all back to the breakeven stop 21.53.
Live runner: out on the first 5-minute close under the 20-EMA (or the breakeven stop, or 13:30). Each test keeps that and ADDS one fade rule, or replaces it:
  GIVE   once the best close is at least m R above entry, sell when a close gives back f of the open gain (f = 0.3 0.4 0.5 0.6; m = 1 2 3)
  PEAK   sell when a close is p % below the best close since entry (p = 1 1.5 2 3), only after the 1/3 sold
  LOCK   once the best close is at least m R up, raise the stop to entry + n R (m/n = 2/1, 3/1, 3/2, 4/2)
  FAST   runner on the 9-EMA close or the 3-bar low (replacing the 20-EMA)
Judged inside the live joint book v5.2.60, one change at a time. Train 2022/2024/2026, test 2023/2025. QUALIFIES = beats the live book on train compounded and in 2 of 3 train
years; PASSES = also beats it in both test years.
    python3 -I tools/backtest/pb_fade_exit.py > tools/backtest/results/pb_fade_exit_2026-11-17.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pb_three_tranche as P3
PS, ENT, book, yb, verdict, stat = P3.PS, P3.ENT, P3.book, P3.yb, P3.verdict, P3.stat


def manage(t, c):
    """1/3 at the morning high (stop to breakeven), 2/3 runner. c: ema (20 | 9 | None), give (f, m), peak p, lock (m, n), nlow n."""
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']; T = t['T']
    rem, g, hit, pend, out, bestc = 1.0, 0.0, False, None, False, e; j = k
    for j in range(k, PS.LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if pend is not None: stop = max(stop, pend); pend = None
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if T is not None and not hit and h >= T:
            px = max(T, o); q = min(1 / 3, rem); g += q * (px - e); rem -= q; hit = True; stop = max(stop, e)
        bestc = max(bestc, cl)
        if c.get('lock') and (bestc - e) / r >= c['lock'][0]: pend = max(pend or -1e9, e + c['lock'][1] * r)
        if hit and j < PS.LAST:
            ema = c.get('ema', 20)
            if ema and cl < t['e20' if ema == 20 else 'e9'][j]: out = True
            if c.get('nlow') and j > k and cl < min(x[2] for x in b[max(k, j - c['nlow']):j]): out = True
            if c.get('give'):
                f, m = c['give']
                if (bestc - e) / r >= m and cl < e + (1 - f) * (bestc - e): out = True
            if c.get('peak') and cl < bestc * (1 - c['peak'] / 100): out = True
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, rv=t['rv'], sys=1)


def pbt(c): return [manage(t, c) for t in ENT]


def row(tag, T):
    y = book(T)
    print(f"   {verdict(y):<5}{tag:<58} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) | {stat(T)}")
    return y


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); parentheses = points vs the live book; stats = PULLBACK trades alone\n')
    live = pbt(dict()); y0 = row('LIVE check (must match): runner 20-EMA close', live)
    res = []
    print('\nGIVE: + sell when a close gives back f of the open gain, once it is m R up')
    for m in (1, 2, 3):
        for f in (0.3, 0.4, 0.5, 0.6): res.append((f'give back {f:.0%} after {m}R', row(f'+ give back {f:.0%} of the gain once {m}R up', pbt(dict(give=(f, m))))))
    print('\nPEAK: + sell when a close is p % under the best close')
    for p in (1, 1.5, 2, 3): res.append((f'peak -{p}%', row(f'+ close {p:g}% under the best close', pbt(dict(peak=p)))))
    print('\nLOCK: + raise the stop once the trade is well up')
    for m, n in ((2, 1), (3, 1), (3, 2), (4, 2)): res.append((f'lock {n}R at {m}R', row(f'+ stop to +{n}R once {m}R up', pbt(dict(lock=(m, n))))))
    print('\nFAST runner (replaces the 20-EMA)')
    res.append(('9-EMA', row('runner 9-EMA close', pbt(dict(ema=9)))))
    res.append(('3-bar low', row('runner 3-bar low close (no 20-EMA)', pbt(dict(ema=None, nlow=3)))))
    np_ = sum(verdict(y) == 'PASS' for _, y in res); nq = sum(verdict(y) == 'qual' for _, y in res)
    best = max(res, key=lambda x: x[1][:4].mean())
    print(f"\n   {len(res)} fade rules: {np_} PASS, {nq} qualify on train only. Best average 2022-25: {best[0]} {best[1][:4].mean():+.1f} vs live {yb[:4].mean():+.1f}")


if __name__ == '__main__':
    main()
