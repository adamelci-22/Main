#!/usr/bin/env python3
"""Full available period (2026-03-03..2026-10-14) for the fade (5 or 7 proxies) + pullback List B, plus the untouched March window.
    python3 tools/backtest/full_period.py > tools/backtest/results_full_period.txt
2026-03-03..04-06 was never used to choose any rule or list (all tuning used 04-07..10-14), so it is a genuine out-of-sample check.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, combined_v2 as C2, expand_lists as EX, fade_addone as FA
from lab import get_data

LISTS = {'current fade 5': ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI'], 'full fade 7 (+AMD, XLF)': ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD', 'XLF']}


def run(D, days, L):
    F = [c for p in L for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')]
    return F, C2.pb_cands(D, days)


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    for title, days in (('FULL PERIOD', D.days[1:]), ('UNTOUCHED WINDOW (never used for tuning)', [d for d in D.days[1:] if d < '2026-04-07'])):
        h = len(days) // 2
        print(f"== {title}: {days[0]}..{days[-1]} ({len(days)} days) ==")
        for name, L in LISTS.items():
            F, PB = run(D, days, L)
            for lab, c in (('fade alone', F), ('pullback alone', PB), ('fade + pullback', F + PB)):
                a = MXD.account(D, days, c); tk = a['taken']; dl = a['daily']
                print(f"  {name:<24} {lab:<16} trades {len(tk):3d} win {100*sum(x['usd']>0 for x in tk)/max(len(tk),1):3.0f}% {st.mean(dl.values()):+.3f}%/day "
                      f"ret {a['ret']:+6.1f}% maxDD {a['mdd']:4.1f}% H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
        print()


if __name__ == '__main__':
    main()
