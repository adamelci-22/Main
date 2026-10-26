#!/usr/bin/env python3
"""LIVE rules (v5.2.16, nothing re-tuned) on Massive consolidated-tape 5-minute bars, about 5 years (Starter plan limit).
    /usr/bin/python3 -I tools/backtest/massive_bt.py M5.json.gz > tools/backtest/results/massive_5y.txt
FADE QQQ SOXX IWM XLK XBI XLF (legs = leverage x proxy, as in the live backtest); PULLBACK SOXS LABD TECS UVXY on the funds' own bars.
Also: (1) feed check against the Robinhood cache on the shared days, (2) by year / half-year, (3) FADE-only and PULLBACK-only."""
import collections, gzip, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
_rh_load = BT.load
SRC = sys.argv[1]
_raw = json.load(gzip.open(SRC, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
import lab, manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
FADE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; PB = ['SOXS', 'LABD', 'TECS', 'UVXY']
PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD', 'UVXY': 'UVXY'})


def load(kind):
    if kind == 'rh': BT.load = _rh_load; BT.PROXIES = ['QQQ', 'SPY', 'SOXX', 'IWM', 'XLF', 'XLE', 'TLT', 'XBI']
    else: BT.load = lambda: (_raw, _daily); BT.PROXIES = FADE
    lab._DATA = None; D = lab.get_data(); m.rvol = PBF.rvol(D); return D


def cands(D, days, fade=True, pb=True):
    f = [c for p in FADE for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')] if fade else []
    p = []
    if pb:
        s = PBF.run(D, days, [x for x in PB if x in D.bars], oco_gap=True)
        p = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    return f, p


def summ(tag, D, days, cs):
    S = set(days); a = MXD.account(D, days, [c for c in cs if c['day'] in S]); t = a['taken']; dl = a['daily']
    if not t: print(f"{tag:<34} {len(days):>4} days  no trades"); return a
    w = [x for x in t if x['usd'] > 0]; h = len(days) // 2
    print(f"{tag:<34} {len(days):>4} days  trades {len(t):>3} ({len(t)/len(days)*5:.1f}/wk)  win {100*len(w)/len(t):>3.0f}%  {st.mean(dl.values()):+.3f}%/day  "
          f"ret {a['ret']:+8.1f}%  DD {a['mdd']:5.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
    return a


def main():
    R = load('rh'); rdays = R.days[1:]; rf, rp = cands(R, rdays)
    D = load('massive'); days = D.days[1:]; mf, mp = cands(D, days)
    print(f"Massive 5-minute bars, regular hours, split-adjusted: {len(days)} trading days {days[0]}..{days[-1]}\n")
    print("== FEED CHECK on the shared days 2026-03-03..10-14 (Robinhood vs Massive) ==")
    sh = [d for d in rdays if d in D.idx_map] if hasattr(D, 'idx_map') else [d for d in rdays if d in set(days)]
    for name, rc, mc in (('FADE', rf, mf), ('PULLBACK', rp, mp)):
        a = {(c['day'], c['name']): c for c in rc if c['day'] in set(sh)}; b = {(c['day'], c['name']): c for c in mc if c['day'] in set(sh)}; both = set(a) & set(b)
        print(f"  {name}: setups RH {len(a)}, Massive {len(b)}, same day+name {len(both)}"
              + (f"; same entry bar {sum(a[k]['k']==b[k]['k'] for k in both)}, same win/loss {sum((a[k]['pct']>0)==(b[k]['pct']>0) for k in both)}; avg RH {st.mean(a[k]['pct'] for k in both):+.2f}% vs Massive {st.mean(b[k]['pct'] for k in both):+.2f}%" if both else ''))
    S = set(sh); print()
    summ('Robinhood combined (reference)', R, rdays, rf + rp); summ('Massive  combined, same days', D, sh, mf + mp)
    print("\n== LIVE RULES on Massive, all days ==")
    wins = [('ALL', days[0], days[-1])] + [(y, f'{y}-01-01', f'{y}-12-31') for y in ('2021', '2022', '2023', '2024', '2025', '2026')] + \
           [('2022 H1', '2022-01-01', '2022-06-30'), ('2022 H2', '2022-07-01', '2022-12-31'), ('2023 H1', '2023-01-01', '2023-06-30'), ('2023 H2', '2023-07-01', '2023-12-31'),
            ('2024 H1', '2024-01-01', '2024-06-30'), ('2024 H2', '2024-07-01', '2024-12-31'), ('2025 H1', '2025-01-01', '2025-06-30'), ('2025 H2', '2025-07-01', '2025-12-31'),
            ('2026 Jan-Feb', '2026-01-01', '2026-02-27'), ('2026 Mar-Oct', '2026-03-01', '2026-12-31')]
    for sysname, cs in (('FADE + PULLBACK', mf + mp), ('FADE alone', mf), ('PULLBACK alone', mp)):
        print(f"-- {sysname}")
        for lab_, a_, b_ in wins:
            ds = [d for d in days if a_ <= d <= b_]
            if len(ds) > 20: summ('  ' + lab_, D, ds, cs)
    print("\n== by ticker, whole period (combined account) ==")
    a = MXD.account(D, days, mf + mp); g = collections.defaultdict(list)
    for x in a['taken']: g[(x['sys'], x['proxy'] if x['sys'] == 'FADE' else x['name'])].append(x)
    for (s_, n), v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
        print(f"   {s_:<4} {n:<5} {len(v):3d} trades win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}% avg {st.mean(x['pct'] for x in v):+.2f}% total ${sum(x['usd'] for x in v):+.0f}")


if __name__ == '__main__':
    main()
