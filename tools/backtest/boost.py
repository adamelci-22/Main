#!/usr/bin/env python3
"""Boost study (governor 2026-11-13: "get the system to average over 30% per year without 2026 by tweaking everything ... entry,
exit, hold mechanics ... I'm ok with bigger drawdown"). Research only.
Split stays the governor's: TRAIN = 2022, 2024, 2026; TEST = 2023, 2025. Every choice is made on TRAIN and judged on TEST.
Score reported for each book: the average year 2022-2025 (2026 left out), the compound rate, the worst year and the drawdown.
Levers tested (the earlier knob grid of 14,244 tunes did not transfer, so these are structural):
  A  daily-trend filter on FADE (take only fades WITH the proxy's daily trend, or only against it) and on PULLBACK (inverse leg only
     when its underlying is below / above its average) - the idea IBS-TREND rests on
  B  IBS-TREND mechanics: threshold, average length, stop width (or none), afternoon-only entry (13:30, runs beside the morning book),
     a mirror on the inverse leg (below the average and a close in the top of the range)
  C  books: live + IBS-TREND as pushed (v5.2.48) against the best TRAIN choices of A and B
    python3 -I tools/backtest/boost.py > tools/backtest/results/boost_2026-11-13.txt"""
import itertools, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import split_build as SB
TB, BC, NS, N2 = SB.TB, SB.BC, SB.NS, SB.N2
FS, PS, EP = BC.FS, BC.PS, BC.EP
dm = SB.dm; YEARS = SB.YEARS; TR = [YEARS.index(y) for y in SB.TRAIN]; TE = [YEARS.index(y) for y in SB.TEST]; PRE = [0, 1, 2, 3]
ds, ctx = TB.ds_m, TB.cx_m; UND = dict(SOXS='SOXX', LABD='XBI', TECS='XLK', UVXY='QQQ')
mg, fin = NS.mg, NS.fin


def line(name, r, mark=''):
    y = SB.yret(r); dd = SB.ydd(r); w = [float(SB.mstats(SB.mret(r))[yy][0]) for yy in YEARS]
    return (f"   {mark:<2}{name:<50} {' '.join(f'{v:+7.1f}' for v in y)} | avg 22-25 {y[PRE].mean():+6.1f} cmpd {((np.prod(1 + y[PRE] / 100)) ** 0.25 - 1) * 100:+6.1f}/yr | "
            f"TRAIN {(np.prod(1 + y[TR] / 100) - 1) * 100:+7.1f} TEST {(np.prod(1 + y[TE] / 100) - 1) * 100:+6.1f} | worst {y.min():+6.1f} DD {dd.max():4.1f} | win mo {np.mean(w):3.0f}%")


HEAD = f"     {'book':<50} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7} {'2026':>7} | average and compound rate 2022-2025 | TRAIN and TEST compounded | worst year, max DD | winning months"


def fade_trades(trend=None, n=20):
    """Live FADE trades. trend: None = all, 'with' = bull leg only above the average / inverse only below, 'against' = the reverse."""
    out = []
    for t in TB.fade_entries(ds, ctx, dm, 0.5):
        if t['fri'] or t['run']: continue
        if trend:
            u = N2.up(t['proxy'], t['day'], n)
            if u is None: continue
            ok = (t['side'] > 0) == u
            if (trend == 'with') != ok: continue
        m = FS.manage(t, {}); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=0))
    return out


def pb_trades(trend=None, n=20):
    """Live PULLBACK trades on the 4 tape legs. trend: 'down' = only when the underlying closed below its average, 'up' = only above."""
    out = []
    for t in TB.pb_entries(ds, dm, PS.LEGS_M, dict(EP.LIVE)):
        if trend:
            u = N2.up(UND[t['proxy']], t['day'], n)
            if u is None or (trend == 'up') != u: continue
        m = PS.manage(t, BC.RUN); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
    return out


def ibs_fn(ds_, ctx_, p, d, b, lo=0.1, n=20, stop=1.0, kin=1, mirror=False, hi=0.9):
    v = N2.ibsv(p, d); u = N2.up(p, d, n)
    if v is None or u is None: return None
    s = 1 if (u and v < lo) else -1 if (mirror and (not u) and v > hi) else 0
    if not s: return None
    e = b[kin][0]; x, g, r = mg(b, kin, s, e, e * (1 - s * (stop if stop else 30.0) / 100), NS.END)
    t = fin(d, p, kin, x, e, g, r)
    if not stop: t['leg_risk'] = 3.0                      # no stop: still sized at full cash
    return t


def ibs_trades(sid=4, **kw): return BC.new(ds, ctx, dm, ibs_fn, kw, sid)


def book(*parts): return SB.acct(dm, TB.byday([t for p in parts for t in p]))


def main():
    print(__doc__.split('\n')[0]); print(f"Massive tape {dm[0]}..{dm[-1]}. Account: 3% risk capped at cash, one position at a time. Year returns in %.\n")
    F0, P0 = fade_trades(), pb_trades(); I0 = ibs_trades()
    print('BASE'); print(HEAD)
    print(line('LIVE before today (FADE + PULLBACK)', book(F0, P0))); print(line('LIVE NOW v5.2.48 (FADE + PULLBACK + IBS-TREND)', book(F0, P0, I0)))
    print(line('FADE alone', book(F0))); print(line('PULLBACK alone', book(P0))); print(line('IBS-TREND alone', book(I0)))
    # ---- A: daily-trend filters
    print('\nA. DAILY-TREND FILTER on FADE and PULLBACK (alone). * = best TRAIN among the filtered versions'); print(HEAD)
    fa = {(tr, n): fade_trades(tr, n) for tr, n in itertools.product(('with', 'against'), (10, 20, 50))}
    pa = {(tr, n): pb_trades(tr, n) for tr, n in itertools.product(('down', 'up'), (10, 20, 50))}
    def trainc(r): y = SB.yret(r); return np.prod(1 + y[TR] / 100)
    def trainmin(r): return SB.yret(r)[TR].min()
    fbest = max(fa, key=lambda k: (trainmin(book(fa[k])), trainc(book(fa[k])))); pbest = max(pa, key=lambda k: (trainmin(book(pa[k])), trainc(book(pa[k]))))
    print(line(f'FADE all (live), {len(F0)} trades', book(F0)))
    for k, T in fa.items(): print(line(f'FADE {k[0]} the daily trend, {k[1]}-day average, {len(T)} trades', book(T), '*' if k == fbest else ''))
    print(line(f'PULLBACK all (live), {len(P0)} trades', book(P0)))
    for k, T in pa.items(): print(line(f'PULLBACK only with the underlying {k[0]}, {k[1]}-day, {len(T)} trades', book(T), '*' if k == pbest else ''))
    f_ok = trainmin(book(fa[fbest])) > trainmin(book(F0)) and trainc(book(fa[fbest])) > trainc(book(F0)); p_ok = trainmin(book(pa[pbest])) > trainmin(book(P0)) and trainc(book(pa[pbest])) > trainc(book(P0))
    print(f"   TRAIN verdict: FADE filter {fbest} {'beats' if f_ok else 'does NOT beat'} live FADE on both train measures; PULLBACK filter {pbest} {'beats' if p_ok else 'does NOT beat'} live PULLBACK")
    # ---- B: IBS mechanics
    print('\nB. IBS-TREND MECHANICS (alone). * = best TRAIN (best worst train year, then train total)'); print(HEAD)
    grid = [dict(lo=lo, n=n, stop=stp) for lo, n, stp in itertools.product((0.05, 0.10, 0.15), (10, 20, 30), (1.0, 1.5, 2.5, None))]
    res = [(kw, ibs_trades(**kw)) for kw in grid]
    ib = max(range(len(res)), key=lambda i: (trainmin(book(res[i][1])), trainc(book(res[i][1]))))
    for i, (kw, T) in enumerate(res):
        print(line(f"IBS < {kw['lo']:.2f}, {kw['n']}-day, stop {str(kw['stop']) + '%' if kw['stop'] else 'none'}, {len(T)} signals", book(T), '*' if i == ib else ''))
    yy = np.array([SB.yret(book(T)) for _, T in res]); print(f"   settings positive in both TEST years: {int((yy[:, TE] > 0).all(1).sum())} of {len(res)}; positive in all five years: {int((yy > 0).all(1).sum())} of {len(res)}")
    IB = res[ib][1]; kwb = res[ib][0]
    print('   variants of the pushed rule (0.10, 20-day, stop 1%):')
    PM = ibs_trades(sid=5, kin=48); MIR = ibs_trades(sid=6, mirror=True); MIRonly = [t for t in MIR if t['pct'] is not None and t not in I0]
    print(line(f'afternoon only: enter 13:30, out 15:55, {len(PM)} signals', book(PM)))
    print(line(f'with the mirror (inverse leg below the average, IBS > 0.90), {len(MIR)} signals', book(MIR)))
    # ---- C: books
    print('\nC. BOOKS'); print(HEAD)
    FB = fa[fbest] if f_ok else F0; PB = pa[pbest] if p_ok else P0
    rows = [('LIVE NOW v5.2.48: FADE + PULLBACK + IBS-TREND', book(F0, P0, I0)),
            (f'+ IBS train pick ({kwb["lo"]:.2f}, {kwb["n"]}-day, stop {kwb["stop"] or "none"})', book(F0, P0, IB)),
            ('IBS afternoon only (13:30) beside the morning book', book(F0, P0, PM)),
            ('IBS full day + mirror', book(F0, P0, MIR)),
            (f'FADE {fbest[0]}-trend {fbest[1]}d + PULLBACK + IBS', book(fa[fbest], P0, I0)),
            (f'FADE + PULLBACK und. {pbest[0]} {pbest[1]}d + IBS', book(F0, pa[pbest], I0)),
            (f'FADE {fbest[0]} {fbest[1]}d + PULLBACK {pbest[0]} {pbest[1]}d + IBS', book(fa[fbest], pa[pbest], I0)),
            (f'both filters + IBS train pick', book(fa[fbest], pa[pbest], IB)),
            ('PULLBACK + IBS (no FADE)', book(P0, I0)), ('FADE + IBS (no PULLBACK)', book(F0, I0)), ('IBS + PULLBACK und. filter (no FADE)', book(pa[pbest], I0))]
    for nm, r in rows: print(line(nm, r))
    print(f"\n   TRAIN-approved pieces: FADE filter {'YES ' + str(fbest) if f_ok else 'no'}; PULLBACK filter {'YES ' + str(pbest) if p_ok else 'no'}; IBS setting {kwb}")
    print(line('TRAIN-APPROVED BOOK', book(FB, PB, IB)))


if __name__ == '__main__':
    main()
