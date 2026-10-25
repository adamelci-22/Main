#!/usr/bin/env python3
"""What raises the FADE win rate toward 60%, and what does it cost? Real-leg FADE signals (massive_realleg.real_trade geometry), exit parameters varied.
    /usr/bin/python3 -I tools/backtest/massive_winrate.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_winrate.txt
Variables: stop = s x the live stop distance; target = t x R (R = the live stop distance, so t=2 is the live target); fraction sold at the target (1/3 live, or all);
any runner keeps the live rule (breakeven, then the converted 2-ATR chandelier). Win = trade net P&L above zero after 0.06% cost.
E(R) = average result in units of the risk actually taken (pct / stop distance), which is what 3% risk sizing compounds.
Periods: A = 2021-11..2026-02-27, B = 2026-03-03..10-14.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import manual as m, retest as RT, fade_combo as FC
from lab import get_data
fl = RL.fl; LAST = 47; COST = 0.06


def trade(D, d, p, row, s_mult, t_mult, frac):
    P = D.bars[p][d]; su = RT.setup(P, FC.FADE)
    if not su or su[0] >= LAST: return None
    k, side, e_real, stop_real = su
    bull, lb, bear, lbe = row; leg, lev = (bull, lb) if side > 0 else (bear, lbe)
    L = D.bars.get(leg, {}).get(d)
    if not L: return None
    b, p0 = (P, None) if side > 0 else m.mirror(P)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry_m, stop_m = to_m(e_real), to_m(stop_real)
    if entry_m <= stop_m: return None
    rp = (entry_m - stop_m) / e_real
    F = L[k][0]; stop = fl(F * (1 - s_mult * lev * rp)); target = fl(F * (1 + t_mult * lev * rp))
    if stop >= F or target <= F: return None
    rem = 1.0; hit = False; got = 0.0; hic = entry_m; tp = None; xb = LAST
    for j in range(k, LAST + 1):
        o, h, l, c, v = L[j]
        if l <= stop: got += rem * (min(stop, o) / F - 1); rem = 0; xb = j; break
        if not hit and h >= target:
            got += frac * (max(target, o) / F - 1); rem -= frac; hit = True; tp = j
            if rem <= 1e-9: rem = 0; xb = j; break
        hic = max(hic, b[j][3])
        if hit and j < LAST:
            new = fl(max(F, RL.to_leg(c, P[j][3], to_m(hic - 2 * m.atr(b, j)), side, lev)))
            if j == tp: stop = max(stop, new, F)
            elif new >= stop * 1.001: stop = new
            if stop >= c: got += rem * (c / F - 1); rem = 0; xb = j; break
    if rem > 0: got += rem * (L[LAST][3] / F - 1)
    pct = got * 100 - COST; risk = s_mult * lev * rp * 100
    return dict(day=d, sys='FADE', name=p + ('+' if side > 0 else '-'), proxy=p, k=k, xbar=xb, pct=pct, risk=risk, R=pct / risk)


def main():
    D = get_data(); days = D.days[1:]; rows = {p: RL.FA.ROWS[p] for p in RL.LR.BT.PROXIES}
    print(f"{'stop x':>7}{'target':>8}{'sold at target':>15} | {'A win%':>7}{'A avg %':>9}{'A E(R)':>8} | {'B win%':>7}{'B avg %':>9}{'B E(R)':>8} | breakeven win% (A, from payoff)")
    for s_mult in (1.0, 1.5, 2.0):
        for t_mult, frac in ((0.5, 1.0), (1.0, 1.0), (1.0, 1 / 3), (1.5, 1.0), (2.0, 1 / 3), (2.0, 1.0), (3.0, 1.0)):
            T = [x for p in RL.LR.BT.PROXIES for d in days for x in [trade(D, d, p, rows[p], s_mult, t_mult, frac)] if x]
            out = []
            for sel in (lambda x: x['day'] <= '2026-02-27', lambda x: '2026-03-03' <= x['day'] <= '2026-10-14'):
                v = [x for x in T if sel(x)]; out.append((100 * sum(x['pct'] > 0 for x in v) / len(v), st.mean(x['pct'] for x in v), st.mean(x['R'] for x in v), v))
            va = out[0][3]; w = [x['pct'] for x in va if x['pct'] > 0]; l = [-x['pct'] for x in va if x['pct'] <= 0]
            be = 100 * st.mean(l) / (st.mean(w) + st.mean(l)) if w and l else float('nan')
            tag = ' <- live' if (s_mult, t_mult, frac) == (1.0, 2.0, 1 / 3) else ''
            print(f"{s_mult:>7.1f}{t_mult:>7.1f}R{('1/3' if frac < 1 else 'all'):>15} | {out[0][0]:>6.0f}%{out[0][1]:>+9.3f}{out[0][2]:>+8.3f} | {out[1][0]:>6.0f}%{out[1][1]:>+9.3f}{out[1][2]:>+8.3f} | {be:>5.0f}%{tag}")

    print("\n== Account level: %/day at 3% risk (live sizing, cash cap, one position, 6 entries a day, A1 gates, no extra cost), FADE with PULLBACK unchanged ==")
    import final_system as FS
    f_sig, p_sig = FS.cands(D, days)
    PB = [dict(c, px=None) for c in p_sig]
    wins = (('A  2021-11..2026-02', [d for d in days if d <= '2026-02-27']), ('B  2026-03..10', [d for d in days if '2026-03-03' <= d <= '2026-10-14']))
    print(f"{'stop x':>7}{'target':>8}{'sold':>6}{'risk':>6} | " + ' | '.join(f"{w[0]:<30}" for w in wins))
    for s_mult, t_mult, frac, risk in ((1.0, 2.0, 1 / 3, 0.03), (1.5, 1.0, 1.0, 0.03), (1.5, 2.0, 1 / 3, 0.03), (2.0, 1.0, 1.0, 0.03), (2.0, 2.0, 1 / 3, 0.03), (2.0, 2.0, 1 / 3, 0.06), (1.0, 2.0, 1 / 3, 0.06)):
        T = [x for p in RL.LR.BT.PROXIES for d in days for x in [trade(D, d, p, rows[p], s_mult, t_mult, frac)] if x]
        cs = [dict(c, px=RL.LR.leg_px(D, c)) for c in T] + [dict(c, px=RL.LR.leg_px(D, c)) for c in p_sig]
        row = []
        for _, ds in wins:
            S = set(ds); a = RL.LR.live_account(D, ds, [c for c in cs if c['day'] in S], risk=risk, gates=False, whole=False, max_entries=6)
            row.append(f"{st.mean(a['daily'].values()):+.3f}%/day ret {a['ret']:+7.0f}% DD {a['mdd']:>4.0f}%")
        print(f"{s_mult:>7.1f}{t_mult:>7.1f}R{('1/3' if frac < 1 else 'all'):>6}{risk*100:>5.0f}% | " + ' | '.join(f"{r:<30}" for r in row))


if __name__ == '__main__':
    main()
