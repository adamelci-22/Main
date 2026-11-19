#!/usr/bin/env python3
"""RELVAL exit and hold study (governor 2026-11-19: "Push the relval system have you worked out the best exit and hold strategy for it").
Research only. Signal fixed at the fade_replace.py train pick: a=48 z=72 xm=1.0 ksd=2.5 (13:35-15:30 signal bars; the sector fund's
open-to-now move minus QQQ's is >= 1% and >= 2.5 sd of its 20-day relative moves -> trade the 3x leg back toward QQQ, entry at the next
bar's open). Exit grid, all in units of the gap (the relative move at the signal, in proxy %):
  TARGET  none / 0.25 / 0.5 (current) / 0.75 / 1.0 gap
  STOP    0.5 / 0.75 / 1.0 (current) / 1.5 / 2.0 gap
  BE      stop to breakeven once a close is 0.25 gap in favour: off / on
  HOLD    out at the 15:55 open (current) / out at the next session's 9:35 open (overnight; shares cash with OVERNIGHT, counted below)
Judged inside the live joint book without FADE (PULLBACK, IBS-LONG, MIRROR, DIP, overnight leg 50%), RELVAL in FADE's slot.
Pre-set rule: the PICK is the variant with the best TRAIN (2022, 2024, 2026) compounded book that also beats the current RELVAL exit in
2 of 3 train years; it is read against TEST (2023, 2025) only after it is chosen. If none beats the current exit on train, it stays.
    python3 -I tools/backtest/relval_exit.py > tools/backtest/results/relval_exit_2026-11-19.txt"""
import itertools, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_replace as FR
import new_systems as NS
B, BA, SB, TB, dm, TR, TE, book, base = FR.B, FR.BA, FR.SB, FR.TB, FR.dm, FR.TR, FR.TE, FR.book, FR.base
END = NS.END; COST = NS.COST; ds, ctx = B.ds, B.ctx
_rel = {}


def relx(ds, ctx, p, d, b, a=48, z=72, xm=1.0, ksd=2.5, tg=0.5, sm=1.0, be=False, hold='close'):
    if p == 'QQQ': return None
    q = ds.bars['QQQ'].get(d)
    if not q or len(q) < 78: return None
    if p not in _rel:
        _rel[p] = {x: (ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0]) for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']}
    i = ds.idx[d]; hist = [_rel[p][x] for x in ds.days[max(0, i - 20):i] if x in _rel[p]]
    if len(hist) < 15: return None
    sd = st.pstdev(hist) or 1e-9
    for j in range(a, z):
        rp = b[j][3] / b[0][0] - q[j][3] / q[0][0]
        if abs(rp) * 100 >= xm and abs(rp) >= ksd * sd:
            s = -1 if rp > 0 else 1; k = j + 1; e = b[k][0]; gap = abs(rp) * e
            stop = e - s * sm * gap; T = e + s * tg * gap if tg else None; r = sm * gap; bet = e + s * 0.25 * gap
            nb = None
            if hold == 'next':
                nd = ds.days[i + 1] if i + 1 < len(ds.days) else None; nb = ds.bars[p].get(nd) if nd else None
                if not nb or len(nb) < 2: return None
            seq = [(b, jj) for jj in range(k, END + 1)] + ([(nb, 0)] if nb else [])
            for n, (bb, jj) in enumerate(seq):
                o, h, l, c, v = bb[jj]
                last = n == len(seq) - 1
                if last: px = o; break
                fav, adv = (h, l) if s > 0 else (l, h)
                if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; break
                if T is not None and (fav - T) * s >= 0: px = T if (o - T) * s <= 0 else o; break
                if be and (c - bet) * s >= 0 and (e - stop) * s > 0: stop = e
            x = min(k + n, END)
            return dict(day=d, proxy=p, k=k, xbar=END if hold == 'next' else x, pct=3 * (px - e) * s / e * 100 - COST, leg_risk=max(3 * r / e * 100, 0.3),
                        night=hold == 'next')
    return None


def trades(**kw): return B.BC.new(ds, ctx, dm, relx, kw, 0)


def stat(T):
    p = [t['pct'] for t in T]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x <= 0)
    return f"n {len(p)} win {100 * np.mean([x > 0 for x in p]):.0f}% avg {np.mean(p):+.2f}% PF {g / l if l else 99:.2f}"


def cmp_(y, idx): return (np.prod(1 + y[idx] / 100) - 1) * 100


def main():
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 | TRAIN and TEST compounded, (points vs the current RELVAL exit) | RELVAL trades alone\n')
    cur_T = trades(); cur = book(cur_T)
    def row(tag, y, T, mark=''):
        print(f"   {mark:<5}{tag:<40} {' '.join(f'{a:+7.1f}' for a in y)} | TRAIN {cmp_(y, TR):+7.1f} ({cmp_(y, TR) - cmp_(cur, TR):+6.1f}) TEST {cmp_(y, TE):+6.1f} ({cmp_(y, TE) - cmp_(cur, TE):+6.1f}) | {stat(T)}", flush=True)
    print(f"   {'':<5}{'BASE: book without FADE, no RELVAL':<40} {' '.join(f'{a:+7.1f}' for a in base)} | TRAIN {cmp_(base, TR):+7.1f} TEST {cmp_(base, TE):+6.1f}")
    row('CURRENT: target 0.5, stop 1.0, out 15:55', cur, cur_T, 'cur')
    res = []
    for tg, sm, be, hold in itertools.product((None, 0.25, 0.5, 0.75, 1.0), (0.5, 0.75, 1.0, 1.5, 2.0), (False, True), ('close', 'next')):
        T = trades(tg=tg, sm=sm, be=be, hold=hold); y = book(T)
        tag = f"tgt {tg if tg else 'none'} stop {sm} be {'on' if be else 'off'} {'15:55' if hold == 'close' else 'next 9:35'}"
        q = cmp_(y, TR) > cmp_(cur, TR) and (y[TR] > cur[TR]).sum() >= 2
        res.append((tag, y, T, q))
    print('\nTOP 20 BY TRAIN (all 100 variants run; q = beats the current exit on train compounded and in 2 of 3 train years)')
    for tag, y, T, q in sorted(res, key=lambda r: -cmp_(r[1], TR))[:20]: row(tag, y, T, 'q' if q else '')
    qs = [r for r in res if r[3]]
    print('\nBY DIMENSION (average TRAIN / TEST compounded over the variants holding that value)')
    for name, keyf in (('target', lambda t: t.split()[1]), ('stop', lambda t: t.split()[3]), ('breakeven', lambda t: t.split()[5]), ('hold', lambda t: ' '.join(t.split()[6:]))):
        vals = sorted({keyf(r[0]) for r in res})
        print(f"   {name:<10} " + ' | '.join(f"{v}: {np.mean([cmp_(r[1], TR) for r in res if keyf(r[0]) == v]):+6.1f} / {np.mean([cmp_(r[1], TE) for r in res if keyf(r[0]) == v]):+6.1f}" for v in vals))
    if qs:
        pick = max(qs, key=lambda r: cmp_(r[1], TR))
        print(f"\nPICK (best TRAIN among variants that beat the current exit on train, chosen before reading TEST): {pick[0]}")
        row('PICK', pick[1], pick[2], 'PICK')
        print(f"   test verdict: {'beats the current exit in both test years' if (pick[1][TE] > cur[TE]).all() else 'beats it in one test year' if (pick[1][TE] > cur[TE]).any() else 'loses to the current exit in both test years'}")
        if 'next' in pick[0]:
            ovd = {d for d in O_nights()}; n = sum(1 for t in pick[2] if t['day'] in ovd)
            print(f"   overnight overlap: {n} of {len(pick[2])} RELVAL nights also have an OVERNIGHT signal (they share cash live; not modelled)")
    else:
        print('\nNo variant beats the current exit on train: the current exit stays.')


def O_nights():
    S = FR.O.signals(); return {dm[i] for i, d in enumerate(dm[:-1]) if dm[i + 1] in S and any(t['kind'] == 'long' for t in S[dm[i + 1]])}


if __name__ == '__main__':
    main()
