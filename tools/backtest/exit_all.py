#!/usr/bin/env python3
"""Exit study for every live system (governor 2026-11-14: "make sure there is no better stop/exit/tp strategies for all of these systems
in terms of return and another in terms of win rate"). Research only. Baseline = the live joint book v5.2.52 (overnight leg at 50%).
One system's exit is changed at a time, the rest stay live. Train 2022/2024/2026, test 2023/2025. Pre-set rule: a variant QUALIFIES if
the book beats the baseline on train compounded and in 2 of 3 train years; it PASSES if it also beats it in both test years.
  9:35 systems (IBS-LONG, MIRROR, DIP): stop 0.5/0.75/1/1.5/2% of the proxy x take-profit none/0.5/1/1.5/2% x breakeven lock off/after
      +0.5% x trail off/1% behind the best close x out 13:30/15:00/15:55  (300 each)
  OVERNIGHT: sell at the 9:30 open / 9:35 / 10:00 / 11:00 / 13:30 / 15:55, with a next-day stop none/1/2% and target none/0.5/1%
  FADE: lock +0.15R/breakeven/off x early cut on/off x target 2R/3R x chandelier 2/3 ATR.  PULLBACK: all at the high / 20-EMA runner / chandelier runner
    python3 -I tools/backtest/exit_all.py > tools/backtest/results/exit_all_2026-11-14.txt"""
import itertools, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import overnight as O
B, BA, BM, SB, N2, NS, TB = O.B, O.BA, O.BM, O.SB, O.N2, O.NS, O.TB; TR, TE = O.TR, O.TE; dm = O.dm; ds = B.ds
FS, PS, EP = B.FS, B.PS, B.EP


def mgx(b, k, s, e, stop, last, tp=None, be=None, trail=None):
    """stop/tp/be/trail in % of the proxy. Exit at the open of bar `last`. Returns (exit bar, gain per share)."""
    sp = e * (1 - s * stop / 100); T = e * (1 + s * tp / 100) if tp else None; best = e
    for j in range(k, last):
        o, h, l, c, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - sp) * s <= 0: return j, ((sp if (o - sp) * s >= 0 else o) - e) * s
        if T is not None and (fav - T) * s >= 0: return j, ((T if (o - T) * s <= 0 else o) - e) * s
        best = max(best, c) if s > 0 else min(best, c); gain = (best / e - 1) * 100 * s
        if be and gain >= be and (e - sp) * s > 0: sp = e
        if trail and gain >= 0.5:
            ns = best * (1 - s * trail / 100)
            if (ns - sp) * s > 0: sp = ns
    return last - 1, (b[last][0] - e) * s


def fam(sig, side, sid, stop=1.0, tp=None, be=None, trail=None, last=NS.END):
    out = []
    for d, p, rv in sig:
        b = ds.bars[p][d]; e = b[1][0]; x, g = mgx(b, 1, side, e, stop, last, tp, be, trail)
        out.append(dict(day=d, k=1, xbar=x, pct=3 * g / e * 100 - NS.COST, leg_risk=3 * stop, rv=rv, sys=sid, proxy=p))
    return out


def stats(T): p = [t['pct'] for t in T]; return 100 * np.mean([x > 0 for x in p]), float(np.mean(p))


def main():
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
    M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
    ovn = np.array([onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm])
    def book(F=F0, P=P0, I=I0, Mi=M, Di=D, o=ovn): return SB.yret((1 + BA.acct(dm, TB.byday(F + P + I + Mi + Di), after_stop=False)[0]) * (1 + 0.5 * o) - 1)
    yb = book()
    def verdict(y):
        q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
        return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
    def row(tag, y, w, a, v=None):
        return f"   {verdict(y) if v is None else v:<5}{tag:<58} win {w:3.0f}% avg {a:+.2f}% | book {' '.join(f'{x:+7.1f}' for x in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f})"
    print(__doc__.split('\n')[0]); print(f"   book years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th). win and avg = that system's own signals, leg %.\n   BASELINE book {' '.join(f'{x:+7.1f}' for x in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n")
    summary = []
    # ---- 9:35 family
    for name, base, side, sid, slot in (('IBS-LONG', I0, 1, 4, 'I'), ('MIRROR', M, -1, 5, 'Mi'), ('DIP', D, 1, 2, 'Di')):
        sig = [(t['day'], t['proxy'], t['rv']) for t in base]; res = []
        for stop, tp, be, trail, last in itertools.product((0.5, 0.75, 1.0, 1.5, 2.0), (None, 0.5, 1.0, 1.5, 2.0), (None, 0.5), (None, 1.0), (48, 66, 77)):
            T = fam(sig, side, sid, stop, tp, be, trail, last); w, a = stats(T); y = book(**{slot: T})
            lab = f"stop {stop:g}%, target {str(tp) + '%' if tp else 'none'}, lock {'BE at +0.5%' if be else 'off'}, trail {'1%' if trail else 'off'}, out {'13:30' if last == 48 else '15:00' if last == 66 else '15:55'}"
            res.append((lab, y, w, a, (stop, tp, be, trail, last)))
        live = next(r for r in res if r[4] == (1.0, None, None, None, 77)); npass = sum(verdict(r[1]) == 'PASS' for r in res); nq = sum(verdict(r[1]) == 'qual' for r in res)
        print(f"{name}: {len(sig)} signals, {len(res)} exits tested. {npass} PASS, {nq} qualify on train only.")
        print(row('LIVE: ' + live[0], live[1], live[2], live[3], 'live'))
        print('   best by RETURN (train years compounded):')
        for r in sorted(res, key=lambda r: -np.prod(1 + r[1][TR] / 100))[:4]: print(row(r[0], r[1], r[2], r[3]))
        ps = sorted([r for r in res if verdict(r[1]) == 'PASS'], key=lambda r: -r[1][:4].mean())[:3]
        if ps:
            print('   best that PASS (by average 2022-25):')
            for r in ps: print(row(r[0], r[1], r[2], r[3]))
        print('   best by WIN RATE:')
        for r in sorted(res, key=lambda r: -r[2])[:4]: print(row(r[0], r[1], r[2], r[3]))
        summary.append((name, npass, len(res), live[2], max(r[2] for r in res))); print()
    # ---- overnight
    print(f"OVERNIGHT: {len(onl)} nights. Exits after 9:35 hold the account through the morning, so they are judged alone (leg at full size).")
    res = []
    for xb, stop, tp in itertools.product((0, 1, 6, 18, 48, 77), (None, 1.0, 2.0), (None, 0.5, 1.0)):
        ps_ = []; by = {}
        for i, d in enumerate(dm[:-1]):
            nd = dm[i + 1]
            if nd not in onl: continue
            p = onl[nd]['proxy']; c = ds.bars[p][d][77][0]; nb = ds.bars[p][nd]; px = None
            for j in range(0, xb):
                o, h, l, cl, v = nb[j]
                if stop and l <= c * (1 - stop / 100): px = min(o, c * (1 - stop / 100)); break
                if tp and h >= c * (1 + tp / 100): px = max(o, c * (1 + tp / 100)); break
            if px is None: px = nb[xb][0]
            g = 3 * (px / c - 1) * 100 - NS.COST; ps_.append(g); by[nd[:4]] = by.get(nd[:4], 1.0) * (1 + g / 100)
        yr = np.array([(by.get(y, 1.0) - 1) * 100 for y in SB.YEARS]); tm = {0: '9:30 open', 1: '9:35', 6: '10:00', 18: '11:00', 48: '13:30', 77: '15:55'}[xb]
        res.append((f"sell {tm}, stop {str(stop) + '%' if stop else 'none'}, target {str(tp) + '%' if tp else 'none'}", yr, 100 * np.mean([x > 0 for x in ps_]), float(np.mean(ps_)), (xb, stop, tp)))
    def orow(tag, r): return f"   {tag:<5}{r[0]:<46} win {r[2]:3.0f}% avg {r[3]:+.2f}% | alone {' '.join(f'{x:+6.1f}' for x in r[1])} | avg 22-25 {r[1][:4].mean():+5.1f} | train worst {r[1][TR].min():+5.1f} test {r[1][TE[0]]:+5.1f} {r[1][TE[1]]:+5.1f}"
    live = next(r for r in res if r[4] == (1, None, None)); print(orow('live', live))
    print('   best by RETURN (train years compounded):')
    for r in sorted(res, key=lambda r: -np.prod(1 + r[1][TR] / 100))[:4]: print(orow('', r))
    print('   best by WIN RATE:')
    for r in sorted(res, key=lambda r: -r[2])[:4]: print(orow('', r))
    better = [r for r in res if np.prod(1 + r[1][TR] / 100) > np.prod(1 + live[1][TR] / 100) and (r[1][TE] > live[1][TE]).all()]
    print(f"   exits that beat the live exit on train AND in both test years (alone): {len(better)} of {len(res)}" + (': ' + '; '.join(r[0] for r in better[:4]) if better else '')); print()
    # ---- FADE
    E = [t for t in TB.fade_entries(ds, B.ctx, dm, 0.5) if not t['fri'] and not t['run']]; res = []
    for xn, pk in TB.FEX.items():
        T = []
        for t in E: m = FS.manage(t, pk); T.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=0))
        w, a = stats(T); res.append((xn, book(F=T), w, a))
    live = next(r for r in res if r[0] == 'lock +0.15R|cut on|tp 2R|chand 2'); npass = sum(verdict(r[1]) == 'PASS' for r in res)
    print(f"FADE: {len(E)} signals, {len(res)} exits tested. {npass} PASS. (About 1,000 other FADE exits were tested on 2026-11-11/12: none adopted.)")
    print(row('LIVE: ' + live[0], live[1], live[2], live[3], 'live'))
    print('   best by RETURN:'); [print(row(r[0], r[1], r[2], r[3])) for r in sorted(res, key=lambda r: -np.prod(1 + r[1][TR] / 100))[:3]]
    print('   best by WIN RATE:'); [print(row(r[0], r[1], r[2], r[3])) for r in sorted(res, key=lambda r: -r[2])[:3]]
    summary.append(('FADE', npass, len(res), live[2], max(r[2] for r in res))); print()
    # ---- PULLBACK
    EPB = TB.pb_entries(ds, dm, PS.LEGS_M, dict(EP.LIVE)); res = []
    PBX = dict(TB.PBX); PBX.update({'half at high + runner EMA20': dict(frac=0.5, run=('ema', 20)), 'runner EMA9': dict(frac=1 / 3, run=('ema', 9)), 'runner chand2': dict(frac=1 / 3, run=('chand', 2.0))})
    for xn, cfg in PBX.items():
        T = []
        for t in EPB: m = PS.manage(t, cfg); T.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
        w, a = stats(T); res.append((xn, book(P=T), w, a))
    live = next(r for r in res if r[0] == 'runner EMA20'); npass = sum(verdict(r[1]) == 'PASS' for r in res)
    print(f"PULLBACK: {len(EPB)} signals, {len(res)} exits tested. {npass} PASS. (PULLBACK exits were screened on 2026-11-11/12; the runner was adopted then.)")
    for r in res: print(row(('LIVE: ' if r is live else '') + r[0], r[1], r[2], r[3], 'live' if r is live else None))
    summary.append(('PULLBACK', npass, len(res), live[2], max(r[2] for r in res)))
    print('\nSUMMARY: system, exits that pass the return rule, live win rate, best win rate found')
    for n, p, k, lw, bw in summary: print(f"   {n:<10} {p:3d} of {k:3d} pass | live win {lw:.0f}% | best win {bw:.0f}%")


if __name__ == '__main__':
    main()
