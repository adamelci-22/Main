#!/usr/bin/env python3
"""Regime switch between the live book (FADE v5.2.45 + PULLBACK runner v5.2.46) and first-hour momentum (HOUR1: QQQ SOXX IWM XLK XBI XLF
SPY, 9:30-10:30 move >= 0.5% -> 3x leg with it at 10:30, stop at the open, out 13:30). Governor 2026-11-12: "build this system, it can be
based on prior day close or old info". Each morning a regime feature known BEFORE the trading window picks the system for the day.
Features (QQQ unless noted): prior-day return, 5- and 20-day return, 20-day average daily range, 5/20 range ratio, prior-day intraday
efficiency ratio, first-hour continuation rate over the last 10 and 20 days (share of days the 9:30-10:30 direction held to 13:30),
trailing 20-day paper result of HOUR1 minus the book, today's opening gap, UVXY 5-day change. Rule = feature in a tercile band ->
momentum day, else book day; band chosen on MASSIVE H1 only, judged on MASSIVE H2 and Robinhood 2026. Also pairs of features (AND).
    python3 -I tools/backtest/regime_switch.py > tools/backtest/results/regime_switch_2026-11-12.txt"""
import itertools, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS, other_systems as OS


def curve(d):
    eq = pk = 1.0; mdd = 0.0
    for x in d: eq *= 1 + x / 100; pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100)
    return (eq - 1) * 100, mdd


def feats(ds, days, hdaily, bdaily):
    q = ds.bars['QQQ']; allds = ds.days; out = {}
    cont = {}
    for d in allds:
        b = q.get(d)
        if not b: continue
        fh = b[11][3] - b[0][0]; rest = b[47][3] - b[11][3]; cont[d] = 1.0 if fh * rest > 0 else 0.0
    for d in days:
        i = ds.idx[d]
        if i < 22: continue
        prev = [x for x in allds[i - 21:i] if x in q]
        if len(prev) < 21: continue
        cl = [q[x][-1][3] for x in prev]; rng = [(max(y[1] for y in q[x]) / min(y[2] for y in q[x]) - 1) * 100 for x in prev]
        pb = q[prev[-1]]; cs = [y[3] for y in pb]; dd_ = sum(abs(cs[k] - cs[k - 1]) for k in range(1, len(cs)))
        u = ds.bars.get('UVXY', {}); uv = [u[x][-1][3] for x in prev[-6:] if x in u]
        hi = [hdaily.get(x, 0.0) for x in prev[-20:]]; bi = [bdaily.get(x, 0.0) for x in prev[-20:]]
        out[d] = {'prior-day return %': (cl[-1] / cl[-2] - 1) * 100, '5-day return %': (cl[-1] / cl[-6] - 1) * 100,
                  '20-day return %': (cl[-1] / cl[0] - 1) * 100, '|5-day return| %': abs(cl[-1] / cl[-6] - 1) * 100,
                  '20-day avg range %': st.mean(rng[-20:]), 'range 5/20 ratio': st.mean(rng[-5:]) / st.mean(rng[-20:]),
                  'prior-day efficiency': abs(cs[-1] - cs[0]) / dd_ if dd_ else 0.0,
                  'first-hour continuation 10d': st.mean(cont.get(x, 0.5) for x in prev[-10:]),
                  'first-hour continuation 20d': st.mean(cont.get(x, 0.5) for x in prev[-20:]),
                  'HOUR1 minus book, 20d %': sum(hi) - sum(bi),
                  'gap today %': abs(q[d][0][0] / cl[-1] - 1) * 100,
                  'UVXY 5-day change %': (uv[-1] / uv[0] - 1) * 100 if len(uv) == 6 else 0.0}
    return out


def main():
    FB = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); RUN = dict(frac=1 / 3, run=('ema', 20))
    ds_rh = F.DS(None, OS.PX); cx_rh = F.context(ds_rh, OS.PX); dm = F.DS(OS.AE.M5, OS.PX + ['UVXY']); cm = F.context(dm, OS.PX)
    H = [(ds_rh, cx_rh), (dm, cm), (dm, cm)]
    D = []
    for b in range(3):
        days = PB[b].days
        bk = F.account(PB[b].ds, days, [FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, RUN) for t in PB[b].E])['daily']
        d_, c_ = H[b]
        hT = [x for p in OS.PX if p in d_.bars for d in days if d in d_.bars[p] for x in [OS.hour1(d_, c_, p, d, d_.bars[p][d], xm=0.5)] if x]
        hm = F.account(d_, days, hT)['daily']
        fx = feats(PB[b].ds if b == 0 else dm, days, hm, bk)
        dd = [d for d in days if d in fx]
        D.append(dict(days=dd, B=np.array([bk.get(d, 0.0) for d in dd]), M=np.array([hm.get(d, 0.0) for d in dd]), X=[fx[d] for d in dd]))
    names = ['RH 2026', 'M H1 21-24', 'M H2 24-26']
    print(__doc__.split('\n')[0])
    for nm, x in zip(names, D):
        tb, mb = curve(x['B']); tm, mm = curve(x['M']); print(f"  {nm}: {len(x['days'])} days | book {tb:+.1f}% DD {mb:.1f}% | HOUR1 {tm:+.1f}% DD {mm:.1f}%")
    feat_names = list(D[1]['X'][0])
    def apply(x, mask): return np.where(mask, x['M'], x['B'])
    def masks(f, lo_hi, x, cuts): v = np.array([r[f] for r in x['X']]); band = np.where(v < cuts[0], 0, np.where(v >= cuts[1], 2, 1)); return np.isin(band, lo_hi)
    singles = []
    for f in feat_names:
        v1 = np.array([r[f] for r in D[1]['X']]); cuts = np.percentile(v1, [33.3, 66.7])
        best = None
        for ks in [(0,), (1,), (2,), (0, 1), (1, 2), (0, 2)]:
            t1, _ = curve(apply(D[1], masks(f, ks, D[1], cuts)))
            if best is None or t1 > best[0]: best = (t1, ks)
        ks = best[1]; res = [curve(apply(x, masks(f, ks, x, cuts))) + (masks(f, ks, x, cuts).mean() * 100,) for x in D]
        singles.append((f, ks, cuts, res))
    base = [curve(x['B']) for x in D]
    print('\nA. One feature: momentum day when the feature is in the H1-chosen band (else the live book). total % (change vs book) DD, share of momentum days')
    rows = []
    for f, ks, cuts, res in singles:
        ok = all(res[b][0] > base[b][0] for b in (0, 2)); rows.append((ok, res[0][0] - base[0][0] + res[2][0] - base[2][0], f, ks, cuts, res))
    rows.sort(key=lambda z: (-z[0], -z[1]))
    for ok, sc, f, ks, cuts, res in rows:
        band = '/'.join(['low', 'mid', 'high'][k] for k in ks)
        print(f"  {'PASS ' if ok else '     '}{f + ' ' + band + f' (cuts {cuts[0]:.3g}/{cuts[1]:.3g})':<62} " + ' | '.join(f"{n} {r[0]:+7.1f}% ({r[0] - b0[0]:+6.1f}) DD{r[1]:5.1f} mom{r[2]:3.0f}%" for n, r, b0 in zip(names, res, base)))
    print('\nB. Two features (both in their H1 bands -> momentum day): top 10 by the weaker out-of-sample change')
    pairs = []
    for (f1, k1, c1, _), (f2, k2, c2, _) in itertools.combinations(singles, 2):
        res = [curve(apply(x, masks(f1, k1, x, c1) & masks(f2, k2, x, c2))) + ((masks(f1, k1, x, c1) & masks(f2, k2, x, c2)).mean() * 100,) for x in D]
        if res[1][0] <= base[1][0]: continue
        pairs.append((min(res[0][0] - base[0][0], res[2][0] - base[2][0]), f1, f2, res))
    pairs.sort(key=lambda z: -z[0])
    for sc, f1, f2, res in pairs[:10]:
        print(f"  {'PASS ' if sc > 0 else '     '}{f1 + ' AND ' + f2:<62} " + ' | '.join(f"{n} {r[0]:+7.1f}% ({r[0] - b0[0]:+6.1f}) DD{r[1]:5.1f} mom{r[2]:3.0f}%" for n, r, b0 in zip(names, res, base)))
    print(f"  pairs better on H1: {len(pairs)}, also better on RH and M H2: {sum(p[0] > 0 for p in pairs)}")


if __name__ == '__main__':
    main()
