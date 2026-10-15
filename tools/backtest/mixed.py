#!/usr/bin/env python3
"""Mixed selection: pullback buy + ORB-family setups on the v3.126 Core Five, one account.
    python3 tools/backtest/mixed.py > tools/backtest/results_mixed.txt
Components (all live-realistic: checkpoint entries, target sales at the next checkpoint, hold to 15:55):
  PB   = first-pullback buy (pb_filters.run), leg charts, room >= 0.75%, limit entry
  FADE = failed-retest fade (retest.RC(fade=True)): proxy breaks the 9:30-10:00 box, retests the edge and closes back inside -> opposite leg
  ORB  = plain 2-bar ORB, live (twobar.Cfg(entry='checkpoint', delayed_tp=True)) - for comparison only
Account: $2,000, 3% risk capped at cash, max 3 entries/day.
  'one'  = one position at a time (rulebook E2); simultaneous candidates broken by priority rule.
  'two'  = up to two positions at once, each capped at half the cash (one slot per system family).
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, matrix as MX, pb_filters as PF, retest as RT, twobar as TB
from lab import get_data


def norm_pb(sig):
    return [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PF.LEGS[x['inst']][0], k=x['k'], xbar=x['xbar'],
                 pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in sig]


def norm_px(T, tag):
    return [dict(day=t['day'], sys=tag, name=t['proxy'] + ('+' if t['side'] > 0 else '-'), proxy=t['proxy'], k=t['k'], xbar=t['xbar'],
                 pct=t['pct'], risk=t['leg_risk']) for t in T]


def account(D, days, cands, mode='one', priority=None, risk=0.03, start=2000.0, max_entries=3):
    by = collections.defaultdict(list)
    for c in cands: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []
    for d in days:
        e0 = eq; cs = sorted(by.get(d, []), key=lambda c: c['k']); n = 0
        if mode == 'one':
            free = 0
            while cs and n < max_entries:
                av = [c for c in cs if c['k'] >= free]
                if not av: break
                k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
                if priority: same.sort(key=lambda c: (priority.index(c['sys']), -TB.rvol(D, c['proxy'], d, c['k'])))
                else: same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k']))
                c = same[0]
                notional = min(eq, eq * risk / (c['risk'] / 100)); pnl = notional * c['pct'] / 100
                eq += pnl; taken.append(dict(c, usd=pnl)); free = c['xbar'] + 1; cs.remove(c); n += 1
        else:   # two slots: one per family (PB vs proxy-driven), each half the cash
            fam = lambda c: 'PB' if c['sys'] == 'PB' else 'PX'
            free = {'PB': 0, 'PX': 0}; pnl_day = 0.0
            for c in cs:
                f = fam(c)
                if n >= max_entries or c['k'] < free[f]: continue
                notional = min(e0 / 2, e0 * risk / (c['risk'] / 100)); pnl = notional * c['pct'] / 100
                pnl_day += pnl; taken.append(dict(c, usd=pnl)); free[f] = c['xbar'] + 1; n += 1
            eq += pnl_day
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken)


def show(name, a, days, h):
    dl = a['daily']; tk = a['taken']; ndays = sum(1 for v in dl.values() if v != 0)
    mix = collections.Counter(c['sys'] for c in tk)
    sd = st.pstdev(dl.values()); shp = st.mean(dl.values()) / sd * math.sqrt(252) if sd else 0
    print(f"{name:<52} trades {len(tk):3d} ({dict(mix)}) win {100*sum(c['usd']>0 for c in tk)/max(len(tk),1):3.0f}% {st.mean(dl.values()):+.3f}%/day "
          f"ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}% trade-days {ndays} H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f} Sharpe~{shp:.1f}")


def main():
    D = get_data(); m.rvol = MX.safe_rvol
    days = D.days[25:]; h = len(days) // 2
    PB = norm_pb(PF.run(D, days, 77, True))
    FD = norm_px([t for d in days for p in TB.ROWS for t in [RT.trade(D, d, p, RT.RC(fade=True))] if t], 'FADE')
    OR = norm_px([t for d in days for p in TB.ROWS for t in [TB.trade(D, d, p, TB.Cfg(entry='checkpoint', delayed_tp=True))] if t], 'ORB')
    print(f"Mixed selection, v3.126 Core Five, {days[0]}..{days[-1]} ({len(days)} days). Candidates: PB {len(PB)}, FADE {len(FD)}, ORB {len(OR)}.\n")
    print("== Overlap ==")
    dp = set(c['day'] for c in PB); df = set(c['day'] for c in FD)
    print(f"   days with a PB setup {len(dp)}, with a FADE setup {len(df)}, both {len(dp & df)}, either {len(dp | df)} of {len(days)}")
    a_pb = account(D, days, PB); a_fd = account(D, days, FD)
    x = [a_pb['daily'][d] for d in days]; y = [a_fd['daily'][d] for d in days]
    mx, my = st.mean(x), st.mean(y)
    cor = sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    print(f"   correlation of daily results PB vs FADE: {cor:+.2f}  (near 0 = they diversify each other)\n")
    print("== Each alone ==")
    show('Pullback buy alone', a_pb, days, h)
    show('Failed-retest fade alone', a_fd, days, h)
    show('Plain 2-bar ORB alone', account(D, days, OR), days, h)
    print("\n== Mixed, one position at a time ==")
    show('PB + FADE, earliest first, RVOL tie-break', account(D, days, PB + FD), days, h)
    show('PB + FADE, earliest first, FADE wins ties', account(D, days, PB + FD, priority=['FADE', 'PB']), days, h)
    show('PB + FADE, earliest first, PB wins ties', account(D, days, PB + FD, priority=['PB', 'FADE']), days, h)
    show('PB + plain ORB (comparison)', account(D, days, PB + OR), days, h)
    show('PB + FADE + plain ORB (comparison)', account(D, days, PB + FD + OR), days, h)
    print("\n== Mixed, two slots (one PB + one ORB-family position at once, half cash each) ==")
    show('PB + FADE, two slots', account(D, days, PB + FD, mode='two'), days, h)
    show('PB + plain ORB, two slots (comparison)', account(D, days, PB + OR, mode='two'), days, h)
    print("\n== Months (PB + FADE, one at a time, RVOL tie-break) ==")
    a = account(D, days, PB + FD); mo = collections.defaultdict(float)
    for c in a['taken']: mo[c['day'][:7]] += c['usd']
    print('   ' + ', '.join(f"{k} {v:+.0f}$" for k, v in sorted(mo.items())))
    by = collections.defaultdict(lambda: [0, 0.0])
    for c in a['taken']: by[(c['sys'], c['proxy'])][0] += 1; by[(c['sys'], c['proxy'])][1] += c['usd']
    print('   by system/proxy: ' + ', '.join(f"{s}-{p} {n}tr {u:+.0f}$" for (s, p), (n, u) in sorted(by.items())))


if __name__ == '__main__':
    main()
