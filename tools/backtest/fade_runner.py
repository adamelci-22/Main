#!/usr/bin/env python3
"""Failed-retest fade, half at 2R: how should the stop on the held half move? (v3.126 Core Five, both halves)
    python3 tools/backtest/fade_runner.py > tools/backtest/results_fade_runner.txt
Entry/initial stop = retest.RC(fade=True). First half sold at 2R (OCO, at the level). Runner stop options (decided on completed
5-min bars, effective from the next bar, like a checkpoint moving a resting stop):
  be        = breakeven, never moves again (current)
  lock1R    = stop to +1R after the target
  trailNR   = stop trails N x R below the highest high since entry (never down)
  ema9/ema20= sell at the next open after a 5-min close below the 9/20-period EMA (proxy)
  prevlow   = stop ratchets to the prior completed bar's low (never down)
  chand     = chandelier: highest close since entry minus 2 x ATR(14, 5-min)
Hold to 15:55 unless stopped.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, retest as RT, twobar as TB
from lab import get_data
FADE = RT.RC(fade=True)


def run_trade(D, d, p, mode, last=77):
    raw = D.bars[p][d]; s = RT.setup(raw, FADE)
    if not s: return None
    k, side, e_real, stop_real = s
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry, stop = to_m(e_real), to_m(stop_real)
    if entry <= stop: return None
    r = entry - stop; T = entry + 2 * r
    pd_ = D.days[D.days.index(d) - 1]; prev = D.bars[p][pd_] if side > 0 else m.mirror(D.bars[p][pd_])[0]
    ser = [x[3] for x in prev] + [x[3] for x in b]
    e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
    gross = 0.0; rem = 1.0; hit = False; hi = entry; hic = entry; why = 'time'; xbar = last
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            gross += rem * (min(stop, o) - entry); rem = 0; why = 'stop' if not hit else 'runner_stop'; xbar = j; break
        if not hit and h >= T:
            gross += 0.5 * (max(T, o) - entry); rem = 0.5; hit = True
            stop = max(stop, entry if mode != 'lock1R' else entry + r)
        hi = max(hi, h); hic = max(hic, c)
        if hit and j < last:                       # runner management on the completed bar, effective next bar
            if mode.startswith('trail'): stop = max(stop, hi - float(mode[5:-1]) * r)
            elif mode == 'prevlow': stop = max(stop, l)
            elif mode == 'chand': stop = max(stop, hic - 2 * m.atr(b, j))
            elif mode in ('ema9', 'ema20') and c < (e9 if mode == 'ema9' else e20)[j]:
                gross += rem * (b[j + 1][0] - entry); rem = 0; why = 'runner_ema'; xbar = j + 1; break
    if rem > 0: gross += rem * (b[last][3] - entry)
    lev = TB.ROWS[p][2]
    return dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, pct=lev * gross / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100, hit=hit)


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1 = set(days[:h])
    print(f"Fade runner management after half at 2R, {days[0]}..{days[-1]}. Account: $2,000, cash-capped, one position at a time.\n")
    print(f"{'runner stop':<44}{'%/day':>8}{'ret%':>8}{'DD':>6}{'H1':>8}{'H2':>8}{'runner avg leg%':>17}")
    for mode, lab in (('be', 'breakeven, never moves (current)'), ('lock1R', 'lock +1R after target'), ('trail0.5R', 'trail 0.5R below the high'),
                      ('trail1R', 'trail 1R below the high'), ('trail2R', 'trail 2R below the high'), ('prevlow', 'prior bar low'),
                      ('chand', 'chandelier: high close - 2 ATR'), ('ema9', 'close below 9 EMA'), ('ema20', 'close below 20 EMA')):
        T = [t for d in days for p in TB.ROWS for t in [run_trade(D, d, p, mode)] if t]
        a = TB.account(D, days, T); dl = a['daily']
        d1 = st.mean(TB.account(D, sorted(H1), [t for t in T if t['day'] in H1])['daily'].values())
        d2 = st.mean(TB.account(D, [x for x in days if x not in H1], [t for t in T if t['day'] not in H1])['daily'].values())
        rn = [t['pct'] for t in T if t['hit']]
        print(f"{lab:<44}{st.mean(dl.values()):>+8.3f}{a['ret']:>+8.1f}{a['mdd']:>6.1f}{d1:>+8.3f}{d2:>+8.3f}{st.mean(rn):>+17.3f}")
    T = [t for d in days for p in TB.ROWS for t in [run_trade(D, d, p, 'be')] if t]
    print(f"\nTrades reaching 2R: {sum(t['hit'] for t in T)} of {len(T)} setups.")


if __name__ == '__main__':
    main()
