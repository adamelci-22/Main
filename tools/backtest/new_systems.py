#!/usr/bin/env python3
"""System 3 search (governor 2026-11-13): NEW proxy -> 3x leg systems that could replace FADE and PULLBACK.
Signal on the proxy chart (QQQ SOXX IWM XLK XBI XLF), trade the 3x long or inverse leg, nothing overnight, cost 0.06% a round trip.
Account: 3% risk a trade capped at cash, one position at a time, 3 entries a day. Exit at the 15:55 open unless a variant says 13:30.
Blocks: Massive H1 2021-12..2024-03 (settings are chosen here), Massive H2 2024-04..2026-10, Robinhood 2026-03..10 (judged here).
PASS = profit factor >= 1.15 and a positive total in all three blocks for the setting H1 chose.
Candidates (sources in archive/systems_2026-11-13.md):
  RELVAL     sector vs QQQ gap >= x% and >= 2.5 sd of the 20-day relative move -> trade back toward QQQ, target half the gap, stop one gap
  VWAPTREND  first close >= 0.1% beyond session VWAP and beyond the open -> trade with it, exit on a close across VWAP (Zarattini-Aziz)
  VWAPPB     trend day (>= x% from the open, above VWAP) -> buy the first touch of VWAP that closes back above it, stop under the dip
  ORB5       first 5-minute candle direction, stop-entry at its extreme inside the first hour, stop at the other extreme (Zarattini)
  HOUR1      first hour move >= x% -> trade with it at 10:30, stop at the day's open
  IBS        prior day closed in the bottom/top of its range -> open-to-close reversal (internal bar strength)
  MIDBOX     midday box up to 13:30 -> trade a 5-minute close outside it after 13:30, stop at the box middle
  FADEBOX    the FADE mechanics (break close, failed first retest, 0.5% floor, 1/3 at 2R, chandelier) on a later box
  PDFADE     failed break of the PRIOR DAY high/low (close beyond, then a close back inside within 12 bars) -> fade it, FADE exit
  REBAL      15:30, move from the prior close >= x% -> trade with it into the close (leveraged-fund rebalance flow)
    python3 -I tools/backtest/new_systems.py > tools/backtest/results/new_systems_2026-11-13.txt"""
import os, pickle, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, pb_exit_screen as PS, entry_fade as EF, fade_setup_exits as FS
PX = list(F.LIVE); END = 77; NOON = 48; COST = F.LEGCOST


def mg(b, k, s, e, stop, last, at=None, T=None, tpR=None, frac=1 / 3, chand=0.0, out_fn=None):
    """Manage from bar k (entry at e) to the OPEN of bar `last`. Returns (exit bar, gain per share-fraction, initial risk)."""
    r = (e - stop) * s; P = e + s * tpR * r if tpR else None; rem, g, hit, hic = 1.0, 0.0, False, e
    for j in range(k, last):
        o, h, l, c, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; return j, g + rem * (px - e) * s, r
        if T is not None and (fav - T) * s >= 0: px = T if (o - T) * s <= 0 else o; return j, g + rem * (px - e) * s, r
        if P is not None and not hit and (fav - P) * s >= 0:
            px = P if (o - P) * s <= 0 else o; g += frac * (px - e) * s; rem -= frac; hit = True
            if (e - stop) * s > 0: stop = e
        hic = max(hic, c) if s > 0 else min(hic, c)
        if hit and chand:
            ns = hic - s * chand * at[j]
            if (ns - stop) * s > 0: stop = ns
        if out_fn and out_fn(j) and j + 1 < last: return j + 1, g + rem * (b[j + 1][0] - e) * s, r
    return last - 1, g + rem * (b[last][0] - e) * s, r


def fin(d, p, k, x, e, g, r): return dict(day=d, proxy=p, k=k, xbar=x, R_out=g / r if r else 0, pct=3 * g / e * 100 - COST, leg_risk=max(3 * r / e * 100, 0.3))


def vwap(b):
    pv = cv = 0.0; out = []
    for x in b: pv += (x[1] + x[2] + x[3]) / 3 * x[4]; cv += x[4]; out.append(pv / cv if cv else x[3])
    return out


def prevb(ds, p, d):
    i = ds.idx[d]; return ds.bars[p].get(ds.days[i - 1]) if i else None


_rel = {}
def relval(ds, ctx, p, d, b, a=48, z=72, xm=1.0, ksd=2.5):
    if p == 'QQQ': return None
    q = ds.bars['QQQ'].get(d)
    if not q or len(q) < 78: return None
    key = (id(ds), p)
    if key not in _rel:
        _rel[key] = {x: (ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0]) for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']}
    i = ds.idx[d]; hist = [_rel[key][x] for x in ds.days[max(0, i - 20):i] if x in _rel[key]]
    if len(hist) < 15: return None
    sd = st.pstdev(hist) or 1e-9
    for j in range(a, z):
        rp = b[j][3] / b[0][0] - q[j][3] / q[0][0]
        if abs(rp) * 100 >= xm and abs(rp) >= ksd * sd:
            s = -1 if rp > 0 else 1; k = j + 1; e = b[k][0]; gap = abs(rp) * e
            x, g, r = mg(b, k, s, e, e - s * gap, END, T=e + s * gap / 2); return fin(d, p, k, x, e, g, r)
    return None


def vwaptrend(ds, ctx, p, d, b, a=6, z=60, last=END, band=0.1):
    vw = vwap(b)
    for j in range(a, z):
        c = b[j][3]; dv = (c / vw[j] - 1) * 100; s = 1 if dv >= band and c > b[0][0] else -1 if dv <= -band and c < b[0][0] else 0
        if s:
            k = j + 1; e = b[k][0]; stop = e - s * max(abs(e - vw[j]), 0.005 * e)
            x, g, r = mg(b, k, s, e, stop, last, out_fn=lambda jj, s=s: (b[jj][3] - vw[jj]) * s < 0); return fin(d, p, k, x, e, g, r)
    return None


def vwappb(ds, ctx, p, d, b, xm=0.5, a=12, z=66, last=END):
    vw = vwap(b)
    for j in range(a, z):
        o, h, l, c, v = b[j]; mv = (c / b[0][0] - 1) * 100; s = 1 if mv >= xm else -1 if mv <= -xm else 0
        if not s: continue
        touch = l <= vw[j] if s > 0 else h >= vw[j]
        if touch and (c - vw[j]) * s > 0 and all((b[q][3] - vw[q]) * s > 0 for q in range(j - 6, j)):
            k = j + 1; e = b[k][0]; ext = l if s > 0 else h; stop = e - s * max((e - ext) * s + 0.0005 * e, 0.003 * e)
            x, g, r = mg(b, k, s, e, stop, last, at=ctx['atr'][p][d], tpR=2.0, chand=3.0); return fin(d, p, k, x, e, g, r)
    return None


_fb = {}
def orb5(ds, ctx, p, d, b, last=END, rv=0.0, tgt=None):
    o, h, l, c, v = b[0]
    if c == o: return None
    if rv:
        key = (id(ds), p)
        if key not in _fb: _fb[key] = {x: ds.bars[p][x][0][4] for x in ds.days if x in ds.bars[p]}
        i = ds.idx[d]; hist = [_fb[key][x] for x in ds.days[max(0, i - 14):i] if x in _fb[key]]
        if len(hist) < 10 or v < rv * st.mean(hist): return None
    s = 1 if c > o else -1; trig = h if s > 0 else l; ext = l if s > 0 else h
    for j in range(1, 12):
        if (b[j][1] if s > 0 else b[j][2]) * s >= trig * s:
            e = trig if (b[j][0] - trig) * s <= 0 else b[j][0]; stop = e - s * max((e - ext) * s, 0.0025 * e)
            x, g, r = mg(b, j, s, e, stop, last, T=(e + s * tgt * (e - stop) * s) if tgt else None); return fin(d, p, j, x, e, g, r)
    return None


def hour1(ds, ctx, p, d, b, xm=0.5, last=END, kb=12, vx=False):
    mv = (b[kb - 1][3] / b[0][0] - 1) * 100
    if abs(mv) < xm: return None
    s = 1 if mv > 0 else -1; e = b[kb][0]; stop = b[0][0]
    if (e - stop) * s <= 0: return None
    vw = vwap(b) if vx else None
    x, g, r = mg(b, kb, s, e, stop, last, out_fn=(lambda jj, s=s: (b[jj][3] - vw[jj]) * s < 0) if vx else None); return fin(d, p, kb, x, e, g, r)


def ibs(ds, ctx, p, d, b, lo=0.2, hi=0.8, last=END, stop_pct=1.0):
    pv = prevb(ds, p, d)
    if not pv: return None
    H = max(x[1] for x in pv); L = min(x[2] for x in pv)
    if H <= L: return None
    v = (pv[-1][3] - L) / (H - L); s = 1 if v < lo else -1 if v > hi else 0
    if not s: return None
    e = b[1][0]; x, g, r = mg(b, 1, s, e, e * (1 - s * stop_pct / 100), last); return fin(d, p, 1, x, e, g, r)


def midbox(ds, ctx, p, d, b, a=30, z=66):
    H = max(x[1] for x in b[a:48]); L = min(x[2] for x in b[a:48]); mid = (H + L) / 2
    for j in range(48, z):
        c = b[j][3]; s = 1 if c > H else -1 if c < L else 0
        if s:
            k = j + 1; e = b[k][0]; stop = e - s * max((e - mid) * s, 0.003 * e)
            x, g, r = mg(b, k, s, e, stop, END); return fin(d, p, k, x, e, g, r)
    return None


def fadebox(ds, ctx, p, d, b, a=0, z=6, nb=2, last=NOON, floor=0.5, fri=True):
    """FADE mechanics on the box b[a:z]: break close within nb bars, FIRST retest within 12 bars that closes back inside -> fade."""
    if fri and __import__('datetime').date.fromisoformat(d).weekday() == 4: return None
    H = max(x[1] for x in b[a:z]); L = min(x[2] for x in b[a:z]); at = ctx['atr'][p][d]
    for j in range(z, z + nb):
        c = b[j][3]; sb = 1 if c > H else -1 if c < L else 0
        if not sb: continue
        edge = H if sb > 0 else L; ext = b[j][1] if sb > 0 else b[j][2]
        for q in range(j + 1, min(j + 13, last - 1)):
            o2, h2, l2, c2, v2 = b[q]; ext = max(ext, h2) if sb > 0 else min(ext, l2)
            if (l2 - edge * (1 + 0.001)) <= 0 if sb > 0 else (h2 - edge * (1 - 0.001)) >= 0:
                if (c2 - edge) * sb >= 0: return None                                   # the retest held: no trade
                s = -sb; k = q + 1; e = b[k][0]; r = max((ext - e) * sb, floor / 100 * e)
                if r <= 0: return None
                x, g, r = mg(b, k, s, e, e - s * r, last, at=at, tpR=2.0, chand=2.0); return fin(d, p, k, x, e, g, r)
        return None
    return None


def pdfade(ds, ctx, p, d, b, z=42, last=NOON, floor=0.5, win=12):
    pv = prevb(ds, p, d)
    if not pv: return None
    PH = max(x[1] for x in pv); PL = min(x[2] for x in pv); at = ctx['atr'][p][d]
    for j in range(0, z):
        c = b[j][3]; sb = 1 if c > PH else -1 if c < PL else 0
        if not sb: continue
        edge = PH if sb > 0 else PL; ext = b[j][1] if sb > 0 else b[j][2]
        for q in range(j + 1, min(j + 1 + win, last - 1)):
            ext = max(ext, b[q][1]) if sb > 0 else min(ext, b[q][2])
            if (b[q][3] - edge) * sb < 0:
                s = -sb; k = q + 1; e = b[k][0]; r = max((ext - e) * sb, floor / 100 * e)
                x, g, r = mg(b, k, s, e, e - s * r, last, at=at, tpR=2.0, chand=2.0); return fin(d, p, k, x, e, g, r)
        return None
    return None


def rebal(ds, ctx, p, d, b, xm=1.0, kb=72, fade=False):
    pv = prevb(ds, p, d)
    if not pv: return None
    mv = (b[kb - 1][3] / pv[-1][3] - 1) * 100
    if abs(mv) < xm: return None
    s = (1 if mv > 0 else -1) * (-1 if fade else 1); e = b[kb][0]
    x, g, r = mg(b, kb, s, e, e * (1 - s * 0.005), 78 - 1); return fin(d, p, kb, x, e, g, r)


CANDS = [
    ('RELVAL', relval, [dict(a=48, z=72, xm=1.0), dict(a=48, z=72, xm=0.75), dict(a=48, z=72, xm=1.25), dict(a=6, z=72, xm=1.0), dict(a=6, z=72, xm=1.25), dict(a=6, z=48, xm=1.0), dict(a=24, z=72, xm=1.0)]),
    ('VWAPTREND', vwaptrend, [dict(a=6), dict(a=12), dict(a=6, band=0.2), dict(a=6, last=NOON, z=36), dict(a=48, z=66), dict(a=1)]),
    ('VWAPPB', vwappb, [dict(xm=0.5), dict(xm=0.75), dict(xm=1.0), dict(xm=0.5, last=NOON, z=40), dict(xm=0.5, a=48)]),
    ('ORB5', orb5, [dict(), dict(rv=1.0), dict(rv=1.5), dict(tgt=10), dict(last=NOON), dict(rv=1.0, last=NOON)]),
    ('HOUR1', hour1, [dict(xm=0.5), dict(xm=0.75), dict(xm=1.0), dict(xm=0.5, last=NOON), dict(xm=0.5, vx=True), dict(xm=0.5, kb=6), dict(xm=0.75, kb=6)]),
    ('IBS', ibs, [dict(), dict(lo=0.1, hi=0.9), dict(lo=0.2, hi=2), dict(lo=-1, hi=0.8), dict(lo=0.1, hi=2), dict(lo=0.2, hi=0.8, last=NOON)]),
    ('MIDBOX', midbox, [dict(a=30), dict(a=24), dict(a=36), dict(a=42)]),
    ('FADEBOX', fadebox, [dict(a=0, z=6, nb=2), dict(a=42, z=48, nb=2, last=END), dict(a=36, z=48, nb=2, last=END), dict(a=42, z=48, nb=6, last=END), dict(a=24, z=30, nb=2, last=END), dict(a=0, z=6, nb=2, last=END), dict(a=0, z=12, nb=2, last=END), dict(a=0, z=12, nb=2)]),
    ('PDFADE', pdfade, [dict(), dict(last=END, z=66), dict(win=6), dict(z=12), dict(last=END, z=66, win=6), dict(floor=0.3)]),
    ('REBAL', rebal, [dict(xm=1.0), dict(xm=1.5), dict(xm=2.0), dict(xm=1.0, fade=True), dict(xm=2.0, fade=True), dict(xm=1.0, kb=66)]),
]


def blk(ds, ctx, days, fn, kw):
    T = [x for p in PX for d in days if d in ds.bars[p] and len(ds.bars[p][d]) >= 78 for x in [fn(ds, ctx, p, d, ds.bars[p][d], **kw)] if x]
    if not T: return None
    a = F.account(ds, days, T); tk = a['taken']; gw = sum(x['acct'] for x in tk if x['acct'] > 0); gl = -sum(x['acct'] for x in tk if x['acct'] <= 0)
    return dict(n=len(tk), win=100 * sum(x['acct'] > 0 for x in tk) / len(tk), avg=st.mean(x['pct'] for x in tk), pf=gw / gl if gl else 9.0, ret=a['ret'], dd=a['mdd'], daily=a['daily'], T=T)


def main():
    dm = F.DS(AE.M5, PX); cm = F.context(dm, PX); dr = F.DS(None, PX); cr = F.context(dr, PX)
    dM = [d for d in dm.days[21:] if d <= '2026-10-30']; B = [('H1 21-24', dm, cm, [d for d in dM if d < '2024-04-01']), ('H2 24-26', dm, cm, [d for d in dM if d >= '2024-04-01']), ('RH 2026', dr, cr, [d for d in dr.days if '2026-03-03' <= d <= '2026-10-14'])]
    print(__doc__.split('\n')[0]); print('per block: trades taken, win %, average leg %, profit factor, account total, max drawdown.  * = the setting H1 chose\n')
    keep = {}
    for name, fn, grid in CANDS:
        res = [[blk(ds, cx, days, fn, kw) for _, ds, cx, days in B] for kw in grid]
        best = max(range(len(grid)), key=lambda i: res[i][0]['ret'] if res[i][0] else -1e9)
        for i, kw in enumerate(grid):
            ok = all(r and r['pf'] >= 1.15 and r['ret'] > 0 for r in res[i])
            cells = ' || '.join(f"{bn} n{r['n']:4d} w{r['win']:3.0f}% {r['avg']:+.2f}% PF{r['pf']:4.2f} {r['ret']:+7.1f}% DD{r['dd']:5.1f}" if r else f"{bn} none" for (bn, *_), r in zip(B, res[i]))
            print(f"  {'PASS' if ok else '    '}{'*' if i == best else ' '} {name:<9} {str(kw)[1:-1].replace(chr(39), ''):<34} {cells}")
            keep[(name, i)] = dict(kw=kw, ok=ok, chosen=i == best, daily=[r['daily'] if r else {} for r in res[i]], T=[r['T'] if r else [] for r in res[i]],
                                   stat=[(r['n'], r['win'], r['avg'], r['pf'], r['ret'], r['dd']) if r else None for r in res[i]])
        print()
    pickle.dump(dict(keep=keep, days=[b[3] for b in B]), open('/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/new_systems.pkl', 'wb'))


if __name__ == '__main__':
    main()
