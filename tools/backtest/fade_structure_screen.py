#!/usr/bin/env python3
"""FADE structure: the five built-in constants of paper.fade, varied together (governor question 2026-11-04: "what about other fade changes same treatment").
    python3 -I tools/backtest/fade_structure_screen.py [M5.json.gz]
A research-only copy of paper.fade (this process only; the live code is not touched) takes:
  box     opening box length in 5-minute bars: 6 = 30 min (live), 4, 3, 2
  brk     last bar index a break may close on (exclusive): 9 = through the 10:10 bar (live), 10, 12
  rw      bars after the break the retest may come in: 12 (live), 6, 9, 18
  depth   the retest bar must close this % back inside the box edge: 0 (live), 0.05, 0.10
  sbuf    stop placed this % beyond the break-to-retest extreme: 0 (live), 0.05, 0.10
Entries before 10:00 are dropped (the live checkpoints start at 10:00). Everything else is the rules in force (tunables v3), one $2,000 account.
Two pass bars, fixed before looking, the same as add_trades_screen.py and loser_screen.py:
  ADD   : FADE trades added (not in the live run) win >= 60%, average > +0.1% of the account, positive in both halves; the account keeps its %/day and win rate; DD +0.5 at most
  REMOVE: the account win rate rises > 0.5 point; %/day does not fall (halves -0.005 at most); DD +0.25 at most
Passers and the best near-misses are replayed on Massive bars before 2026-03 (never fitted) and from 2026-03. In-sample, 432 combinations: expect chance passers.
Changes no order, rule or state."""
import contextlib, gzip, inspect, io, itertools, json, os, statistics as st, sys
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
src = inspect.getsource(paper.fade)
for old, new in (('if K < 8: return None', 'if K < FB_BOX + 2: return None'), ('max(x[1] for x in b[:6]), min(x[2] for x in b[:6])', 'max(x[1] for x in b[:FB_BOX]), min(x[2] for x in b[:FB_BOX])'), ('range(6, min(9, K))', 'range(FB_BOX, min(FB_END, K))'),
                 ('min(j + 13, 76)', 'min(j + 1 + FB_RW, 76)'), ('if cc < E:', 'if cc < E * (1 - FB_DEPTH / 100):'),
                 ('stop_real = to_m(max(bb[q][1] for q in range(j, i + 1)))', 'stop_real = to_m(max(bb[q][1] for q in range(j, i + 1)) * (1 + FB_SBUF / 100))\n                    if i + 1 < 6: return None')):
    assert src.count(old) == 1, old; src = src.replace(old, new)
paper.FB_BOX, paper.FB_END, paper.FB_RW, paper.FB_DEPTH, paper.FB_SBUF = 6, 9, 12, 0.0, 0.0
exec(compile(src, 'fade_research_copy', 'exec'), paper.__dict__)
GRID = {'box': [6, 4, 3, 2], 'brk': [9, 10, 12], 'rw': [12, 6, 9, 18], 'depth': [0.0, 0.05, 0.10], 'sbuf': [0.0, 0.05, 0.10]}
LIVE = {k: v[0] for k, v in GRID.items()}


def runp(p):
    paper.FB_BOX, paper.FB_END, paper.FB_RW, paper.FB_DEPTH, paper.FB_SBUF = p['box'], max(p['brk'], p['box'] + 1), p['rw'], p['depth'], p['sbuf']
    try: return A.replay({})
    finally: paper.FB_BOX, paper.FB_END, paper.FB_RW, paper.FB_DEPTH, paper.FB_SBUF = 6, 9, 12, 0.0, 0.0


def judge(p, base, cut):
    daily, trades = runp(p); a = A.acct(daily, trades); b = A.acct(*base)
    h = lambda d, t, lo, hi: A.acct([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi])
    a1, a2, b1, b2 = h(daily, trades, '0', cut), h(daily, trades, cut, '9'), h(*base, '0', cut), h(*base, cut, '9')
    key = lambda t: t[:4]; bk = {key(t) for t in base[1]}; ck = {key(t) for t in trades}
    add = [t for t in trades if key(t) not in bk and t[1] == 'FADE']; gone = [t for t in base[1] if key(t) not in ck]
    fa = [t for t in trades if t[1] == 'FADE']; s = lambda l: sum(t[4] for t in l)
    aw = 100 * sum(1 for t in add if t[4] > 0) / len(add) if add else 0.0
    ok_add = (len(add) >= 3 and aw >= 60 and s(add) / len(add) > 0.1 and s([t for t in add if t[0] < cut]) > 0 and s([t for t in add if t[0] >= cut]) > 0
              and a['mean'] >= b['mean'] and a['win'] >= b['win'] and a['dd'] <= b['dd'] + 0.5)
    ok_rem = (a['win'] > b['win'] + 0.5 and a['mean'] >= b['mean'] and a1['mean'] >= b1['mean'] - 0.005 and a2['mean'] >= b2['mean'] - 0.005 and a['dd'] <= b['dd'] + 0.25)
    return dict(p=p, a=a, h1=a1['mean'] - b1['mean'], h2=a2['mean'] - b2['mean'], add=len(add), addwin=aw, addsum=s(add), gone=len(gone), gonesum=s(gone),
                fn=len(fa), fwin=100 * sum(1 for t in fa if t[4] > 0) / max(len(fa), 1), fsum=s(fa), ok_add=ok_add, ok_rem=ok_rem)


def nm(p): d = [f"{k} {v}" for k, v in p.items() if v != LIVE[k]]; return 'LIVE FADE' if not d else ', '.join(d)


def line(r, b):
    a = r['a']; tag = ('ADD ' if r['ok_add'] else '') + ('REM ' if r['ok_rem'] else '')
    return (f"{tag:<8} {nm(r['p']):<38} acct {a['mean']:+.3f} ({a['mean'] - b['mean']:+.3f}; halves {r['h1']:+.3f}/{r['h2']:+.3f}) win {a['win']:3.0f}% ({a['win'] - b['win']:+4.1f}) DD {a['dd']:4.2f} PF {a['pf']:4.2f} | "
            f"FADE n {r['fn']:3d} win {r['fwin']:3.0f}% total {r['fsum']:+5.1f}% | adds {r['add']:2d} ({r['addwin']:3.0f}% win, {r['addsum']:+5.1f}%) removes {r['gone']:2d} ({r['gonesum']:+5.1f}%)")


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]
    base = runp(LIVE); b = A.acct(*base); chk = A.acct(*A.replay({}))
    assert abs(chk['mean'] - b['mean']) < 1e-9 and chk['n'] == b['n'], 'research copy at live settings must equal the live engine'
    fb = [t for t in base[1] if t[1] == 'FADE']
    print(f"{len(A.DAYS)} Robinhood sessions {A.DAYS[0]}..{A.DAYS[-1]}, rules in force (tunables v{I.current(I.tun())['version']}); the research copy at live settings equals the live engine")
    print(f"rules in force: {b['mean']:+.3f}%/day win {b['win']:.0f}% DD {b['dd']:.2f}% PF {b['pf']:.2f} trades {b['n']} | FADE {len(fb)} trades win {100 * sum(1 for t in fb if t[4] > 0) / len(fb):.0f}% total {sum(t[4] for t in fb):+.1f}%\n")
    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    with get_context('fork').Pool(4) as pool: R = pool.starmap(judge, [(p, base, cut) for p in combos])
    print("ONE CHANGE AT A TIME (each constant moved alone)")
    for r in R:
        if sum(r['p'][k] != LIVE[k] for k in GRID) == 1: print(line(r, b))
    PA = [r for r in R if r['ok_add']]; PR = [r for r in R if r['ok_rem']]
    print(f"\nALL {len(R)} COMBINATIONS: {len(PA)} pass ADD, {len(PR)} pass REMOVE")
    for r in sorted({id(x): x for x in PA + PR}.values(), key=lambda r: -r['a']['mean'])[:20]: print(line(r, b))
    print("\nbest five by account win rate with %/day kept (>= live - 0.01):")
    for r in sorted([r for r in R if r['a']['mean'] >= b['mean'] - 0.01], key=lambda r: -r['a']['win'])[:5]: print(line(r, b))
    print("best five by account %/day:")
    for r in sorted(R, key=lambda r: -r['a']['mean'])[:5]: print(line(r, b))
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars)); mb = runp(LIVE)
        show = sorted({id(x): x for x in PA + PR}.values(), key=lambda r: -r['a']['mean'])[:8]
        show += [r for r in sorted(R, key=lambda r: -r['a']['win']) if r not in show][:3] + [r for r in sorted(R, key=lambda r: -r['a']['mean']) if r not in show][:3]
        for lo, hi, title in (('0000', '2026-03-01', 'Massive before 2026-03 (never fitted)'), ('2026-03-01', '9999', 'Massive 2026-03 on')):
            seg = lambda d, t: A.acct([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); m0 = seg(*mb)
            print(f"\n{title}: rules in force {m0['mean']:+.3f}%/day win {m0['win']:.0f}% DD {m0['dd']:.1f}% PF {m0['pf']:.2f} n {m0['n']}")
            for r in show:
                d, t = runp(r['p']); a = seg(d, t); f = [x for x in t if lo <= x[0] < hi and x[1] == 'FADE']
                tag = ('ADD ' if r['ok_add'] else '') + ('REM ' if r['ok_rem'] else '') or 'near'
                print(f"  {tag:<8} {nm(r['p']):<38} {a['mean']:+.3f}%/day ({a['mean'] - m0['mean']:+.3f}) win {a['win']:3.0f}% ({a['win'] - m0['win']:+4.1f}) DD {a['dd']:5.1f}% PF {a['pf']:4.2f} | FADE n {len(f)} win {100 * sum(1 for x in f if x[4] > 0) / max(len(f), 1):3.0f}%")
