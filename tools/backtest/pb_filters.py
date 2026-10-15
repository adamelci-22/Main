#!/usr/bin/env python3
"""Pullback buy on the v3.126 universe: (1) live-execution realism, (2) walk-forward test of the trend-anatomy filters.
    python3 tools/backtest/pb_filters.py > tools/backtest/results_pb_filters.txt
Realism: live checkpoints run every 5 minutes and the resting stop ties up the shares, so the 60% sale at the morning high
happens at the NEXT bar's open after a completed bar trades through the high (not at the high itself).
Filters (from results_core5_pullback.txt): A skip if the morning breakout came before 10:00; B skip deep pullbacks (>62% of the
morning move given back); C skip weak trends (proxy < +0.5% since open in the trade's direction); D drop the Nasdaq and Small-cap rows.
Walk-forward: every combination of A-D is scored on H1; the best H1 combination is judged on H2.
Caveat: filters are applied to the first qualifying signal per ticker-day; a later signal that day is not searched for.
"""
import itertools, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, matrix as MX, core5_pullback as C
from lab import get_data

LEGS = {k: v for k, v in C.LEGS.items() if k not in ('BITX', 'SBIT')}     # v3.126: BTCL / BTCZ only

_orig_manage = m.manage
def manage_delayed(b, spec, ema_arr, cost, orig):
    """As manual.manage, but the target sale fills at the next bar's open after a bar's high reaches the target."""
    k, entry, stop, T, frac, post = spec['k'], spec['entry'], spec['stop'], spec.get('T'), spec.get('frac', 1.0), spec.get('post')
    risk = entry - stop
    if risk <= 0: return None
    rem = 1.0; gross = 0.0; cost_tot = cost * orig(entry); hit = False; pending = False; why = 'eod'; xbar = m.LAST
    def sell(price, f):
        nonlocal gross, cost_tot, rem
        gross += f * (price - entry); cost_tot += f * cost * orig(price); rem -= f
    for j in range(k, m.LAST + 1):
        o, h, l, c, v = b[j]
        if pending and not hit:
            sell(o, frac); hit = True; pending = False
        if l <= stop:
            sell(min(stop, o), rem); why = 'stop'; xbar = j; break
        if T is not None and not hit and not pending and h >= T: pending = True
        if post in ('ema9', 'ema20') and hit and c < ema_arr[j] and j < m.LAST:
            sell(b[j + 1][0], rem); why = 'trail'; xbar = j + 1; break
        if j == m.LAST:
            sell(c, rem); why = 'eod'; xbar = j
    if rem > 1e-9: sell(b[m.LAST][3], rem)
    return gross - cost_tot, risk, xbar, why


def run(D, days, exit_k=77, delayed=False):
    m.manage = manage_delayed if delayed else _orig_manage
    try: return MX.run(D, days, LEGS, 0.75, 41, exit_k, 'limit')
    finally: m.manage = _orig_manage


def summary(tag, D, days, sig, h):
    a = P.account(sig, D, days); T = a['taken']; dl = a['daily']
    return (f"{tag:<58} trades {len(T):3d} win {100*sum(x['usd']>0 for x in T)/max(len(T),1):3.0f}% avg/day {st.mean(dl.values()):+.3f}% "
            f"ret {a['ret']:+6.1f}% maxDD {a['mdd']:4.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}"), a


FILTERS = {
    'A no breakout before 10:00': lambda x: x['f']['brk'] >= 6,
    'B no deep pullback (>62%)': lambda x: x['f']['depth'] <= 62,
    'C no weak trend (<0.5%)': lambda x: x['f']['move'] >= 0.5,
    'D drop Nasdaq & Small caps': lambda x: C.ROW_OF[x['inst']] not in ('Nasdaq', 'Small caps'),
}


def main():
    D = get_data(); m.rvol = MX.safe_rvol
    days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"Pullback buy, v3.126 universe (TQQQ/SQQQ, SOXL/SOXS, TNA/TZA, TECL/TECS, BTCL/BTCZ), {days[0]}..{days[-1]} ({len(days)} days)\n")
    print("== 1. Live-execution realism ==")
    base = None
    for exit_k, ex in ((77, '15:55'), (36, '12:30')):
        for delayed in (False, True):
            s = run(D, days, exit_k, delayed)
            line, _ = summary(f"exit {ex}, 60% sold {'next checkpoint (live-realistic)' if delayed else 'exactly at the high (backtest)'}", D, days, s, h)
            print(line)
            if exit_k == 77 and delayed: base = s
    print("\n== 2. Filter walk-forward (live-realistic version: 15:55 exit, 60% sold at the next checkpoint) ==")
    for x in base: x['f'] = C.features(D, x)
    s1 = [x for x in base if x['day'] in set(H1)]; s2 = [x for x in base if x['day'] in set(H2)]
    rows = []
    names = list(FILTERS)
    for r in range(0, len(names) + 1):
        for combo in itertools.combinations(names, r):
            keep = lambda v: [x for x in v if all(FILTERS[n](x) for n in combo)]
            a1 = P.account(keep(s1), D, H1); a2 = P.account(keep(s2), D, H2)
            rows.append((combo, len(a1['taken']), st.mean(a1['daily'].values()), len(a2['taken']), st.mean(a2['daily'].values())))
    print(f"{'filters':<92}{'trd H1':>7}{'H1 %/day':>10}{'trd H2':>7}{'H2 %/day':>10}")
    for combo, n1, d1, n2, d2 in sorted(rows, key=lambda r: -r[2]):
        print(f"{(' + '.join(combo) or '(none)'):<92}{n1:>7}{d1:>+10.3f}{n2:>7}{d2:>+10.3f}")
    ok = [r for r in rows if r[1] >= 20]
    best = max(ok, key=lambda r: r[2])
    print(f"\nWALK-FORWARD PICK (best H1 with >= 20 trades): {' + '.join(best[0]) or '(none)'}")
    print(f"   H1 (chosen here): {best[1]} trades, {best[2]:+.3f}%/day   ->   H2 (unseen): {best[3]} trades, {best[4]:+.3f}%/day")
    none = [r for r in rows if not r[0]][0]
    print(f"   no filters:       {none[1]} trades, {none[2]:+.3f}%/day   ->   H2: {none[3]} trades, {none[4]:+.3f}%/day")
    print("\nEach filter alone, H1 -> H2 (does it help in BOTH halves?):")
    for n in names:
        r = [x for x in rows if x[0] == (n,)][0]
        print(f"   {n:<34} H1 {r[2]:+.3f} (vs {none[2]:+.3f})   H2 {r[4]:+.3f} (vs {none[4]:+.3f})   {'helps both' if r[2] > none[2] and r[4] > none[4] else 'mixed/hurts'}")


if __name__ == '__main__':
    main()
