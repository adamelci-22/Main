#!/usr/bin/env python3
"""First-pullback buy on the v3.125 Core Five (QQQ, SOXX, IWM, XLK, IBIT -> 12 legs), with a breakdown of which trend types fail.
    python3 tools/backtest/core5_pullback.py > tools/backtest/results_core5_pullback.txt
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, matrix as MX
from lab import get_data

ROWS = {'Nasdaq': ('QQQ', [('TQQQ', 1), ('SQQQ', -1)]), 'Semis': ('SOXX', [('SOXL', 1), ('SOXS', -1)]),
        'Small caps': ('IWM', [('TNA', 1), ('TZA', -1)]), 'Technology': ('XLK', [('TECL', 1), ('TECS', -1)]),
        'Bitcoin': ('IBIT', [('BITX', 1), ('BTCL', 1), ('SBIT', -1), ('BTCZ', -1)])}
LEGS = MX.legs_of(ROWS)
ROW_OF = {l: r for r, (_, ls) in ROWS.items() for l, _ in ls}


def features(D, x):
    leg = x['inst']; px, sd = LEGS[leg]; d = x['day']; i = D.days.index(d); pd_ = D.days[i - 1]
    pb = D.bars[px][d]; j = x['sp']['sig_bar']
    move = sd * (pb[j][3] / pb[0][0] - 1) * 100                    # proxy move since open, in the trade's direction
    gap = sd * (pb[0][0] / D.bars[px][pd_][77][3] - 1) * 100       # overnight gap, in the trade's direction
    b = D.bars[leg][d]; bh = max(c[1] for c in b[:3]); o = b[0][0]
    brk = next((k for k in range(3, j) if b[k][3] > bh), j)
    hod = x['sp']['hod']; low = x['sp']['entry'] - x['risk'] + 0.025 * 0 if False else min(c[2] for c in b[j - x['sp']['pb_len']:j])
    depth = (hod - low) / (hod - o) * 100 if hod > o else 100.0     # % of the up-move from the open given back in the pullback
    seg = b[x['k']:x['xbar'] + 1]
    mae = (min(c[2] for c in seg) / x['entry'] - 1) * 100
    mfe = (max(c[1] for c in seg) / x['entry'] - 1) * 100
    return dict(move=move, gap=gap, brk=brk, depth=depth, mae=mae, mfe=mfe)


def bucket_table(title, sig, key, order=None):
    g = collections.defaultdict(list)
    for x in sig: g[key(x)].append(x)
    print(f"\n-- {title}")
    print(f"   {'type':<34}{'n':>4}{'share':>7}{'fail%':>7}{'avg%':>8}{'avg dip after entry':>21}{'worst dip':>11}{'acct$/sig':>10}")
    for k in (order or sorted(g)):
        v = g.get(k)
        if not v: continue
        f = 100 * sum(1 for x in v if x['pnl'] <= 0) / len(v)
        print(f"   {k:<34}{len(v):>4}{100*len(v)/len(sig):>6.0f}%{f:>7.0f}{st.mean(x['pct'] for x in v):>+8.3f}{st.mean(x['f']['mae'] for x in v):>+20.2f}%{min(x['f']['mae'] for x in v):>+10.2f}%"
              f"{st.mean(x['pct'] for x in v) * 20:>+10.2f}")


def main():
    D = get_data(); m.rvol = MX.safe_rvol
    days = D.days[25:]; h = len(days) // 2
    print(f"First-pullback buy on the Core Five v3.125 (QQQ, SOXX, IWM, XLK, IBIT; 12 legs), {days[0]}..{days[-1]} ({len(days)} days).")
    print("Rules as pullback.py walk-forward pick: stop room >= 0.75%, entries to 13:00, hold to 15:55, limit entry; 3% risk cap, one position at a time, max 3/day, $2,000.\n")
    for room in (0.75, 0.0):
        s = MX.run(D, days, LEGS, room); a = P.account(s, D, days); T = a['taken']; dl = a['daily']
        print(f"room>={room}: signals {len(s)} avg/signal {st.mean(x['pct'] for x in s):+.3f}% | taken {len(T)} ({len(T)/len(days):.2f}/day) win {100*sum(x['usd']>0 for x in T)/len(T):.0f}% "
              f"avg/day {st.mean(dl.values()):+.3f}% ret {a['ret']:+.1f}% maxDD {a['mdd']:.1f}% | H1 {st.mean(dl[d] for d in days[:h]):+.3f}%/day H2 {st.mean(dl[d] for d in days[h:]):+.3f}%/day")
        if room == 0.75:
            c = collections.defaultdict(float); n = collections.Counter()
            for x in T: c[ROW_OF[x['inst']]] += x['acct_pct']; n[ROW_OF[x['inst']]] += 1
            print('   by row (% of account, trades):', ', '.join(f"{r} {c[r]:+.1f} ({n[r]})" for r in ROWS))
            mo = collections.defaultdict(float)
            for x in T: mo[x['day'][:7]] += x['acct_pct']
            print('   by month:', ', '.join(f"{k} {v:+.1f}" for k, v in sorted(mo.items())))
    # trend anatomy on ALL signals (no room filter) for sample size, then the traded set
    for room, label in ((0.0, 'ALL pullback signals (no room filter) - largest sample'), (0.75, 'Signals the system actually takes (room >= 0.75%)')):
        sig = MX.run(D, days, LEGS, room)
        for x in sig: x['f'] = features(D, x)
        print(f"\n================ TREND ANATOMY: {label}, n={len(sig)} ================")
        print("   fail% = share that lost money; avg dip after entry = average worst point after entry (MAE); acct$/sig = avg % x 20, rough $ per $2,000 account")
        bucket_table('Market direction of the trend', sig, lambda x: 'up-trend (bull leg)' if LEGS[x['inst']][1] > 0 else 'down-trend (inverse leg)')
        bucket_table('Trend strength: proxy move since open, in trade direction', sig,
                     lambda x: 'a weak  (< +0.5%)' if x['f']['move'] < 0.5 else 'b medium (+0.5..1.5%)' if x['f']['move'] < 1.5 else 'c strong (> +1.5%)')
        bucket_table('Gap type', sig, lambda x: 'gap-and-go (gap > +0.3% same way)' if x['f']['gap'] > 0.3 else
                     'reversal (gapped the other way)' if x['f']['gap'] < -0.3 else 'no real gap (+/-0.3%)')
        bucket_table('When the breakout happened', sig, lambda x: 'a 9:45-10:00' if x['f']['brk'] < 6 else 'b 10:00-10:30' if x['f']['brk'] < 12 else 'c after 10:30')
        bucket_table('Pullback depth (% of morning move given back)', sig,
                     lambda x: 'a shallow (< 38%)' if x['f']['depth'] < 38 else 'b normal (38-62%)' if x['f']['depth'] < 62 else 'c deep (> 62%)')
        bucket_table('Row', sig, lambda x: ROW_OF[x['inst']])
        bucket_table('Leg', sig, lambda x: x['inst'])
        worst = sorted(sig, key=lambda x: x['f']['mae'])[:8]
        print("\n   Worst dips after entry:")
        for x in worst:
            print(f"     {x['day']} {x['inst']:<5} dip {x['f']['mae']:+.2f}%  result {x['pct']:+.2f}%  exit {x['why']:<6} trend {x['f']['move']:+.2f}%  gap {x['f']['gap']:+.2f}%  depth {x['f']['depth']:.0f}%")


if __name__ == '__main__':
    main()
