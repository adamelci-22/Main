#!/usr/bin/env python3
"""Universe check of every system in the live book v5.2.65 (governor 2026-11-20: "make sure all the trade universes are optimal").
Research only. Book = PULLBACK (SOXS LABD TECS UVXY on the 5-minute tape), the 9:35 family (IBS-LONG, MIRROR, DIP on QQQ SOXX IWM XLK
XBI XLF), RELVAL (SOXX IWM XLK XBI XLF against QQQ) and the overnight leg at 50%, one shared account, Massive tape 2022-01..2026-10.
  A  9:35 family: drop one proxy; add one of SPY DIA TLT EEM FXI XLRE (3x both ways), XLE GDX XOP (2x), KRE XLV XLU (3x long only)
  B  RELVAL: drop one sector; add one new proxy measured against QQQ (both legs needed: SPY DIA TLT EEM FXI XLRE XLE GDX XOP)
  C  PULLBACK: drop one leg; add one inverse leg that has five-year bars (SQQQ, TZA, FAZ)
  D  OVERNIGHT: checked 2026-11-14 (overnight_universe.py): no change passed; not repeated
Pre-set rule: QUALIFIES = beats the live book on TRAIN (2022, 2024, 2026) compounded and in 2 of 3 train years; PASSES = also beats
it in BOTH TEST years (2023, 2025). Note: NVDQ, NVD, MSFU and SSG (live PULLBACK legs) have no five-year bars and are judged by the
paper trial drop.pb.NVDQ and the 8-month Robinhood screen, not here.
    python3 -I tools/backtest/universe2.py DATA_DIR > tools/backtest/results/universe2_2026-11-20.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import universe as U
F, B, BA, SB, N2, NS, TB = U.F, U.B, U.BA, U.SB, U.N2, U.NS, U.TB
import overnight as O
TR, TE = B.TR, B.TE; dm = B.dm


def main():
    path = os.path.join(sys.argv[1], 'M5U.json.gz')
    allp = list(F.LIVE) + list(U.NEW); F.LEV.update({p: (3, 3) for p in U.NEW}); ds = F.DS(path, allp); ctx = F.context(ds, allp)
    N2.PX = [p for p in allp if p != 'SPY']; N2.daily_init(ds)
    S = O.signals(); ovn = np.array([max([t for t in S.get(d, []) if t['kind'] == 'long'], key=lambda t: t['rv'])['pct'] / 100 if any(t['kind'] == 'long' for t in S.get(d, [])) else 0.0 for d in dm])

    dsx = F.DS(TB.AE.M5, list(F.LIVE) + list(B.PS.LEGS_M) + ['SQQQ', 'TZA', 'FAZ'])
    def pbt(legs):
        out = []
        for t in TB.pb_entries(dsx, dm, legs, dict(B.EP.LIVE)):
            m = B.PS.manage(t, B.BC.RUN); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1, proxy=t['proxy']))
        return out

    def rel(p, lev=3):
        b0 = [] if p not in ds.bars else None
        out = []
        for d in dm:
            b = ds.bars[p].get(d) if p in ds.bars else None
            if not b or len(b) < 78: continue
            x = NS.relval(ds, ctx, p, d, b, a=48, z=72, xm=1.0)
            if x: out.append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=(x['pct'] + NS.COST) * lev / 3 - NS.COST, leg_risk=x['leg_risk'] * lev / 3, rv=ds.rvol(p, d, x['k']), sys=0, proxy=p))
        return out

    PB = pbt(B.PS.LEGS_M); FAM = [t for p in F.LIVE for t in U.family(ds, ctx, p, (3, 3))]
    RV = {p: rel(p) for p in ['SOXX', 'IWM', 'XLK', 'XBI', 'XLF']}; REL = [t for v in RV.values() for t in v]

    def run(parts):
        r = BA.acct(dm, TB.byday([t for p in parts for t in p]), after_stop=False)[0]; return SB.yret((1 + r) * (1 + 0.5 * ovn) - 1)
    yb = run([PB, FAM, REL])
    def row(tag, y):
        print(U.row(tag, y, yb), flush=True)
        return U.verdict(y, yb)
    print(__doc__.split('\n')[0]); print('   years 2022 2023 2024 2025 2026 (TRAIN = 1st, 3rd, 5th); change = points against the live book\n')
    print(U.row('LIVE book v5.2.65', yb)); res = []
    print('\nA. 9:35 FAMILY')
    for p in F.LIVE: res.append(('A', f'family without {p}', row(f'family without {p}', run([PB, REL, [t for t in FAM if t['proxy'] != p]]))))
    for p, lev in U.NEW.items():
        if p not in ds.bars or len(ds.bars[p]) < 500: continue
        T = U.family(ds, ctx, p, lev); res.append(('A', f'family + {p}', row(f'family + {p} ({U.LEGS[p]}), {len(T)} signals', run([PB, REL, FAM, T]))))
    print('\nB. RELVAL')
    for p in RV: res.append(('B', f'RELVAL without {p}', row(f'RELVAL without {p}', run([PB, FAM, [t for t in REL if t['proxy'] != p]]))))
    for p, lev in U.NEW.items():
        if not lev[1] or p not in ds.bars or len(ds.bars[p]) < 500: continue
        T = rel(p, lev[0]); res.append(('B', f'RELVAL + {p}', row(f'RELVAL + {p} ({U.LEGS[p]}), {len(T)} signals', run([PB, FAM, REL, T]))))
    print('\nC. PULLBACK')
    for p in B.PS.LEGS_M: res.append(('C', f'PULLBACK without {p}', row(f'PULLBACK without {p}', run([[t for t in PB if t['proxy'] != p], FAM, REL]))))
    for p in ('SQQQ', 'TZA', 'FAZ'):
        T = pbt([p]); res.append(('C', f'PULLBACK + {p}', row(f'PULLBACK + {p}, {len(T)} signals', run([PB + T, FAM, REL]))))
    print('\nD. RELVAL COMBINATIONS of the passes (one test, chosen after the single tests: read with care)')
    base_rel = [t for t in REL if t['proxy'] != 'XBI']
    for tag, parts in (('RELVAL without XBI, + DIA', base_rel + rel('DIA')), ('RELVAL without XBI, + XLRE', base_rel + rel('XLRE')), ('RELVAL + DIA + XLRE', REL + rel('DIA') + rel('XLRE')),
                       ('RELVAL without XBI, + DIA + XLRE', base_rel + rel('DIA') + rel('XLRE'))):
        res.append(('D', tag, row(tag, run([PB, FAM, parts]))))
    print('\nSUMMARY')
    for g in 'ABCD':
        q = [(n, v) for k, n, v in res if k == g and v]
        print(f"   {g}: {len([1 for k, n, v in res if k == g])} changes tested; qualify {', '.join(n + ' (' + v + ')' for n, v in q) or 'none'}")


if __name__ == '__main__':
    main()
