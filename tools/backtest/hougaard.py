#!/usr/bin/env python3
"""Tom Hougaard day-based setups (governor 2026-11-16: "can you incorporate this"). Research only. Same method as the other studies:
proxies QQQ SOXX IWM XLK XBI XLF, trade the 3x long leg or the 3x inverse leg, Massive tape 2022-2026, cost 0.06%, signals on a 5-minute
close with entry at the next open. Train 2022/2024/2026, test 2023/2025. A setup is judged alone and as an ADDITION to the live book
(v5.2.52), where it only trades when the account is free. PASS = beats the book on train compounded and in 2 of 3 train years, then in both test years.
  TFM    Thursday-Friday-Monday: Friday's high did not exceed Thursday's -> the next session closes below Friday's low -> inverse leg
  MTWT   Monday's high above Tuesday's and Wednesday's -> Thursday closes below Wednesday's low -> inverse leg
  MONFB  failed break of Monday's range on Tue-Fri: a close beyond Monday's high/low, back inside within 12 bars -> fade it
  GAP    gap of >= x% away from the prior close (Tuesday and Friday, or every day) -> trade toward the prior close
  SCHOOL second 15-minute bar (9:45-10:00): first close beyond its high/low after 10:00 -> trade the break, stop at the other side
  FIRSTB first 15-minute bar (9:30-9:45): first close beyond its high/low, in the direction of the bar (First Bar Positive / Negative)
  RULE4  FOMC days: the first four 5-minute bars after 14:00 set a range; the first close beyond it -> trade the break, stop at the other side
    python3 -I tools/backtest/hougaard.py > tools/backtest/results/hougaard_2026-11-16.txt"""
import datetime as dt, itertools, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import overnight as O
B, BA, BM, SB, N2, NS, TB = O.B, O.BA, O.BM, O.SB, O.N2, O.NS, O.TB; TR, TE = O.TR, O.TE; dm = O.dm; ds = B.ds; PX = NS.PX[:0] or list(__import__('fade_diag').LIVE)
mg, fin = NS.mg, NS.fin; END = NS.END
FOMC = '''2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14 2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28'''.split()
wd = lambda d: dt.date.fromisoformat(d).weekday()
days = [d for d in ds.days if d in ds.bars['QQQ']]; ix = {d: i for i, d in enumerate(days)}
def dly(p, d): b = ds.bars[p][d]; return max(x[1] for x in b), min(x[2] for x in b), b[-1][3], b[0][0]
def prev(d, n=1): i = ix[d] - n; return days[i] if i >= 0 else None
def cons(d1, d2): return (dt.date.fromisoformat(d2) - dt.date.fromisoformat(d1)).days <= 4        # consecutive sessions, allowing a weekend or one holiday


def trade(p, d, b, j, s, stop_px, last=END, tgt=None):
    """Signal on the close of bar j: enter at the open of bar j+1, side s (+1 long leg, -1 inverse leg)."""
    k = j + 1
    if k >= last - 1: return None
    e = b[k][0]
    if (e - stop_px) * s <= 0: return None
    risk = abs(e - stop_px)
    if risk < 0.003 * e: stop_px = e - s * 0.003 * e
    x, g, r = mg(b, k, s, e, stop_px, last, T=tgt); t = fin(d, p, k, x, e, g, r); t['rv'] = ds.rvol(p, d, k); return t


def first_close(b, a, z, level, up):
    for j in range(a, z):
        if (b[j][3] > level) if up else (b[j][3] < level): return j
    return None


def tfm(p, d, b, last=END, stop='pct'):
    f = prev(d); th = prev(d, 2) if f else None
    if not th or wd(f) != 4 or wd(th) != 3 or not cons(th, f) or not cons(f, d): return None
    fh, fl, _, _ = dly(p, f); thh = dly(p, th)[0]
    if fh > thh: return None
    j = first_close(b, 0, 70, fl, False)
    if j is None: return None
    return trade(p, d, b, j, -1, b[j + 1][0] * 1.01 if j + 1 < len(b) else fl * 1.01, last)


def mtwt(p, d, b, last=END):
    if wd(d) != 3: return None
    w = prev(d); t = prev(d, 2); m = prev(d, 3)
    if not m or wd(w) != 2 or wd(t) != 1 or wd(m) != 0 or not (cons(m, t) and cons(t, w) and cons(w, d)): return None
    if not (dly(p, m)[0] > dly(p, t)[0] and dly(p, m)[0] > dly(p, w)[0]): return None
    wl = dly(p, w)[1]; j = first_close(b, 0, 70, wl, False)
    return trade(p, d, b, j, -1, b[j + 1][0] * 1.01, last) if j is not None else None


def monfb(p, d, b, last=END):
    if wd(d) not in (1, 2, 3, 4): return None
    i = ix[d]; mon = next((days[q] for q in range(i - 1, max(i - 5, -1), -1) if wd(days[q]) == 0), None)
    if not mon or (dt.date.fromisoformat(d) - dt.date.fromisoformat(mon)).days > 4: return None
    mh, ml, _, _ = dly(p, mon)
    for lvl, up in ((mh, True), (ml, False)):
        j = first_close(b, 0, 60, lvl, up)
        if j is None: continue
        for q in range(j + 1, min(j + 13, 70)):
            if (b[q][3] < lvl) if up else (b[q][3] > lvl):
                ext = max(x[1] for x in b[j:q + 1]) if up else min(x[2] for x in b[j:q + 1])
                return trade(p, d, b, q, -1 if up else 1, ext * (1.0005 if up else 0.9995), last)
    return None


def gap(p, d, b, gm=0.5, dow='tf', last=END):
    f = prev(d)
    if not f or (dow == 'tf' and wd(d) not in (1, 4)): return None
    pc = dly(p, f)[2]; g = (b[0][0] / pc - 1) * 100
    if abs(g) < gm: return None
    s = 1 if g < 0 else -1; e = b[1][0]
    return trade(p, d, b, 0, s, e * (1 - s * 0.01), last, tgt=pc)


def school(p, d, b, last=END, mode='break'):
    H = max(x[1] for x in b[3:6]); L = min(x[2] for x in b[3:6])
    for j in range(6, 40):
        if b[j][3] > H: return trade(p, d, b, j, 1, L, last)
        if b[j][3] < L: return trade(p, d, b, j, -1, H, last)
    return None


def firstb(p, d, b, last=END, same=True):
    H = max(x[1] for x in b[:3]); L = min(x[2] for x in b[:3]); col = 1 if b[2][3] > b[0][0] else -1
    for j in range(3, 30):
        if b[j][3] > H and (not same or col > 0): return trade(p, d, b, j, 1, L, last)
        if b[j][3] < L and (not same or col < 0): return trade(p, d, b, j, -1, H, last)
    return None


def rule4(p, d, b, last=END):
    if d not in FOMC: return None
    H = max(x[1] for x in b[54:58]); L = min(x[2] for x in b[54:58])
    for j in range(58, 74):
        if b[j][3] > H: return trade(p, d, b, j, 1, L, last)
        if b[j][3] < L: return trade(p, d, b, j, -1, H, last)
    return None


def gen(fn, **kw):
    out = []
    for d in days:
        if d < '2022-01-03': continue
        for p in PX:
            b = ds.bars[p][d]
            if len(b) < 78: continue
            t = fn(p, d, b, **kw)
            if t: t['sys'] = 7; t['proxy'] = p; out.append(t)
    return out


def main():
    F0 = B.fade_trades(); P0 = B.pb_trades(); I0 = B.ibs_trades(sid=4); M = B.BC.new(ds, B.ctx, dm, BM.mirror_fn, dict(hi=0.95, n=20), 5); D = B.BC.new(ds, B.ctx, dm, N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)
    S = O.signals(); onl = {d: max([t for t in v if t['kind'] == 'long'], key=lambda t: t['rv']) for d, v in S.items() if any(t['kind'] == 'long' for t in v)}
    ovn = np.array([0.5 * onl[d]['pct'] / 100 if d in onl else 0.0 for d in dm]); base = F0 + P0 + I0 + M + D
    yb = SB.yret((1 + BA.acct(dm, TB.byday(base), after_stop=False)[0]) * (1 + ovn) - 1)
    print(__doc__.split('\n')[0]); print(f"   FOMC dates checked against the tape: " + ', '.join(f"{d} range {100 * (max(x[1] for x in ds.bars['QQQ'][d][54:58]) / min(x[2] for x in ds.bars['QQQ'][d][54:58]) - 1):.2f}%" for d in FOMC[:0]) or '')
    # sanity: is the 14:00-14:20 range bigger than a normal day's on FOMC dates
    def r4(d): b = ds.bars['QQQ'][d]; return 100 * (max(x[1] for x in b[54:58]) / min(x[2] for x in b[54:58]) - 1)
    fo = [r4(d) for d in FOMC if d in ds.bars['QQQ'] and len(ds.bars['QQQ'][d]) >= 78]; ot = [r4(d) for d in days if d not in FOMC and d >= '2022-01-03' and len(ds.bars['QQQ'][d]) >= 78]
    print(f"   date check: QQQ range of the four bars after 14:00: FOMC days mean {np.mean(fo):.3f}% (n {len(fo)}) vs other days {np.mean(ot):.3f}% (n {len(ot)}): {'dates plausible' if np.mean(fo) > 1.3 * np.mean(ot) else 'NO CLEAR SPIKE: dates unreliable'}")
    print(f"   BASELINE book + overnight: {' '.join(f'{x:+7.1f}' for x in yb)} | avg 22-25 {yb[:4].mean():+.1f}\n   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th). alone = that setup only at full cash; book = added to the live book.\n")
    GRID = [('TFM', tfm, [dict(last=END), dict(last=48)]), ('MTWT', mtwt, [dict(last=END), dict(last=48)]), ('MONFB', monfb, [dict(last=END), dict(last=48)]),
            ('GAP Tue+Fri', gap, [dict(gm=g, dow='tf', last=l) for g in (0.3, 0.5, 1.0) for l in (END, 48)]), ('GAP every day', gap, [dict(gm=g, dow='all', last=l) for g in (0.3, 0.5, 1.0) for l in (END, 48)]),
            ('SCHOOL', school, [dict(last=END), dict(last=48)]), ('FIRSTB same dir', firstb, [dict(last=END, same=True), dict(last=48, same=True)]), ('FIRSTB either', firstb, [dict(last=END, same=False), dict(last=48, same=False)]),
            ('RULE4 FOMC', rule4, [dict(last=END)])]
    npass = 0
    for name, fn, kws in GRID:
        print(name)
        for kw in kws:
            T = gen(fn, **kw)
            if not T: print(f"     {str(kw):<44} no signals"); continue
            alone = SB.yret(BA.acct(dm, TB.byday(T), after_stop=False)[0]); y = SB.yret((1 + BA.acct(dm, TB.byday(base + T), after_stop=False)[0]) * (1 + ovn) - 1)
            p = [t['pct'] for t in T]; gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
            q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2; v = 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''
            npass += v == 'PASS'
            print(f"   {v:<5}{str(kw):<44} n {len(T):4d} win {100 * np.mean([x > 0 for x in p]):3.0f}% avg {np.mean(p):+.2f}% PF {gw / gl if gl else 9:4.2f} | alone {' '.join(f'{x:+6.1f}' for x in alone)} | book avg 22-25 {y[:4].mean():+6.1f} ({y[:4].mean() - yb[:4].mean():+5.1f}) test {y[TE[0]] - yb[TE[0]]:+5.1f} {y[TE[1]] - yb[TE[1]]:+5.1f}")
        print()
    print(f"   PASS count: {npass}")


if __name__ == '__main__':
    main()
