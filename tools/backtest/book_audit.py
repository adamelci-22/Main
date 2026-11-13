#!/usr/bin/env python3
"""Audit of the v5.2.50 joint book (governor 2026-11-13: "one last pass to clean up anything you can to reduce drag and inefficiency
and tell me which subsystems will now be used"). Research only.
1. Usage: trades taken, win rate and account contribution of each subsystem, by year, in the one shared account.
2. Live rule the backtest never applied: A1.2 daily loss limit (account down 3% on the day -> no new entries). Measured here.
3. Drag checks: trades taken AFTER an IBS-family stop-out the same day; signals of one subsystem blocked by another; leg cost doubled.
    python3 -I tools/backtest/book_audit.py > tools/backtest/results/book_audit_2026-11-13.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boost as B, boost_mirror as BM
SB, N2, NS, BC = B.SB, B.N2, B.NS, B.BC; YEARS = SB.YEARS
NAME = {0: 'FADE', 1: 'PULLBACK', 2: 'DIP', 4: 'IBS-TREND long', 5: 'IBS mirror'}; FAM = (2, 4, 5)


def acct(days, by, dll=None, after_stop=True, extra_cost=0.0, risk=3.0, cap=3):
    out = np.zeros(len(days)); taken = []; blockedby = {}
    for n, d in enumerate(days):
        cs = by.get(d)
        if not cs: continue
        cs = sorted(cs, key=lambda t: (t['k'], -t['rv'], t['sys'])); free = 0; eq = 0.0; cnt = 0; lost = set(); holder = None; famstop = False
        for t in cs:
            if cnt >= cap: break
            if t['sys'] in lost: continue
            if t['k'] < free:
                if holder is not None and holder != t['sys'] and not (holder in FAM and t['sys'] in FAM): blockedby[(holder, t['sys'])] = blockedby.get((holder, t['sys']), 0) + 1
                continue
            if dll is not None and eq <= -dll / 100: break
            if famstop and not after_stop: break
            g = min(1.0, risk / t['leg_risk']) * (t['pct'] - extra_cost) / 100; eq = (1 + eq) * (1 + g) - 1; free = t['xbar'] + 1; cnt += 1; holder = t['sys']
            taken.append(dict(day=d, sys=t['sys'], g=g * 100, after=famstop))
            if g <= 0: lost.add(t['sys'])
            if t['sys'] in FAM and g < 0 and t['xbar'] < NS.END - 1: famstop = True
        out[n] = eq
    return out, taken, blockedby


def main():
    F0, P0 = B.fade_trades(), B.pb_trades(); I0 = B.ibs_trades(sid=4)
    M = BC.new(B.ds, B.ctx, B.dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = BC.new(B.ds, B.ctx, B.dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    by = B.TB.byday(F0 + P0 + I0 + M + D); r, tk, bb = acct(B.dm, by); y = SB.yret(r)
    print(__doc__.split('\n')[0]); print(f"\nv5.2.50 book by year: {' '.join(f'{yy} {v:+.1f}%' for yy, v in zip(YEARS, y))} | average 2022-25 {y[:4].mean():+.1f}%\n")
    print('1. USAGE in the shared account: trades taken (wins %) and account points added, by year')
    print(f"   {'subsystem':<16} " + ' '.join(f"{yy:>17}" for yy in YEARS) + f" | {'all':>17} | days traded")
    for s in (0, 1, 4, 5, 2):
        cells = []
        for yy in YEARS:
            x = [t for t in tk if t['sys'] == s and t['day'][:4] == yy]; cells.append(f"{len(x):3d} ({100 * np.mean([t['g'] > 0 for t in x]) if x else 0:2.0f}%) {sum(t['g'] for t in x):+6.1f}")
        x = [t for t in tk if t['sys'] == s]; nd = len({t['day'] for t in x})
        print(f"   {NAME[s]:<16} " + ' '.join(f"{c:>17}" for c in cells) + f" | {len(x):3d} ({100 * np.mean([t['g'] > 0 for t in x]):2.0f}%) {sum(t['g'] for t in x):+6.1f} | {nd} ({100 * nd / len(B.dm):.0f}%)")
    alld = len({t['day'] for t in tk}); print(f"   days with any trade: {alld} of {len(B.dm)} ({100 * alld / len(B.dm):.0f}%). Signals offered: FADE {len(F0)}, PULLBACK {len(P0)}, IBS long {len(I0)}, mirror {len(M)}, DIP {len(D)}.")
    print('   signals lost to another subsystem holding the account: ' + ', '.join(f"{NAME[a]} blocked {NAME[b]} {n}x" for (a, b), n in sorted(bb.items(), key=lambda z: -z[1])[:6]))
    print('\n2. LIVE RULES THE BACKTEST DID NOT APPLY')
    for tag, kw in (('A1.2 daily loss limit 3% (live rule)', dict(dll=3.0)), ('no entry after an IBS-family stop-out that day', dict(after_stop=False)), ('daily loss limit 2.5%', dict(dll=2.5))):
        r2, tk2, _ = acct(B.dm, by, **kw); y2 = SB.yret(r2)
        print(f"   {tag:<48} {' '.join(f'{v:+7.1f}' for v in y2)} | change {' '.join(f'{v:+5.1f}' for v in y2 - y)} | average 22-25 {y2[:4].mean():+.1f} | trades {len(tk2)} (was {len(tk)})")
    aft = [t for t in tk if t['after']]
    print(f"   trades taken after an IBS-family stop-out the same day: {len(aft)}, wins {100 * np.mean([t['g'] > 0 for t in aft]) if aft else 0:.0f}%, account points {sum(t['g'] for t in aft):+.1f} over five years")
    print('\n3. COST SENSITIVITY (leg cost 0.06% a round trip in the model)')
    for ec in (0.06, 0.14):
        r3, _, _ = acct(B.dm, by, extra_cost=ec); y3 = SB.yret(r3); print(f"   cost {0.06 + ec:.2f}% a round trip: {' '.join(f'{v:+7.1f}' for v in y3)} | average 22-25 {y3[:4].mean():+.1f}")
    print('\n4. ONE SUBSYSTEM REMOVED (what each is worth inside the joint book)')
    for s in (0, 1, 4, 5, 2):
        r4, _, _ = acct(B.dm, B.TB.byday([t for t in F0 + P0 + I0 + M + D if t['sys'] != s])); y4 = SB.yret(r4)
        print(f"   without {NAME[s]:<15} {' '.join(f'{v:+7.1f}' for v in y4)} | change {' '.join(f'{v:+6.1f}' for v in y4 - y)} | average 22-25 {y4[:4].mean():+.1f} ({y4[:4].mean() - y[:4].mean():+.1f})")


if __name__ == '__main__':
    main()
