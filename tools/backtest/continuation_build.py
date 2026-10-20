#!/usr/bin/env python3
"""Continuation system built from scratch with the same process the FADE went through (standalone, ignoring FADE/PULLBACK).
    python3 tools/backtest/continuation_build.py > tools/backtest/results/continuation_build.txt
Tuning window = 2026-04-07..10-14 (same as the fade's research), split H1 / H2. Every choice is made on H1 only and then judged on H2.
March 3 - Apr 6 is held back and looked at once, at the end (it was never used to pick anything).
Stages:  1 entry family x stop (neutral exit)  ->  2 filters  ->  3 exits (target R x fraction x runner x sell-by)  ->  4 proxy list
         ->  5 final: H2 + untouched March, account, cost stress, and a luck check (how good the best of N looks when there is no edge).
Pool: 21 proxies with leveraged legs (fade_addone.ROWS); legs must trade >= $250k per 5-min bar (expand_lists.LIQ).
Leg return = leverage x proxy return - 0.06%. Account: $2,000, 3% risk capped at cash, one position at a time, entries 10:00-12:55.
"""
import collections, itertools, math, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, twobar as TB, fade_addone as FA, expand_lists as EX
from lab import get_data

KMAX = 41                      # last entry bar (12:55)
TN = {29: '12:00', 35: '12:30', 48: '13:30', 77: '15:55'}


def dspace(raw, side):
    if side > 0: return raw, (lambda x: x)
    b, p0 = m.mirror(raw); return b, (lambda x, p0=p0: 2 * p0 - x)


def setup(raw, fam, brk=9, W=12, tol=0.10, hold=6, lb=6, start=18, end=36):
    """First 5-min close outside the 9:30-10:00 box (by bar `brk`), then the family's entry trigger.
    Returns dict(k, side, j, e, stops) with stops in direction space, or None."""
    H = max(x[1] for x in raw[:6]); L = min(x[2] for x in raw[:6])
    for j in range(6, brk + 1):
        c = raw[j][3]; side = 1 if c > H else -1 if c < L else 0
        if not side: continue
        b, to_m = dspace(raw, side)
        Hd = max(x[1] for x in b[:6]); Ld = min(x[2] for x in b[:6]); mid = (Hd + Ld) / 2
        mk = lambda k, i: None if k > KMAX else dict(k=k, side=side, j=j, i=i, e=raw[k][0],
                                                     stops=dict(mid=mid, box=Ld, edge=Hd * (1 - 0.001), swing=min(x[2] for x in b[j:k])))
        if fam == 'ORB': return mk(j + 1, j)
        if fam in ('HOLD', 'RECLAIM'):
            touched = False
            for i in range(j + 1, min(j + 1 + W, 40)):
                o, h, l, cc, v = b[i]
                if not touched:
                    if l <= Hd * (1 + tol / 100):
                        touched = True
                        if cc > Hd: return mk(i + 1, i)
                        if fam == 'HOLD': return None
                    continue
                if l <= mid: return None
                if cc > Hd: return mk(i + 1, i)
            return None
        if fam == 'FLAG':      # first pullback after the break that stays above the edge, then a close above the prior bar's high
            for i in range(j + 2, min(j + 1 + W, 40)):
                if min(b[q][2] for q in range(j + 1, i + 1)) <= Hd: return None
                pb = b[i - 1][3] < b[i - 1][0] or b[i - 1][1] < b[i - 2][1]
                if pb and b[i][3] > b[i - 1][1]: return mk(i + 1, i)
            return None
        if fam == 'LATE':
            for i in range(max(j + hold, start), end + 1):
                if min(b[q][2] for q in range(j + 1, i + 1)) <= Hd: return None
                if b[i][3] > max(b[q][1] for q in range(i - lb, i)): return mk(i + 1, i)
            return None
    return None


def manage(b, k, entry, stop, R, frac, runner, last):
    """Direction space. Target = entry + R x risk (OCO, fills at the level); frac sold there; the rest: 'be' = breakeven,
    'chand2' = breakeven then 2-ATR chandelier ratchet (as the fade). frac=1 sells everything at the target."""
    r = entry - stop; T = entry + R * r if R else None; gross = 0.0; rem = 1.0; hit = False; hic = entry
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            gross += rem * (min(stop, o) - entry); return gross, j
        if T is not None and not hit and h >= T:
            gross += frac * (max(T, o) - entry); rem -= frac; hit = True
            if rem <= 1e-9: return gross, j
            stop = max(stop, entry)
        hic = max(hic, c)
        if hit and runner == 'chand2': stop = max(stop, hic - 2 * m.atr(b, j))
    return gross + rem * (b[last][3] - entry), last


class Ctx:
    def __init__(self, D, pool):
        self.D = D; self.pool = pool; self.idx = {d: i for i, d in enumerate(D.days)}; self.pre = {}
        for p in pool:
            for d in D.days:
                if d not in D.bars[p]: continue
                i = self.idx[d]
                if i < 6: continue
                prev = [D.days[i - q] for q in range(1, 21) if i - q >= 0 and D.days[i - q] in D.bars[p]]
                if len(prev) < 5: continue
                pc = D.bars[p][prev[0]][-1][3]
                widths = []
                for x in prev:
                    bb = D.bars[p][x]; widths.append((max(y[1] for y in bb[:6]) - min(y[2] for y in bb[:6])) / bb[0][0])
                self.pre[(p, d)] = dict(pc=pc, mw=st.median(widths), ma5=st.mean(D.bars[p][x][-1][3] for x in prev[:5]))


def filters_ok(cx, p, d, raw, s, flt):
    if not flt: return True
    pre = cx.pre.get((p, d))
    if pre is None: return False
    side, j, k = s['side'], s['j'], s['k']
    b, to_m = dspace(raw, side)
    for f in flt:
        if f == 'vol':
            ref = [b[q][4] for q in range(max(0, j - 6), j)]
            if not (ref and b[j][4] > 1.5 * st.mean(ref)): return False
        elif f == 'vwap':
            pv = sum(((x[1] + x[2] + x[3]) / 3) * x[4] for x in b[:k]); v = sum(x[4] for x in b[:k])
            if not (v and b[k - 1][3] > pv / v): return False
        elif f == 'gap':
            if side * (raw[0][0] - pre['pc']) <= 0: return False
        elif f == 'trend':
            if side * (pre['pc'] - pre['ma5']) <= 0: return False
        elif f == 'rvol':
            if TB.rvol(cx.D, p, d, j) < 1.2: return False
        elif f == 'narrow':
            if (max(x[1] for x in raw[:6]) - min(x[2] for x in raw[:6])) / raw[0][0] >= pre['mw']: return False
        elif f == 'wide':
            if (max(x[1] for x in raw[:6]) - min(x[2] for x in raw[:6])) / raw[0][0] < pre['mw']: return False
    return True


def trades(cx, days, fam, stop='mid', R=1.0, frac=1.0, runner='be', last=48, flt=(), pool=None, extra=0.0, **kw):
    out = []
    for p in pool or cx.pool:
        bull, lb_, bear, lbe = FA.ROWS[p]
        for d in days:
            if d not in cx.D.bars[p]: continue
            raw = cx.D.bars[p][d]
            if len(raw) <= last: continue
            s = setup(raw, fam, **kw)
            if not s or s['k'] > last - 1 or not filters_ok(cx, p, d, raw, s, flt): continue
            b, to_m = dspace(raw, s['side']); entry = to_m(s['e']); sp = s['stops'][stop]
            if entry <= sp: continue
            g, xb = manage(b, s['k'], entry, sp, R, frac, runner, last)
            lev = lb_ if s['side'] > 0 else lbe
            out.append(dict(day=d, proxy=p, side=s['side'], k=s['k'], xbar=xb, pct=lev * g / s['e'] * 100 - TB.LEGCOST - extra,
                            leg_risk=lev * (entry - sp) / s['e'] * 100))
    return out


def sig_stats(T):
    pc = [t['pct'] for t in T]
    if len(pc) < 3: return len(pc), 0.0, 0.0, 0.0
    sd = st.pstdev(pc)
    return len(pc), st.mean(pc), (st.mean(pc) / (sd / math.sqrt(len(pc))) if sd else 0.0), 100 * sum(x > 0 for x in pc) / len(pc)


def acct(D, days, T):
    a = MXD.account(D, days, MXD.norm_px(T, 'CONT')); dl = a['daily']
    return st.mean(dl[d] for d in days), a


def line(T1, T2):
    n1, a1, t1, w1 = sig_stats(T1); n2, a2, t2, w2 = sig_stats(T2)
    return f"H1 n {n1:3d} avg {a1:+.3f}% t {t1:+.1f} win {w1:3.0f}% | H2 n {n2:3d} avg {a2:+.3f}% t {t2:+.1f} win {w2:3.0f}%"


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    tune = D.days[25:]; h = len(tune) // 2; H1, H2 = tune[:h], tune[h:]; MAR = D.days[1:25]
    liq = [p for p in FA.ROWS if p in D.bars and all(r in D.bars and EX.dollar_vol(D, r, tune) >= EX.LIQ for r in (FA.ROWS[p][0], FA.ROWS[p][2]))]
    cx = Ctx(D, liq); tried = 0
    print(f"CONTINUATION BUILD  tuning {tune[0]}..{tune[-1]} ({len(tune)} days): H1 {H1[0]}..{H1[-1]}, H2 {H2[0]}..{H2[-1]}; untouched March {MAR[0]}..{MAR[-1]}")
    print(f"Pool ({len(liq)} liquid proxies): {' '.join(liq)}\n")

    # ---------------- STAGE 1: entry family x stop, neutral exit (all out at 1R, else 13:30)
    print("== STAGE 1: entry family x stop (exit: all out at 1R / stop / 13:30). Ranked by H1 avg leg %. ==")
    res = []
    for fam in ('ORB', 'HOLD', 'RECLAIM', 'FLAG', 'LATE'):
        for brk in (9, 12):
            for stop in ('mid', 'edge', 'swing', 'box'):
                if stop == 'edge' and fam == 'ORB': continue
                cfg = dict(fam=fam, brk=brk, stop=stop); tried += 1
                T1 = trades(cx, H1, **cfg); n, a, t, w = sig_stats(T1)
                res.append((a, cfg, T1))
    res.sort(key=lambda r: -r[0])
    for a, cfg, T1 in res[:12] + res[-3:]:
        print(f"   {cfg['fam']:<8} break by {'10:15' if cfg['brk'] == 9 else '10:30'} stop {cfg['stop']:<6} {line(T1, trades(cx, H2, **cfg))}")
    top = [r[1] for r in res if r[0] > 0 and sig_stats(r[2])[0] >= 30][:4]
    print(f"   -> carried forward (H1 avg > 0, >= 30 H1 signals): {[(c['fam'], c['brk'], c['stop']) for c in top]}\n")
    if not top:
        print("No entry family is positive on H1 with enough signals. Stop here."); return

    # ---------------- STAGE 2: filters on the carried families
    print("== STAGE 2: filters (single and pairs) on each carried entry. Ranked by H1 avg leg %, needs >= 25 H1 signals. ==")
    FL = ('vol', 'vwap', 'gap', 'trend', 'rvol', 'narrow', 'wide')
    res2 = []
    for cfg in top:
        for flt in [()] + [(f,) for f in FL] + [c for c in itertools.combinations(FL, 2) if not ('narrow' in c and 'wide' in c)]:
            tried += 1; T1 = trades(cx, H1, flt=flt, **cfg); n, a, t, w = sig_stats(T1)
            if n >= 25: res2.append((a, dict(cfg, flt=flt), T1))
    res2.sort(key=lambda r: -r[0])
    for a, cfg, T1 in res2[:12]:
        print(f"   {cfg['fam']:<8} {'10:15' if cfg['brk'] == 9 else '10:30'} {cfg['stop']:<6} filters {'+'.join(cfg['flt']) or 'none':<14} {line(T1, trades(cx, H2, **cfg))}")
    best2 = res2[0][1]
    print(f"   -> carried forward: {best2}\n")

    # ---------------- STAGE 3: exits
    print("== STAGE 3: exits on the chosen entry (target R x fraction sold x runner x sell-by). Ranked by H1 account %/day. ==")
    res3 = []
    for R, frac, runner, last in itertools.product((0.5, 1.0, 1.5, 2.0, 3.0, None), (1.0, 0.5, 1 / 3), ('be', 'chand2'), (29, 35, 48, 77)):
        if (frac == 1.0 or R is None) and runner == 'chand2': continue
        if R is None and frac != 1.0: continue
        cfg = dict(best2, R=R, frac=frac, runner=runner, last=last); tried += 1
        T1 = trades(cx, H1, **cfg); a1, _ = acct(D, H1, T1); res3.append((a1, cfg, T1))
    res3.sort(key=lambda r: -r[0])
    for a1, cfg, T1 in res3[:10]:
        T2 = trades(cx, H2, **cfg); a2, _ = acct(D, H2, T2)
        ex = 'no target' if cfg['R'] is None else f"{cfg['R']}R sell {cfg['frac']:.2f} runner {cfg['runner']}"
        print(f"   {ex:<34} out {TN[cfg['last']]}  H1 acct {a1:+.3f}%/day  H2 acct {a2:+.3f}%/day | {line(T1, T2)}")
    best3 = res3[0][1]
    print(f"   -> carried forward: {best3}\n")

    # ---------------- STAGE 4: proxy list
    print("== STAGE 4: proxy list. Each proxy on H1 (chosen config); keep those with H1 avg > 0 and >= 3 signals. ==")
    keep = []
    for p in liq:
        T1 = trades(cx, H1, pool=[p], **best3); T2 = trades(cx, H2, pool=[p], **best3); n1, a1, t1, w1 = sig_stats(T1); n2, a2, _, _ = sig_stats(T2)
        mark = ''
        if n1 >= 3 and a1 > 0: keep.append(p); mark = '  keep'
        print(f"   {p:<5} H1 n {n1:3d} avg {a1:+.3f}%   H2 n {n2:3d} avg {a2:+.3f}%{mark}")
    tried += len(liq)
    print(f"   -> list: {keep}\n")
    final = dict(best3, pool=keep)

    # ---------------- STAGE 5: verdict
    print("== STAGE 5: the final system, judged where it was NOT tuned ==")
    for lab, ds in (('H1 (tuned here)', H1), ('H2 (out of sample)', H2), ('March (untouched)', MAR), ('ALL 157 days', D.days[1:])):
        T = trades(cx, ds, **final); n, a, t, w = sig_stats(T); ad, A = acct(D, ds, T)
        print(f"   {lab:<20} signals {n:3d} avg leg {a:+.3f}% t {t:+.1f} win {w:3.0f}% | account {len(A['taken']):3d} trades {ad:+.3f}%/day ret {A['ret']:+6.1f}% DD {A['mdd']:4.1f}%")
    print("   same system on the FULL pool (no list selection), H2:", end=' ')
    T = trades(cx, H2, **best3); n, a, t, w = sig_stats(T); ad, _ = acct(D, H2, T); print(f"signals {n} avg {a:+.3f}% t {t:+.1f} acct {ad:+.3f}%/day")
    print("   cost stress (extra % per trade, all 157 days, account %/day):", end=' ')
    for ex in (0.1, 0.2, 0.4):
        ad, _ = acct(D, D.days[1:], trades(cx, D.days[1:], extra=ex, **final)); print(f"+{ex}: {ad:+.3f}", end='  ')
    print()
    # luck check: flip each H1 signal's sign at random -> how good does the best of the stage-2 search look with zero edge?
    print(f"\n   variants tried across stages: about {tried}")
    rng = random.Random(7); base = res2
    best_null = []
    for _ in range(200):
        best_null.append(max(st.mean([t['pct'] * (1 if rng.random() < .5 else -1) for t in T1]) for a, cfg, T1 in base))
    best_null.sort()
    print(f"   luck check (stage 2, {len(base)} variants): with ZERO edge the best H1 avg would be ~{st.median(best_null):+.3f}% (95th pct {best_null[189]:+.3f}%); "
          f"our best H1 avg was {res2[0][0]:+.3f}%")


if __name__ == '__main__': main()
