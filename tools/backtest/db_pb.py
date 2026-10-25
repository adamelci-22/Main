#!/usr/bin/env python3
"""PULLBACK-only backtest of the LIVE rules (v5.2.15, nothing re-tuned) on Databento EQUS.MINI bars, 2023-03-28 .. 2026-10-23.
    /usr/bin/python3 -I tools/backtest/db_pb.py DB_5M.json.gz > tools/backtest/results/db_pb.txt
Live list SOXS LABD TECS UVXY; UVXY was not in the purchase, so the Databento runs use SOXS LABD TECS. PULLBACK trades the fund's own bars,
so the Mini feed's thin volume (about 5-20% of the full tape, many empty 5-min bars on thin funds) matters more here than for FADE.
Same account as the live backtest: $2,000, 3% risk capped at cash, one position at a time, max 3/day, earliest first, ties by RVOL.
"""
import collections, gzip, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
_rh = BT.load
SRC = sys.argv[1]
_raw = json.load(gzip.open(SRC, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
LIVE = ['SOXS', 'LABD', 'TECS']
OTHERS = ['SQQQ', 'TZA', 'SPXU', 'SDS', 'QID', 'SRTY', 'SDOW', 'FAZ', 'ERY', 'DRIP', 'DUST', 'TMV', 'UVIX',
          'TQQQ', 'SOXL', 'TECL', 'LABU', 'TNA', 'FAS', 'NUGT', 'TMF', 'SVIX', 'VIXY']


def load_db():
    import lab
    BT.load = lambda: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None
    return lab.get_data()


def load_rh():
    import lab
    BT.load = _rh; BT.PROXIES = ['QQQ', 'SPY', 'SOXX', 'IWM', 'XLF', 'XLE', 'TLT', 'XBI']; lab._DATA = None
    return lab.get_data()


import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD
PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD', 'UVXY': 'UVXY'})


def cands(D, days, legs):
    for l in legs: PI.PROXY.setdefault(l, l)
    s = PBF.run(D, days, legs, oco_gap=True)
    return [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100,
                 hit=x.get('hit')) for x in s]


def summ(tag, D, days, cs, show_tk=False):
    a = MXD.account(D, days, [c for c in cs if c['day'] in set(days)]); t = a['taken']; dl = a['daily']
    if not t: print(f"{tag:<34} {len(days):>4} days  no trades"); return a
    w = [x for x in t if x['usd'] > 0]; l = [x for x in t if x['usd'] <= 0]; h = len(days) // 2
    print(f"{tag:<34} {len(days):>4} days  trades {len(t):>3} ({len(t)/len(days)*5:.1f}/wk)  win {100*len(w)/len(t):>3.0f}%  "
          f"avg win {st.mean(x['pct'] for x in w) if w else 0:+.2f}% loss {st.mean(x['pct'] for x in l) if l else 0:+.2f}%  {st.mean(dl.values()):+.3f}%/day  "
          f"ret {a['ret']:+6.1f}%  DD {a['mdd']:4.1f}%  H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")
    if show_tk:
        g = collections.defaultdict(list)
        for x in t: g[x['name']].append(x)
        for n, v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
            print(f"      {n:<5} {len(v):3d} trades  win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}%  avg {st.mean(x['pct'] for x in v):+.2f}%  total ${sum(x['usd'] for x in v):+.0f}")
        ex = collections.Counter('target' if x.get('hit') else ('stop' if x['pct'] < -0.1 else '13:30') for x in t)
        print(f"      exits (approx.): {dict(ex)}")
    return a


def main():
    R = load_rh(); m.rvol = PBF.rvol(R); rd = R.days[1:]
    print("== Robinhood data 2026-03-03..10-14 (the original backtest), for reference ==")
    summ('PULLBACK live 4 (+UVXY)', R, rd, cands(R, rd, LIVE + ['UVXY']), True)
    summ('PULLBACK SOXS LABD TECS only', R, rd, cands(R, rd, LIVE), True)
    D = load_db(); m.rvol = PBF.rvol(D); days = D.days[1:]
    print(f"\n== Databento EQUS.MINI, {len(days)} days {days[0]}..{days[-1]}, PULLBACK SOXS LABD TECS (UVXY not in the data) ==")
    c = cands(D, days, LIVE)
    for name, ds in (('ALL', days), ('OUT OF SAMPLE 2023-03..2026-02', [d for d in days if d <= '2026-02-27']),
                     ('Overlap 2026-03-03..10-14', [d for d in days if '2026-03-03' <= d <= '2026-10-14'])):
        summ(name, D, ds, c, True)
    print("\n  by year / half-year")
    for lab_, a_, b_ in (('2023 Apr-Dec', '2023-01-01', '2023-12-31'), ('2024 H1', '2024-01-01', '2024-06-30'), ('2024 H2', '2024-07-01', '2024-12-31'),
                         ('2025 H1', '2025-01-01', '2025-06-30'), ('2025 H2', '2025-07-01', '2025-12-31'), ('2026 Jan-Feb', '2026-01-01', '2026-02-27'),
                         ('2026 Mar-Oct', '2026-03-01', '2026-10-31')):
        summ('  ' + lab_, D, [d for d in days if a_ <= d <= b_], c)
    print("\n  each ticker alone (same rules), ALL / out of sample / 2026 Mar-Oct, %/day and trades")
    oos = [d for d in days if d <= '2026-02-27']; rec = [d for d in days if d >= '2026-03-01']
    for t in LIVE + OTHERS:
        if t not in D.bars: continue
        ct = cands(D, days, [t]); row = []
        for ds in (days, oos, rec):
            a = MXD.account(D, ds, [x for x in ct if x['day'] in set(ds)]); row.append(f"{st.mean(a['daily'].values()):+.3f} ({len(a['taken']):3d})")
        tag = '  (live)' if t in LIVE else ''
        print(f"      {t:<5} " + '   '.join(row) + tag)


if __name__ == '__main__':
    main()
