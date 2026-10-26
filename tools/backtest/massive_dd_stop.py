#!/usr/bin/env python3
"""Proposed drawdown stop: no new entries once equity is X% below its high-water mark; the governor clears it after at least N trading days, and the high-water mark restarts at the equity on the clearing day.
    /usr/bin/python3 -I tools/backtest/massive_dd_stop.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_dd_stop.txt
Full system, REAL-leg FADE + PULLBACK, live account rules (whole shares, 5-loss, 3% day, 6 a day, 50% floor), cost +0.10% per round trip. Clearance is assumed after exactly N days (a hand clearance is later or never).
Each year is restarted at $2,000. The high-water mark starts at the deposit.
"""
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import final_system as FS
from lab import get_data
LR = RL.LR


def main():
    D = get_data(); LR.m.rvol = RL.PBF.rvol(D); days = D.days[1:]; rows = {p: RL.FA.ROWS[p] for p in LR.BT.PROXIES}
    fade = [t for p in LR.BT.PROXIES for d in days for t in [RL.real_trade(D, d, p, rows[p])] if t]
    cs = [dict(c, px=LR.leg_px(D, c)) for c in fade + FS.cands(D, days)[1]]
    periods = [(y, [d for d in days if d.startswith(y)]) for y in ('2021', '2022', '2023', '2024', '2025')] + [('2026-03..10', [d for d in days if '2026-03-03' <= d <= '2026-10-14']), ('2026 full', [d for d in days if d.startswith('2026')])]
    print(f"{'rule':<26}" + ''.join(f"{n:>22}" for n, _ in periods))
    print(f"{'':<26}" + ''.join(f"{'end $ / maxDD / stops':>22}" for _ in periods))
    for lab, kw in (('none', {}), ('10% below high, 20d', dict(dd_stop=0.10, dd_pause=20)), ('15% below high, 20d', dict(dd_stop=0.15, dd_pause=20)), ('15% below high, 40d', dict(dd_stop=0.15, dd_pause=40)), ('20% below high, 20d', dict(dd_stop=0.20, dd_pause=20))):
        cells = []
        for n, ds in periods:
            S = set(ds); a = LR.live_account(D, ds, [c for c in cs if c['day'] in S], extra_rt=0.10, **kw)
            cells.append(f"{a['eq']:>8,.0f} /{a['mdd']:>4.0f}% /{a['cnt'].get('dd stops', 0):>2}")
        print(f"{lab:<26}" + ''.join(f"{c:>22}" for c in cells))
    print("\nAll five years in one run (not restarted), same rules:")
    for lab, kw in (('none', {}), ('15% below high, 20d', dict(dd_stop=0.15, dd_pause=20)), ('15% below high, 40d', dict(dd_stop=0.15, dd_pause=40)), ('15% below high, hard stop (no resume)', dict(dd_stop=0.15, dd_pause=10**6)), ('10% below high, hard stop (no resume)', dict(dd_stop=0.10, dd_pause=10**6))):
        a = LR.live_account(D, days, cs, extra_rt=0.10, **kw)
        print(f"   {lab:<24} end ${a['eq']:>7,.0f}  max DD {a['mdd']:>4.0f}%  trades {len(a['taken']):>4}  {dict(a['cnt'])}" + (f"  halted {a['halted']}" if a['halted'] else ''))


if __name__ == '__main__':
    main()
