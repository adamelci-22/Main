#!/usr/bin/env python3
"""Does a bigger universe help? Add-one tests on top of the live system (final_system.py), FADE proxies and PULLBACK tickers.
    python3 tools/backtest/universe_study.py > tools/backtest/results/universe_study.txt
Base = FADE QQQ SOXX IWM XLK XBI AMD + PULLBACK SOXS LABD TECS UVXY NVD, 2026-03-03..10-14, $2,000, same engine as final_system.py.
Each candidate is added alone; judged on both halves and on the untouched window (03-03..04-06). Thin legs (median 5-min $ volume < LIQ) flagged.
"""
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
import final_system as FS
from lab import get_data

FADE_CAND = ['SPY', 'XLF', 'XLE', 'NVDA']           # TSLA excluded by the governor
PB_CAND = [s for s in EX.NEW_PB]


def pbc(D, days, names):
    for n in names: PI.PROXY.setdefault(n, n)
    s = PBF.run(D, days, names, oco_gap=True)
    return [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]


def fadec(D, days, p):
    return MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')


def st_(D, days, cs):
    a = MXD.account(D, days, cs); dl = a['daily']; h = len(days) // 2
    return dict(d=st.mean(dl.values()), h1=st.mean(dl[d] for d in days[:h]), h2=st.mean(dl[d] for d in days[h:]), ret=a['ret'], dd=a['mdd'], n=len(a['taken']),
                tdays=len({x['day'] for x in a['taken']}))


def row(tag, s, b, extra=''):
    print(f"{tag:<18}{s['d']:+.3f} ({s['d']-b['d']:+.3f}) H1 {s['h1']:+.3f} ({s['h1']-b['h1']:+.3f}) H2 {s['h2']:+.3f} ({s['h2']-b['h2']:+.3f}) "
          f"ret {s['ret']:+6.1f}% DD {s['dd']:.1f}% trades {s['n']:3d} tradedays {s['tdays']:3d} {extra}")


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    mar = [d for d in days if d < '2026-04-07']
    f, p = FS.cands(D, days); fm = [c for c in f if c['day'] < '2026-04-07']; pm = [c for c in p if c['day'] < '2026-04-07']
    b = st_(D, days, f + p); bm = st_(D, mar, fm + pm)
    print(f"BASE (live system): {b['d']:+.3f}%/day H1 {b['h1']:+.3f} H2 {b['h2']:+.3f} ret {b['ret']:+.1f}% DD {b['dd']:.1f}% trades {b['n']} on {b['tdays']} of {len(days)} days; "
          f"March window {bm['d']:+.3f}%/day, {bm['n']} trades\n")
    print("== FADE: add one proxy (deltas vs base in brackets) ==")
    fres = {}
    for q in FADE_CAND:
        if q not in D.bars: print(q, 'no data'); continue
        c = fadec(D, days, q); s = st_(D, days, f + p + c); sm = st_(D, mar, fm + pm + [x for x in c if x['day'] < '2026-04-07'])
        dv = (EX.dollar_vol(D, FA.ROWS[q][0], days), EX.dollar_vol(D, FA.ROWS[q][2], days))
        fres[q] = (s, sm, c)
        row(q, s, b, f"| alone: {len(c)} trades | Mar {sm['d']-bm['d']:+.3f} | $vol legs {dv[0]/1e3:,.0f}k/{dv[1]/1e3:,.0f}k")
    print("\n== PULLBACK: add one leveraged/inverse ticker ==")
    pres = {}
    for q in PB_CAND:
        if q not in D.bars: continue
        c = pbc(D, days, [q])
        if not c: print(f"{q:<18}no qualifying setups"); continue
        s = st_(D, days, f + p + c); sm = st_(D, mar, fm + pm + [x for x in c if x['day'] < '2026-04-07'])
        dvv = EX.dollar_vol(D, q, days); alone = st_(D, days, c)
        w = sum(1 for x in c if x['pct'] > 0)
        pres[q] = (s, sm, c, dvv, alone)
        row(q, s, b, f"| alone {len(c)} setups win {100*w/len(c):.0f}% {alone['d']:+.3f}%/day | Mar {sm['d']-bm['d']:+.3f} | $vol {dvv/1e3:,.0f}k{' THIN' if dvv < EX.LIQ else ''}")
    ok = [q for q, (s, sm, c, dvv, al) in pres.items() if dvv >= EX.LIQ and s['h1'] > b['h1'] and s['h2'] > b['h2'] and sm['d'] >= bm['d']]
    rank = sorted(ok, key=lambda q: -(pres[q][0]['d'] - b['d']))
    print(f"\nPassing all screens (liquid, helps both halves, not worse in March window): {rank}")
    top = rank[:5]
    if top:
        c = pbc(D, days, top); cm = [x for x in c if x['day'] < '2026-04-07']
        print(f"\n== Top {len(top)} PULLBACK adds together: {top} ==")
        row('PB +top', st_(D, days, f + p + c), b, f"| Mar {st_(D, mar, fm + pm + cm)['d']-bm['d']:+.3f}")
    fok = [q for q, (s, sm, c) in fres.items() if s['h1'] > b['h1'] and s['h2'] > b['h2'] and sm['d'] >= bm['d']]
    print(f"\nFADE proxies passing screens: {fok}")
    allf = [x for q in fok for x in fres[q][2]]
    allp = pbc(D, days, top) if top else []
    if fok or top:
        print("\n== Combined universe (passing FADE adds + top PB adds) ==")
        cs = f + p + allf + allp; cm_ = [x for x in cs if x['day'] < '2026-04-07']
        row('combined', st_(D, days, cs), b, f"| Mar {st_(D, mar, cm_)['d']-bm['d']:+.3f}")


if __name__ == '__main__':
    main()
