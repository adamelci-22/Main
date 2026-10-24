#!/usr/bin/env python3
"""Predicted daily return by account size for the v5.2.14 lists (FADE QQQ SOXX IWM XLK XBI XLF; PULLBACK SOXS LABD TECS UVXY).
    python3 tools/backtest/scale_v5214.py > tools/backtest/results/scale_v5214.txt
Same liquidity/impact model as scale_500k.py (impact is an ASSUMPTION); whole-share rounding for small accounts as whole_share_drag.py.
"""
import io, contextlib, math, statistics as st
with contextlib.redirect_stdout(io.StringIO()):
    import scale_500k as S
caps = (None, 0.50, 0.30, 0.20, 0.10, 0.05)
print(f"Lists: FADE {S.FS.FADE}  PULLBACK {S.FS.PB}; {len(S.days)} days {S.days[0]}..{S.days[-1]}\n")
print(f"{'account':>11}" + ''.join(f"{('no cap' if c is None else str(int(c*100))+'% cap'):>10}" for c in caps) + "   best   $/day at best   $/week")
for a in (2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000, 2000000):
    r = {c: S.account(S.base, a, c)['day'] for c in caps}
    b = max(r, key=r.get)
    print(f"{a:>11,}" + ''.join(f"{r[c]:>+10.3f}" for c in caps) + f"   {('none' if b is None else str(int(b*100))+'%'):>5}   {a*r[b]/100:>12,.0f}   {5*a*r[b]/100:>8,.0f}")
