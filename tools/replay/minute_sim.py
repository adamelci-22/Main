#!/usr/bin/env python3
"""Minute-resolution replay of C1 entries + B2 management, to test check cadence and
1-minute vs 5-minute breakout confirmation. Everything runs on 1-minute bars (9/1-10/6);
5-minute bars for confirmation are aggregated from them. Prior-day RVOL profiles and ATR
come from the 5-minute history (from 8/18).

Model (same as the earlier 5-minute replay where possible):
- 12 proxies; leveraged leg = L x proxy move (bull) or -L x (inverse).
- RVOL >= 1.0 vs 20-day same-time cumulative average (top-3 floor), measured at the last
  completed 5-minute boundary.
- Breakout: two consecutive closes outside the opening range (5-min or 1-min closes).
- Volume test on the triggering bar (first close of the current run outside the range) vs
  the 3 bars before it, at checks before 11:00 only (v3.117).
- Score (1 - expansion) x RVOL; expansion = day range so far / ATR14.
- Entry at the open of the minute after the check plus LAT minutes of latency.
- Stop = proxy's opening-range far side (the leg's OR low/high), filled at the stop when any
  1-minute bar touches it. Ratchet at management checks: candidate = best price since entry
  x (1 - 2 x 0.10% / L), only when last close is beyond entry and beyond the candidate and the
  move clears 0.07%.
- 12:30 close; 3% risk sizing; no stop ceiling; 0.10% round-trip cost (leveraged terms);
  2 fresh + 1 re-entry; losing leg excluded for the day.
"""
import json, random, statistics as st
from collections import defaultdict

import os
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
import gzip
M1 = json.load(gzip.open(f"{SP}/proxies_1m.json.gz"))          # sym -> day -> [ (o,h,l,c,v,interp) x 390 ]
F5 = json.load(gzip.open(f"{SP}/proxies_5m_v2.json.gz"))       # sym -> [[t,o,h,l,c,v,interp],...]
LEV = {'QQQ': 3, 'SPY': 3, 'SOXX': 3, 'IWM': 3, 'XLF': 3, 'XLE': 2, 'TLT': 3, 'XBI': 3,
       'XOP': 2, 'XLRE': 3, 'EEM': 3, 'XLU': 3}
SYMS = sorted(LEV)
COST, STALL = 0.10, 0.10

D5 = defaultdict(dict)
for s, bars in F5.items():
    by = defaultdict(list)
    for t, o, h, l, c, v, _ in bars:
        by[t[:10]].append((o, h, l, c, v))
    for d, bl in by.items():
        D5[d][s] = bl
ALL5 = sorted(D5)
DAYS = sorted(set.intersection(*[set(M1[s]) for s in SYMS]))


def prior(d, n):
    i = ALL5.index(d) if d in ALL5 else len([x for x in ALL5 if x < d])
    return [x for x in ALL5[max(0, i - n):i] if all(s in D5[x] and len(D5[x][s]) >= 78 for s in SYMS)]


PRE = {}
for d in DAYS:
    ps = prior(d, 20)
    for s in SYMS:
        prof = [0.0] * 78
        for pd in ps:
            cum = 0
            for k, b in enumerate(D5[pd][s][:78]):
                cum += b[4]; prof[k] += cum
        prof = [x / len(ps) for x in prof]
        p15 = prior(d, 15)
        trs = []
        for a, b in zip(p15, p15[1:]):
            hi = max(x[1] for x in D5[b][s]); lo = min(x[2] for x in D5[b][s]); pc = D5[a][s][-1][3]
            trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
        PRE[(d, s)] = (prof, sum(trs[-14:]) / len(trs[-14:]))


def agg5(m):
    """1-minute bars -> 5-minute bars (o,h,l,c,v)."""
    out = []
    for i in range(0, len(m), 5):
        ch = m[i:i + 5]
        out.append((ch[0][0], max(x[1] for x in ch), min(x[2] for x in ch), ch[-1][3], sum(x[4] for x in ch)))
    return out


B5 = {(d, s): agg5(M1[s][d]) for d in DAYS for s in SYMS}


def candidates(d, t, cfg):
    """check at minute t (bars < t completed). Returns candidate dicts."""
    orm = cfg['or']                      # opening range minutes (30 or 15)
    k5 = t // 5                          # completed 5-min bars
    rv = {}
    for s in SYMS:
        cum = sum(b[4] for b in B5[(d, s)][:k5])
        rv[s] = cum / PRE[(d, s)][0][k5 - 1]
    passing = [s for s in SYMS if rv[s] >= 1.0] or []
    if len(passing) < 3:
        passing = sorted(SYMS, key=lambda s: -rv[s])[:3]
    out = []
    for s in passing:
        m = M1[s][d]
        orh = max(b[1] for b in m[:orm]); orl = min(b[2] for b in m[:orm])
        conf = cfg['conf'] if t < cfg.get('fast_until', 0) else '5m'
        if conf == '5m':
            bars = B5[(d, s)][:k5]; nb = orm // 5
        else:
            bars = m[:t]; nb = orm
        if len(bars) - 2 < nb:
            continue
        c1, c2 = bars[-2][3], bars[-1][3]
        if c1 > orh and c2 > orh: side = 1
        elif c1 < orl and c2 < orl: side = -1
        else: continue
        j = len(bars) - 1
        while j - 1 >= nb and ((bars[j - 1][3] > orh) if side == 1 else (bars[j - 1][3] < orl)):
            j -= 1
        if cfg['vol'] and t < 150 and j >= 3:      # volume test before 11:00 (minute 90 = 11:00)
            pass
        if cfg['vol'] and t < 90 and j >= 3:
            if not bars[j][4] > sum(b[4] for b in bars[j - 3:j]) / 3:
                continue
        hi = max(b[1] for b in m[:t]); lo = min(b[2] for b in m[:t])
        exp = (hi - lo) / PRE[(d, s)][1]
        out.append(dict(sym=s, side=side, rvol=rv[s], score=(1 - exp) * rv[s], orh=orh, orl=orl))
    return out


CLOSE = 180   # minute index 180 = 12:30; exit at close of minute 179


def manage_times(cfg, t0):
    ts = set(range(30, CLOSE, 5)) | set(cfg.get('extra_mgmt', ()))
    return sorted(x for x in ts if x > t0)


def trade(d, c, t_entry, cfg):
    s, side, L = c['sym'], c['side'], LEV[c['sym']]
    m = M1[s][d]
    if t_entry >= CLOSE: return None
    e = m[t_entry][0]
    stop = c['orl'] if side == 1 else c['orh']
    dist = abs(e - stop) / e * 100 * L
    if (e - stop) * side <= 0: return None
    disc = 2 * STALL / L / 100
    mg = set(manage_times(cfg, t_entry))
    ext = e
    for i in range(t_entry, CLOSE):
        o, h, l, cl, v, _ = m[i]
        if (side == 1 and l <= stop) or (side == -1 and h >= stop):
            px = min(o, stop) if side == 1 else max(o, stop)
            return dict(ret=side * (px / e - 1) * 100 * L - COST, dist=dist, exit=i + 1)
        ext = max(ext, h) if side == 1 else min(ext, l)
        if (i + 1) in mg and (cl - e) * side > 0:            # management check at end of minute i
            cand = ext * (1 - disc) if side == 1 else ext * (1 + disc)
            if (side == 1 and cl > cand and cand > stop * 1.0007) or (side == -1 and cl < cand and cand < stop * 0.9993):
                stop = cand
    px = m[CLOSE - 1][3]
    return dict(ret=side * (px / e - 1) * 100 * L - COST, dist=dist, exit=CLOSE)


def run(cfg, LAT=1):
    daily, trades = [], []
    for d in DAYS:
        checks = sorted(set(range(30, 146, 5)) | set(cfg.get('extra_checks', ())))
        checks = [x for x in checks if x >= cfg['or'] + (10 if cfg['conf'] == '5m' and cfg['or'] == 15 else 0)]
        busy = 0; legs = defaultdict(int); distinct = set(); reent = 0; lost = set(); day = 0.0
        for t in checks:
            if t < busy: continue
            cands = []
            for c in candidates(d, t, cfg):
                leg = (c['sym'], c['side'])
                if leg in lost or legs[leg] >= 2: continue
                if leg in distinct:
                    if reent >= 1: continue
                elif len(distinct) >= 2: continue
                cands.append(c)
            if not cands: continue
            c = max(cands, key=lambda x: x['score'])
            tr = trade(d, c, t + LAT, cfg)
            if tr is None: continue
            leg = (c['sym'], c['side'])
            if leg in distinct: reent += 1
            distinct.add(leg); legs[leg] += 1
            if tr['ret'] < 0: lost.add(leg)
            day += tr['ret'] * min(1.0, 3.0 / tr['dist'])
            trades.append((d, t, c['sym'], c['side'], tr['ret']))
            busy = tr['exit'] + 1
        daily.append(day)
    return daily, trades


def summ(lab, daily, trades):
    w = sum(1 for *_, r in trades if r > 0)
    print(f"{lab:62} trades={len(trades):3} win={w/len(trades):.0%} avg/day={st.mean(daily):+.3f}% "
          f"worst={min(daily):+.2f} green={sum(x>0 for x in daily)}/{len(daily)} total={sum(daily):+.2f}")


if __name__ == "__main__":
    print(f"Days {DAYS[0]}..{DAYS[-1]} ({len(DAYS)}), 12 proxies, entry latency 1 min\n")
    ONE_TO_1030 = range(30, 60)          # 10:00-10:29 every minute (30-min range)
    ONE_945_1030 = range(15, 60)         # 9:45-10:29 every minute (15-min range)
    THREE_TO_1030 = range(30, 60, 3)
    cfgs = [
        ("A  CURRENT: 30-min range, 5-min closes, checks every 5 min", dict(**{'or': 30, 'conf': '5m', 'vol': True})),
        ("B  30-min range, 5-min closes, checks every 1 min to 10:30", dict(**{'or': 30, 'conf': '5m', 'vol': True, 'extra_checks': ONE_TO_1030, 'extra_mgmt': ONE_TO_1030})),
        ("C  30-min range, 1-min closes + 1-min checks to 10:30", dict(**{'or': 30, 'conf': '1m', 'fast_until': 60, 'vol': True, 'extra_checks': ONE_TO_1030, 'extra_mgmt': ONE_TO_1030})),
        ("C' same, no volume test on 1-min bars", dict(**{'or': 30, 'conf': '1m', 'fast_until': 60, 'vol': False, 'extra_checks': ONE_TO_1030, 'extra_mgmt': ONE_TO_1030})),
        ("D  30-min range, 1-min closes, checks every 3 min to 10:30", dict(**{'or': 30, 'conf': '1m', 'fast_until': 60, 'vol': True, 'extra_checks': THREE_TO_1030, 'extra_mgmt': THREE_TO_1030})),
        ("E  15-min range, 5-min closes, checks every 5 min from 9:55", dict(**{'or': 15, 'conf': '5m', 'vol': True, 'extra_checks': (25,)})),
        ("F  15-min range, 1-min closes + 1-min checks 9:45-10:30 (your ask)", dict(**{'or': 15, 'conf': '1m', 'fast_until': 60, 'vol': True, 'extra_checks': ONE_945_1030, 'extra_mgmt': ONE_945_1030})),
        ("F' same, no volume test on 1-min bars", dict(**{'or': 15, 'conf': '1m', 'fast_until': 60, 'vol': False, 'extra_checks': ONE_945_1030, 'extra_mgmt': ONE_945_1030})),
    ]
    res = {}
    for lab, cfg in cfgs:
        res[lab] = run(cfg); summ(lab, *res[lab])
    base = res[cfgs[0][0]][0]
    random.seed(17)
    print()
    for lab, _ in cfgs[1:]:
        diffs = [a - b for a, b in zip(res[lab][0], base)]
        w = sum(sum(random.choice(diffs) for _ in diffs) > 0 for _ in range(4000))
        print(f"  {lab[:3]} vs current: {st.mean(diffs):+.3f}%/day, P(better)={w/4000:.0%}")
    print("\nLatency check (current vs F with 2-3 min latency, realistic for a 1-3 min checkpoint):")
    for lat in (2, 3):
        a = run(cfgs[0][1], lat); f = run(cfgs[6][1], lat)
        summ(f"  A latency {lat}", *a); summ(f"  F latency {lat}", *f)
