#!/usr/bin/env python3
"""Variable exits on the v5.2.46 system (governor 2026-11-12: "test a variable exit using the current as a default, find other exits
that can be triggered either on entry or during a trade"). Default = the live exit of each system (FADE v5.2.45: floor 0.5%, 1/3 at 2R,
+0.15R lock, 15-min cut, 2-ATR chandelier; PULLBACK v5.2.46: 1/3 at the morning high, 2/3 runner to a 20-EMA close).
Three kinds of override, each chosen on MASSIVE H1 ONLY and judged on MASSIVE H2 and Robinhood 2026 (never seen):
  ENTRY   a setup class (one entry-time feature, split at an H1 tercile) switches to another exit package
  DURING  a detector fires mid-trade and switches the remaining shares to a defensive or offensive action
  BOTH    the detector only runs inside an entry class
PASS = mean R per setup better on H2 and RH with paired bootstrap > 90% in each; then the account check.
    python3 -I tools/backtest/variable_exits.py > tools/backtest/results/variable_exits_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, adaptive_exit as AE, pb_exit_screen as PS, entry_pb as EP
rng = np.random.default_rng(21); LAST = 47


# ------------------------------------------------------------------ PULLBACK manager: default runner + override hooks
def pbm(t, pk=None, det=None, act=None):
    pk = pk or {}; b, k, e = t['b'], t['k'], t['entry']; r = e - t['stop']; stop = t['stop']
    T = t['T'] if pk.get('tgt', 'hod') == 'hod' else e + pk['tgt'] * r
    frac = pk.get('frac', 1 / 3); runx = pk.get('run', 'e20'); rem, g, hit, hic, bestc, out, pend = 1.0, 0.0, False, e, 0.0, False, None
    fired = None; tight = None; sell_next = 0.0; peak = k; j = k
    for j in range(k, LAST + 1):
        o, h, l, c, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if sell_next:
            q = min(sell_next, rem); g += q * (o - e); rem -= q; sell_next = 0
            if rem <= 1e-9: break
        if pend is not None: stop = max(stop, pend); pend = None
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if not hit and h >= T:
            px = max(T, o); q = min(frac, rem); g += q * (px - e); rem -= q; hit = True; stop = max(stop, e)
            if rem <= 1e-9: break
        cr = (c - e) / r
        if cr > bestc: bestc = cr; peak = j
        hic = max(hic, c)
        if pk.get('lock') and bestc >= pk['lock'][0]: pend = max(pend or -1e9, e + pk['lock'][1] * r)
        if hit and j < LAST:
            if runx == 'e20' and c < t['e20'][j]: out = True
            elif runx == 'e9' and c < t['e9'][j]: out = True
            elif runx == 'ch3': pend = max(pend or -1e9, hic - 3 * t['atr'][j])
        if tight and j < LAST: pend = max(pend or -1e9, hic - tight * t['atr'][j])
        if det and fired is None and j > k and j < LAST:
            S = dict(j=j, cr=cr, bestc=bestc, hit=hit, peak=peak)
            if det(t, j, S):
                fired = j
                if act == 'exit': out = True
                elif act == 'be': pend = max(pend or -1e9, e)
                elif act == 'third' and not hit: sell_next = frac; hit = True; stop = max(stop, e)
                elif act == 'tight1': tight = 1.0
                elif act == 'hold': runx = None            # offensive: stop using the EMA exit, keep breakeven / 13:30
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=g / r, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100, fired=fired)


def er(xs, j, n):
    d = sum(abs(xs[i] - xs[i - 1]) for i in range(j - n + 1, j + 1)); return (xs[j] - xs[j - n]) / d if d else 0.0
def pb_dets():
    C = lambda t: [x[3] for x in t['b']]
    D = {'pre: close < EMA9 after +0.5R': (lambda t, j, S: not S['hit'] and S['bestc'] >= 0.5 and t['b'][j][3] < t['e9'][j]),
         'pre: gave back 0.5R from best (>= +1R)': (lambda t, j, S: not S['hit'] and S['bestc'] >= 1.0 and S['bestc'] - S['cr'] >= 0.5),
         'pre: ER4 <= -0.5 after +0.5R': (lambda t, j, S: not S['hit'] and S['bestc'] >= 0.5 and j - t['k'] >= 4 and er(C(t), j, 4) <= -0.5),
         'pre: PSAR flip after +0.5R': (lambda t, j, S: not S['hit'] and S['bestc'] >= 0.5 and t['sar'][j] is not None and t['b'][j][2] < t['sar'][j]),
         'pre: no target after 60 min': (lambda t, j, S: not S['hit'] and j - t['k'] + 1 >= 12),
         'pre: below entry after 30 min': (lambda t, j, S: not S['hit'] and j - t['k'] + 1 >= 6 and S['cr'] < 0),
         'run: gave back 1R from best': (lambda t, j, S: S['hit'] and S['bestc'] - S['cr'] >= 1.0),
         'run: ER6 < -0.3': (lambda t, j, S: S['hit'] and j - t['k'] >= 6 and er(C(t), j, 6) < -0.3),
         'run: close < EMA9': (lambda t, j, S: S['hit'] and t['b'][j][3] < t['e9'][j]),
         'run: 3 lower closes': (lambda t, j, S: S['hit'] and all(t['b'][j - i][3] < t['b'][j - i - 1][3] for i in range(3))),
         'run: new high on 2x volume (strong trend)': (lambda t, j, S: S['hit'] and S['peak'] == j and t['b'][j][4] >= 2 * (st.mean(x[4] for x in t['b'][j - 6:j]) or 1))}
    A = {'pre': ['exit', 'be', 'third', 'tight1'], 'run': ['exit', 'tight1', 'hold']}
    return [(dn, df, a) for dn, df in D.items() for a in A[dn[:3] if dn[:3] in A else 'run']]
PB_PKGS = {'DEFAULT runner (1/3 high, EMA20)': {}, '100% at the high (old)': dict(frac=1.0), '1/2 high, EMA20': dict(frac=0.5),
           '1/3 high, EMA9 runner': dict(run='e9'), '1/3 high, 3-ATR chandelier': dict(run='ch3'), '1/3 high, hold to 13:30': dict(run=None),
           '1/3 at 2R, EMA20': dict(tgt=2.0), '1/3 high + lock +0.15R at +0.5R': dict(lock=(0.5, 0.15)), '2/3 high, EMA20': dict(frac=2 / 3)}


def boot(d):
    bs = np.array([rng.choice(d, len(d)).mean() for _ in range(2000)]); return 100 * np.mean(bs > 0)


def study(name, blocks, Rdef, Rpk, pknames, Rdet, detnames, feats):
    print(f"\n==================== {name} ====================")
    print('blocks: ' + ' | '.join(f"{B.name[:12]} {len(B.E)} setups, default {Rdef[b].mean():+.3f}R" for b, B in enumerate(blocks)))
    res = []
    # ENTRY: class -> best H1 package
    for f in feats[0][0]:
        v1 = np.array([x[f] for x in feats[1]]); cuts = np.percentile(v1, [33.3, 66.7])
        for lo_side in (True, False):
            for th in cuts:
                m1 = v1 < th if lo_side else v1 >= th
                if m1.sum() < 25: continue
                gain = (Rpk[1][m1] - Rdef[1][m1][:, None]).mean(0); p = int(np.argmax(gain))
                if gain[p] <= 0: continue
                ds_ = []
                for b in (0, 2):
                    v = np.array([x[f] for x in feats[b]]); m = v < th if lo_side else v >= th
                    ds_.append(np.where(m, Rpk[b][:, p], Rdef[b]) - Rdef[b])
                res.append(('ENTRY', f"{f} {'<' if lo_side else '>='} {th:.3g} -> {pknames[p]}", gain[p] * m1.mean(), ds_))
    # DURING: detector -> action (global)
    for i, dn in enumerate(detnames):
        h1 = (Rdet[1][:, i] - Rdef[1]).mean()
        if h1 > 0: res.append(('DURING', dn, h1, [Rdet[b][:, i] - Rdef[b] for b in (0, 2)]))
    # BOTH: detector inside a class (best detector for the class on H1)
    for f in feats[0][0]:
        v1 = np.array([x[f] for x in feats[1]]); cuts = np.percentile(v1, [33.3, 66.7])
        for lo_side in (True, False):
            for th in cuts:
                m1 = v1 < th if lo_side else v1 >= th
                if m1.sum() < 25: continue
                gain = (Rdet[1][m1] - Rdef[1][m1][:, None]).mean(0); p = int(np.argmax(gain))
                if gain[p] <= 0: continue
                ds_ = []
                for b in (0, 2):
                    v = np.array([x[f] for x in feats[b]]); m = v < th if lo_side else v >= th
                    ds_.append(np.where(m, Rdet[b][:, p], Rdef[b]) - Rdef[b])
                res.append(('BOTH', f"{f} {'<' if lo_side else '>='} {th:.3g} AND {detnames[p]}", gain[p] * m1.mean(), ds_))
    rows = []
    for kind, nm, h1, ds_ in res:
        m0, m2 = ds_[0].mean(), ds_[1].mean(); c0, c2 = boot(ds_[0]), boot(ds_[1])
        rows.append((bool(m0 > 0 and m2 > 0 and min(c0, c2) > 90), min(m0, m2), kind, nm, h1, m0, c0, m2, c2))
    rows.sort(key=lambda z: (-z[0], -z[1]))
    for kind in ('ENTRY', 'DURING', 'BOTH'):
        k_ = [r for r in rows if r[2] == kind]
        print(f"\n  {kind}: {len(k_)} rules that helped on H1 (design); passing out of sample: {sum(r[0] for r in k_)}. Top 8 by the weaker out-of-sample block:")
        for ok, sc, _, nm, h1, m0, c0, m2, c2 in k_[:8]:
            print(f"    {'PASS ' if ok else '     '}{nm:<96} H1 {h1:+.3f} | RH {m0:+.3f} ({c0:3.0f}%) | H2 {m2:+.3f} ({c2:3.0f}%)")
    return rows


def main():
    print(__doc__.split('\n')[0])
    # FADE
    FB = EF.blocks(F.P(floor_pct=0.5)); fnames = list(FS.PKGS)
    Rdef = [np.array([FS.manage(t, {})['R_out'] for t in B.E]) for B in FB]
    Rpk = [np.array([[FS.manage(t, FS.PKGS[n])['R_out'] for n in fnames] for t in B.E]) for B in FB]
    dl = [(dn, df, an, ac, arm) for arm in (0.5, 1.0) for dn, df in AE.DETS.items() for an, ac in AE.ACTS.items()]
    base_ae = [np.array([AE.manage(t, None, t['atr'])['R_out'] for t in B.E]) for B in FB]
    Rdet = [np.array([[AE.manage(t, dict(det=df, arm=arm, acts=ac), t['atr'])['R_out'] for (dn, df, an, ac, arm) in dl] for t in B.E]) - base_ae[b][:, None] + Rdef[b][:, None] for b, B in enumerate(FB)]
    feats = [[FS.features(B, t) for t in B.E] for B in FB]
    fr = study('FADE (default v5.2.45 exits)', FB, Rdef, Rpk, fnames, Rdet, [f"arm {arm:g}R {dn} -> {an}" for (dn, df, an, ac, arm) in dl], feats)
    # PULLBACK
    PBb = EP.blocks(EP.LIVE); pnames = list(PB_PKGS); dets = pb_dets()
    Rd = [np.array([pbm(t)['R_out'] for t in B.E]) for B in PBb]
    Rp = [np.array([[pbm(t, PB_PKGS[n])['R_out'] for n in pnames] for t in B.E]) for B in PBb]
    Rx = [np.array([[pbm(t, None, df, a)['R_out'] for (dn, df, a) in dets] for t in B.E]) for B in PBb]
    pfe = [[EP.feats(B, t) for t in B.E] for B in PBb]
    pr = study('PULLBACK (default v5.2.46 runner)', PBb, Rd, Rp, pnames, Rx, [f"{dn} -> {a}" for (dn, df, a) in dets], pfe)
    # account check of every passing rule
    print('\nAccount check of passing rules (system alone, live account rules): none above means nothing to check.')


if __name__ == '__main__':
    main()
