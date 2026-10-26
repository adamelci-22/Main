#!/usr/bin/env python3
"""Best mix of five FADE proxies out of eleven (QQQ SOXX IWM XLK XBI XLF SPY TLT KRE GLD VIXY), all 462 combinations, Massive bars, signal-model legs (0.06% cost).
    /usr/bin/python3 -I tools/backtest/massive_best5.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_best5.txt
Account: $2,000, 3% risk capped at cash, one position at a time, 3 entries a day, earliest trigger first, ties by RVOL (mixed.account; final_system.py's account). FADE only, then with the live PULLBACK.
B = 2026-03-03..10-14 (the window the list came from). A = 2021-11-02..2026-02-27. Half-window check: choose on 2026-03..06, judge on 2026-07..10.
Null: the same ranking on shuffled trade results shows how good the best of 462 looks by chance alone.
"""
import itertools, os, statistics as st, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
import gzip, json
_raw = json.load(gzip.open(sys.argv[1], 'rt')); _daily = json.load(gzip.open(sys.argv[2], 'rt'))
BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY', 'TLT']
import manual as m, pb_final as PBF, mixed as MXD, expand_lists as EX, fade_addone as FA
import final_system as FS
from lab import get_data
LIVE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
ROWS = {p: FA.ROWS[p] for p in LIVE}
ROWS.update({'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'KRE': ('DPST', 3, 'KRED', 3), 'GLD': ('UGL', 2, 'GLL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)})
A_END, B0, B1, MID = '2026-02-27', '2026-03-03', '2026-10-14', '2026-06-30'


def acct(D, ds, cs):
    S = set(ds); a = MXD.account(D, ds, [c for c in cs if c['day'] in S]); t = a['taken']
    dl = list(a['daily'].values())
    return dict(pd=st.mean(dl), ret=a['ret'], dd=a['mdd'], n=len(t), win=100 * sum(x['usd'] > 0 for x in t) / len(t) if t else 0)


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    DA = [d for d in days if d <= A_END]; DB = [d for d in days if B0 <= d <= B1]; DB1 = [d for d in DB if d <= MID]; DB2 = [d for d in DB if d > MID]
    cand = {p: MXD.norm_px(EX.fade_trades(D, days, p, ROWS[p]), 'FADE') for p in ROWS}
    P = list(ROWS); combos = list(itertools.combinations(P, 5)); out = []
    for c in combos:
        cs = [x for p in c for x in cand[p]]
        out.append((c, acct(D, DB, cs), acct(D, DA, cs), acct(D, DB1, cs), acct(D, DB2, cs)))
    out.sort(key=lambda r: -r[1]['pd'])
    f = lambda r: f"{r['pd']:+.3f}%/d ret {r['ret']:+6.0f}% DD {r['dd']:>4.1f}% n={r['n']:>3} win {r['win']:>3.0f}%"
    print(f"{len(combos)} combinations of 5 from {len(P)} proxies. FADE only, signal-model legs.\n")
    print(f"{'rank':<5}{'proxies':<28}{'B 2026-03..10 (selection window)':<56}{'A 2021-11..2026-02':<56}")
    for i, (c, b, a, b1, b2) in enumerate(out[:10], 1): print(f"{i:<5}{' '.join(c):<28}{f(b):<56}{f(a):<56}")
    print("\nFive of the live six (drop one) and the live six:")
    for c, b, a, b1, b2 in out:
        if set(c) <= set(LIVE): print(f"     {' '.join(c):<28}{f(b):<56}{f(a):<56}  rank {out.index((c, b, a, b1, b2)) + 1}")
    cs6 = [x for p in LIVE for x in cand[p]]; b6, a6 = acct(D, DB, cs6), acct(D, DA, cs6)
    print(f"     {'live six':<28}{f(b6):<56}{f(a6):<56}")
    print("\nHow often each proxy appears in the top 20 combinations: " + ', '.join(f"{p} {sum(p in r[0] for r in out[:20])}" for p in sorted(P, key=lambda p: -sum(p in r[0] for r in out[:20]))))
    print(f"\nA, the 462 combinations: best {max(r[2]['pd'] for r in out):+.3f}%/d, median {st.median(r[2]['pd'] for r in out):+.3f}%/d, share above zero {100*sum(r[2]['pd'] > 0 for r in out)/len(out):.0f}%. The chosen best-of-B combination in A: {out[0][2]['pd']:+.3f}%/d.")
    print(f"B, the 462 combinations: best {out[0][1]['pd']:+.3f}%/d, median {st.median(r[1]['pd'] for r in out):+.3f}%/d, worst {out[-1][1]['pd']:+.3f}%/d.")
    ch = max(out, key=lambda r: r[3]['pd'])
    print(f"\nHalf-window check: best on 2026-03..06 is {' '.join(ch[0])} ({ch[3]['pd']:+.3f}%/d). On 2026-07..10 it earns {ch[4]['pd']:+.3f}%/d; the median combination earns {st.median(r[4]['pd'] for r in out):+.3f}%/d; the live six earn {acct(D, DB2, cs6)['pd']:+.3f}%/d.")
    rk1 = {r[0]: i for i, r in enumerate(sorted(out, key=lambda r: -r[3]['pd']))}; rk2 = {r[0]: i for i, r in enumerate(sorted(out, key=lambda r: -r[4]['pd']))}
    ks = list(rk1); print(f"Rank correlation of the 462 combinations, 03-06 against 07-10: {np.corrcoef([rk1[k] for k in ks], [rk2[k] for k in ks])[0, 1]:+.2f}; against A: {np.corrcoef([rk1[k] for k in ks], [sorted(out, key=lambda r: -r[2]['pd']).index(next(r for r in out if r[0] == k)) for k in ks])[0, 1]:+.2f}")
    # null: shuffle trade results among the pooled trades, same ranking on B
    rng = np.random.default_rng(3); allB = [(p, x) for p in P for x in cand[p] if B0 <= x['day'] <= B1]; best = []
    pcts = np.array([x['pct'] for _, x in allB])
    for _ in range(40):
        sp = rng.permutation(pcts); cc = {p: [] for p in P}
        for (p, x), v in zip(allB, sp): cc[p].append(dict(x, pct=float(v)))
        top = -9
        for c in combos[::6]:
            top = max(top, acct(D, DB, [x for p in c for x in cc[p]])['pd'])
        best.append(top)
    print(f"Null (trade results shuffled across proxies inside B, best of 77 sampled combinations, 40 shuffles): best-combination median {np.median(best):+.3f}%/d, 90th percentile {np.quantile(best, .9):+.3f}%/d. The real best is {out[0][1]['pd']:+.3f}%/d.")
    c = out[0][0]; cs = [x for p in c for x in cand[p]]
    cp = [x for x in FS.cands(D, days)[1]]
    print(f"\n== Top combination {' '.join(c)} with the live PULLBACK ==")
    for lab, ds in (('B 2026-03..10', DB), ('A 2021-11..2026-02', DA), ('all', days)):
        print(f"   {lab:<20}FADE only {f(acct(D, ds, cs))}\n   {'':<20}FADE + PULLBACK {f(acct(D, ds, cs + cp))}")
    cl = [x for p in LIVE for x in cand[p]]
    print("   live six for comparison:")
    for lab, ds in (('B 2026-03..10', DB), ('A 2021-11..2026-02', DA)): print(f"   {lab:<20}FADE + PULLBACK {f(acct(D, ds, cl + cp))}")


if __name__ == '__main__':
    main()
