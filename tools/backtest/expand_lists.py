#!/usr/bin/env python3
"""Which other proxies suit the FADE, and which other leveraged tickers suit the PULLBACK? (current candidate rules)
    python3 tools/backtest/expand_lists.py > tools/backtest/results_expand_lists.txt
FADE rules = combined_v2 (1/3 at 2R, 2-ATR chandelier, 13:30). PULLBACK rules = pb_final (PULLBACK_SPEC.md, incl. $0.10 OCO rule).
Each candidate is scored alone (both halves), then a walk-forward check: candidates chosen on H1 only, added to the current list, judged on H2.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, fade_combo as FC, twobar as TB, mixed as MXD, pullback as P
from lab import get_data

CUR_FADE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'IBIT']
NEW_FADE = {  # proxy: (bull leg, bull lev, bear leg, bear lev)
    'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'XLF': ('FAS', 3, 'FAZ', 3), 'XLE': ('ERX', 2, 'ERY', 2),
    'XBI': ('LABU', 3, 'LABD', 3), 'XOP': ('GUSH', 2, 'DRIP', 2), 'GDX': ('NUGT', 2, 'DUST', 2), 'NVDA': ('NVDL', 2, 'NVDQ', 2),
    'TSLA': ('TSLL', 2, 'TSLQ', 1), 'MSTR': ('MSTU', 2, 'MSTZ', 2), 'AMD': ('AMDL', 2, 'AMDD', 1), 'UNG': ('BOIL', 2, 'KOLD', 2),
    'FXI': ('YINN', 3, 'YANG', 3), 'ETHA': ('ETHU', 2, 'ETHD', 2), 'SLV': ('AGQ', 2, 'ZSL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)}
CUR_PB = PI.B
NEW_PB = ['SPXS', 'SPXU', 'SDOW', 'SRTY', 'SARK', 'VXX', 'VIXY', 'TSLZ', 'TSDD', 'TSLQ', 'NVD', 'NVDQ', 'AMDD', 'MSTZ', 'JDST', 'DUST', 'ZSL',
          'SCO', 'HIBS', 'WEBS', 'QID', 'SDS', 'TWM', 'REW', 'SBIT', 'ETHD', 'FNGD', 'YANG', 'DRIP', 'ERY', 'FAZ']
LIQ = 250_000


def dollar_vol(D, s, days):
    v = [x[4] * x[3] for d in days if d in D.bars.get(s, {}) for x in D.bars[s][d][6:47]]
    return st.median(v) if v else 0


def fade_trades(D, days, p, row):
    bull, lb, bear, lbe = row
    saved = TB.ROWS.get(p); TB.ROWS[p] = (bull, bear, lb)
    out = []
    for d in days:
        if d not in D.bars.get(p, {}): continue
        t = FC.run_trade(D, d, p, R=2.0, frac=1 / 3, runner='chand2', last=47)
        if not t: continue
        if t['side'] < 0 and lbe != lb:   # rescale to the bear leg's leverage
            t['pct'] = (t['pct'] + TB.LEGCOST) / lb * lbe - TB.LEGCOST; t['leg_risk'] = t['leg_risk'] / lb * lbe
        out.append(t)
    if saved: TB.ROWS[p] = saved
    else: del TB.ROWS[p]
    return out


def acct(D, days, cands):
    a = MXD.account(D, days, cands); return st.mean(a['daily'].values()), a


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]; s1 = set(H1)
    m.rvol = PBF.rvol(D)
    print(f"List expansion study, {days[0]}..{days[-1]} ({len(days)} days). H1 {H1[0]}..{H1[-1]}, H2 {H2[0]}..{H2[-1]}. Liquid = median $ per 5-min bar >= ${LIQ:,}.\n")
    # ---------------- FADE
    print("== FADE: each proxy alone ==")
    print(f"{'proxy':<6}{'legs':<14}{'leg $/bar (bull/bear)':>24}{'trades':>7}{'win%':>6}{'avg leg%':>9}{'H1 avg':>8}{'H2 avg':>8}{'both+':>6}{'alone %/day':>12}")
    FT = {}
    for p in CUR_FADE + list(NEW_FADE):
        row = NEW_FADE.get(p) or (TB.ROWS[p][0], TB.ROWS[p][2], TB.ROWS[p][1], TB.ROWS[p][2])
        if p not in D.bars: print(f"{p:<6} no data"); continue
        T = fade_trades(D, days, p, row); FT[p] = (row, T)
        dv = (dollar_vol(D, row[0], days), dollar_vol(D, row[2], days))
        if not T: print(f"{p:<6}{row[0]+'/'+row[2]:<14}{dv[0]:>12,.0f}/{dv[1]:<11,.0f}{0:>7}"); continue
        a = [t['pct'] for t in T]; a1 = [t['pct'] for t in T if t['day'] in s1]; a2 = [t['pct'] for t in T if t['day'] not in s1]
        f = lambda v: st.mean(v) if v else float('nan')
        cand = MXD.norm_px(T, 'FADE'); ad, _ = acct(D, days, cand)
        both = 'yes' if a1 and a2 and f(a1) > 0 and f(a2) > 0 else ''
        tag = '  (current)' if p in CUR_FADE else ''
        print(f"{p:<6}{row[0]+'/'+row[2]:<14}{dv[0]:>12,.0f}/{dv[1]:<11,.0f}{len(T):>7}{100*sum(x>0 for x in a)/len(a):>6.0f}{f(a):>+9.3f}{f(a1):>+8.3f}{f(a2):>+8.3f}{both:>6}{ad:>+12.3f}{tag}")
    def fade_set(ps): return [c for p in ps for c in MXD.norm_px(FT[p][1], 'FADE')]
    liquid = lambda p: min(dollar_vol(D, FT[p][0][0], days), dollar_vol(D, FT[p][0][2], days)) >= LIQ
    pick = [p for p in NEW_FADE if p in FT and liquid(p) and len([t for t in FT[p][1] if t['day'] in s1]) >= 3
            and st.mean(t['pct'] for t in FT[p][1] if t['day'] in s1) > 0]
    print(f"\n   walk-forward: new proxies chosen on H1 only (liquid legs, >=3 H1 trades, H1 avg > 0): {pick}")
    for name, ps in (('current 5', CUR_FADE), ('current 5 + H1 picks', CUR_FADE + pick), ('current 5 + all liquid new', CUR_FADE + [p for p in NEW_FADE if p in FT and liquid(p)])):
        c = fade_set(ps)
        d1, _ = acct(D, H1, [x for x in c if x['day'] in s1]); d2, _ = acct(D, H2, [x for x in c if x['day'] not in s1])
        print(f"   FADE list {name:<30} H1 {d1:+.3f}%/day   H2 (unseen) {d2:+.3f}%/day")
    # ---------------- PULLBACK
    print("\n== PULLBACK: each ticker alone (PULLBACK_SPEC rules) ==")
    print(f"{'ticker':<7}{'$/5m bar':>12}{'trades':>7}{'win%':>6}{'avg%':>8}{'H1 avg':>8}{'H2 avg':>8}{'both+':>6}{'alone %/day':>12}")
    PT = {}
    for t in CUR_PB + NEW_PB:
        if t not in D.bars: print(f"{t:<7} no data"); continue
        PI.PROXY.setdefault(t, t)
        sig = PBF.run(D, days, [t], oco_gap=True); PT[t] = sig
        dv = dollar_vol(D, t, days)
        if not sig: print(f"{t:<7}{dv:>12,.0f}{0:>7}"); continue
        a = [x['pct'] for x in sig]; a1 = [x['pct'] for x in sig if x['day'] in s1]; a2 = [x['pct'] for x in sig if x['day'] not in s1]
        f = lambda v: st.mean(v) if v else float('nan')
        m.LEGS = {t: (PI.PROXY[t], 1)}; ad = st.mean(P.account(sig, D, days)['daily'].values())
        both = 'yes' if a1 and a2 and f(a1) > 0 and f(a2) > 0 else ''
        print(f"{t:<7}{dv:>12,.0f}{len(sig):>7}{100*sum(x>0 for x in a)/len(a):>6.0f}{f(a):>+8.3f}{f(a1):>+8.3f}{f(a2):>+8.3f}{both:>6}{ad:>+12.3f}{'  (current)' if t in CUR_PB else ''}")
    pickp = [t for t in NEW_PB if t in PT and dollar_vol(D, t, days) >= LIQ and len([x for x in PT[t] if x['day'] in s1]) >= 2
             and st.mean(x['pct'] for x in PT[t] if x['day'] in s1) > 0]
    print(f"\n   walk-forward: new tickers chosen on H1 only (liquid, >=2 H1 trades, H1 avg > 0): {pickp}")
    def pb_set(ts):
        m.LEGS = {t: (PI.PROXY[t], 1) for t in ts}; return [x for t in ts for x in PT.get(t, [])]
    for name, ts in (('current List B', CUR_PB), ('List B + H1 picks', CUR_PB + pickp), ('List B + all liquid new', CUR_PB + [t for t in NEW_PB if t in PT and dollar_vol(D, t, days) >= LIQ])):
        sig = pb_set(ts)
        d1 = st.mean(P.account([x for x in sig if x['day'] in s1], D, H1)['daily'].values())
        d2 = st.mean(P.account([x for x in sig if x['day'] not in s1], D, H2)['daily'].values())
        print(f"   PULLBACK list {name:<28} H1 {d1:+.3f}%/day   H2 (unseen) {d2:+.3f}%/day")


if __name__ == '__main__':
    main()
