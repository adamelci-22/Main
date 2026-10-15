#!/usr/bin/env python3
"""Combined system v2: failed-retest fade (Core Five proxies) + pullback candidate (List B), each with the governor's chosen exits.
    python3 tools/backtest/combined_v2.py > tools/backtest/results_combined_v2.txt
FADE: QQQ/SOXX/IWM/XLK/IBIT box 9:30-10:00, break, retest closes back inside -> opposite leg; stop beyond the failed breakout's extreme;
      1/3 off at 2R (OCO), rest breakeven -> 2-ATR chandelier ratchet; sell rest 13:30.
PB:   List B (SOXS SQQQ TZA TECS BTCZ LABD UVXY), rules in PULLBACK_SPEC.md incl. the $0.10 OCO rule; one OCO 100% at the morning high; 13:30.
Account: $2,000, 3% risk capped at cash, max 3 entries/day.  one = one position at a time; two = two at once, half the cash each.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, fade_combo as FC, twobar as TB, mixed as MXD
from lab import get_data


def pb_cands(D, days):
    sig = PBF.run(D, days, PI.B, oco_gap=True)
    return [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'],
                 risk=x['risk'] / x['entry'] * 100) for x in sig]


def fade_cands(D, days):
    return MXD.norm_px([t for d in days for p in TB.ROWS for t in [FC.run_trade(D, d, p, R=2.0, frac=1 / 3, runner='chand2', last=47)] if t], 'FADE')


def show(name, a, days, h):
    dl = a['daily']; tk = a['taken']; mix = collections.Counter(c['sys'] for c in tk)
    sd = st.pstdev(dl.values()); shp = st.mean(dl.values()) / sd * math.sqrt(252) if sd else 0
    print(f"{name:<36} trades {len(tk):3d} (FADE {mix.get('FADE',0)}, PB {mix.get('PB',0)}) win {100*sum(c['usd']>0 for c in tk)/max(len(tk),1):3.0f}% "
          f"{st.mean(dl.values()):+.3f}%/day  ret {a['ret']:+6.1f}%  maxDD {a['mdd']:4.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f}  H2 {st.mean(dl[d] for d in days[h:]):+.3f}  Sharpe~{shp:.1f}")


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2
    PB = pb_cands(D, days); FD = fade_cands(D, days)
    m.rvol = PBF.rvol(D)
    print(f"Combined fade + pullback (List B), {days[0]}..{days[-1]} ({len(days)} days). H1 = Apr 7-Jul 10 (SPY +15%), H2 = Jul 13-Oct 14 (SPY +2%).")
    print(f"Candidate setups: FADE {len(FD)}, PB {len(PB)}. Goal +0.400%/day.\n")
    dp = set(c['day'] for c in PB); df = set(c['day'] for c in FD)
    print(f"Days with a fade setup {len(df)}, with a pullback setup {len(dp)}, both {len(dp & df)}, either {len(dp | df)} of {len(days)}")
    both = [d for d in dp & df]
    clash = sum(1 for d in both if min(c['k'] for c in PB if c['day'] == d) <= max(c['xbar'] for c in FD if c['day'] == d))
    print(f"On shared days, the pullback triggered while a fade could still be open: {clash} of {len(both)}\n")
    show('Fade alone', MXD.account(D, days, FD), days, h)
    show('Pullback alone (List B)', MXD.account(D, days, PB), days, h)
    print()
    a1 = MXD.account(D, days, PB + FD); show('COMBINED, one position at a time', a1, days, h)
    a2 = MXD.account(D, days, PB + FD, mode='two'); show('COMBINED, two positions (half cash)', a2, days, h)
    for name, a in (('one position', a1), ('two positions', a2)):
        print(f"\n-- {name}: detail")
        mo = collections.defaultdict(float)
        for c in a['taken']: mo[c['day'][:7]] += c['usd']
        print('   by month: ' + ', '.join(f"{k} {v:+.0f}$" for k, v in sorted(mo.items())))
        g = collections.defaultdict(lambda: [0, 0.0])
        for c in a['taken']: g[(c['sys'], c['name'])][0] += 1; g[(c['sys'], c['name'])][1] += c['usd']
        print('   by system/ticker: ' + ', '.join(f"{s} {nm} {n}tr {u:+.0f}$" for (s, nm), (n, u) in sorted(g.items(), key=lambda kv: -kv[1][1])))
        dl = list(a['daily'].values())
        print(f"   trade days {sum(1 for v in dl if v != 0)}; winning days {sum(1 for v in dl if v > 0)}, losing days {sum(1 for v in dl if v < 0)}; "
              f"best day {max(dl):+.2f}%, worst day {min(dl):+.2f}%; months positive {sum(1 for v in mo.values() if v > 0)} of {len(mo)}")
        top = sorted(a['taken'], key=lambda c: -c['usd'])[:3]
        rest = sum(c['usd'] for c in a['taken']) - sum(c['usd'] for c in top)
        print(f"   top 3 trades {sum(c['usd'] for c in top):+.0f}$ ({', '.join(c['day']+' '+c['sys']+' '+c['name'] for c in top)}); everything else {rest:+.0f}$")


if __name__ == '__main__':
    main()
