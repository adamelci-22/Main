#!/usr/bin/env python3
"""Tests of outside suggestions against the live system's backtest (governor request, 2026-10-16).
    python3 tools/backtest/suggestion_tests.py > tools/backtest/results/suggestion_tests.txt
A. FADE trail ATR variants (fixed morning ATR instead of rolling ATR14)     [suggestion 3]
B. PULLBACK time-decay exits (breakeven stop / cut after N bars)           [advanced 1]
C. Dynamic daily circuit breaker and the flat -3% breaker, on the account's real trade sequence  [advanced 2]
D. Days after AMD / NVDA earnings: what the semis rows did               [suggestion 4]
E. Spread filter: what 0.30% means in cents for each ticker; PULLBACK results on market-selloff days [suggestion 2]
All variants use the same account rules as final_system.py (one position, 3% risk capped at cash, same costs)."""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_system as FS, pb_final as PBF, pb_inverse as PI, mixed as MXD, manual as m
from lab import get_data

SELL_BY = PBF.SELL_BY
ORIG_ATR = m.atr


def atr_morning(b, j):                       # average of the rolling ATR14 from 10:00 up to now, frozen after 11:00 (no look-ahead)
    vals = [ORIG_ATR(b, i) for i in range(6, min(j, 17) + 1)]
    return st.mean(vals) if vals else ORIG_ATR(b, j)


def atr_floor(b, j):                         # trail never tightens below the morning level
    return max(ORIG_ATR(b, j), atr_morning(b, j))


def stats(D, days, cs, sysname=None):
    a = MXD.account(D, days, cs); tk = [x for x in a['taken'] if sysname is None or x.get('sys') == sysname]
    dl = list(a['daily'].values()); w = [x for x in tk if x['usd'] > 0]; h = len(days) // 2
    return dict(n=len(tk), win=100 * len(w) / max(len(tk), 1), day=st.mean(dl), ret=a['ret'], dd=a['mdd'],
                h1=st.mean(dl[:h]), h2=st.mean(dl[h:]), taken=a['taken'])


def row(tag, r, base=None):
    d = f"({r['day'] - base['day']:+.3f})" if base else ''
    return f"{tag:<44}{r['n']:>5}{r['win']:>6.0f}%{r['day']:>+9.3f} {d:<9}{r['ret']:>+8.1f}%{r['dd']:>6.1f}%{r['h1']:>+8.3f}{r['h2']:>+8.3f}"


HDR = f"{'':<44}{'trd':>5}{'win':>7}{'%/day':>9} {'':<9}{'return':>9}{'maxDD':>7}{'H1':>8}{'H2':>8}"


def pb_manage(s, mode, N):
    b, k, entry, stop = s['b'], s['k'], s['entry'], s['stop']
    last = SELL_BY
    if k > last: return None
    r = entry - stop; T = s['hod']
    gross = 0.0; cost = 0.0001 * entry; xbar = last; hit = False; closed = False
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross += px - entry; cost += 0.0003 * px; xbar = j; closed = True; break
        if h >= T:
            px = max(T, o); gross += px - entry; cost += 0.0003 * px; xbar = j; closed = True; hit = True; break
        if mode and j - k + 1 == N and j + 1 <= last:
            if mode == 'be': stop = max(stop, entry)
            elif mode == 'cut' or (mode == 'cutred' and c < entry):
                px = b[j + 1][0]; gross += px - entry; cost += 0.0003 * px; xbar = j + 1; closed = True; break
    if not closed:
        px = b[last][3]; gross += px - entry; cost += 0.0003 * px
    pnl = gross - cost
    return dict(day=s['day'], inst=s['inst'], k=k, xbar=xbar, pnl=pnl, risk=r, entry=entry, pct=pnl / entry * 100, hit=hit)


def pb_cands(x):
    return dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100)


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
    march = [d for d in days if d < '2026-04-07']
    print("TESTS OF OUTSIDE SUGGESTIONS vs the live system's backtest (2026-03-03..10-14, 157 days; same account rules)\n")

    # ---------------- baseline
    f0, p0 = FS.cands(D, days); base = stats(D, days, f0 + p0)
    print(HDR); print(row('BASELINE (live rules, v5.1)', base)); print()

    # ---------------- A. fade trail ATR
    print("A. FADE trail: rolling ATR14 (live) vs a fixed morning ATR   [suggestion 3: 'lunch compresses ATR, trail knocks you out']")
    ratios = []
    for p in FS.FADE:
        for d in days:
            b = D.bars.get(p, {}).get(d)
            if b: ratios.append(ORIG_ATR(b, 36) / ORIG_ATR(b, 17))
    print(f"   premise check: ATR14 at 12:30 / ATR14 at 11:00, all proxies, all days: median {st.median(ratios):.2f}x, mean {st.mean(ratios):.2f}x, share of days where it is lower: {100*sum(r<1 for r in ratios)/len(ratios):.0f}%")
    for tag, fn in (('rolling ATR14 (live)', ORIG_ATR), ('morning-average ATR (10:00-11:00, frozen)', atr_morning), ('max(rolling, morning)  [never tighter]', atr_floor)):
        m.atr = fn
        try:
            f, p = FS.cands(D, days); r = stats(D, days, f + p); fa = stats(D, days, f, 'FADE')
            f2, p2 = FS.cands(D, march); mr = stats(D, march, f2 + p2)
        finally:
            m.atr = ORIG_ATR
        print(row('  ' + tag, r, base) + f"   | fade-only {fa['day']:+.3f}/day | March {mr['day']:+.3f}")
    print()

    # ---------------- B. pullback time decay
    print("B. PULLBACK time decay   [advanced 1: 'if not at target after 20-30 min, go breakeven or cut']")
    PBF.TARGET_MODE = 'floor'
    S = PBF.setups(D, days, FS.PB, True)
    def run(mode, N):
        t = [pb_manage(s, mode, N) for s in S]; return [pb_cands(x) for x in t if x]
    chk = run(None, 0)
    r0 = stats(D, days, f0 + chk); print(row('  no decay (live)  [matches baseline?]', r0, base))
    for mode, label in (('be', 'stop to breakeven'), ('cut', 'cut at next open'), ('cutred', 'cut only if price below entry')):
        for N in (4, 6, 9):
            r = stats(D, days, f0 + run(mode, N)); pbo = stats(D, days, f0 + run(mode, N), 'PB')
            print(row(f"  after {N} bars ({5*N} min): {label}", r, base) + f"   | pullback win {pbo['win']:.0f}%")
    # how the live pullback trades behave in time
    tr = [pb_manage(s, None, 0) for s in S]; tr = [t for t in tr if t]
    hold = [t['xbar'] - t['k'] + 1 for t in tr if t['hit']]
    print(f"   live pullback trades: {sum(t['hit'] for t in tr)} of {len(tr)} reach the target; winners take median {st.median(hold)} bars ({5*st.median(hold):.0f} min), 75th pct {sorted(hold)[int(.75*len(hold))]} bars; {sum(h>6 for h in hold)} of {len(hold)} winners needed more than 6 bars")
    print()

    # ---------------- C. circuit breakers
    print("C. Daily circuit breakers on the account's real trade sequence   [advanced 2]")
    tk = sorted(base['taken'], key=lambda x: (x['day'], x['k'])); eq = 2000.0; byday = collections.OrderedDict()
    for x in tk: byday.setdefault(x['day'], []).append(x)
    blk_dyn = []; blk_flat = []; ndays2 = 0; hit4 = 0; below3 = 0; dayrets = []
    for d, xs in byday.items():
        e0 = eq; cum = 0.0; peak = 0.0
        if len(xs) >= 2: ndays2 += 1
        for x in xs:
            r_ = cum / e0 * 100
            if peak >= 4.0 and r_ <= peak - 2.0: blk_dyn.append(x)
            if r_ <= -3.0: blk_flat.append(x)
            cum += x['usd']; r_ = cum / e0 * 100; peak = max(peak, r_)
            if r_ >= 4.0 and not any(True for _ in ()): pass
        if peak >= 4.0: hit4 += 1
        if cum / e0 * 100 <= -3.0 or min((sum(y['usd'] for y in xs[:i + 1]) / e0 * 100) for i in range(len(xs))) <= -3.0: below3 += 1
        dayrets.append((cum / e0 * 100, d, len(xs))); eq += sum(x['usd'] for x in xs)
    print(f"   trading days {len(byday)}; days with 2+ trades {ndays2}; days whose running return ever reached +4%: {hit4}; days that ever touched -3%: {below3}")
    print(f"   dynamic breaker (peak>=4% then stop at peak-2%): trades it would have blocked: {len(blk_dyn)} (their P&L ${sum(x['usd'] for x in blk_dyn):+.0f})")
    print(f"   flat -3% breaker: trades it would have blocked: {len(blk_flat)} (their P&L ${sum(x['usd'] for x in blk_flat):+.0f})")
    best = sorted(dayrets, reverse=True)[:5]
    print("   best days, % of that day's starting equity: " + ', '.join(f"{d} {v:+.1f}% ({n} trade{'s' if n>1 else ''})" for v, d, n in best))
    print()

    # ---------------- D. earnings
    print("D. Days after earnings (AMD reported after the close 2026-05-05 and 2026-08-04; NVDA 2026-05-20 and 2026-08-26)   [suggestion 4]")
    after = {'AMD': ['2026-05-06', '2026-08-05'], 'NVDA': ['2026-05-21', '2026-08-27']}
    for who, ds in after.items():
        for d in ds:
            ev = [x for x in base['taken'] if x['day'] == d]
            if not ev: print(f"   day after {who} earnings {d}: no trades taken"); continue
            for x in ev: print(f"   day after {who} earnings {d}: {x['sys']} {x['name'] if x.get('name') else x.get('proxy')} {x['pct']:+.2f}% (${x['usd']:+.1f})")
    semis = [x for x in base['taken'] if (x.get('proxy') == 'SOXX') or x.get('name') == 'SOXS']
    print(f"   all-period SOXX fade + SOXS pullback: {len(semis)} trades, avg {st.mean(x['pct'] for x in semis):+.2f}%; the 4 post-earnings days contain {sum(1 for x in semis if x['day'] in sum(after.values(), []))} of them")
    print()

    # ---------------- E. spread
    print("E. Spread filter   [suggestion 2]")
    for t in ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD', 'TQQQ', 'SOXL', 'TNA', 'LABU', 'AMDD']:
        px = [x[3] for d in days if d in D.bars.get(t, {}) for x in D.bars[t][d][6:48]]
        if not px: continue
        med = st.median(px); cap = med * 0.003
        print(f"   {t:<5} median price ${med:7.2f}: 0.30% = {100*cap:5.1f} cents (one tick = 1 cent = {100*0.01/med:.2f}% )")
    # pullback trades on selloff days: proxy (SOXX/XLK/QQQ) daily return
    def dayret(sym, d):
        b = D.bars.get(sym, {}).get(d)
        pd_ = D.days[D.days.index(d) - 1]; pb = D.bars.get(sym, {}).get(pd_)
        return (b[-1][3] / pb[-1][3] - 1) * 100 if b and pb else None
    sel = [x for x in base['taken'] if x['sys'] == 'PB' and (dayret(PI.PROXY.get(x['name'], 'QQQ'), x['day']) or 0) <= -1.5]
    allpb = [x for x in base['taken'] if x['sys'] == 'PB']
    print(f"   pullback trades taken on days when the ticker's proxy fell 1.5% or more: {len(sel)} of {len(allpb)}; their P&L ${sum(x['usd'] for x in sel):+.0f} vs ${sum(x['usd'] for x in allpb):+.0f} for all pullbacks")
    for extra in (0.30, 0.50):
        pc = [dict(c, pct=c['pct'] - extra) for c in p0]; fc = [dict(c) for c in f0]
        rp = stats(D, days, fc + pc)
        print(f"   cost test: +{extra:.2f}% extra round-trip cost on EVERY pullback trade (fade unchanged): {rp['day']:+.3f}%/day ({rp['day'] - base['day']:+.3f}), return {rp['ret']:+.1f}%")
    print("   (the backtest has no bid/ask data, so a spread-dependent rule itself cannot be tested; costs of +0.30% on every thin-ticker trade were tested in stress.txt: +0.518%/day)")


if __name__ == '__main__':
    main()
