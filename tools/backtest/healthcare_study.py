#!/usr/bin/env python3
"""Healthcare study: (1) XLV as a FADE proxy with CURE (3x bull) / RXD (2x bear) as its legs, (2) CURE and RXD as PULLBACK tickers.
    python3 tools/backtest/healthcare_study.py > tools/backtest/results/healthcare_study.txt
Same harness, window and account rules as final_system.py / payout_ideas.py (D3: both halves + the untouched March window).
CHOOSE-WINDOW = TUNE-H1 2026-04-07..07-10; JUDGE on TUNE-H2 07-13..10-14 and MARCH 03-03..04-06.
Realism: the backtest carries a leg with no trade in a 5-min bar forward flat (as if it filled). CURE and RXD are thin, so every
candidate is also shown with a FILL filter: drop trades whose entry bar or exit bar had no real trade in the leg.
"""
import io, contextlib, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA, final_system as FS, twobar as TB
    from lab import get_data

D = get_data(); m.rvol = PBF.rvol(D); ALL = D.days[1:]
MAR = [d for d in ALL if d < '2026-04-07']; TUNE = [d for d in ALL if d >= '2026-04-07']; h = len(TUNE) // 2; H1, H2 = TUNE[:h], TUNE[h:]
ROW = ('CURE', 3, 'RXD', 2)                       # XLV proxy -> bull leg, lev, bear leg, lev (CURE 3x bull, RXD 2x ultrashort)
print(f"HEALTHCARE STUDY  ALL {ALL[0]}..{ALL[-1]} ({len(ALL)} d) | H1 {H1[0]}..{H1[-1]} | H2 {H2[0]}..{H2[-1]} | MARCH {MAR[0]}..{MAR[-1]}\n")

# ------------------------------------------------------------------ 0. liquidity / real-bar coverage
print("== 0. LIQUIDITY: share of 5-min bars 10:00-13:30 with a real trade, and median $ per bar (needs >= $250,000 to count as liquid) ==")
def cover(s):
    n = r = 0
    for d in ALL:
        if d not in D.bars.get(s, {}): continue
        for x in D.bars[s][d][6:47]:
            n += 1; r += x[4] > 0
    return r / n if n else 0
for s in ('XLV', 'XBI', 'XLK', 'TECL', 'TECS', 'LABU', 'LABD', 'AMDL', 'AMDD', 'CURE', 'RXD'):
    if s not in D.bars: print(f"   {s:<5} no data"); continue
    print(f"   {s:<5} real-bar coverage {100*cover(s):5.1f}%   median $/bar {EX.dollar_vol(D, s, ALL):>12,.0f}")

# ------------------------------------------------------------------ helpers
def fade_raw(days):
    saved = TB.ROWS.get('XLV'); TB.ROWS['XLV'] = (ROW[0], ROW[2], ROW[1])
    out = []
    for d in days:
        if d not in D.bars.get('XLV', {}): continue
        t = EX.FC.run_trade(D, d, 'XLV', R=2.0, frac=1 / 3, runner='chand2', last=47)
        if not t: continue
        if t['side'] < 0 and ROW[3] != ROW[1]:
            t['pct'] = (t['pct'] + TB.LEGCOST) / ROW[1] * ROW[3] - TB.LEGCOST; t['leg_risk'] = t['leg_risk'] / ROW[1] * ROW[3]
        out.append(t)
    if saved: TB.ROWS['XLV'] = saved
    else: del TB.ROWS['XLV']
    return out

def fills(leg, d, k, x):
    b = D.bars[leg][d]; return b[k][4] > 0 and b[x][4] > 0

def acct(cands):
    a = MXD.account(D, ALL, cands); dl = a['daily']; v = lambda ds: st.mean(dl[d] for d in ds)
    return dict(all=v(ALL), h1=v(H1), h2=v(H2), mar=v(MAR), ret=a['ret'], dd=a['mdd'], n=len(a['taken']))

f0, p0 = FS.cands(D, ALL); BASE = acct(f0 + p0)
def line(label, r, ref=BASE):
    ok = r['h2'] > ref['h2'] and r['mar'] > ref['mar'] and r['all'] > ref['all']
    print(f"   {label:<46} {r['all']:+.3f}%/day (H1 {r['h1']:+.3f} H2 {r['h2']:+.3f} Mar {r['mar']:+.3f}) ret {r['ret']:+7.1f}% DD {r['dd']:4.1f}% n {r['n']:3d}" + ('  BEATS BASE H2+MARCH' if ok else ''))
print()
line('BASE (live system)', BASE)

# ------------------------------------------------------------------ 1. FADE on XLV
print("\n== 1. FADE with XLV as proxy, legs CURE (3x) / RXD (2x) ==")
T = fade_raw(ALL)
print(f"   XLV fade trades: {len(T)}; win {100*sum(t['pct']>0 for t in T)/max(1,len(T)):.0f}%; avg leg result {st.mean(t['pct'] for t in T) if T else 0:+.3f}%")
for nm, ds in (('H1', H1), ('H2', H2), ('MARCH', MAR)):
    x = [t['pct'] for t in T if t['day'] in set(ds)]
    print(f"      {nm:<6} n {len(x):2d}  avg {st.mean(x) if x else 0:+.3f}%  win {100*sum(v>0 for v in x)/max(1,len(x)):.0f}%")
real = [t for t in T if fills(ROW[0] if t['side'] > 0 else ROW[2], t['day'], t['k'], t['xbar'])]
print(f"   with a real trade in the leg on BOTH the entry bar and the exit bar: {len(real)} of {len(T)} trades ({100*len(real)/max(1,len(T)):.0f}%)")
for nm, TT in (('as modelled (flat-carried bars fill)', T), ('FILL filter (real trades only)', real)):
    cand = MXD.norm_px(TT, 'FADE')
    line(f'FADE + XLV [{nm}], no PB', acct(f0 + cand), acct(f0))
    line(f'FADE + XLV [{nm}] + PB (full system)', acct(f0 + cand + p0))

# ------------------------------------------------------------------ 2. PULLBACK tickers
print("\n== 2. PULLBACK with CURE and/or RXD added (own chart, same rules) ==")
PI.PROXY.update({'CURE': 'CURE', 'RXD': 'RXD'})
for tick in (['RXD'], ['CURE'], ['CURE', 'RXD']):
    S = PBF.run(D, ALL, tick, oco_gap=True)
    pm = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S]
    rl = [c for c in pm if fills(c['name'], c['day'], c['k'], c['xbar'])]
    print(f"   {'+'.join(tick)} alone: {len(pm)} setups, avg {st.mean(c['pct'] for c in pm) if pm else 0:+.3f}%; with real fills on entry and exit bars: {len(rl)}")
    line(f"PB + {'+'.join(tick)} [as modelled]", acct(f0 + p0 + pm))
    line(f"PB + {'+'.join(tick)} [FILL filter]", acct(f0 + p0 + rl))
