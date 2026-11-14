#!/usr/bin/env python3
"""Universe check for the overnight leg (governor 2026-11-14: "push all these changes and confirm no other universe changes are better
or more robust"). Baseline = v5.2.51 joint book + the overnight leg on the long signal at 50% of cash on the six proxies.
SHRINK: the overnight leg without one of the six. EXPAND: the overnight leg with one of 12 new proxies added (SPY DIA TLT EEM FXI XLRE
3x; XLE GDX XOP 2x; KRE XLV XLU 3x long). Same pre-set rule: beat the baseline on train compounded and in 2 of 3 train years
(qualifies), then in both test years (passes). Train 2022/2024/2026, test 2023/2025.
    python3 -I tools/backtest/overnight_universe.py DATA_DIR > tools/backtest/results/overnight_universe_2026-11-14.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, universe as U, overnight as O
B, BA, BM, SB, N2, NS, TB = O.B, O.BA, O.BM, O.SB, O.N2, O.NS, O.TB; TR, TE = O.TR, O.TE; dm = O.dm


def legs(ds, p, lev):
    """{next day: (pct, rv)} for the overnight long signal on proxy p."""
    out = {}
    for i, d in enumerate(dm[:-1]):
        b = ds.bars[p].get(d); nb = ds.bars[p].get(dm[i + 1]); h = N2.hist(p, d, 49)
        if not b or not nb or len(b) < 78 or len(nb) < 78 or h is None: continue
        c = b[77][0]; H = max(x[1] for x in b[:77]); L = min(x[2] for x in b[:77])
        if H <= L or not (c > st.mean(h[2][-19:] + [c]) and (c - L) / (H - L) < 0.10): continue
        out[dm[i + 1]] = (lev * (nb[1][0] / c - 1) * 100 - NS.COST, ds.rvol(p, d, 77))
    return out


def main():
    path = os.path.join(sys.argv[1], 'M5U.json.gz'); allp = list(F.LIVE) + list(U.NEW); F.LEV.update({p: (3, 3) for p in U.NEW})
    ds = F.DS(path, allp); N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
    M = B.BC.new(B.ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(B.ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    book = BA.acct(dm, TB.byday(F0 + P0 + I0 + M + D), after_stop=False)[0]
    L = {p: legs(ds, p, 3) for p in F.LIVE}; LN = {p: legs(ds, p, U.NEW[p][0]) for p in U.NEW if p in ds.bars and len(ds.bars[p]) > 500}
    def ov(ps):
        r = np.zeros(len(dm))
        for n, d in enumerate(dm):
            c = [x[d] for x in ps if d in x]
            if c: r[n] = max(c, key=lambda t: t[1])[0] / 100
        return r
    def run(ps): return SB.yret((1 + book) * (1 + 0.5 * ov(ps)) - 1)
    yb = run(list(L.values())); y0 = SB.yret(book)
    def row(tag, y, extra=''):
        q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
        return f"   {v:<5}{tag:<40} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} | change {' '.join(f'{a:+5.1f}' for a in y - yb)}{extra}"
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th)\n')
    print(f"        {'v5.2.51 book, no overnight':<40} {' '.join(f'{a:+7.1f}' for a in y0)} | avg 22-25 {y0[:4].mean():+6.1f}")
    print(f"        {'BASELINE: + overnight long 50%, six proxies':<40} {' '.join(f'{a:+7.1f}' for a in yb)} | avg 22-25 {yb[:4].mean():+6.1f}")
    print('\nSHRINK the overnight leg')
    for p in F.LIVE:
        x = list(L[p].values()); print(row(f'without {p}', run([L[q] for q in F.LIVE if q != p]), f" | {p} alone: {len(x)} nights, {100 * np.mean([t[0] > 0 for t in x]):.0f}% wins, {np.mean([t[0] for t in x]):+.2f}% a leg"))
    print('\nEXPAND the overnight leg')
    ok = []
    for p, x in LN.items():
        v = list(x.values()); y = run(list(L.values()) + [x]); r = row(f'+ {p} ({U.LEGS[p]})', y, f" | alone: {len(v)} nights, {100 * np.mean([t[0] > 0 for t in v]):.0f}% wins, {np.mean([t[0] for t in v]):+.2f}% a leg"); print(r)
        if r.strip().startswith(('PASS', 'qual')): ok.append(p)
    print(row('+ ALL twelve', run(list(L.values()) + list(LN.values()))))
    print(f"\n   qualified or passed: {', '.join(ok) or 'none'}")


if __name__ == '__main__':
    main()
