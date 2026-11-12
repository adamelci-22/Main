#!/usr/bin/env python3
"""PULLBACK entry deep dive (governor 2026-11-12). Parametric copy of paper.pullback (defaults = live, tunables v4: vol 1.3x).
Exit = live (100% at the morning high, stop, 13:30), so only the entry changes. Part 1: signal parameters one at a time.
Part 2: entry-time filters (keep set chosen on MASSIVE H1, judged on MASSIVE H2 and Robinhood 2026).
    python3 -I tools/backtest/entry_pb.py > tools/backtest/results/entry_pb_2026-11-12.txt"""
import math, os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'live'))
import fade_diag as F, pb_exit_screen as PS, paper as PP
LIVE = dict(vol=1.3, dips=(2, 3, 4, 5), zlo=0.995, zhi=1.001, j0=8, j1=41, minstop=0.75, buf=0.05, hodx=0.75, hodpct=0.25,
            trend=True, entry='limit', orh=3, brk=True)


def signal(b, prev, P):
    ser = [x[3] for x in prev] + [x[3] for x in b]
    e9 = PP.ema(ser, 9)[len(prev):]; e20 = PP.ema(ser, 20)[len(prev):]
    bh = max(x[1] for x in b[:P['orh']])
    for j in range(P['j0'], min(P['j1'], 77)):
        if P['trend'] and not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in P['dips']:
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * P['zlo'] <= low <= e9[j - 1] * P['zhi']): continue
            pre = j - n
            if P['brk'] and not any(b[i][3] > bh and b[i][4] > P['vol'] * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = math.floor(max(b[i][1] for i in range(0, pre)) * 100 + 1e-9) / 100; stop = low * (1 - P['buf'] / 100); lim = b[j][3]
            if j + 1 > 47: return None
            if P['entry'] == 'limit':
                if b[j + 1][2] > lim: continue
                entry = min(b[j + 1][0], lim)
            else: entry = b[j + 1][0]
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < P['minstop']: continue
            if (hod - entry) < P['hodx'] * (entry - stop) or (hod - entry) / entry * 100 < P['hodpct']: continue
            if hod - stop < 0.10: continue
            return dict(k=j + 1, entry=entry, stop=stop, T=hod, j=j, n=n, e9=e9, e20=e20, low=low)
    return None


class PB2:
    def __init__(self, B, P):
        self.name, self.ds, self.days = B.name, B.ds, B.days; E = []
        for s in sorted({t['proxy'] for t in B.E} | set(PS.LEGS_RH if 'RH' in B.name else PS.LEGS_M)):
            for d in B.days:
                i = B.ds.idx[d]
                if s not in B.ds.bars or d not in B.ds.bars[s] or i == 0 or B.ds.days[i - 1] not in B.ds.bars[s]: continue
                b = B.ds.bars[s][d]; pv = B.ds.bars[s][B.ds.days[i - 1]]; x = signal(b, pv, P)
                if x: t = dict(day=d, proxy=s, b=b, prev=pv, **{k: x[k] for k in ('k', 'entry', 'stop', 'T')}); PS.prep(t); t['sig'] = x; E.append(t)
        self.E = E


BASE = PS.load()
def blocks(P): return [PB2(B, P) for B in BASE]
def score(B, keep=None):
    T = [PS.manage(t, {}) for t in B.E if keep is None or keep(t)]
    a = F.account(B.ds, B.days, T); R = np.array([x['R_out'] for x in T]) if T else np.zeros(1)
    return dict(n=len(T), sumR=R.sum(), mR=R.mean(), ret=a['ret'], dd=a['mdd'])
cell = lambda s: f"n{s['n']:4d} sumR {s['sumR']:+6.1f} mR {s['mR']:+.3f} acct {s['ret']:+7.1f}% DD{s['dd']:5.1f}"


def part1():
    V = [('LIVE', {})] + [(f'breakout volume {v:g}x', dict(vol=v)) for v in (1.0, 1.5, 2.0)] + [('no breakout required', dict(brk=False))] + \
        [('opening range 9:30-9:40', dict(orh=2)), ('opening range 9:30-10:00', dict(orh=6))] + \
        [('dip 2-3 bars', dict(dips=(2, 3))), ('dip 3-5 bars', dict(dips=(3, 4, 5))), ('dip 2-7 bars', dict(dips=(2, 3, 4, 5, 6, 7)))] + \
        [('dip zone to 1.0% under EMA20', dict(zlo=0.990)), ('dip zone only to EMA20', dict(zlo=1.0)), ('dip zone to 0.3% over EMA9', dict(zhi=1.003)), ('dip must touch EMA9 or lower', dict(zhi=1.0))] + \
        [('triggers from 10:00', dict(j0=6)), ('triggers to 11:30', dict(j1=25)), ('triggers to 12:00', dict(j1=31)), ('triggers from 10:30', dict(j0=12))] + \
        [(f'min stop {m:g}%', dict(minstop=m)) for m in (0.5, 0.85, 1.0, 1.25)] + [(f'stop buffer {bf:g}%', dict(buf=bf)) for bf in (0.0, 0.15, 0.3)] + \
        [(f'room to high >= {x:g} x stop', dict(hodx=x)) for x in (0.5, 1.0, 1.5)] + [('no trend test', dict(trend=False)), ('market entry at next open', dict(entry='market'))]
    base = None
    print('PART 1. PULLBACK signal parameters (exit = live). PASS = account total better on all three blocks.')
    for name, ch in V:
        P = dict(LIVE, **ch); res = [score(B) for B in blocks(P)]
        if base is None: base = res
        ok = name != 'LIVE' and all(r['ret'] > b0['ret'] for r, b0 in zip(res, base))
        print(f"  {('PASS ' if ok else '     ') + name:<40} " + ' | '.join(f"{B.name[:10]} {cell(r)}" for B, r in zip(BASE, res)))


def feats(B, t):
    b, k, x = t['b'], t['k'], t['sig']; r = t['entry'] - t['stop']; ds = B.ds; d = t['day']
    i = ds.idx[d]; q = ds.bars['QQQ'].get(d); qp = ds.bars['QQQ'].get(ds.days[i - 1]) if i else None
    return {'room to high (R)': (t['T'] - t['entry']) / r, 'stop %': r / t['entry'] * 100, 'entry bar': k,
            'EMA9-EMA20 spread %': (x['e9'][k - 1] / x['e20'][k - 1] - 1) * 100, 'gap %': (b[0][0] / t['prev'][-1][3] - 1) * 100,
            'day move to entry %': (b[k - 1][3] / b[0][0] - 1) * 100, 'QQQ day move %': (q[k - 1][3] / q[0][0] - 1) * 100 if q else 0.0,
            'ATR/R': t['atr'][k - 1] / r, 'trigger bar vol / 6-bar avg': b[k - 1][4] / (st.mean(y[4] for y in b[k - 7:k - 1]) or 1),
            'dip bars': x['n'], 'RVOL': ds.rvol(t['proxy'], d, k), 'prior day move %': (t['prev'][-1][3] / t['prev'][0][0] - 1) * 100}


def part2():
    BL = blocks(LIVE); FX = [[feats(B, t) for t in B.E] for B in BL]; base = [score(B) for B in BL]
    print('\nPART 2. PULLBACK entry-time filters (keep set chosen on M H1). PASS = account and sum R better on RH and M H2.')
    print(f"  {'LIVE (no filter)':<58} " + ' | '.join(f"{B.name[:10]} {cell(r)}" for B, r in zip(BL, base)))
    out = []
    for f in FX[0][0]:
        v1 = np.array([x[f] for x in FX[1]]); lo, hi = np.percentile(v1, [33.3, 66.7])
        band = lambda v, lo=lo, hi=hi: 0 if v < lo else (2 if v >= hi else 1); best = None
        for ks in [(0,), (1,), (2,), (0, 1), (1, 2), (0, 2)]:
            idx = [i for i, x in enumerate(FX[1]) if band(x[f]) in ks]
            if len(idx) < 0.4 * len(FX[1]): continue
            sR = sum(PS.manage(BL[1].E[i], {})['R_out'] for i in idx)
            if best is None or sR > best[0]: best = (sR, ks)
        ks = best[1]; res = []
        for b, B in enumerate(BL):
            keep = {id(t) for t, x in zip(B.E, FX[b]) if band(x[f]) in ks}; res.append(score(B, lambda t, k=keep: id(t) in k))
        ok = all(res[b]['ret'] > base[b]['ret'] and res[b]['sumR'] > base[b]['sumR'] for b in (0, 2))
        out.append((ok, res[0]['ret'] - base[0]['ret'] + res[2]['ret'] - base[2]['ret'], f"{f}: keep {'/'.join(['low', 'mid', 'high'][i] for i in ks)} ({lo:.3g} / {hi:.3g})", res))
    out.sort(key=lambda z: (-z[0], -z[1]))
    for ok, sc, name, res in out: print(f"  {('PASS ' if ok else '     ') + name:<58} " + ' | '.join(f"{B.name[:10]} {cell(r)}" for B, r in zip(BL, res)))


if __name__ == '__main__':
    part1(); part2()
