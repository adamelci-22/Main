#!/usr/bin/env python3
"""PULLBACK on inverse funds: does it work when the market is falling and fail when it is rising? Two features known at entry.
    /usr/bin/python3 -I tools/backtest/massive_pb_regime.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_pb_regime.txt
F1 = the underlying's move from the 9:30 open to the entry bar, signed so that positive means the underlying fell (the inverse fund's side).
F2 = the underlying's close the day before against its 20-day mean close, signed the same way (positive = underlying in a downtrend).
Funds: SOXS(SOXX) LABD(XBI) TECS(XLK) UVXY(QQQ) SQQQ(QQQ) TZA(IWM) FAZ(XLF) SRTY(IWM) SDOW(QQQ) SPXU(QQQ) SDS(QQQ) QID(QQQ). Splits: TRAIN 2021-11..2023, VALID 2024-2025, TEST 2026-03..10.
"""
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_live_rules as LR
import pb_final as PBF, pb_inverse as PI
from lab import get_data
UND = {'SOXS': 'SOXX', 'LABD': 'XBI', 'TECS': 'XLK', 'UVXY': 'QQQ', 'SQQQ': 'QQQ', 'TZA': 'IWM', 'FAZ': 'XLF', 'SRTY': 'IWM', 'SDOW': 'QQQ', 'SPXU': 'QQQ', 'SDS': 'QQQ', 'QID': 'QQQ'}
TR, VA, TE = ('2021-11-01', '2023-12-31'), ('2024-01-01', '2025-12-31'), ('2026-03-03', '2026-10-14')
inP = lambda d, P: P[0] <= d <= P[1]
avg = lambda v: f"{st.mean(v):+.3f}% win {100*sum(x > 0 for x in v)/len(v):>3.0f}% n={len(v):>3}" if v else 'n/a'


def main():
    D = get_data(); days = D.days[1:]
    for f in UND: PI.PROXY.setdefault(f, f)
    sig = PBF.run(D, days, [f for f in UND if f in D.bars], oco_gap=True); rows = []
    for x in sig:
        u = UND[x['inst']]; d = x['day']; P = D.bars[u][d]; k = x['k']
        f1 = -(P[k - 1][3] / P[0][0] - 1) * 100
        pri = D.prior(d, 21); pc = D.dhlc[u][pri[-1]][2]; f2 = -(pc / st.mean(D.dhlc[u][q][2] for q in pri[-20:]) - 1) * 100
        rows.append(dict(day=d, pct=x['pct'], f1=f1, f2=f2, inst=x['inst']))
    print(f"{len(rows)} PULLBACK signals, {days[0]}..{days[-1]}\n")
    for name, key in (('F1 underlying move open -> entry (positive = underlying fell)', 'f1'), ('F2 underlying vs its 20-day mean (positive = downtrend)', 'f2')):
        v = sorted(r[key] for r in rows if inP(r['day'], TR)); c1, c2 = v[len(v) // 3], v[2 * len(v) // 3]
        print(f"== {name}; TRAIN tercile cuts {c1:+.2f}, {c2:+.2f} ==")
        for lab, fn in ((f'low  (< {c1:+.2f})', lambda x: x < c1), (f'mid', lambda x: c1 <= x < c2), (f'high (>= {c2:+.2f})', lambda x: x >= c2)):
            print(f"   {lab:<16}" + ' | '.join(f"{n} {avg([r['pct'] for r in rows if inP(r['day'], P) and fn(r[key])])}" for n, P in (('TRAIN', TR), ('VALID', VA), ('TEST', TE))))
        print()
    both = lambda r: r['f1'] >= 0.5 and r['f2'] >= 0
    print("== Both: underlying down at least 0.5% on the day and in a downtrend ==")
    print('   ' + ' | '.join(f"{n} {avg([r['pct'] for r in rows if inP(r['day'], P) and both(r)])}" for n, P in (('TRAIN', TR), ('VALID', VA), ('TEST', TE))))
    print("   others:  " + ' | '.join(f"{n} {avg([r['pct'] for r in rows if inP(r['day'], P) and not both(r)])}" for n, P in (('TRAIN', TR), ('VALID', VA), ('TEST', TE))))


if __name__ == '__main__':
    main()
