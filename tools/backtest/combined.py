#!/usr/bin/env python3
"""Combined system test: pullback buy + failed-retest fade with the governor's fade exit, v3.126 Core Five.
    python3 tools/backtest/combined.py > tools/backtest/results_combined.txt
FADE exit: stop beyond the failed breakout's extreme; 1/3 off at 2R (OCO, at the level); rest from breakeven, 2-ATR chandelier
ratchet at checkpoints; sell what's left at 13:30.   PB: pullback buy, live-realistic (as pb_filters.run), hold to 15:55.
Account: $2,000, 3% risk capped at cash, max 3 entries/day. Modes:
  one      = one position at a time; a later setup waits until the open trade closes (rulebook E2)
  pb_first = one position at a time, but a pullback signal closes an open fade (at that checkpoint) and takes the cash
  two      = two positions at once, half the cash each (one fade slot, one pullback slot)
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, matrix as MX, pb_filters as PF, fade_combo as FC, twobar as TB, mixed as MXD
from lab import get_data

FADE_KW = dict(R=2.0, frac=1 / 3, runner='chand2')


def fades(D, days, last):
    return MXD.norm_px([t for d in days for p in TB.ROWS for t in [FC.run_trade(D, d, p, last=last, **FADE_KW)] if t], 'FADE')


def account_pb_first(D, days, PB, FD, last, risk=0.03, start=2000.0, max_entries=3):
    """One position; an arriving pullback closes an open fade at the pullback's entry checkpoint."""
    pbd = collections.defaultdict(list); fdd = collections.defaultdict(list)
    for c in PB: pbd[c['day']].append(c)
    for c in FD: fdd[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []
    for d in days:
        e0 = eq; n = 0; free = 0
        cs = sorted(pbd.get(d, []) + fdd.get(d, []), key=lambda c: c['k'])
        while cs and n < max_entries:
            av = [c for c in cs if c['k'] >= free]
            if not av: break
            c = min(av, key=lambda c: (c['k'], -TB.rvol(D, c['proxy'], d, c['k'])))
            cs.remove(c)
            if c['sys'] == 'FADE':
                nxt = [x for x in cs if x['sys'] == 'PB' and c['k'] < x['k'] <= c['xbar']]
                if nxt:   # a pullback arrives while the fade is open -> cut the fade at that checkpoint
                    kp = min(x['k'] for x in nxt)
                    t = FC.run_trade(D, d, c['proxy'], last=kp - 1, **FADE_KW)
                    if t: c = MXD.norm_px([t], 'FADE')[0]; c['cut'] = True
            notional = min(eq, eq * risk / (c['risk'] / 100)); pnl = notional * c['pct'] / 100
            eq += pnl; taken.append(dict(c, usd=pnl)); free = c['xbar'] + 1; n += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken)


def show(name, a, days, h):
    dl = a['daily']; tk = a['taken']; mix = collections.Counter(c['sys'] for c in tk)
    sd = st.pstdev(dl.values()); shp = st.mean(dl.values()) / sd * math.sqrt(252) if sd else 0
    cut = sum(1 for c in tk if c.get('cut'))
    print(f"{name:<46} trades {len(tk):3d} (PB {mix.get('PB',0)}, FADE {mix.get('FADE',0)}{f', {cut} fades cut' if cut else ''}) win {100*sum(c['usd']>0 for c in tk)/max(len(tk),1):3.0f}% "
          f"{st.mean(dl.values()):+.3f}%/day ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}% H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f} Sharpe~{shp:.1f}")


def main():
    D = get_data(); m.rvol = MX.safe_rvol
    days = D.days[25:]; h = len(days) // 2
    PB = MXD.norm_pb(PF.run(D, days, 77, True))
    print(f"Combined pullback + fade, v3.126 Core Five, {days[0]}..{days[-1]} ({len(days)} days). Goal +0.400%/day.")
    print("FADE exit: 1/3 at 2R (OCO) + 2-ATR chandelier, sell-by as shown. PB: hold to 15:55.\n")
    print("== Each alone ==")
    show('Pullback alone', MXD.account(D, days, PB), days, h)
    for last, lab in ((47, '13:30'),):
        show(f'Fade alone (sell by {lab})', MXD.account(D, days, fades(D, days, last)), days, h)
    print("\n== Combined, fade sell-by 13:30 ==")
    FD = fades(D, days, 47)
    show('one position at a time', MXD.account(D, days, PB + FD), days, h)
    show('one position, pullback cuts an open fade', account_pb_first(D, days, PB, FD, 47), days, h)
    show('two positions (half cash each)', MXD.account(D, days, PB + FD, mode='two'), days, h)
    print("\n== Same, other fade sell-by times (for comparison) ==")
    for last, lab in ((35, '12:30'), (77, '15:55')):
        F2 = fades(D, days, last)
        show(f'one position, fade by {lab}', MXD.account(D, days, PB + F2), days, h)
        show(f'pullback cuts fade, fade by {lab}', account_pb_first(D, days, PB, F2, last), days, h)
        show(f'two positions, fade by {lab}', MXD.account(D, days, PB + F2, mode='two'), days, h)
    print("\n== Detail: one position at a time, fade by 13:30 ==")
    a = MXD.account(D, days, PB + FD)
    mo = collections.defaultdict(float)
    for c in a['taken']: mo[c['day'][:7]] += c['usd']
    print('   by month: ' + ', '.join(f"{k} {v:+.0f}$" for k, v in sorted(mo.items())))
    by = collections.defaultdict(lambda: [0, 0.0])
    for c in a['taken']: by[(c['sys'], c['proxy'])][0] += 1; by[(c['sys'], c['proxy'])][1] += c['usd']
    print('   by system/proxy: ' + ', '.join(f"{s}-{p} {n}tr {u:+.0f}$" for (s, p), (n, u) in sorted(by.items())))
    dl = list(a['daily'].values())
    print(f"   days traded {sum(1 for v in dl if v != 0)} of {len(dl)}; best day {max(dl):+.2f}%, worst day {min(dl):+.2f}%; "
          f"losing days {sum(1 for v in dl if v < 0)}, winning days {sum(1 for v in dl if v > 0)}")
    skipped = len(PB) - sum(1 for c in a['taken'] if c['sys'] == 'PB')
    print(f"   pullback setups skipped because the account was busy or the day's 3 entries were used: {skipped} of {len(PB)}")


if __name__ == '__main__':
    main()
