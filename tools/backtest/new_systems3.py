#!/usr/bin/env python3
"""System 3 search, round 3 (governor 2026-11-13). Rounds 1-2: breakout and momentum families fail 2024-26; reversion families pass
(RELVAL afternoon, RSI2D dip-buy in an uptrend). Round 3 looks for a third reversion system on a different clock. Same account/blocks/PASS.
  DIPDAY   uptrend (close > 50-day average); the proxy falls >= x% under its open, then a 5-minute close above the prior bar's high
           -> long, stop under the day's low, exit 15:55 (intraday dip reversal)
  PMFADE   13:30: the move from the open is >= k x the 20-day average open-to-close move -> fade it into the close
  RELBASK  RELVAL against the equal-weight basket of the other five proxies (QQQ included as a tradable) after 13:30
  RELPAIR  RELVAL against the closest sibling (SOXX-XLK, IWM-XLF, XBI-IWM) after 13:30
  DOWNN    n down closes in a row in an uptrend -> long open-to-close
    python3 -I tools/backtest/new_systems3.py > tools/backtest/results/new_systems3_2026-11-13.txt"""
import os, pickle, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, new_systems as NS, new_systems2 as N2
PX = NS.PX; END = NS.END; NOON = NS.NOON; mg = NS.mg; fin = NS.fin; up = N2.up; hist = N2.hist
SIB = dict(SOXX='XLK', XLK='SOXX', IWM='XLF', XLF='IWM', XBI='IWM', QQQ='XLK')


def dipday(ds, ctx, p, d, b, xm=1.0, n=50, a=6, z=60, tp=None, mirror=False):
    u = up(p, d, n) if n else True
    if u is None: return None
    s = 1 if u else (-1 if mirror else 0)
    if not s: return None
    o0 = b[0][0]; ext = o0; armed = False
    for j in range(0, z):
        o, h, l, c, v = b[j]; ext = min(ext, l) if s > 0 else max(ext, h)
        if (o0 - ext) * s / o0 * 100 >= xm: armed = True
        if armed and j >= a and j >= 1 and ((c > b[j - 1][1]) if s > 0 else (c < b[j - 1][2])):
            k = j + 1; e = b[k][0]; stop = ext * (1 - s * 0.0005)
            if (e - stop) * s <= 0: return None
            stop = e - s * max((e - stop) * s, 0.003 * e)
            x, g, r = mg(b, k, s, e, stop, END, at=ctx['atr'][p][d], tpR=tp, chand=3.0 if tp else 0); return fin(d, p, k, x, e, g, r)
    return None


_oc = {}
def pmfade(ds, ctx, p, d, b, k_=1.5, kb=48, n=None, half=True):
    ds_, ix, o, h, l, c = N2.D[p]; i = ix.get(d)
    if i is None or i < 20: return None
    avg = st.mean(abs(c[q] / o[q] - 1) for q in range(i - 20, i)); mv = b[kb - 1][3] / b[0][0] - 1
    if abs(mv) < k_ * avg: return None
    s = -1 if mv > 0 else 1
    if n:
        u = up(p, d, n)
        if u is None or (s > 0) != u: return None
    e = b[kb][0]; ext = max(x[1] for x in b[:kb]) if s < 0 else min(x[2] for x in b[:kb]); stop = e - s * max((ext - e) * (-s) + 0.001 * e, 0.004 * e)
    T = e + s * abs(mv) * e / 2 if half else None
    x, g, r = mg(b, kb, s, e, stop, END, T=T); return fin(d, p, kb, x, e, g, r)


_rb = {}
def relref(ds, ctx, p, d, b, mode='bask', a=48, z=72, xm=1.0, ksd=2.5):
    refs = [q for q in PX if q != p] if mode == 'bask' else [SIB[p]]
    if any(d not in ds.bars[q] or len(ds.bars[q][d]) < 78 for q in refs): return None
    def rel(x, j=-1):
        bb = ds.bars[p].get(x)
        if not bb or any(x not in ds.bars[q] or len(ds.bars[q][x]) <= (j if j >= 0 else 0) for q in refs): return None
        return bb[j][3] / bb[0][0] - st.mean(ds.bars[q][x][j][3] / ds.bars[q][x][0][0] for q in refs)
    key = (id(ds), p, mode)
    if key not in _rb: _rb[key] = {x: rel(x) for x in ds.days}
    i = ds.idx[d]; hs = [_rb[key][x] for x in ds.days[max(0, i - 20):i] if _rb[key].get(x) is not None]
    if len(hs) < 15: return None
    sd = st.pstdev(hs) or 1e-9
    for j in range(a, z):
        rp = b[j][3] / b[0][0] - st.mean(ds.bars[q][d][j][3] / ds.bars[q][d][0][0] for q in refs)
        if abs(rp) * 100 >= xm and abs(rp) >= ksd * sd:
            s = -1 if rp > 0 else 1; k = j + 1; e = b[k][0]; gap = abs(rp) * e
            x, g, r = mg(b, k, s, e, e - s * gap, END, T=e + s * gap / 2); return fin(d, p, k, x, e, g, r)
    return None


def downn(ds, ctx, p, d, b, n=3, sma=50, last=END):
    x = hist(p, d, n + 1); u = up(p, d, sma) if sma else True
    if x is None or u is None or not u: return None
    c = x[2]
    if not all(c[i] < c[i - 1] for i in range(1, n + 1)): return None
    e = b[1][0]; x_, g, r = mg(b, 1, 1, e, e * 0.99, last); return fin(d, p, 1, x_, e, g, r)


CANDS = [
    ('DIPDAY', dipday, [dict(xm=1.0), dict(xm=0.75), dict(xm=1.5), dict(xm=1.0, n=None), dict(xm=1.0, tp=2.0), dict(xm=1.0, mirror=True), dict(xm=1.0, a=12), dict(xm=0.5)]),
    ('PMFADE', pmfade, [dict(k_=1.5), dict(k_=1.0), dict(k_=2.0), dict(k_=1.5, n=50), dict(k_=1.5, half=False), dict(k_=1.0, n=50), dict(k_=1.5, kb=60)]),
    ('RELBASK', relref, [dict(xm=1.0), dict(xm=0.75), dict(xm=1.25), dict(xm=1.0, ksd=2.0), dict(xm=1.0, ksd=3.0), dict(xm=0.5)]),
    ('RELPAIR', relref, [dict(mode='pair', xm=1.0), dict(mode='pair', xm=0.75), dict(mode='pair', xm=1.25), dict(mode='pair', xm=1.0, ksd=2.0), dict(mode='pair', xm=1.0, ksd=3.0)]),
    ('DOWNN', downn, [dict(n=3), dict(n=2), dict(n=4), dict(n=3, sma=None), dict(n=3, sma=20), dict(n=3, last=NOON)]),
]


def main():
    dm = F.DS(AE.M5, PX + ['SPY']); cm = F.context(dm, PX); dr = F.DS(None, PX); cr = F.context(dr, PX); N2.daily_init(dm)
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
    pickle.dump(dict(keep=keep, days=[b[3] for b in B]), open('/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/new_systems3.pkl', 'wb'))


if __name__ == '__main__':
    main()
