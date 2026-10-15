#!/usr/bin/env python3
"""Inverse-list pullback: SELL ALL at the morning high, with a minimum-target rule. Both halves + walk-forward.
    python3 tools/backtest/pb_sellall.py > tools/backtest/results_pb_sellall.txt
Minimum target: skip a setup unless (morning high - entry) >= X x (entry - stop) AND >= 0.25% of the entry (Robinhood OCO minimum).
A skipped setup does not end the ticker's day: later setups on that ticker are still checked.
Exit: one OCO for the whole position (take profit at the morning high, stop 2.5c under the pullback low); sell what's left at 13:30
(15:55 shown too). Current 60/40 exit shown for reference. H1 = 2026-04-07..07-10 (SPY +15%), H2 = 07-13..10-14 (SPY +2%).
"""
import os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, pb_inverse as PI
from lab import get_data


def scan(b, e9, e20, min_rr, min_room=0.75, last_k=41):
    bh = max(x[1] for x in b[:3])
    for j in range(8, last_k):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre)); stop = low - 0.025
            lim = b[j][3]
            if b[j + 1][2] > lim: continue
            entry = min(b[j + 1][0], lim)
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < min_room: continue
            if min_rr is not None and ((hod - entry) < min_rr * (entry - stop) or (hod - entry) / entry * 100 < 0.25): continue
            return dict(k=j + 1, entry=entry, stop=stop, hod=hod, sig=j)
    return None


def setups(D, days, leg, min_rr):
    out = []
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]
        if d not in D.bars.get(leg, {}) or pd_ not in D.bars.get(leg, {}): continue
        b = D.bars[leg][d]; pb = D.bars[leg][pd_]
        ser = [x[3] for x in pb] + [x[3] for x in b]; e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
        s = scan(b, e9, e20, min_rr)
        if s: s.update(day=d, inst=leg, b=b, e20=e20); out.append(s)
    return out


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    m.rvol = lambda D_, p, d, k: (lambda pri: (D.cum[p][d][k] / st.mean(D.cum[p][x][k] for x in pri)) if p in D.cum and all(x in D.cum[p] for x in pri) else 0.0)(D.prior(d, 20))
    print(f"Inverse-list pullback, sell all at the morning high + minimum target, {days[0]}..{days[-1]}.\n")
    for lname, legs in (('A: SOXS SQQQ TZA TECS BTCZ', PI.A), ('B: A + LABD + UVXY', PI.B)):
        m.LEGS = {l: (PI.PROXY[l], 1) for l in legs}
        print(f"== List {lname} ==")
        print(f"{'min target':<28}{'exit':<26}{'trd':>4}{'win%':>6}{'avg win':>8}{'avg loss':>9}{'%/day':>8}{'ret%':>7}{'DD':>6}{'H1':>8}{'H2':>8}")
        rows = []
        for rr in (None, 0.5, 0.75, 1.0, 1.25):
            S = [s for l in legs for s in setups(D, days, l, rr)]
            for frac, runner, last, ex in ((1.0, 'be', 47, 'sell all, by 13:30'), (1.0, 'be', 77, 'sell all, by 15:55'), (0.6, 'ema20', 47, '60/40 (current), by 13:30')):
                sig = [t for s in S for t in [PI.manage(s, frac, runner, last)] if t]
                a = P.account(sig, D, days); tk = a['taken']
                d1 = st.mean(P.account([x for x in sig if x['day'] in set(H1)], D, H1)['daily'].values())
                d2 = st.mean(P.account([x for x in sig if x['day'] in set(H2)], D, H2)['daily'].values())
                wins = [x['pct'] for x in tk if x['usd'] > 0]; losses = [x['pct'] for x in tk if x['usd'] <= 0]
                lab = 'none (current)' if rr is None else f">= {rr}x stop distance"
                rows.append((rr, ex, d1, d2))
                print(f"{lab:<28}{ex:<26}{len(tk):>4}{100*len(wins)/max(len(tk),1):>6.0f}{(st.mean(wins) if wins else 0):>+8.2f}{(st.mean(losses) if losses else 0):>+9.2f}"
                      f"{st.mean(a['daily'].values()):>+8.3f}{a['ret']:>+7.1f}{a['mdd']:>6.1f}{d1:>+8.3f}{d2:>+8.3f}")
        sa = [r for r in rows if r[1] == 'sell all, by 13:30']
        best = max(sa, key=lambda r: r[2])
        print(f"   WALK-FORWARD (sell all, 13:30): best minimum on H1 = {best[0]} (H1 {best[2]:+.3f}) -> H2 {best[3]:+.3f}; no minimum H2 {sa[0][3]:+.3f}\n")


if __name__ == '__main__':
    main()
