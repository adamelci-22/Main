#!/usr/bin/env python3
"""Best mix of 4 to 10 FADE proxies out of ten tradable ones (QQQ SOXX IWM XLK XBI XLF SPY TLT GLD VIXY; KRE is excluded: it has no inverse leg), all 848 combinations, Massive bars, signal-model legs (0.06% cost).
    /usr/bin/python3 -I tools/backtest/massive_bestk.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_bestk.txt
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
ROWS.update({'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'GLD': ('UGL', 2, 'GLL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)})
A_END, B0, B1, MID = '2026-02-27', '2026-03-03', '2026-10-14', '2026-06-30'


def acct(D, ds, cs):
    S = set(ds); a = MXD.account(D, ds, [c for c in cs if c['day'] in S]); t = a['taken']
    dl = list(a['daily'].values())
    return dict(pd=st.mean(dl), ret=a['ret'], dd=a['mdd'], n=len(t), win=100 * sum(x['usd'] > 0 for x in t) / len(t) if t else 0)


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    DA = [d for d in days if d <= A_END]; DB = [d for d in days if B0 <= d <= B1]; DB1 = [d for d in DB if d <= MID]; DB2 = [d for d in DB if d > MID]
    cand = {p: MXD.norm_px(EX.fade_trades(D, days, p, ROWS[p]), 'FADE') for p in ROWS}
    P = list(ROWS); combos = [c for k in range(4, 11) for c in itertools.combinations(P, k)]; out = []
    for c in combos:
        cs = [x for p in c for x in cand[p]]
        out.append((c, acct(D, DB, cs), acct(D, DA, cs), acct(D, DB1, cs), acct(D, DB2, cs)))
    f = lambda r: f"{r['pd']:+.3f}%/d ret {r['ret']:+6.0f}% DD {r['dd']:>4.1f}% n={r['n']:>3} win {r['win']:>3.0f}%"
    print(f"{len(combos)} combinations of 4 to 10 from {len(P)} tradable proxies ({' '.join(P)}). FADE only, signal-model legs.\n")
    print("== Best combination for each size, ranked on B ==")
    print(f"{'size':<5}{'proxies':<48}{'B 2026-03..10':<56}{'A 2021-11..2026-02':<30}")
    for k in range(4, 11):
        r = max((r for r in out if len(r[0]) == k), key=lambda r: r[1]['pd']); print(f"{k:<5}{' '.join(r[0]):<48}{f(r[1]):<56}{r[2]['pd']:+.3f}%/d DD {r[2]['dd']:.0f}%")
    srt = sorted(out, key=lambda r: -r[1]['pd'])
    print("\n== Top 10 overall on B ==")
    for i, (c, b, a, b1, b2) in enumerate(srt[:10], 1): print(f"{i:<3}{' '.join(c):<48}{f(b):<56}A {a['pd']:+.3f}%/d  halves {b1['pd']:+.3f} / {b2['pd']:+.3f}")
    print("\n== Top 5 by the weaker of the two halves of B (rewards a combination that works in both) ==")
    for i, (c, b, a, b1, b2) in enumerate(sorted(out, key=lambda r: -min(r[3]['pd'], r[4]['pd']))[:5], 1): print(f"{i:<3}{' '.join(c):<48}{f(b):<56}A {a['pd']:+.3f}%/d  halves {b1['pd']:+.3f} / {b2['pd']:+.3f}")
    cs6 = [x for p in LIVE for x in cand[p]]; b6, a6 = acct(D, DB, cs6), acct(D, DA, cs6)
    rk6 = 1 + sum(r[1]['pd'] > b6['pd'] for r in out)
    cs10 = [x for p in P for x in cand[p]]
    print(f"\nLive six:  B {f(b6)}  A {a6['pd']:+.3f}%/d DD {a6['dd']:.0f}%   rank {rk6} of {len(out)}")
    b10, a10 = acct(D, DB, cs10), acct(D, DA, cs10)
    print(f"All ten:   B {f(b10)}  A {a10['pd']:+.3f}%/d DD {a10['dd']:.0f}%")
    print(f"\nA: best of the {len(out)} combinations {max(r[2]['pd'] for r in out):+.3f}%/d, median {st.median(r[2]['pd'] for r in out):+.3f}%/d, share above zero {100*sum(r[2]['pd'] > 0 for r in out)/len(out):.0f}%.  B: best {srt[0][1]['pd']:+.3f}%/d, median {st.median(r[1]['pd'] for r in out):+.3f}%/d, worst {srt[-1][1]['pd']:+.3f}%/d.")
    ch = max(out, key=lambda r: r[3]['pd'])
    print(f"Choose on 2026-03..06: {' '.join(ch[0])} ({ch[3]['pd']:+.3f}%/d). On 2026-07..10: {ch[4]['pd']:+.3f}%/d. Median combination {st.median(r[4]['pd'] for r in out):+.3f}%/d. Live six {acct(D, DB2, cs6)['pd']:+.3f}%/d.")
    rng = np.random.default_rng(3); allB = [(p, x) for p in P for x in cand[p] if B0 <= x['day'] <= B1]; best = []
    pcts = np.array([x['pct'] for _, x in allB])
    for _ in range(30):
        sp = rng.permutation(pcts); cc = {p: [] for p in P}
        for (p, x), v in zip(allB, sp): cc[p].append(dict(x, pct=float(v)))
        best.append(max(acct(D, DB, [x for p in c for x in cc[p]])['pd'] for c in combos[::8]))
    print(f"Null (results shuffled across proxies inside B, best of {len(combos[::8])} sampled combinations, 30 shuffles): best median {np.median(best):+.3f}%/d, 90th percentile {np.quantile(best, .9):+.3f}%/d.  Real best {srt[0][1]['pd']:+.3f}%/d.")
    c = srt[0][0]; cs = [x for p in c for x in cand[p]]; cp = FS.cands(D, days)[1]
    print(f"\n== Top combination {' '.join(c)} with the live PULLBACK ==")
    for lab, ds in (('B 2026-03..10', DB), ('A 2021-11..2026-02', DA)):
        print(f"   {lab:<20}FADE only {f(acct(D, ds, cs))}\n   {'':<20}FADE + PULLBACK {f(acct(D, ds, cs + cp))}")


if __name__ == '__main__':
    main()
