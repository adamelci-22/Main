"""FADE and PULLBACK applied to BTC and ETH on weekends only (Sat+Sun, 09:30-16:00 ET window, same clock as the equity rules).
Spot, long-only, no leverage (Robinhood crypto has no shorts/inverse legs). Costs are round-trip, swept. 2026-03-07..10-11, 31 weekends, 62 days."""
import json, math, statistics as st, datetime as dt, collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, expand_lists as EX, twobar as TB
class M: pass
D = M(); D.bars = {c: json.load(open(f'crypto/bars_{c}.json')) for c in ('BTC', 'ETH')}
alld = sorted(D.bars['BTC']); D.days = alld
wk = [d for d in alld if dt.date.fromisoformat(d).weekday() in (5, 6) and d in D.bars['ETH']]
for c in D.bars: D.bars[c] = {d: b for d, b in D.bars[c].items() if all(x is not None for x in b)}
wk = [d for d in wk if d in D.bars['BTC'] and d in D.bars['ETH']]
PBF.TARGET_MODE = 'floor'

def fade(cost, shorts=False):
    out = []
    for p in ('BTC', 'ETH'):
        for t in EX.fade_trades(D, wk, p, (p, 1, p + 'S', 1)):
            if t['side'] < 0 and not shorts: continue
            t = dict(t); t['pct'] = t['pct'] + TB.LEGCOST - cost; t['sys'] = 'FADE'; t['name'] = p + ('+' if t['side'] > 0 else '-'); out.append(t)
    return out

def pb_manage(s, cost):
    b, k, entry, stop, T = s['b'], s['k'], s['entry'], s['stop'], s['hod']; last = 47
    if k > last: return None
    r = entry - stop; xbar = last; closed = False; gross = 0.0
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop: px = min(stop, o); gross = px - entry; xbar = j; closed = True; break
        if h >= T: px = max(T, o); gross = px - entry; xbar = j; closed = True; break
    if not closed: gross = b[last][3] - entry
    return dict(day=s['day'], proxy=s['inst'], name=s['inst'], sys='PB', k=k, xbar=xbar, pct=gross / entry * 100 - cost, leg_risk=r / entry * 100)

def pullback(cost):
    S = PBF.setups(D, wk, ['BTC', 'ETH'], True)
    return [t for t in (pb_manage(s, cost) for s in S) if t]

def account(cs, start=2500.0, risk=0.03):
    by = collections.defaultdict(list)
    for c in cs: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; daily = []; taken = []
    for d in wk:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: c['k']); free = 0; n = 0
        while day and n < 3:
            av = [c for c in day if c['k'] >= free]
            if not av: break
            c = min(av, key=lambda c: (c['k'], c['proxy'])); notional = min(eq, eq * risk / (c['leg_risk'] / 100))
            pnl = notional * c['pct'] / 100; eq += pnl; taken.append(dict(c, usd=pnl)); free = c['xbar'] + 1; day.remove(c); n += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily.append((eq / e0 - 1) * 100)
    wins = sum(t['usd'] > 0 for t in taken)
    return dict(n=len(taken), win=100 * wins / max(len(taken), 1), day=st.mean(daily), ret=(eq / start - 1) * 100, dd=mdd, eq=eq, daily=daily,
                avg=st.mean(t['pct'] for t in taken) if taken else 0, taken=taken)

def row(tag, r):
    h = len(r['daily']) // 2
    return f"{tag:<44}{r['n']:>5}{r['win']:>6.0f}%{r['avg']:>+9.3f}%{r['day']:>+9.3f}%{r['ret']:>+9.1f}%{r['dd']:>6.1f}%{st.mean(r['daily'][:h]):>+8.3f}{st.mean(r['daily'][h:]):>+8.3f}"
H = f"{'':<44}{'trd':>5}{'win':>7}{'avg/trade':>10}{'%/wkend day':>11}{'return':>10}{'DD':>7}{'H1':>8}{'H2':>8}"
print(f"Weekend days tested: {len(wk)} ({wk[0]}..{wk[-1]}); BTC and ETH; start $2,500; 3% risk, spot long-only, 1 position at a time\n")
bh = {c: st.mean((D.bars[c][d][47][3] / D.bars[c][d][0][0] - 1) * 100 for d in wk) for c in ('BTC', 'ETH')}
print(f"reference: average 09:30->13:30 buy-and-hold on a weekend day: BTC {bh['BTC']:+.3f}%, ETH {bh['ETH']:+.3f}%\n")
print(H)
for cost in (0.06, 0.30, 0.60, 1.00):
    print(f"-- round-trip cost {cost:.2f}% --")
    f = fade(cost); p = pullback(cost)
    print(row('FADE (long side only)', account(f))); print(row('PULLBACK (long)', account(p))); print(row('FADE + PULLBACK', account(f + p)))
    if cost == 0.06: print(row('FADE with shorts (not available on spot)', account(fade(cost, True))))
