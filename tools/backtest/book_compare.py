#!/usr/bin/env python3
"""Book comparison for the four-system build (governor 2026-11-13). One shared account (3% risk capped at cash, one position at a
time, 3 entries a day, same-system loss block). Year by year on the Massive tape 2021-12..2026-10 (FADE on 6 proxies, PULLBACK on the
4 legs that tape has), then the Robinhood 2026-03..10 check (8 PULLBACK legs). 2026 is the period the live rules were designed on;
2022-2025 are the years they never saw.
Books: LIVE v5.2.46 | SYSTEM 1 (robust tune) | SYSTEM 2 (best average month tune) | NEW = DIP + RELVAL without FADE/PULLBACK |
LIVE + RELVAL | LIVE + DIP + RELVAL | SYSTEM 1 + DIP + RELVAL.
    python3 -I tools/backtest/book_compare.py > tools/backtest/results/book_compare_2026-11-13.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, fade_setup_exits as FS, pb_exit_screen as PS, entry_pb as EP, adaptive_exit as AE
import tune_book as TB, new_systems as NS, new_systems2 as N2
N2.daily_init(F.DS(AE.M5, NS.PX))
RUN = dict(frac=1 / 3, run=('ema', 20))


def fade(ds, ctx, days, floor, pk, runaway=True):
    out = []
    for t in TB.fade_entries(ds, ctx, days, floor):
        if t['fri'] or (runaway and t['run']): continue
        m = FS.manage(t, pk); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=0))
    return out


def pb(ds, days, legs, P, cfg):
    out = []
    for t in TB.pb_entries(ds, days, legs, dict(EP.LIVE, **P)):
        m = PS.manage(t, cfg); out.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
    return out


def new(ds, ctx, days, fn, kw, sid):
    out = []
    for p in NS.PX:
        for d in days:
            b = ds.bars[p].get(d)
            if not b or len(b) < 78: continue
            x = fn(ds, ctx, p, d, b, **kw)
            if x: out.append(dict(day=d, k=x['k'], xbar=x['xbar'], pct=x['pct'], leg_risk=x['leg_risk'], rv=ds.rvol(p, d, x['k']), sys=sid, proxy=p))
    return out


def main():
    print(__doc__.split('\n')[0])
    R = {}
    for sn, ds, ctx, days, legs in TB.SETS:
        c = {}
        c['FADE'] = fade(ds, ctx, days, 0.5, {}); c['PB'] = pb(ds, days, legs, {}, RUN)
        c['FADE1'] = fade(ds, ctx, days, 0.5, dict(locklvl=0.0)); c['PB1'] = pb(ds, days, legs, dict(orh=6), RUN)
        c['FADE2'] = fade(ds, ctx, days, 1.0, dict(locklvl=0.0, cut=False), runaway=False); c['PB2'] = pb(ds, days, legs, dict(orh=6, vol=1.0), RUN)
        c['DIP'] = new(ds, ctx, days, N2.rsi2d, dict(th=10, n=50, last=NS.NOON), 2); c['DIPF'] = new(ds, ctx, days, N2.rsi2d, dict(th=10, n=50), 2)
        c['IBST'] = new(ds, ctx, days, N2.ibsf, dict(lo=0.1, n=50, last=NS.NOON), 4); c['REL'] = new(ds, ctx, days, NS.relval, dict(a=48, z=72, xm=1.0), 3)
        dd = {(t['day'], t['proxy']) for t in c['DIP']}; ii = {(t['day'], t['proxy']) for t in c['IBST']}
        c['DIPOR'] = c['DIP'] + [dict(t, sys=2) for t in c['IBST'] if (t['day'], t['proxy']) not in dd]
        print(f"# {sn}: DIP signals {len(dd)}, IBS-TREND signals {len(ii)}, shared {len(dd & ii)}")
        R[sn] = c
    BOOKS = [('FADE alone (live)', ['FADE']), ('PULLBACK alone (live)', ['PB']), ('DIP alone (out 13:30)', ['DIP']), ('DIP alone (out 15:55)', ['DIPF']), ('IBS-TREND alone (out 13:30)', ['IBST']), ('RELVAL alone', ['REL']), None,
             ('LIVE v5.2.46', ['FADE', 'PB']), ('SYSTEM 1 robust', ['FADE1', 'PB1']), ('SYSTEM 2 best month', ['FADE2', 'PB2']), ('NEW: DIP + RELVAL', ['DIP', 'REL']), ('NEW: DIP(15:55) only', ['DIPF']),
             ('NEW: DIP-or-IBS + RELVAL', ['DIPOR', 'REL']), ('LIVE + RELVAL', ['FADE', 'PB', 'REL']), ('LIVE + DIP + RELVAL', ['FADE', 'PB', 'DIP', 'REL']), ('SYSTEM 1 + DIP + RELVAL', ['FADE1', 'PB1', 'DIP', 'REL']),
             ('SYSTEM 1 + RELVAL', ['FADE1', 'PB1', 'REL']), ('SYSTEM 2 + DIP + RELVAL', ['FADE2', 'PB2', 'DIP', 'REL'])]
    dm = TB.days_m; ym = [d[:7] for d in dm]; mi = [i for i in range(len(ym)) if i == 0 or ym[i] != ym[i - 1]]
    yy = ['2022' if d < '2022-01-01' else d[:4] for d in dm]; yi = [i for i in range(len(yy)) if i == 0 or yy[i] != yy[i - 1]]
    print(f"\n{'book':<30} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7} {'2026':>7} | {'total':>7} {'maxDD':>6} | 22-25 cmpd | month mean  med   win% worst | RH 2026    DD")
    for bk in BOOKS:
        if bk is None: print(); continue
        name, parts = bk
        r = TB.account(dm, TB.byday([t for p in parts for t in R['M'][p]]), {}); mo, dd, tot = TB.stats(r, mi); yr, _, _ = TB.stats(r, yi)
        rr = TB.account(TB.days_r, TB.byday([t for p in parts for t in R['R'][p]]), {}); _, ddr, totr = TB.stats(rr, [0])
        pre = (np.prod(1 + yr[:4]) - 1) * 100
        print(f"{name:<30} {' '.join(f'{v * 100:+7.1f}' for v in yr)} | {tot:+7.1f} {dd:6.1f} | {pre:+9.1f}% | {mo.mean() * 100:+9.2f} {np.median(mo) * 100:+5.2f} {100 * np.mean(mo > 0):5.0f}% {mo.min() * 100:+5.1f} | {totr:+7.1f} {ddr:5.1f}")


if __name__ == '__main__':
    main()
