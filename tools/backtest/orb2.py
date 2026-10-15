#!/usr/bin/env python3
"""Proxy-driven 2-Bar Compressed ORB and 15-min ORB on the v3.126 Core Five, as recommended by an outside AI write-up.
    python3 tools/backtest/orb2.py > tools/backtest/results_orb2.txt
Signal and stop/target on the PROXY chart (QQQ, SOXX, IWM, XLK, IBIT); trade the leg (TQQQ/SQQQ, SOXL/SOXS, TNA/TZA, TECL/TECS, BTCL/BTCZ).
Leg return = leverage x proxy return (intraday approximation) minus 0.06% round-trip cost on the leg.
2-bar: box = 9:30-10:00 high/low; buy the leg when the proxy trades through the box during 10:00-10:15 (stop-entry fill at the level or the open);
       a bar that hits both box edges is skipped; stop checked first in the entry bar (conservative).
15-min ORB: box = 9:30-9:45; first 5-min close outside -> entry next open.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m
from lab import get_data

ROWS = {'QQQ': ('TQQQ', 'SQQQ', 3), 'SOXX': ('SOXL', 'SOXS', 3), 'IWM': ('TNA', 'TZA', 3), 'XLK': ('TECL', 'TECS', 3), 'IBIT': ('BTCL', 'BTCZ', 2)}
LEGCOST = 0.0006 * 100   # % round trip on the leg


def two_bar(b, stop_rule):
    bh = max(x[1] for x in b[:6]); bl = min(x[2] for x in b[:6])
    for j in range(6, 9):
        up, dn = b[j][1] >= bh, b[j][2] <= bl
        if up and dn: return None
        if up or dn: return j, (1 if up else -1), bh, bl
    return None


def orb15(b):
    bh = max(x[1] for x in b[:3]); bl = min(x[2] for x in b[:3])
    for j in range(3, 29):
        if b[j][3] > bh: return j, 1, bh, bl
        if b[j][3] < bl: return j, -1, bh, bl
    return None


def make(D, d, p, system, stop_rule, exit_rule):
    raw = D.bars[p][d]
    sig = two_bar(raw, stop_rule) if system == '2bar' else orb15(raw)
    if not sig: return None
    j, side, bh, bl = sig
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    orig = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    # box edges in (possibly mirrored) space
    H = max(x[1] for x in b[:6 if system == '2bar' else 3]); L = min(x[2] for x in b[:6 if system == '2bar' else 3])
    if system == '2bar':
        k = j; entry = max(b[j][0], H); stop_entry = True
    else:
        k = j + 1; entry = b[k][0]; stop_entry = False
    if stop_rule == 'bar2': stop = min(x[2] for x in b[3:6])
    elif stop_rule == 'opp': stop = L
    elif stop_rule == 'mid': stop = (H + L) / 2
    elif stop_rule == 'mid_or_candle': stop = max((H + L) / 2, b[j][2])
    else: stop = entry * (1 - float(stop_rule[3:]) / 100)        # 'pct0.3'
    if entry <= stop: return None
    r = entry - stop
    if exit_rule == 'half1R_be': spec = dict(T=entry + r, frac=0.5, post='be')
    elif exit_rule == 'half_box_ema9': spec = dict(T=entry + (H - L), frac=0.5, post='ema9')
    elif exit_rule.startswith('R'): spec = dict(T=entry + float(exit_rule[1:]) * r, frac=1.0, post=None)
    else: spec = dict(T=None, frac=1.0, post=None)
    spec.update(k=k, entry=entry, stop=stop, stop_entry=stop_entry)
    pd_ = D.days[D.days.index(d) - 1]; prev = D.bars[p][pd_] if side > 0 else m.mirror(D.bars[p][pd_])[0]
    e9 = m.ema([x[3] for x in prev] + [x[3] for x in b], 9)[78:]
    m.LAST = 36 if exit_rule.endswith('1230') or exit_rule == 'eod1230' else 77
    res = m.manage(b, spec, e9, 0.0, orig); m.LAST = 77
    if not res: return None
    pnl, risk, xbar, why = res
    lev = ROWS[p][2]; pe = orig(entry)
    proxy_pct = pnl / pe * 100; risk_pct = risk / pe * 100
    return dict(day=d, proxy=p, leg=ROWS[p][0] if side > 0 else ROWS[p][1], side=side, k=k, xbar=xbar, why=why,
                proxy_pct=proxy_pct, pct=lev * proxy_pct - LEGCOST, risk_leg=lev * risk_pct, proxy_risk=risk_pct)


def account(trades, D, days, mode, risk=0.03, start=2000.0):
    by = collections.defaultdict(list)
    for t in trades: by[t['day']].append(t)
    eq = start; peak = start; mdd = 0; daily = {}; taken = []
    for d in days:
        e0 = eq; ts = sorted(by.get(d, []), key=lambda t: t['k'])
        if mode == 'one':        # one position at a time, highest proxy RVOL among the earliest triggers
            free = 0; n = 0
            while ts and n < 3:
                av = [t for t in ts if t['k'] >= free]
                if not av: break
                k0 = min(t['k'] for t in av); same = [t for t in av if t['k'] == k0]
                t = max(same, key=lambda t: rv(D, t['proxy'], d, t['k']))
                notional = min(eq, eq * risk / (t['risk_leg'] / 100)); pnl = notional * t['pct'] / 100
                eq += pnl; taken.append(dict(t, acct=pnl / (eq - pnl) * 100)); free = t['xbar'] + 1; ts.remove(t); n += 1
        else:                    # every trigger, risk split evenly, cash split evenly
            n = len(ts)
            for t in ts:
                notional = min(eq / n, eq * risk / n / (t['risk_leg'] / 100)); pnl = notional * t['pct'] / 100
                taken.append(dict(t, acct=pnl / eq * 100))
            eq += sum(min(e0 / n, e0 * risk / n / (t['risk_leg'] / 100)) * t['pct'] / 100 for t in ts)
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
        daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken)


def rv(D, p, d, k):
    try:
        pri = D.prior(d, 20); base = st.mean(D.cum[p][x][k] for x in pri); return D.cum[p][d][k] / base
    except Exception: return 0.0


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2
    print(f"Proxy-driven ORB systems on QQQ/SOXX/IWM/XLK/IBIT -> 10 legs, {days[0]}..{days[-1]} ({len(days)} days). Leg cost 0.06% round trip.")
    print("Reference: first-pullback buy on the same list = +0.091%/day, +12.1%, maxDD 6.3% (H1 +0.112, H2 +0.071).\n")
    print(f"{'system':<8}{'stop':<15}{'exit':<15}{'trades':>7}{'win%':>6}{'leg avg%':>9}{'t':>6}{'proxy risk%':>12} || {'one-at-a-time  %/day   ret   maxDD  H1/H2':<44}|| all-triggers %/day  ret  maxDD  H1/H2")
    grid = [('2bar', s, e) for s in ('bar2', 'opp', 'mid', 'pct0.3', 'pct0.4') for e in ('half1R_be', 'R1.5', 'R2.5', 'eod', 'eod1230')] + \
           [('15min', s, e) for s in ('mid_or_candle', 'mid', 'pct0.3') for e in ('half_box_ema9', 'R1.5', 'eod', 'eod1230')]
    best = []
    for sysn, sr, er in grid:
        T = [t for d in days for p in ROWS for t in [make(D, d, p, sysn, sr, er)] if t]
        a = [t['pct'] for t in T]; mu = st.mean(a); tt = mu / (st.pstdev(a) / math.sqrt(len(a)))
        r1 = account(T, D, days, 'one'); r2 = account(T, D, days, 'all')
        f = lambda r: f"{st.mean(r['daily'].values()):>+8.3f}{r['ret']:>+7.1f}{r['mdd']:>7.1f}  {st.mean(r['daily'][d] for d in days[:h]):+.3f}/{st.mean(r['daily'][d] for d in days[h:]):+.3f}"
        print(f"{sysn:<8}{sr:<15}{er:<15}{len(T):>7}{100*sum(x>0 for x in a)/len(a):>6.1f}{mu:>+9.3f}{tt:>6.1f}{st.mean(t['proxy_risk'] for t in T):>12.2f} || {f(r1):<44}|| {f(r2)}")
        best.append((st.mean(r1['daily'].values()), sysn, sr, er, T))
    best.sort(key=lambda x: -x[0])
    print("\nBest one-at-a-time version, by row and side:")
    _, sysn, sr, er, T = best[0]; print(f"  {sysn} stop={sr} exit={er}")
    g = collections.defaultdict(list)
    for t in T: g[(t['proxy'], 'bull' if t['side'] > 0 else 'bear')].append(t)
    for k in sorted(g):
        v = g[k]; print(f"   {k[0]:<5}{k[1]:<5} n={len(v):3d} win={100*sum(x['pct']>0 for x in v)/len(v):3.0f}% leg avg={st.mean(x['pct'] for x in v):+.3f}%")
    # raw follow-through for the 2-bar trigger, unlevered
    print("\nRaw follow-through after the 10:00-10:15 2-bar trigger (proxy, signed, no stop):")
    for hz, lab in ((6, '+30m'), (12, '+60m'), (30, 'to 12:30'), (77, 'to close')):
        v = []
        for d in days:
            for p in ROWS:
                raw = D.bars[p][d]; s = two_bar(raw, None)
                if not s: continue
                j, side, bh, bl = s; e = max(raw[j][0], bh) if side > 0 else min(raw[j][0], bl)
                v.append(side * (raw[min(j + hz, 77)][3] / e - 1) * 100)
        print(f"   {lab:<9} n={len(v)} avg {st.mean(v):+.3f}% (se {st.pstdev(v)/math.sqrt(len(v)):.3f})  positive {100*sum(x>0 for x in v)/len(v):.0f}%")


if __name__ == '__main__':
    main()
