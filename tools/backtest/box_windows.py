#!/usr/bin/env python3
"""Live rules, ONLY the opening-box length changed: 30 min (live) vs 10 min vs 15 min. Everything else identical: 3% risk, same exits, same 10:15 break deadline, same PULLBACK, no pause rules.
    /usr/bin/python3 -I tools/backtest/box_windows.py M5.json.gz > results/box_windows.txt
'*' rows additionally drop FADE entries before 10:00 (the live checkpoints start at 10:00, so those entries could not be taken today). One continuous $2,000 account per row."""
import collections, contextlib, io, os, statistics as st, sys
SRC = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.argv = ['massive_bt.py', SRC]
with contextlib.redirect_stdout(io.StringIO()):
    import massive_bt as MB
import mixed as MXD, fade_diag as F
D = MB.load('massive'); days = D.days[1:]; mf, mp = MB.cands(D, days)
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars]); dsd = [d for d in days if d in ds.idx]


def cand(T): return [dict(day=t['day'], sys='FADE', name=t['proxy'] + ('+' if t['side'] > 0 else '-'), proxy=t['proxy'], k=t['k'], xbar=t['xbar'], pct=t['pct'], risk=t['leg_risk']) for t in T]


def fade(n, brk_end): return cand(F.trades(ds, dsd, F.LIVE, F.P(box=n, brk_end=brk_end), ctx))


V = {'30-min box (LIVE)': mf, '10-min box': fade(2, 9), '15-min box': fade(3, 9)}
V['10-min box, entries from 10:00 only *'] = [c for c in V['10-min box'] if c['k'] >= 6]; V['15-min box, entries from 10:00 only *'] = [c for c in V['15-min box'] if c['k'] >= 6]
periods = [('2021 (Nov-Dec)', lambda d: d < '2022'), ('2022', lambda d: d.startswith('2022')), ('2023', lambda d: d.startswith('2023')), ('2024', lambda d: d.startswith('2024')),
           ('2025', lambda d: d.startswith('2025')), ('2026 to Oct 23', lambda d: d.startswith('2026')), ('before 2026-03', lambda d: d < '2026-03-01'), ('since 2026-03', lambda d: d >= '2026-03-01'), ('ALL 5 YEARS', lambda d: True)]


def run(cands):
    a = MXD.account(D, days, cands, risk=0.03); eq = 2000.0; curve = {}; by = collections.defaultdict(list)
    for x in a['taken']: by[x['day']].append(x)
    daily = a['daily']
    for d in days: eq *= 1 + daily[d] / 100; curve[d] = eq
    return daily, curve, a['taken']


def stats(daily, curve, taken, sel):
    dd = [d for d in days if sel(d)]; i = days.index(dd[0]); e0 = curve[days[i - 1]] if i else 2000.0; pk = e0; mdd = 0.0
    for d in dd: pk = max(pk, curve[d]); mdd = max(mdd, (pk - curve[d]) / pk * 100)
    S = set(dd); tr = [x for x in taken if x['day'] in S]
    return len(tr), (100 * sum(1 for x in tr if x['usd'] > 0) / len(tr) if tr else 0), st.mean(daily[d] for d in dd), (curve[dd[-1]] / e0 - 1) * 100, mdd


print(f"Massive 5-minute bars {days[0]}..{days[-1]}. Live rules (FADE six proxies + PULLBACK SOXS LABD TECS UVXY, 3% risk). Only the FADE opening-box length differs.\n")
for title, comp in (('COMBINED SYSTEM (FADE + PULLBACK)', True), ('FADE ONLY', False)):
    print("=" * 20, title, "=" * 20)
    R = {k: run((c + mp) if comp else c) for k, c in V.items()}
    for name, sel in periods:
        print(f"== {name} ==")
        for k, (dl, cv, tk) in R.items():
            n, w, a, r, dd_ = stats(dl, cv, tk, sel); print(f"  {k:<44} trades {n:4d}  win {w:3.0f}%  avg/day {a:+.3f}%  return {r:+8.1f}%  max DD {dd_:5.1f}%")
    print("  entry-time mix of FADE setups (share before 10:00): " + ', '.join(f"{k.split(',')[0]} {100*sum(1 for c in V[k] if c['k']<6)/len(V[k]):.0f}%" for k in ('30-min box (LIVE)', '10-min box', '15-min box')))
    print()
