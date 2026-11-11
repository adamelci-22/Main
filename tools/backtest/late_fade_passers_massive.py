#!/usr/bin/env python3
"""Massive replay (before 2026-03 never fitted, and 2026-03 on) of the five late-fade variants that passed the ADD bar on Robinhood data (late_fade_size_screen_2026-11-11)."""
import contextlib, gzip, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, late_fade_size_screen as L
M5 = sys.argv[1]
PASS = [dict(e=15, s='high', t=None, f=False, mw=1, dp=0.20, r=1.5, fr=1 / 3, sz=sz, idle=idle) for sz, idle in ((1.0, True), (0.5, False), (0.5, True), (0.33, False), (0.33, True))]
with contextlib.redirect_stdout(io.StringIO()):
    import backtest as BT, lab
    _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
    BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
A.setup(DM, sorted(DM.bars)); mb = L.run(None)
for lo, hi, title in (('0000', '2026-03-01', 'Massive before 2026-03 (never fitted)'), ('2026-03-01', '9999', 'Massive 2026-03 on')):
    seg = lambda d, t: ([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); m0 = A.acct(*seg(*mb))
    print(f"\n{title}: live rule {m0['mean']:+.3f}%/day win {m0['win']:.0f}% DD {m0['dd']:.1f}% n {m0['n']}", flush=True)
    for p in PASS:
        d, t = seg(*L.run(p)); a = A.acct(d, t); ct = [x for x in t if x[1] == 'CONT']
        print(f"  {L.nm(p)}  CONT n {len(ct):3d} win {100 * sum(1 for x in ct if x[4] > 0) / max(len(ct), 1):3.0f}% avg {sum(x[4] for x in ct) / max(len(ct), 1):+.3f}% | acct {a['mean']:+.3f} ({a['mean'] - m0['mean']:+.3f}) win {a['win']:3.0f}% DD {a['dd']:5.1f}% (live {m0['dd']:.1f}%)", flush=True)
