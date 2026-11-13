#!/usr/bin/env python3
"""System 3 search, round 2 (governor 2026-11-13). Round 1 (new_systems.py): only RELVAL passed; IBS earned 2024-26 and lost 2022,
HOUR1 earned 2022-23 and lost 2026. Round 2 tests the conditioned versions. Same account, blocks and PASS rule as round 1.
  IBSF     IBS reversal only with the trend: long a low close when the proxy is above its n-day average (short a high close below it)
  IBSC     low prior close AND a green first 30 minutes -> long at 10:00, stop at the day's low
  RSI2D    daily RSI(2) below x -> long open-to-close, with the same trend filter
  SWITCH   QQQ 20-day average daily range >= x% -> HOUR1 momentum; below it -> IBS long (volatility regime switch)
  BREADTH  at 10:30/11:00, >= 5 of the 6 proxies moved >= 0.3% the same way -> trade the strongest with them, stop at its open
  GAPDN    gap down >= x% in an uptrend -> long the open to the close
    python3 -I tools/backtest/new_systems2.py > tools/backtest/results/new_systems2_2026-11-13.txt"""
import os, pickle, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, new_systems as NS
PX = NS.PX; END = NS.END; NOON = NS.NOON; mg = NS.mg; fin = NS.fin
D = {}                                                    # daily table from the Massive tape: D[p] = (days, {d: index}, o, h, l, c)


def daily_init(dm):
    for p in PX + ['SPY']:
        ds_ = [d for d in dm.days if d in dm.bars[p]]; b = [dm.bars[p][d] for d in ds_]
        D[p] = (ds_, {d: i for i, d in enumerate(ds_)}, [x[0][0] for x in b], [max(y[1] for y in x) for x in b], [min(y[2] for y in x) for x in b], [x[-1][3] for x in b])


def hist(p, d, n):
    """Prior n daily (h, l, c) rows before day d, or None."""
    ds_, ix, o, h, l, c = D[p]; i = ix.get(d)
    if i is None or i < n: return None
    return h[i - n:i], l[i - n:i], c[i - n:i]


def up(p, d, n):
    x = hist(p, d, n)
    return None if x is None else x[2][-1] > st.mean(x[2])


def ibsv(p, d):
    x = hist(p, d, 1)
    if x is None or x[0][0] <= x[1][0]: return None
    return (x[2][0] - x[1][0]) / (x[0][0] - x[1][0])


def rsi2(p, d):
    x = hist(p, d, 12)
    if x is None: return None
    c = x[2]; ag = al = 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 2: ag += g / 2; al += lo / 2
        else: ag = (ag + g) / 2; al = (al + lo) / 2
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def ibsf(ds, ctx, p, d, b, lo=0.2, hi=None, n=50, ref=None, last=END, stop_pct=1.0):
    v = ibsv(p, d); u = up(ref or p, d, n)
    if v is None or u is None: return None
    s = 1 if (v < lo and u) else -1 if (hi is not None and v > hi and not u) else 0
    if not s: return None
    e = b[1][0]; x, g, r = mg(b, 1, s, e, e * (1 - s * stop_pct / 100), last); return fin(d, p, 1, x, e, g, r)


def ibsc(ds, ctx, p, d, b, lo=0.2, n=None, kb=6, last=END):
    v = ibsv(p, d)
    if v is None or v >= lo or (n and not up(p, d, n)): return None
    if b[kb - 1][3] <= b[0][0]: return None
    e = b[kb][0]; stop = min(x[2] for x in b[:kb]); stop = min(stop, e * 0.997)
    x, g, r = mg(b, kb, 1, e, stop, last); return fin(d, p, kb, x, e, g, r)


def rsi2d(ds, ctx, p, d, b, th=10, n=50, last=END):
    v = rsi2(p, d); u = up(p, d, n) if n else True
    if v is None or u is None or v >= th or not u: return None
    e = b[1][0]; x, g, r = mg(b, 1, 1, e, e * 0.99, last); return fin(d, p, 1, x, e, g, r)


def volreg(d, n=20):
    x = hist('QQQ', d, n)
    return None if x is None else st.mean((h - l) / c * 100 for h, l, c in zip(*x))


def switch(ds, ctx, p, d, b, thr=1.8, lo=0.2, last=END, mom=True, rev=True):
    v = volreg(d)
    if v is None: return None
    if v >= thr: return NS.hour1(ds, ctx, p, d, b, xm=0.5, last=last) if mom else None
    if not rev: return None
    iv = ibsv(p, d)
    if iv is None or iv >= lo: return None
    e = b[1][0]; x, g, r = mg(b, 1, 1, e, e * 0.99, last); return fin(d, p, 1, x, e, g, r)


_br = {}
def breadth(ds, ctx, p, d, b, kb=12, need=5, xm=0.3, last=END, pick='strong'):
    key = (id(ds), d, kb, need, xm, pick)
    if key not in _br:
        mv = {q: (ds.bars[q][d][kb - 1][3] / ds.bars[q][d][0][0] - 1) * 100 for q in PX if d in ds.bars[q] and len(ds.bars[q][d]) >= 78}
        upn = sum(v >= xm for v in mv.values()); dn = sum(v <= -xm for v in mv.values()); s = 1 if upn >= need else -1 if dn >= need else 0
        ch = None
        if s and len(mv) == len(PX): ch = ('QQQ' if pick == 'qqq' else max(mv, key=lambda q: mv[q] * s) if pick == 'strong' else min(mv, key=lambda q: mv[q] * s)), s
        _br[key] = ch
    ch = _br[key]
    if not ch or ch[0] != p: return None
    s = ch[1]; e = b[kb][0]; stop = b[0][0]
    if (e - stop) * s <= 0: return None
    x, g, r = mg(b, kb, s, e, stop, last); return fin(d, p, kb, x, e, g, r)


def gapdn(ds, ctx, p, d, b, gm=0.5, n=50, last=END):
    x = hist(p, d, 1); u = up(p, d, n) if n else True
    if x is None or u is None or not u: return None
    if (b[0][0] / x[2][0] - 1) * 100 > -gm: return None
    e = b[1][0]; x_, g, r = mg(b, 1, 1, e, e * 0.99, last); return fin(d, p, 1, x_, e, g, r)


CANDS = [
    ('IBSF', ibsf, [dict(lo=0.2, n=20), dict(lo=0.2, n=50), dict(lo=0.2, n=100), dict(lo=0.1, n=50), dict(lo=0.3, n=50), dict(lo=0.2, n=50, hi=0.8), dict(lo=0.2, n=50, ref='QQQ'), dict(lo=0.2, n=100, ref='QQQ'), dict(lo=0.2, n=50, last=NOON), dict(lo=0.2, n=200)]),
    ('IBSC', ibsc, [dict(), dict(n=50), dict(lo=0.3), dict(kb=3), dict(n=50, kb=3), dict(last=NOON)]),
    ('RSI2D', rsi2d, [dict(th=10), dict(th=5), dict(th=20), dict(th=10, n=None), dict(th=10, n=100), dict(th=10, last=NOON)]),
    ('SWITCH', switch, [dict(thr=1.5), dict(thr=1.8), dict(thr=2.1), dict(thr=1.8, last=NOON), dict(thr=1.8, rev=False), dict(thr=1.8, mom=False), dict(thr=1.5, mom=False), dict(thr=2.1, rev=False)]),
    ('BREADTH', breadth, [dict(kb=12), dict(kb=18), dict(kb=6), dict(kb=12, need=6), dict(kb=12, pick='qqq'), dict(kb=12, pick='weak'), dict(kb=12, xm=0.5), dict(kb=12, last=NOON)]),
    ('GAPDN', gapdn, [dict(gm=0.5), dict(gm=1.0), dict(gm=0.5, n=None), dict(gm=0.3)]),
]


def main():
    dm = F.DS(AE.M5, PX + ['SPY']); cm = F.context(dm, PX); dr = F.DS(None, PX); cr = F.context(dr, PX); daily_init(dm)
    dM = [d for d in dm.days[21:] if d <= '2026-10-30']; B = [('H1 21-24', dm, cm, [d for d in dM if d < '2024-04-01']), ('H2 24-26', dm, cm, [d for d in dM if d >= '2024-04-01']), ('RH 2026', dr, cr, [d for d in dr.days if '2026-03-03' <= d <= '2026-10-14'])]
    print(__doc__.split('\n')[0]); print('per block: trades taken, win %, average leg %, profit factor, account total, max drawdown.  * = the setting H1 chose\n')
    keep = {}
    for name, fn, grid in CANDS:
        res = [[NS.blk(ds, cx, days, fn, kw) for _, ds, cx, days in B] for kw in grid]
        best = max(range(len(grid)), key=lambda i: res[i][0]['ret'] if res[i][0] else -1e9)
        for i, kw in enumerate(grid):
            ok = all(r and r['pf'] >= 1.15 and r['ret'] > 0 for r in res[i])
            cells = ' || '.join(f"{bn} n{r['n']:4d} w{r['win']:3.0f}% {r['avg']:+.2f}% PF{r['pf']:4.2f} {r['ret']:+7.1f}% DD{r['dd']:5.1f}" if r else f"{bn} none" for (bn, *_), r in zip(B, res[i]))
            print(f"  {'PASS' if ok else '    '}{'*' if i == best else ' '} {name:<8} {str(kw)[1:-1].replace(chr(39), ''):<30} {cells}")
            keep[(name, i)] = dict(kw=kw, ok=ok, chosen=i == best, T=[r['T'] if r else [] for r in res[i]], daily=[r['daily'] if r else {} for r in res[i]])
        print()
    pickle.dump(dict(keep=keep, days=[b[3] for b in B]), open('/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/new_systems2.pkl', 'wb'))


if __name__ == '__main__':
    main()
