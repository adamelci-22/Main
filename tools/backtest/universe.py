#!/usr/bin/env python3
"""Universe study (governor 2026-11-13: "do all of these systems work with each other or do we need to remove some, also feel free
to expand or shrink the universe of tradeable things"). Research only.
Baseline = the live joint book v5.2.51 (FADE + PULLBACK + IBS-TREND long + mirror + dip, no entry after an IBS-family stop-out).
Train = 2022, 2024, 2026; test = 2023, 2025. Rule fixed in advance for every change: it QUALIFIES if the book beats the baseline on
train compounded and in at least 2 of the 3 train years; it PASSES if it also beats the baseline in both test years.
  SHRINK  drop one proxy from FADE, one leg from PULLBACK, one proxy from the 9:35 family
  EXPAND  add one new proxy to the 9:35 family (IBS-TREND long, mirror, dip): SPY DIA TLT EEM FXI XLRE (3x both ways),
          XLE GDX XOP (2x both ways), KRE XLV XLU (3x long only: no mirror)
    python3 -I tools/backtest/universe.py DATA_DIR > tools/backtest/results/universe_2026-11-13.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, stock_fade as SF, boost as B, boost_mirror as BM, book_audit as BA
SB, N2, NS, TB = B.SB, B.N2, B.NS, B.TB; TR, TE = B.TR, B.TE; YEARS = SB.YEARS
NEW = {'SPY': (3, 3), 'DIA': (3, 3), 'TLT': (3, 3), 'EEM': (3, 3), 'FXI': (3, 3), 'XLRE': (3, 3), 'XLE': (2, 2), 'GDX': (2, 2), 'XOP': (2, 2), 'KRE': (3, 0), 'XLV': (3, 0), 'XLU': (3, 0)}
LEGS = dict(SPY='SPXL/SPXS', DIA='UDOW/SDOW', TLT='TMF/TMV', EEM='EDC/EDZ', FXI='YINN/YANG', XLRE='DRN/DRV', XLE='ERX/ERY', GDX='NUGT/DUST', XOP='GUSH/DRIP', KRE='DPST', XLV='CURE', XLU='UTSL')


def family(ds, ctx, p, lev=(3, 3)):
    """IBS-TREND long (sys 4), mirror (sys 5) and dip (sys 2) trades for one proxy, sized for its leverage."""
    out = []
    for d in B.dm:
        b = ds.bars[p].get(d)
        if not b or len(b) < 78: continue
        for fn, kw, sid in ((B.ibs_fn, {}, 4), (BM.mirror_fn, dict(hi=0.95, n=20), 5), (N2.rsi2d, dict(th=10, n=50, last=NS.END), 2)):
            if sid == 5 and not lev[1]: continue
            x = fn(ds, ctx, p, d, b, **kw)
            if not x: continue
            L = lev[1] if sid == 5 else lev[0]; pct = (x['pct'] + NS.COST) * L / 3 - NS.COST
            out.append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=pct, leg_risk=x['leg_risk'] * L / 3, rv=ds.rvol(p, d, x['k']), sys=sid, proxy=p))
    return out


def run(parts): return SB.yret(BA.acct(B.dm, TB.byday([t for p in parts for t in p]), after_stop=False)[0])


def verdict(y, yb):
    q = np.prod(1 + y[TR] / 100) > np.prod(1 + yb[TR] / 100) and (y[TR] > yb[TR]).sum() >= 2
    return 'PASS' if q and bool((y[TE] > yb[TE]).all()) else 'qual' if q else ''


def row(tag, y, yb=None):
    v = verdict(y, yb) if yb is not None else ''
    d = ('  change ' + ' '.join(f'{a:+6.1f}' for a in y - yb)) if yb is not None else ''
    return f"   {v:<5}{tag:<44} {' '.join(f'{a:+7.1f}' for a in y)} | avg 22-25 {y[:4].mean():+6.1f} worst {y[:4].min():+6.1f}{d}"


def main():
    path = os.path.join(sys.argv[1], 'M5U.json.gz')
    if not os.path.exists(path): SF.STK = dict(NEW); SF.STK.pop('SPY', None); SF.download(path)
    allp = list(F.LIVE) + list(NEW); F.LEV.update({p: (3, 3) for p in NEW}); ds = F.DS(path, allp); ctx = F.context(ds, allp)
    N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
    F0 = B.fade_trades(); P0 = TB.pb_entries(B.ds, B.dm, B.PS.LEGS_M, dict(B.EP.LIVE)); PBt = []
    for t in P0:
        m = B.PS.manage(t, B.BC.RUN); PBt.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1, proxy=t['proxy']))
    Fp = []
    for t in TB.fade_entries(B.ds, B.ctx, B.dm, 0.5):
        if t['fri'] or t['run']: continue
        m = B.FS.manage(t, {}); Fp.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=0, proxy=t['proxy']))
    fam = {p: family(ds, ctx, p, (3, 3)) for p in F.LIVE}; famnew = {p: family(ds, ctx, p, NEW[p]) for p in NEW if p in ds.bars and len(ds.bars[p]) > 500}
    FAM = [t for p in F.LIVE for t in fam[p]]; yb = run([Fp, PBt, FAM])
    print(__doc__.split('\n')[0]); print(f"   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); change = points against the baseline\n")
    print(row('BASELINE v5.2.51 joint book', yb))
    print('\nA. DO THE SYSTEMS WORK TOGETHER? one subsystem removed')
    for nm, parts in (('without FADE', [PBt, FAM]), ('without PULLBACK', [Fp, FAM]), ('without IBS-TREND long', [Fp, PBt, [t for t in FAM if t['sys'] != 4]]), ('without the mirror', [Fp, PBt, [t for t in FAM if t['sys'] != 5]]),
                      ('without the dip', [Fp, PBt, [t for t in FAM if t['sys'] != 2]])):
        print(row(nm, run(parts), yb))
    print('\nB. SHRINK: one ticker removed from one subsystem')
    for p in F.LIVE: print(row(f'FADE without {p}', run([[t for t in Fp if t['proxy'] != p], PBt, FAM]), yb))
    for p in B.PS.LEGS_M: print(row(f'PULLBACK without {p}', run([Fp, [t for t in PBt if t['proxy'] != p], FAM]), yb))
    for p in F.LIVE: print(row(f'9:35 family without {p}', run([Fp, PBt, [t for t in FAM if t['proxy'] != p]]), yb))
    print('\nC. EXPAND: one new proxy added to the 9:35 family (alone = that proxy only, full cash)')
    ok = []
    for p, T in famnew.items():
        ya = SB.yret(BA.acct(B.dm, TB.byday(T), after_stop=False)[0]); y = run([Fp, PBt, FAM, T]); v = verdict(y, yb)
        print(row(f'+ {p} ({LEGS[p]}, {NEW[p][0]}x{"" if NEW[p][1] else ", long only"}), {len(T)} signals', y, yb)); print(f"        {p} alone: {' '.join(f'{a:+6.1f}' for a in ya)}")
        if v: ok.append((p, v))
    print(f"\n   qualified on TRAIN: {', '.join(p + ' (' + v + ')' for p, v in ok) or 'none'}")
    q = [p for p, v in ok]; ps = [p for p, v in ok if v == 'PASS']
    if q: print(row('+ ALL that qualify on train: ' + ' '.join(q), run([Fp, PBt, FAM] + [famnew[p] for p in q]), yb))
    if ps and ps != q: print(row('+ ALL that pass: ' + ' '.join(ps), run([Fp, PBt, FAM] + [famnew[p] for p in ps]), yb))
    print(row('+ ALL twelve', run([Fp, PBt, FAM] + list(famnew.values())), yb))


if __name__ == '__main__':
    main()
