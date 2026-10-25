#!/usr/bin/env python3
"""Why is the live system positive only from 2026-03? Stock choice or system? Tests on the Massive 5-year bars (signal model of final_system.py, nothing re-tuned).
    /usr/bin/python3 -I tools/backtest/massive_diagnosis.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz > tools/backtest/results/massive_diagnosis.txt
1. Market regime by year: daily range, gap, opening-box width, trend, share of days with a FADE setup.
2. FADE decomposition by year: win rate, share reaching 2R, average win and loss, stop-outs.
3. Direction-only test: does the proxy move the fade's way from entry to 13:30? (no stops, no targets, no leverage cost)
4. FADE by volatility regime: results against the proxy's trailing 20-day range relative to its own median.
5. Stock choice, FADE: the six live proxies against five proxies that were not selected (SPY TLT KRE GLD VIXY), before and after 2026-03-03.
6. Stock choice, PULLBACK: the four live funds against fourteen others.
A = 2021-11 .. 2026-02-27 (before the rules' data). B = 2026-03-03 .. 2026-10-14 (the rules' data).
"""
import collections, gzip, json, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
_raw = json.load(gzip.open(sys.argv[1], 'rt')); _daily = json.load(gzip.open(sys.argv[2], 'rt'))
BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
import manual as m, pb_final as PBF, pb_inverse as PI, expand_lists as EX, fade_addone as FA, fade_combo as FC, twobar as TB, retest as RT
from lab import get_data

LIVE = BT.PROXIES
ALT = {'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'KRE': ('DPST', 3, 'KRED', 3), 'GLD': ('UGL', 2, 'GLL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)}
PB_LIVE = ['SOXS', 'LABD', 'TECS', 'UVXY']
PB_ALT = ['SPXU', 'SDS', 'QID', 'SRTY', 'SDOW', 'ERY', 'DRIP', 'DUST', 'TMV', 'UVIX', 'SVIX', 'TZA', 'SQQQ', 'FAZ']
A_END, B0, B1 = '2026-02-27', '2026-03-03', '2026-10-14'
per = lambda d: 'A' if d <= A_END else ('B' if B0 <= d <= B1 else None)
yr = lambda d: d[:4]


def stats(v):
    if not v: return 'n=0'
    return f"n={len(v):>3} win {100*sum(x>0 for x in v)/len(v):>3.0f}% avg {st.mean(v):+.3f}%"


def main():
    D = get_data(); days = D.days[1:]
    print(f"Massive bars, {len(days)} days {days[0]}..{days[-1]}\n")
    print("== 1. Market regime by year (mean over the six live proxies) ==")
    print(f"{'year':<6}{'days':>5}{'range %':>9}{'|gap| %':>9}{'box 9:30-10 %':>14}{'QQQ ret %':>10}{'FADE setups/day':>16}")
    ft = {p: EX.fade_trades(D, days, p, FA.ROWS[p]) for p in LIVE}
    for y in sorted({yr(d) for d in days}):
        ds = [d for d in days if yr(d) == y]; rng = []; gap = []; box = []
        for p in LIVE:
            for d in ds:
                H, L, C = D.dhlc[p][d]; b = D.bars[p][d]; rng.append((H - L) / C * 100)
                i = D.days.index(d); pc = D.dhlc[p][D.days[i - 1]][2] if i else None
                if pc: gap.append(abs(b[0][0] / pc - 1) * 100)
                box.append((max(x[1] for x in b[:6]) - min(x[2] for x in b[:6])) / b[0][0] * 100)
        q0 = D.bars['QQQ'][ds[0]][0][0]; q1 = D.dhlc['QQQ'][ds[-1]][2]
        ns = sum(1 for p in LIVE for t in ft[p] if yr(t['day']) == y)
        print(f"{y:<6}{len(ds):>5}{st.mean(rng):>9.2f}{st.mean(gap):>9.2f}{st.mean(box):>14.2f}{(q1/q0-1)*100:>10.1f}{ns/len(ds):>16.2f}")
    print("\n== 2. FADE decomposition by year (six live proxies, leg % per trade, signal model) ==")
    print(f"{'year':<6}{'n':>5}{'win%':>6}{'2R hit%':>9}{'stop%':>7}{'time%':>7}{'avg win':>9}{'avg loss':>9}{'avg':>8}")
    for y in sorted({yr(d) for d in days}):
        T = [t for p in LIVE for t in ft[p] if yr(t['day']) == y]
        if not T: continue
        w = [t['pct'] for t in T if t['pct'] > 0]; l = [t['pct'] for t in T if t['pct'] <= 0]
        print(f"{y:<6}{len(T):>5}{100*len(w)/len(T):>6.0f}{100*sum(t['hit'] for t in T)/len(T):>9.0f}{100*sum(t['why'] == 'stop' for t in T)/len(T):>7.0f}{100*sum(t['why'] == 'time' for t in T)/len(T):>7.0f}"
              f"{st.mean(w) if w else 0:>+9.2f}{st.mean(l) if l else 0:>+9.2f}{st.mean(t['pct'] for t in T):>+8.3f}")
    print("\n== 3. Direction-only test: proxy move in the fade's direction, entry bar open -> 13:30 close (bp, no stops, targets or costs) ==")
    print(f"{'year':<6}{'n':>5}{'mean bp':>9}{'median bp':>11}{'up-share %':>11}   (the same trades, opposite direction = the negative of mean)")
    fw = collections.defaultdict(list)
    for p in LIVE:
        for d in days:
            s = RT.setup(D.bars[p][d], FC.FADE)
            if not s or s[0] >= 47: continue
            k, side = s[0], s[1]; b = D.bars[p][d]; fw[yr(d)].append(side * (b[47][3] / b[k][0] - 1) * 1e4)
    for y in sorted(fw):
        v = fw[y]; print(f"{y:<6}{len(v):>5}{st.mean(v):>+9.1f}{st.median(v):>+11.1f}{100*sum(x > 0 for x in v)/len(v):>11.0f}")
    print("\n== 4. FADE by volatility regime (proxy's trailing 20-day mean range / its own median over the sample) ==")
    ratio = {}
    for p in LIVE:
        rg = {d: (D.dhlc[p][d][0] - D.dhlc[p][d][1]) / D.dhlc[p][d][2] for d in D.days}
        tr = {d: st.mean(rg[x] for x in D.prior(d, 20)) for d in days if len(D.prior(d, 20)) == 20}
        med = st.median(tr.values()); ratio[p] = {d: v / med for d, v in tr.items()}
    for lab, lo, hi in (('calm  (<0.85)', 0, 0.85), ('normal(0.85-1.15)', 0.85, 1.15), ('wild  (>1.15)', 1.15, 9)):
        T = [(t, ratio[p][t['day']]) for p in LIVE for t in ft[p] if t['day'] in ratio[p]]
        sel = [t['pct'] for t, r in T if lo <= r < hi]; a = [t['pct'] for t, r in T if lo <= r < hi and per(t['day']) == 'A']; b = [t['pct'] for t, r in T if lo <= r < hi and per(t['day']) == 'B']
        print(f"  {lab:<20} all: {stats(sel)} | A: {stats(a)} | B: {stats(b)}")
    for y in sorted({yr(d) for d in days}):
        v = [ratio[p][d] for p in LIVE for d in ratio[p] if yr(d) == y]
        print(f"  mean regime ratio {y}: {st.mean(v):.2f}")
    print("\n== 5. Stock choice, FADE: live proxies vs proxies that were not selected (leg % per trade, signal model) ==")
    print(f"{'proxy':<6}{'':<6}{'A  (before 2026-03)':<38}{'B  (2026-03..10)':<38}")
    for tag, rows in (('live', {p: FA.ROWS[p] for p in LIVE}), ('alt', ALT)):
        for p, row in rows.items():
            T = EX.fade_trades(D, days, p, row)
            a = [t['pct'] for t in T if per(t['day']) == 'A']; b = [t['pct'] for t in T if per(t['day']) == 'B']
            print(f"{p:<6}{tag:<6}{stats(a):<38}{stats(b):<38}")
    print("\n== 6. Stock choice, PULLBACK: live funds vs other funds (own chart, same rules, % per trade) ==")
    for t_ in PB_ALT: PI.PROXY.setdefault(t_, t_)
    print(f"{'fund':<6}{'':<6}{'A  (before 2026-03)':<38}{'B  (2026-03..10)':<38}")
    for tag, legs in (('live', PB_LIVE), ('alt', PB_ALT)):
        for t_ in legs:
            if t_ not in D.bars: continue
            S = PBF.run(D, days, [t_], oco_gap=True)
            a = [x['pct'] for x in S if per(x['day']) == 'A']; b = [x['pct'] for x in S if per(x['day']) == 'B']
            print(f"{t_:<6}{tag:<6}{stats(a):<38}{stats(b):<38}")


if __name__ == '__main__':
    main()
