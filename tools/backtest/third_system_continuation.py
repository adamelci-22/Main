#!/usr/bin/env python3
"""A THIRD system: ORB continuation (trade WITH the break) alongside the current FADE + PULLBACK, one account, one position at a time.
    python3 tools/backtest/third_system_continuation.py > tools/backtest/results/third_system_continuation.txt
Proxies/legs = the six FADE rows (QQQ SOXX IWM XLK XBI AMD). Box = 9:30-10:00 high/low. Entries 10:00-12:55, out by 13:30, cost 0.06%/trade.
Families (all trade direction = direction of the break):
  ORB    first 5-min close outside the box (by `jmax`), enter next open; optional volume filter (bar vol > 1.5x prior-6 avg) and VWAP filter
  LATE   after the first break held 6+ bars outside the box edge, a close above the prior-6-bar high (11:00-12:30) -> enter next open
Stops: mid (box midpoint) | box (opposite edge) | brk (breakout/consolidation low).  Exit: ALL out at N x R, stop, or 13:30.
Judged per rulebook D3: both halves AND the untouched March window (3 Mar - 6 Apr).  The grid below is ~100 variants: expect a few to look
good by luck alone; only a variant positive in H1, H2 AND March, AND lifting the COMBINED account, deserves a second look.
"""
import itertools, math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, twobar as TB, fade_addone as FA, final_system as FS
from lab import get_data

LAST = 48            # 13:30 bar index
KMAX = 41            # last entry bar (12:55)

def direction_space(raw, side):
    if side > 0: return raw, (lambda x: x)
    b, p0 = m.mirror(raw); return b, (lambda x, p0=p0: 2 * p0 - x)

def vwap_ok(b, j):
    pv = sum(((x[1] + x[2] + x[3]) / 3) * x[4] for x in b[:j + 1]); v = sum(x[4] for x in b[:j + 1])
    return v > 0 and b[j][3] > pv / v

def signal(raw, fam, jmax, volf, vwapf):
    """Return (k, side, stop_cands dict, entry_real) or None. Stops are in direction space."""
    H = max(x[1] for x in raw[:6]); L = min(x[2] for x in raw[:6])
    for j in range(6, min(jmax, 40) + 1):
        c = raw[j][3]; side = 1 if c > H else -1 if c < L else 0
        if not side: continue
        b, to_m = direction_space(raw, side)
        Hd = max(x[1] for x in b[:6]); Ld = min(x[2] for x in b[:6]); mid = (Hd + Ld) / 2
        if fam == 'ORB':
            if volf and not (j >= 7 and b[j][4] > 1.5 * st.mean(b[q][4] for q in range(j - 6, j))): return None
            if vwapf and not vwap_ok(b, j): return None
            k = j + 1
            if k > KMAX: return None
            return k, side, dict(mid=mid, box=Ld, brk=b[j][2]), raw[k][0]
        # LATE: needs 6 bars outside the edge after the break, then a new 6-bar-high close in 11:00-12:30
        for i in range(j + 6, 37):
            if i < 18: continue
            if min(b[q][2] for q in range(j + 1, i + 1)) <= Hd: return None      # lost the edge: setup dead
            if b[i][3] > max(b[q][1] for q in range(i - 6, i)):
                k = i + 1
                if k > KMAX: return None
                if vwapf and not vwap_ok(b, i): continue
                return k, side, dict(mid=mid, box=Ld, brk=min(b[q][2] for q in range(i - 6, i))), raw[k][0]
        return None
    return None

def trade(D, d, p, row, fam, jmax, volf, vwapf, stop, N):
    raw = D.bars[p][d]
    if len(raw) < 60: return None
    s = signal(raw, fam, jmax, volf, vwapf)
    if not s: return None
    k, side, stops, e_real = s
    b, to_m = direction_space(raw, side); entry = to_m(e_real); st_ = stops[stop]
    if entry <= st_: return None
    r = entry - st_
    pnl, xbar, why = TB.manage(b, k, entry, st_, entry + N * r, 1.0, False, LAST, True, True)
    bull, lb, bear, lbe = row; lev = lb if side > 0 else lbe
    return dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, pct=lev * pnl / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100)

def stats(dl, days, h, mar):
    v = lambda ds: st.mean(dl[d] for d in ds) if ds else 0.0
    return v(days), v(days[:h]), v(days[h:]), v([d for d in days if d in mar])

def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2; mar = {d for d in days if d < '2026-04-07'}
    f, p = FS.cands(D, days); base = MXD.account(D, days, f + p)
    b_all, b1, b2, bm = stats(base['daily'], days, h, mar)
    print(f"THIRD SYSTEM: ORB continuation added to FADE + PULLBACK. {days[0]}..{days[-1]} ({len(days)} days), $2,000, one position, 3% risk, out 13:30.")
    print(f"BASE (FADE+PB only): {b_all:+.3f}%/day (H1 {b1:+.3f} H2 {b2:+.3f} March {bm:+.3f}), ret {base['ret']:+.1f}%, {len(base['taken'])} trades\n")
    print("variant                                              | standalone legs: n  win  avg%  t  H1avg H2avg | COMBINED %/day  d_vs_base  H1   H2   Mar  trades")
    rows = []
    for fam, jmax, volf, vwapf, stop, N in itertools.product(('ORB', 'LATE'), (9, 12), (False, True), (False, True), ('mid', 'box', 'brk'), (0.5, 1.0, 1.5)):
        if fam == 'LATE' and (volf or jmax == 12): continue
        T = [t for pp in FA.ROWS if pp in D.bars and pp in ('QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD')
             for d in days if d in D.bars[pp] for t in [trade(D, d, pp, FA.ROWS[pp], fam, jmax, volf, vwapf, stop, N)] if t]
        if len(T) < 15: continue
        pc = [t['pct'] for t in T]; a1 = [t['pct'] for t in T if t['day'] in set(days[:h])]; a2 = [t['pct'] for t in T if t['day'] in set(days[h:])]
        tt = st.mean(pc) / (st.pstdev(pc) / math.sqrt(len(pc))) if st.pstdev(pc) else 0
        cont = MXD.norm_px(T, 'CONT'); a = MXD.account(D, days, f + p + cont); c_all, c1, c2, cm = stats(a['daily'], days, h, mar)
        name = f"{fam} brk<={'10:15' if jmax == 9 else '10:30'}{' vol' if volf else ''}{' vwap' if vwapf else ''} stop {stop} TP {N}R"
        rows.append((c_all - b_all, name, len(T), 100 * sum(x > 0 for x in pc) / len(pc), st.mean(pc), tt, st.mean(a1) if a1 else 0, st.mean(a2) if a2 else 0, c_all, c1, c2, cm,
                     sum(1 for x in a['taken'] if x['sys'] == 'CONT')))
    rows.sort(reverse=True)
    for r in rows[:25] + [None] + rows[-5:]:
        if r is None: print("   ..."); continue
        d, name, n, w, av, tt, a1, a2, c, c1, c2, cm, nc = r
        print(f"{name:<52} | {n:4d} {w:3.0f}% {av:+.3f} {tt:+.1f} {a1:+.3f} {a2:+.3f} | {c:+.3f} {d:+.3f} {c1:+.3f} {c2:+.3f} {cm:+.3f}  {nc:3d}")
    pos = [r for r in rows if r[6] > 0 and r[7] > 0]
    print(f"\n{len(rows)} variants tried. Standalone positive in BOTH halves: {len(pos)}. Combined account beats base: {sum(1 for r in rows if r[0] > 0)}.")
    good = [r for r in rows if r[0] > 0 and r[9] > b1 and r[10] > b2 and r[11] > bm]
    print(f"Beats the base in H1, H2 AND untouched March (combined): {len(good)}")
    for r in good[:10]: print("   ", r[1], f"{r[8]:+.3f}%/day ({r[0]:+.3f})")

if __name__ == '__main__': main()
