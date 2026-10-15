#!/usr/bin/env python3
"""(1) How well does 'leverage x proxy return' track the leveraged partner's real price over fade trades?
   (2) Add-one test: fade list QQQ SOXX IWM XLK XBI (v3.130) + one candidate proxy at a time; fade alone and with the List-B pullback.
    python3 tools/backtest/fade_addone.py > tools/backtest/results_fade_addone.txt
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, combined_v2 as C2, expand_lists as EX, fade_lists as FL, retest as RT
from lab import get_data

BASE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI']
CAND = dict(EX.NEW_FADE); CAND['IBIT'] = ('BITX', 2, 'BTCZ', 2); CAND.pop('XBI', None)
ROWS = dict(FL.ROWS); ROWS.update(CAND)


def tracking(D, days, p, row):
    """For each fade trade: real leg return (entry-bar open -> exit-bar close) vs leverage x proxy return over the same bars."""
    bull, lb, bear, lbe = row; out = []
    for d in days:
        if d not in D.bars.get(p, {}): continue
        s = RT.setup(D.bars[p][d], RT.RC(fade=True))
        if not s: continue
        k, side, e, _ = s
        t = [x for x in EX.fade_trades(D, [d], p, row)]
        if not t: continue
        x = t[0]['xbar']; leg = bull if side > 0 else bear; lev = lb if side > 0 else lbe
        if leg not in D.bars or d not in D.bars[leg]: continue
        L = D.bars[leg][d]; P = D.bars[p][d]
        real = (L[x][3] / L[k][0] - 1) * 100
        est = lev * side * (P[x][3] / P[k][0] - 1) * 100
        out.append((real, est))
    return out


def stats(a, days, h):
    dl = a['daily']; return st.mean(dl.values()), st.mean(dl[d] for d in days[:h]), st.mean(dl[d] for d in days[h:]), a['ret'], a['mdd'], len(a['taken'])


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; m.rvol = PBF.rvol(D)
    print("(1) Tracking check: real leveraged-partner return vs leverage x proxy return, per fade trade (entry open -> exit bar close)")
    print(f"{'proxy':<6}{'legs':<12}{'n':>4}{'avg real':>10}{'avg est':>9}{'avg gap':>9}{'abs gap':>9}{'corr':>6}")
    for p in BASE + sorted(CAND):
        if p not in D.bars: continue
        tr = tracking(D, days, p, ROWS[p])
        if len(tr) < 3: print(f"{p:<6}{ROWS[p][0]+'/'+ROWS[p][2]:<12}{len(tr):>4}  too few"); continue
        r = [a for a, _ in tr]; e = [b for _, b in tr]
        mr, me = st.mean(r), st.mean(e)
        den = math.sqrt(sum((a - mr) ** 2 for a in r) * sum((b - me) ** 2 for b in e))
        cor = sum((a - mr) * (b - me) for a, b in tr) / den if den else 0
        print(f"{p:<6}{ROWS[p][0]+'/'+ROWS[p][2]:<12}{len(tr):>4}{mr:>+10.3f}{me:>+9.3f}{mr-me:>+9.3f}{st.mean(abs(a-b) for a,b in tr):>9.3f}{cor:>6.2f}")
    F = {p: MXD.norm_px(EX.fade_trades(D, days, p, ROWS[p]), 'FADE') for p in BASE + list(CAND) if p in D.bars}
    PB = C2.pb_cands(D, days)
    base_f = [c for p in BASE for c in F[p]]
    b1 = stats(MXD.account(D, days, base_f), days, h); b2 = stats(MXD.account(D, days, base_f + PB), days, h)
    print(f"\n(2) Add-one test. BASE fade list {BASE}:")
    print(f"   fade alone   {b1[0]:+.3f}%/day (H1 {b1[1]:+.3f}, H2 {b1[2]:+.3f}) ret {b1[3]:+.1f}% DD {b1[4]:.1f}% trades {b1[5]}")
    print(f"   fade + PB    {b2[0]:+.3f}%/day (H1 {b2[1]:+.3f}, H2 {b2[2]:+.3f}) ret {b2[3]:+.1f}% DD {b2[4]:.1f}% trades {b2[5]}\n")
    print(f"{'add':<6}{'legs':<12}{'leg $/bar bull/bear':>22} | {'fade alone d/day':>16}{'dH1':>8}{'dH2':>8} | {'fade+PB d/day':>14}{'dH1':>8}{'dH2':>8}{'DD':>6}  verdict")
    for p in sorted(CAND):
        if p not in F: continue
        f = base_f + F[p]
        s1 = stats(MXD.account(D, days, f), days, h); s2 = stats(MXD.account(D, days, f + PB), days, h)
        dv = (EX.dollar_vol(D, ROWS[p][0], days), EX.dollar_vol(D, ROWS[p][2], days))
        good = s2[1] > b2[1] and s2[2] > b2[2]
        thin = min(dv) < EX.LIQ
        verdict = ('helps both halves' if good else 'mixed/hurts') + (', THIN leg' if thin else '')
        print(f"{p:<6}{ROWS[p][0]+'/'+ROWS[p][2]:<12}{dv[0]:>10,.0f}/{dv[1]:<11,.0f}| {s1[0]-b1[0]:>+16.3f}{s1[1]-b1[1]:>+8.3f}{s1[2]-b1[2]:>+8.3f} | "
              f"{s2[0]-b2[0]:>+14.3f}{s2[1]-b2[1]:>+8.3f}{s2[2]-b2[2]:>+8.3f}{s2[4]:>6.1f}  {verdict}")


if __name__ == '__main__':
    main()
