#!/usr/bin/env python3
"""Weakness and gap tests for the v4.0 paper system (FADE 6 + PULLBACK 5), 2026-03-03..10-14.
    python3 tools/backtest/stress.py > tools/backtest/results/stress.txt
"""
import math, os, random, statistics as st, sys, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA, fade_combo as FC, retest as RT, twobar as TB
from lab import get_data

FADE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD']
PB = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD']
THIN = {'TECS', 'AMDD', 'LABU'}
PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'NVD': 'NVDA', 'LABD': 'LABD', 'UVXY': 'UVXY'})
D = get_data(); m.rvol = PBF.rvol(D); DAYS = D.days[1:]; H = len(DAYS) // 2; MAR = [d for d in DAYS if d < '2026-04-07']


def fade_c(days, rows=FADE, R=2.0, frac=1 / 3, runner='chand2', last=47):
    out = []
    for p in rows:
        row = FA.ROWS[p]; bull, lb, bear, lbe = row
        saved = TB.ROWS.get(p); TB.ROWS[p] = (bull, bear, lb)
        for d in days:
            if d not in D.bars.get(p, {}): continue
            t = FC.run_trade(D, d, p, R=R, frac=frac, runner=runner, last=last)
            if not t: continue
            if t['side'] < 0 and lbe != lb:
                t['pct'] = (t['pct'] + TB.LEGCOST) / lb * lbe - TB.LEGCOST; t['leg_risk'] = t['leg_risk'] / lb * lbe
            t['leg'] = bull if t['side'] > 0 else bear
            out.append(t)
        if saved: TB.ROWS[p] = saved
        else: del TB.ROWS[p]
    c = MXD.norm_px(out, 'FADE')
    for x, t in zip(c, out): x['leg'] = t['leg']
    return c


def pb_c(days, tickers=PB):
    s = PBF.run(D, days, tickers, oco_gap=True)
    return [dict(day=x['day'], sys='PB', name=x['inst'], leg=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'],
                 risk=x['risk'] / x['entry'] * 100, entry_px=x['entry']) for x in s]


def res(cands, days=DAYS):
    a = MXD.account(D, days, cands); dl = a['daily']; h = len(days) // 2
    return dict(a=a, d=st.mean(dl.values()), h1=st.mean(dl[d] for d in days[:h]), h2=st.mean(dl[d] for d in days[h:]), ret=a['ret'], dd=a['mdd'], n=len(a['taken']))


def line(name, r, base=None):
    delta = f"  ({r['d']-base['d']:+.3f})" if base else ''
    print(f"   {name:<50} {r['d']:+.3f}%/day{delta:<10} ret {r['ret']:+7.1f}%  DD {r['dd']:4.1f}%  H1 {r['h1']:+.3f}  H2 {r['h2']:+.3f}  trades {r['n']}")


def main():
    F = fade_c(DAYS); P = pb_c(DAYS); B = res(F + P)
    print(f"STRESS TESTS, v4.0 system, {DAYS[0]}..{DAYS[-1]} ({len(DAYS)} days)\n")
    line('BASELINE', B)

    print("\n1. COSTS AND SLIPPAGE (extra round-trip cost per trade, on top of what the backtest already charges)")
    for x in (0.05, 0.10, 0.20, 0.30, 0.50):
        line(f'+{x:.2f}% every trade', res([dict(c, pct=c['pct'] - x) for c in F + P]), B)
    line('+0.30% only on thin tickers (TECS, AMDD, LABU)', res([dict(c, pct=c['pct'] - (0.30 if c['leg'] in THIN else 0)) for c in F + P]), B)
    line('+0.50% only on thin tickers', res([dict(c, pct=c['pct'] - (0.50 if c['leg'] in THIN else 0)) for c in F + P]), B)
    lo = [c for c in F + P if c['pct'] < 0]
    line('stops slip: losing trades lose 0.25% more', res([dict(c, pct=c['pct'] - (0.25 if c['pct'] < 0 else 0)) for c in F + P]), B)
    line('stops slip: losing trades lose 0.50% more', res([dict(c, pct=c['pct'] - (0.50 if c['pct'] < 0 else 0)) for c in F + P]), B)
    be = None
    for x in [i / 100 for i in range(0, 200, 2)]:
        if res([dict(c, pct=c['pct'] - x) for c in F + P])['d'] <= 0: be = x; break
    print(f"   -> break-even extra cost: about {be:.2f}% per round trip")

    print("\n2. LATE ENTRY (a missed/late checkpoint: the FADE buys one bar later)")
    orig = RT.setup
    def late(b, c):
        s = orig(b, c)
        if not s or s[0] + 1 > 76: return None
        k, side, e, stop = s
        return k + 1, side, b[k + 1][0], stop
    RT.setup = late
    try: line('FADE entry one bar (5 min) late', res(fade_c(DAYS) + P), B)
    finally: RT.setup = orig

    print("\n3. PARAMETER SENSITIVITY (one change at a time; a robust system degrades gently)")
    for name, kw in (('fade target 1.5R', dict(R=1.5)), ('fade target 2.5R', dict(R=2.5)), ('fade sells 1/4 at target', dict(frac=0.25)),
                     ('fade sells 1/2 at target', dict(frac=0.5)), ('fade chandelier 1.5 ATR', dict(runner='chand1.5')), ('fade chandelier 3 ATR', dict(runner='chand3')),
                     ('fade sell-by 13:00', dict(last=41)), ('fade sell-by 14:00', dict(last=53))):
        line(name, res(fade_c(DAYS, **kw) + P), B)
    o = FC.FADE
    for name, rc in (('fade retest tolerance 0.05%', RT.RC(fade=True, tol=0.05)), ('fade retest tolerance 0.20%', RT.RC(fade=True, tol=0.20)),
                     ('fade retest window 8 bars', RT.RC(fade=True, max_wait=8)), ('fade retest window 18 bars', RT.RC(fade=True, max_wait=18)),
                     ('fade break allowed until 10:25', RT.RC(fade=True, brk_end=12))):
        FC.FADE = rc
        try: line(name, res(fade_c(DAYS) + P), B)
        finally: FC.FADE = o
    for name, attr, val in (('pullback stop buffer 0%', 'BUFFER_PCT', 0.0), ('pullback stop buffer 0.10%', 'BUFFER_PCT', 0.10),
                            ('pullback min room 0.5%', 'MIN_ROOM', 0.5), ('pullback min room 1.0%', 'MIN_ROOM', 1.0),
                            ('pullback min target 0.5x', 'MIN_RR', 0.5), ('pullback min target 1.0x', 'MIN_RR', 1.0),
                            ('pullback sell-by 13:00', 'SELL_BY', 41), ('pullback sell-by 14:00', 'SELL_BY', 53)):
        old = getattr(PBF, attr); setattr(PBF, attr, val)
        try: line(name, res(F + pb_c(DAYS)), B)
        finally: setattr(PBF, attr, old)
    for name, mx in (('max 2 entries/day', 2), ('max 4 entries/day', 4)):
        a = MXD.account(D, DAYS, F + P, max_entries=mx); dl = a['daily']
        line(name, dict(d=st.mean(dl.values()), h1=st.mean(dl[d] for d in DAYS[:H]), h2=st.mean(dl[d] for d in DAYS[H:]), ret=a['ret'], dd=a['mdd'], n=len(a['taken'])), B)
    a = MXD.account(D, DAYS, F + P, mode='two'); dl = a['daily']
    line('two positions at once (half cash each)', dict(d=st.mean(dl.values()), h1=st.mean(dl[d] for d in DAYS[:H]), h2=st.mean(dl[d] for d in DAYS[H:]), ret=a['ret'], dd=a['mdd'], n=len(a['taken'])), B)

    print("\n4. DEPENDENCE ON SINGLE NAMES / BIG DAYS")
    line('without the SOXX fade row', res(fade_c(DAYS, rows=[p for p in FADE if p != 'SOXX']) + P), B)
    line('without SOXS in the pullback', res(F + pb_c(DAYS, [t for t in PB if t != 'SOXS'])), B)
    line('without any semis (SOXX fade, SOXS pullback)', res(fade_c(DAYS, rows=[p for p in FADE if p != 'SOXX']) + pb_c(DAYS, [t for t in PB if t != 'SOXS'])), B)
    tk = sorted(B['a']['taken'], key=lambda c: -c['usd']); topdays = {c['day'] for c in tk[:5]}
    line('without the 5 best trading days', res([c for c in F + P if c['day'] not in topdays]), B)
    topdays10 = {c['day'] for c in tk[:10]}
    line('without the 10 best trading days', res([c for c in F + P if c['day'] not in topdays10]), B)

    print("\n5. MONTE CARLO (resample the 157 daily returns with replacement, 10,000 paths of 157 days)")
    dl = list(B['a']['daily'].values()); rng = random.Random(1); finals = []; dds = []; lm = 0
    for _ in range(10000):
        eq = 1.0; peak = 1.0; mdd = 0.0; path = []
        for _ in range(len(dl)):
            eq *= 1 + rng.choice(dl) / 100; peak = max(peak, eq); mdd = max(mdd, 1 - eq / peak); path.append(eq)
        finals.append((eq - 1) * 100); dds.append(mdd * 100)
    finals.sort(); dds.sort()
    pc = lambda v, q: v[int(q * (len(v) - 1))]
    print(f"   return after 157 days: 5th pct {pc(finals,.05):+.0f}%, median {pc(finals,.5):+.0f}%, 95th {pc(finals,.95):+.0f}%; paths losing money: {100*sum(f<0 for f in finals)/len(finals):.2f}%")
    print(f"   max drawdown: median {pc(dds,.5):.1f}%, 95th pct {pc(dds,.95):.1f}%, worst {dds[-1]:.1f}%")
    half = [d for d in dl]; rng = random.Random(2); fin2 = []
    for _ in range(10000):
        eq = 1.0
        for _ in range(len(dl)): eq *= 1 + rng.choice(half) * 0.5 / 100
        fin2.append((eq - 1) * 100)
    fin2.sort(); print(f"   if every day earned only HALF its backtest result: median {pc(fin2,.5):+.0f}%, 5th pct {pc(fin2,.05):+.0f}%")
    # 20-day windows
    win = [sum(dl[i:i + 20]) for i in range(len(dl) - 19)]
    print(f"   rolling 20-day (about a month) sums: worst {min(win):+.1f}%, best {max(win):+.1f}%, negative windows {100*sum(w<0 for w in win)/len(win):.0f}%")

    print("\n6. REGIMES")
    rows = collections.defaultdict(list)
    for d, v in B['a']['daily'].items():
        s = D.bars['SPY'][d]; ch = (s[77][3] / s[0][0] - 1) * 100
        i = D.days.index(d); g = (s[0][0] / D.bars['SPY'][D.days[i - 1]][77][3] - 1) * 100
        rows['SPY day: up > +0.5%' if ch > 0.5 else 'SPY day: down < -0.5%' if ch < -0.5 else 'SPY day: flat'].append(v)
        rows['SPY gap > 0.5% (either way)' if abs(g) > 0.5 else 'SPY gap small'].append(v)
        rows[dt.date.fromisoformat(d).strftime('%A')].append(v)
    for k in sorted(rows):
        v = rows[k]; print(f"   {k:<30} days {len(v):3d}  avg {st.mean(v):+.3f}%/day  losing days {100*sum(x<0 for x in v)/len(v):.0f}%")

    print("\n7. SINGLE-TRADE RISK AND CAPACITY")
    t = B['a']['taken']
    print(f"   worst trade {min(c['pct'] for c in t):+.2f}% on the ticker (positions are capped at 100% of cash, so at most that % of the account); "
          f"worst day {min(B['a']['daily'].values()):+.2f}%")
    caps = []
    for c in t:
        b = D.bars.get(c['leg'], {}).get(c['day'])
        if not b: continue
        k = c['k']; bv = st.mean(x[4] * x[3] for x in b[max(0, k - 3):k + 3])
        caps.append((c['leg'], bv))
    for size in (2000, 10000, 50000):
        share = [size / bv * 100 for _, bv in caps if bv]
        print(f"   position ${size:,}: median {st.median(share):.1f}% of a 5-min bar's $ volume at entry, worst {max(share):.0f}%"
              f"{' (thin: ' + ', '.join(sorted({l for l, bv in caps if bv and size / bv > 0.25})) + ')' if any(size / bv > 0.25 for _, bv in caps if bv) else ''}")

    print("\n8. UNTOUCHED WINDOW (Mar 3 - Apr 6) under stress")
    for name, extra in (('as backtested', 0), ('+0.10% cost every trade', 0.10), ('+0.20% cost every trade', 0.20)):
        Fm = fade_c(MAR); Pm = pb_c(MAR)
        r = res([dict(c, pct=c['pct'] - extra) for c in Fm + Pm], MAR); print(f"   {name:<26} {r['d']:+.3f}%/day ret {r['ret']:+.1f}% trades {r['n']}")


if __name__ == '__main__':
    main()
