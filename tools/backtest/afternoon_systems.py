#!/usr/bin/env python3
"""Third system AFTER 13:30, when FADE and PULLBACK are always flat (governor 2026-11-12: "a 3rd system that adds more trades without
interfering ... maybe later in the day"). Proxies QQQ SOXX IWM XLK XBI XLF SPY, trading the 3x leg (3 x proxy return - 0.06%),
one proxy-day at most one trade, entries from 13:30, everything sold at the 15:55 bar close (nothing overnight). Systems:
  LASTHALF  Gao-Han-Li-Zhou (2018) intraday momentum: the move from the prior close to 10:00 predicts 15:30-15:55. Enter 15:30 with it.
  LASTHALF2 same, only when the 15:00-15:30 move agrees (their best combination).
  PMTREND   afternoon trend continuation: at 13:30 the proxy is >= x% from the open and on the same side of VWAP -> enter with it,
            stop at VWAP (or 2 ATR), out 15:55.
  NOISEPM   Zarattini-Aziz-Barbon (2024) noise-boundary momentum checked at 13:30, 14:00 ... 15:30, exit on a close back inside or 15:55.
  VWAPPM    afternoon VWAP reversion: from 13:30, a close >= k ATR from VWAP fades toward VWAP (target VWAP, stop 1 stretch beyond).
Because the book is flat by 13:30, the combined result is the book's day compounded with the afternoon system's day.
    python3 -I tools/backtest/afternoon_systems.py > tools/backtest/results/afternoon_systems_2026-11-12.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, other_systems as OS, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PX = OS.PX; END = 76                     # bar 76 = 15:55-16:00; exit at its OPEN (15:55) is the last price we trade at
def run2(b, k, s, e, stop, inside=None, T=None):
    j = k; g = None
    for j in range(k, END + 1):
        o, h, l, c, v = b[j]; adv = l if s > 0 else h; fav = h if s > 0 else l
        if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; return j, (px - e) * s
        if T is not None and (fav - T) * s >= 0: px = T if (o - T) * s <= 0 else o; return j, (px - e) * s
        if j == END: return j, (o - e) * s
        if inside and inside(j): return j + 1, (b[j + 1][0] - e) * s
    return j, (b[END][0] - e) * s
def fin(d, p, k, x, e, g, r): return dict(day=d, proxy=p, k=k, xbar=x, R_out=g / r if r else 0, pct=3 * g / e * 100 - F.LEGCOST, leg_risk=3 * r / e * 100 if r else 3.0)
def prevc(ds, p, d):
    i = ds.idx[d]; return ds.bars[p][ds.days[i - 1]][-1][3] if i and ds.days[i - 1] in ds.bars[p] else None
def vwap(b):
    pv = cv = 0.0; out = []
    for x in b: pv += (x[1] + x[2] + x[3]) / 3 * x[4]; cv += x[4]; out.append(pv / cv if cv else x[3])
    return out
def lasthalf(ds, ctx, p, d, b, th=0.0, agree=False):
    pc = prevc(ds, p, d)
    if pc is None: return None
    r1 = b[5][3] / pc - 1
    if abs(r1) * 100 < th or r1 == 0: return None
    s = 1 if r1 > 0 else -1
    if agree and (b[71][3] - b[66][0]) * s <= 0: return None
    k = 72; e = b[k][0]; stop = e - s * 2 * ctx['atr'][p][d][71]
    x, g = run2(b, k, s, e, stop); return fin(d, p, k, x, e, g, abs(e - stop))
def pmtrend(ds, ctx, p, d, b, xm=0.5, stopkind='vwap'):
    vw = vwap(b); m = b[47][3] / b[0][0] - 1
    if abs(m) * 100 < xm: return None
    s = 1 if m > 0 else -1
    if (b[47][3] - vw[47]) * s <= 0: return None
    k = 48; e = b[k][0]; stop = vw[47] if stopkind == 'vwap' else e - s * 2 * ctx['atr'][p][d][47]
    if (e - stop) * s <= 0: return None
    x, g = run2(b, k, s, e, stop); return fin(d, p, k, x, e, g, abs(e - stop))
def noisepm(ds, ctx, p, d, b, n=14):
    i = ds.idx[d]; prior = [ds.bars[p].get(x) for x in ds.days[max(0, i - n):i]]; prior = [x for x in prior if x]
    pc = prevc(ds, p, d)
    if len(prior) < n or pc is None: return None
    o0 = b[0][0]; up0, lo0 = max(o0, pc), min(o0, pc); sig = [st.mean(abs(x[j][3] / x[0][0] - 1) for x in prior) for j in range(78)]
    for j in range(47, 72, 6):
        c = b[j][3]; U = up0 * (1 + sig[j]); Lb = lo0 * (1 - sig[j]); s = 1 if c > U else -1 if c < Lb else 0
        if s:
            k = j + 1; e = b[k][0]; stop = U if s > 0 else Lb
            if (e - stop) * s <= 0: stop = e - s * e * 0.002
            inside = lambda jj, s=s: (b[jj][3] - (up0 * (1 + sig[jj]) if s > 0 else lo0 * (1 - sig[jj]))) * s < 0
            x, g = run2(b, k, s, e, stop, inside=inside); return fin(d, p, k, x, e, g, abs(e - stop))
    return None
def vwappm(ds, ctx, p, d, b, kx=2.0):
    vw = vwap(b); at = ctx['atr'][p][d]
    for j in range(47, 71):
        dev = b[j][3] - vw[j]
        if at[j] > 0 and abs(dev) >= kx * at[j]:
            s = -1 if dev > 0 else 1; k = j + 1; e = b[k][0]; stop = e - s * abs(dev)
            x, g = run2(b, k, s, e, stop, T=vw[j]); return fin(d, p, k, x, e, g, abs(dev))
    return None
SYS = [('LASTHALF (prior close->10:00 sign)', lasthalf, {}), ('LASTHALF >= 0.25%', lasthalf, dict(th=0.25)), ('LASTHALF >= 0.5%', lasthalf, dict(th=0.5)),
       ('LASTHALF2 (+ 15:00-15:30 agrees)', lasthalf, dict(agree=True)), ('LASTHALF2 >= 0.25%', lasthalf, dict(th=0.25, agree=True)),
       ('PMTREND 0.5%, stop VWAP', pmtrend, {}), ('PMTREND 1.0%, stop VWAP', pmtrend, dict(xm=1.0)), ('PMTREND 0.5%, stop 2 ATR', pmtrend, dict(stopkind='atr')),
       ('PMTREND 1.0%, stop 2 ATR', pmtrend, dict(xm=1.0, stopkind='atr')), ('NOISEPM', noisepm, {}), ('VWAPPM 2 ATR', vwappm, {}), ('VWAPPM 3 ATR', vwappm, dict(kx=3.0))]
def curve(d):
    eq = pk = 1.0; mdd = 0.0
    for x in d: eq *= 1 + x / 100; pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100)
    return (eq - 1) * 100, mdd
def main():
    FB = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); RUN = dict(frac=1 / 3, run=('ema', 20))
    ds_rh = F.DS(None, PX); cx_rh = F.context(ds_rh, PX); dm = F.DS(OS.AE.M5, PX); cm = F.context(dm, PX); H = [(ds_rh, cx_rh), (dm, cm), (dm, cm)]
    book = [F.account(PB[b].ds, PB[b].days, [FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, RUN) for t in PB[b].E])['daily'] for b in range(3)]
    names = ['RH 2026', 'M H1 21-24', 'M H2 24-26']
    print(__doc__.split('\n')[0]); print('LIVE BOOK alone: ' + ' | '.join(f"{n} {curve([book[b][d] for d in PB[b].days])[0]:+.1f}% DD {curve([book[b][d] for d in PB[b].days])[1]:.1f}%" for b, n in enumerate(names)))
    print('per block: ALONE n, win %, avg leg %, PF, total, DD | BOOK + SYSTEM total (change vs book) DD')
    for name, fn, kw in SYS:
        cells = []; ok = True
        for b in range(3):
            d_, c_ = H[b]; days = PB[b].days
            T = [x for p in PX if p in d_.bars for d in days if d in d_.bars[p] for x in [fn(d_, c_, p, d, d_.bars[p][d], **kw)] if x]
            a = F.account(d_, days, T, max_entries=3); tk = a['taken']
            if not tk: cells.append(f"{names[b]} no trades"); ok = False; continue
            g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
            alone = curve([a['daily'].get(d, 0.0) for d in days]); bk = curve([book[b].get(d, 0.0) for d in days])
            comb = curve([((1 + book[b].get(d, 0.0) / 100) * (1 + a['daily'].get(d, 0.0) / 100) - 1) * 100 for d in days])
            ok &= comb[0] > bk[0]
            cells.append(f"{names[b]} n{len(tk):4d} w{100*sum(x['acct'] > 0 for x in tk)/len(tk):3.0f}% {st.mean(x['pct'] for x in tk):+.2f}% PF{(g/l if l else 9):4.2f} {alone[0]:+7.1f}% DD{alone[1]:5.1f} | +BOOK {comb[0]:+7.1f}% ({comb[0] - bk[0]:+6.1f}) DD{comb[1]:5.1f}")
        print(f"  {'PASS ' if ok else '     '}{name:<36} " + ' || '.join(cells))
if __name__ == '__main__':
    main()
