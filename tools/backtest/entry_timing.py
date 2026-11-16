#!/usr/bin/env python3
"""Entry-timing study (governor 2026-11-16: "entry timing ... later entries, fill latency, earlier overnight entry or later overnight exit"). Research only.
Baseline = live joint book v5.2.59 (FADE, PULLBACK, IBS-LONG, MIRROR, DIP, overnight leg at 50%). One change at a time. Train 2022/2024/2026, test 2023/2025.
Pre-set rule: QUALIFIES = beats baseline on train compounded and in 2 of 3 train years. PASSES = also beats it in both test years.
  A  9:35 family entry bar: 9:30, 9:35 (live), 9:40, 9:45, 9:50, 10:05, 10:35 (signal is known at the prior close; only the fill time moves)
  B  fill latency / slippage on the 9:35 family: entry price worse by 0, 0.05, 0.10, 0.20% of the proxy, and a 5-minute delay (9:40) with the same slips
  C  overnight entry time: signal recomputed at 15:55 (live), 15:30, 15:00, 14:00, 13:00 with the price then as "the close"
  D  overnight exit time: 9:30 open, 9:35 (live), 9:40, 9:45, 10:00
  E  overnight fill slip 0, 0.05, 0.10, 0.20% each way on the 3x leg
    python3 -I tools/backtest/entry_timing.py > tools/backtest/results/entry_timing_2026-11-16.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import exit_all as X
O, B, BA, BM, SB, N2, NS, TB = X.O, X.B, X.BA, X.BM, X.SB, X.N2, X.NS, X.TB; TR, TE = X.TR, X.TE; dm = X.dm; ds = X.ds; mgx = X.mgx
F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4)
M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
SIG = {nm: [(t['day'], t['proxy'], t['rv']) for t in base] for nm, base in (('I', I0), ('Mi', M), ('Di', D))}; SIDE = dict(I=1, Mi=-1, Di=1); SID = dict(I=4, Mi=5, Di=2)


def fam(nm, kin=1, slip=0.0, stop=1.0):
    out = []
    for d, p, rv in SIG[nm]:
        b = ds.bars[p][d]; s = SIDE[nm]
        if kin >= NS.END - 2: continue
        e = b[kin][0] * (1 + s * slip / 100); x, g = mgx(b, kin, s, e, stop, NS.END)
        out.append(dict(day=d, k=kin, xbar=x, pct=3 * g / e * 100 - NS.COST, leg_risk=3 * stop, rv=rv, sys=SID[nm], proxy=p))
    return out


def ovn(k=77, xb=1, slip=0.0):
    """Overnight long leg: signal at bar k of day d (price b[k][0] as the close, range of bars before k), exit at open of bar xb next day. Array on the exit day."""
    r = np.zeros(len(dm)); n = 0; best = {}
    for i, d in enumerate(dm[:-1]):
        nd = dm[i + 1]
        for p in B.F.LIVE if hasattr(B, 'F') else O.F.LIVE:
            b = ds.bars[p].get(d); nb = ds.bars[p].get(nd); h = N2.hist(p, d, 49)
            if not b or not nb or len(b) < 78 or h is None: continue
            c = b[k][0]; H = max(x[1] for x in b[:k]); L = min(x[2] for x in b[:k])
            if H <= L: continue
            ibs = (c - L) / (H - L); c20 = h[2][-19:] + [c]
            if not (c > st.mean(c20) and ibs < 0.10): continue
            ce = c * (1 + slip / 100); px = nb[xb][0] * (1 - slip / 100); pct = 3 * (px / ce - 1) * 100 - NS.COST
            rv = ds.rvol(p, d, k)
            if nd not in best or rv > best[nd][0]: best[nd] = (rv, pct, d, p)
    for nd, (rv, pct, d, p) in best.items(): r[dm.index(nd)] = pct / 100
    return r, best


def book(F=F0, P=P0, I=None, Mi=None, Di=None, o=None):
    I = I0 if I is None else I; Mi = M if Mi is None else Mi; Di = D if Di is None else Di
    a = BA.acct(dm, TB.byday(F + P + I + Mi + Di), after_stop=False)[0]
    return SB.yret((1 + a) * (1 + 0.5 * o) - 1)


ob, bb = ovn(); yb = book(o=ob)


def verdict(y):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''


def row(tag, y, extra=''):
    print(f"   {verdict(y) if tag[:4] != 'LIVE' else '':<5}{tag:<48} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) {extra}")


def stat(T): p = [t['pct'] for t in T]; return f"win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.2f}% n {len(p)}"


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); parentheses = points vs the live book\n')
    row('LIVE book (9:35 entry, overnight 15:55 to 9:35)', yb)
    print('\nA. 9:35 FAMILY ENTRY BAR (all three systems move together)')
    for kin, lab in ((0, '9:30'), (1, '9:35 live'), (2, '9:40'), (3, '9:45'), (4, '9:50'), (7, '10:05'), (13, '10:35')):
        T = {nm: fam(nm, kin) for nm in SIG}; y = book(I=T['I'], Mi=T['Mi'], Di=T['Di'], o=ob)
        row(f'enter {lab}', y, '| ' + stat(T['I'] + T['Mi'] + T['Di']))
    print('\nB. FILL SLIPPAGE ON THE 9:35 FAMILY (entry price worse by x% of the proxy; 3x on the leg)')
    for kin, lab in ((1, '9:35'), (2, '9:40 (5 min late)')):
        for slip in (0, 0.05, 0.10, 0.20):
            if kin == 1 and slip == 0: continue
            T = {nm: fam(nm, kin, slip) for nm in SIG}; row(f'enter {lab}, slip {slip:.2f}%', book(I=T['I'], Mi=T['Mi'], Di=T['Di'], o=ob), '| ' + stat(T['I'] + T['Mi'] + T['Di']))
    print('\nC. OVERNIGHT ENTRY TIME (signal recomputed then; exit 9:35)')
    for k, lab in ((77, '15:55 live'), (75, '15:45'), (72, '15:30'), (66, '15:00'), (54, '14:00'), (42, '13:00')):
        o, bst = ovn(k=k); row(f'enter {lab}', book(o=o), f'| {len(bst)} nights, avg leg {np.mean([v[1] for v in bst.values()]):+.2f}%')
    print('\nD. OVERNIGHT EXIT TIME (entry 15:55)')
    for xb, lab in ((0, '9:30 open'), (1, '9:35 live'), (2, '9:40'), (3, '9:45'), (6, '10:00')):
        o, bst = ovn(xb=xb); row(f'exit {lab}', book(o=o), f'| avg leg {np.mean([v[1] for v in bst.values()]):+.2f}%')
    print('\nE. OVERNIGHT FILL SLIP (each side, % of the 3x leg price proxy)')
    for slip in (0.05, 0.10, 0.20):
        o, bst = ovn(slip=slip); row(f'slip {slip:.2f}% each way', book(o=o), f'| avg leg {np.mean([v[1] for v in bst.values()]):+.2f}%')
    # conflict: overnight entry earlier than 15:55 against open day trades
    print('\nCONFLICT CHECK for C: nights where a day trade is still open at the earlier entry bar')
    by = TB.byday(F0 + P0 + I0 + M + D)
    for k in (72, 66, 54):
        o, bst = ovn(k=k); n = sum(1 for nd, v in bst.items() if any(t['xbar'] >= k for t in by.get(v[2], [])))
        print(f"      entry bar {k}: {n} of {len(bst)} signal nights have a day trade open at entry (they would split cash)")


if __name__ == '__main__':
    main()
