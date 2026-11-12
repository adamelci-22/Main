#!/usr/bin/env python3
"""Published intraday systems on the same data and constraints as the live account (governor 2026-11-12: "are there better systems out there").
Constraints: entries 10:00-12:55, flat by 13:30, trades the 3x leg of the proxy (leg return = 3 x proxy return - 0.06% cost),
one proxy-day = at most one trade, $2,000-style account with 3% risk capped at cash, one position at a time, 3 entries a day.
Proxies: QQQ SOXX IWM XLK XBI XLF SPY. Systems:
  ORB30   Crabel / Zarattini-Aziz (2023) opening-range breakout CONTINUATION: first close beyond the 9:30-10:00 box, enter next open, stop
          at the box middle, 1/3 at 2R then 2-ATR chandelier (same exit family as FADE), out 13:30.
  NOISE   Zarattini-Aziz-Barbon (2024) noise-boundary momentum: boundary = open x (1 +/- mean 14-day |move from open| at that time of day);
          checked at :00/:30 from 10:00, enter on a close outside, exit on a close back inside the boundary or 13:30; stop = boundary.
  VWAP    VWAP reversion: close more than k x ATR(14) from session VWAP -> fade toward VWAP (target VWAP, stop 1 extension beyond).
  GAP     Gap fade: |gap| >= 0.5%, at 10:00 if price is still beyond the prior close, fade toward it (target prior close, stop = 9:30-10:00 extreme).
  HOUR1   First-hour momentum (Gao-Han-Li-Zhou 2018 idea, cut to our window): 9:30-10:30 move >= x% -> enter 10:30 with it, stop at the open, out 13:30.
    python3 -I tools/backtest/other_systems.py > tools/backtest/results/other_systems_2026-11-12.txt"""
import datetime as dt, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE, fade_setup_exits as FS, pb_exit_screen as PS
PX = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY']; LAST = 47; LEV = 3; COST = F.LEGCOST


def fin(day, p, k, xbar, e, g, r):
    return dict(day=day, proxy=p, k=k, xbar=xbar, R_out=g / r if r else 0, pct=LEV * g / e * 100 - COST, leg_risk=LEV * r / e * 100 if r else 3.0)


def run_exit(b, k, s, e, stop, at, tpR=2.0, frac=1 / 3, chand=2.0, inside=None):
    r = (e - stop) * s; T = e + s * tpR * r if tpR else None; rem, g, hit, hic = 1.0, 0.0, False, e; j = k; out = False
    for j in range(k, LAST + 1):
        o, h, l, c, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: g += rem * (o - e) * s; rem = 0; break
        if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; g += rem * (px - e) * s; rem = 0; break
        if T is not None and not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; q = min(frac, rem); g += q * (px - e) * s; rem -= q; hit = True
            if (e - stop) * s > 0: stop = e
            if rem <= 1e-9: break
        hic = max(hic, c) if s > 0 else min(hic, c)
        if hit and chand and j < LAST:
            ns = hic - s * chand * at[j]
            if (ns - stop) * s > 0: stop = ns
        if inside and inside(j) and j < LAST: out = True
    if rem > 0: g += rem * (b[j][3] - e) * s
    return j, g, r


def orb30(ds, ctx, p, d, b, **kw):
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6]); mid = (H + L) / 2
    for j in range(6, 42):
        c = b[j][3]; s = 1 if c > H else -1 if c < L else 0
        if s:
            k = j + 1; e = b[k][0]; stop = mid
            if (e - stop) * s <= 0: return None
            x, g, r = run_exit(b, k, s, e, stop, ctx['atr'][p][d]); return fin(d, p, k, x, e, g, r)
    return None


def noise(ds, ctx, p, d, b, n=14, **kw):
    i = ds.idx[d]; prior = [ds.bars[p].get(x) for x in ds.days[max(0, i - n):i]]; prior = [x for x in prior if x]
    if len(prior) < n or i == 0: return None
    pc = ds.bars[p][ds.days[i - 1]][-1][3] if ds.days[i - 1] in ds.bars[p] else b[0][0]; o0 = b[0][0]
    up0, lo0 = max(o0, pc), min(o0, pc)
    sig = [st.mean(abs(x[j][3] / x[0][0] - 1) for x in prior) for j in range(78)]
    for j in range(5, 42, 6):                      # closes at 10:00, 10:30, ... (bar j closes at 9:35 + 5j)
        c = b[j][3]; U = up0 * (1 + sig[j]); Lb = lo0 * (1 - sig[j])
        s = 1 if c > U else -1 if c < Lb else 0
        if s:
            k = j + 1; e = b[k][0]; stop = U if s > 0 else Lb
            if (e - stop) * s <= 0: stop = e - s * e * 0.002
            inside = lambda jj, s=s: (b[jj][3] - (up0 * (1 + sig[jj]) if s > 0 else lo0 * (1 - sig[jj]))) * s < 0
            x, g, r = run_exit(b, k, s, e, stop, ctx['atr'][p][d], tpR=None, chand=0, inside=inside); return fin(d, p, k, x, e, g, r)
    return None


def vwap(ds, ctx, p, d, b, kx=2.0, **kw):
    pv = cv = 0.0; at = ctx['atr'][p][d]
    for j in range(0, 42):
        o, h, l, c, v = b[j]; tp = (h + l + c) / 3; pv += tp * v; cv += v; vw = pv / cv if cv else c
        if j < 6: continue
        dev = c - vw
        if abs(dev) >= kx * at[j] and at[j] > 0:
            s = -1 if dev > 0 else 1; k = j + 1; e = b[k][0]; stop = e - s * abs(dev)
            tgtR = abs(vw - e) / abs(dev)
            if tgtR <= 0.2: return None
            x, g, r = run_exit(b, k, s, e, stop, at, tpR=tgtR, frac=1.0, chand=0); return fin(d, p, k, x, e, g, r)
    return None


def gap(ds, ctx, p, d, b, gmin=0.5, **kw):
    i = ds.idx[d]
    if i == 0 or ds.days[i - 1] not in ds.bars[p]: return None
    pc = ds.bars[p][ds.days[i - 1]][-1][3]; gp = (b[0][0] / pc - 1) * 100
    if abs(gp) < gmin: return None
    c = b[5][3]; s = -1 if gp > 0 else 1
    if (pc - c) * s <= 0: return None              # already filled
    k = 6; e = b[k][0]; stop = max(x[1] for x in b[:6]) if s < 0 else min(x[2] for x in b[:6])
    if (e - stop) * s <= 0: return None
    tgtR = abs(pc - e) / abs(e - stop)
    x, g, r = run_exit(b, k, s, e, stop, ctx['atr'][p][d], tpR=tgtR, frac=1.0, chand=0); return fin(d, p, k, x, e, g, r)


def hour1(ds, ctx, p, d, b, xm=0.5, **kw):
    mv = (b[11][3] / b[0][0] - 1) * 100
    if abs(mv) < xm: return None
    s = 1 if mv > 0 else -1; k = 12; e = b[k][0]; stop = b[0][0]
    if (e - stop) * s <= 0: return None
    x, g, r = run_exit(b, k, s, e, stop, ctx['atr'][p][d], tpR=None, chand=0); return fin(d, p, k, x, e, g, r)


SYS = [('ORB30 continuation (box middle stop, 2R + chandelier)', orb30, {}),
       ('NOISE boundary momentum (Zarattini-Aziz-Barbon)', noise, {}),
       ('VWAP reversion, 2 ATR stretch', vwap, dict(kx=2.0)), ('VWAP reversion, 3 ATR stretch', vwap, dict(kx=3.0)),
       ('GAP fade >= 0.5%', gap, dict(gmin=0.5)), ('GAP fade >= 1.0%', gap, dict(gmin=1.0)),
       ('HOUR1 momentum >= 0.5%', hour1, dict(xm=0.5)), ('HOUR1 momentum >= 1.0%', hour1, dict(xm=1.0))]


def main():
    ds = F.DS(None, PX); ctx = F.context(ds, PX); dm = F.DS(AE.M5, PX); cm = F.context(dm, PX); dd = dm.days[21:]
    BL = [('RH 26-03..10', ds, ctx, [x for x in ds.days[15:] if '2026-03-03' <= x <= '2026-10-14']),
          ('M H1 21-24', dm, cm, [x for x in dd if x < '2024-04-01']), ('M H2 24-26', dm, cm, [x for x in dd if x >= '2024-04-01'])]
    print(__doc__.split('\n')[0]); print('per block: trades, win %, avg leg % per trade, PF (account), account total, %/day, max DD')
    def stats(ds_, days, T):
        a = F.account(ds_, days, T); tk = a['taken']
        if not tk: return 'no trades'
        g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
        return f"n{len(tk):4d} win{100*sum(x['acct'] > 0 for x in tk)/len(tk):3.0f}% avg{st.mean(x['pct'] for x in tk):+.2f}% PF{(g/l if l else 99):5.2f} tot{a['ret']:+7.1f}% {st.mean(a['daily'].values()):+.3f}%/d DD{a['mdd']:5.1f}"
    # reference rows: live FADE and live PULLBACK
    FA = AE.load(); PB = PS.load()
    print(f"  {'LIVE FADE (reference)':<52} " + ' | '.join(f"{B.name[:10]} {stats(B.ds, B.days, [x for x in (FS.manage(t, {}) for t in B.E) if x])}" for B in FA))
    print(f"  {'LIVE PULLBACK (reference)':<52} " + ' | '.join(f"{B.name[:10]} {stats(B.ds, B.days, [PS.manage(t, {}) for t in B.E])}" for B in PB))
    for name, fn, kw in SYS:
        cells = []
        for bn, d_, c_, days in BL:
            T = [x for p in PX if p in d_.bars for d in days if d in d_.bars[p] for x in [fn(d_, c_, p, d, d_.bars[p][d], **kw)] if x]
            cells.append(f"{bn[:10]} {stats(d_, days, T)}")
        print(f"  {name:<52} " + ' | '.join(cells))


if __name__ == '__main__':
    main()
