"""Backtest of the three crypto day-trading systems from the outside write-up, on weekends only (UTC Sat+Sun), coins BTC ETH SOL DOGE (PEPE if available).
Rules as written in the write-up, parameters chosen up front (not tuned). 5-minute bars, positions closed by 23:55 UTC at the latest (no overnight).
1. Breakout & retest   range = prior 36 bars (height 0.25-3% of price); close breaks out; retest within 12 bars (low within 0.10% of the broken level, close back above);
                      enter next open; stop 0.05% under the retest low/level (max 2% away); target = level + range height.
2. VWAP trend          VWAP resets 00:00 UTC; last 6 closes above VWAP, bar tags VWAP (low within 0.05%) closes above it as engulfing or hammer, volume 3-bar avg > 10-bar avg;
                      enter next open; stop under signal low (-0.05%); half off at 1.5 x ATR14, rest at 2 x ATR14.
3. Range mean-rev      00:00-08:00 UTC only; range = prior 48 bars, height <= 1.5%; buy within 15% of range low with RSI14 < 30 (mirror for shorts, RSI > 70);
                      stop 0.10% beyond the range edge; target the range midpoint; out at 08:00 UTC.
Spot (Robinhood) is LONG ONLY; 'long+short' rows are a reference for futures/perps only (shorts simulated on the inverted price series).
Risk 1% of equity per trade (notional capped at equity), one position at a time, $2,500 start. Round-trip cost is swept."""
import json, statistics as st, datetime as dt, collections, os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
COINS = [c for c in ('BTC', 'ETH', 'SOL', 'DOGE', 'PEPE') if os.path.exists(f'crypto/full_{c}.json')]
DATA = {c: json.load(open(f'crypto/full_{c}.json')) for c in COINS}
weekends = []
d = dt.date(2026, 3, 6)
while d <= dt.date(2026, 10, 9):
    if d.weekday() == 4: weekends.append([(d + dt.timedelta(days=i)).isoformat() for i in range(3)])
    d += dt.timedelta(days=1)

def series(coin, wkd):
    if not all(x in DATA[coin] for x in wkd): return None
    return [bar for x in wkd for bar in DATA[coin][x]]            # 864 bars: Fri 0-287, Sat 288-575, Sun 576-863

def indicators(b):
    n = len(b); vw = [0.0] * n
    for day in range(3):
        cv = cp = 0.0
        for i in range(day * 288, day * 288 + 288):
            tp = (b[i][1] + b[i][2] + b[i][3]) / 3; cv += b[i][4]; cp += tp * b[i][4]; vw[i] = cp / cv if cv > 0 else b[i][3]
    tr = [b[0][1] - b[0][2]] + [max(b[i][1] - b[i][2], abs(b[i][1] - b[i - 1][3]), abs(b[i][2] - b[i - 1][3])) for i in range(1, n)]
    atr = [0.0] * n
    for i in range(n): atr[i] = st.mean(tr[max(0, i - 13):i + 1])
    rsi = [50.0] * n; ag = al = 0.0
    for i in range(1, n):
        ch = b[i][3] - b[i - 1][3]; g, l = max(ch, 0), max(-ch, 0)
        if i <= 14: ag += g / 14; al += l / 14
        else: ag = (ag * 13 + g) / 14; al = (al * 13 + l) / 14
        if i >= 14: rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return vw, atr, rsi

def flip(b, vw, atr, rsi):   # short = long on the inverted series
    nb = [[1 / o, 1 / l, 1 / h, 1 / c, v] for o, h, l, c, v in b]
    return nb, [1 / x for x in vw], [a / (c * c) for a, (_, _, _, c, _) in zip(atr, b)], [100 - r for r in rsi]

def manage(b, k, entry, stop, targets, end):
    """targets = [(price, fraction)]; returns gross fraction return of entry, exit bar"""
    rem = 1.0; gross = 0.0; T = list(targets)
    for j in range(k, end + 1):
        o, h, l, c, v = b[j]
        if l <= stop: gross += rem * (min(stop, o) / entry - 1); return gross, j
        while T and h >= T[0][0]:
            px, fr = T.pop(0); fr = min(fr, rem); gross += fr * (max(px, o) / entry - 1); rem -= fr
            if rem <= 1e-9: return gross, j
    gross += rem * (b[end][3] / entry - 1); return gross, end

def sys1(b, ind, lo_i, hi_i):
    out = []; i = lo_i
    while i < hi_i - 14:
        rh = max(x[1] for x in b[i - 36:i]); rl = min(x[2] for x in b[i - 36:i]); ht = rh - rl
        if not (0.0025 <= ht / rh <= 0.03) or not (b[i][3] > rh and b[i - 1][3] <= rh): i += 1; continue
        level = rh; ok = False
        for j in range(i + 1, min(i + 13, hi_i - 2)):
            if b[j][3] < level: break
            if b[j][2] <= level * 1.001 and b[j][3] > level: ok = True; break
        if not ok: i += 1; continue
        k = j + 1; entry = b[k][0]; stop = min(b[j][2], level) * 0.9995
        if entry <= stop or (entry - stop) / entry > 0.02 or (entry - stop) / entry < 0.001 or level + ht <= entry: i += 1; continue
        g, x = manage(b, k, entry, stop, [(level + ht, 1.0)], hi_i - 1)
        out.append((k, x, g, (entry - stop) / entry)); i = x + 1
    return out

def sys2(b, ind, lo_i, hi_i):
    vw, atr, _ = ind; out = []; i = lo_i
    while i < hi_i - 2:
        if i < 12 or not all(b[q][3] > vw[q] for q in range(i - 6, i)): i += 1; continue
        o, h, l, c, v = b[i]; po, ph, pl, pc, pv = b[i - 1]
        eng = c > o and pc < po and c >= po and o <= pc
        ham = (min(o, c) - l) >= 2 * abs(c - o) and (h - max(o, c)) <= abs(c - o) + 1e-12 * h and c > o
        volup = st.mean(b[q][4] for q in range(i - 2, i + 1)) > st.mean(b[q][4] for q in range(i - 9, i + 1))
        if not (l <= vw[i] * 1.0005 and c > vw[i] and (eng or ham) and volup): i += 1; continue
        k = i + 1; entry = b[k][0]; stop = l * 0.9995; a = atr[i]
        if entry <= stop or (entry - stop) / entry > 0.02 or (entry - stop) / entry < 0.001 or a <= 0: i += 1; continue
        g, x = manage(b, k, entry, stop, [(entry + 1.5 * a, 0.5), (entry + 2.0 * a, 0.5)], hi_i - 1)
        out.append((k, x, g, (entry - stop) / entry)); i = x + 1
    return out

def sys3(b, ind, lo_i, hi_i):
    _, _, rsi = ind; out = []; i = lo_i; end = lo_i + 96 - 1          # window 00:00-08:00 UTC of this day
    while i < end - 1:
        rh = max(x[1] for x in b[i - 48:i]); rl = min(x[2] for x in b[i - 48:i]); ht = rh - rl
        if ht / rh > 0.015 or ht <= 0: i += 1; continue
        c = b[i][3]
        if not (rl <= c <= rl + 0.15 * ht and rsi[i] < 30): i += 1; continue
        k = i + 1; entry = b[k][0]; stop = rl * 0.999; tgt = rl + 0.5 * ht
        if entry <= stop or tgt <= entry or (entry - stop) / entry > 0.02 or (entry - stop) / entry < 0.001: i += 1; continue
        g, x = manage(b, k, entry, stop, [(tgt, 1.0)], end)
        out.append((k, x, g, (entry - stop) / entry)); i = x + 1
    return out

SYS = {'1 Breakout & retest': sys1, '2 VWAP trend': sys2, '3 Range mean-reversion': sys3}

def candidates(sysfn, shorts):
    out = []
    for wi, wkd in enumerate(weekends):
        for coin in COINS:
            b = series(coin, wkd)
            if not b: continue
            ind = indicators(b)
            for side in ((1, -1) if shorts else (1,)):
                bb, ii = (b, ind) if side > 0 else (flip(b, *ind)[0], flip(b, *ind)[1:])
                for day in (1, 2):
                    for (k, x, g, risk) in sysfn(bb, ii, day * 288, day * 288 + 288):
                        out.append(dict(w=wi, day=day, coin=coin, side=side, t0=wi * 1000 + day * 288 + k - day * 288 + (day - 1) * 0, k=day * 288 + k - day * 288, ke=x, g=g * (1 if side > 0 else 1), risk=risk, d=wkd[day]))
    return out

def run(cands, cost, start=2500.0, risk=0.01):
    byday = collections.defaultdict(list)
    for c in cands: byday[(c['w'], c['day'])].append(c)
    eq = start; peak = start; mdd = 0.0; taken = []; dl = []
    for w in range(len(weekends)):
        for day in (1, 2):
            e0 = eq; free = -1
            for c in sorted(byday.get((w, day), []), key=lambda c: (c['k'], c['coin'])):
                if c['k'] <= free: continue
                notional = min(eq, eq * risk / c['risk']); pnl = notional * (c['g'] - cost / 100); eq += pnl; free = c['ke']
                taken.append(dict(c, usd=pnl, pct=(c['g'] - cost / 100) * 100))
            peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); dl.append((eq / e0 - 1) * 100)
    n = len(taken); wins = sum(t['usd'] > 0 for t in taken); h = len(dl) // 2
    return dict(n=n, win=100 * wins / max(n, 1), avg=st.mean(t['pct'] for t in taken) if n else 0, day=st.mean(dl), ret=(eq / start - 1) * 100, dd=mdd, h1=st.mean(dl[:h]), h2=st.mean(dl[h:]), taken=taken, eq=eq)

def line(tag, r): return f"  {tag:<28}{r['n']:>5}{r['win']:>6.0f}%{r['avg']:>+9.3f}%{r['day']:>+9.3f}%{r['ret']:>+9.1f}%{r['dd']:>6.1f}%{r['h1']:>+8.3f}{r['h2']:>+8.3f}"
HDR = f"  {'':<28}{'trd':>5}{'win':>7}{'avg/trade':>10}{'%/wkend day':>11}{'return':>10}{'DD':>7}{'H1':>8}{'H2':>8}"

if __name__ == '__main__':
    print(f"Crypto systems, weekends only: {len(weekends)} weekends ({weekends[0][1]}..{weekends[-1][2]}), {2*len(weekends)} Sat/Sun days, coins {COINS}, start $2,500, 1% risk per trade\n")
    for shorts in (False, True):
        print('=' * 20, 'LONG ONLY (what spot Robinhood allows)' if not shorts else 'LONG + SHORT (reference only: futures/perps)', '=' * 20)
        allc = []
        for name, fn in SYS.items():
            cs = candidates(fn, shorts); allc += cs
            print(f"{name}  - {len(cs)} raw signals")
            print(HDR)
            for cost in (0.0, 0.1, 0.4, 0.8, 1.2): print(line(f'round-trip cost {cost:.1f}%', run(cs, cost)))
        print('All three together'); print(HDR)
        for cost in (0.0, 0.1, 0.4, 0.8, 1.2): print(line(f'round-trip cost {cost:.1f}%', run(allc, cost)))
        print()
    cs = [c for fn in SYS.values() for c in candidates(fn, False)]
    print("By coin, long only, cost 0.4%:")
    for coin in COINS:
        r = run([c for c in cs if c['coin'] == coin], 0.4); print(line(coin, r))
