#!/usr/bin/env python3
"""2-bar ORB: which rule should pick between proxies that trigger together?
    python3 tools/backtest/twobar_pick.py > tools/backtest/results_twobar_pick.txt
Live-realistic 2-bar (checkpoint entry, Bar-2 stop, half at 1:1 + breakeven, hold to 15:55). For each day, the candidate set is
either (a) the proxies that trigger in the EARLIEST 5-min bar (current), or (b) every proxy that triggers in 10:00-10:15
(wait until the window closes, then pick). Score = average leg % of the picked trade; judged on H1 and H2 separately.
"""
import math, os, random, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twobar as TB
from lab import get_data


def feats(D, t):
    d = t['day']; p = t['proxy']; s = t['side']; b = D.bars[p][d]; k = t['k']
    i = D.days.index(d); pd_ = D.days[i - 1]; pb = D.bars[p][pd_]
    H, L = TB.box(b); o = b[0][0]
    pri = D.prior(d, 14)
    atr = st.mean(D.dhlc[p][x][0] - D.dhlc[p][x][1] for x in pri) if all(x in D.dhlc[p] for x in pri) else (H - L)
    sb = D.bars['SPY'][d]; spy = (sb[k - 1][3] / sb[0][0] - 1) * 100
    move = s * (b[k - 1][3] / o - 1) * 100
    edge = H if s > 0 else L
    c5 = D.bars[p][D.days[i - 5]][77][3]
    tv = b[k - 1][4]; av = st.mean(x[4] for x in b[max(0, k - 7):k - 1]) or 1
    return dict(
        rvol=TB.rvol(D, p, d, k),
        rs_spy=move - s * spy,
        gap=s * (o / pb[77][3] - 1) * 100,
        box_pct=(H - L) / o * 100,
        box_atr=(H - L) / atr if atr else 1,
        brk=s * (b[k - 1][3] - edge) / edge * 100,
        trig_vol=tv / av,
        prev_day=s * (pb[77][3] / pb[0][0] - 1) * 100,
        trend5=s * (pb[77][3] / c5 - 1) * 100,
        move=move,
        spy_agree=1.0 if s * spy > 0 else 0.0,
        lev=TB.ROWS[p][2],
        atr_pct=atr / o * 100,
    )


RULES = [  # (label, key, 'max'|'min')
    ('highest RVOL (current)', 'rvol', 'max'), ('lowest RVOL', 'rvol', 'min'),
    ('narrowest 2-bar box (% of price)', 'box_pct', 'min'), ('widest 2-bar box', 'box_pct', 'max'),
    ('most compressed box (box / daily ATR)', 'box_atr', 'min'), ('least compressed box', 'box_atr', 'max'),
    ('biggest gap in trade direction', 'gap', 'max'), ('biggest gap against trade (gap reversal)', 'gap', 'min'),
    ('weakest break (closest to the edge)', 'brk', 'min'), ('strongest break past the edge', 'brk', 'max'),
    ('highest trigger-bar volume vs prior 6', 'trig_vol', 'max'), ('lowest trigger-bar volume', 'trig_vol', 'min'),
    ('prior day moved WITH the trade most', 'prev_day', 'max'), ('prior day moved AGAINST the trade most', 'prev_day', 'min'),
    ('5-day trend WITH the trade', 'trend5', 'max'), ('5-day trend AGAINST the trade', 'trend5', 'min'),
    ('furthest moved since open (momentum)', 'move', 'max'), ('least moved since open', 'move', 'min'),
    ('strongest vs SPY (relative strength)', 'rs_spy', 'max'), ('weakest vs SPY', 'rs_spy', 'min'),
    ('SPY agrees with the direction', 'spy_agree', 'max'),
    ('most volatile proxy (daily ATR %)', 'atr_pct', 'max'), ('least volatile proxy', 'atr_pct', 'min'),
]


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1 = set(days[:h])
    cfg = TB.Cfg(entry='checkpoint', delayed_tp=True)
    T = [t for d in days for p in TB.ROWS for t in [TB.trade(D, d, p, cfg)] if t]
    for t in T: t['f'] = feats(D, t)
    by = collections.defaultdict(list)
    for t in T: by[t['day']].append(t)
    print(f"2-bar ORB, live-realistic, {days[0]}..{days[-1]}: {len(T)} triggers on {len(by)} days. Score = avg leg % of the trade picked each day (one trade/day).")
    print("A rule is only interesting if it beats random in BOTH halves.\n")
    for mode in ('earliest', 'window'):
        sets = {}
        for d, ts in by.items():
            if mode == 'earliest':
                k0 = min(t['k'] for t in ts); sets[d] = [t for t in ts if t['k'] == k0]
            else: sets[d] = ts
        multi = sum(1 for v in sets.values() if len(v) > 1)
        def score(pick):
            a = [pick(v) for v in sets.values()]
            f = lambda S: st.mean(x['pct'] for x in S) if S else 0
            return f(a), f([x for x in a if x['day'] in H1]), f([x for x in a if x['day'] not in H1])
        rnd = [score(lambda v, r=random.Random(s): r.choice(v)) for s in range(200)]
        r0 = tuple(st.mean(x[i] for x in rnd) for i in range(3))
        print(f"== Candidates: {'proxies triggering in the EARLIEST bar (current)' if mode == 'earliest' else 'ALL proxies triggering 10:00-10:15 (wait, then pick)'}; days with a real choice: {multi}")
        print(f"   {'rule':<44}{'all':>8}{'H1':>8}{'H2':>8}   vs random ({r0[0]:+.3f} / {r0[1]:+.3f} / {r0[2]:+.3f})")
        rows = []
        for lab, key, how in RULES:
            fn = (lambda v, key=key: max(v, key=lambda t: t['f'][key])) if how == 'max' else (lambda v, key=key: min(v, key=lambda t: t['f'][key]))
            a, b1, b2 = score(fn); rows.append((lab, a, b1, b2))
        for lab, a, b1, b2 in sorted(rows, key=lambda r: -r[1]):
            tag = 'BEATS RANDOM IN BOTH HALVES' if b1 > r0[1] and b2 > r0[2] else ''
            print(f"   {lab:<44}{a:>+8.3f}{b1:>+8.3f}{b2:>+8.3f}   {tag}")
        best = max(rows, key=lambda r: r[2])
        print(f"   walk-forward: best rule on H1 = '{best[0]}' ({best[2]:+.3f}) -> H2 {best[3]:+.3f} (random H2 {r0[2]:+.3f})")
        pos = [r for r in rows if r[1] > 0]
        print(f"   rules with a positive average overall: {len(pos)} of {len(rows)}\n")


if __name__ == '__main__':
    main()
