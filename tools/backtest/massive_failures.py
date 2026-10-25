#!/usr/bin/env python3
"""What kinds of FADE failure are there, and what is different about 2026-03..10? Real-leg FADE trades (massive_realleg.real_trade), Massive 5-minute bars.
    /usr/bin/python3 -I tools/backtest/massive_failures.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_failures.txt
A. Intraday behaviour by quarter: does the first 30 minutes reverse or continue? (correlation of the 9:30-10:00 return with the 10:00-13:30 return; mean drift)
B. Failure types for FADE trades.
C. Features known at entry against results, three periods: TRAIN 2021-11..2023-12, VALID 2024-2025, TEST 2026-03..10.
D. One walk-forward filter: chosen on TRAIN only, shown on VALID and TEST.
E. How unusual is 2026-03..10? t-test, share of other 157-day windows that do as well, and the result without the two best months.
F. A rolling-edge gate: take a signal only while the previous N signals averaged above zero (no look-ahead). FADE and PULLBACK.
"""
import collections, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import manual as m, twobar as TB
from lab import get_data
LR = RL.LR; PROXIES = LR.BT.PROXIES
TR, VA, TE = ('2021-11-01', '2023-12-31'), ('2024-01-01', '2025-12-31'), ('2026-03-03', '2026-10-14')
inP = lambda d, P: P[0] <= d <= P[1]


def avg(v): return f"{st.mean(v):+.3f}" if v else '   n/a'


def main():
    D = get_data(); days = D.days[1:]; rows = {p: RL.FA.ROWS[p] for p in PROXIES}
    trades = [t for p in PROXIES for d in days for t in [RL.real_trade(D, d, p, rows[p])] if t]
    print(f"{len(trades)} real-leg FADE trades, {days[0]}..{days[-1]}\n")
    print("== A. Intraday behaviour by quarter (six live proxies pooled) ==")
    print(f"{'quarter':<9}{'days':>5}{'corr 1st30m vs 10:00-13:30':>28}{'mean 10:00-13:30 ret bp':>25}{'mean |1st30m| bp':>18}{'trend-day share %':>19}")
    byq = collections.defaultdict(lambda: ([], [], [], []))
    for p in PROXIES:
        for d in days:
            b = D.bars[p][d]; r1 = (b[5][3] / b[0][0] - 1) * 1e4; r2 = (b[47][3] / b[6][0] - 1) * 1e4
            H = max(x[1] for x in b); L = min(x[2] for x in b); trend = abs(b[-1][3] - b[0][0]) / (H - L) > 0.6 if H > L else False
            q = d[:4] + 'Q' + str((int(d[5:7]) - 1) // 3 + 1); x = byq[q]; x[0].append(r1); x[1].append(r2); x[2].append(abs(r1)); x[3].append(trend)
    for q in sorted(byq):
        a, b_, c, t = byq[q]
        print(f"{q:<9}{len(a)//6:>5}{st.correlation(a, b_):>28.3f}{st.mean(b_):>25.1f}{st.mean(c):>18.1f}{100*sum(t)/len(t):>19.0f}")
    print("\n   monthly FADE result (real legs, leg % per trade):")
    mo = collections.defaultdict(list)
    for t in trades: mo[t['day'][:7]].append(t['pct'])
    print('   ' + ' '.join(f"{k[2:]}:{st.mean(v):+.2f}({len(v)})" for k, v in sorted(mo.items())))
    print("\n== B. Failure types (real legs) ==")
    print(f"{'type':<62}{'before 2026-03':>16}{'2026-03..10':>14}")
    def cls(t):
        d, k = t['day'], t['k']; L = D.bars[t['leg']][d]
        if t['why'] == 'stop':
            n = t['xbar'] - k
            if n <= 1: return '1 stopped within 1 bar of entry (retest did not hold)'
            end = L[47][3]
            if end > t['F']: return '3 stopped, but the leg closed above entry at 13:30 (shaken out)'
            return '2 stopped later and stayed lower (real reversal failed)'
        if t['why'] == 'time' and not t['hit']: return '4 never hit stop or 2R; sold at 13:30' + (' at a loss' if t['pct'] < 0 else ' at a gain')
        if t['hit']: return '5 reached 2R (win; runner stopped or sold)'
        return '6 other'
    for name in sorted({cls(t) for t in trades}):
        a = [t for t in trades if t['day'] <= '2026-02-27' and cls(t) == name]; b = [t for t in trades if TE[0] <= t['day'] <= TE[1] and cls(t) == name]
        na = sum(1 for t in trades if t['day'] <= '2026-02-27'); nb = sum(1 for t in trades if TE[0] <= t['day'] <= TE[1])
        print(f"{name[2:]:<62}{100*len(a)/na:>10.0f}% {avg([t['pct'] for t in a]):>5}{100*len(b)/nb:>8.0f}% {avg([t['pct'] for t in b]):>5}")
    # ---- features
    setups = collections.defaultdict(list)
    for t in trades: setups[t['day']].append(t['side'])
    feats = []
    for t in trades:
        d, p, k = t['day'], t['proxy'], t['k']; P = D.bars[p][d]; i = D.days.index(d); pdy = D.days[i - 1]
        H, L = TB.box(P); bj = next(j for j in range(6, 9) if P[j][3] > H or P[j][3] < L); bside = 1 if P[bj][3] > H else -1
        adr = st.mean((D.dhlc[p][x][0] - D.dhlc[p][x][1]) / D.dhlc[p][x][2] for x in D.prior(d, 20))
        pc = D.dhlc[p][pdy][2]; gap = (P[0][0] / pc - 1)
        tr10 = pc / st.mean(D.dhlc[p][x][2] for x in D.prior(d, 11)[:10]) - 1
        feats.append(dict(t, bside=bside, bj=bj, box=(H - L) / P[0][0] / adr, gapb=gap * bside * 100, aligned=t['side'] * tr10 * 100,
                          rp_adr=(t['risk'] / RL.FA.ROWS[p][1]) / 100 / adr, breadth=sum(1 for s in setups[d] if s == t['side']) - 1, kk=k,
                          atr=m.atr(P, k - 1) / P[k][0] / adr, side_leg='bull' if t['side'] > 0 else 'inverse'))
    print("\n== C. Features known at entry (avg leg % per trade; n in brackets). Cut points are TRAIN terciles. ==")
    def table(name, key, cuts=None, cats=None):
        if cats is None:
            v = sorted(f[key] for f in feats if inP(f['day'], TR)); c1, c2 = v[len(v) // 3], v[2 * len(v) // 3]
            cats = [(f'low (<{c1:.2f})', lambda x: x < c1), (f'mid ({c1:.2f}..{c2:.2f})', lambda x: c1 <= x < c2), (f'high (>={c2:.2f})', lambda x: x >= c2)]
        print(f"  {name}")
        for lab, fn in cats:
            out = []
            for P in (TR, VA, TE):
                v = [f['pct'] for f in feats if inP(f['day'], P) and fn(f[key])]; out.append(f"{avg(v)} ({len(v):>3}) win {100*sum(x > 0 for x in v)/len(v) if v else 0:>3.0f}%")
            print(f"     {lab:<24}TRAIN {out[0]:<22} VALID {out[1]:<22} TEST {out[2]}")
    table('side of the leg bought', 'side_leg', cats=[('bull leg', lambda x: x == 'bull'), ('inverse leg', lambda x: x == 'inverse')])
    table('break bar (6=10:00, 7=10:05, 8=10:10)', 'bj', cats=[(f'bar {j}', lambda x, j=j: x == j) for j in (6, 7, 8)])
    table('entry bar index (k)', 'kk')
    table('opening box width / 20-day average daily range', 'box')
    table('gap in the direction of the breakout (% of prior close)', 'gapb')
    table('fade direction aligned with the 10-day trend (%)', 'aligned')
    table('stop distance / 20-day average daily range', 'rp_adr')
    table('other proxies with the same-direction fade the same day', 'breadth', cats=[('0 others', lambda x: x == 0), ('1 other', lambda x: x == 1), ('2+ others', lambda x: x >= 2)])
    table('5-minute ATR / 20-day average daily range', 'atr')
    print("\n== D. Walk-forward: the single best split above, chosen on TRAIN only ==")
    best = None
    for key in ('box', 'gapb', 'aligned', 'rp_adr', 'atr', 'kk'):
        v = sorted(f[key] for f in feats if inP(f['day'], TR)); c1, c2 = v[len(v) // 3], v[2 * len(v) // 3]
        for lab, fn in ((f'{key} < {c1:.3f}', lambda x, c=c1: x < c), (f'{key} >= {c2:.3f}', lambda x, c=c2: x >= c), (f'{key} < {c2:.3f}', lambda x, c=c2: x < c), (f'{key} >= {c1:.3f}', lambda x, c=c1: x >= c)):
            tv = [f['pct'] for f in feats if inP(f['day'], TR) and fn(f[key])]
            if len(tv) > 100 and (best is None or st.mean(tv) > best[0]): best = (st.mean(tv), lab, key, fn)
    _, lab, key, fn = best
    print(f"   chosen on TRAIN: keep trades with {lab}")
    for nm, P in (('TRAIN', TR), ('VALID', VA), ('TEST', TE)):
        allv = [f['pct'] for f in feats if inP(f['day'], P)]; kv = [f['pct'] for f in feats if inP(f['day'], P) and fn(f[key])]
        print(f"   {nm}: all trades {avg(allv)} (n={len(allv)})   kept {avg(kv)} (n={len(kv)}, win {100*sum(x > 0 for x in kv)/max(len(kv),1):.0f}%)")

    print("\n== E. How unusual is the 2026-03..10 FADE result? ==")
    allp = [t['pct'] for t in sorted(trades, key=lambda t: (t['day'], t['k']))]
    A_ = [t['pct'] for t in trades if t['day'] <= '2026-02-27']; B_ = [t['pct'] for t in trades if TE[0] <= t['day'] <= TE[1]]
    se = (st.variance(A_) / len(A_) + st.variance(B_) / len(B_)) ** 0.5
    print(f"   before 2026-03: n={len(A_)} mean {st.mean(A_):+.3f}% sd {st.pstdev(A_):.2f};  2026-03..10: n={len(B_)} mean {st.mean(B_):+.3f}% sd {st.pstdev(B_):.2f};  Welch t of the difference = {(st.mean(B_)-st.mean(A_))/se:.2f}")
    print(f"   all {len(allp)} trades: mean {st.mean(allp):+.3f}%, t against zero = {st.mean(allp)/(st.pstdev(allp)/len(allp)**0.5):.2f}")
    wd = [d for d in days if d <= '2026-02-27']; W = 157; res = []
    for i in range(0, len(wd) - W, 5):
        S = set(wd[i:i + W]); v = [t['pct'] for t in trades if t['day'] in S]
        if len(v) > 40: res.append(st.mean(v))
    print(f"   157-day windows before 2026-03 (step 5 days, {len(res)} windows): best mean {max(res):+.3f}%, 95th percentile {sorted(res)[int(.95*len(res))]:+.3f}%, share at or above +0.483%: {100*sum(r >= 0.483 for r in res)/len(res):.1f}%")
    ex = [t['pct'] for t in trades if TE[0] <= t['day'] <= TE[1] and t['day'][:7] not in ('2026-06', '2026-07')]
    print(f"   2026-03..10 without 2026-06 and 2026-07: n={len(ex)} mean {st.mean(ex):+.3f}%;  those two months alone: n={len(B_)-len(ex)} mean {st.mean([t['pct'] for t in trades if t['day'][:7] in ('2026-06','2026-07')]):+.3f}%")
    fw = []
    for p in PROXIES:
        for d in days:
            s_ = RL.RT.setup(D.bars[p][d], RL.FC.FADE)
            if s_ and s_[0] < 47: fw.append((d, s_[1] * (D.bars[p][d][47][3] / D.bars[p][d][s_[0]][0] - 1) * 1e4))
    a = [v for d, v in fw if d <= '2026-02-27']; b_ = [v for d, v in fw if d >= '2026-03-03']
    print(f"   direction-only drift of the proxy after the signal (bp): before {st.mean(a):+.1f} (t {st.mean(a)/(st.pstdev(a)/len(a)**0.5):+.2f}), 2026-03..10 {st.mean(b_):+.1f} (t {st.mean(b_)/(st.pstdev(b_)/len(b_)**0.5):+.2f}), all {st.mean(a+b_):+.1f} (t {st.mean(a+b_)/(st.pstdev(a+b_)/len(a+b_)**0.5):+.2f})")
    print("\n== F. Rolling-edge gate: take the next signal only if the previous N signals (taken or not) averaged above zero ==")
    import final_system as FS
    f_sig, p_sig = FS.cands(D, days)
    for nm, sig in (('FADE (real legs)', trades), ('PULLBACK', p_sig)):
        sig = sorted(sig, key=lambda t: (t['day'], t['k']))
        for N in (20, 40, 80):
            kept = [t for i, t in enumerate(sig) if i >= N and st.mean(x['pct'] for x in sig[i - N:i]) > 0]
            line = f"   {nm:<18} N={N:<3}"
            for lab, P in (('TRAIN', TR), ('VALID', VA), ('TEST', TE)):
                al = [t['pct'] for t in sig if inP(t['day'], P)]; kv = [t['pct'] for t in kept if inP(t['day'], P)]
                line += f" | {lab} all {avg(al)} ({len(al)}) gated {avg(kv)} ({len(kv)})"
            print(line)


if __name__ == '__main__':
    main()
