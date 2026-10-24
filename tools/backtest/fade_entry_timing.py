#!/usr/bin/env python3
"""FADE entry timing: can the first entry come earlier than 10:10 (or is later better)? Current lists (v5.2.14), 157 days.
    python3 tools/backtest/fade_entry_timing.py > tools/backtest/results/fade_entry_timing.txt
Variants (everything else unchanged: retest within 12 bars, 0.10% touch, close back inside, stop, exits, 13:30 out):
  box30 (live)  : box 9:30-10:00, break by the 10:10 bar, entry at the open after the retest bar  -> earliest entry 10:10
  box25         : box 9:30-9:55, break by the 10:05 bar                                            -> earliest entry 10:05
  box20         : box 9:30-9:50, break by the 10:00 bar                                            -> earliest entry 10:00
  box35         : box 9:30-10:05, break by the 10:15 bar                                           -> earliest entry 10:15
  box30 +1 bar  : live box, but enter one bar later (5 minutes after the retest close)             -> earliest entry 10:15
"""
import os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, final_system as FS, retest as RT, twobar as TB
from lab import get_data

ORIG_SETUP, ORIG_BOX = RT.setup, TB.box


def make(nbox, delay=0):
    def box(b): return max(x[1] for x in b[:nbox]), min(x[2] for x in b[:nbox])
    def setup(b, c):
        H, L = box(b)
        for j in range(nbox, min(nbox + 3, 76)):
            cl = b[j][3]; side = 1 if cl > H else -1 if cl < L else 0
            if not side: continue
            bb, p0 = (b, None) if side > 0 else m.mirror(b)
            to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
            E = to_m(H if side > 0 else L)
            for i in range(j + 1, min(j + 1 + c.max_wait, 76)):
                o, h, l, cc, v = bb[i]
                if l <= E * (1 + c.tol / 100):
                    if cc < E:
                        k = i + 1 + delay
                        if k > 75: return None
                        return k, -side, b[k][0], to_m(max(bb[q][1] for q in range(j, i + 1)))
                    return None
            return None
        return None
    return box, setup


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2
    mar = [d for d in days if d < '2026-04-07']
    k2t = lambda k: f"{(570 + 5 * k) // 60}:{(570 + 5 * k) % 60:02d}"
    print("FADE entry timing, current lists, 157 days (FADE alone | full system with PULLBACK)\n")
    print(f"{'variant':<16}{'earliest':>9} | {'FADE %/day':>10}{'H1':>8}{'H2':>8}{'March':>8}{'trades':>7}{'win%':>6}{'DD':>6} | {'FULL %/day':>10}{'H1':>8}{'H2':>8}{'March':>8}{'win%':>6}{'DD':>6} | first-entry times")
    for name, nbox, delay in (('box30 (live)', 6, 0), ('box25', 5, 0), ('box20', 4, 0), ('box35', 7, 0), ('box30 +1 bar', 6, 1)):
        bx, su = make(nbox, delay)
        RT.setup, TB.box = su, bx
        f, p = FS.cands(D, days)
        RT.setup, TB.box = ORIG_SETUP, ORIG_BOX
        if name == 'box30 (live)':
            f0, p0 = FS.cands(D, days)
            assert len(f0) == len(f) and all(a['day'] == b['day'] and a['k'] == b['k'] and abs(a['pct'] - b['pct']) < 1e-9 for a, b in zip(sorted(f0, key=lambda x: (x['day'], x['proxy'])), sorted(f, key=lambda x: (x['day'], x['proxy'])))), 'live variant does not reproduce the engine'
        row = []
        for cs in (f, f + p):
            a = MXD.account(D, days, cs); t = a['taken']
            sub = lambda ds: st.mean(MXD.account(D, ds, [c for c in cs if c['day'] in set(ds)])['daily'].values())
            row.append((st.mean(a['daily'].values()), sub(days[:h]), sub(days[h:]), sub(mar), len(t), 100 * sum(x['usd'] > 0 for x in t) / len(t), a['mdd'], t))
        tf = [x for x in row[1][7] if x['sys'] == 'FADE']
        times = collections.Counter(k2t(x['k']) for x in tf)
        first = ' '.join(f"{tm}:{n}" for tm, n in sorted(times.items(), key=lambda z: z[0].zfill(5))[:3])
        a, b = row
        print(f"{name:<16}{k2t(nbox + 2 + delay):>9} | {a[0]:>+10.3f}{a[1]:>+8.3f}{a[2]:>+8.3f}{a[3]:>+8.3f}{a[4]:>7}{a[5]:>6.0f}{a[6]:>6.1f} | {b[0]:>+10.3f}{b[1]:>+8.3f}{b[2]:>+8.3f}{b[3]:>+8.3f}{b[5]:>6.0f}{b[6]:>6.1f} | {first}")


if __name__ == '__main__':
    main()
