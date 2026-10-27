#!/usr/bin/env python3
"""Detail for candidate #2: no FADE Fridays + chandelier k ATR after the 2R partial (live: k=2).  /usr/bin/python3 -I tools/backtest/chand3_detail.py M5.json.gz"""
import os, sys, datetime as dt, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
K = {}
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; mfe = 0.0; run_exit = None; j = k
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; run_exit = (px - entry) * s / r; rem = 0; break
        mfe = max(mfe, (fav - entry) * s / r)
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o
            gross += (1 / 3) * (px - entry) * s; rem = 2 / 3; hit = True
            if (entry - stop) * s > 0: stop = entry
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * K['k'] * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s; run_exit = (b[last][3] - entry) * s / r
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=j, hit=hit, mfe=mfe, run_exit=run_exit, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info
F._manage = manage
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
def summary(ds, days, T):
    a = F.account(ds, days, T); tk = a['taken']; s = F.stat(a)
    g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
    hit = [t for t in tk if t['hit']]
    keep = sum(max(t['run_exit'], 0) / t['mfe'] for t in hit) / len(hit) if hit else 0
    return dict(n=len(tk), pf=g / l if l else 99, day=s['avg'], dd=s['mdd'], ret=a['ret'], green=100 * sum(t['acct'] > 0 for t in tk) / len(tk),
                run=sum(t['run_exit'] for t in hit) / len(hit) if hit else 0, keep=100 * keep, big=sum(t['R_out'] >= 3 for t in tk))
for name, src in (('ROBINHOOD 2026-03..10', None), ('MASSIVE 5 YEARS', sys.argv[1])):
    ds = F.DS(src, F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
    days = ds.days[1:] if src is None else ds.days[21:]
    split = sorted(days)[len(days) // 2] if src is None else '2024-04-01'
    print(f"\n== {name}  (FADE only, no Fridays; PULLBACK unaffected)")
    print(f"{'chandelier':<12} {'trades':>6} {'green':>6} {'PF':>5} {'%/day':>7} {'H1':>7} {'H2':>7} {'maxDD':>6} {'total':>7} {'runner exit':>11} {'kept of peak':>12} {'trades>=3R':>10}")
    for k in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        K['k'] = k
        T = [t for t in F.trades(ds, days, syms, F.P(), ctx) if not fri(t['day'])]
        a = summary(ds, days, T); h1 = summary(ds, [d for d in days if d < split], [t for t in T if t['day'] < split]); h2 = summary(ds, [d for d in days if d >= split], [t for t in T if t['day'] >= split])
        tag = f"{k} ATR" + ('  <- live' if k == 2.0 else ('  <- #2' if k == 3.0 else ''))
        print(f"{tag:<12} {a['n']:>6} {a['green']:>5.0f}% {a['pf']:>5.2f} {a['day']:>+6.3f}% {h1['day']:>+6.3f}% {h2['day']:>+6.3f}% {a['dd']:>5.1f}% {a['ret']:>+6.1f}% {a['run']:>+10.2f}R {a['keep']:>11.0f}% {a['big']:>10}")
    if src:
        print("  by year, %/day (chandelier 2 -> 3):")
        for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
            dd = [d for d in days if d[:4] == y]
            if len(dd) < 20: continue
            out = []
            for k in (2.0, 3.0):
                K['k'] = k; T = [t for t in F.trades(ds, dd, syms, F.P(), ctx) if not fri(t['day'])]; out.append(summary(ds, dd, T))
            print(f"   {y}: {out[0]['day']:+.3f} -> {out[1]['day']:+.3f}  (PF {out[0]['pf']:.2f} -> {out[1]['pf']:.2f}, {out[0]['n']} trades)")
