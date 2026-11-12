#!/usr/bin/env python3
"""FADE exit search on the v5.2.45 system (stop floor 0.5%). Governor 2026-11-12: "find the best absolute best variable fade exits
for this new system". Fixed packages, lock / cut / target / chandelier grids, setup-conditional policies (chosen on MASSIVE H1 only),
in-trade detectors (adaptive_exit), and the combined account with PULLBACK (live and runner).
    python3 -I tools/backtest/fade_exit_floor.py > tools/backtest/results/fade_exit_floor_2026-11-12.txt"""
import itertools, os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, adaptive_exit as AE, pb_exit_screen as PS
BL = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); rng = np.random.default_rng(9)
def acct(b, pk): return F.account(BL[b].ds, BL[b].days, [FS.manage(t, pk) for t in BL[b].E])
base_R = [np.array([FS.manage(t, {})['R_out'] for t in B.E]) for B in BL]; base_A = [acct(b, {}) for b in range(3)]
def row(name, pk):
    cells = []; ok = True; ch = []
    for b, B in enumerate(BL):
        rr = np.array([FS.manage(t, pk)['R_out'] for t in B.E]); d = rr - base_R[b]
        bs = np.array([rng.choice(d, len(d)).mean() for _ in range(2000)]); a = acct(b, pk)
        ok &= a['ret'] > base_A[b]['ret'] + 1e-9; ch.append(100 * np.mean(bs > 0))
        cells.append(f"{a['ret']:+7.1f}% ({a['ret'] - base_A[b]['ret']:+6.1f}) DD{a['mdd']:5.1f} R{rr.mean():+.3f} ({d.mean():+.3f},{ch[-1]:3.0f}%)")
    return ok, min(ch), name, cells
G = [('LIVE v5.2.45 exits (1/3@2R, lock +0.15R at +0.5R, 15-min cut, chand 2)', {})]
G += [(n, p) for n, p in FS.PKGS.items() if n != 'LIVE 1/3@2R chand2']
for tp, fr, ch in itertools.product((1.5, 2.0, 2.5, 3.0), (1 / 4, 1 / 3, 1 / 2), (1.5, 2.0, 2.5, 3.0)):
    if (tp, fr, ch) != (2.0, 1 / 3, 2.0): G.append((f'grid: {fr:.2f} @ {tp:g}R, chand {ch:g}', dict(tp=tp, frac=fr, chand=ch)))
for la, ll in itertools.product((0.3, 0.5, 0.75, 1.0, 1.25), (0.0, 0.15, 0.3, 0.5)):
    if ll < la and (la, ll) != (0.5, 0.15): G.append((f'lock: +{ll:g}R at +{la:g}R', dict(lockarm=la, locklvl=ll)))
G.append(('lock off', dict(lock=False)))
for cb, cr_ in itertools.product((2, 3, 4, 6), (-0.3, -0.5, -0.7)):
    if (cb, cr_) != (3, -0.5): G.append((f'cut: {cb * 5} min at {cr_:g}R', dict(cutbars=cb, cutR=cr_)))
G.append(('cut off', dict(cut=False)))
rows = [row(n, p) for n, p in G]
print(__doc__.split('\n')[0]); print('blocks: ' + ' | '.join(f"{B.name}: {len(B.E)} setups" for B in BL))
print('\nA. Fixed exits. account total (change) DD, mean R per setup (change, bootstrap chance > 0). PASS = account better in all three blocks')
live = rows[0]; rest = sorted(rows[1:], key=lambda z: (-z[0], -z[1]))
for ok, c, name, cells in [live] + rest:
    print(f"  {('PASS ' if ok else '     ') + name:<70} " + ' | '.join(f"{B.name[:10]} {x}" for B, x in zip(BL, cells)))
# B. setup-conditional policies on the floored system
names = list(FS.PKGS); R = [np.array([[FS.manage(t, FS.PKGS[n])['R_out'] for n in names] for t in B.E]) for B in BL]
X = [[FS.features(B, t) for t in B.E] for B in BL]
print('\nB. Setup-conditional policies (feature split at an H1 percentile, each class gets its best H1 package). Judged on RH and M H2.')
print(f"   ORACLE ceiling (best package per trade in hindsight): " + ' | '.join(f"{B.name[:10]} {R[b].max(1).mean():+.3f}R vs {R[b][:, 0].mean():+.3f}R" for b, B in enumerate(BL)))
out = []
for f in X[0][0]:
    v1 = np.array([x[f] for x in X[1]])
    for q in (33, 50, 67):
        th = np.percentile(v1, q); lo1 = v1 < th
        if lo1.sum() < 20 or (~lo1).sum() < 20: continue
        a_, b_ = int(np.argmax(R[1][lo1].mean(0))), int(np.argmax(R[1][~lo1].mean(0)))
        if a_ == 0 and b_ == 0: continue
        res = []
        for b in range(3):
            v = np.array([x[f] for x in X[b]]); pol = np.where(v < th, R[b][:, a_], R[b][:, b_]); d = pol - R[b][:, 0]
            bs = np.array([rng.choice(d, len(d)).mean() for _ in range(2000)]); res.append((d.mean(), 100 * np.mean(bs > 0)))
        ok = bool(res[0][0] > 0 and res[2][0] > 0 and min(res[0][1], res[2][1]) > 90)
        out.append((ok, min(res[0][0], res[2][0]), f"{f} < {th:.3g} -> {names[a_]} else {names[b_]}", res))
out.sort(key=lambda z: (-z[0], -z[1]))
for ok, sc, name, res in out[:12]:
    print(f"  {('PASS ' if ok else '     ') + name:<92} RH {res[0][0]:+.3f} ({res[0][1]:3.0f}%) | H1 {res[1][0]:+.3f} (design) | H2 {res[2][0]:+.3f} ({res[2][1]:3.0f}%)")
print(f"  policies tested {len(out)}, passing {sum(o[0] for o in out)}")
# C. in-trade detectors from adaptive_exit, on the floored entries
print('\nC. In-trade detectors -> defensive actions (adaptive_exit), floored entries. PASS = avg R better in all three blocks')
ab = [AE.run(B, None) for B in BL]; cnt = 0; passed = []
for arm in (1.0, 0.5):
    for dn, df in AE.DETS.items():
        for an, ac in AE.ACTS.items():
            res = [AE.run(B, dict(det=df, arm=arm, acts=ac)) for B in BL]; cnt += 1
            if all(x['R'] > y['R'] + 1e-9 for x, y in zip(res, ab)): passed.append((f"arm {arm:g}R | {dn} -> {an}", res))
print(f"  default under this manager: " + ' | '.join(f"{B.name[:10]} R {x['R']:+.3f} acct {x['ret']:+.1f}%" for B, x in zip(BL, ab)))
print(f"  detector rules tested {cnt}, passing {len(passed)}")
for name, res in passed[:10]: print(f"  PASS {name:<66} " + ' | '.join(f"{B.name[:10]} R {x['R']:+.3f} ({x['R'] - y['R']:+.3f}) acct {x['ret']:+.1f}% f{x['fired']}" for B, x, y in zip(BL, res, ab)))
