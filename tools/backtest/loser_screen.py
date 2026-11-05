#!/usr/bin/env python3
"""Rules that REMOVE losing trades or turn them smaller (governor question 2026-11-04 after v5.2.40: "is there anything that removes loser trades? any rules we can add or edit").
    python3 -I tools/backtest/loser_screen.py [M5.json.gz]
Each candidate is applied ALONE to the rules in force (tunables v3, paper.simulate, one $2,000 account) on the Robinhood 5-minute data:
  filters  : skip entries (one loss ends the day, no late FADE / PULLBACK entries, stricter retest, wider minimum stop, longer wait before the retest, stricter runaway skip)
  exit edits: early cut level, lock trigger and level, take-profit R and share, chandelier multiple, PULLBACK stop buffer, the 'chop' half take-profit
The pass bar, fixed before looking: the account's win rate rises by more than 0.5 point, its %/day does not fall (whole sample, and neither half by more than 0.005),
and its drawdown does not grow by more than 0.25 point. Passers are replayed on Massive bars before 2026-03 (never fitted) and from 2026-03.
In-sample, many candidates: expect one or two to pass by chance. Changes no order, rule or state."""
import contextlib, gzip, io, json, os, statistics as st, sys
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I
M5 = sys.argv[1] if len(sys.argv) > 1 else None
CANDS = [('one loss ends the day', {'x.one_loss_day': True}),
         ('no FADE entry after 10:30', {'x.fade_last_bar': 12}), ('no FADE entry after 11:00', {'x.fade_last_bar': 18}), ('no FADE entry after 11:30', {'x.fade_last_bar': 24}),
         ('no PULLBACK entry at 11:30+', {'x.pb_last_bar': 23}), ('no PULLBACK entry at 12:00+', {'x.pb_last_bar': 29}), ('no PULLBACK entry at 12:30+', {'x.pb_last_bar': 35}),
         ('FADE retest tolerance 0.08%', {'fade.retest_tol_pct': 0.08}), ('FADE retest tolerance 0.06%', {'fade.retest_tol_pct': 0.06}),
         ('FADE retest wait >= 2 bars', {'x.fade_min_wait': 2}), ('FADE retest wait >= 3 bars', {'x.fade_min_wait': 3}),
         ('runaway skip 0.70%', {'x.fade_max_trend': 0.70}), ('runaway skip 0.60%', {'x.fade_max_trend': 0.60}),
         ('PULLBACK min stop 0.85%', {'pb.min_stop_pct': 0.85}), ('PULLBACK min stop 1.00%', {'pb.min_stop_pct': 1.0}),
         ('early cut at -0.3R', {'fade.cut_r': -0.3}), ('early cut at -0.4R', {'fade.cut_r': -0.4}), ('early cut at -0.6R', {'fade.cut_r': -0.6}),
         ('lock trigger 0.4R', {'fade.lock_trigger_r': 0.4}), ('lock trigger 0.6R', {'fade.lock_trigger_r': 0.6}),
         ('lock level 0.0R (breakeven)', {'fade.lock_level_r': 0.0}), ('lock level 0.25R', {'fade.lock_level_r': 0.25}),
         ('FADE take-profit at 1.5R', {'fade.target_r': 1.5}), ('FADE take-profit at 1.75R', {'fade.target_r': 1.75}), ('FADE take-profit at 2.5R', {'fade.target_r': 2.5}),
         ('FADE sells 1/2 at the target', {'fade.take_frac': 0.5}), ('FADE sells 1/4 at the target', {'fade.take_frac': 0.25}),
         ('chandelier 1.5 ATR', {'fade.chandelier_atr': 1.5}), ('chandelier 3.0 ATR', {'fade.chandelier_atr': 3.0}),
         ('PULLBACK stop buffer 0.03%', {'pb.stop_buffer_pct': 0.03}), ('PULLBACK stop buffer 0.10%', {'pb.stop_buffer_pct': 0.10}), ('PULLBACK stop buffer 0.15%', {'pb.stop_buffer_pct': 0.15}),
         ('chop: 3 of first 6 closes red -> 1/2 at 1R', {'x.chop': [3, 1.0]}), ('chop: 4 of first 6 closes red -> 1/2 at 1R', {'x.chop': [4, 1.0]})]


def split(daily, trades, cut):
    a = A.acct(daily, trades); h1 = A.acct([x for x in daily if x[0] < cut], [t for t in trades if t[0] < cut]); h2 = A.acct([x for x in daily if x[0] >= cut], [t for t in trades if t[0] >= cut])
    return a, h1, h2


def judge(label, over, base, cut):
    daily, trades = A.replay(over); a, h1, h2 = split(daily, trades, cut); b, b1, b2 = split(*base, cut)
    key = lambda t: t[:4]; bk = {key(t) for t in base[1]}; ck = {key(t) for t in trades}
    gone = [t for t in base[1] if key(t) not in ck]; new = [t for t in trades if key(t) not in bk]
    losers = [t for t in trades if t[4] < 0]; blosers = [t for t in base[1] if t[4] < 0]
    ok = (a['win'] > b['win'] + 0.5 and a['mean'] >= b['mean'] and h1['mean'] >= b1['mean'] - 0.005 and h2['mean'] >= b2['mean'] - 0.005 and a['dd'] <= b['dd'] + 0.25)
    return dict(label=label, over=over, a=a, h1=h1, h2=h2, gone=gone, new=new, losers=len(losers), loss=sum(t[4] for t in losers), blosers=len(blosers), bloss=sum(t[4] for t in blosers), ok=ok)


def line(r, b, b1, b2):
    a = r['a']; g = r['gone']
    return (f"{'PASS' if r['ok'] else '    '} {r['label']:<44} win {a['win']:3.0f}% ({a['win'] - b['win']:+4.1f})  %/day {a['mean']:+.3f} ({a['mean'] - b['mean']:+.3f}; halves {r['h1']['mean'] - b1['mean']:+.3f}/{r['h2']['mean'] - b2['mean']:+.3f})  "
            f"DD {a['dd']:4.2f}  PF {a['pf']:4.2f}  n {a['n']:3d}  losers {r['losers']:2d} ({r['loss']:+5.1f}%)  removed {len(g):2d} trades (win {100 * sum(1 for t in g if t[4] > 0) / max(len(g), 1):3.0f}%, {sum(t[4] for t in g):+5.1f}%)")


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]; base = A.replay({}); b, b1, b2 = split(*base, cut)
    print(f"{len(A.DAYS)} Robinhood sessions {A.DAYS[0]}..{A.DAYS[-1]}, rules in force (tunables v{I.current(I.tun())['version']}); halves split at {cut}")
    bl = [t for t in base[1] if t[4] < 0]
    print(f"rules in force: win {b['win']:.0f}%  {b['mean']:+.3f}%/day (halves {b1['mean']:+.3f}/{b2['mean']:+.3f})  DD {b['dd']:.2f}%  PF {b['pf']:.2f}  trades {b['n']}  losers {len(bl)} ({sum(t[4] for t in bl):+.1f}% of the account)\n")
    with get_context('fork').Pool(4) as pool: R = pool.starmap(judge, [(l, o, base, cut) for l, o in CANDS])
    for r in sorted(R, key=lambda r: (not r['ok'], -(r['a']['win'] - b['win']))): print(line(r, b, b1, b2))
    P = [r for r in R if r['ok']]
    print(f"\n{len(P)} of {len(R)} pass")
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars)); mb = A.replay({})
        show = P + sorted([r for r in R if not r['ok']], key=lambda r: -(r['a']['win'] - b['win']))[:6]
        for lo, hi, nm in (('0000', '2026-03-01', 'Massive before 2026-03 (never fitted)'), ('2026-03-01', '9999', 'Massive 2026-03 on')):
            seg = lambda d, t: A.acct([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); m0 = seg(*mb)
            print(f"\n{nm}: rules in force win {m0['win']:.0f}% {m0['mean']:+.3f}%/day DD {m0['dd']:.1f}% PF {m0['pf']:.2f} n {m0['n']}")
            for r in show:
                d, t = A.replay(r['over']); a = seg(d, t)
                print(f"  {'PASS ' if r['ok'] else 'near '}{r['label']:<44} win {a['win']:3.0f}% ({a['win'] - m0['win']:+4.1f})  %/day {a['mean']:+.3f} ({a['mean'] - m0['mean']:+.3f})  DD {a['dd']:5.1f}%  PF {a['pf']:4.2f}  n {a['n']}")
