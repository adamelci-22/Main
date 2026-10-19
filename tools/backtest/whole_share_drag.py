"""Whole-share rounding drag: the backtest sizes positions as a continuous dollar amount; the broker only sells whole shares (limit/stop orders can't be fractional).
Re-runs the live-rules backtest with shares = floor(notional / leg price at the entry bar open), at several account sizes."""
import io, contextlib, statistics as st, collections, math
with contextlib.redirect_stdout(io.StringIO()):
    import scale_500k as S
D, days, f0, p0 = S.D, S.days, S.f0, S.p0
LEG = S.LEG
def leg_of(c):
    if c['sys'] == 'PB': return c['name']
    bull, bear, lb, lbe = LEG[c['proxy']]
    return bull if c['name'].endswith('+') else bear
def price(c):
    b = D.bars.get(leg_of(c), {}).get(c['day'])
    return b[c['k']][0] if b and c['k'] < len(b) else None
cs = [dict(c, px=price(c)) for c in f0 + p0]
def account(start, whole, risk=0.03):
    import twobar as TB
    by = collections.defaultdict(list)
    for c in cs: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; dl = []; taken = []; idle = []
    for d in days:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: c['k']); free = 0; n = 0
        while day and n < 3:
            av = [c for c in day if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq, eq * risk / (c['risk'] / 100))
            if whole and c['px']:
                sh = math.floor(notional / c['px'])
                if sh < 1: day.remove(c); continue          # cannot afford one share: no trade
                idle.append(1 - sh * c['px'] / notional); notional = sh * c['px']
            pnl = notional * c['pct'] / 100; eq += pnl; free = c['xbar'] + 1; taken.append(c); day.remove(c); n += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); dl.append((eq / e0 - 1) * 100)
    return len(taken), st.mean(dl), (eq / start - 1) * 100, mdd, (100 * st.mean(idle) if idle else 0)
print(f"{'account':>10}{'continuous $':>16}{'whole shares':>16}{'  idle cash/trade':>18}{'  trades':>9}")
for a in (1000, 2000, 2500, 5000, 10000, 25000, 100000):
    n0, d0, r0, m0, _ = account(a, False); n1, d1, r1, m1, idle = account(a, True)
    print(f"{a:>10,}{d0:>+13.3f}%/d{d1:>+13.3f}%/d{idle:>16.1f}%{n1:>9}  (return {r0:+.0f}% -> {r1:+.0f}%)")
