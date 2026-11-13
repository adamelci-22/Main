#!/usr/bin/env python3
"""Systems 1 and 2 (governor 2026-11-13): the current book (FADE + PULLBACK, proxy -> leveraged leg) re-tuned two ways.
  SYSTEM 1 "robust":  the configuration whose WORST calendar year is best (maximin over 2022..2026), ties by the median year.
  SYSTEM 2 "monthly": the configuration with the highest average monthly return.
Grid: FADE stop floor, lock, early cut, target R, chandelier, runaway skip, Friday skip, FADE on/off; PULLBACK exit, breakout volume,
minimum stop, opening range, PULLBACK on/off. Account: 3% risk capped at cash, one position at a time, 3 entries a day, same-system loss
block. Data: Massive 5-minute tape 2021-12..2026-10 (4 PULLBACK legs) for the folds; Robinhood 2026-03..10 (8 legs) as a second check.
Honest test: walk-forward - for each year pick the winner on the years before it only, then trade that year.
    python3 -I tools/backtest/tune_book.py > tools/backtest/results/tune_book_2026-11-13.txt"""
import datetime as dt, itertools, os, pickle, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, fade_setup_exits as FS, pb_exit_screen as PS, entry_pb as EP, adaptive_exit as AE
T0 = time.time()
ds_m = F.DS(AE.M5, F.LIVE + PS.LEGS_M); cx_m = F.context(ds_m, F.LIVE); days_m = [d for d in ds_m.days[21:] if d <= '2026-10-30']
ds_r = F.DS(None, F.LIVE + PS.LEGS_RH); cx_r = F.context(ds_r, F.LIVE); days_r = [d for d in ds_r.days if '2026-03-03' <= d <= '2026-10-14']
SETS = [('M', ds_m, cx_m, days_m, PS.LEGS_M), ('R', ds_r, cx_r, days_r, PS.LEGS_RH)]


def fade_entries(ds, ctx, days, floor):
    def grab(ds_, p, d, b, k, side, entry, ext, c_, info, ctx_):
        r = (entry - ext) * side
        if r <= 0: return None
        if c_.floor_pct: r = max(r, entry * c_.floor_pct / 100)
        i = ds_.idx[d]; pv = ds_.bars[p].get(ds_.days[i - 1]) if i else None
        run = bool(pv) and (b[info['touch']][3] / pv[-1][3] - 1) * 100 * (-side) >= 0.85
        info.update(b=b, k=k, side=side, entry=entry, ext=entry - side * r, r=r, atr=ctx_['atr'][p][d], far_R=None, run=run,
                    fri=dt.date.fromisoformat(d).weekday() == 4, rv=ds_.rvol(p, d, k)); return info
    old = F._manage; F._manage = grab
    try: return F.trades(ds, days, F.LIVE, F.P(floor_pct=floor), ctx)
    finally: F._manage = old


def pb_entries(ds, days, legs, P):
    E = []
    for s in legs:
        for d in days:
            i = ds.idx[d]
            if s not in ds.bars or d not in ds.bars[s] or i == 0 or ds.days[i - 1] not in ds.bars[s]: continue
            b = ds.bars[s][d]; pv = ds.bars[s][ds.days[i - 1]]; x = EP.signal(b, pv, P)
            if x:
                t = dict(day=d, proxy=s, b=b, prev=pv, k=x['k'], entry=x['entry'], stop=x['stop'], T=x['T']); PS.prep(t); t['rv'] = ds.rvol(s, d, x['k']); E.append(t)
    return E


def byday(T):
    m = {}
    for t in T: m.setdefault(t['day'], []).append(t)
    return m


def account(days, fd, pd_, lossblock=True, risk=3.0, cap=3):
    out = np.zeros(len(days))
    for n, d in enumerate(days):
        cs = fd.get(d, []) + pd_.get(d, [])
        if not cs: continue
        cs = sorted(cs, key=lambda t: (t['k'], -t['rv'], t['sys'])); free = 0; eq = 1.0; cnt = 0; blocked = set()
        for t in cs:
            if cnt >= cap: break
            if t['k'] < free or t['sys'] in blocked: continue
            f = min(1.0, risk / t['leg_risk']); g = f * t['pct'] / 100; eq *= 1 + g; free = t['xbar'] + 1; cnt += 1
            if lossblock and g <= 0: blocked.add(t['sys'])
        out[n] = eq - 1
    return out


FLOORS = (0.3, 0.5, 0.7, 1.0)
FEX = {f"lock {ln}|cut {'on' if cut else 'off'}|tp {tp:g}R|chand {ch:g}": dict(tp=tp, chand=ch, cut=cut, **lk)
       for (ln, lk), cut, tp, ch in itertools.product((('+0.15R', {}), ('BE', dict(locklvl=0.0)), ('off', dict(lock=False))), (True, False), (2.0, 3.0), (2.0, 3.0))}
PBE = [dict(vol=v, minstop=ms, orh=o) for v, ms, o in itertools.product((1.0, 1.3, 1.5), (0.75, 1.0), (3, 6))]
PBX = {'100% at high': {}, 'runner EMA20': dict(frac=1 / 3, run=('ema', 20)), 'runner chand3': dict(frac=1 / 3, run=('chand', 3.0))}
LIVE_F = 'floor 0.5|lock +0.15R|cut on|tp 2R|chand 2|runaway 0.85|Fri skip'; LIVE_P = 'vol 1.3|minstop 0.75|OR 9:45|runner EMA20'


def build():
    cache = os.path.join('/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad', 'tune_book.pkl')
    FC = {s[0]: {'FADE off': {}} for s in SETS}; PC = {s[0]: {'PB off': {}} for s in SETS}
    for sn, ds, ctx, days, legs in SETS:
        for fl in FLOORS:
            E = fade_entries(ds, ctx, days, fl)
            for xn, pk in FEX.items():
                T = []
                for t in E:
                    m = FS.manage(t, pk); T.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=0, run=t['run'], fri=t['fri']))
                for rw, fr in itertools.product((False, True), (False, True)):
                    FC[sn][f"floor {fl:g}|{xn}|runaway {'0.85' if rw else 'off'}|Fri {'skip' if fr else 'trade'}"] = byday([t for t in T if not (rw and t['run']) and not (fr and t['fri'])])
        for P in PBE:
            E = pb_entries(ds, days, legs, dict(EP.LIVE, **P))
            for xn, cfg in PBX.items():
                T = []
                for t in E:
                    m = PS.manage(t, cfg); T.append(dict(day=t['day'], k=m['k'], xbar=m['xbar'], pct=m['pct'], leg_risk=m['leg_risk'], rv=t['rv'], sys=1))
                PC[sn][f"vol {P['vol']:g}|minstop {P['minstop']:g}|OR {'9:45' if P['orh'] == 3 else '10:00'}|{xn}"] = byday(T)
        print(f"# built {sn}: {len(FC[sn])} FADE x {len(PC[sn])} PULLBACK configs ({time.time() - T0:.0f}s)", file=sys.stderr, flush=True)
    return FC, PC


def stats(r, idx):
    lg = np.log1p(r); cum = np.cumsum(lg); dd = 1 - np.exp(cum - np.maximum.accumulate(np.concatenate([[0], cum]))[1:])
    return np.expm1(np.add.reduceat(lg, idx)), float(dd.max() * 100), float(np.expm1(cum[-1]) * 100)


def main():
    FC, PC = build()
    ym = [d[:7] for d in days_m]; mi = [i for i in range(len(ym)) if i == 0 or ym[i] != ym[i - 1]]
    yy = ['2022' if d < '2022-01-01' else d[:4] for d in days_m]; yi = [i for i in range(len(yy)) if i == 0 or yy[i] != yy[i - 1]]; years = [yy[i] for i in yi]
    fk = list(FC['M']); pk = list(PC['M']); rows = []
    for a, b in itertools.product(fk, pk):
        if a == 'FADE off' and b == 'PB off': continue
        r = account(days_m, FC['M'][a], PC['M'][b]); mo, dd, tot = stats(r, mi); yr, _, _ = stats(r, yi)
        rr = account(days_r, FC['R'][a], PC['R'][b]); _, ddr, totr = stats(rr, [0])
        rows.append((a, b, yr * 100, mo * 100, dd, tot, totr, ddr))
    print(f"# {len(rows)} combinations ({time.time() - T0:.0f}s)", file=sys.stderr, flush=True)
    Y = np.array([r[2] for r in rows]); MO = np.array([r[3] for r in rows]); nm = MO.shape[1]
    li = next(i for i, r in enumerate(rows) if r[0] == LIVE_F and r[1] == LIVE_P)
    def show(tag, i):
        a, b, yr, mo, dd, tot, totr, ddr = rows[i]
        print(f"{tag}\n   FADE: {a}\n   PULLBACK: {b}")
        print(f"   years {' '.join(f'{y} {v:+.1f}%' for y, v in zip(years, yr))} | worst year {yr.min():+.1f}% | total {tot:+.1f}% | max DD {dd:.1f}%")
        print(f"   months: mean {mo.mean():+.2f}% median {np.median(mo):+.2f}% winning {100 * np.mean(mo > 0):.0f}% worst {mo.min():+.1f}% best {mo.max():+.1f}% | Robinhood 2026 check: {totr:+.1f}% DD {ddr:.1f}%")
    print(__doc__.split('\n')[0]); print(f"combinations tested: {len(rows)}; Massive {days_m[0]}..{days_m[-1]} ({len(days_m)} days, {nm} months); Robinhood {days_r[0]}..{days_r[-1]}\n")
    show('LIVE v5.2.46', li)
    s1 = np.lexsort((np.median(Y, 1), Y.min(1)))[::-1]; s2 = np.argsort(-MO.mean(1))
    print(); show('SYSTEM 1 (most robust: best worst-year)', s1[0])
    print('   next four by worst year:'); [print(f"     worst {Y[i].min():+.1f}% median {np.median(Y[i]):+.1f}% total {rows[i][5]:+.0f}% RH {rows[i][6]:+.0f}% | {rows[i][0]} || {rows[i][1]}") for i in s1[1:5]]
    print(); show('SYSTEM 2 (highest average month)', s2[0])
    print('   next four by average month:'); [print(f"     mean {MO[i].mean():+.2f}% winning {100 * np.mean(MO[i] > 0):.0f}% total {rows[i][5]:+.0f}% RH {rows[i][6]:+.0f}% | {rows[i][0]} || {rows[i][1]}") for i in s2[1:5]]
    # what the top 5% share (parameter votes)
    for tag, order in (('SYSTEM 1 top 2%', s1), ('SYSTEM 2 top 2%', s2)):
        top = order[:max(20, len(rows) // 50)]; votes = {}
        for i in top:
            for part in (rows[i][0] + '|' + rows[i][1]).split('|'): votes[part] = votes.get(part, 0) + 1
        print(f"\n{tag} ({len(top)} configs): most common settings: " + ', '.join(f"{k} {100 * v / len(top):.0f}%" for k, v in sorted(votes.items(), key=lambda z: -z[1])[:14]))
    # walk-forward
    print('\nWALK-FORWARD (pick on the years before, trade the next year). Yearly return of the pick vs LIVE that year:')
    yrcol = {y: n for n, y in enumerate(years)}; mon_year = np.array([ym[i][:4] if ym[i] >= '2022' else '2022' for i in mi])
    for tag in ('robust', 'monthly'):
        line = []; cw = 1.0; cl = 1.0
        for y in years[1:]:
            prior = [yrcol[x] for x in years if x < y]
            if tag == 'robust': i = int(np.lexsort((np.median(Y[:, prior], 1), Y[:, prior].min(1)))[-1])
            else: i = int(np.argmax(MO[:, mon_year < y].mean(1)))
            v = Y[i, yrcol[y]]; lv = Y[li, yrcol[y]]; cw *= 1 + v / 100; cl *= 1 + lv / 100; line.append(f"{y}: pick {v:+.1f}% vs live {lv:+.1f}%")
        print(f"   {tag:<8} " + ' | '.join(line) + f" || compounded {100 * (cw - 1):+.1f}% vs live {100 * (cl - 1):+.1f}%")
    # one change at a time from LIVE: which single knobs help in most years
    print('\nONE CHANGE AT A TIME vs LIVE (points: year by year, total, average month, max drawdown, Robinhood 2026). better = years improved of 5')
    la = LIVE_F.split('|'); lb = LIVE_P.split('|'); L = rows[li]
    for i, r in enumerate(rows):
        if r[0] in ('FADE off',) or r[1] in ('PB off',):
            if not ((r[0] == 'FADE off' and r[1] == LIVE_P) or (r[1] == 'PB off' and r[0] == LIVE_F)): continue
            ch = r[0] if r[0] == 'FADE off' else r[1]
        else:
            da = [x for x, y in zip(r[0].split('|'), la) if x != y]; db = [x for x, y in zip(r[1].split('|'), lb) if x != y]
            if len(da) + len(db) != 1: continue
            ch = ('FADE ' + da[0]) if da else ('PB ' + db[0])
        dy = r[2] - L[2]
        print(f"   {ch:<22} years {' '.join(f'{v:+6.1f}' for v in dy)} | better {int((dy > 0).sum())}/5 | total {r[5] - L[5]:+7.1f} | avg month {r[3].mean() - L[3].mean():+.2f} | worst yr {r[2].min():+6.1f} | DD {r[4]:4.1f} ({r[4] - L[4]:+.1f}) | RH {r[6] - L[6]:+6.1f}")
    # more walk-forward selection rules
    for tag in ('sharpe', 'rank'):
        line = []; cw = 1.0; cl = 1.0
        for y in years[1:]:
            prior = [yrcol[x] for x in years if x < y]; mm = MO[:, mon_year < y]
            if tag == 'sharpe': i = int(np.argmax(mm.mean(1) / (mm.std(1) + 1e-9)))
            else: i = int(np.argmin(sum(np.argsort(np.argsort(-Y[:, c])) for c in prior)))
            v = Y[i, yrcol[y]]; lv = Y[li, yrcol[y]]; cw *= 1 + v / 100; cl *= 1 + lv / 100; line.append(f"{y}: pick {v:+.1f}% vs live {lv:+.1f}%")
        print(f"   WF {tag:<7} " + ' | '.join(line) + f" || compounded {100 * (cw - 1):+.1f}% vs live {100 * (cl - 1):+.1f}%")
    pct = lambda col, v: 100 * float((col < v).mean())
    print(f"\nLIVE rank among {len(rows)}: total {pct(np.array([r[5] for r in rows]), L[5]):.0f}th percentile, average month {pct(MO.mean(1), L[3].mean()):.0f}th, worst year {pct(Y.min(1), L[2].min()):.0f}th, Robinhood 2026 {pct(np.array([r[6] for r in rows]), L[6]):.0f}th")
    pickle.dump(dict(rows=[(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows], years=years), open('/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/tune_rows.pkl', 'wb'))


if __name__ == '__main__':
    main()
