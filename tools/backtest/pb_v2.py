#!/usr/bin/env python3
"""Pullback buy v2 study on the v3.126 Core Five: exits (as done for the fade) + entry checks, judged on both halves.
    python3 tools/backtest/pb_v2.py > tools/backtest/results_pb_v2.txt
Setup = pullback.scan (breakout on volume, EMA9>EMA20, 2-5 bar pullback into the EMA zone, close above prior high, limit entry,
stop 2.5c under the pullback low, room >= 0.75%), entries 10:10-13:00, on the leg's own chart (long only).
Exits: target = morning high of day (current) or R multiple, sold by OCO at the level; fraction sold at the target;
runner = 20-EMA close (current) / breakeven / 2- or 3-ATR chandelier (leg, from breakeven); sell-by time.
Entry check: proxy confirmation = the proxy is on the trade's side of BOTH its own VWAP and 20-EMA at the signal bar.
Costs: 0.01% limit entry, 0.03% exits. Account: $2,000, 3% risk capped at cash, one position at a time, max 3/day.
"""
import itertools, math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, matrix as MX, pb_filters as PF
from lab import get_data

TN = {35: '12:30', 47: '13:30', 59: '14:30', 77: '15:55'}


def scan(b, e9, e20, ok, min_room=0.75, last_k=41):
    bh = max(x[1] for x in b[:3])
    for j in range(8, last_k):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre)); stop = low - 0.025
            lim = b[j][3]
            if b[j + 1][2] > lim: continue
            entry = min(b[j + 1][0], lim)
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < min_room: continue
            if not ok(j): continue
            return dict(k=j + 1, entry=entry, stop=stop, hod=hod, sig=j)
    return None


def setups(D, days, confirm):
    out = []
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]
        for leg, (px, sd) in PF.LEGS.items():
            if d not in D.bars.get(leg, {}) or pd_ not in D.bars.get(leg, {}): continue
            b = D.bars[leg][d]; pb = D.bars[leg][pd_]
            ser = [x[3] for x in pb] + [x[3] for x in b]; e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
            pxb = D.bars[px][d]; pser = [x[3] for x in D.bars[px][pd_]] + [x[3] for x in pxb]; pe20 = m.ema(pser, 20)[78:]
            def ok(j):
                if not confirm: return True
                vw, _ = m.vwap_sd(pxb, j); c = pxb[j][3]
                return sd * (c - vw) > 0 and sd * (c - pe20[j]) > 0
            s = scan(b, e9, e20, ok)
            if s: s.update(day=d, inst=leg, b=b, e20=e20); out.append(s)
    return out


def manage(s, target, frac, runner, last):
    b, k, entry, stop = s['b'], s['k'], s['entry'], s['stop']
    if k > last: return None
    r = entry - stop
    T = s['hod'] if target == 'hod' else entry + float(target) * r
    if T <= entry: T = entry + r
    gross = 0.0; rem = 1.0; hit = False; hic = entry; cost = 0.0001 * entry; xbar = last
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross += rem * (px - entry); cost += rem * 0.0003 * px; rem = 0; xbar = j; break
        if not hit and h >= T:
            px = max(T, o); f = frac; gross += f * (px - entry); cost += f * 0.0003 * px; rem -= f; hit = True
            if rem <= 1e-9: xbar = j; break
            if runner != 'ema20': stop = max(stop, entry)
        hic = max(hic, c)
        if hit and j < last:
            if runner.startswith('chand'): stop = max(stop, hic - float(runner[5:]) * m.atr(b, j))
            elif runner == 'ema20' and c < s['e20'][j]:
                px = b[j + 1][0]; gross += rem * (px - entry); cost += rem * 0.0003 * px; rem = 0; xbar = j + 1; break
    if rem > 1e-9: px = b[last][3]; gross += rem * (px - entry); cost += rem * 0.0003 * px
    pnl = gross - cost
    return dict(day=s['day'], inst=s['inst'], k=k, xbar=xbar, pnl=pnl, risk=r, entry=entry, pct=pnl / entry * 100, hit=hit)


def run(D, days, h, S, target, frac, runner, last):
    sig = [t for s in S for t in [manage(s, target, frac, runner, last)] if t]
    a = P.account(sig, D, days); H1 = set(days[:h])
    d1 = st.mean(P.account([x for x in sig if x['day'] in H1], D, days[:h])['daily'].values())
    d2 = st.mean(P.account([x for x in sig if x['day'] not in H1], D, days[h:])['daily'].values())
    return sig, a, d1, d2


def main():
    D = get_data(); m.rvol = MX.safe_rvol; m.LEGS = PF.LEGS
    days = D.days[25:]; h = len(days) // 2
    print(f"Pullback buy v2, v3.126 Core Five legs, {days[0]}..{days[-1]} ({len(days)} days). Fade reference (1/3 at 2R + chandelier, 13:30): +0.258%/day, H2 +0.200.\n")
    S0 = setups(D, days, False); S1 = setups(D, days, True)
    print(f"setups: {len(S0)} without proxy confirmation, {len(S1)} with it\n")
    cur = ('hod', 0.6, 'ema20', 77)
    for S, lab in ((S0, 'no proxy check'), (S1, 'proxy confirms')):
        sig, a, d1, d2 = run(D, days, h, S, *cur)
        print(f"CURRENT EXIT (60% at morning high, rest on 20-EMA close, hold to 15:55), {lab}: trades {len(a['taken'])}, "
              f"{st.mean(a['daily'].values()):+.3f}%/day, ret {a['ret']:+.1f}%, DD {a['mdd']:.1f}%, H1 {d1:+.3f} H2 {d2:+.3f}")
    rows = []
    for (S, conf), target, frac, runner, last in itertools.product(((S0, False), (S1, True)), ('hod', '1.5', '2', '3'), (0.33, 0.5, 0.6, 1.0),
                                                                  ('ema20', 'be', 'chand2', 'chand3'), (47, 59, 77)):
        if frac == 1.0 and runner != 'be': continue
        sig, a, d1, d2 = run(D, days, h, S, target, frac, runner, last)
        rows.append(((conf, target, frac, runner, last), st.mean(a['daily'].values()), a['ret'], a['mdd'], d1, d2, len(a['taken'])))
    lab = lambda c: (f"{'proxy-check ' if c[0] else ''}{'all' if c[2] == 1 else f'{int(round(c[2]*100))}%'} at "
                     f"{'morning high' if c[1] == 'hod' else c[1] + 'R'}, runner {c[3]}, by {TN[c[4]]}")
    print(f"\n== Grid: {len(rows)} combinations (top 20 by full period) ==")
    print(f"{'exit / entry check':<62}{'trd':>4}{'%/day':>8}{'ret%':>8}{'DD':>6}{'H1':>8}{'H2':>8}")
    for c, dd, ret, mdd, a1, a2, n in sorted(rows, key=lambda r: -r[1])[:20]:
        print(f"{lab(c):<62}{n:>4}{dd:>+8.3f}{ret:>+8.1f}{mdd:>6.1f}{a1:>+8.3f}{a2:>+8.3f}")
    print(f"   positive in both halves: {sum(r[4] > 0 and r[5] > 0 for r in rows)} of {len(rows)}")
    print("\n   Averages by each choice (%/day overall / H2):")
    for i, name in enumerate(('proxy check', 'target', 'fraction', 'runner', 'sell-by')):
        g = collections.defaultdict(list)
        for r in rows: g[r[0][i]].append(r)
        print(f"     {name:<12}" + '  '.join(f"{(TN[k] if i == 4 else k)}: {st.mean(x[1] for x in v):+.3f}/{st.mean(x[5] for x in v):+.3f}" for k, v in g.items()))
    best = max(rows, key=lambda r: r[4])
    print(f"\n   WALK-FORWARD: best on H1 = {lab(best[0])} (H1 {best[4]:+.3f}) -> H2 {best[5]:+.3f}")
    c0 = [r for r in rows if r[0] == (False,) + cur][0]
    print(f"   current exit: H1 {c0[4]:+.3f} -> H2 {c0[5]:+.3f}")
    # where do pullback trades make / lose money under the current exit
    sig, a, _, _ = run(D, days, h, S0, *cur)
    g = collections.defaultdict(lambda: [0, 0.0])
    for x in a['taken']: g[x['inst']][0] += 1; g[x['inst']][1] += x['usd']
    print("\n   current exit, by ticker: " + ', '.join(f"{k} {n}tr {u:+.0f}$" for k, (n, u) in sorted(g.items(), key=lambda kv: -kv[1][1])))


if __name__ == '__main__':
    main()
