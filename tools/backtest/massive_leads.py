#!/usr/bin/env python3
"""Leads for a signal that might work: intraday momentum and the close, on the six live proxies, Massive bars, 2021-11..2026-10. Before costs, in bp on the proxy.
    /usr/bin/python3 -I tools/backtest/massive_leads.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz > tools/backtest/results/massive_leads.txt
H1 last-30-minute momentum: sign of (open 9:30 -> 15:30) x return of 15:30 -> 16:00 (leveraged-ETF rebalancing flows push the close in the day's direction).
H2 first-30-minute momentum into the close: sign of (9:30 -> 10:00) x return of 10:00 -> 15:55.
H3 midday-to-close momentum: sign of (9:30 -> 13:30) x return of 13:30 -> 16:00.
H4 the same as H1 but only on days with |open -> 15:30| above 1%.
Each row: mean bp per trade, t-stat, share of days positive, by year. Costs on a 3x leg are about 6-10 bp round trip on the leg = 2-3 bp on the proxy.
"""
import collections, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_live_rules as LR
from lab import get_data


def row(v):
    if len(v) < 5: return 'n/a'
    sd = st.pstdev(v); t = st.mean(v) / (sd / len(v) ** 0.5) if sd else 0
    return f"{st.mean(v):+6.1f} bp t {t:+5.2f} pos {100*sum(x > 0 for x in v)/len(v):>3.0f}% n={len(v)}"


def main():
    D = get_data(); days = D.days[1:]; P6 = LR.BT.PROXIES
    H = {k: collections.defaultdict(list) for k in ('H1', 'H2', 'H3', 'H4')}
    for p in P6:
        for d in days:
            b = D.bars[p][d]
            if len(b) < 78: continue
            o = b[0][0]; s1 = b[71][3] / o - 1; s2 = b[5][3] / o - 1; s3 = b[47][3] / o - 1
            sg = lambda x: 1 if x > 0 else -1
            y = d[:4]
            r1 = (b[77][3] / b[72][0] - 1) * 1e4 * sg(s1); H['H1'][y].append(r1)
            H['H2'][y].append((b[77][3] / b[6][0] - 1) * 1e4 * sg(s2))
            H['H3'][y].append((b[77][3] / b[48][0] - 1) * 1e4 * sg(s3))
            if abs(s1) > 0.01: H['H4'][y].append(r1)
    names = {'H1': 'H1 last 30 min follows the day so far', 'H2': 'H2 first 30 min direction, held 10:00 -> 15:55', 'H3': 'H3 9:30-13:30 direction, held 13:30 -> 16:00', 'H4': 'H4 H1 on days that moved more than 1%'}
    for h in H:
        print(f"== {names[h]} ==")
        for y in sorted(H[h]): print(f"   {y}  {row(H[h][y])}")
        al = [x for y in H[h] for x in H[h][y]]; print(f"   ALL   {row(al)}\n")
    print("== H1 by proxy, all years ==")
    for p in P6:
        v = []
        for d in days:
            b = D.bars[p][d]
            if len(b) < 78: continue
            s1 = b[71][3] / b[0][0] - 1; v.append((b[77][3] / b[72][0] - 1) * 1e4 * (1 if s1 > 0 else -1))
        print(f"   {p:<5}{row(v)}")


if __name__ == '__main__':
    main()
