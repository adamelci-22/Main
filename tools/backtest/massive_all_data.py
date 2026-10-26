#!/usr/bin/env python3
"""Best FADE and PULLBACK lists across ALL the data: Massive before 2026 (A), Massive 2026-03-03..10-14 (B-MS), Robinhood 2026-03-03..10-14 (B-RH).
    step 1  /usr/bin/python3 -I tools/backtest/massive_all_data.py ms MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz - OUT_MS.json
    step 2  /usr/bin/python3 -I tools/backtest/massive_all_data.py rh OUT_RH.json
    step 3  /usr/bin/python3 -I tools/backtest/massive_all_data.py merge OUT_MS.json OUT_RH.json CHOSEN.json > tools/backtest/results/massive_all_data.txt
    step 4  /usr/bin/python3 -I tools/backtest/massive_all_data.py joint rh CHOSEN.json   or   joint ms CHOSEN.json - MASSIVE_5M MASSIVE_DAILY >> tools/backtest/results/massive_all_data.txt
FADE pool (tradable proxies): QQQ SOXX IWM XLK XBI XLF SPY TLT GLD VIXY, lists of 4 to 10 (signal-model legs). PULLBACK pool: SOXS LABD TECS UVXY SRTY DRIP DUST UVIX TZA SQQQ NUGT FAZ ERY, lists of 4 to 10.
Account: mixed.account ($2,000, 3% risk capped at cash, one position, 3 entries a day). Metric: average %/day over each window.
"""
import gzip, itertools, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
mode = sys.argv[1]
import backtest as BT
if mode == 'ms' or (mode == 'joint' and sys.argv[2] == 'ms'):
    i = 2 if mode == 'ms' else 5
    _raw = json.load(gzip.open(sys.argv[i], 'rt')); _daily = json.load(gzip.open(sys.argv[i + 1], 'rt')); BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY', 'TLT']
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
from lab import get_data
LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
FROWS = {p: FA.ROWS[p] for p in LIVE6}
FROWS.update({'SPY': ('UPRO', 3, 'SPXU', 3), 'TLT': ('TMF', 3, 'TMV', 3), 'GLD': ('UGL', 2, 'GLL', 2), 'VIXY': ('UVXY', 1.5, 'SVIX', 1)})
PBPOOL = ['SOXS', 'LABD', 'TECS', 'UVXY', 'SRTY', 'DRIP', 'DUST', 'UVIX', 'TZA', 'SQQQ', 'NUGT', 'FAZ', 'ERY']
A_END, B0, B1 = '2026-02-27', '2026-03-03', '2026-10-14'


def build():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    for f in PBPOOL: PI.PROXY.setdefault(f, f)
    PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD', 'UVXY': 'UVXY'})
    S = PBF.run(D, days, [f for f in PBPOOL if f in D.bars], oco_gap=True)
    pb = {f: [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S if x['inst'] == f] for f in PBPOOL}
    fd = {p: MXD.norm_px(EX.fade_trades(D, days, p, FROWS[p]), 'FADE') for p in FROWS}
    return D, days, pb, fd


def pd_(D, ds, cs):
    S = set(ds); a = MXD.account(D, ds, [c for c in cs if c['day'] in S]); return round(st.mean(a['daily'].values()), 4), round(a['ret'], 1), round(a['mdd'], 1), len(a['taken'])


def dump(path):
    D, days, pb, fd = build(); DA = [d for d in days if d <= A_END]; DB = [d for d in days if B0 <= d <= B1]; out = {'fade': {}, 'pb': {}}
    for kind, pool, cand in (('fade', list(FROWS), fd), ('pb', PBPOOL, pb)):
        for k in range(4, 11):
            for c in itertools.combinations(pool, k):
                cs = [x for p in c for x in cand[p]]
                out[kind][' '.join(c)] = {'B': pd_(D, DB, cs)} | ({'A': pd_(D, DA, cs)} if mode == 'ms' else {})
    json.dump(out, open(path, 'w'))


def merge(ms, rh, chosen):
    M = json.load(open(ms)); R = json.load(open(rh)); pick = {}
    for kind in ('fade', 'pb'):
        rows = []
        for k, v in M[kind].items():
            if k in R[kind]: rows.append((k, v['A'][0], v['B'][0], R[kind][k]['B'][0], v['B'], R[kind][k]['B']))
        print(f"== {kind.upper()}: {len(rows)} lists of 4 to 10. Columns: A = Massive before 2026, B-MS = Massive 2026 window, B-RH = Robinhood 2026 window (%/day) ==")
        live = ' '.join(LIVE6) if kind == 'fade' else 'SOXS LABD TECS UVXY'
        keyfn = {'weakest of A, B-MS, B-RH': lambda r: min(r[1], r[2], r[3]), 'weakest of B-MS and B-RH (both 2026 feeds)': lambda r: min(r[2], r[3]), 'average of B-MS and B-RH': lambda r: (r[2] + r[3]) / 2}
        for nm, fn in keyfn.items():
            top = sorted(rows, key=lambda r: -fn(r))[:5]
            print(f"  -- ranked by {nm}")
            for r in top: print(f"     {len(r[0].split())}  {r[0]:<54}A {r[1]:+.3f}  B-MS {r[2]:+.3f} (DD {r[4][2]:.0f}%, n={r[4][3]})  B-RH {r[3]:+.3f} (DD {r[5][2]:.0f}%, n={r[5][3]})")
            pick[(kind, nm)] = top[0][0]
        lr = next((r for r in rows if r[0] == live), None)
        if lr:
            rk = lambda fn: 1 + sum(fn(r) > fn(lr) for r in rows)
            print(f"  -- live list ({live}): A {lr[1]:+.3f}  B-MS {lr[2]:+.3f}  B-RH {lr[3]:+.3f};  rank by weakest-of-both-2026 {rk(keyfn['weakest of B-MS and B-RH (both 2026 feeds)'])} of {len(rows)}, by weakest of all three {rk(keyfn['weakest of A, B-MS, B-RH'])}")
        pos3 = [r for r in rows if min(r[1], r[2], r[3]) > 0]; pos2 = [r for r in rows if min(r[2], r[3]) > 0]
        print(f"  -- lists positive in all three: {len(pos3)}; positive in both 2026 feeds: {len(pos2)} of {len(rows)}\n")
    json.dump({'fade': {nm: pick[('fade', nm)] for nm in ('weakest of A, B-MS, B-RH', 'weakest of B-MS and B-RH (both 2026 feeds)', 'average of B-MS and B-RH')},
               'pb': {nm: pick[('pb', nm)] for nm in ('weakest of A, B-MS, B-RH', 'weakest of B-MS and B-RH (both 2026 feeds)', 'average of B-MS and B-RH')}}, open(chosen, 'w'))


def joint(which, chosen):
    D, days, pb, fd = build(); C = json.load(open(chosen)); DA = [d for d in days if d <= A_END]; DB = [d for d in days if B0 <= d <= B1]
    sets = {'LIVE': (' '.join(LIVE6), 'SOXS LABD TECS UVXY')}
    for nm in C['fade']: sets[f"best-of: {nm}"] = (C['fade'][nm], C['pb'][nm])
    print(f"== Joint FADE + PULLBACK, {'Massive' if which == 'ms' else 'Robinhood'} bars ==")
    for nm, (fl, pl) in sets.items():
        cs = [x for p in fl.split() for x in fd[p]] + [x for f in pl.split() for x in pb[f]]
        b = pd_(D, DB, cs); line = f"  {nm:<58} B {b[0]:+.3f}%/d ret {b[1]:+.0f}% DD {b[2]:.0f}% n={b[3]}"
        if which == 'ms': a = pd_(D, DA, cs); line += f"  A {a[0]:+.3f}%/d ret {a[1]:+.0f}% DD {a[2]:.0f}%"
        print(line + f"\n      FADE {fl} | PB {pl}")


if __name__ == '__main__':
    if mode == 'ms': dump(sys.argv[5])
    elif mode == 'rh': dump(sys.argv[2])
    elif mode == 'merge': merge(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == 'joint': joint(sys.argv[2], sys.argv[3])
