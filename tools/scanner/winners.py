#!/usr/bin/env python3
"""Which FEAR-DIP trades made +50% or more, and can they be picked in advance?
    python3 tools/scanner/winners.py > tools/scanner/results/winners.txt
Every trait is measured at the signal close (known before entry). Each trait is tested on DEV and TEST separately."""
import math, os, statistics as st, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lab as L

SECTOR = {**{s: 'semis/AI' for s in ('NVDA', 'AMD', 'AVGO', 'MU', 'QCOM', 'INTC', 'SMCI', 'ANET', 'DELL', 'SMH')},
          **{s: 'crypto/fintech' for s in ('COIN', 'MSTR', 'HOOD', 'SOFI', 'PYPL')},
          **{s: 'software' for s in ('MSFT', 'CRM', 'ORCL', 'ADBE', 'PLTR', 'SNOW', 'PANW', 'CRWD', 'SHOP')},
          **{s: 'mega internet' for s in ('AAPL', 'AMZN', 'META', 'GOOGL', 'NFLX', 'UBER', 'ABNB')},
          **{s: 'banks/cards' for s in ('JPM', 'BAC', 'GS', 'WFC', 'C', 'MS', 'V', 'MA', 'XLF', 'KRE')},
          **{s: 'energy' for s in ('XOM', 'CVX', 'OXY', 'SLB', 'COP', 'XLE', 'USO')},
          **{s: 'health' for s in ('UNH', 'LLY', 'JNJ', 'PFE', 'MRK', 'XLV', 'XBI')},
          **{s: 'consumer/industrial' for s in ('WMT', 'COST', 'HD', 'TGT', 'NKE', 'MCD', 'SBUX', 'DIS', 'BA', 'CAT', 'XLY', 'XLP', 'XLI')},
          **{s: 'EV/high beta' for s in ('TSLA', 'RIVN', 'ARKK')},
          **{s: 'index/macro' for s in ('SPY', 'QQQ', 'IWM', 'XLK', 'XLU', 'TLT', 'GLD', 'SLV', 'HYG')}}


def beta(U, s, i, n=60):
    S = U[s]; P = U['SPY']; d = S['d'][i]
    if d not in P['idx'] or i < n + 1: return None
    j = P['idx'][d]
    a = [S['c'][k] / S['c'][k - 1] - 1 for k in range(i - n + 1, i + 1)]
    b = [P['c'][k] / P['c'][k - 1] - 1 for k in range(j - n + 1, j + 1)]
    mb = st.mean(b); va = sum((x - mb) ** 2 for x in b)
    return sum((x - st.mean(a)) * (y - mb) for x, y in zip(a, b)) / va if va else None


def main():
    raw, vix = L.load(); U, reg = L.build(raw, vix); L.prep(U)
    ep = L.episodes(reg); T = []; seen = set()
    for nm in L.CORE:
        for t in L.run(U, reg, vix, nm, L.CORE_OC, flt=L.CORE_FLT):
            if (t['sym'], t['d']) in seen: continue
            seen.add((t['sym'], t['d'])); t['sig'] = nm[:2]; T.append(t)
    for t in T:
        S = U[t['sym']]; i = t['i']
        t['rv'] = max(S['rv20'][i] or 0, S['rv60'][i] or 0)
        t['beta'] = beta(U, t['sym'], i)
        t['drop5'] = (S['c'][i] / S['c'][i - 5] - 1) * 100
        t['atr_below20'] = (S['sma20'][i] - S['c'][i]) / S['atr14'][i] if S['atr14'][i] else 0
        t['vs200'] = (S['c'][i] / S['sma200'][i] - 1) * 100
        t['ret63'] = (S['ret63'][i] or 0) * 100
        t['vix'] = reg[t['d']]['vix']
        dd = sorted(x for x in ep if ep[x] == ep[t['d']]); t['ep_day'] = dd.index(t['d']) + 1 if t['d'] in dd else None
        t['sector'] = SECTOR.get(t['sym'], 'other')
        t['dev'] = t['d'] < L.SPLIT
    n = len(T)
    big = [t for t in T if t['ret'] >= 0.5]; pk = [t for t in T if t['peak'] >= 0.5]
    print(f'FEAR-DIP trades: {n} (42-session 0.75-delta call, exit at the 10th session close)')
    print(f'  ended >= +50%: {len(big)} ({100*len(big)/n:.0f}%)   touched >= +50% at some close during the hold: {len(pk)} ({100*len(pk)/n:.0f}%)')
    print(f'  ended >= +100%: {sum(t["ret"] >= 1 for t in T)}   ended positive: {sum(t["ret"] > 0 for t in T)} ({100*sum(t["ret"] > 0 for t in T)/n:.0f}%)   lost >= 50%: {sum(t["ret"] <= -0.5 for t in T)}')
    pd = [t['peak_day'] for t in pk]; print(f'  session the peak came on, for the {len(pk)} that touched +50%: median {st.median(pd)}, ' + ', '.join(f'{d}:{pd.count(d)}' for d in range(1, 11)))
    print('\nA. +50% winners by name (repeat winners?)')
    by = defaultdict(list)
    for t in T: by[t['sym']].append(t)
    rows = sorted(by.items(), key=lambda kv: -sum(t['ret'] >= .5 for t in kv[1]))
    for s, x in rows[:20]:
        b = sum(t['ret'] >= .5 for t in x)
        if not b: break
        print(f"  {s:5s} {L.SECTOR if False else SECTOR.get(s, 'other'):18s} trades {len(x):2d}  >=+50%: {b:2d} ({100*b/len(x):3.0f}%)  mean {100*st.mean(t['ret'] for t in x):+5.0f}%  "
              f"DEV {sum(t['ret']>=.5 for t in x if t['dev'])}/{sum(t['dev'] for t in x)}  TEST {sum(t['ret']>=.5 for t in x if not t['dev'])}/{sum(not t['dev'] for t in x)}")
    print('\nB. By sector: share of trades ending >= +50%, mean return, DEV | TEST')
    sec = defaultdict(list)
    for t in T: sec[t['sector']].append(t)
    for k, x in sorted(sec.items(), key=lambda kv: -st.mean(t['ret'] >= .5 for t in kv[1])):
        dv = [t for t in x if t['dev']]; ts = [t for t in x if not t['dev']]
        f = lambda y: f"{100*st.mean(t['ret']>=.5 for t in y):3.0f}% / {100*st.mean(t['ret'] for t in y):+5.1f}% (n{len(y)})" if y else 'n0'
        print(f"  {k:20s} ALL {f(x)}   DEV {f(dv)}   TEST {f(ts)}")
    print('\nC. Traits measured at the signal: thirds (low / mid / high). Columns: share ending >= +50% | mean return | n. DEV then TEST.')
    for key, lab in [('rv', 'stock volatility (realised)'), ('beta', 'beta to SPY (60d)'), ('drop5', '5-day % change (more negative = deeper dip)'),
                     ('atr_below20', 'ATRs below the 20-day average'), ('vs200', '% above the 200-day'), ('ret63', '3-month return %'),
                     ('vix', 'VIX at signal'), ('ep_day', 'session number inside the fear episode')]:
        xs = sorted(t[key] for t in T if t[key] is not None); c1, c2 = xs[len(xs) // 3], xs[2 * len(xs) // 3]
        print(f"  {lab} (cuts {c1:.2f} / {c2:.2f})")
        for part, flag in (('DEV ', True), ('TEST', False)):
            out = []
            for lo, hi, nm in ((-1e9, c1, 'low'), (c1, c2, 'mid'), (c2, 1e9, 'high')):
                y = [t for t in T if t[key] is not None and lo <= t[key] < hi and t['dev'] == flag]
                out.append(f"{nm} {100*st.mean(t['ret']>=.5 for t in y):3.0f}% {100*st.mean(t['ret'] for t in y):+5.1f}% n{len(y):3d}" if y else f'{nm} n0')
            print(f"    {part} " + ' | '.join(out))
    print('\nD. By signal:')
    for sg in ('C1', 'C7', 'C8'):
        x = [t for t in T if t['sig'] == sg]
        print(f"  {sg}: n {len(x)}, ended >= +50% {100*st.mean(t['ret']>=.5 for t in x):.0f}%, mean {100*st.mean(t['ret'] for t in x):+.1f}%, win {100*st.mean(t['ret']>0 for t in x):.0f}%")
    print('\nE. Rule candidates built from the traits (fixed cut: top third of volatility, i.e. rv >= DEV cut). Does it repeat in TEST?')
    dv = sorted(t['rv'] for t in T if t['dev']); cut = dv[2 * len(dv) // 3]
    for nm, f in [('all FEAR-DIP', lambda t: True), (f'high vol only (rv >= {cut:.2f})', lambda t: t['rv'] >= cut),
                  ('high vol + 5d drop <= -8%', lambda t: t['rv'] >= cut and t['drop5'] <= -8), ('first 3 sessions of an episode', lambda t: t['ep_day'] and t['ep_day'] <= 3),
                  ('high vol + first 3 sessions', lambda t: t['rv'] >= cut and t['ep_day'] and t['ep_day'] <= 3)]:
        for part, flag in (('DEV ', True), ('TEST', False)):
            y = [t for t in T if f(t) and t['dev'] == flag]
            if len(y) < 5: print(f'  {nm:34s} {part} n{len(y)}'); continue
            m = st.mean(t['ret'] for t in y); sd = st.pstdev([t['ret'] for t in y])
            print(f"  {nm:34s} {part} n {len(y):3d}  >=+50% {100*st.mean(t['ret']>=.5 for t in y):3.0f}%  win {100*st.mean(t['ret']>0 for t in y):3.0f}%  mean {100*m:+5.1f}%  "
                  f"worst {100*min(t['ret'] for t in y):+4.0f}%  t {m/(sd/math.sqrt(len(y))):+.1f}")
    print('\nF. Exit rule test: take profit at +50% at a close (otherwise exit at session 10), all FEAR-DIP trades:')
    for part, flag in (('DEV ', True), ('TEST', False), ('ALL ', None)):
        y = [t for t in T if flag is None or t['dev'] == flag]
        tp = [0.5 if t['peak'] >= 0.5 else t['ret'] for t in y]
        print(f"  {part} hold to day 10: mean {100*st.mean(t['ret'] for t in y):+.1f}%   take +50%: mean {100*st.mean(tp):+.1f}%   (n {len(y)})")


if __name__ == '__main__':
    main()
