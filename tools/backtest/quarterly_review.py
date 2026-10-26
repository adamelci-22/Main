#!/usr/bin/env python3
"""Why did the 10-minute box do so well in 2024, can a quarterly review see it coming?   /usr/bin/python3 -I tools/backtest/quarterly_review.py M5.json.gz > results/quarterly_review.txt
Box-only variants (live rules, same 10:15 break deadline). FADE only (PULLBACK is unchanged in every variant)."""
import collections, math, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
SRC = sys.argv[1]; LIVE = F.LIVE
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); days = ds.days[21:]
qkey = lambda d: f"{d[:4]}-Q{(int(d[5:7]) - 1) // 3 + 1}"
quarters = sorted({qkey(d) for d in days})
V = {n: F.trades(ds, days, LIVE, F.P(box=n, brk_end=9), ctx) for n in (1, 2, 3, 4, 5, 6)}
acc = {n: F.account(ds, days, V[n]) for n in V}; nm = {1: '5min', 2: '10min', 3: '15min', 4: '20min', 5: '25min', 6: '30min(live)'}
print(f"Massive bars {days[0]}..{days[-1]}; FADE six proxies, live exits, 3% risk; box length is the only difference\n")

print("A. WHAT MADE 2024 (10-minute box vs the live 30-minute box)")
T10 = [t for t in V[2] if t['day'].startswith('2024')]; T30 = [t for t in V[6] if t['day'].startswith('2024')]
for lab, T in (('10-min', T10), ('30-min', T30)):
    r = sorted((t['R_out'] for t in T), reverse=True); tot = sum(r)
    print(f"  {lab}: {len(T)} setups, sum R {tot:+.1f}, avg R {st.mean(r):+.3f}; best 10 setups add {sum(r[:10]):+.1f} R ({100*sum(r[:10])/tot if tot>0 else float('nan'):.0f}% of the total); without the best 10: {tot-sum(r[:10]):+.1f} R; setups with R >= 3: {sum(1 for x in r if x>=3)}")
print("  by quarter 2024 (setups, avg R, share of days with a setup):")
for q in [q for q in quarters if q.startswith('2024')]:
    for lab, n in (('10-min', 2), ('30-min', 6)):
        v = [t for t in V[n] if qkey(t['day']) == q]; dq = [d for d in days if qkey(d) == q]
        print(f"    {q} {lab}: n {len(v):3d} avg R {st.mean(t['R_out'] for t in v):+.2f} setups/day {len(v)/len(dq):.2f}")
print("  by proxy 2024 (10-min): " + '  '.join(f"{p} {st.mean([t['R_out'] for t in T10 if t['proxy']==p] or [0]):+.2f}({sum(1 for t in T10 if t['proxy']==p)})" for p in LIVE))
print("  by side 2024 (10-min): up-break faded " + f"{st.mean([t['R_out'] for t in T10 if t['side']<0]):+.2f} ({sum(1 for t in T10 if t['side']<0)}), down-break faded {st.mean([t['R_out'] for t in T10 if t['side']>0]):+.2f} ({sum(1 for t in T10 if t['side']>0)})")
mo = collections.defaultdict(float)
for t in T10: mo[t['day'][:7]] += t['R_out']
print("  sum R by month 2024 (10-min): " + ', '.join(f"{m[5:]} {v:+.0f}" for m, v in sorted(mo.items())))

print("\nB. MARKET BACKDROP PER QUARTER vs HOW EACH BOX DID (avg R per setup)")
print(f"  {'quarter':<8}{'10min R':>8}{'30min R':>8}{'QQQ %':>7}{'QQQ vol':>8}{'avg |gap|':>10}{'open-30 range':>14}{'setups/day 10m':>15}")
rows = {}
for q in quarters:
    dq = [d for d in days if qkey(d) == q]
    if len(dq) < 30: continue
    qq = [ds.bars['QQQ'][d][-1][3] for d in dq]; rets = [qq[i] / qq[i - 1] - 1 for i in range(1, len(qq))]
    gaps = [abs(ctx['gap'][p][d]) * 100 for p in LIVE for d in dq if d in ctx['gap'][p]]
    orr = [(max(x[1] for x in ds.bars[p][d][:6]) - min(x[2] for x in ds.bars[p][d][:6])) / ds.bars[p][d][0][0] * 100 for p in LIVE for d in dq]
    r10 = st.mean(t['R_out'] for t in V[2] if qkey(t['day']) == q); r30 = st.mean(t['R_out'] for t in V[6] if qkey(t['day']) == q)
    sp = sum(1 for t in V[2] if qkey(t['day']) == q) / len(dq)
    rows[q] = dict(r10=r10, r30=r30, ret=(qq[-1] / qq[0] - 1) * 100, vol=st.pstdev(rets) * 100, gap=st.mean(gaps), orr=st.mean(orr), sp=sp)
    print(f"  {q:<8}{r10:>+8.2f}{r30:>+8.2f}{rows[q]['ret']:>+7.1f}{rows[q]['vol']:>8.2f}{rows[q]['gap']:>10.2f}{rows[q]['orr']:>14.2f}{sp:>15.2f}")
qs = list(rows)


def spear(a, b):
    def rk(v): o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v); [r.__setitem__(i, p) for p, i in enumerate(o)]; return r
    ra, rb = rk(a), rk(b); ma, mb = st.mean(ra), st.mean(rb); den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / den if den else float('nan')


print(f"\n  Spearman with the 10-minute box's quarterly avg R ({len(qs)} quarters; |rho| > 0.45 needed for 5% significance). 'same quarter' is known only afterwards; 'prior quarter' is what a review could use:")
for key, lab in (('ret', 'QQQ quarter return'), ('vol', 'QQQ daily volatility'), ('gap', 'avg |opening gap|'), ('orr', 'avg first-30-min range'), ('sp', 'setups per day (how often early breaks fail)'), ('r10', "the 10-min box's own result")):
    same = spear([rows[q][key] for q in qs], [rows[q]['r10'] for q in qs]); prior = spear([rows[qs[i]][key] for i in range(len(qs) - 1)], [rows[qs[i + 1]]['r10'] for i in range(len(qs) - 1)])
    print(f"    {lab:<46} same quarter {same:+.2f}   prior quarter -> next {prior:+.2f}")

print("\nC. COULD A QUARTERLY REVIEW HAVE PICKED THE BOX? (each quarter choose the box with the best account %/day over the trailing N quarters; daily account results are independent of equity, so stitching is exact)")
dq_idx = collections.defaultdict(list)
for d in days: dq_idx[qkey(d)].append(d)
first_test = qs.index('2023-Q1')


def pick_strategy(cands, N):
    chosen = {}; stitched = {}
    for i in range(first_test, len(qs)):
        q = qs[i]; hist = [d for qq_ in qs[max(0, i - N):i] for d in dq_idx[qq_]]
        best = max(cands, key=lambda n: st.mean(acc[n]['daily'][d] for d in hist)); chosen[q] = best
        for d in dq_idx[q]: stitched[d] = acc[best]['daily'][d]
    return chosen, stitched


def summ(daily):
    eq = 1.0; pk = 1.0; mdd = 0.0
    for d in sorted(daily): eq *= 1 + daily[d] / 100; pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100)
    return st.mean(daily.values()), (eq - 1) * 100, mdd


test_days = [d for q in qs[first_test:] for d in dq_idx[q]]
print(f"  test period {test_days[0]}..{test_days[-1]} ({len(test_days)} days)")
for lab, fn in (('fixed 30-min (LIVE)', lambda: {d: acc[6]['daily'][d] for d in test_days}), ('fixed 10-min', lambda: {d: acc[2]['daily'][d] for d in test_days}), ('fixed 15-min', lambda: {d: acc[3]['daily'][d] for d in test_days})):
    a, r, m_ = summ(fn()); print(f"  {lab:<42} {a:+.3f}%/day  return {r:+8.1f}%  max DD {m_:5.1f}%")
oracle = {}
for q in qs[first_test:]:
    best = max((2, 3, 6), key=lambda n: st.mean(acc[n]['daily'][d] for d in dq_idx[q]))
    for d in dq_idx[q]: oracle[d] = acc[best]['daily'][d]
a, r, m_ = summ(oracle); print(f"  {'ORACLE: best of 10/15/30 in hindsight':<42} {a:+.3f}%/day  return {r:+8.1f}%  max DD {m_:5.1f}%   (the ceiling, not achievable)")
for N in (2, 4):
    for cands, lab in (((2, 3, 6), '10/15/30'), ((1, 2, 3, 4, 5, 6), '5 to 30')):
        ch, stch = pick_strategy(cands, N); a, r, m_ = summ(stch); hits = 0
        for q in qs[first_test:]:
            truth = max(cands, key=lambda n: st.mean(acc[n]['daily'][d] for d in dq_idx[q])); hits += ch[q] == truth
        print(f"  quarterly pick among {lab:<9} trailing {N}Q            {a:+.3f}%/day  return {r:+8.1f}%  max DD {m_:5.1f}%   picked the real best in {hits} of {len(qs)-first_test} quarters (chance {100/len(cands):.0f}%)")
print("  picks (10/15/30, trailing 4Q): " + ' '.join(f"{q[2:]}:{nm[c][:4]}" for q, c in pick_strategy((2, 3, 6), 4)[0].items()))
print("\n  quarterly avg %/day of each box (account) for reference:")
print("  " + ' '.join(f"{q[2:]}" for q in qs[first_test:]))
for n in (2, 6): print(f"  {nm[n]:<12}" + ' '.join(f"{st.mean(acc[n]['daily'][d] for d in dq_idx[q]):+5.2f}" for q in qs[first_test:]))
