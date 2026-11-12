#!/usr/bin/env python3
"""Robustness of the afternoon RELVAL system (the one pass in more_systems.py): sector vs QQQ relative-move reversion after 13:30.
Grid: minimum gap (0.3/0.5/0.75/1.0%), stretch (2.0/2.5/3.0 sd of the 20-day daily relative move), target (half / full gap closed),
stop (1 / 1.5 gaps further). Book + system compounded per day (no interference). Paired day bootstrap of the change vs the book.
    python3 -I tools/backtest/relval_grid.py > tools/backtest/results/relval_grid_2026-11-12.txt"""
import itertools, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, other_systems as OS, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS, more_systems as MS
PX = OS.PX; rng = np.random.default_rng(13)
def relval(ds, p, d, b, xm, k_sd, tf, sm, rel):
    if p == 'QQQ': return None
    q = ds.bars['QQQ'].get(d)
    if not q: return None
    i = ds.idx[d]; hist = [rel[p][x] for x in ds.days[max(0, i - 20):i] if x in rel[p]]
    if len(hist) < 15: return None
    sd = st.pstdev(hist) or 1e-9
    for j in range(47, 75):
        rp = b[j][3] / b[0][0] - q[j][3] / q[0][0]
        if abs(rp) * 100 >= xm and abs(rp) >= k_sd * sd:
            s = -1 if rp > 0 else 1; k = j + 1; e = b[k][0]; gap = abs(rp) * e
            x, g = MS.run(b, k, s, e, e - s * sm * gap, 76, T=e + s * tf * gap); return MS.fin(d, p, k, x, e, g, sm * gap)
    return None
def main():
    FB = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); RUN = dict(frac=1 / 3, run=('ema', 20))
    ds_rh = F.DS(None, PX + PS.LEGS_RH); dm = F.DS(OS.AE.M5, PX + PS.LEGS_M); H = [ds_rh, dm, dm]
    book = [F.account(PB[b].ds, PB[b].days, [FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, RUN) for t in PB[b].E])['daily'] for b in range(3)]
    rels = {}
    for ds in (ds_rh, dm):
        rels[id(ds)] = {p: {x: ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0] for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']} for p in PX if p != 'QQQ'}
    names = ['RH 2026', 'M H1 21-24', 'M H2 24-26']; npass = 0; rows = []
    for xm, ksd, tf, sm in itertools.product((0.3, 0.5, 0.75, 1.0), (2.0, 2.5, 3.0), (0.5, 1.0), (1.0, 1.5)):
        cells = []; ok = True
        for b in range(3):
            ds = H[b]; days = PB[b].days
            T = [x for p in PX if p in ds.bars for d in days if d in ds.bars[p] for x in [relval(ds, p, d, ds.bars[p][d], xm, ksd, tf, sm, rels[id(ds)])] if x]
            a = F.account(ds, days, T); tk = a['taken']
            diff = np.array([((1 + book[b].get(d, 0) / 100) * (1 + a['daily'].get(d, 0) / 100) - 1) * 100 - book[b].get(d, 0) for d in days])
            bs = np.array([rng.choice(diff, len(diff)).mean() for _ in range(2000)]); chance = 100 * np.mean(bs > 0)
            ok &= diff.sum() > 0
            g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
            cells.append(f"{names[b]} n{len(tk):3d} PF{(g / l if l else 9):5.2f} alone {a['ret']:+6.1f}% add {diff.sum():+6.1f}pts ({chance:3.0f}%)")
        npass += ok; rows.append((ok, f"gap>={xm:.2f}% stretch>={ksd:.1f}sd target {tf:.1f} gap stop {sm:.1f} gap", cells))
    print(__doc__.split('\n')[0]); print('add = sum of daily return added to the book (points), bootstrap chance > 0')
    for ok, n, c in rows: print(f"  {'PASS ' if ok else '     '}{n:<52} " + ' | '.join(c))
    print(f"  passing in all three blocks: {npass} of {len(rows)}")
if __name__ == '__main__':
    main()
