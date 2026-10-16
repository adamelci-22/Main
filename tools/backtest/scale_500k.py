"""Scale tests on a $500,000 account (same signals, same account rules, 2026-03-03..10-14).
A. Liquidity-capped sizing: position <= CAP x dollar volume of the signal bar of the instrument bought, plus an assumed market-impact cost.
B. FADE traded on the liquid proxy itself (QQQ SOXX IWM XLK XBI AMD) with leverage via margin/futures; PULLBACK stays on its ETFs (capped as in A).
Impact model (ASSUMPTION, not measured): extra round-trip cost = 2 x 0.5 x 0.5% x sqrt(participation) of the position.
"""
import math, statistics as st, collections
from suggestion_tests import *
import mixed as MXD, manual as m, twobar as TB
LEG = {'QQQ': ('TQQQ', 'SQQQ', 3, 3), 'SOXX': ('SOXL', 'SOXS', 3, 3), 'IWM': ('TNA', 'TZA', 3, 3), 'XLK': ('TECL', 'TECS', 3, 3), 'XBI': ('LABU', 'LABD', 3, 3), 'AMD': ('AMDL', 'AMDD', 2, 1)}
D = get_data(); m.rvol = PBF.rvol(D)
days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
f0, p0 = FS.cands(D, days)

def dvol(sym, day, k):
    b = D.bars.get(sym, {}).get(day)
    if not b: return None
    j = min(max(k - 1, 0), len(b) - 1); return b[j][3] * b[j][4]      # signal bar: known before the order

def prep(c, direct=False):
    c = dict(c)
    if c['sys'] == 'FADE':
        bull, bear, lb, lbe = LEG[c['proxy']]; up = c['name'].endswith('+'); L = lb if up else lbe; leg = bull if up else bear
        if direct:
            c['pct'] = (c['pct'] + 0.06) / L - 0.03; c['risk'] = c['risk'] / L; c['vol'] = dvol(c['proxy'], c['day'], c['k'])
        else:
            c['vol'] = dvol(leg, c['day'], c['k'])
    else:
        c['vol'] = dvol(c['name'], c['day'], c['k'])
    return c

def account(cs, start, cap, maxlev=1.0, impact=True, risk=0.03):
    by = collections.defaultdict(list)
    for c in cs: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []; parts = []
    for d in days:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: c['k']); n = 0; free = 0
        while day and n < 3:
            av = [c for c in day if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq * maxlev, eq * risk / (c['risk'] / 100))
            part = 0.0
            if c['vol']:
                if cap: notional = min(notional, cap * c['vol'])
                part = notional / c['vol']
            imp = 2 * 0.5 * 0.5 * math.sqrt(part) if impact else 0.0         # % round trip
            pnl = notional * (c['pct'] - imp) / 100; parts.append(part)
            eq += pnl; taken.append(dict(c, usd=pnl, notional=notional, part=part)); free = c['xbar'] + 1; day.remove(c); n += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    dl = list(daily.values())
    return dict(n=len(taken), win=100 * sum(t['usd'] > 0 for t in taken) / max(len(taken), 1), day=st.mean(dl), ret=(eq / start - 1) * 100, dd=mdd,
                usd=eq - start, avgpos=st.mean(t['notional'] for t in taken), avgpart=100 * st.mean(parts), taken=taken)

def line(tag, r):
    return f"{tag:<46}{r['n']:>5}{r['win']:>5.0f}%{r['day']:>+8.3f}%{r['ret']:>+9.1f}%{r['dd']:>6.1f}%{r['avgpos']:>11,.0f}{r['avgpart']:>7.1f}%{r['usd']:>13,.0f}"
H = f"{'':<46}{'trd':>5}{'win':>6}{'%/day':>9}{'return':>10}{'DD':>7}{'avg pos $':>11}{'part.':>8}{'profit $':>13}"
S = 500_000
base = [prep(c) for c in f0 + p0]
chk = account(base, 2000, None, impact=False)
print(f"check: $2,000, no cap, no impact -> {chk['n']} trades, ${chk['usd']:,.2f} (live-rules backtest: 115, $4,764.36)\n")
print("A. LIQUIDITY-CAPPED SIZING, $500,000 account, trade the same ETFs (1x cash max; impact charged on participation)")
print(H)
print(line('  $2,000 account, no cap (reference)', chk))
print(line('  $500k, no cap, no impact (unrealistic)', account(base, S, None, impact=False)))
print(line('  $500k, no cap, with impact', account(base, S, None)))
for cap in (0.10, 0.05, 0.02, 0.01):
    print(line(f"  $500k, cap {int(cap*100)}% of signal-bar $volume", account(base, S, cap)))
print()
print("B. FADE ON THE PROXY (leverage via margin/futures, proxy round-trip cost 0.03%); PULLBACK on its ETFs. $500,000, cap 5% of signal-bar $volume")
print(H)
mixed = lambda: [prep(c, direct=True) for c in f0] + [prep(c) for c in p0]
M = mixed()
for lev in (1.0, 2.0, 3.0, 4.0):
    print(line(f"  FADE direct, max leverage {lev:.0f}x", account(M, S, 0.05, maxlev=lev)))
fd = [c for c in M if c['sys'] == 'FADE']
print(line('  FADE direct only, 4x', account(fd, S, 0.05, maxlev=4.0)))
print(line('  FADE on ETFs only, cap 5% (for comparison)', account([c for c in base if c['sys'] == 'FADE'], S, 0.05)))
print(line('  FADE direct, 4x, no impact (upper bound)', account(M, S, 0.05, maxlev=4.0, impact=False)))
print("\n  note: 4x ~ Reg-T intraday buying power on a full margin account; our account is limited margin (cash-like), so 2x+ needs an account change or futures.")
