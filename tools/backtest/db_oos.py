#!/usr/bin/env python3
"""Out-of-sample run of the LIVE rules (v5.2.15, nothing re-tuned) on Databento EQUS.MINI bars, 2023-03-28 .. 2026-10-23.
    /usr/bin/python3 tools/backtest/db_oos.py DB_5M.json.gz > tools/backtest/results/db_oos.txt
FADE needs only the six proxies (QQQ SOXX IWM XLK XBI XLF; legs modelled as leverage x proxy, as in the live backtest).
PULLBACK needs the funds' own bars: SOXS LABD TECS are in the data, UVXY was not purchased, so PULLBACK here is SOXS+LABD+TECS only and is
a rougher test (EQUS.MINI volume is about 5-20% of the full tape and thin funds have many empty 5-minute bars).
Windows: 2023-03-28..2026-02-27 is entirely before the data the rules were chosen on (out of sample); 2026-03-03..2026-10-14 reproduces the earlier backtest.
"""
import collections, gzip, json, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
SRC = sys.argv[1]
_raw = json.load(gzip.open(SRC, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
from lab import get_data
FADE = BT.PROXIES
PB = ['SOXS', 'LABD', 'TECS']


def summ(tag, D, days, cs):
    a = MXD.account(D, days, cs); t = a['taken']; dl = a['daily']
    if not t: print(f"{tag:<40} no trades"); return a
    w = [x for x in t if x['usd'] > 0]; h = len(days) // 2
    print(f"{tag:<40} {len(days):>4} days  trades {len(t):>3} ({len(t)/len(days)*5:.1f}/wk)  win {100*len(w)/len(t):>3.0f}%  {st.mean(dl.values()):+.3f}%/day  ret {a['ret']:+7.1f}%  DD {a['mdd']:>4.1f}%  "
          f"H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
    return a


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    print(f"Databento EQUS.MINI, regular hours, split-adjusted; {len(days)} trading days {days[0]}..{days[-1]}\n")
    f = [c for p in FADE for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')]
    PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD'})
    PBF.run  # noqa
    s = PBF.run(D, days, PB, oco_gap=True)
    p = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    win = {'ALL (2023-03-28..2026-10-23)': days,
           'OUT OF SAMPLE 2023-03-28..2026-02-27': [d for d in days if d <= '2026-02-27'],
           'Overlap with earlier backtest 2026-03-03..10-14': [d for d in days if '2026-03-03' <= d <= '2026-10-14']}
    for name, ds in win.items():
        S = set(ds); fc = [c for c in f if c['day'] in S]; pc = [c for c in p if c['day'] in S]
        print(f"== {name} ==")
        summ('FADE alone (6 proxies)', D, ds, fc); summ('PULLBACK alone (SOXS LABD TECS)', D, ds, pc); summ('FADE + PULLBACK(3)', D, ds, fc + pc); print()
    print("== By calendar year, FADE alone and combined ==")
    for y in ('2023', '2024', '2025', '2026'):
        ds = [d for d in days if d.startswith(y)]; S = set(ds)
        summ(f'{y} FADE', D, ds, [c for c in f if c['day'] in S]); summ(f'{y} FADE + PULLBACK(3)', D, ds, [c for c in f + p if c['day'] in S])
    print("\n== By half-year (FADE + PULLBACK(3)) ==")
    for lab, a_, b_ in (('2023 Apr-Dec', '2023-03-28', '2023-12-31'), ('2024 H1', '2024-01-01', '2024-06-30'), ('2024 H2', '2024-07-01', '2024-12-31'), ('2025 H1', '2025-01-01', '2025-06-30'),
                        ('2025 H2', '2025-07-01', '2025-12-31'), ('2026 Jan-Feb', '2026-01-01', '2026-02-27'), ('2026 Mar-Oct', '2026-03-03', '2026-10-14')):
        ds = [d for d in days if a_ <= d <= b_]; S = set(ds)
        summ(lab, D, ds, [c for c in f + p if c['day'] in S])
    print("\n== FADE by proxy over 2023-03-28..2026-02-27 (trades taken in the account, FADE alone) ==")
    S = set(win['OUT OF SAMPLE 2023-03-28..2026-02-27']); a = MXD.account(D, sorted(S), [c for c in f if c['day'] in S])
    g = collections.defaultdict(list)
    for x in a['taken']: g[x['proxy']].append(x)
    for q, v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
        r = sorted(x['usd'] for x in v)
        print(f"   {q:<5} {len(v):3d} trades win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}% avg {st.mean(x['pct'] for x in v):+.2f}% total ${sum(r):+.0f}  without best 2 ${sum(r[:-2]):+.0f}")


if __name__ == '__main__':
    main()
