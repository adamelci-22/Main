#!/usr/bin/env python3
"""First-pullback buy on the "Leveraged Sector & Crypto Day Trading Matrix" rows (plus the Core Five for comparison).
    python3 tools/backtest/matrix.py > tools/backtest/results_matrix.txt
Same setup, fills, costs and account rules as pullback.py. Config = pullback.py's walk-forward pick
(stop room >= 0.75%, entries to 13:00, exit 15:55, limit entry); the no-filter version is shown for reference.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P
from lab import get_data

MATRIX = {   # row: (proxy, [(leg, direction), ...])
    'Bitcoin': ('IBIT', [('BITX', 1), ('BTCL', 1), ('SBIT', -1), ('BTCZ', -1)]),
    'Technology': ('XLK', [('TECL', 1), ('TECS', -1)]),
    'Semiconductors': ('SOXX', [('SOXL', 1), ('SOXS', -1)]),
    'DRAM / Memory': ('DRAM', [('RAM', 1), ('DRAL', 1), ('RAMZ', -1)]),
    'Energy': ('XLE', [('ERX', 1), ('ERY', -1)]),
    'Oil & Gas E&P': ('XOP', [('GUSH', 1), ('DRIP', -1)]),
    'Gold Miners': ('GDX', [('NUGT', 1), ('DUST', -1)]),
    'Financials': ('XLF', [('FAS', 1), ('FAZ', -1)]),
    'South Korea': ('EWY', [('KORU', 1), ('KRWX', 1)]),
}
CORE5 = {'Nasdaq (core)': ('QQQ', [('TQQQ', 1), ('SQQQ', -1)]), 'S&P 500 (core)': ('SPY', [('UPRO', 1), ('SPXU', -1)]),
         'Small caps (core)': ('IWM', [('TNA', 1), ('TZA', -1)]), 'Treasuries (core)': ('TLT', [('TMF', 1), ('TMV', -1)])}
THIN = 2000   # median 5-min bar volume below this = thin; fills in the backtest are optimistic


def legs_of(rows):
    return {leg: (px, sd) for _, (px, legs) in rows.items() for leg, sd in legs}


def safe_rvol(D, proxy, d, k):
    try:
        pri = D.prior(d, 20); base = st.mean(D.cum[proxy][x][k] for x in pri)
        return D.cum[proxy][d][k] / base if base else 0.0
    except Exception:
        return 0.0


def run(D, days, legs, room, last_k=41, exit_k=77, em='limit'):
    m.LEGS = legs
    keep = {l: v for l, v in legs.items()}
    out = []
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]
        sub = {l: v for l, v in keep.items() if d in D.bars.get(l, {}) and pd_ in D.bars.get(l, {})}
        if not sub: continue
        m.LEGS = sub
        out += P.signals(D, [d], room, last_k, exit_k, em)
    m.LEGS = legs
    return out


def med_vol(D, leg, days):
    v = [st.median([b[4] for b in D.bars[leg][d]]) for d in days if d in D.bars.get(leg, {})]
    return st.median(v) if v else 0


def main():
    D = get_data(); m.rvol = safe_rvol
    days = D.days[25:]; h = len(days) // 2; H1, H2 = set(days[:h]), set(days[h:])
    print(f"First-pullback buy on the matrix rows, {days[0]}..{days[-1]} ({len(days)} days). Goal +0.400%/day. Config: room>=0.75%, entries to 13:00, hold to 15:55, limit entry.")
    print("KORS.L (Europe-listed) not available. RAM/DRAL from 2026-06-25, RAMZ from 2026-07-28, KRWX from 2026-06-03, DRAM proxy from 2026-04-02.\n")
    print("== Per leg ==")
    print(f"{'row':<20}{'leg':<6}{'dir':>4}{'med vol':>9}{'days':>6} | {'all sig':>7}{'avg%':>8} | {'room>=.75':>9}{'win%':>6}{'avg%':>8}{'H1 avg':>8}{'H2 avg':>8}")
    allrows = dict(MATRIX, **CORE5)
    for row, (px, legs) in allrows.items():
        for leg, sd in legs:
            nd = sum(1 for d in days if d in D.bars.get(leg, {}))
            if not nd: print(f"{row:<20}{leg:<6} no data"); continue
            s0 = run(D, days, {leg: (px, sd)}, 0.0); s = run(D, days, {leg: (px, sd)}, 0.75)
            a0 = st.mean(x['pct'] for x in s0) if s0 else 0
            f = lambda v: st.mean(x['pct'] for x in v) if v else float('nan')
            mv = med_vol(D, leg, days)
            print(f"{row:<20}{leg:<6}{sd:>+4}{int(mv):>9}{nd:>6} | {len(s0):>7}{a0:>+8.3f} | {len(s):>9}{100*sum(x['pnl']>0 for x in s)/max(len(s),1):>6.0f}{f(s):>+8.3f}"
                  f"{f([x for x in s if x['day'] in H1]):>+8.3f}{f([x for x in s if x['day'] in H2]):>+8.3f}{'  THIN' if mv < THIN else ''}")
    print("\n== Per row, account sim ($2,000, 3% risk cap, one position at a time, max 3/day) ==")
    print(f"{'row':<20}{'trades':>7}{'win%':>6}{'avg/day':>9}{'ret%':>8}{'maxDD':>7}{'H1 %/day':>10}{'H2 %/day':>10}")
    res = {}
    for row, (px, legs) in allrows.items():
        L = {l: (px, sd) for l, sd in legs}
        s = run(D, days, L, 0.75); a = P.account(s, D, days); res[row] = (s, a)
        T = a['taken']; dl = a['daily']
        print(f"{row:<20}{len(T):>7}{100*sum(x['usd']>0 for x in T)/max(len(T),1):>6.0f}{st.mean(dl.values()):>+9.3f}{a['ret']:>+8.1f}{a['mdd']:>7.1f}"
              f"{st.mean(dl[d] for d in days[:h]):>+10.3f}{st.mean(dl[d] for d in days[h:]):>+10.3f}")
    print("\n== Combined universes (account sim) ==")
    liquid = {l: v for l, v in legs_of(allrows).items() if med_vol(D, l, days) >= THIN}
    combos = {'All matrix rows': legs_of(MATRIX), 'All matrix + Core Five rest': legs_of(allrows),
              'Liquid legs only (median bar vol >= 2000)': liquid}
    for name, L in combos.items():
        for room in (0.75, 0.0):
            s = run(D, days, L, room); a = P.account(s, D, days); T = a['taken']; dl = a['daily']
            byrow = collections.Counter()
            for x in T: byrow[x['inst']] += x['acct_pct']
            print(f"{name:<44} room>={room:<4} trades {len(T):3d} ({len(T)/len(days):.2f}/day) win {100*sum(x['usd']>0 for x in T)/max(len(T),1):3.0f}%  "
                  f"avg/day {st.mean(dl.values()):+.3f}%  ret {a['ret']:+.1f}%  maxDD {a['mdd']:.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
            if room == 0.75: print('      contribution by leg (% of account):', ', '.join(f"{k} {v:+.1f}" for k, v in byrow.most_common()))


if __name__ == '__main__':
    main()
