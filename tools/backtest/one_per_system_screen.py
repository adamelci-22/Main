#!/usr/bin/env python3
"""Rule: no trading the same system twice per day (governor question 2026-11-05).
    python3 -I tools/backtest/one_per_system_screen.py [M5.json.gz]
Research-only copy of paper.simulate with a day limit on taken trades. Modes:
  live            : no limit
  1 per system    : a system (FADE or PB) takes at most 1 trade per day
  1 per system, only after a loss : the same system is blocked for the day only after it lost
  1 trade a day   : one trade in total
  PB cap 2/day    : PULLBACK at most 2 trades per day
Rules in force (tunables v3), one $2,000 account. Pass bar (REMOVE bar of loser_screen.py): win rate up > 0.5 point, %/day not lower (halves -0.005 at most), DD +0.25 at most.
Changes no order, rule or state."""
import contextlib, gzip, inspect, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
src = inspect.getsource(paper.simulate)
old = "        if streak >= LOCKOUT_LOSSES:\n            c['why_skipped'] = 'LOCKOUT (5 losses in a row)'"
new = ("        if MODE == 'sys' and any(x['system'] == c['system'] for x in taken): c['why_skipped'] = 'same system twice'; skipped.append(c); continue\n"
       "        if MODE == 'sysloss' and any(x['system'] == c['system'] and x['status'] == 'closed' and x['usd'] < 0 for x in taken): c['why_skipped'] = 'same system after loss'; skipped.append(c); continue\n"
       "        if MODE == 'one' and taken: c['why_skipped'] = 'one trade a day'; skipped.append(c); continue\n"
       "        if MODE == 'pb2' and c['system'] == 'PB' and sum(1 for x in taken if x['system'] == 'PB') >= 2: c['why_skipped'] = 'PB 2 a day'; skipped.append(c); continue\n" + old)
assert src.count(old) == 1; src = src.replace(old, new)
paper.MODE = None
exec(compile(src, 'one_per_system_copy', 'exec'), paper.__dict__)
CANDS = [('live', None), ('1 per system a day', 'sys'), ('1 per system, only after a loss', 'sysloss'), ('PB at most 2 a day', 'pb2'), ('1 trade a day in total', 'one')]


def run(mode):
    paper.MODE = mode
    try: return A.replay({})
    finally: paper.MODE = None


def table(title, getter, lo='0000', hi='9999'):
    seg = lambda d, t: ([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); print(f"\n{title}"); base = None
    for label, mode in CANDS:
        d, t = seg(*getter(mode)); a = A.acct(d, t); base = base or a
        n2 = len({x[0] for x in t if sum(1 for y in t if y[0] == x[0] and y[1] == x[1]) > 1})
        print(f"  {label:<32} %/day {a['mean']:+.3f} ({a['mean'] - base['mean']:+.3f}) win {a['win']:3.0f}% ({a['win'] - base['win']:+4.1f}) DD {a['dd']:5.2f} PF {a['pf']:4.2f} n {a['n']:3d} | days with the same system twice: {n2}")


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]
    base = run(None); chk = A.acct(*A.replay({})); assert abs(A.acct(*base)['mean'] - chk['mean']) < 1e-9
    table('Robinhood, whole sample', run); table(f'Robinhood first half (< {cut})', run, '0', cut); table(f'Robinhood second half (>= {cut})', run, cut, '9')
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars))
        table('Massive before 2026-03 (never fitted)', run, '0000', '2026-03-01'); table('Massive 2026-03 on', run, '2026-03-01', '9999')
