#!/usr/bin/env python3
"""TMF / TMV on PULLBACK with the filters loosened (they formed 0 setups under the live rules).
    python3 tools/backtest/pb_tmf_loose.py > tools/backtest/results/pb_tmf_loose.txt
Funnel: for each ticker, how many (day, bar) candidates survive each stage of pb_final.scan under the LIVE rules and under looser ones.
Variants loosen the stop-distance floor (0.75%), room-to-target (0.25%), reward/risk (0.75), and the volume multiple (1.5x).
Each variant is applied to TMF/TMV AND to the live four, so the spill-over onto the live tickers is visible.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, final_system as FS, combo_search as C
from lab import get_data

VOLX = [1.5]
SCAN_ORIG = PBF.scan


def scan(b, e9, e20, oco_gap):
    bh = max(x[1] for x in b[:3])
    for j in range(8, 41):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > VOLX[0] * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre)); stop = low * (1 - PBF.BUFFER_PCT / 100)
            hod = PBF.target_level(b, pre, hod); lim = b[j][3]
            if b[j + 1][2] > lim: continue
            entry = min(b[j + 1][0], lim)
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < PBF.MIN_ROOM: continue
            if (hod - entry) < PBF.MIN_RR * (entry - stop) or (hod - entry) / entry * 100 < PBF.MIN_ROOM_PCT: continue
            if oco_gap and hod - stop < 0.10: continue
            return dict(k=j + 1, entry=entry, stop=stop, hod=hod, sig=j)
    return None


PBF.scan = scan
VARIANTS = [('LIVE rules', 0.75, 0.25, 0.75, 1.5), ('stop floor 0.40%', 0.40, 0.25, 0.75, 1.5), ('stop 0.40, room 0.15', 0.40, 0.15, 0.75, 1.5),
            ('stop 0.40, room 0.15, R/R 0.5', 0.40, 0.15, 0.50, 1.5), ('volume 1.0x', 0.75, 0.25, 0.75, 1.0),
            ('ALL loose: stop 0.40 room 0.15 R/R 0.5 vol 1.0x', 0.40, 0.15, 0.50, 1.0), ('EXTREME: stop 0.25 room 0.10 R/R 0.3 vol 0.8x', 0.25, 0.10, 0.30, 0.8)]


def funnel(D, days, sym):
    cnt = dict(days=0, trend=0, dip=0, ema_zone=0, trigger=0, vol=0, fill=0, stop_floor=0, room=0)
    for d in days:
        b = D.bars[sym].get(d)
        if not b: continue
        cnt['days'] += 1
        e9 = m.ema([x[3] for x in D.bars[sym][D.days[D.days.index(d) - 1]]] + [x[3] for x in b], 9)[78:] if False else None
    return cnt


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2
    mar = [d for d in days if d < '2026-04-07']
    PI.PROXY.update(C.PB_MAP); PI.PROXY.update({'TMF': 'TLT', 'TMV': 'TLT'})
    f, _ = FS.cands(D, days)
    live = ['SOXS', 'LABD', 'TECS', 'UVXY']
    for q in ('TMF', 'TMV'):
        B = D.bars[q]; ds = [d for d in days if d in B]
        rng = st.median((max(x[1] for x in B[d]) - min(x[2] for x in B[d])) / B[d][0][0] * 100 for d in ds)
        print(f"{q}: median day range {rng:.2f}%, median 5-min $vol {st.median(sum(x[4]*x[3] for x in B[d][6:47])/41 for d in ds)/1e3:,.0f}k")
    print()
    print(f"{'variant':<52}{'TMF':>5}{'TMV':>5} | {'live4 setups':>12} | PB-alone live4+TMF+TMV: %/day  H1  H2  March  win% trades | vs live4 same filters")
    for name, room, roompct, rr, vx in VARIANTS:
        PBF.MIN_ROOM, PBF.MIN_ROOM_PCT, PBF.MIN_RR = room, roompct, rr; VOLX[0] = vx
        res = {}
        for q in live + ['TMF', 'TMV']:
            PI.PROXY.setdefault(q, q)
            s = PBF.run(D, days, [q], oco_gap=True)
            res[q] = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
        def run(L, ds):
            a = MXD.account(D, ds, [c for q in L for c in res[q] if c['day'] in set(ds)]); return a
        def sub(L, ds): return st.mean(run(L, ds)['daily'].values())
        L6 = live + ['TMF', 'TMV']; a = run(L6, days); t = a['taken']; a0 = run(live, days)
        win = 100 * sum(x['usd'] > 0 for x in t) / max(1, len(t))
        print(f"{name:<52}{len(res['TMF']):>5}{len(res['TMV']):>5} | {sum(len(res[q]) for q in live):>12} | {st.mean(a['daily'].values()):>+8.3f} {sub(L6, days[:h]):>+6.3f} {sub(L6, days[h:]):>+6.3f} {sub(L6, mar):>+6.3f} {win:>5.0f} {len(t):>6} | live4 alone: {st.mean(a0['daily'].values()):+.3f} (H1 {sub(live, days[:h]):+.3f} H2 {sub(live, days[h:]):+.3f} Mar {sub(live, mar):+.3f}, {len(a0['taken'])} trades, win {100*sum(x['usd']>0 for x in a0['taken'])/len(a0['taken']):.0f}%)")
        if res['TMF'] or res['TMV']:
            for q in ('TMF', 'TMV'):
                r = res[q]
                if r: print(f"      {q}: {len(r)} setups, win {100*sum(c['pct']>0 for c in r)/len(r):.0f}%, avg {st.mean(c['pct'] for c in r):+.2f}%, sum {sum(c['pct'] for c in r):+.1f}%, without best 1 {sum(sorted(c['pct'] for c in r)[:-1]):+.1f}%")
    PBF.MIN_ROOM, PBF.MIN_ROOM_PCT, PBF.MIN_RR = 0.75, 0.25, 0.75; VOLX[0] = 1.5


if __name__ == '__main__':
    main()
