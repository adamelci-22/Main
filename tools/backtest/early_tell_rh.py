#!/usr/bin/env python3
"""EARLY TELL study (choppy vs clean FADE trades) (governor question 2026-10-28; research only, no rule changed). Based on v5.2.19 evidence: FADE +0.15R lock at the first +0.5R close (B) and early cut 15 min after entry at -0.5R or worse (C), Robinhood cache only.
    python3 tools/backtest/early_tell_rh.py > tools/backtest/results/early_tell_rh.txt
FADE live 6, no Fridays, v5.2.18 exits otherwise (frozen 1R trail capped at +0.75R, 1/3 at 2R, 2-ATR chandelier, out 13:30); 3% risk capped at cash, one position."""
import os, sys, datetime as dt, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(None, F.LIVE); ctx = F.context(ds, F.LIVE); days = [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14']
H1 = [d for d in days if d < '2026-06-24']; H2 = [d for d in days if d >= '2026-06-24']
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
LOCK = (0.5, 0.15); CUT = (3, -0.5)
CFG = dict(N=None, mae=None, nneg=None, alt=None)   # tell: within the first N bars after entry, adverse excursion >= mae R or >= nneg closes below entry -> "choppy"; alt = (kind, X): ('full', X) sell all at +X R, ('half', X) sell half at +X R
def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    at = ctx_['atr'][p][d]; last = c.last; T = entry + s * 2 * r
    rem = 1.0; gross = 0.0; hit = False; hic = entry; bestc = 0.0; j = k; pend = None; out = False
    mae = 0.0; nneg = 0; choppy = False; ptp = False; mfe = 0.0; seen = 0
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: gross += rem * (o - entry) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o; gross += rem * (px - entry) * s; rem = 0; break
        mfe = max(mfe, (fav - entry) * s / r)
        if choppy and CFG['alt']:
            kind, X = CFG['alt']; Xp = entry + s * X * r
            if (fav - Xp) * s >= 0 and not ptp:
                px = Xp if (o - Xp) * s <= 0 else o
                if kind == 'full': gross += rem * (px - entry) * s; rem = 0; break
                gross += 0.5 * (px - entry) * s; rem -= 0.5; ptp = True
                if (entry - stop) * s > 0: stop = entry
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; gross += (1 / 3) * (px - entry) * s; rem = rem - (1 / 3) if rem > 1 / 3 else rem / 2; hit = True
            if (entry - stop) * s > 0: stop = entry
        cr = (cl - entry) * s / r; bestc = max(bestc, cr)
        seen += 1
        if seen <= (CFG['N'] or 6):
            mae = min(mae, (adv - entry) * s / r)
            if cr < 0: nneg += 1
            if seen == (CFG['N'] or 6) and CFG['N']:
                choppy = (CFG['mae'] is not None and -mae >= CFG['mae']) or (CFG['nneg'] is not None and nneg >= CFG['nneg'])
        if LOCK and bestc >= LOCK[0]: pend = entry + s * LOCK[1] * r
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < last:
            ns = hic - s * 2 * at[j]
            if (ns - stop) * s > 0: stop = ns
        if CUT and j - k + 1 == CUT[0] and cr <= CUT[1] and j < last: out = True
    if rem > 0: gross += rem * (b[j][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=j, R_out=gross / r, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100, mae6=-mae, nneg6=nneg, mfe=mfe, choppy=choppy)
    return info
F._manage = manage
def summ(dd, T):
    S = set(dd); a = F.account(ds, dd, [t for t in T if t['day'] in S]); tk = a['taken']
    g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
    return dict(n=len(tk), pf=g / l if l else 99, ret=a['ret'], dd=a['mdd'], avg=sum(t['acct'] for t in tk) / len(tk))
def run(cfg):
    CFG.update(dict(N=None, mae=None, nneg=None, alt=None)); CFG.update(cfg)
    return [t for t in F.trades(ds, days, F.LIVE, F.P(), ctx) if not fri(t['day'])]
# ---- 1. does the first 6 bars (30 min) tell us anything? (base exits; features measured, no rule applied)
T = run({'N': 6})
print(f"1) Base trades: {len(T)}. Keys: {sorted(T[0].keys())[:30]}")
def grp(name, f):
    a = [t for t in T if f(t)]; b = [t for t in T if not f(t)]
    def st_(x):
        if not x: return 'n=0'
        r2 = sum(1 for t in x if t.get('R_out', 0) >= 1.0) / len(x) * 100
        return f"n={len(x):2d} avgR {sum(t['R_out'] for t in x)/len(x):+.2f}  best-run(mfe)>=2R {100*sum(1 for t in x if t['mfe']>=2)/len(x):3.0f}%  mfe median {sorted(t['mfe'] for t in x)[len(x)//2]:.2f}R  win {100*sum(1 for t in x if t['pct']>0)/len(x):3.0f}%"
    print(f"   {name:<46} YES {st_(a)}\n   {'':<46}  NO {st_(b)}")
grp('first 6 bars: adverse excursion >= 0.3R', lambda t: t['mae6'] >= 0.3)
grp('first 6 bars: adverse excursion >= 0.5R', lambda t: t['mae6'] >= 0.5)
grp('first 6 bars: >= 2 closes below entry', lambda t: t['nneg6'] >= 2)
grp('first 6 bars: >= 3 closes below entry', lambda t: t['nneg6'] >= 3)
# ---- 2. treat the 'choppy' ones differently
print("\n2) Choppy trades get an earlier exit (rest of trades: live rules). PF all (half 1 / half 2)")
RUNS = [('BASE (live v5.2.22)', {})]
for N in (4, 6):
    for tell in (dict(mae=0.3), dict(mae=0.5), dict(nneg=2), dict(nneg=3)):
        for alt in (('full', 0.75), ('full', 1.0), ('half', 0.75)):
            RUNS.append((f"N={N} {tell} -> {alt[0]} at +{alt[1]}R", dict(N=N, alt=alt, **tell)))
for name, cfg in RUNS:
    T2 = run(cfg); a, b1, b2 = summ(days, T2), summ(H1, T2), summ(H2, T2)
    nch = sum(1 for t in T2 if t.get('choppy'))
    print(f"  {name:<46} choppy {nch:2d} trades {a['n']:3d} PF {a['pf']:4.2f} ({b1['pf']:4.2f}/{b2['pf']:4.2f}) total {a['ret']:+6.1f}% avg {a['avg']:+5.2f}%")
