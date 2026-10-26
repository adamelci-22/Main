#!/usr/bin/env python3
"""Is a new mix better than the live system? FADE on the live six + SPY with a six-fund PULLBACK list, against the live FADE six + live PULLBACK. Massive bars, signal-model FADE legs.
    /usr/bin/python3 -I tools/backtest/massive_combo_compare.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_combo_compare.txt
Systems (FADE proxies + PULLBACK funds):
  LIVE     QQQ SOXX IWM XLK XBI XLF            + SOXS LABD TECS UVXY
  NEW-B    live six + SPY                      + SOXS LABD TECS DRIP UVIX FAZ   (best six on the 2026 window)
  NEW-A    live six + SPY                      + SOXS SRTY TZA SQQQ NUGT FAZ    (best six before 2026)
  NEW-AB   live six + SPY                      + SOXS SRTY DRIP SQQQ NUGT FAZ   (best six on the weaker of both)
  FADE+SPY alone and the live PULLBACK, to separate the two changes.
Account 1 (mixed.account): $2,000, 3% risk capped at cash, one position, 3 entries a day, signal-model costs.
Account 2 (live_account): the same with the A1 gates (5-loss, 3% day stop, 6 entries, 50% floor), continuous sizing, +0.10% round-trip cost. SPY's leg (UPRO) has no price in the data, so whole shares are not applied.
"""
import gzip, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
_raw = json.load(gzip.open(sys.argv[1], 'rt')); _daily = json.load(gzip.open(sys.argv[2], 'rt'))
BT.load = lambda: (_raw, _daily)
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY']
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
import massive_live_rules as LR
from lab import get_data
LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
ROWS = {p: FA.ROWS[p] for p in LIVE6}; ROWS['SPY'] = ('UPRO', 3, 'SPXU', 3)
PBL = {'LIVE': ['SOXS', 'LABD', 'TECS', 'UVXY'], 'B': ['SOXS', 'LABD', 'TECS', 'DRIP', 'UVIX', 'FAZ'], 'A': ['SOXS', 'SRTY', 'TZA', 'SQQQ', 'NUGT', 'FAZ'], 'AB': ['SOXS', 'SRTY', 'DRIP', 'SQQQ', 'NUGT', 'FAZ']}
A_END, B0, B1 = '2026-02-27', '2026-03-03', '2026-10-14'


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    allf = sorted({f for v in PBL.values() for f in v})
    for f in allf: PI.PROXY.setdefault(f, f)
    PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD', 'UVXY': 'UVXY'})
    S = PBF.run(D, days, allf, oco_gap=True)
    pb = {f: [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S if x['inst'] == f] for f in allf}
    fd = {p: MXD.norm_px(EX.fade_trades(D, days, p, ROWS[p]), 'FADE') for p in ROWS}
    f6 = [x for p in LIVE6 for x in fd[p]]; f7 = f6 + fd['SPY']
    systems = {'LIVE (FADE 6 + PB live4)': f6 + [x for f in PBL['LIVE'] for x in pb[f]],
               'FADE+SPY, PB live4': f7 + [x for f in PBL['LIVE'] for x in pb[f]],
               'FADE 6, PB best-six-B': f6 + [x for f in PBL['B'] for x in pb[f]],
               'FADE+SPY, PB best-six-B': f7 + [x for f in PBL['B'] for x in pb[f]],
               'FADE+SPY, PB best-six-A': f7 + [x for f in PBL['A'] for x in pb[f]],
               'FADE+SPY, PB best-six-AB': f7 + [x for f in PBL['AB'] for x in pb[f]]}
    wins = [('B 2026-03..10', [d for d in days if B0 <= d <= B1]), ('A 2021-11..2026-02', [d for d in days if d <= A_END])] + [(y, [d for d in days if d.startswith(y)]) for y in ('2022', '2023', '2024', '2025')]
    def a1(ds, cs):
        S_ = set(ds); a = MXD.account(D, ds, [c for c in cs if c['day'] in S_]); t = a['taken']
        return f"{st.mean(a['daily'].values()):+.3f}%/d {a['ret']:+5.0f}% DD{a['mdd']:>3.0f}% n={len(t):>3} w{100*sum(x['usd']>0 for x in t)/max(len(t),1):>3.0f}%"
    def a2(ds, cs):
        S_ = set(ds); a = LR.live_account(D, ds, [dict(c, px=None) for c in cs if c['day'] in S_], extra_rt=0.10, whole=False)
        return f"{st.mean(a['daily'].values()):+.3f}%/d {a['ret']:+5.0f}% DD{a['mdd']:>3.0f}%"
    print("== Account 1: signal-model costs, 3 entries a day ==")
    print(f"{'system':<28}" + ''.join(f"{n:<36}" for n, _ in wins[:2]))
    for nm, cs in systems.items(): print(f"{nm:<28}" + ''.join(f"{a1(ds, cs):<36}" for _, ds in wins[:2]))
    print("\n== Account 1 by calendar year (each year restarted at $2,000) ==")
    print(f"{'system':<28}" + ''.join(f"{n:<36}" for n, _ in wins[2:]))
    for nm, cs in systems.items(): print(f"{nm:<28}" + ''.join(f"{a1(ds, cs):<36}" for _, ds in wins[2:]))
    print("\n== Account 2: A1 gates, +0.10% cost ==")
    print(f"{'system':<28}" + ''.join(f"{n:<28}" for n, _ in wins))
    for nm, cs in systems.items(): print(f"{nm:<28}" + ''.join(f"{a2(ds, cs):<28}" for _, ds in wins))
    print("\nPULLBACK alone, same windows (account 1):")
    for k, v in PBL.items():
        cs = [x for f in v for x in pb[f]]; print(f"   {k:<6}{' '.join(v):<40}" + ''.join(f"{a1(ds, cs):<36}" for _, ds in wins[:2]))
    print("FADE alone, same windows (account 1):")
    for nm, cs in (('six', f6), ('six + SPY', f7)): print(f"   {nm:<10}{'':<36}" + ''.join(f"{a1(ds, cs):<36}" for _, ds in wins[:2]))


if __name__ == '__main__':
    main()
