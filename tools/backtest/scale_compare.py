#!/usr/bin/env python3
"""Old lists (v5.2.12: FADE + AMD, PULLBACK + NVD) vs new lists (v5.2.14) at each account size, same capacity/impact model and whole-share check.
    python3 tools/backtest/scale_compare.py > tools/backtest/results/scale_compare.txt
"""
import importlib, io, contextlib, sys, os, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_system as FS
OLD = (['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD'], ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD'])
NEW = (['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF'], ['SOXS', 'LABD', 'TECS', 'UVXY'])
SIZES = (2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000, 2000000)
CAPS = (None, 0.50, 0.30, 0.20, 0.10, 0.05)
PI_DEFAULT = {'SOXS': 'SOXX', 'TECS': 'XLK', 'NVD': 'NVDA', 'LABD': 'LABD', 'UVXY': 'UVXY'}


def run(lists):
    FS.FADE[:] = lists[0]; FS.PB[:] = lists[1]
    for mod in ('scale_500k', 'whole_share_drag'):
        sys.modules.pop(mod, None)
    with contextlib.redirect_stdout(io.StringIO()):
        S = importlib.import_module('scale_500k')
    out = {}
    for a in SIZES:
        r = {c: S.account(S.base, a, c) for c in CAPS}
        b = max(r, key=lambda c: r[c]['day'])
        out[a] = (r[b]['day'], b, r[None]['day'], r[b].get('mdd'))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        importlib.import_module('whole_share_drag')
    ws = {}
    for line in buf.getvalue().splitlines():
        p = line.split()
        if p and p[0].replace(',', '').isdigit(): ws[int(p[0].replace(',', ''))] = (float(p[1].rstrip('%/d')), float(p[2].rstrip('%/d')))
    return out, ws


o, wo = run(OLD); n, wn = run(NEW)
print("Same 157 days (2026-03-03..10-14), same model. OLD = v5.2.12 (FADE ... AMD; PULLBACK ... NVD). NEW = v5.2.14 (FADE ... XLF; PULLBACK SOXS LABD TECS UVXY).")
print("Small accounts: whole-share rounding. Larger: liquidity cap + assumed market impact, best cap shown.\n")
print(f"{'account':>11} | {'OLD %/day':>9} {'$/day':>8} | {'NEW %/day':>9} {'$/day':>8} | {'diff %/day':>10} {'diff $/day':>10}")
for a in SIZES:
    if a in wo and a <= 10000:
        ov, nv = wo[a][1], wn[a][1]; tag = 'whole shares'
    else:
        ov, nv = o[a][0], n[a][0]; tag = f"cap old {'none' if o[a][1] is None else int(o[a][1]*100)}% / new {'none' if n[a][1] is None else int(n[a][1]*100)}%"
    print(f"{a:>11,} | {ov:>+9.3f} {a*ov/100:>8,.0f} | {nv:>+9.3f} {a*nv/100:>8,.0f} | {nv-ov:>+10.3f} {a*(nv-ov)/100:>+10,.0f}   ({tag})")
