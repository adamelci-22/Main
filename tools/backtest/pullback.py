#!/usr/bin/env python3
"""First-pullback buy (Intraday Strategy Manual system 2), built out for the Core Five 3x legs and tested properly.
    python3 tools/backtest/pullback.py > tools/backtest/results_pullback.txt
Setup (per leg, long only; inverse legs cover the short side):
  morning breakout above the 15-min high on a bar with volume > 1.5x the prior 6 bars; then EMA9 > EMA20 and price above EMA9;
  2-5 bar pullback (red or lower-high bars) whose low reaches the EMA9/EMA20 zone; trigger = a bar closing above the prior bar's high.
  stop = pullback low - $0.025; 60% off at the prior high of day; rest trails on a close below EMA20; else out at the time exit.
Parameters searched: minimum stop room (% of price), last entry time, time exit (12:30 or 15:55), entry order (market or limit).
Limit entry: limit at the trigger bar's close, filled only if the next bar trades at/below it, at min(open, limit), cost 0.01% instead of 0.03%.
Account: $2,000 start, 3% of account at risk per trade, one position at a time, max 3 entries/day, ties broken by proxy RVOL.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m
from lab import get_data

MKT, LIM = 0.0003, 0.0001


def scan(b, e9, e20, min_room, last_k, entry_mode):
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
            hod = max(b[i][1] for i in range(0, pre))
            stop = low - 0.025
            if entry_mode == 'limit':
                lim = b[j][3]
                if b[j + 1][2] > lim: continue          # not filled; keep looking for a later trigger
                entry = min(b[j + 1][0], lim)
            else:
                entry = b[j + 1][0]
            if hod <= entry or entry <= stop: continue
            if (entry - stop) / entry * 100 < min_room: continue
            return dict(k=j + 1, entry=entry, stop=stop, T=hod, frac=0.6, post='ema20', ema=e20,
                        sig_bar=j, pb_len=n, hod=hod)
    return None


def signals(D, days, min_room, last_k, exit_k, entry_mode):
    out = []
    m.LAST = exit_k
    try:
        for d in days:
            i = D.days.index(d); pd_ = D.days[i - 1]
            for leg in m.LEGS:
                b = D.bars[leg][d]; pb = D.bars[leg][pd_]
                ser = [x[3] for x in pb] + [x[3] for x in b]
                e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
                sp = scan(b, e9, e20, min_room, last_k, entry_mode)
                if not sp: continue
                r = m.manage(b, sp, e20, MKT, lambda p: p)
                if not r: continue
                pnl, risk, xbar, why = r
                if entry_mode == 'limit': pnl += (MKT - LIM) * sp['entry']
                out.append(dict(day=d, inst=leg, k=sp['k'], pnl=pnl, risk=risk, entry=sp['entry'], why=why, xbar=xbar,
                                pct=pnl / sp['entry'] * 100, R=pnl / risk, room=risk / sp['entry'] * 100, sp=sp))
    finally:
        m.LAST = 77
    return out


def account(sig, D, days, risk=0.03, max_entries=3, start=2000.0):
    by = {}
    for x in sig: by.setdefault(x['day'], []).append(x)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []
    for d in days:
        e0 = eq; cands = sorted(by.get(d, []), key=lambda x: x['k']); free = 0; n = 0
        while n < max_entries:
            avail = [x for x in cands if x['k'] >= free]
            if not avail: break
            k0 = min(x['k'] for x in avail); same = [x for x in avail if x['k'] == k0]
            pick = max(same, key=lambda x: m.rvol(D, m.LEGS[x['inst']][0], d, x['k']))
            sh = math.floor(min(eq / pick['entry'], eq * risk / pick['risk']))
            if sh >= 1:
                pnl = sh * pick['pnl']; eq += pnl; n += 1
                taken.append(dict(pick, usd=pnl, acct_pct=pnl / (eq - pnl) * 100, sh=sh))
                peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
            free = pick['xbar'] + 1; cands.remove(pick)
        daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken)


def line(tag, sig, acc, days_sub=None):
    dl = list(acc['daily'].values()) if days_sub is None else [acc['daily'][d] for d in days_sub]
    a = [x['pct'] for x in sig]
    t = st.mean(a) / (st.pstdev(a) / math.sqrt(len(a))) if len(a) > 2 and st.pstdev(a) else 0
    tk = acc['taken']
    return (f"{tag:<44} sig={len(sig):4d} avg/sig={st.mean(a) if a else 0:+.3f}% t={t:+.1f} | taken={len(tk):3d} "
            f"win={100 * sum(x['usd'] > 0 for x in tk) / max(len(tk), 1):4.1f}% avg/day={st.mean(dl):+.3f}% ret={acc['ret']:+.1f}% maxDD={acc['mdd']:.1f}%")


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"First-pullback buy, Core Five 3x legs, {days[0]}..{days[-1]} ({len(days)} days). Goal: +0.400%/day.")
    print(f"Walk-forward: choose on H1 {H1[0]}..{H1[-1]}, judge on H2 {H2[0]}..{H2[-1]}.\n")
    grid = [(r, lk, xk, em) for r in (0.0, 0.5, 0.75, 1.0) for lk in (17, 23, 29, 41) for xk in (36, 77) for em in ('market', 'limit')]
    tname = {17: '11:00', 23: '11:30', 29: '12:00', 41: '13:00', 36: '12:30', 77: '15:55'}
    rows = []
    for r, lk, xk, em in grid:
        s1 = signals(D, H1, r, lk, xk, em); s2 = signals(D, H2, r, lk, xk, em)
        a1 = account(s1, D, H1); a2 = account(s2, D, H2)
        rows.append(((r, lk, xk, em), s1, s2, a1, a2))
    print("Full grid (avg %/day in each half, account sim):")
    print(f"{'room>=':>7}{'last entry':>11}{'exit':>7}{'entry':>8}{'trd H1':>8}{'H1 %/day':>10}{'trd H2':>8}{'H2 %/day':>10}")
    for (r, lk, xk, em), s1, s2, a1, a2 in rows:
        print(f"{r:>7.2f}{tname[lk]:>11}{tname[xk]:>7}{em:>8}{len(a1['taken']):>8}{st.mean(a1['daily'].values()):>+10.3f}"
              f"{len(a2['taken']):>8}{st.mean(a2['daily'].values()):>+10.3f}")
    ok = [x for x in rows if len(x[3]['taken']) >= 20]
    best = max(ok, key=lambda x: st.mean(x[3]['daily'].values()))
    (r, lk, xk, em), s1, s2, a1, a2 = best
    print(f"\nWALK-FORWARD PICK (best H1 %/day with >=20 trades): room>={r}%, entries to {tname[lk]}, exit {tname[xk]}, {em} entry")
    print('  H1 (in-sample) ', line('', s1, a1)); print('  H2 (out-sample)', line('', s2, a2))
    print("\nPRE-REGISTERED (stated before testing): room>=0.75%, entries to 11:00, exit 15:55, limit entry")
    s = signals(D, days, 0.75, 17, 77, 'limit'); a = account(s, D, days)
    print('  full period    ', line('', s, a))
    return D, days


if __name__ == '__main__':
    main()
