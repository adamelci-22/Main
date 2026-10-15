#!/usr/bin/env python3
"""Fade list variants (IBIT bull leg BITX, XBI instead of IWM, + VIXY), alone and combined with the List-B pullback.
    python3 tools/backtest/fade_lists.py > tools/backtest/results_fade_lists.txt
Fade P&L is leverage x proxy return, so BTCL -> BITX (both 2x) does not change backtest numbers - only real fills (BTCL barely trades).
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, combined_v2 as C2, expand_lists as EX
from lab import get_data

ROWS = {'QQQ': ('TQQQ', 3, 'SQQQ', 3), 'SOXX': ('SOXL', 3, 'SOXS', 3), 'IWM': ('TNA', 3, 'TZA', 3), 'XLK': ('TECL', 3, 'TECS', 3),
        'IBIT': ('BITX', 2, 'BTCZ', 2), 'XBI': ('LABU', 3, 'LABD', 3), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)}
VARIANTS = {
    'A current (IWM, IBIT w/ BITX)': ['QQQ', 'SOXX', 'IWM', 'XLK', 'IBIT'],
    'B XBI instead of IWM': ['QQQ', 'SOXX', 'XBI', 'XLK', 'IBIT'],
    'C XBI instead of IWM + VIXY': ['QQQ', 'SOXX', 'XBI', 'XLK', 'IBIT', 'VIXY'],
    'D keep IWM, add XBI + VIXY': ['QQQ', 'SOXX', 'IWM', 'XLK', 'IBIT', 'XBI', 'VIXY'],
    'E keep IWM, add XBI': ['QQQ', 'SOXX', 'IWM', 'XLK', 'IBIT', 'XBI'],
}


def show(name, a, days, h):
    dl = a['daily']; tk = a['taken']; mix = collections.Counter(c['sys'] for c in tk)
    sd = st.pstdev(dl.values()); shp = st.mean(dl.values()) / sd * math.sqrt(252) if sd else 0
    print(f"   {name:<34} trades {len(tk):3d} (F {mix.get('FADE',0)}, PB {mix.get('PB',0)}) win {100*sum(c['usd']>0 for c in tk)/max(len(tk),1):3.0f}% "
          f"{st.mean(dl.values()):+.3f}%/day ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f}  H2 {st.mean(dl[d] for d in days[h:]):+.3f}  Sharpe~{shp:.1f}")


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2
    m.rvol = PBF.rvol(D)
    F = {p: MXD.norm_px(EX.fade_trades(D, days, p, r), 'FADE') for p, r in ROWS.items()}
    PB = C2.pb_cands(D, days)
    print(f"Fade list variants, {days[0]}..{days[-1]} ({len(days)} days). Pullback = List B. H1 Apr 7-Jul 10, H2 Jul 13-Oct 14.\n")
    print("Per proxy (fade alone): " + ', '.join(f"{p} {len(v)}tr avg {st.mean(c['pct'] for c in v):+.2f}%" for p, v in F.items()))
    for name, ps in VARIANTS.items():
        fd = [c for p in ps for c in F[p]]
        print(f"\n{name}: {ps}")
        show('fade alone', MXD.account(D, days, fd), days, h)
        show('fade + pullback (one position)', MXD.account(D, days, fd + PB), days, h)
        show('fade + pullback (two positions)', MXD.account(D, days, fd + PB, mode='two'), days, h)


if __name__ == '__main__':
    main()
