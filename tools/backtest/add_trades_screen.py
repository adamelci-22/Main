#!/usr/bin/env python3
"""Rules that ADD winning trades (governor request 2026-11-05: "help with success rate ... increasing the amount of successful trades (i prefer this one)").
    python3 -I tools/backtest/add_trades_screen.py [M5.json.gz]
Each candidate is added ALONE to the live rules (paper.simulate, rule set in force, one $2,000 account, one position at a time) on the Robinhood 5-minute data:
  A. an extra PULLBACK leg (x.add_pb), every ETF / leveraged fund in the data with a liquid tape;
  B. an extra FADE proxy with its leveraged pair (x.add_fade), ETFs only (the governor ruled single stocks out as FADE proxies, v5.2.13);
  C. looser setup thresholds that let more setups through (pb.vol_mult, pb.min_stop_pct, fade.retest_tol_pct, x.fade_min_wait).
For each: the trades it adds (in the new run, not in the live run) and the trades it displaces (one position at a time), and the whole account.
The pass bar is the governor's own v5.2.21 rule, fixed before looking: added trades win >= 60%, average > +0.1% of the account, positive in both halves;
and the whole account keeps its %/day and win rate and its drawdown does not grow by more than 0.5 point. Passers are replayed on Massive bars before 2026-03 when given.
In-sample, many candidates: expect a few to pass by chance. Changes no order, rule or state."""
import contextlib, gzip, io, json, os, statistics as st, sys
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
BASE = I.champion_values(I.tun()); D = None; SYMS = None; DAYS = None
FADE_ETF = {'SPY': ('UPRO', 'SPXU', 3, 3), 'TLT': ('TMF', 'TMV', 3, 3), 'XLE': ('ERX', 'ERY', 2, 2), 'XOP': ('GUSH', 'DRIP', 2, 2), 'GDX': ('NUGT', 'DUST', 2, 2),
            'FXI': ('YINN', 'YANG', 3, 3), 'SLV': ('AGQ', 'ZSL', 2, 2), 'UNG': ('BOIL', 'KOLD', 2, 2), 'GLD': ('UGL', 'GLL', 2, 2), 'XLU': ('UTSL', 'SDP', 3, 3),
            'XLRE': ('DRN', 'DRV', 3, 3), 'EEM': ('EDC', 'EDZ', 3, 3), 'KRE': ('DPST', 'FAZ', 3, 3), 'SMH': ('USD', 'SSG', 2, 2), 'ETHA': ('ETHU', 'ETHD', 2, 2), 'IBIT': ('BITX', 'SBIT', 2, 2)}
STOCKS = {'AAPL', 'AMD', 'AMZN', 'COIN', 'META', 'MSFT', 'MSTR', 'NVDA', 'TSLA'}
TUNE = [('pb.vol_mult', 1.4), ('pb.vol_mult', 1.3), ('pb.vol_mult', 1.2), ('pb.min_stop_pct', 0.70), ('pb.min_stop_pct', 0.65), ('pb.min_stop_pct', 0.60),
        ('fade.retest_tol_pct', 0.12), ('fade.retest_tol_pct', 0.14), ('fade.retest_tol_pct', 0.16), ('x.fade_min_wait', 0)]


def setup(d, extra=()):
    global D, SYMS, DAYS
    D = d; DAYS = D.days; SYMS = set(I.WANT()) | set(extra)


def replay(over):
    saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
    v = dict(BASE); v.update(over)
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = v, '0000-00-00', '0000-00-00', True
    try:
        eq, daily, trades = 2000.0, [], []
        for i in range(1, len(DAYS)):
            d, pd = DAYS[i], DAYS[i - 1]
            tod = {s: D.bars[s][d][:48] for s in SYMS if d in D.bars.get(s, {})}
            prv = {s: D.bars[s][pd] for s in SYMS if pd in D.bars.get(s, {})}
            with contextlib.redirect_stdout(io.StringIO()):
                taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
            for t in taken:
                if t['status'] == 'closed': trades.append((d, t['system'], t['ticker'], t['k'], t['usd'] / eq * 100))
            daily.append((d, (e2 / eq - 1) * 100)); eq = e2
        return daily, trades
    finally:
        paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved


def acct(daily, trades):
    eq = peak = 1.0; dd = 0.0
    for _, x in daily: eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    w = sum(t[4] for t in trades if t[4] > 0); l = -sum(t[4] for t in trades if t[4] < 0)
    return dict(mean=st.mean(x for _, x in daily), dd=dd, ret=(eq - 1) * 100, n=len(trades), win=100 * sum(1 for t in trades if t[4] > 0) / max(len(trades), 1), pf=w / l if l else 99.0)


def judge(label, over, base, cut):
    daily, trades = replay(over); a = acct(daily, trades); b = acct(*base)
    key = lambda t: t[:4]; bk = {key(t) for t in base[1]}; ck = {key(t) for t in trades}
    add = [t for t in trades if key(t) not in bk]; rem = [t for t in base[1] if key(t) not in ck]
    h1 = [t for t in add if t[0] < cut]; h2 = [t for t in add if t[0] >= cut]
    s = lambda l: sum(t[4] for t in l)
    win = 100 * sum(1 for t in add if t[4] > 0) / len(add) if add else 0.0; avg = s(add) / len(add) if add else 0.0
    ok = (len(add) >= 3 and win >= 60 and avg > 0.1 and s(h1) > 0 and s(h2) > 0 and a['mean'] >= b['mean'] and a['win'] >= b['win'] and a['dd'] <= b['dd'] + 0.5)
    return dict(label=label, over=over, a=a, add=len(add), addwin=win, addavg=avg, h1=s(h1), h2=s(h2), rem=len(rem), remtot=s(rem), ok=ok)


def line(r, b):
    a = r['a']
    return (f"{'PASS' if r['ok'] else '    '} {r['label']:<34} adds {r['add']:3d} win {r['addwin']:3.0f}% avg {r['addavg']:+.2f}% halves {r['h1']:+5.1f}/{r['h2']:+5.1f}  displaces {r['rem']:2d} ({r['remtot']:+5.1f}%) | "
            f"account {a['mean']:+.3f}%/day ({a['mean'] - b['mean']:+.3f}) win {a['win']:3.0f}% ({a['win'] - b['win']:+3.0f}) DD {a['dd']:4.2f} PF {a['pf']:4.2f} n {a['n']}")


def liquid(s, days):
    v = [x[4] * x[3] for d in days if d in D.bars.get(s, {}) for x in D.bars[s][d][6:47]]
    return (st.median(v) if v else 0) >= 250_000


if __name__ == '__main__':
    setup(I.load_data())
    allsyms = sorted(D.bars); cut = DAYS[int(len(DAYS) * I.SPLIT)]
    pbcand = [s for s in allsyms if s not in paper.PB_LIST and s not in STOCKS and s not in paper.FADE_ROWS and liquid(s, DAYS)]
    fadecand = {p: r for p, r in FADE_ETF.items() if p in D.bars and r[0] in D.bars and r[1] in D.bars}
    setup(D, allsyms); base = replay({}); b = acct(*base)
    print(f"{len(DAYS)} Robinhood sessions {DAYS[0]}..{DAYS[-1]} (extra tickers carry data to the end of the base file); halves split at {cut}")
    print(f"live rules: {b['mean']:+.3f}%/day  win {b['win']:.0f}%  DD {b['dd']:.2f}%  PF {b['pf']:.2f}  trades {b['n']}\n")
    jobs = ([(f'PB + {s}', {'x.add_pb': [s]}) for s in pbcand] + [(f'FADE + {p} ({r[0]}/{r[1]})', {'x.add_fade': [[p, *r]]}) for p, r in fadecand.items()]
            + [(f'{k} {v}', {k: v}) for k, v in TUNE])
    with get_context('fork').Pool(4) as pool: R = pool.starmap(judge, [(l, o, base, cut) for l, o in jobs])
    for title, pre in (('A. extra PULLBACK legs', 'PB +'), ('B. extra FADE proxies', 'FADE +'), ('C. looser setup thresholds', '')):
        rs = [r for r in R if (r['label'].startswith(pre) if pre else not (r['label'].startswith('PB +') or r['label'].startswith('FADE +')))]
        print(f"== {title}: {len(rs)} tried, {sum(r['ok'] for r in rs)} pass ==")
        for r in sorted(rs, key=lambda r: (not r['ok'], -r['addavg'] * r['add'])):
            if r['ok'] or r['add'] >= 3: print(line(r, b))
        print()
    P = [r for r in R if r['ok']]
    if len(P) > 1:
        both = {}
        for r in P:
            for k, v in r['over'].items():
                if k in ('x.add_pb', 'x.add_fade'): both.setdefault(k, []).extend(v)
                else: both[k] = v
        print(line(judge('ALL PASSERS TOGETHER', both, base, cut), b))
    if M5 and P:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        setup(DM, sorted(DM.bars)); pre = [d for d in DAYS if d < '2026-03-01']
        print(f"\nOUT OF SAMPLE  Massive bars before 2026-03 ({len(pre)} sessions), passers whose tickers exist there")
        base = replay({}); bm = acct([x for x in base[0] if x[0] < '2026-03-01'], [t for t in base[1] if t[0] < '2026-03-01'])
        print(f"  live rules: {bm['mean']:+.3f}%/day win {bm['win']:.0f}% DD {bm['dd']:.1f}% n {bm['n']}")
        for r in P:
            need = [x for k in ('x.add_pb',) for x in r['over'].get(k, [])] + [x for row in r['over'].get('x.add_fade', []) for x in row[:3]]
            if any(x not in DM.bars for x in need): print(f"  {r['label']:<34} not in the Massive file: {', '.join(x for x in need if x not in DM.bars)}"); continue
            daily, trades = replay(r['over']); pd_ = [x for x in daily if x[0] < '2026-03-01']; pt = [t for t in trades if t[0] < '2026-03-01']
            a = acct(pd_, pt); key = lambda t: t[:4]; bk = {key(t) for t in base[1]}; add = [t for t in pt if key(t) not in bk]
            print(f"  {r['label']:<34} adds {len(add)} win {100 * sum(1 for t in add if t[4] > 0) / max(len(add), 1):3.0f}% avg {st.mean(t[4] for t in add) if add else 0:+.2f}%  | account {a['mean']:+.3f}%/day win {a['win']:.0f}% DD {a['dd']:.1f}%")
