#!/usr/bin/env python3
"""FADE with more filters, fewer trades, bigger payout: a disciplined search on real-leg FADE trades, Massive bars.
    /usr/bin/python3 -I tools/backtest/massive_fade_filters.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_fade_filters.txt
Candidate filters: 17 features known at entry, each cut at TRAIN terciles (and the two categorical ones), single filters and pairs of different features.
SELECT on TRAIN (2021-11..2023-12) and VALID (2024-01..2025-12) only: a filter must average above zero in both, with at least 40 TRAIN and 30 VALID trades. Rank by the weaker of the two.
TEST (2026-03-03..10-14) is looked at once, after the choice. NULL: the same search on shuffled trade results (200 shuffles) shows how good a filter pure chance finds.
Then the payout side: for the chosen filter, stop x target x fraction variants (massive_winrate.trade).
"""
import itertools, os, statistics as st, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import massive_winrate as WR
import manual as m, twobar as TB
from lab import get_data
LR = RL.LR; PROXIES = LR.BT.PROXIES
TR, VA, TE = ('2021-11-01', '2023-12-31'), ('2024-01-01', '2025-12-31'), ('2026-03-03', '2026-10-14')
inP = lambda d, P: P[0] <= d <= P[1]


def features(D, trades):
    setups = {}
    for t in trades: setups.setdefault(t['day'], []).append(t['side'])
    out = []
    for t in trades:
        d, p, k, side = t['day'], t['proxy'], t['k'], t['side']; P = D.bars[p][d]; i = D.days.index(d); pri = D.days[i - 1]
        H, L = TB.box(P); bj = next(j for j in range(6, 9) if P[j][3] > H or P[j][3] < L); bside = 1 if P[bj][3] > H else -1
        adr = st.mean((D.dhlc[p][x][0] - D.dhlc[p][x][1]) / D.dhlc[p][x][2] for x in D.prior(d, 20))
        adr100 = st.mean((D.dhlc[p][x][0] - D.dhlc[p][x][1]) / D.dhlc[p][x][2] for x in D.prior(d, 100)) if i >= 100 else adr
        pdh, pdl, pdc = D.dhlc[p][pri]; v0 = st.mean(x[4] for x in P[:6]) or 1
        E = H if bside > 0 else L; ext = pdh if bside > 0 else pdl
        i_r = k - 1; rb = P[i_r]; rng = (rb[1] - rb[2]) or 1e-9
        rej = (rb[1] - rb[3]) / rng if bside > 0 else (rb[3] - rb[2]) / rng          # how far the retest bar closed off the edge, 0..1
        sweep = max(x[1] for x in P[bj:i_r + 1]) if bside > 0 else min(x[2] for x in P[bj:i_r + 1])
        cum = D.cum[p][d][k] / st.mean(D.cum[p][x][k] for x in D.prior(d, 20))
        pc = pdc; tr10 = pc / st.mean(D.dhlc[p][x][2] for x in D.prior(d, 11)[:10]) - 1
        ppc = D.dhlc[p][D.days[i - 2]][2]
        out.append(dict(
            leg=0 if side > 0 else 1, bj=bj, kk=k, box=(H - L) / P[0][0] / adr, gap=(P[0][0] / pdc - 1) * bside * 100, trend=side * tr10 * 100,
            rp=(t['risk'] / RL.FA.ROWS[p][1]) / 100 / adr, atr=m.atr(P, k - 1) / P[k][0] / adr, breadth=sum(1 for s in setups[d] if s == side) - 1,
            vbrk=P[bj][4] / v0, vret=rb[4] / v0, rej=rej, pdext=(E - ext) / P[0][0] / adr * bside, sweep=((sweep - ext) / P[0][0] / adr) * bside,
            pdret=side * (pdc / ppc - 1) * 100, openloc=(P[0][0] - pdl) / ((pdh - pdl) or 1e-9), rvol=cum, volreg=adr / adr100))
    return out


def conds(F, tr_idx):
    names = list(F[0].keys()); C = []
    for n in names:
        v = np.array([f[n] for f in F], dtype=float)
        if n == 'leg': C += [(f'{n}=bull', v == 0), (f'{n}=inverse', v == 1)]; continue
        if n == 'bj': C += [(f'{n}={j}', v == j) for j in (6, 7, 8)]; continue
        if n == 'breadth': C += [(f'{n}=0', v == 0), (f'{n}>=1', v >= 1)]; continue
        c1, c2 = np.quantile(v[tr_idx], [1 / 3, 2 / 3])
        C += [(f'{n}<{c1:.2f}', v < c1), (f'{n}<{c2:.2f}', v < c2), (f'{n}>={c1:.2f}', v >= c1), (f'{n}>={c2:.2f}', v >= c2)]
    return C


def search(pct, masks, names, itr, iva, minw=(40, 30)):
    keys = [n.split('<')[0].split('>')[0].split('=')[0] for n in names]; res = []
    combos = [(a,) for a in range(len(names))] + [(a, b) for a in range(len(names)) for b in range(a + 1, len(names)) if keys[a] != keys[b]]
    for c in combos:
        mk = masks[c[0]] if len(c) == 1 else masks[c[0]] & masks[c[1]]
        a = mk & itr; b = mk & iva
        if a.sum() < minw[0] or b.sum() < minw[1]: continue
        ma, mb = pct[a].mean(), pct[b].mean()
        if ma > 0 and mb > 0: res.append((min(ma, mb), ma, mb, c))
    return sorted(res, reverse=True)


def main():
    D = get_data(); days = D.days[1:]; rows = {p: RL.FA.ROWS[p] for p in PROXIES}
    trades = [t for p in PROXIES for d in days for t in [RL.real_trade(D, d, p, rows[p])] if t and d >= days[0]]
    trades = [t for t in trades if D.days.index(t['day']) >= 101]       # needs 100 prior days for the volatility-regime feature
    F = features(D, trades); pct = np.array([t['pct'] for t in trades]); day = [t['day'] for t in trades]
    itr = np.array([inP(d, TR) for d in day]); iva = np.array([inP(d, VA) for d in day]); ite = np.array([inP(d, TE) for d in day])
    print(f"{len(trades)} real-leg FADE trades (first 100 days dropped for the features): TRAIN {itr.sum()}, VALID {iva.sum()}, TEST {ite.sum()}.  All trades: TRAIN {pct[itr].mean():+.3f}  VALID {pct[iva].mean():+.3f}  TEST {pct[ite].mean():+.3f}\n")
    C = conds(F, itr); names = [n for n, _ in C]; masks = [m_ for _, m_ in C]
    res = search(pct, masks, names, itr, iva)
    print(f"{len(names)} conditions, {len(res)} single or pair filters positive in both TRAIN and VALID.\n")
    print(f"{'filter (chosen on TRAIN+VALID)':<62}{'TRAIN':>16}{'VALID':>16}{'TEST (once)':>22}")
    def line(c):
        mk = masks[c[0]] if len(c) == 1 else masks[c[0]] & masks[c[1]]
        f = lambda s: f"{pct[mk & s].mean():+.3f} ({(mk & s).sum():>3})" if (mk & s).sum() else 'n/a'
        w = lambda s: 100 * (pct[mk & s] > 0).mean() if (mk & s).sum() else 0
        return f"{' AND '.join(names[i] for i in c):<62}{f(itr):>16}{f(iva):>16}{f(ite):>16} win {w(ite):>3.0f}%"
    for r in res[:12]: print(line(r[3]))
    # null: shuffle results
    rng = np.random.default_rng(7); best = []
    for _ in range(200):
        sp = rng.permutation(pct); rr = search(sp, masks, names, itr, iva); best.append(rr[0][0] if rr else 0.0)
    best = np.array(best); real = res[0][0] if res else 0.0
    print(f"\nNULL (same search on 200 shuffles of the results): best weaker-period average found by chance: median {np.median(best):+.3f}, 90th percentile {np.quantile(best, .9):+.3f}, max {best.max():+.3f}.  Real best: {real:+.3f}.  Share of shuffles that beat the real best: {100*(best >= real).mean():.0f}%")
    # how many filters would chance give that pass both periods
    cnt = []
    for _ in range(50):
        sp = rng.permutation(pct); cnt.append(len(search(sp, masks, names, itr, iva)))
    print(f"Filters positive in both periods: real {len(res)}; shuffled results {np.median(cnt):.0f} on median (range {min(cnt)} to {max(cnt)}).")
    j = names.index(next(n for n in names if n.startswith('vbrk<0.6')))
    print(f"\nPOST-HOC (named after the search, so treat as a hypothesis): the one filter that appears in five of the top twelve, {names[j]}: a weak-volume breakout is more likely to fail.")
    for nm, s_ in (('TRAIN', itr), ('VALID', iva), ('TEST', ite), ('first 6 months of TEST', ite & np.array([d <= '2026-08-31' for d in day]))):
        k_ = masks[j] & s_; o_ = (~masks[j]) & s_
        print(f"   {nm:<24} kept {pct[k_].mean():+.3f}% win {100*(pct[k_]>0).mean():.0f}% n={k_.sum():>3}   dropped {pct[o_].mean():+.3f}% win {100*(pct[o_]>0).mean():.0f}% n={o_.sum():>3}")
    if not res: return
    c = res[0][3]; mk = masks[c[0]] if len(c) == 1 else masks[c[0]] & masks[c[1]]
    keep = {(trades[i]['day'], trades[i]['proxy']) for i in np.where(mk)[0]}
    print(f"\n== Payout variants on the top filter ({' AND '.join(names[i] for i in c)}); kept {mk.sum()} of {len(mk)} trades ({100*mk.mean():.0f}%) ==")
    print(f"{'stop x':>7}{'target':>8}{'sold':>6} | {'TRAIN avg':>10}{'win':>5}{'E(R)':>7} | {'VALID avg':>10}{'win':>5}{'E(R)':>7} | {'TEST avg':>9}{'win':>5}{'E(R)':>7}")
    for s_mult, t_mult, frac in ((1.0, 2.0, 1 / 3), (1.0, 3.0, 1 / 3), (1.0, 3.0, 1.0), (1.0, 4.0, 1.0), (1.5, 3.0, 1 / 3), (1.5, 2.0, 1 / 3), (2.0, 2.0, 1 / 3), (2.0, 3.0, 1 / 3)):
        T = [x for p in PROXIES for d in days for x in [WR.trade(D, d, p, rows[p], s_mult, t_mult, frac)] if x and (d, p) in keep]
        cells = []
        for P in (TR, VA, TE):
            v = [x for x in T if inP(x['day'], P)]
            cells.append(f"{st.mean(x['pct'] for x in v):>+10.3f}{100*sum(x['pct'] > 0 for x in v)/len(v):>4.0f}%{st.mean(x['R'] for x in v):>+7.3f}" if v else f"{'n/a':>22}")
        print(f"{s_mult:>7.1f}{t_mult:>7.1f}R{('1/3' if frac < 1 else 'all'):>6} | " + ' | '.join(cells))


if __name__ == '__main__':
    main()
