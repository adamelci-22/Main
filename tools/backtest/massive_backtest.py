#!/usr/bin/env python3
"""Five-year backtest of the LIVE rules (v5.2.15, nothing re-tuned) on Massive bars (full consolidated tape, regular hours, split-adjusted), 2021-11 .. 2026-10.
    /usr/bin/python3 -I tools/backtest/massive_backtest.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz > tools/backtest/results/massive_backtest.txt
    /usr/bin/python3 -I tools/backtest/massive_backtest.py --rh > tools/backtest/results/massive_backtest_rh_check.txt     (same code on the Robinhood bars, 2026-03-03..10-14)
FADE: QQQ SOXX IWM XLK XBI XLF (legs modelled as leverage x proxy, as in final_system.py). PULLBACK: SOXS LABD TECS UVXY on the funds' own bars.
Everything else is final_system.py: $2,000, 3% risk capped at cash, one position at a time, max 3 entries a day, every signal on time (scenario A of full_backtest_v523.py).
Windows: 2026-03-03..10-14 is the period the rules were chosen on (Robinhood bars). Everything before 2026-03-03 is out of sample.
"""
import collections, gzip, json, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
RH = sys.argv[1] == '--rh'
if not RH:
    _raw = json.load(gzip.open(sys.argv[1], 'rt')); _daily = json.load(gzip.open(sys.argv[2], 'rt'))
    BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
import mixed as MXD, manual as m, pb_final as PBF, pb_inverse as PI
import final_system as FS
from lab import get_data


def summ(tag, D, days, cs):
    a = MXD.account(D, days, cs); t = a['taken']; dl = a['daily']
    if not t: print(f"{tag:<44} {len(days):>4} days  no trades"); return a
    w = [x for x in t if x['usd'] > 0]; h = len(days) // 2; sd = st.pstdev(dl.values())
    print(f"{tag:<44} {len(days):>4} days  trades {len(t):>3} ({len(t)/len(days)*5:.1f}/wk)  win {100*len(w)/len(t):>3.0f}%  {st.mean(dl.values()):+.3f}%/day  ret {a['ret']:+8.1f}%  "
          f"DD {a['mdd']:>4.1f}%  Sharpe~{st.mean(dl.values())/sd*math.sqrt(252) if sd else 0:.1f}  H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
    return a


def block(title, D, days, f, p):
    S = set(days); fc = [c for c in f if c['day'] in S]; pc = [c for c in p if c['day'] in S]
    print(f"== {title}: {days[0]}..{days[-1]} ==")
    summ('FADE alone (6 proxies)', D, days, fc); summ('PULLBACK alone (SOXS LABD TECS UVXY)', D, days, pc); a = summ('COMBINED', D, days, fc + pc); print()
    return a


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    print(f"{'Robinhood bars (repo data)' if RH else 'Massive'}: regular hours, split-adjusted; {len(days)} trading days {days[0]}..{days[-1]}\n")
    f, p = FS.cands(D, days)
    print(f"candidates: FADE {len(f)}, PULLBACK {len(p)}\n")
    win = [('ALL', days)] if not RH else []
    win += [('OUT OF SAMPLE (before the rules\' data)', [d for d in days if d <= '2026-02-27']), ('RULES WINDOW 2026-03-03..10-14', [d for d in days if '2026-03-03' <= d <= '2026-10-14']),
            ('UNTOUCHED 2026-03-03..04-06', [d for d in days if '2026-03-03' <= d <= '2026-04-06']), ('SINCE LIVE 2026-10-16..', [d for d in days if d >= '2026-10-16'])]
    for name, ds in win:
        if ds: block(name, D, ds, f, p)
    if RH: return
    print("== By calendar year (combined and each system) ==")
    for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
        ds = [d for d in days if d.startswith(y)]; S = set(ds)
        summ(f'{y} FADE', D, ds, [c for c in f if c['day'] in S]); summ(f'{y} PULLBACK', D, ds, [c for c in p if c['day'] in S]); summ(f'{y} COMBINED', D, ds, [c for c in f + p if c['day'] in S])
    print("\n== By half-year (combined) ==")
    for y in range(2021, 2027):
        for hh, (a_, b_) in enumerate((('01-01', '06-30'), ('07-01', '12-31'))):
            ds = [d for d in days if f'{y}-{a_}' <= d <= f'{y}-{b_}']
            if len(ds) > 20: S = set(ds); summ(f'{y} H{hh+1}', D, ds, [c for c in f + p if c['day'] in S])
    a = MXD.account(D, days, f + p); tk = a['taken']
    print("\n== By system and ticker, whole period (combined account) ==")
    g = collections.defaultdict(list)
    for x in tk: g[(x['sys'], x['proxy'] if x['sys'] == 'FADE' else x['name'])].append(x)
    for (s, n), v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
        r = sorted(x['usd'] for x in v)
        print(f"   {s:<4} {n:<5} {len(v):3d} trades win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}% avg {st.mean(x['pct'] for x in v):+.2f}% total ${sum(r):+.0f}  without best 2 ${sum(r[:-2]):+.0f}")
    print("\n== Month by month (combined, compounding from $2,000) ==")
    mo = collections.OrderedDict(); eq = 2000.0
    for d in days:
        e0 = eq; eq *= 1 + a['daily'][d] / 100; mo.setdefault(d[:7], [e0, eq])[1] = eq
    print('  ' + ', '.join(f"{k} {100*(v[1]/v[0]-1):+.1f}%" for k, v in mo.items()))


if __name__ == '__main__':
    main()
