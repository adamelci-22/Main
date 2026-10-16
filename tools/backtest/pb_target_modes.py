#!/usr/bin/env python3
"""Where should the pullback take-profit sit relative to the morning-high candle? (governor question, 2026-10-16)
    python3 tools/backtest/pb_target_modes.py > tools/backtest/results/pb_target_modes.txt
wick = exact high (pre-v5.1) | floor = high rounded down to the cent (v5.1, live) | body = top of the high bar's body |
mid = middle of the high bar | close = highest close before the dip. Everything else as final_system.py (same account rules)."""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_system as FS, pb_final as PBF, mixed as MXD, manual as m
from lab import get_data

def stats(D, days, cs, sysname=None):
    a = MXD.account(D, days, cs); tk = [x for x in a['taken'] if sysname is None or x.get('sys') == sysname]
    dl = list(a['daily'].values()); w = [x for x in tk if x['usd'] > 0]; l = [x for x in tk if x['usd'] <= 0]
    h = len(days) // 2
    return (len(tk), 100 * len(w) / max(len(tk), 1), st.mean(dl), a['ret'], a['mdd'],
            st.mean(dl[:h]), st.mean(dl[h:]), st.mean([x['pct'] for x in w]) if w else 0, st.mean([x['pct'] for x in l]) if l else 0)

def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    full = D.days[1:]; full = [d for d in full if '2026-03-03' <= d <= '2026-10-14']; march = [d for d in full if d < '2026-04-07']
    print("Pullback take-profit placement (combined FADE+PULLBACK account, 2026-03-03..10-14; PB rows = pullback trades only)\n")
    print(f"{'mode':<7}{'PB trades':>10}{'PB win%':>9}{'PB avgW':>9}{'PB avgL':>9} | {'comb trades':>11}{'win%':>6}{'%/day':>8}{'return':>9}{'maxDD':>7}{'H1':>8}{'H2':>8} | {'March %/day':>12}")
    for mode in ('wick', 'floor', 'body', 'mid', 'close'):
        PBF.TARGET_MODE = mode
        f, p = FS.cands(D, full); cs = f + p
        pb = stats(D, full, cs, 'PB'); co = stats(D, full, cs)
        f2, p2 = FS.cands(D, march); ma = stats(D, march, f2 + p2)
        print(f"{mode:<7}{pb[0]:>10}{pb[1]:>8.0f}%{pb[7]:>+8.2f}%{pb[8]:>+8.2f}% | {co[0]:>11}{co[1]:>5.0f}%{co[2]:>+8.3f}{co[3]:>+8.1f}%{co[4]:>6.1f}%{co[5]:>+8.3f}{co[6]:>+8.3f} | {ma[2]:>+12.3f}")
    PBF.TARGET_MODE = 'floor'

if __name__ == '__main__':
    main()
