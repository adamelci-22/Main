#!/usr/bin/env python3
"""Which proxies are best for FADE in the 2026-03-03..10-14 window (Massive bars), and does that ranking carry any information?
    /usr/bin/python3 -I tools/backtest/massive_proxy_rank.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_proxy_rank.txt
Eleven candidates: the six live proxies and SPY TLT KRE GLD VIXY. Signal-model legs (leverage x proxy, 0.06% cost) for all eleven so they compare like for like;
real-leg results for the live six are in massive_realleg.txt. B = 2026-03-03..10-14. A = 2021-11..2026-02-27.
Rank check: Spearman correlation between a proxy's rank in A and its rank in B. Near zero means B's ranking says nothing about the future.
Split-half check inside B: rank on 2026-03..06, look at 2026-07..10.
"""
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import expand_lists as EX
from lab import get_data
LR = RL.LR
ROWS = {p: RL.FA.ROWS[p] for p in LR.BT.PROXIES}
ROWS.update({'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'KRE': ('DPST', 3, 'KRED', 3), 'GLD': ('UGL', 2, 'GLL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)})
A_END, B0, B1, MID = '2026-02-27', '2026-03-03', '2026-10-14', '2026-06-30'


def spearman(x, y):
    rk = lambda v: [sorted(v).index(a) + 1 for a in v]
    return st.correlation(rk(x), rk(y))


def main():
    D = get_data(); days = D.days[1:]; res = {}
    for p, row in ROWS.items():
        T = EX.fade_trades(D, days, p, row)
        res[p] = dict(A=[t['pct'] for t in T if t['day'] <= A_END], B=[t['pct'] for t in T if B0 <= t['day'] <= B1],
                      B1=[t['pct'] for t in T if B0 <= t['day'] <= MID], B2=[t['pct'] for t in T if MID < t['day'] <= B1])
    f = lambda v: f"{st.mean(v):+.3f}" if v else '  n/a'
    print(f"{'proxy':<6}{'live':>5} | {'B n':>4}{'win%':>6}{'avg %':>8}{'sum %':>8}{'t':>6} | {'B 03-06':>9}{'B 07-10':>9} | {'A n':>4}{'avg %':>8}")
    order = sorted(res, key=lambda p: -st.mean(res[p]['B']))
    for p in order:
        b = res[p]['B']; t = st.mean(b) / (st.pstdev(b) / len(b) ** 0.5) if len(b) > 1 and st.pstdev(b) else 0
        print(f"{p:<6}{'yes' if p in LR.BT.PROXIES else '':>5} | {len(b):>4}{100*sum(x > 0 for x in b)/len(b):>5.0f}%{st.mean(b):>+8.3f}{sum(b):>+8.1f}{t:>6.2f} | {f(res[p]['B1']):>9}{f(res[p]['B2']):>9} | {len(res[p]['A']):>4}{f(res[p]['A']):>8}")
    ps = list(res)
    print(f"\nRank correlation, A against B, all 11 proxies: {spearman([st.mean(res[p]['A']) for p in ps], [st.mean(res[p]['B']) for p in ps]):+.2f}")
    ok = [p for p in ps if res[p]['B1'] and res[p]['B2']]
    print(f"Rank correlation inside B, 03-06 against 07-10: {spearman([st.mean(res[p]['B1']) for p in ok], [st.mean(res[p]['B2']) for p in ok]):+.2f}")
    top = order[:4]; live = list(LR.BT.PROXIES)
    pool = lambda ps_, k: [x for p in ps_ for x in res[p][k]]
    print(f"\nTop four in B ({', '.join(top)}): B avg {st.mean(pool(top,'B')):+.3f} (n={len(pool(top,'B'))}), A avg {st.mean(pool(top,'A')):+.3f}")
    print(f"Live six:                    B avg {st.mean(pool(live,'B')):+.3f} (n={len(pool(live,'B'))}), A avg {st.mean(pool(live,'A')):+.3f}")
    top1 = [p for p in order if res[p]['B1']][:4]
    print(f"Top four on 03-06, judged on 07-10 ({', '.join(top1)}): {st.mean(pool(top1,'B2')):+.3f} (n={len(pool(top1,'B2'))}) against all eleven {st.mean(pool(ps,'B2')):+.3f}")


if __name__ == '__main__':
    main()
