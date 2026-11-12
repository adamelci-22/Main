#!/usr/bin/env python3
"""FADE setup-conditional exits (governor 2026-11-12: "variable exits, multiple exit types triggered by certain setups").
At ENTRY the setup is classified from facts known before the order (box width, stop size, far box edge distance, ATR vs stop,
gap and trend vs the trade, RVOL, entry time, market so far, retest depth and wait). Each class gets its own exit package.
Method (guards against curve fitting): every setup is replayed under every exit package; a policy = one feature split at a
threshold into two classes, each class given the package that did best on MASSIVE H1 ONLY (design). The policy is then judged on
MASSIVE H2 and the Robinhood sample, which it never saw. The oracle row (best package per trade in hindsight) is the ceiling.
    python3 -I tools/backtest/fade_setup_exits.py > tools/backtest/results/fade_setup_exits_2026-11-12.txt"""
import os, sys, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, adaptive_exit as AE
LAST = 47


def manage(t, pk):
    """pk: tp (R or 'far'), frac, chand (ATR mult, 0 = none), lock (bool), cut (bool), be (bool)."""
    b, s, k, e = t['b'], t['side'], t['k'], t['entry']; stop = t['ext']; r = t['r']
    tp = pk.get('tp', 2.0)
    if tp == 'far': tp = t['far_R'] if t['far_R'] is not None and 0.75 <= t['far_R'] < 2.0 else 2.0
    T = e + s * tp * r if tp else None; frac = pk.get('frac', 1 / 3); ch = pk.get('chand', 2.0)
    rem, g, hit, hic, bestc, pend, out = 1.0, 0.0, False, e, 0.0, None, False; at = t['atr']; j = k
    for j in range(k, LAST + 1):
        o, h, l, cl, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: g += rem * (o - e) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0: px = stop if (o - stop) * s >= 0 else o; g += rem * (px - e) * s; rem = 0; break
        if T is not None and not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; q = min(frac, rem); g += q * (px - e) * s; rem -= q; hit = True
            if pk.get('be', True) and (e - stop) * s > 0: stop = e
            if rem <= 1e-9: break
        cr = (cl - e) * s / r; bestc = max(bestc, cr); hic = max(hic, cl) if s > 0 else min(hic, cl)
        if pk.get('lock', True) and bestc >= pk.get('lockarm', 0.5):
            ns = e + s * pk.get('locklvl', 0.15) * r
            if (ns - stop) * s > 0: pend = ns
        if ch and j < LAST and (hit or (T is None and bestc >= pk.get('arm', 1.0))):
            ns = hic - s * ch * at[j]
            if (ns - stop) * s > 0: stop = ns
        if pk.get('cut', True) and j - k + 1 == pk.get('cutbars', 3) and cr <= pk.get('cutR', -0.5) and j < LAST: out = True
    if rem > 0: g += rem * (b[j][3] - e) * s
    lev = F.LEV[t['proxy']][0] if s > 0 else F.LEV[t['proxy']][1]
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=g / r, pct=lev * g / e * 100 - F.LEGCOST, leg_risk=lev * r / e * 100)


PKGS = {'LIVE 1/3@2R chand2': dict(),
        '1/3@far edge': dict(tp='far'), '1/3@1.5R': dict(tp=1.5), '1/3@2.5R': dict(tp=2.5), '1/3@3R': dict(tp=3.0),
        '1/2@2R': dict(frac=0.5), '100%@2R': dict(frac=1.0), '100%@far edge': dict(tp='far', frac=1.0), '100%@1.5R': dict(tp=1.5, frac=1.0),
        'no target, chand2 from +1R': dict(tp=None), 'no target, chand3 from +1R': dict(tp=None, chand=3.0),
        '1/3@2R chand3': dict(chand=3.0), '1/3@2R chand1.5': dict(chand=1.5), '1/3@2R no lock': dict(lock=False),
        '1/3@2R no cut': dict(cut=False), '1/3@2R hold runner (BE only)': dict(chand=0)}


def features(B, t):
    ds, ctx = B.ds, B.ctx; k, s, p, d = t['k'], t['side'], t['proxy'], t['day']; r = t['r']
    g = ctx['gap'][p].get(d); tr = ctx['trend'][p].get(d)
    return {'far edge R': t['far_R'] if t['far_R'] is not None else 9.0, 'ATR/R': t['atr'][k - 1] / r, 'stop %': r / t['entry'] * 100,
            'box %': t['box_pct'], 'gap vs trade %': (g or 0) * s * 100, 'trend vs trade %': (tr or 0) * s * 100,
            'RVOL': ds.rvol(p, d, k), 'entry bar': k, 'QQQ so far vs trade %': (t['mk'][k - 1] if t['mk'] else 0.0),
            'retest depth': t['depth'], 'wait bars': t['wait'], 'prior-day level R': t['pdx_R'] if t['pdx_R'] is not None else 9.0}


def main():
    BL = AE.load(); names = list(PKGS)
    R = []; X = []
    for B in BL:
        R.append(np.array([[manage(t, PKGS[n])['R_out'] for n in names] for t in B.E])); X.append([features(B, t) for t in B.E])
    print(__doc__.split('\n')[0])
    print('blocks: ' + ' | '.join(f"{B.name}: {len(B.E)} setups" for B in BL))
    print('\nA. Each exit package alone: mean R per setup (all setups, no account)')
    for i, n in enumerate(names): print(f"  {n:<30} " + ' | '.join(f"{B.name[:10]} {R[b][:, i].mean():+.3f}" for b, B in enumerate(BL)))
    print('  ' + f"{'ORACLE (best per trade, hindsight)':<30} " + ' | '.join(f"{B.name[:10]} {R[b].max(1).mean():+.3f}" for b, B in enumerate(BL)))
    feats = list(X[0][0]); rows = []
    for f in feats:
        v1 = np.array([x[f] for x in X[1]])
        for q in (33, 50, 67):
            th = np.percentile(v1, q)
            lo1 = v1 < th
            if lo1.sum() < 20 or (~lo1).sum() < 20: continue
            plo = int(np.argmax(R[1][lo1].mean(0))); phi = int(np.argmax(R[1][~lo1].mean(0)))
            if plo == 0 and phi == 0: continue
            res = []
            for b in range(3):
                v = np.array([x[f] for x in X[b]]); lo = v < th
                pol = np.where(lo, R[b][:, plo], R[b][:, phi]); res.append((pol.mean() - R[b][:, 0].mean(), pol))
            rows.append((min(res[0][0], res[2][0]), f, q, th, names[plo], names[phi], res))
    rows.sort(key=lambda z: -z[0])
    print('\nB. Two-class policies: feature < threshold -> package A, else package B (packages picked on MASSIVE H1 only). Change in mean R per setup vs LIVE.')
    print('   Out-of-sample blocks are MASSIVE H2 and RH. OOS PASS = better in both, with a bootstrap chance > 90% in each.')
    rng = np.random.default_rng(3)
    for sc, f, q, th, a, bpk, res in rows[:30]:
        ch = []
        for b in (0, 2):
            d = res[b][1] - R[b][:, 0]; bs = np.array([rng.choice(d, len(d)).mean() for _ in range(3000)]); ch.append(100 * np.mean(bs > 0))
        ok = res[0][0] > 0 and res[2][0] > 0 and min(ch) > 90
        print(f"  {'PASS ' if ok else '     '}{f:<22} < {th:7.3f} (p{q}) -> {a:<28} else {bpk:<28} | RH {res[0][0]:+.3f} ({ch[0]:3.0f}%) | H1 {res[1][0]:+.3f} (design) | H2 {res[2][0]:+.3f} ({ch[1]:3.0f}%)")
    # best policy at account level
    if rows:
        sc, f, q, th, a, bpk, res = rows[0]
        print(f"\nC. Account check of the top policy ({f} < {th:.3f} -> {a}, else {bpk}): FADE alone, live account rules")
        for b, B in enumerate(BL):
            base = F.account(B.ds, B.days, [manage(t, PKGS[names[0]]) for t in B.E])
            pol = F.account(B.ds, B.days, [manage(t, PKGS[a] if features(B, t)[f] < th else PKGS[bpk]) for t in B.E])
            print(f"  {B.name:<26} live {base['ret']:+7.1f}% DD {base['mdd']:4.1f}%  ->  policy {pol['ret']:+7.1f}% DD {pol['mdd']:4.1f}%")


if __name__ == '__main__':
    main()
