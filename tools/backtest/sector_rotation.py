#!/usr/bin/env python3
"""Quarterly universe rotation for FADE across every sector/index ETF that has BOTH a leveraged bull and a leveraged inverse fund.
   /usr/bin/python3 -I tools/backtest/sector_rotation.py M5_MERGED.json.gz > results/sector_rotation.txt
Rules (v5.2.18 live: no Fridays, frozen 1R trail cap +0.75R, 1/3 at 2R, 2-ATR chandelier, out 13:30; 3% risk, one position, max 3 entries/day).
Each quarter the list is chosen ONLY from the previous quarter's data:
  ETF momentum (best / worst prior-quarter return), chop (lowest |return| / volatility), FADE momentum (best / worst prior-quarter avg R per setup).
Leverage per proxy = the real pair (3x where 3x pairs exist; 2x ProShares pairs on thin sectors)."""
import os, sys, collections, statistics as st, datetime as dt, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
PAIRS = {  # proxy: (bull, bear, lev_bull, lev_bear, liquid?)
 'QQQ': ('TQQQ', 'SQQQ', 3, 3, 1), 'SPY': ('SPXL', 'SPXS', 3, 3, 1), 'DIA': ('UDOW', 'SDOW', 3, 3, 1), 'IWM': ('TNA', 'TZA', 3, 3, 1),
 'XLK': ('TECL', 'TECS', 3, 3, 1), 'XLF': ('FAS', 'FAZ', 3, 3, 1), 'SOXX': ('SOXL', 'SOXS', 3, 3, 1), 'XBI': ('LABU', 'LABD', 3, 3, 1),
 'XLE': ('ERX', 'ERY', 2, 2, 1), 'XLRE': ('DRN', 'DRV', 3, 3, 1), 'TLT': ('TMF', 'TMV', 3, 3, 1),
 'XLB': ('UYM', 'SMN', 2, 2, 0), 'XLV': ('CURE', 'RXD', 3, 2, 0), 'XLU': ('UTSL', 'SDP', 3, 2, 0), 'XLP': ('UGE', 'SZK', 2, 2, 0),
 'XLI': ('UXI', 'SIJ', 2, 2, 0), 'XLY': ('UCC', 'SCC', 2, 2, 0)}
for p, v in PAIRS.items(): F.LEV[p] = (v[2], v[3])
LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
LIQ = [p for p, v in PAIRS.items() if v[4]]; ALLP = list(PAIRS)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frozen_vs_chand3.py')).read()
ns = {'__file__': os.path.abspath(__file__)}; exec(src[:src.index("fri = lambda")], ns)
ns['K'].update(k=2.0, frozen=True)
ds = F.DS(sys.argv[1], ALLP); have = [p for p in ALLP if p in ds.bars]
ctx = F.context(ds, have); days = ds.days[21:]
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
SET = [t for t in F.trades(ds, days, have, F.P(), ctx) if not fri(t['day'])]
q = lambda d: f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"
quarters = sorted(set(q(d) for d in days)); qdays = collections.defaultdict(list)
for d in days: qdays[q(d)].append(d)
# prior-quarter features per proxy
def close(p, d): return ds.bars[p][d][-1][3]
feat = {}
for i, Q in enumerate(quarters):
    if i == 0: continue
    P = qdays[quarters[i - 1]]; f = {}
    for p in have:
        dd = [d for d in P if d in ds.bars[p]]
        if len(dd) < 20: continue
        ret = close(p, dd[-1]) / close(p, dd[0]) - 1
        rr = [close(p, dd[j]) / close(p, dd[j - 1]) - 1 for j in range(1, len(dd))]
        vol = st.pstdev(rr) * math.sqrt(len(rr))
        fr = [t['R_out'] for t in SET if t['proxy'] == p and q(t['day']) == quarters[i - 1]]
        f[p] = dict(ret=ret, chop=abs(ret) / vol if vol else 9, fadeR=(sum(fr) / len(fr)) if len(fr) >= 3 else None, n=len(fr))
    feat[Q] = f
def pick(Q, rule, pool, N):
    f = {p: v for p, v in feat.get(Q, {}).items() if p in pool}
    if not f: return pool
    if rule == 'best_ret': return sorted(f, key=lambda p: -f[p]['ret'])[:N]
    if rule == 'worst_ret': return sorted(f, key=lambda p: f[p]['ret'])[:N]
    if rule == 'chop': return sorted(f, key=lambda p: f[p]['chop'])[:N]
    if rule == 'trend': return sorted(f, key=lambda p: -f[p]['chop'])[:N]
    g = {p: v for p, v in f.items() if v['fadeR'] is not None}
    if rule == 'best_fade': return sorted(g, key=lambda p: -g[p]['fadeR'])[:N]
    if rule == 'worst_fade': return sorted(g, key=lambda p: g[p]['fadeR'])[:N]
def evaluate(lists):
    T = [t for t in SET if t['proxy'] in lists.get(q(t['day']), [])]
    out = {}
    for tag, dd in (('all', days), ('H1', [d for d in days if d < '2024-04-01']), ('H2', [d for d in days if d >= '2024-04-01'])):
        S = set(dd); a = F.account(ds, dd, [t for t in T if t['day'] in S]); tk = a['taken']; s = F.stat(a)
        g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
        out[tag] = dict(n=len(tk), pf=g / l if l else 99, day=s['avg'], dd=s['mdd'], ret=a['ret'], green=100 * sum(t['acct'] > 0 for t in tk) / max(1, len(tk)))
    yrs = {}
    for y in ('2022', '2023', '2024', '2025', '2026'):
        dd = [d for d in days if d[:4] == y]; S = set(dd)
        a = F.account(ds, dd, [t for t in T if t['day'] in S]); yrs[y] = F.stat(a)['avg']
    return out, yrs
print(f"Universe with BOTH leveraged bull and inverse funds (proxy: bull/bear, leverage). Data present: {', '.join(have)}")
for p, v in PAIRS.items(): print(f"  {p:<5} {v[0]}/{v[1]} {v[2]}x/{v[3]}x {'liquid' if v[4] else 'THIN (wide spreads, few trades per hour)'}")
print("  XLC (communication services): no leveraged inverse fund -> excluded")
print(f"\nPer-proxy FADE results, whole 5 years (setups, not account; no Fridays, v5.2.18 exits):")
for p in have:
    r = [t['R_out'] for t in SET if t['proxy'] == p]
    if r: print(f"  {p:<5} setups {len(r):4d}  avg {sum(r)/len(r):+.3f}R  win {100*sum(x>0 for x in r)/len(r):3.0f}%  "
                f"H1 {st.mean([t['R_out'] for t in SET if t['proxy']==p and t['day']<'2024-04-01'] or [0]):+.3f}R  H2 {st.mean([t['R_out'] for t in SET if t['proxy']==p and t['day']>='2024-04-01'] or [0]):+.3f}R")
rows = []
def show(tag, lists):
    o, y = evaluate(lists); rows.append((tag, o, y))
    a, h1, h2 = o['all'], o['H1'], o['H2']
    print(f"  {tag:<44} n{a['n']:4d} PF {a['pf']:4.2f} green {a['green']:3.0f}% {a['day']:+.3f}%/d (H1 {h1['day']:+.3f} H2 {h2['day']:+.3f}) DD{a['dd']:5.1f}% total {a['ret']:+6.1f}% | "
          + ' '.join(f"{k} {v:+.3f}" for k, v in y.items()))
print("\nACCOUNT RESULTS (5 years; one position at a time; years = %/day)")
fixed = lambda L: {Q: L for Q in quarters}
show('FIXED live 6 (QQQ SOXX IWM XLK XBI XLF)', fixed(LIVE6))
show('FIXED all 11 liquid pairs', fixed(LIQ))
show('FIXED all 17 (incl. thin 2x pairs)', fixed(ALLP))
for pool, pname in ((LIQ, 'liquid 11'), (ALLP, 'all 17')):
    for N in (3, 6):
        for rule in ('best_ret', 'worst_ret', 'chop', 'trend', 'best_fade', 'worst_fade'):
            show(f"{pname}: top {N} by {rule}", {Q: pick(Q, rule, pool, N) for Q in quarters})
print("\nLists chosen by 'liquid 11: top 6 by best_fade' per quarter:")
for Q in quarters[1:]: print(f"  {Q}: {' '.join(pick(Q, 'best_fade', LIQ, 6))}")
