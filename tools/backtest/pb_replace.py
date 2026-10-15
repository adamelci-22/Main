#!/usr/bin/env python3
"""Pullback list: keep SOXS LABD TECS UVXY, cut BTCZ SQQQ TZA, pick 5 replacements by a fixed rule, test.
    python3 tools/backtest/pb_replace.py > tools/backtest/results_pb_replace.txt
Rule (fixed before looking at the picks): inverse/fear leveraged ticker, median $ per 5-min bar >= $250k, >= 4 trades over the full period,
average trade positive in BOTH halves (split 2026-06-24); rank by average trade; top 5.
Full period 2026-03-03..10-14; March 3 - April 6 shown separately (never used to tune any rule).
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, pullback as P, mixed as MXD, expand_lists as EX, fade_addone as FA
from lab import get_data

KEEP = ['SOXS', 'LABD', 'TECS', 'UVXY']
CUT = ['BTCZ', 'SQQQ', 'TZA']
POOL = ['SPXS', 'SPXU', 'SDOW', 'SRTY', 'SARK', 'VXX', 'VIXY', 'TSLZ', 'TSDD', 'TSLQ', 'TSLS', 'NVD', 'NVDQ', 'NVDS', 'AMDD', 'MSTZ', 'SMST',
        'JDST', 'DUST', 'ZSL', 'SCO', 'HIBS', 'WEBS', 'QID', 'SDS', 'TWM', 'REW', 'SBIT', 'BITI', 'ETHD', 'FNGD', 'YANG', 'DRIP', 'ERY', 'FAZ',
        'CONI', 'PLTZ', 'SPDN', 'DXD']
FADE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD']


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = D.days[1:]; h = len(days) // 2; s1 = set(days[:h]); mar = [d for d in days if d < '2026-04-07']
    for t in KEEP + CUT + POOL: PI.PROXY.setdefault(t, t)
    print(f"Pullback replacements, {days[0]}..{days[-1]} ({len(days)} days), halves split at {days[h]}.\n")
    print(f"{'ticker':<7}{'$/5m bar':>12}{'trades':>7}{'win%':>6}{'avg%':>8}{'H1 avg':>8}{'H2 avg':>8}{'Mar-Apr6':>10}  status")
    sc = {}
    for t in KEEP + CUT + POOL:
        if t not in D.bars: print(f"{t:<7} no data"); continue
        sig = PBF.run(D, days, [t], oco_gap=True); dv = EX.dollar_vol(D, t, days)
        f = lambda v: st.mean(v) if v else float('nan')
        a = [x['pct'] for x in sig]; a1 = [x['pct'] for x in sig if x['day'] in s1]; a2 = [x['pct'] for x in sig if x['day'] not in s1]
        am = [x['pct'] for x in sig if x['day'] < '2026-04-07']
        ok = t in POOL and dv >= 250_000 and len(a) >= 4 and a1 and a2 and f(a1) > 0 and f(a2) > 0
        sc[t] = (ok, f(a), sig)
        status = 'kept' if t in KEEP else 'cut' if t in CUT else ('QUALIFIES' if ok else '')
        print(f"{t:<7}{dv:>12,.0f}{len(a):>7}{(100*sum(x>0 for x in a)/len(a) if a else 0):>6.0f}{f(a):>+8.3f}{f(a1):>+8.3f}{f(a2):>+8.3f}"
              f"{(f(am) if am else float('nan')):>+10.3f}  {status}")
    picks = sorted([t for t in POOL if t in sc and sc[t][0]], key=lambda t: -sc[t][1])[:5]
    print(f"\nQualifying replacements, ranked: {sorted([t for t in POOL if t in sc and sc[t][0]], key=lambda t: -sc[t][1])}")
    print(f"Top 5 picked: {picks}\n")
    LISTS = {'old List B': KEEP + CUT, 'kept 4 only': KEEP, 'kept 4 + 5 picks': KEEP + picks}
    fade = [c for p in FADE6 for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')]
    for name, L in LISTS.items():
        m.LEGS = {t: (PI.PROXY[t], 1) for t in L}
        sig = [x for t in L for x in sc[t][2]]
        a = P.account(sig, D, days); dl = a['daily']; tk = a['taken']
        am = P.account([x for x in sig if x['day'] < '2026-04-07'], D, mar)
        print(f"PULLBACK {name:<18} {L}")
        print(f"   alone: trades {len(tk)} win {100*sum(x['usd']>0 for x in tk)/max(len(tk),1):.0f}% {st.mean(dl.values()):+.3f}%/day ret {a['ret']:+.1f}% DD {a['mdd']:.1f}% "
              f"H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f} | Mar-Apr6 {am['ret']:+.1f}% ({len(am['taken'])} trades)")
        pbc = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in sig]
        c = MXD.account(D, days, fade + pbc); dlc = c['daily']
        cm = MXD.account(D, mar, [x for x in fade + pbc if x['day'] < '2026-04-07'])
        mix = collections.Counter(x['sys'] for x in c['taken'])
        print(f"   with fade-6: trades {len(c['taken'])} (F {mix['FADE']}, PB {mix['PB']}) {st.mean(dlc.values()):+.3f}%/day ret {c['ret']:+.1f}% DD {c['mdd']:.1f}% "
              f"H1 {st.mean(dlc[d] for d in days[:h]):+.3f} H2 {st.mean(dlc[d] for d in days[h:]):+.3f} | Mar-Apr6 {cm['ret']:+.1f}%\n")


if __name__ == '__main__':
    main()
