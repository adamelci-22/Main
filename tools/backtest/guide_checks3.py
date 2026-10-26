#!/usr/bin/env python3
"""Calibrate the proposed circuit breakers against the real trade record, and test whether the 15-minute-box 'lead' is distinguishable from noise.
    /usr/bin/python3 -I tools/backtest/guide_checks3.py M5.json.gz > tools/backtest/results/guide_checks3.txt"""
import contextlib, io, math, os, random, statistics as st, sys
from dataclasses import replace
SRC = sys.argv[1]; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.argv = ['regime_adapt.py', SRC]
with contextlib.redirect_stdout(io.StringIO()):
    import regime_adapt as RA
F = RA.F; ds = RA.ds; T = RA.T; days = RA.days; CUT = '2026-03-01'; LIVE = F.LIVE; ctx = RA.ctx
pre = [d for d in days if d < CUT]; rec = [d for d in days if d >= CUT]; rnd = random.Random(21)
print("Worlds for the simulation: NO-EDGE = the 797 setups before 2026-03; EDGE = the 119 setups since 2026-03 (the period the rules were built on).\n")
Rs = {'null': [t['R_out'] for t in T if t['day'] < CUT], 'edge': [t['R_out'] for t in T if t['day'] >= CUT]}
sd = st.pstdev(Rs['null']); print(f"std of R per trade {sd:.2f}; avg R null {st.mean(Rs['null']):+.3f}, edge {st.mean(Rs['edge']):+.3f}")
print(f"trades needed to tell +0.20 R from zero at 5% error and 90% power: {math.ceil(((1.645+1.2816)*sd/0.20)**2)}; to tell +0.10: {math.ceil(((1.645+1.2816)*sd/0.10)**2)}\n")

print("A. 40-TRADE REVIEW AT LIVE SIZE: how often would each proposed pause rule fire, in each world? (account-% per trade from the real account at the given risk; 4000 bootstrap runs)")
for risk in (0.03, 0.01):
    pools = {}
    for w, dd, cf in (('null', pre, lambda d: d < CUT), ('edge', rec, lambda d: d >= CUT)):
        a = F.account(ds, dd, [t for t in T if cf(t['day'])], risk=risk); pools[w] = [(x['acct'], x['R_out']) for x in a['taken']]
    for w in ('null', 'edge'):
        dd_hit = 0; avgr_lt0 = 0; avgdaily_lt = 0; pctdd = []
        for _ in range(4000):
            seq = [rnd.choice(pools[w]) for _ in range(40)]; eq = 1.0; pk = 1.0; mdd = 0.0
            for a_, r_ in seq: eq *= 1 + a_ / 100; pk = max(pk, eq); mdd = max(mdd, 1 - eq / pk)
            dd_hit += mdd > 0.08; avgr_lt0 += st.mean(r for _, r in seq) < 0; pctdd.append(mdd)
        print(f"  risk {risk*100:.0f}% {w:>4}: pause on drawdown >8% within 40 trades: {100*dd_hit/4000:3.0f}%   pause if avg R of the 40 < 0: {100*avgr_lt0/4000:3.0f}%   median max drawdown {100*st.median(pctdd):.1f}%")

print("\nB. RESTART RULE 'any 15 simulated trades averaging > +0.20 R': how often does the NO-EDGE world satisfy it?")
for n_try in (1, 10, 40):
    ok = sum(any(st.mean(rnd.choice(Rs['null']) for _ in range(15)) > 0.20 for _ in range(n_try)) for _ in range(3000))
    print(f"  chance in {n_try:>2} tries (one try per 15 trades): {100*ok/3000:.0f}% (edge world: {100*sum(any(st.mean(rnd.choice(Rs['edge']) for _ in range(15)) > 0.20 for _ in range(n_try)) for _ in range(1000))/1000:.0f}%)")
print("  paper equity making a new 20-day high is not a test either: a flat random series does it all the time.")

print("\nC. IS THE 15-MINUTE-BOX 'LEAD' REAL? z-score of each variant's average R before 2026-03 (23 variants were looked at, the best always looks good)")
abl = {'live': F.P(), 'box15': F.P(box=3, brk_end=6), 'box45': F.P(box=9, brk_end=12), 'R1': F.P(R=1.0), 'R3': F.P(R=3.0), 'nochand': F.P(chand=0), 'chand3': F.P(chand=3.0), 'last29': F.P(last=29), 'last77': F.P(last=77),
       'tol0': F.P(tol=0.0), 'tol.3': F.P(tol=0.3), 'wait3': F.P(wait=3), 'brk12': F.P(brk_end=12), 'brk7': F.P(brk_end=7), 'floor.3': F.P(floor_pct=0.3), 'floor.5': F.P(floor_pct=0.5),
       'upbreaks': F.P(side=-1), 'downbreaks': F.P(side=1), 'gapwith': F.P(gap='with'), 'frac0': F.P(frac=0.0), 'frac.5': F.P(frac=0.5), 'nobe': F.P(be=False), 'box4': F.P(box=4, brk_end=7)}
zs = {}
for k, c in abl.items():
    v = [t['R_out'] for t in F.trades(ds, days, LIVE, c, ctx) if t['day'] < CUT]; zs[k] = (st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))), st.mean(v), len(v))
for k, (z, m_, n_) in sorted(zs.items(), key=lambda kv: -kv[1][0])[:6]: print(f"  {k:<10} avg R {m_:+.3f}  n {n_}  z {z:+.2f}")
best = max(v[0] for v in zs.values()); print(f"  best z among {len(zs)} variants = {best:+.2f}. For {len(zs)} pure-noise variants the expected best z is about +{(2*math.log(len(zs)))**.5 - 0.6:.1f}; a z of 2 or less is not evidence.")
