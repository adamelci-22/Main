#!/usr/bin/env python3
"""2-bar ORB with a RETEST rule, v3.126 Core Five (QQQ, SOXX, IWM, XLK, IBIT -> leveraged legs).
    python3 tools/backtest/retest.py > tools/backtest/results_retest.txt
1. Box = proxy 9:30-10:00 high/low.  2. Break: a 5-min bar CLOSES outside the box, by `brk_end` (10:15 / 10:30 / 11:00).
3. Retest: within the next `max_wait` bars, price comes back to the broken edge (bar low <= edge x (1 + tol) for a long).
   'hold'    = the retest bar must close back outside the box (on the breakout side); a close back inside kills the setup.
   'reclaim' = may close inside; the setup lives until a later bar closes back outside (still within max_wait); it dies if the
               box midpoint is hit.
4. Entry: next 5-min open after the confirming close (live checkpoint).  Optional `confirm`: the confirming bar must also close
   above the retest bar's high.
5. Stop: 'retest' = lowest low from the retest to entry; 'mid' = box midpoint; 'bar2' = Bar 2 low.
6. Exit: half at 1:1 + breakeven / 2R / time; target sale at the next checkpoint; time exit 15:55 or 12:30.
Leg return = leverage x proxy return - 0.06%. Account: $2,000, 3% risk capped at cash, one position at a time, highest RVOL first.
Also: FAILED-RETEST FADE = the retest closes back inside the box -> trade the opposite leg (the pattern the data keeps pointing at).
"""
import itertools, math, os, statistics as st, sys, collections
from dataclasses import dataclass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, twobar as TB
from lab import get_data


@dataclass(frozen=True)
class RC:
    brk_end: int = 9          # break must close by this 5-min bar index (9 = by 10:15, 12 = 10:30, 18 = 11:00)
    max_wait: int = 12        # bars allowed between break and confirmed retest (12 = 1 hour)
    tol: float = 0.10         # % tolerance for "touching" the edge
    mode: str = 'hold'
    confirm: bool = False
    stop: str = 'retest'
    exit: str = 'half1R_be'
    time_exit: int = 77
    fade: bool = False        # trade the failed retest in the opposite direction instead


def setup(b, c):
    """b in trade-direction space is not known yet -> work in real space for both sides. Returns (k, side, entry, stop) or None."""
    H, L = TB.box(b)
    for j in range(6, min(c.brk_end, 76)):
        cl = b[j][3]
        side = 1 if cl > H else -1 if cl < L else 0
        if not side: continue
        bb, p0 = (b, None) if side > 0 else m.mirror(b)
        to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
        E = to_m(H if side > 0 else L); MID = to_m((H + L) / 2)
        touched = None; low = None
        for i in range(j + 1, min(j + 1 + c.max_wait, 76)):
            o, h, l, cc, v = bb[i]
            if touched is None:
                if l <= E * (1 + c.tol / 100):
                    touched = i; low = l
                    if c.fade:
                        if cc < E: return i + 1, -side, b[i + 1][0], to_m(max(bb[k][1] for k in range(j, i + 1)))  # fade: stop above the post-break high
                        return None
                    if cc > E and (not c.confirm):
                        return i + 1, side, b[i + 1][0], _stop(c, bb, to_m, low, MID)
                    if cc <= E and c.mode == 'hold': return None
                continue
            low = min(low, l)
            if l <= MID: return None
            ok = cc > E and (not c.confirm or cc > bb[touched][1])
            if ok: return i + 1, side, b[i + 1][0], _stop(c, bb, to_m, low, MID)
            if c.mode == 'hold' and cc <= E: return None
        return None
    return None


def _stop(c, bb, to_m, low, MID):
    if c.stop == 'retest': s = low - 0.02
    elif c.stop == 'mid': s = MID
    else: s = min(x[2] for x in bb[3:6])
    return ('m', s)


def trade(D, d, p, c):
    raw = D.bars[p][d]; s = setup(raw, c)
    if not s: return None
    k, side, e_real, stop = s
    if k > c.time_exit or k > 76: return None
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry = to_m(e_real)
    st_ = stop[1] if isinstance(stop, tuple) else to_m(stop)
    if isinstance(stop, tuple) and side != (1 if True else 0): pass
    if entry <= st_: return None
    r = entry - st_
    if c.exit == 'half1R_be': T, frac, be = entry + r, 0.5, True
    elif c.exit.startswith('R'): T, frac, be = entry + float(c.exit[1:]) * r, 1.0, False
    else: T, frac, be = None, 1.0, False
    pnl, xbar, why = TB.manage(b, k, entry, st_, T, frac, be, c.time_exit, True, True)
    lev = TB.ROWS[p][2]
    return dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, proxy_pct=pnl / e_real * 100,
                pct=lev * pnl / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100)


def evaluate(D, days, c):
    T = [t for d in days for p in TB.ROWS for t in [trade(D, d, p, c)] if t]
    return T, TB.account(D, days, T)


def line(T, a, days, h):
    dl = a['daily']; tk = a['taken']; pc = [t['pct'] for t in T] or [0]
    tt = st.mean(pc) / (st.pstdev(pc) / math.sqrt(len(pc))) if len(pc) > 2 and st.pstdev(pc) else 0
    return (f"setups {len(T):3d} leg avg {st.mean(pc):+.3f}% t {tt:+.1f} | taken {len(tk):3d} win {100*sum(x['usd']>0 for x in tk)/max(len(tk),1):3.0f}% "
            f"{st.mean(dl.values()):+.3f}%/day ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}% H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")


def desc(c):
    t = {9: '10:15', 12: '10:30', 18: '11:00'}[c.brk_end]; x = {77: '15:55', 35: '12:30'}[c.time_exit]
    return f"{'FADE ' if c.fade else ''}break by {t}, wait {c.max_wait*5}m, tol {c.tol}%, {c.mode}{'+confirm' if c.confirm else ''}, stop {c.stop}, exit {c.exit} out {x}"


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"2-bar ORB + retest, v3.126 Core Five, {days[0]}..{days[-1]} ({len(days)} days). Live-realistic (checkpoint entries/targets).")
    print("Reference: 2-bar ORB without retest (live) -0.149%/day, -19.3%; pullback buy +0.108%/day, +14.6%.\n")
    base = RC()
    for name, c in (('Retest, default (break by 10:15, hold, retest-low stop, half 1:1 + BE, hold to close)', base),
                    ('Retest + confirmation bar', RC(confirm=True)),
                    ('Retest, reclaim allowed', RC(mode='reclaim')),
                    ('FAILED-RETEST FADE (retest closes back inside -> opposite leg)', RC(fade=True)),
                    ('FAILED-RETEST FADE, 2R target', RC(fade=True, exit='R2'))):
        T, a = evaluate(D, days, c); print(f"{name}\n   {line(T, a, days, h)}")
    print("\n== Follow-through after the retest entry (proxy, signed, no stop) ==")
    for c, lab in ((base, 'retest held'), (RC(fade=True), 'failed retest, faded')):
        for hz, hl in ((6, '+30m'), (12, '+60m'), (77, 'close')):
            v = []
            for d in days:
                for p in TB.ROWS:
                    raw = D.bars[p][d]; s = setup(raw, c)
                    if not s or s[0] > 76: continue
                    k, side, e, _ = s
                    v.append(side * (raw[min(k + hz, 77) if hz != 77 else 77][3] / e - 1) * 100)
            print(f"   {lab:<22}{hl:<7} n={len(v):3d} avg {st.mean(v):+.3f}% (se {st.pstdev(v)/math.sqrt(len(v)):.3f}) in profit {100*sum(x>0 for x in v)/len(v):.0f}%")
    print("\n== Grid (walk-forward: choose on H1, judge on H2) ==")
    grid = [RC(brk_end=be, max_wait=w, tol=tl, mode=md, confirm=cf, stop=sp, exit=ex, time_exit=tx)
            for be in (9, 12, 18) for w in (6, 12, 24) for tl in (0.05, 0.15) for md in ('hold', 'reclaim') for cf in (False, True)
            for sp in ('retest', 'mid') for ex in ('half1R_be', 'R2', 'time') for tx in (77,)]
    res = []
    for c in grid:
        _, a1 = evaluate(D, H1, c); _, a2 = evaluate(D, H2, c)
        res.append((c, len(a1['taken']), st.mean(a1['daily'].values()), len(a2['taken']), st.mean(a2['daily'].values())))
    res.sort(key=lambda r: -r[2])
    for c, n1, d1, n2, d2 in res[:12]:
        print(f"   {desc(c):<92} H1 {n1:3d} trd {d1:+.3f}  H2 {n2:3d} trd {d2:+.3f}")
    print(f"   configs: {len(res)}; positive H1 {sum(r[2]>0 for r in res)}, positive H2 {sum(r[4]>0 for r in res)}, positive BOTH {sum(r[2]>0 and r[4]>0 for r in res)}")
    ok = [r for r in res if r[1] >= 15]; b = ok[0]
    print(f"   WALK-FORWARD PICK: {desc(b[0])}\n      H1 {b[1]} trades {b[2]:+.3f}%/day -> H2 {b[3]} trades {b[4]:+.3f}%/day")


if __name__ == '__main__':
    main()
