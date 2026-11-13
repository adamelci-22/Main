#!/usr/bin/env python3
"""Two governor leads (2026-11-13): (1) PULLBACK partial targets set part-way to the morning high with the rest still aiming for the
high / running on the 20-EMA; (2) FADE far-box-edge: does the opposite box edge sitting inside the 2R path predict stalls, and do
edge-triggered actions (sell a tranche, raise the stop, sell half) beat the live exits. Exits only; entries as live (FADE floor 0.5%,
PULLBACK v5.2.46 entries). Three blocks: Robinhood 2026, Massive 2021-24, Massive 2024-26.
    python3 -I tools/backtest/halfway_and_edge.py > tools/backtest/results/halfway_and_edge_2026-11-13.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, pb_exit_screen as PS, entry_fade as EF, fade_setup_exits as FS
LAST = 47; rng = np.random.default_rng(31)


# ------------------------------------------------------------------ PULLBACK: tranches part-way to the morning high
def pbh(t, tr, ema_after='last', be=True):
    """tr = [(fraction of the distance entry->morning high, fraction of the original position)], sorted. The rest is the runner
    (20-EMA close exit, active once ema_after is satisfied: 'last' = all tranches filled, 'first' = first tranche filled)."""
    b, k, e, T, stop = t['b'], t['k'], t['entry'], t['T'], t['stop']; r = e - stop; stop0 = stop
    lv = [(e + p * (T - e), fr) for p, fr in tr]; filled = [False] * len(lv); rem = 1.0; g = 0.0; out = False; j = k
    run_frac = 1.0 - sum(f for _, f in tr)
    for j in range(k, LAST + 1):
        o, h, l, c, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if l <= stop: g += rem * (min(stop, o) - e); rem = 0; break
        for i, (px, fr) in enumerate(lv):
            if not filled[i] and h >= px:
                q = min(fr, rem); g += q * (max(px, o) - e); rem -= q; filled[i] = True
                if be: stop = max(stop, e)
        if rem <= 1e-9: break
        if run_frac > 1e-9 and j < LAST and ((all(filled) if ema_after == 'last' else any(filled))) and c < t['e20'][j]: out = True
    if rem > 1e-9: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=g / r, pct=g / e * 100 - PS.COST, leg_risk=r / e * 100)


PBV = [('LIVE v5.2.46: 1/3 at the high, 2/3 runner', [(1.0, 1 / 3)], 'last', True),
       ('OLD: 100% at the high', [(1.0, 1.0)], 'last', True),
       ('A. 1/3 half-way + 1/3 high + 1/3 runner', [(0.5, 1 / 3), (1.0, 1 / 3)], 'last', True),
       ('B. same, runner exit armed after the half-way fill', [(0.5, 1 / 3), (1.0, 1 / 3)], 'first', True),
       ('C. 1/3 half-way, 2/3 to the high (no runner)', [(0.5, 1 / 3), (1.0, 2 / 3)], 'last', True),
       ('D. 1/2 half-way, 1/2 to the high', [(0.5, 1 / 2), (1.0, 1 / 2)], 'last', True),
       ('E. 1/3 half-way, 2/3 runner only (no high target)', [(0.5, 1 / 3)], 'first', True),
       ('F. 1/3 at 1/3 of the way + 1/3 high + runner', [(0.33, 1 / 3), (1.0, 1 / 3)], 'last', True),
       ('G. 1/3 at 2/3 of the way + 1/3 high + runner', [(0.67, 1 / 3), (1.0, 1 / 3)], 'last', True),
       ('H. 1/4 half-way + 1/4 high + 1/2 runner', [(0.5, 1 / 4), (1.0, 1 / 4)], 'last', True),
       ('I. like A, stop stays at the dip stop after half-way', [(0.5, 1 / 3), (1.0, 1 / 3)], 'last', False),
       ('J. 1/3 at 40% of the way + 2/3 runner', [(0.4, 1 / 3)], 'first', True),
       ('K. 1/3 at 30% of the way + 2/3 runner', [(0.3, 1 / 3)], 'first', True)]


def pb_part():
    BL = PS.load(); base = None
    print('PART 1. PULLBACK partial targets part-way to the morning high (entries as live). account total (change), DD | per-setup mean R change, bootstrap chance > 0')
    print('blocks: ' + ' | '.join(f"{B.name[:12]} {len(B.E)} setups" for B in BL))
    for name, tr, ea, be in PBV:
        cells = []; R = []
        for B in BL:
            T = [pbh(t, tr, ea, be) for t in B.E]; a = F.account(B.ds, B.days, T); R.append(np.array([x['R_out'] for x in T]))
            cells.append((a['ret'], a['mdd'], R[-1]))
        if base is None: base = cells; print(f"  {name:<54} " + ' | '.join(f"{c[0]:+7.1f}% DD{c[1]:5.1f} R{c[2].mean():+.3f}" for c in cells)); continue
        out = []
        for c, b0 in zip(cells, base):
            d = c[2] - b0[2]; bs = np.array([rng.choice(d, len(d)).mean() for _ in range(2000)])
            out.append(f"{c[0]:+7.1f}% ({c[0] - b0[0]:+6.1f}) DD{c[1]:4.1f} R{d.mean():+.3f} ({100 * np.mean(bs > 0):3.0f}%)")
        ok = all(c[0] > b0[0] for c, b0 in zip(cells, base))
        print(f"  {'PASS ' if ok else '     '}{name:<54} " + ' | '.join(out))


# ------------------------------------------------------------------ FADE: far box edge
def fm(t, edge=None):
    """live FADE exits (FS.manage defaults) + an optional action when the high reaches the far box edge (far_R in [0.75, 2.0)).
    edge = 'third' (sell 1/3 there, replaces the 2R tranche) | 'extra' (sell 1/3 there AND keep 1/3 at 2R) | 'stop05' | 'half' (sell half of what is left)."""
    b, s, k, e = t['b'], t['side'], t['k'], t['entry']; stop = t['ext']; r = t['r']; at = t['atr']
    T = e + s * 2 * r; rem, g, hit, hic, bestc, pend, out = 1.0, 0.0, False, e, 0.0, None, False; j = k; edone = False
    E = t['far_R'] if (t['far_R'] is not None and 0.75 <= t['far_R'] < 2.0) else None
    tr2 = 1 / 3
    for j in range(k, LAST + 1):
        o, h, l, c, v = b[j]; fav, adv = (h, l) if s > 0 else (l, h)
        if out: g += rem * (o - e) * s; rem = 0; break
        if pend is not None:
            if (pend - stop) * s > 0: stop = pend
            pend = None
        if (adv - stop) * s <= 0: g += rem * ((stop if (o - stop) * s >= 0 else o) - e) * s; rem = 0; break
        if edge and E is not None and not edone and (fav - (e + s * E * r)) * s >= 0:
            px = e + s * E * r; px = px if (o - px) * s <= 0 else o; edone = True
            if edge == 'third': q = min(1 / 3, rem); g += q * (px - e) * s; rem -= q; hit = True; stop = e if (e - stop) * s > 0 else stop
            elif edge == 'extra': q = min(1 / 3, rem); g += q * (px - e) * s; rem -= q; stop = e if (e - stop) * s > 0 else stop
            elif edge == 'half': q = rem / 2; g += q * (px - e) * s; rem -= q; stop = e if (e - stop) * s > 0 else stop
            elif edge == 'stop05':
                ns = e + s * 0.5 * r
                if (ns - stop) * s > 0: stop = ns
            if rem <= 1e-9: break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o; q = min(tr2, rem); g += q * (px - e) * s; rem -= q; hit = True
            if (e - stop) * s > 0: stop = e
            if rem <= 1e-9: break
        cr = (c - e) * s / r; bestc = max(bestc, cr); hic = max(hic, c) if s > 0 else min(hic, c)
        if bestc >= 0.5:
            ns = e + s * 0.15 * r
            if (ns - stop) * s > 0: pend = ns
        if (hit or (edge == 'third' and edone)) and j < LAST:
            ns = hic - s * 2.0 * at[j]
            if (ns - stop) * s > 0: stop = ns
        if j - k + 1 == 3 and cr <= -0.5 and j < LAST: out = True
    if rem > 0: g += rem * (b[j][3] - e) * s
    lev = F.LEV[t['proxy']][0] if s > 0 else F.LEV[t['proxy']][1]
    mf = 0.0
    for x in b[k:j + 1]:
        mf = max(mf, ((x[1] if s > 0 else x[2]) - e) * s / r)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=g / r, pct=lev * g / e * 100 - F.LEGCOST, leg_risk=lev * r / e * 100, mfe=mf)


def edge_part():
    BL = EF.blocks(F.P(floor_pct=0.5))
    print('\nPART 2a. Does a far box edge inside the 2R path predict a stall? (FADE, live exits)')
    print('   Trades that reached +1R (before the edge matters): share that go on to 2R, split by where the far edge sits')
    for B in BL:
        rows = [(t['far_R'], fm(t)) for t in B.E if t['far_R'] is not None]
        near = [m for fr, m in rows if 0.75 <= fr < 2.0 and m['mfe'] >= 1.0]; far = [m for fr, m in rows if fr >= 2.0 and m['mfe'] >= 1.0]
        a = np.array([m['mfe'] >= 2.0 for m in near], float); bb = np.array([m['mfe'] >= 2.0 for m in far], float)
        d = a.mean() - bb.mean() if len(a) and len(bb) else float('nan')
        bs = np.array([rng.choice(a, len(a)).mean() - rng.choice(bb, len(bb)).mean() for _ in range(3000)]) if len(a) and len(bb) else np.zeros(1)
        print(f"   {B.name[:12]:<14} edge inside 2R: n {len(a):3d}, reach 2R {100 * a.mean():3.0f}% | edge beyond 2R: n {len(bb):3d}, reach 2R {100 * bb.mean():3.0f}% | gap {100 * d:+.0f} pts, chance edge-inside is lower {100 * np.mean(bs < 0):3.0f}%")
    print('\nPART 2b. Edge-triggered actions on the live FADE exits. account total (change) DD | per-setup mean R change, bootstrap chance > 0')
    base = [F.account(B.ds, B.days, [fm(t) for t in B.E]) for B in BL]; Rb = [np.array([fm(t)['R_out'] for t in B.E]) for B in BL]
    print('   LIVE exits: ' + ' | '.join(f"{B.name[:10]} {a['ret']:+7.1f}% DD{a['mdd']:5.1f} R{r.mean():+.3f}" for B, a, r in zip(BL, base, Rb)))
    for name, ed in (('sell 1/3 at the far edge (replaces the 2R tranche)', 'third'), ('sell 1/3 at the far edge AND keep 1/3 at 2R', 'extra'),
                     ('raise the stop to +0.5R at the far edge', 'stop05'), ('sell half of what is left at the far edge', 'half')):
        out = []; ok = True
        for B, b0, rb in zip(BL, base, Rb):
            T = [fm(t, ed) for t in B.E]; a = F.account(B.ds, B.days, T); r = np.array([x['R_out'] for x in T]); d = r - rb
            bs = np.array([rng.choice(d, len(d)).mean() for _ in range(2000)]); ok &= a['ret'] > b0['ret']
            out.append(f"{a['ret']:+7.1f}% ({a['ret'] - b0['ret']:+6.1f}) DD{a['mdd']:4.1f} R{d.mean():+.3f} ({100 * np.mean(bs > 0):3.0f}%)")
        print(f"   {'PASS ' if ok else '     '}{name:<54} " + ' | '.join(out))


if __name__ == '__main__':
    print(__doc__.split('\n')[0]); pb_part(); edge_part()
