#!/usr/bin/env python3
"""FADE simulated on the REAL leveraged-leg bars, following RULEBOOK B2/B5.2/B5.4 order by order, then the full system with the live account rules.
    /usr/bin/python3 -I tools/backtest/massive_realleg.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_realleg.txt
Signal: the proxy's failed retest (retest.setup, as paper.py). Entry: the leg's open of the bar after the retest bar.
Leg levels from the fill F (B5.2): stop = F x (1 - lev x R%), target = F x (1 + 2 x lev x R%), both rounded down to the cent, R% = proxy distance entry to stop.
The stop and the 2R target are judged on the LEG's own bars (a stop-market and an OCO on the leg), not on the proxy.
After the 1/3 target fills (B5.4): the 2/3 stop moves to the fill F, raised at each later bar close to the proxy's 2-ATR chandelier converted to the leg (paper.py to_leg),
only if it is at least 0.10% above the current stop and never below F. A stop that would sit at or above the leg's last close sells the runner at that close.
Stops fill at the stop or the bar open on a gap. Anything left sells at the 13:30 bar close. Cost 0.06% round trip on the leg (the signal model's), plus the scenarios below.
"""
import collections, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_live_rules as LR
import manual as m, retest as RT, fade_combo as FC, fade_addone as FA, expand_lists as EX, mixed as MXD, pb_final as PBF
from lab import get_data
import final_system as FS

LAST = 47; FRAC = 1 / 3; COST = 0.06
fl = lambda x: math.floor(x * 100 + 1e-9) / 100


def to_leg(leg_now, proxy_now, level, side, lev):
    return leg_now * (1 + lev * side * (level / proxy_now - 1))


def real_trade(D, d, p, row):
    P = D.bars[p][d]; s = RT.setup(P, FC.FADE)
    if not s or s[0] >= LAST: return None
    k, side, e_real, stop_real = s
    bull, lb, bear, lbe = row; leg, lev = (bull, lb) if side > 0 else (bear, lbe)
    L = D.bars.get(leg, {}).get(d)
    if not L: return None
    b, p0 = (P, None) if side > 0 else m.mirror(P)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry_m, stop_m = to_m(e_real), to_m(stop_real)
    if entry_m <= stop_m: return None
    rp = (entry_m - stop_m) / e_real
    F = L[k][0]; stop = fl(F * (1 - lev * rp)); target = fl(F * (1 + 2 * lev * rp))
    if stop >= F or target <= F: return None
    rem = 1.0; hit = False; hic = entry_m; got = 0.0; why = 'time'; xbar = LAST; tp_bar = None
    for j in range(k, LAST + 1):
        o, h, l, c, v = L[j]
        if l <= stop:
            px = min(stop, o); got += rem * (px / F - 1); rem = 0; why = 'stop' if not hit else 'runner_stop'; xbar = j; break
        if not hit and h >= target:
            px = max(target, o); got += FRAC * (px / F - 1); rem -= FRAC; hit = True; tp_bar = j
        hic = max(hic, b[j][3])
        if hit and j < LAST:
            chand_m = hic - 2 * m.atr(b, j)
            new = fl(max(F, to_leg(c, P[j][3], to_m(chand_m), side, lev)))
            if j == tp_bar: stop = max(stop, new, F)
            elif new >= stop * 1.001: stop = new
            if stop >= c: got += rem * (c / F - 1); rem = 0; why = 'runner_sold'; xbar = j; break
    if rem > 0: got += rem * (L[LAST][3] / F - 1)
    return dict(day=d, sys='FADE', name=p + ('+' if side > 0 else '-'), proxy=p, side=side, k=k, xbar=xbar, why=why, hit=hit, leg=leg, F=F,
                pct=got * 100 - COST, risk=lev * rp * 100)


def main():
    D = get_data(); LR.m.rvol = PBF.rvol(D); days = D.days[1:]
    live_rows = {p: FA.ROWS[p] for p in LR.BT.PROXIES}
    real = []; model = {}
    for p in LR.BT.PROXIES:
        for t in EX.fade_trades(D, days, p, live_rows[p]): model[(t['day'], p)] = t
        for d in days:
            t = real_trade(D, d, p, live_rows[p])
            if t: real.append(t)
    print(f"Real-leg FADE: {len(real)} trades; signal-model FADE: {len(model)} trades; {days[0]}..{days[-1]}\n")
    print("== 1. Real legs against the leverage model, same signals (leg % per trade) ==")
    print(f"{'period':<18}{'n':>5}{'model avg':>10}{'real avg':>10}{'diff':>8}{'model win':>10}{'real win':>9}{'corr':>7}{'|diff|>1% share':>16}")
    for lab, a_, b_ in (('2021-11..2022', '2021-11-01', '2022-12-31'), ('2023', '2023-01-01', '2023-12-31'), ('2024', '2024-01-01', '2024-12-31'), ('2025', '2025-01-01', '2025-12-31'),
                        ('2026-01..02', '2026-01-01', '2026-02-27'), ('2026-03..10', '2026-03-03', '2026-10-14')):
        pr = [(model[(t['day'], t['proxy'])]['pct'], t['pct']) for t in real if a_ <= t['day'] <= b_ and (t['day'], t['proxy']) in model]
        if len(pr) < 3: continue
        x = [a for a, _ in pr]; y = [b_ for _, b_ in pr]
        cor = st.correlation(x, y) if len(set(x)) > 1 and len(set(y)) > 1 else float('nan')
        print(f"{lab:<18}{len(pr):>5}{st.mean(x):>+10.3f}{st.mean(y):>+10.3f}{st.mean(y)-st.mean(x):>+8.3f}{100*sum(v>0 for v in x)/len(x):>9.0f}%{100*sum(v>0 for v in y)/len(y):>8.0f}%{cor:>7.2f}{100*sum(abs(a-b_)>1 for a, b_ in pr)/len(pr):>15.0f}%")
    print("\n== 2. Real-leg FADE by proxy, before / after 2026-03-03 (leg % per trade) ==")
    for p in LR.BT.PROXIES:
        a = [t['pct'] for t in real if t['proxy'] == p and t['day'] <= '2026-02-27']; b_ = [t['pct'] for t in real if t['proxy'] == p and '2026-03-03' <= t['day'] <= '2026-10-14']
        print(f"   {p:<5} A n={len(a):>3} win {100*sum(v>0 for v in a)/len(a):>3.0f}% avg {st.mean(a):+.3f}%   B n={len(b_):>3} win {100*sum(v>0 for v in b_)/max(len(b_),1):>3.0f}% avg {st.mean(b_) if b_ else 0:+.3f}%")
    pbf, pbp = FS.cands(D, days)[0], None
    f_model, p_sig = FS.cands(D, days)
    cs_real = [dict(c, px=LR.leg_px(D, c)) for c in real + p_sig]
    cs_model = [dict(c, px=LR.leg_px(D, c)) for c in f_model + p_sig]
    win = [('ALL 2021-11..2026-10', days), ('BEFORE 2026-03-03', [d for d in days if d <= '2026-02-27']), ('RULES WINDOW 2026-03-03..10-14', [d for d in days if '2026-03-03' <= d <= '2026-10-14'])]
    print("\n== 3. Full system, live account rules (whole shares, 5-loss, 3% day, 6/day, 50% floor), cost +0.00% / +0.10% ==")
    for wn, ds in win:
        S = set(ds); print(f"-- {wn}")
        for nm, cs in (('signal model legs', cs_model), ('REAL legs', cs_real)):
            for extra in (0.0, 0.10):
                a = LR.live_account(D, ds, [c for c in cs if c['day'] in S], extra_rt=extra); print(LR.line(f'{nm} +{extra:.2f}%', ds, a))
        a = LR.live_account(D, ds, [c for c in cs_real if c['day'] in S and c['sys'] == 'FADE'], extra_rt=0.0); print(LR.line('REAL legs FADE only +0.00%', ds, a))
    print("\n== 4. By calendar year, REAL legs, live rules, +0.10%, each year restarted at $2,000 ==")
    for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
        ds = [d for d in days if d.startswith(y)]; S = set(ds)
        print(LR.line(f'{y} FADE+PB', ds, LR.live_account(D, ds, [c for c in cs_real if c['day'] in S], extra_rt=0.10)))
    print("\n== 5. Exit mix, REAL legs ==")
    for lab, a_, b_ in (('before 2026-03', '2021-11-01', '2026-02-27'), ('2026-03..10', '2026-03-03', '2026-10-14')):
        T = [t for t in real if a_ <= t['day'] <= b_]; c = collections.Counter(t['why'] for t in T)
        print(f"   {lab}: n={len(T)} " + ', '.join(f"{k} {100*v/len(T):.0f}%" for k, v in c.most_common()) + f", 2R filled {100*sum(t['hit'] for t in T)/len(T):.0f}%")


if __name__ == '__main__':
    main()
