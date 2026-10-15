#!/usr/bin/env python3
"""Failed-retest fade: which exit? Walk-forward on the v3.126 Core Five.
    python3 tools/backtest/fade_exits.py > tools/backtest/results_fade_exits.txt
Entry/stop exactly as retest.RC(fade=True). Exits are measured on the PROXY (target sold at the next 5-min checkpoint).
Targets: R multiples of the stop distance, the box MIDPOINT, the OPPOSITE box edge (a fade's natural destination), or none.
Partial versions sell half at the first target and move the stop to breakeven. Time exits: 15:55, 12:30, 11:30.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, retest as RT, twobar as TB
from lab import get_data

FADE = RT.RC(fade=True)


def trade(D, d, p, tgt, frac, be, tx):
    raw = D.bars[p][d]; s = RT.setup(raw, FADE)
    if not s: return None
    k, side, e_real, stop_real = s
    if k > tx: return None
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry, stop = to_m(e_real), to_m(stop_real)
    if entry <= stop: return None
    r = entry - stop
    Hr, Lr = TB.box(raw)
    if tgt == 'none': T = None
    elif tgt == 'mid': T = to_m((Hr + Lr) / 2)
    elif tgt == 'opp': T = to_m(Lr if side < 0 else Hr)     # fade of an up-break goes short -> opposite edge = box low
    else: T = entry + float(tgt) * r
    if T is not None and T <= entry: T = entry + r          # target already behind entry -> fall back to 1R
    pnl, xbar, why = TB.manage(b, k, entry, stop, T, frac if T is not None else 1.0, be, tx, True, True)
    lev = TB.ROWS[p][2]
    return dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, pct=lev * pnl / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100)


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"Failed-retest fade exits, {days[0]}..{days[-1]}. Current rule = half at 1R + breakeven, hold to 15:55.\n")
    opts = []
    for tgt in ('1', '1.5', '2', '3', 'mid', 'opp', 'none'):
        for frac, be in ((1.0, False), (0.5, True)):
            if tgt == 'none' and frac < 1: continue
            for tx in (77, 35, 23):
                opts.append((tgt, frac, be, tx))
    tn = {77: '15:55', 35: '12:30', 23: '11:30'}
    rows = []
    for tgt, frac, be, tx in opts:
        T = [t for d in days for p in TB.ROWS for t in [trade(D, d, p, tgt, frac, be, tx)] if t]
        a = TB.account(D, days, T); dl = a['daily']; tk = a['taken']
        T1 = [t for t in T if t['day'] in set(H1)]; T2 = [t for t in T if t['day'] in set(H2)]
        d1 = st.mean(TB.account(D, H1, T1)['daily'].values()); d2 = st.mean(TB.account(D, H2, T2)['daily'].values())
        name = (f"{'all out' if frac == 1 else 'half + BE'} at " + {'mid': 'box midpoint', 'opp': 'opposite box edge', 'none': '(no target)'}.get(tgt, f'{tgt}R')
                ) if tgt != 'none' else 'no target, time exit only'
        rows.append((name + f", out {tn[tx]}", len(tk), 100 * sum(x['usd'] > 0 for x in tk) / max(len(tk), 1), st.mean(dl.values()), a['ret'], a['mdd'], d1, d2,
                     st.mean(t['pct'] for t in T)))
    print(f"{'exit':<52}{'trd':>4}{'win%':>6}{'%/day':>8}{'ret%':>8}{'DD':>6}{'H1':>8}{'H2':>8}{'leg avg':>9}")
    for r in sorted(rows, key=lambda r: -r[3]):
        cur = '  <- current' if r[0] == 'half + BE at 1R, out 15:55' else ''
        print(f"{r[0]:<52}{r[1]:>4}{r[2]:>6.0f}{r[3]:>+8.3f}{r[4]:>+8.1f}{r[5]:>6.1f}{r[6]:>+8.3f}{r[7]:>+8.3f}{r[8]:>+9.3f}{cur}")
    best = max(rows, key=lambda r: r[6])
    cur = [r for r in rows if r[0] == 'half + BE at 1R, out 15:55'][0]
    print(f"\nWALK-FORWARD: best exit on H1 = '{best[0]}' ({best[6]:+.3f}) -> H2 {best[7]:+.3f}   | current rule H1 {cur[6]:+.3f} -> H2 {cur[7]:+.3f}")
    print(f"Exits positive in both halves: {sum(1 for r in rows if r[6] > 0 and r[7] > 0)} of {len(rows)}")


if __name__ == '__main__':
    main()
