#!/usr/bin/env python3
"""PULLBACK stop-distance CAP (governor request 2026-11-05 after the SOXS stop of 1.89%: "make these tests").
    python3 -I tools/backtest/pb_max_stop_screen.py [M5.json.gz]
A research-only copy of paper.pullback skips a setup whose stop is farther than CAP % below the entry (the live code has a floor, pb.min_stop_pct, and no cap).
Caps 2.0, 1.75, 1.5, 1.25, 1.0, alone and with the 0.85 floor. Rules in force (tunables v3), one $2,000 account. Pass bar = REMOVE bar of loser_screen.py:
win rate up > 0.5 point, %/day not lower (halves -0.005 at most), DD +0.25 at most. Massive replay before 2026-03 (never fitted) and from 2026-03. Changes no order, rule or state."""
import contextlib, gzip, inspect, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
name = [n for n in dir(paper) if n in ('pullback',)][0]
src = inspect.getsource(paper.pullback)
for old, new in (('(lim - stop) / lim * 100 < PB_MIN_STOP:', '(lim - stop) / lim * 100 < PB_MIN_STOP or (lim - stop) / lim * 100 > PB_CAP:'),
                 ('(ref - stop) / ref * 100 < PB_MIN_STOP:', '(ref - stop) / ref * 100 < PB_MIN_STOP or (ref - stop) / ref * 100 > PB_CAP:')):
    assert src.count(old) == 1, old; src = src.replace(old, new)
paper.PB_CAP = 99.0
exec(compile(src, 'pb_cap_copy', 'exec'), paper.__dict__)
CANDS = [('live (no cap)', {}, 99.0)] + [(f'cap {c:.2f}%', {}, c) for c in (2.0, 1.75, 1.5, 1.25, 1.0)] + [(f'cap {c:.2f}% + floor 0.85%', {'pb.min_stop_pct': 0.85}, c) for c in (1.75, 1.5, 1.25)]


def run(over, cap):
    paper.PB_CAP = cap
    try: return A.replay(over)
    finally: paper.PB_CAP = 99.0


def row(label, d, t, b):
    a = A.acct(d, t); pb = [x for x in t if x[1] == 'PB']; w = 100 * sum(1 for x in pb if x[4] > 0) / max(len(pb), 1)
    worst = min([x[4] for x in pb] or [0])
    return f"{label:<30} %/day {a['mean']:+.3f} ({a['mean'] - b['mean']:+.3f}) win {a['win']:3.0f}% ({a['win'] - b['win']:+4.1f}) DD {a['dd']:5.2f} PF {a['pf']:4.2f} n {a['n']:3d} | PB n {len(pb):2d} win {w:3.0f}% worst {worst:+.2f}%"


def table(title, getter, lo='0000', hi='9999'):
    seg = lambda d, t: ([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi])
    base = A.acct(*seg(*getter({}, 99.0))); print(f"\n{title}")
    for label, over, cap in CANDS:
        d, t = seg(*getter(over, cap)); print('  ' + row(label, d, t, base))


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]
    print(f"{len(A.DAYS)} Robinhood sessions, rules in force (tunables v{I.current(I.tun())['version']}), halves split at {cut}")
    table('Robinhood, whole sample', run); table(f'Robinhood first half (< {cut})', run, '0', cut); table(f'Robinhood second half (>= {cut})', run, cut, '9')
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars))
        table('Massive before 2026-03 (never fitted)', run, '0000', '2026-03-01'); table('Massive 2026-03 on', run, '2026-03-01', '9999')
