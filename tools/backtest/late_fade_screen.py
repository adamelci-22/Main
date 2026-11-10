#!/usr/bin/env python3
"""LATE FADE: a held first retest that fails later (governor question 2026-11-10) (governor question 2026-11-06: "if we know that some days are more one directional can we create an orb retest continuation system to work with the fade").
    python3 -I tools/backtest/orb_continuation_screen.py [M5.json.gz]
Research-only (this process only; live code untouched). Same 30-minute box and same break window as FADE. FADE enters when the retest FAILS (close back inside the box).
CONT enters when the retest HOLDS (the bar touches the edge within the retest tolerance and closes on the break side), in the break direction, on the proxy's leveraged leg.
  entry : open of the bar after the retest bar          stop : CT_STOP 'low' = lowest low from the break bar to the retest bar, 'edge' = 0.15% beyond the box edge
  filter: CT_TREND = the proxy has already moved at least this % from the prior close in the break direction at the retest close (0 = no filter; 0.85 = exactly the days the runaway skip removes FADE from)
  exits : the live FADE management (take 1/3 at 2R, lock, early cut, chandelier, 13:30), sizing and one position at a time as the rest of the account (tunables v4).
Variants: trend filter 0, 0.5, 0.85, 1.2 x stop low/edge x Fridays off/on = 16, each added to the live rules. Pass bar = the ADD bar of add_trades_screen.py (fixed before looking):
added trades win >= 60%, average > +0.1% of the account, positive in both halves; the account keeps %/day and win rate; drawdown +0.5 at most.
Also standalone (FADE and PULLBACK dropped) to see the edge by itself. Massive replay for the best variants (before 2026-03 never fitted, and from 2026-03). Changes no order, rule or state."""
import contextlib, gzip, inspect, io, itertools, json, os, sys
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
CONT = '''
def cont(b, K, pc):
    # LATE FADE: break, first retest HELD (live FADE gets the failed ones), then a later 5-minute close back inside the box inside the window
    if K < 8: return None
    H, L = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
    for j in range(6, min(9, K)):
        cl = b[j][3]; bside = 1 if cl > H else -1 if cl < L else 0
        if not bside: continue
        bb, p0 = (b, None) if bside > 0 else mirror(b)
        to_m = (lambda x: x) if bside > 0 else (lambda x, p0=p0: 2 * p0 - x)
        E = to_m(H if bside > 0 else L)
        for i in range(j + 1, min(j + 13, 76)):
            if i >= K: return None
            o, h, l, cc, v = bb[i]
            if l <= E * (1 + RETEST_TOL / 100):
                if cc < E: return None
                if CT_MAXT is not None and (b[i][3] / pc - 1) * 100 * bside >= CT_MAXT: return None
                for m in range(i + 1, min(CT_END + 1, 76)):
                    if m >= K: return None
                    if bb[m][3] < E:
                        if m + 1 >= K: return None
                        lo = i if CT_STOP == 'recent' else j
                        stop_real = to_m(max(bb[q][1] for q in range(lo, m + 1)))
                        return fade_manage(b, K, m + 1, -bside, b[m + 1][0], stop_real)
                return None
        return None
    return None
'''
src = inspect.getsource(paper.simulate)
anchor = "    for i, leg in enumerate(list(PB_LIST) + [x for x in X_ADD_PB if x not in PB_LIST]):"
block = '''    if CT_ON:
        for p, (bull, bear, lev_bull, lev_bear) in rows.items():
            if p not in today or p not in prev or p in X_DROP_FADE_C or (not CT_FRI and not fade_day_ok(day)): continue
            tc = cont(today[p], K, prev[p][-1][3])
            if not tc or tc['status'] not in ('open', 'closed'): continue
            leg = bull if tc['side'] > 0 else bear; lev = lev_bull if tc['side'] > 0 else lev_bear
            if leg not in today: continue
            tc.update(system='CONT', proxy=p, ticker=leg, lev=lev, order=0.5, leg_entry=today[leg][tc['k']][0])
            cands.append(tc)
'''
for old, new in ((anchor, block + anchor), ("c['proxy'] if c['system'] == 'FADE' else PB_PROXY", "c['proxy'] if c['system'] in ('FADE', 'CONT') else PB_PROXY"),
                 ("        if c['system'] == 'FADE':\n            leg_risk", "        if c['system'] in ('FADE', 'CONT'):\n            leg_risk")):
    assert src.count(old) == 1, old; src = src.replace(old, new)
paper.CT_ON, paper.CT_MAXT, paper.CT_STOP, paper.CT_FRI, paper.CT_END, paper.X_DROP_FADE_C = False, None, 'high', False, 18, ()
exec(compile(CONT, 'cont_research', 'exec'), paper.__dict__); exec(compile(src, 'cont_simulate_copy', 'exec'), paper.__dict__)
GRID = [dict(e=e, s=st_, t=t, f=f) for e in (18, 24, 30) for st_ in ('high', 'recent') for t in (None, 0.85) for f in (False, True)]
GRID2 = []


def run(p, solo=False):
    paper.CT_ON, paper.CT_MAXT, paper.CT_STOP, paper.CT_FRI, paper.CT_END = p is not None, (p or {}).get('t'), (p or {}).get('s', 'high'), (p or {}).get('f', False), (p or {}).get('e', 18)
    over = {'x.drop_fade': list(paper.FADE_ROWS), 'x.drop_pb': list(paper.PB_LIST)} if solo else {}
    try: return A.replay(over)
    finally: paper.CT_ON = False


def nm(p):
    if p is None: return 'LIVE (no LATE)'
    return f"window to bar {p['e']} stop-from {p['s']:<6} maxtrend {p['t'] if p['t'] is not None else 'none':<5} Fri {'on' if p['f'] else 'off'}"


def judge(p, base, cut):
    d, t = run(p); a = A.acct(d, t); b = A.acct(*base)
    ct = [x for x in t if x[1] == 'CONT']; s = lambda l: sum(x[4] for x in l)
    w = 100 * sum(1 for x in ct if x[4] > 0) / len(ct) if ct else 0.0
    sd, st = run(p, True); sa = A.acct(sd, [x for x in st if x[1] == 'CONT'])
    sc = [x for x in st if x[1] == 'CONT']; sw = 100 * sum(1 for x in sc if x[4] > 0) / len(sc) if sc else 0.0
    ok = (len(ct) >= 3 and w >= 60 and s(ct) / len(ct) > 0.1 and s([x for x in ct if x[0] < cut]) > 0 and s([x for x in ct if x[0] >= cut]) > 0 and a['mean'] >= b['mean'] and a['win'] >= b['win'] and a['dd'] <= b['dd'] + 0.5)
    return dict(p=p, a=a, n=len(ct), w=w, avg=s(ct) / len(ct) if ct else 0.0, h1=s([x for x in ct if x[0] < cut]), h2=s([x for x in ct if x[0] >= cut]), solo_n=len(sc), solo_w=sw,
                solo_avg=s(sc) / len(sc) if sc else 0.0, ok=ok, days=len({x[0] for x in ct}))


def line(r, b):
    a = r['a']
    return (f"{'ADD ' if r['ok'] else '    '}{nm(r['p']):<40} CONT n {r['n']:3d} ({r['days']:3d} days) win {r['w']:3.0f}% avg {r['avg']:+.2f}% halves {r['h1']:+6.1f}/{r['h2']:+6.1f} | acct {a['mean']:+.3f} ({a['mean'] - b['mean']:+.3f}) "
            f"win {a['win']:3.0f}% ({a['win'] - b['win']:+4.1f}) DD {a['dd']:4.2f} | alone: n {r['solo_n']:3d} win {r['solo_w']:3.0f}% avg {r['solo_avg']:+.2f}%")


if __name__ == '__main__':
    A.setup(I.load_data()); cut = A.DAYS[int(len(A.DAYS) * I.SPLIT)]
    base = run(None); b = A.acct(*base); chk = A.acct(*A.replay({})); assert abs(chk['mean'] - b['mean']) < 1e-9 and chk['n'] == b['n'], 'research copy with CONT off must equal the live engine'
    print(f"{len(A.DAYS)} Robinhood sessions, rules in force (tunables v{I.current(I.tun())['version']}), halves split at {cut}; the research copy with CONT off equals the live engine")
    print(f"rules in force: {b['mean']:+.3f}%/day win {b['win']:.0f}% DD {b['dd']:.2f}% PF {b['pf']:.2f} trades {b['n']}\n")
    with get_context('fork').Pool(4) as pool: R = pool.starmap(judge, [(p, base, cut) for p in GRID])
    for r in R: print(line(r, b))
    print(f"\n{sum(r['ok'] for r in R)} of {len(R)} pass the ADD bar\n\nOTHER EXITS AND A PLAIN BREAK ENTRY")
    with get_context('fork').Pool(4) as pool: R2 = pool.starmap(judge, [(p, base, cut) for p in GRID2])
    for r in R2: print(line(r, b))
    print(f"\n{sum(r['ok'] for r in R2)} of {len(R2)} pass the ADD bar"); R = R + R2
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars)); mb = run(None)
        top = sorted(R, key=lambda r: (-r['ok'], -(r['a']['mean'])))[:4]
        for lo, hi, title in (('0000', '2026-03-01', 'Massive before 2026-03 (never fitted)'), ('2026-03-01', '9999', 'Massive 2026-03 on')):
            seg = lambda d, t: ([x for x in d if lo <= x[0] < hi], [x for x in t if lo <= x[0] < hi]); m0 = A.acct(*seg(*mb))
            print(f"\n{title}: rules in force {m0['mean']:+.3f}%/day win {m0['win']:.0f}% DD {m0['dd']:.1f}% n {m0['n']}")
            for r in top:
                d, t = seg(*run(r['p'])); a = A.acct(d, t); ct = [x for x in t if x[1] == 'CONT']
                sd, st = seg(*run(r['p'], True)); sc = [x for x in st if x[1] == 'CONT']
                print(f"  {nm(r['p']):<40} CONT n {len(ct):3d} win {100 * sum(1 for x in ct if x[4] > 0) / max(len(ct), 1):3.0f}% avg {sum(x[4] for x in ct) / max(len(ct), 1):+.2f}% | acct {a['mean']:+.3f} ({a['mean'] - m0['mean']:+.3f}) win {a['win']:3.0f}% ({a['win'] - m0['win']:+4.1f}) DD {a['dd']:5.1f}% | alone n {len(sc):3d} win {100 * sum(1 for x in sc if x[4] > 0) / max(len(sc), 1):3.0f}% avg {sum(x[4] for x in sc) / max(len(sc), 1):+.2f}%")
