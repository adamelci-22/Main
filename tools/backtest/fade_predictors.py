#!/usr/bin/env python3
"""Does anything in a prior window predict WHERE (which ETF) or WHEN (which period) FADE works next window?
   /usr/bin/python3 -I tools/backtest/fade_predictors.py M5_ALL.json.gz > results/fade_predictors.txt
Universe: every sector, total-market and international ETF with BOTH a leveraged bull and a leveraged inverse fund (23 proxies).
Windows: month, quarter, half-year. Rules: v5.2.18 live (no Fridays, frozen 1R trail cap +0.75R, 1/3 at 2R, 2-ATR chandelier, out 13:30).
Part 1 (WHERE): per window, Spearman rank correlation (IC) across ETFs between a prior-window feature and next-window FADE avg R per setup.
Part 2 (WHEN): across windows, Spearman correlation between prior-window market features and next-window FADE avg R (live 6 and all).
Part 3: selection backtests (account, one position) for each window length; feature + direction chosen on H1 only, then judged on H2."""
import os, sys, collections, statistics as st, datetime as dt, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
PAIRS = {  # proxy: (bull, bear, lev_bull, lev_bear, liquid?)
 'QQQ': ('TQQQ', 'SQQQ', 3, 3, 1), 'SPY': ('SPXL', 'SPXS', 3, 3, 1), 'DIA': ('UDOW', 'SDOW', 3, 3, 1), 'IWM': ('TNA', 'TZA', 3, 3, 1),
 'XLK': ('TECL', 'TECS', 3, 3, 1), 'XLF': ('FAS', 'FAZ', 3, 3, 1), 'SOXX': ('SOXL', 'SOXS', 3, 3, 1), 'XBI': ('LABU', 'LABD', 3, 3, 1),
 'XLE': ('ERX', 'ERY', 2, 2, 1), 'XLRE': ('DRN', 'DRV', 3, 3, 1), 'TLT': ('TMF', 'TMV', 3, 3, 1), 'FXI': ('YINN', 'YANG', 3, 3, 1),
 'XLB': ('UYM', 'SMN', 2, 2, 0), 'XLV': ('CURE', 'RXD', 3, 2, 0), 'XLU': ('UTSL', 'SDP', 3, 2, 0), 'XLP': ('UGE', 'SZK', 2, 2, 0),
 'XLI': ('UXI', 'SIJ', 2, 2, 0), 'XLY': ('UCC', 'SCC', 2, 2, 0), 'MDY': ('UMDD', 'SMDD', 3, 3, 0), 'IJR': ('SAA', 'SDD', 2, 2, 0),
 'EEM': ('EDC', 'EDZ', 3, 3, 0), 'EFA': ('EFO', 'EFU', 2, 2, 0), 'EWJ': ('EZJ', 'EWV', 2, 2, 0)}
for p, v in PAIRS.items(): F.LEV[p] = (v[2], v[3])
LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
LIQ = [p for p, v in PAIRS.items() if v[4]]; ALLP = list(PAIRS)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frozen_vs_chand3.py')).read()
src = src[:src.index("fri = lambda")].replace("info.update(xbar=j,", "info.update(best=bestc, xbar=j,")
ns = {'__file__': os.path.abspath(__file__)}; exec(src, ns); ns['K'].update(k=2.0, frozen=True)
ds = F.DS(sys.argv[1], ALLP + ['VIXY']); have = [p for p in ALLP if p in ds.bars]
ctx = F.context(ds, have); days = ds.days[21:]
fri = lambda d: dt.date.fromisoformat(d).weekday() == 4
SET = [t for t in F.trades(ds, days, have, F.P(), ctx) if not fri(t['day'])]
SPLIT = '2024-04-01'
WIN = {'month': lambda d: d[:7], 'quarter': lambda d: f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}", 'half-year': lambda d: f"{d[:4]}H{(int(d[5:7]) - 1) // 6 + 1}"}
alld = ds.days
def C(p, d): return ds.bars[p][d][-1][3]
def O(p, d): return ds.bars[p][d][0][0]
def rank(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r
def spear(a, b):
    if len(a) < 4: return None
    ra, rb = rank(a), rank(b); ma, mb = st.mean(ra), st.mean(rb)
    va = sum((x - ma) ** 2 for x in ra); vb = sum((x - mb) ** 2 for x in rb)
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / math.sqrt(va * vb) if va and vb else None
def features(p, dd, prev_dd, tr):
    dd = [d for d in dd if d in ds.bars[p]]
    if len(dd) < 15: return None
    i0 = alld.index(dd[0]); before = alld[max(0, i0 - 100):i0]
    pc = C(p, before[-1]) if before and before[-1] in ds.bars[p] else O(p, dd[0])
    ret = C(p, dd[-1]) / pc - 1
    spy = C('SPY', dd[-1]) / (C('SPY', before[-1]) if before else O('SPY', dd[0])) - 1
    rr = [C(p, dd[j]) / C(p, dd[j - 1]) - 1 for j in range(1, len(dd))]
    vol = st.pstdev(rr) * math.sqrt(252) * 100
    rng = st.mean((max(b[1] for b in ds.bars[p][d]) - min(b[2] for b in ds.bars[p][d])) / C(p, d) * 100 for d in dd)
    gaps = [abs(O(p, dd[j]) / C(p, dd[j - 1]) - 1) * 100 for j in range(1, len(dd))]
    ac = []
    for d in dd:
        b = ds.bars[p][d]; x = [b[j][3] / b[j - 1][3] - 1 for j in range(1, len(b))]
        if len(x) > 10 and st.pstdev(x) > 0:
            m = st.mean(x); ac.append(sum((x[j] - m) * (x[j - 1] - m) for j in range(1, len(x))) / sum((v - m) ** 2 for v in x))
    rev = []  # first 30 min vs rest of day: negative = the day reverses its open move (what FADE needs)
    for d in dd:
        b = ds.bars[p][d]; a1 = b[5][3] / b[0][0] - 1; a2 = b[-1][3] / b[5][3] - 1; rev.append(-1 if a1 * a2 < 0 else 1)
    box = st.mean((max(x[1] for x in ds.bars[p][d][:6]) - min(x[2] for x in ds.bars[p][d][:6])) / ds.bars[p][d][0][0] * 100 for d in dd)
    hist = [d for d in alld[max(0, i0 - 100):i0] if d in ds.bars[p]]
    ma = C(p, dd[-1]) / st.mean(C(p, d) for d in hist + dd) - 1 if hist else 0
    v1 = st.mean(sum(x[4] for x in ds.bars[p][d]) for d in dd)
    pv = [d for d in (prev_dd or []) if d in ds.bars[p]]
    v0 = st.mean(sum(x[4] for x in ds.bars[p][d]) for d in pv) if pv else None
    f = dict(ret=ret * 100, rel_spy=(ret - spy) * 100, abs_ret=abs(ret) * 100, vol=vol, chop=-abs(ret) / (st.pstdev(rr) * math.sqrt(len(rr))) if st.pstdev(rr) else 0,
             range=rng, gap=st.mean(gaps), autocorr=st.mean(ac), reversal_days=100 * sum(x < 0 for x in rev) / len(rev), box=box, vs_ma100=ma * 100,
             vol_trend=(v1 / v0 - 1) * 100 if v0 else None, setups=len(tr))
    if len(tr) >= 3:
        r = [t['R_out'] for t in tr]
        f.update(fadeR=st.mean(r), fade_win=100 * sum(x > 0 for x in r) / len(r), never1R=100 * sum(t['best'] < 1 for t in tr) / len(tr))
    else: f.update(fadeR=None, fade_win=None, never1R=None)
    return f
FEATS = ['ret', 'rel_spy', 'abs_ret', 'vol', 'chop', 'range', 'gap', 'autocorr', 'reversal_days', 'box', 'vs_ma100', 'vol_trend', 'setups', 'fadeR', 'fade_win', 'never1R']
DESC = dict(ret='prior return', rel_spy='return minus SPY', abs_ret='|return| (big move either way)', vol='daily volatility', chop='choppiness (low |ret|/vol)',
            range='avg daily high-low %', gap='avg |opening gap|', autocorr='5-min return autocorrelation', reversal_days='% days 10:00 move reversed by close',
            box='avg opening-box size', vs_ma100='price vs 100-day average', vol_trend='volume change vs window before', setups='FADE setups count',
            fadeR='FADE avg R (momentum)', fade_win='FADE win rate', never1R='% trades never closing at +1R')
byP = collections.defaultdict(list)
for t in SET: byP[t['proxy']].append(t)
print("Universe (proxy: bull/bear leverage). Liquid = both legs trade tight; thin = wide spreads / little volume, results there are not tradeable as modelled.")
for p in ALLP: print(f"  {p:<5} {PAIRS[p][0]}/{PAIRS[p][1]} {PAIRS[p][2]}x/{PAIRS[p][3]}x {'liquid' if PAIRS[p][4] else 'thin'}{'' if p in have else '  (NO DATA)'}")
print("\nPer-ETF FADE, 5 years, setups (no Fridays, v5.2.18 exits):")
for p in sorted(have, key=lambda p: -st.mean([t['R_out'] for t in byP[p]] or [0])):
    r = [t['R_out'] for t in byP[p]]; h1 = [t['R_out'] for t in byP[p] if t['day'] < SPLIT]; h2 = [t['R_out'] for t in byP[p] if t['day'] >= SPLIT]
    print(f"  {p:<5} n {len(r):4d} avg {st.mean(r):+.3f}R  H1 {st.mean(h1 or [0]):+.3f}R  H2 {st.mean(h2 or [0]):+.3f}R  never+1R {100*sum(t['best']<1 for t in byP[p])/len(r):3.0f}%  {'liquid' if PAIRS[p][4] else 'thin'}")
results = {}
for wname, wf in WIN.items():
    wins = sorted(set(wf(d) for d in days)); wd = collections.defaultdict(list)
    for d in days: wd[wf(d)].append(d)
    tw = collections.defaultdict(list)
    for t in SET: tw[(t['proxy'], wf(t['day']))].append(t)
    feat = {}
    for i in range(1, len(wins)):
        feat[wins[i]] = {p: f for p in have for f in [features(p, wd[wins[i - 1]], wd[wins[i - 2]] if i >= 2 else None, tw[(p, wins[i - 1])])] if f}
    tgt = {(p, w): st.mean([t['R_out'] for t in tw[(p, w)]]) for p in have for w in wins if len(tw[(p, w)]) >= 3}
    print(f"\n================ WINDOW = {wname.upper()} ({len(wins)} windows; H1 < {SPLIT} <= H2)")
    print("PART 1 - WHERE: does a prior-window feature rank which ETFs FADE best next window? (Spearman IC across ETFs, averaged over windows)")
    print("  IC > 0: high feature -> better FADE next window. |t| > 2 and same sign in both halves would be needed to take it seriously (16 features x 2 pools tested).")
    for pool, pname in ((LIQ, 'liquid 12'), (have, 'all 23')):
        print(f"  pool {pname}:  {'feature':<38} {'meanIC':>7} {'t':>6} {'%pos':>5} {'H1 IC':>7} {'H2 IC':>7}")
        for fn in FEATS:
            ics = []
            for w in wins[1:]:
                xs, ys = [], []
                for p in pool:
                    f = feat[w].get(p)
                    if f and f.get(fn) is not None and (p, w) in tgt: xs.append(f[fn]); ys.append(tgt[(p, w)])
                ic = spear(xs, ys)
                if ic is not None: ics.append((w, ic))
            if len(ics) < 3: continue
            v = [x for _, x in ics]; sd = st.pstdev(v); t_ = st.mean(v) / sd * math.sqrt(len(v)) if sd else 0
            h1 = [x for w, x in ics if wd[w][0] < SPLIT]; h2 = [x for w, x in ics if wd[w][0] >= SPLIT]
            flag = '  <-- consistent' if abs(t_) > 2 and h1 and h2 and st.mean(h1) * st.mean(h2) > 0 else ''
            results[(wname, pname, fn)] = (st.mean(v), t_, st.mean(h1 or [0]), st.mean(h2 or [0]))
            print(f"     {DESC[fn]:<45} {st.mean(v):+7.3f} {t_:+6.2f} {100*sum(x>0 for x in v)/len(v):4.0f}% {st.mean(h1 or [0]):+7.3f} {st.mean(h2 or [0]):+7.3f}{flag}")
    # PART 2 - WHEN
    print("PART 2 - WHEN: does the prior window's market predict next window's overall FADE result? (Spearman across windows)")
    mk = {}
    for i in range(1, len(wins)):
        P = wd[wins[i - 1]]; f = features('SPY', P, wd[wins[i - 2]] if i >= 2 else None, [])
        if f is None: continue
        vx = [d for d in P if d in ds.bars.get('VIXY', {})]
        f['vixy_ret'] = (C('VIXY', vx[-1]) / C('VIXY', vx[0]) - 1) * 100 if len(vx) > 5 else None
        rets = [feat[wins[i]][p]['ret'] for p in have if p in feat[wins[i]]]; f['dispersion'] = st.pstdev(rets) if len(rets) > 3 else None
        pr = [t['R_out'] for t in SET if wf(t['day']) == wins[i - 1] and t['proxy'] in LIVE6]; f['prior_fadeR'] = st.mean(pr) if pr else None
        mk[wins[i]] = f
    MF = [('ret', 'SPY return'), ('abs_ret', 'SPY |return|'), ('vol', 'SPY volatility'), ('chop', 'SPY choppiness'), ('range', 'SPY daily range'), ('gap', 'SPY avg |gap|'),
          ('autocorr', 'SPY 5-min autocorr'), ('reversal_days', 'SPY % reversal days'), ('vs_ma100', 'SPY vs 100-day avg'), ('vixy_ret', 'VIXY change (fear rising)'),
          ('dispersion', 'cross-ETF return dispersion'), ('prior_fadeR', 'prior FADE avg R (live 6)')]
    for tname, pool in (('live 6', LIVE6), ('liquid 12', LIQ)):
        y = {w: st.mean(r) for w in wins[1:] if w in mk for r in [[t['R_out'] for t in SET if wf(t['day']) == w and t['proxy'] in pool]] if len(r) >= 5}
        print(f"  target = next-window FADE avg R, {tname}:  {'feature':<32} {'rho':>6} {'H1':>6} {'H2':>6}  (n windows {len(y)})")
        for fn, dsc in MF:
            ws = [w for w in y if mk[w].get(fn) is not None]
            r = spear([mk[w][fn] for w in ws], [y[w] for w in ws])
            a = [w for w in ws if wd[w][0] < SPLIT]; b = [w for w in ws if wd[w][0] >= SPLIT]
            r1 = spear([mk[w][fn] for w in a], [y[w] for w in a]); r2 = spear([mk[w][fn] for w in b], [y[w] for w in b])
            sig = 2 / math.sqrt(max(1, len(ws) - 1))
            flag = '  <-- consistent' if r is not None and abs(r) > sig and r1 is not None and r2 is not None and r1 * r2 > 0 and abs(r1) > 0.1 and abs(r2) > 0.1 else ''
            fm = lambda v: f"{v:+6.2f}" if v is not None else '   n/a'
            print(f"     {dsc:<45} {fm(r)} {fm(r1)} {fm(r2)}{flag}")
        print(f"     (|rho| above ~{2/math.sqrt(max(1,len(y)-1)):.2f} is needed just to clear noise with {len(y)} windows)")
    # PART 3 - selection backtests
    def pick(w, fn, sign, pool, N):
        f = {p: v[fn] for p, v in feat.get(w, {}).items() if p in pool and v.get(fn) is not None}
        return sorted(f, key=lambda p: -sign * f[p])[:N] if f else pool
    def run(lists, dd):
        S = set(dd); T = [t for t in SET if t['day'] in S and t['proxy'] in lists.get(wf(t['day']), [])]
        a = F.account(ds, dd, T); tk = a['taken']; g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
        return dict(n=len(tk), pf=g / l if l else 99, day=F.stat(a)['avg'], dd=a['mdd'])
    H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
    print("PART 3 - selection backtests (account, one position, 3% risk). Feature+direction picked by H1 result ONLY, then H2 is the honest test.")
    base = {pn: (run({w: L for w in wins}, H1), run({w: L for w in wins}, H2)) for pn, L in (('FIXED live 6', LIVE6), ('FIXED liquid 12', LIQ))}
    for pn, (a, b) in base.items(): print(f"  {pn:<40} H1 PF {a['pf']:4.2f} {a['day']:+.3f}%/d | H2 PF {b['pf']:4.2f} {b['day']:+.3f}%/d DD {b['dd']:4.1f}%")
    for pool, pname in ((LIQ, 'liquid 12'), (have, 'all 23')):
        for N in (3, 6):
            cand = []
            for fn in FEATS:
                for sg in (1, -1):
                    L = {w: pick(w, fn, sg, pool, N) for w in wins}; cand.append((run(L, H1)['day'], fn, sg, L))
            cand.sort(key=lambda x: -x[0])
            for h1d, fn, sg, L in cand[:3]:
                b = run(L, H2); a = run(L, H1)
                print(f"  {pname} top {N} by {'high' if sg > 0 else 'low'} {DESC[fn]:<36} H1 PF {a['pf']:4.2f} {a['day']:+.3f}%/d | H2 PF {b['pf']:4.2f} {b['day']:+.3f}%/d DD {b['dd']:4.1f}%")
# PART 4 - the two market-level signals that held in both halves (monthly): sit out the next month when they say so
wf = WIN['month']; wins = sorted(set(wf(d) for d in days)); wd = collections.defaultdict(list)
for d in days: wd[wf(d)].append(d)
sig = {}
for i in range(1, len(wins)):
    P = wd[wins[i - 1]]; f = features('SPY', P, None, [])
    vx = [d for d in P if d in ds.bars.get('VIXY', {})]
    if f is None or len(vx) < 6: continue
    sig[wins[i]] = dict(vixy=(C('VIXY', vx[-1]) / C('VIXY', vx[0]) - 1) * 100, ac=f['autocorr'])
h1w = [w for w in sig if wd[w][0] < SPLIT]
med = {k: st.median(sig[w][k] for w in h1w) for k in ('vixy', 'ac')}   # thresholds from H1 only
def gate(name, ok):
    print(f"  {name:<52}", end='')
    for pool, pn in ((LIVE6, 'live 6'), (LIQ, 'liquid 12')):
        for tag, dd in (('H1', [d for d in days if d < SPLIT]), ('H2', [d for d in days if d >= SPLIT])):
            S = set(dd); T = [t for t in SET if t['day'] in S and t['proxy'] in pool and ok(wf(t['day']))]
            a = F.account(ds, dd, T); tk = a['taken']; g = sum(t['acct'] for t in tk if t['acct'] > 0); l = -sum(t['acct'] for t in tk if t['acct'] <= 0)
            print(f" | {pn} {tag} n{len(tk):3d} PF {g/l if l else 99:4.2f} {F.stat(a)['avg']:+.3f}%/d DD{a['mdd']:4.1f}", end='')
    print(f"  (months traded {sum(ok(w) for w in sig)}/{len(sig)})")
print(f"\n================ PART 4 - monthly ON/OFF switch from market signals (thresholds = H1 medians: VIXY {med['vixy']:+.1f}%, SPY autocorr {med['ac']:+.3f})")
gate('always on', lambda w: True)
gate('sit out month after VIXY rose (> 0%)', lambda w: w in sig and sig[w]['vixy'] <= 0)
gate('sit out month after VIXY rose more than H1 median', lambda w: w in sig and sig[w]['vixy'] <= med['vixy'])
gate('sit out month after SPY 5-min autocorr > H1 median', lambda w: w in sig and sig[w]['ac'] <= med['ac'])
gate('trade only when both say go', lambda w: w in sig and sig[w]['vixy'] <= med['vixy'] and sig[w]['ac'] <= med['ac'])
print("\nRecent months (live 6, setups avg R) and what the VIXY gate (> H1 median = sit out) would have said:")
for w in sorted(sig)[-12:]:
    r = [t['R_out'] for t in SET if wf(t['day']) == w and t['proxy'] in LIVE6]
    print(f"  {w}: prior-month VIXY {sig[w]['vixy']:+6.1f}% -> {'TRADE' if sig[w]['vixy'] <= med['vixy'] else 'sit out'}   FADE that month n{len(r):3d} avg {st.mean(r or [0]):+.3f}R")
