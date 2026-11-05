#!/usr/bin/env python3
"""Every rule change we have made (and the open ideas), searched as combinations (governor request 2026-11-05: "find me 5 different combos ... minimums are .25% per day").
    python3 -I tools/backtest/combo_search_2026_11.py OUTDIR [M5.json.gz]
Factors (each level = a version of the rules we have run, removed, or have open):
  lockcut     v5.2.19 FADE lock (+0.5R close -> stop +0.15R) and 15-minute early cut at -0.5R: on (live) / off
  no_friday   v5.2.17 no FADE entries on Fridays: on (live) / off
  runaway     v5.2.39 FADE runaway skip: 0.85 (live) / off / 1.25
  pb_target   PULLBACK take-profit: morning high floored to the cent (live) / floored + 1c (research pb.tp_1c_above) / not floored (before 2026-10-19)
  frozen      v5.2.18 frozen FADE trail before 2R: off (live; removed v5.2.22) / on
  fade_list   QQQ SOXX IWM XLK XBI XLF (live, v5.2.13) / the five without XLF / the pre-v5.2.13 list with AMD (AMDL 2x / AMDD 1x) for XLF
  pb_list     eight legs (live, v5.2.21) / SOXS LABD TECS UVXY (v5.2.14) / those four + NVD (before v5.2.14)
  judge_sig   open decision pb.judge_at_signal: off (live) / on
  pb_1130     idea from 2026-11-04: no PULLBACK entries at 11:30 or later: off (live) / on
Stage 2 adds a position size cap (size.cap_pct 100 ... 50) to the finalists, the drawdown lever. Data: Robinhood 5-minute sessions (base + live, the D3 evidence feed).
Each combination: one $2,000 account, paper.simulate (the live engine), losing streak cleared each morning (improve.run_cf convention). Halves = improve.SPLIT.
Walk-forward: every pick is also re-made on the first half only and scored on the second, to show how much of the edge is selection. With M5.json.gz the five picks and
the live rules are replayed on Massive 5-minute bars before 2026-03 (out of sample; AMD and the four new PULLBACK legs are absent there).
In-sample: a guide for D4 trials, never a rule by itself. Changes no order, rule or state."""
import contextlib, gzip, io, itertools, json, math, os, statistics as st, sys, time
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import improve as I, paper
OUT = sys.argv[1]; M5 = sys.argv[2] if len(sys.argv) > 2 else None; os.makedirs(OUT, exist_ok=True)
FACT = {'lockcut': [True, False], 'no_friday': [True, False], 'runaway': [0.85, None, 1.25], 'pb_target': ['floor', 'floor+1c', 'raw'], 'frozen': [False, True],
        'fade_list': ['live6', 'noXLF5', 'oldAMD'], 'pb_list': ['live8', 'four', 'fiveNVD'], 'judge_sig': [False, True], 'pb_1130': [False, True]}
LIVE = {k: v[0] for k, v in FACT.items()}
D = None; SYMS = None; BASE = I.champion_values(I.tun()); DAYS = None


def setup(d):
    global D, SYMS, DAYS
    D = d; SYMS = set(I.WANT()) | {'AMD', 'AMDL', 'AMDD'}; DAYS = D.days


def values(c, size=100.0):
    v = dict(BASE)
    v['x.fade_max_trend'] = c['runaway']; v['x.pb_tp_cents_below'] = -1 if c['pb_target'] == 'floor+1c' else 0
    v['x.drop_fade'] = ['XLF'] if c['fade_list'] != 'live6' else []
    v['x.add_fade'] = [['AMD', 'AMDL', 'AMDD', 2, 1]] if c['fade_list'] == 'oldAMD' else []
    v['x.drop_pb'] = {'live8': [], 'four': ['NVDQ', 'NVD', 'MSFU', 'SSG'], 'fiveNVD': ['NVDQ', 'MSFU', 'SSG']}[c['pb_list']]
    v['x.pb_judge_at_signal'] = c['judge_sig']; v['x.pb_last_bar'] = 23 if c['pb_1130'] else 99; v['size.cap_pct'] = size
    return v


def replay(c, size=100.0):
    """improve.run_cf with the date switches set from the combination. Returns [(day, day_ret%)], [(day, usd, acct%, system)]."""
    saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET, paper.FROZEN_FROM, paper.FROZEN_OFF_FROM)
    paper.OVERRIDE = values(c, size)
    paper.LOCKCUT_FROM = '0000-00-00' if c['lockcut'] else '9999-99-99'
    paper.FADE_NO_FRIDAY_FROM = '0000-00-00' if c['no_friday'] else '9999-99-99'
    paper.FLOOR_TARGET = c['pb_target'] != 'raw'
    paper.FROZEN_FROM, paper.FROZEN_OFF_FROM = ('0000-00-00', '9999-99-99') if c['frozen'] else ('9999-99-99', '9999-99-99')
    try:
        eq, daily, trades = 2000.0, [], []
        for i in range(1, len(DAYS)):
            d, pd = DAYS[i], DAYS[i - 1]
            tod = {s: D.bars[s][d][:48] for s in SYMS if d in D.bars.get(s, {})}
            prv = {s: D.bars[s][pd] for s in SYMS if pd in D.bars.get(s, {})}
            with contextlib.redirect_stdout(io.StringIO()):
                taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
            for t in taken:
                if t['status'] == 'closed': trades.append((d, t['usd'], t['usd'] / eq * 100, t['system']))
            daily.append((d, (e2 / eq - 1) * 100)); eq = e2
        return daily, trades
    finally:
        paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET, paper.FROZEN_FROM, paper.FROZEN_OFF_FROM = saved


def stats(daily, trades):
    r = [x for _, x in daily]; eq = peak = 1.0; dd = 0.0
    for x in r: eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    dset = {d for d, _ in daily}; t = [x for x in trades if x[0] in dset]
    w = sum(x[1] for x in t if x[1] > 0); l = -sum(x[1] for x in t if x[1] < 0); sd = st.pstdev(r) if len(r) > 1 else 0
    return dict(mean=st.mean(r) if r else 0.0, dd=dd, ret=(eq - 1) * 100, n=len(t), win=100 * sum(1 for x in t if x[1] > 0) / len(t) if t else 0.0,
                pf=w / l if l else (99.0 if w else 0.0), sharpe=st.mean(r) / sd * math.sqrt(252) if sd else 0.0,
                nf=sum(1 for x in t if x[3] == 'FADE'), np=sum(1 for x in t if x[3] != 'FADE'))


def score(c, size=100.0):
    daily, trades = replay(c, size); cut = int(len(daily) * I.SPLIT)
    return dict(combo=c, size=size, full=stats(daily, trades), h1=stats(daily[:cut], trades), h2=stats(daily[cut:], trades))


def name(c, size=100.0):
    diff = [f"{k}={'on' if v is True else 'off' if v is False else v}" for k, v in c.items() if v != LIVE[k]]
    return ('LIVE RULES' if not diff else ', '.join(diff)) + (f", size cap {size:.0f}%" if size < 100 else '')


def row(r, tag=''):
    f, a, b = r['full'], r['h1'], r['h2']
    return (f"{tag:<16} {f['mean']:+.3f} {f['ret']:7.1f} {f['dd']:5.2f} {f['win']:4.0f}% {f['pf']:5.2f} {f['n']:4d} ({f['nf']:3d}/{f['np']:3d}) {f['sharpe']:5.1f} | "
            f"H1 {a['mean']:+.3f} dd {a['dd']:4.1f} | H2 {b['mean']:+.3f} dd {b['dd']:4.1f} | {name(r['combo'], r['size'])}")


HDR = f"{'':<16} {'%/day':>6} {'ret%':>7} {'DD%':>5} {'win':>5} {'PF':>5} {'n':>4} (FADE/PB) {'Shrp':>5} | first half          | second half        | what differs from the live rules"

if __name__ == '__main__':
    t0 = time.time(); setup(I.load_data())
    combos = [dict(zip(FACT, vs)) for vs in itertools.product(*FACT.values())]
    print(f"{len(combos)} combinations on {len(DAYS)} Robinhood sessions {DAYS[0]}..{DAYS[-1]}")
    with get_context('fork').Pool(4) as pool: R = pool.map(score, combos, chunksize=16)
    print(f"stage 1 done in {time.time() - t0:.0f}s")
    json.dump([dict(r, combo={k: v for k, v in r['combo'].items()}) for r in R], open(os.path.join(OUT, 'combo_stage1.json'), 'w'))
    live = next(r for r in R if r['combo'] == LIVE)
    ok = [r for r in R if r['full']['mean'] >= 0.25 and r['full']['n'] >= 50]
    print(f"{len(ok)} of {len(R)} meet >= 0.25%/day with >= 50 trades\n"); print(HDR); print(row(live, 'live rules'))
    picks = {'best return': max(ok, key=lambda r: r['full']['mean']), 'best drawdown': min(ok, key=lambda r: (r['full']['dd'], -r['full']['mean'])),
             'best win rate': max(ok, key=lambda r: (r['full']['win'], r['full']['mean'])), 'best PF': max(ok, key=lambda r: (r['full']['pf'], r['full']['mean']))}
    # mixed: both halves >= 0.25, then the best average rank on return, drawdown, win rate, PF
    mix = [r for r in ok if r['h1']['mean'] >= 0.25 and r['h2']['mean'] >= 0.25]
    def rank(key, rev): s = sorted(mix, key=lambda r: r['full'][key], reverse=rev); return {id(r): i for i, r in enumerate(s)}
    rk = [rank('mean', True), rank('dd', False), rank('win', True), rank('pf', True)]
    picks['mixed'] = min(mix, key=lambda r: sum(x[id(r)] for x in rk))
    for k, r in picks.items(): print(row(r, k))
    print("\nTOP 8 by each measure (>= 0.25%/day, >= 50 trades)")
    for k, key, rev in (('return', 'mean', True), ('drawdown', 'dd', False), ('win rate', 'win', True), ('PF', 'pf', True)):
        print(f"-- {k}"); [print(row(r)) for r in sorted(ok, key=lambda r: r['full'][key], reverse=rev)[:8]]
    print("\nWHICH CHANGES MATTER: average %/day and drawdown over all 2,592 combinations, by factor level (the live level first)")
    for f, lv in FACT.items():
        print('  ' + f"{f:<10} " + '   '.join(f"{str(l):>8}: {st.mean(r['full']['mean'] for r in R if r['combo'][f] == l):+.3f}%/day DD {st.mean(r['full']['dd'] for r in R if r['combo'][f] == l):4.2f}%" for l in lv))
    # stage 2: size cap on the finalists for the drawdown pick and the mixed pick
    fin = sorted(ok, key=lambda r: r['full']['dd'] / max(r['full']['mean'], 1e-9))[:12] + [picks['mixed'], picks['best return'], live]
    S2 = []
    for r in fin:
        for cap in (90, 80, 70, 60, 50):
            S2.append(score(r['combo'], cap))
    ok2 = [r for r in S2 if r['full']['mean'] >= 0.25]
    print("\nSTAGE 2  position size cap on the finalists (lower cap = smaller position = smaller swings and return)")
    print(HDR)
    for r in sorted(ok2, key=lambda r: r['full']['dd'])[:10]: print(row(r))
    if ok2:
        b2 = min(ok2, key=lambda r: (r['full']['dd'], -r['full']['mean']))
        if b2['full']['dd'] < picks['best drawdown']['full']['dd']: picks['best drawdown'] = b2
    print("\nFINAL FIVE (and the live rules)"); print(HDR); print(row(live, 'live rules'))
    for k, r in picks.items(): print(row(r, k))
    # walk-forward: make each pick from the first half only, score it on the second half
    print("\nWALK-FORWARD  pick on the first half only (>= 0.25%/day there, >= 25 trades), then score on the second half (the honest number)")
    okh = [r for r in R if r['h1']['mean'] >= 0.25 and r['h1']['n'] >= 25]
    wf = {'best return': max(okh, key=lambda r: r['h1']['mean']), 'best drawdown': min(okh, key=lambda r: (r['h1']['dd'], -r['h1']['mean'])),
          'best win rate': max(okh, key=lambda r: (r['h1']['win'], r['h1']['mean'])), 'best PF': max(okh, key=lambda r: (r['h1']['pf'], r['h1']['mean']))}
    for k, r in wf.items():
        print(f"  {k:<14} first half {r['h1']['mean']:+.3f}%/day dd {r['h1']['dd']:.1f} win {r['h1']['win']:.0f}% PF {r['h1']['pf']:.2f}  ->  second half {r['h2']['mean']:+.3f}%/day dd {r['h2']['dd']:.1f} win {r['h2']['win']:.0f}% PF {r['h2']['pf']:.2f}   [{name(r['combo'])}]")
    print(f"  live rules     first half {live['h1']['mean']:+.3f}%/day  ->  second half {live['h2']['mean']:+.3f}%/day")
    json.dump({k: dict(v, combo=v['combo']) for k, v in picks.items()}, open(os.path.join(OUT, 'combo_picks.json'), 'w'))
    # out of sample on Massive bars before 2026-03
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        setup(DM)
        print(f"\nOUT OF SAMPLE  Massive 5-minute bars {DAYS[0]}..{DAYS[-1]} (rules never fitted on the part before 2026-03; AMD and NVDQ/NVD/MSFU/SSG absent)")
        print(f"{'':<16} {'before 2026-03: %/day':>22} {'ret%':>7} {'DD%':>6} {'win':>5} {'PF':>5} {'n':>4} | {'2026-03 on: %/day':>18} {'ret%':>7} {'DD%':>6}")
        for k, r in [('live rules', live)] + list(picks.items()):
            daily, trades = replay(r['combo'], r['size']); a = [x for x in daily if x[0] < '2026-03-01']; b = [x for x in daily if x[0] >= '2026-03-01']
            sa, sb = stats(a, trades), stats(b, trades)
            print(f"{k:<16} {sa['mean']:+22.3f} {sa['ret']:7.1f} {sa['dd']:6.1f} {sa['win']:4.0f}% {sa['pf']:5.2f} {sa['n']:4d} | {sb['mean']:+18.3f} {sb['ret']:7.1f} {sb['dd']:6.1f}")
    print(f"\ndone in {time.time() - t0:.0f}s")
