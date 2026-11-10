#!/usr/bin/env python3
"""PULLBACK entry order type (governor question 2026-11-10: "would a market buy be better or stick with limit?").
    python3 -I tools/backtest/pb_entry_screen.py [M5.json.gz]
Live rule: limit buy at the trigger-bar close, valid for the next bar only; no fill if the next bar's low stays above it (then no trade).
Variants (research copy only, live code untouched): CHASE c = a marketable limit at trigger close x (1 + c%), placed at the start of the next bar.
  It fills at the next open if the open is at or under the cap, else at the cap if the bar's low reaches it, else no trade. c = 0 is the live rule. c = 99 is a market buy at the next open.
The skip rules (reward and stop-distance, B3.7) judge the setup at the actual fill price, as the engine already does for a repriced fill. Sizing, stop (dip low), target (morning high) and the OCO are unchanged.
Pass bar (fixed before looking): the variant beats the live rule on the account %/day and on the PULLBACK trades' average, with drawdown no more than +0.5 worse, in both halves. Massive replay for the best."""
import contextlib, gzip, inspect, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
src = inspect.getsource(paper.pullback)
old = "            if b[j + 1][2] > lim: continue\n            entry = min(b[j + 1][0], lim); ref = lim if X_PBSIG else entry"
new = "            cap = lim * (1 + PB_CHASE / 100)\n            if b[j + 1][2] > cap: continue\n            entry = min(b[j + 1][0], cap); ref = lim if X_PBSIG else entry"
assert src.count(old) == 1
paper.PB_CHASE = 0.0
exec(compile(src.replace(old, new), 'pb_entry_copy', 'exec'), paper.__dict__)
GRID = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0, 99.0]


def run(c):
    paper.PB_CHASE = c
    try: return A.replay({})
    finally: paper.PB_CHASE = 0.0


def pbs(t): return [x for x in t if x[1] in ('PB', 'PULLBACK')]


def line(c, d, t, base, cut):
    a = A.acct(d, t); b = A.acct(*base); p = pbs(t); bp = pbs(base[1]); s = lambda l: sum(x[4] for x in l)
    w = 100 * sum(1 for x in p if x[4] > 0) / max(len(p), 1)
    h1 = s([x for x in p if x[0] < cut]); h2 = s([x for x in p if x[0] >= cut])
    return (f"chase {c:>5g}%  PB n {len(p):3d} win {w:3.0f}% avg {s(p) / max(len(p), 1):+.3f}% halves {h1:+6.1f}/{h2:+6.1f} | acct {a['mean']:+.3f} ({a['mean'] - b['mean']:+.3f}) win {a['win']:3.0f}% DD {a['dd']:4.2f} ({a['dd'] - b['dd']:+.2f}) PF {a['pf']:.2f}"), a, p


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]
    base = run(0.0); b = A.acct(*base); chk = A.acct(*A.replay({})); assert abs(chk['mean'] - b['mean']) < 1e-9, 'chase 0 must equal the live engine'
    print(f"{len(A.DAYS)} Robinhood sessions, halves split at {cut}; chase 0 equals the live engine\nrules in force: {b['mean']:+.3f}%/day win {b['win']:.0f}% DD {b['dd']:.2f}% PF {b['pf']:.2f} trades {b['n']} (PB {len(pbs(base[1]))})\n")
    R = []
    for c in GRID:
        d, t = run(c); l, a, p = line(c, d, t, base, cut); print(l); R.append((c, a, p))
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars)); mb = run(0.0)
        for lo, hi, title in (('0000', '2026-03-01', 'Massive before 2026-03 (never fitted)'), ('2026-03-01', '9999', 'Massive 2026-03 on')):
            seg = lambda d, t: ([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); m0 = A.acct(*seg(*mb)); mp = pbs(seg(*mb)[1])
            print(f"\n{title}: live rule {m0['mean']:+.3f}%/day win {m0['win']:.0f}% DD {m0['dd']:.1f}% n {m0['n']} (PB {len(mp)} avg {sum(x[4] for x in mp) / max(len(mp), 1):+.3f}%)")
            for c in GRID[1:]:
                d, t = seg(*run(c)); a = A.acct(d, t); p = pbs(t)
                print(f"  chase {c:>5g}%  PB n {len(p):3d} win {100 * sum(1 for x in p if x[4] > 0) / max(len(p), 1):3.0f}% avg {sum(x[4] for x in p) / max(len(p), 1):+.3f}% | acct {a['mean']:+.3f} ({a['mean'] - m0['mean']:+.3f}) win {a['win']:3.0f}% DD {a['dd']:5.1f}%")
