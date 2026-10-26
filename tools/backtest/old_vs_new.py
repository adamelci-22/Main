#!/usr/bin/env python3
"""OLD (live v5.2.16: 30-min box FADE + PULLBACK, 3% risk) vs NEW (same signals, 1% risk + pause rules) vs NEW+ (10-min box FADE from 9:50 + PULLBACK, 0.5% risk + pause rules).
One continuous $2,000 account per column over the 5 years (so yearly rows differ a little from the restart-each-year table).   /usr/bin/python3 -I tools/backtest/old_vs_new.py M5.json.gz > results/old_vs_new.txt
Pause rule (simulated): after each live trade, pause if the last 40 live trades average R < 0, or equity is 8% below its high. While paused the same signals are tracked on paper;
resume when the last 40 paper trades average R > 0 (stand-in for the governor's manual restart). R = trade % / its stop risk %. Skipping a trade is applied after the account picks it
(a skipped trade does not free its slot for another signal; small effect). The -15% hard stop never binds before the 8% rule here."""
import collections, contextlib, io, os, statistics as st, sys
SRC = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.argv = ['massive_bt.py', SRC]
with contextlib.redirect_stdout(io.StringIO()):
    import massive_bt as MB
import mixed as MXD, fade_diag as F
D = MB.load('massive'); days = D.days[1:]
mf, mp = MB.cands(D, days)
ds = F.DS(SRC, F.ALL); ctx = F.context(ds, [s for s in F.ALL if s in ds.bars])
T10 = F.trades(ds, [d for d in days if d in ds.idx], F.LIVE, F.P(box=2, brk_end=5), ctx)
f10 = [dict(day=t['day'], sys='FADE', name=t['proxy'] + ('+' if t['side'] > 0 else '-'), proxy=t['proxy'], k=t['k'], xbar=t['xbar'], pct=t['pct'], risk=t['leg_risk']) for t in T10]


def simulate(cands, risk, pause):
    a = MXD.account(D, days, cands, risk=risk); taken = a['taken']; by = collections.defaultdict(list)
    for x in taken: by[x['day']].append(x)
    eq = 2000.0; peak = eq; live = True; lh = []; ph = []; daily = {}; live_n = []; paused_days = 0; npause = 0; curve = {}
    for d in days:
        e0 = eq
        if not live: paused_days += 1
        for x in by.get(d, []):
            R = x['pct'] / x['risk'] if x['risk'] else 0.0; f = min(1.0, risk / (x['risk'] / 100)) if x['risk'] else 0.0
            if live:
                eq *= 1 + f * x['pct'] / 100; peak = max(peak, eq); lh.append(R); live_n.append(x)
                if pause and ((len(lh) >= 40 and st.mean(lh[-40:]) < 0) or eq <= 0.92 * peak): live = False; ph = []; npause += 1
            else:
                ph.append(R)
                if len(ph) >= 40 and st.mean(ph[-40:]) > 0: live = True; lh = []; peak = eq
        daily[d] = (eq / e0 - 1) * 100; curve[d] = eq
    return daily, curve, live_n, paused_days, npause


def block(tag, daily, curve, live_n, sel):
    dd = [d for d in days if sel(d)]
    if not dd: return
    e0 = curve[days[days.index(dd[0]) - 1]] if days.index(dd[0]) else 2000.0
    ret = (curve[dd[-1]] / e0 - 1) * 100; pk = e0; mdd = 0.0
    for d in dd: pk = max(pk, curve[d]); mdd = max(mdd, (pk - curve[d]) / pk * 100)
    S = set(dd); tr = [x for x in live_n if x['day'] in S]
    return dict(n=len(tr), win=100 * sum(1 for x in tr if x['pct'] > 0) / len(tr) if tr else 0.0, avg=st.mean(daily[d] for d in dd), ret=ret, mdd=mdd, active=100 * len({x['day'] for x in tr}) / len(dd))


cols = {'OLD  live: 30-min box, 3% risk': simulate(mf + mp, 0.03, False), 'NEW  1% risk + pause rules': simulate(mf + mp, 0.01, True), 'NEW+ 10-min box (from 9:50), 0.5% risk + pause rules': simulate(f10 + mp, 0.005, True)}
print(f"Massive 5-minute bars {days[0]}..{days[-1]} ({len(days)} days). FADE six proxies + PULLBACK SOXS LABD TECS UVXY. One continuous $2,000 account per column.\n")
periods = [('2021 (Nov-Dec)', lambda d: d < '2022'), ('2022', lambda d: d.startswith('2022')), ('2023', lambda d: d.startswith('2023')), ('2024', lambda d: d.startswith('2024')),
           ('2025', lambda d: d.startswith('2025')), ('2026 to Oct 23', lambda d: d.startswith('2026')), ('ALL 5 YEARS', lambda d: True), ('before 2026-03', lambda d: d < '2026-03-01'), ('since 2026-03', lambda d: d >= '2026-03-01')]
for name, sel in periods:
    print(f"== {name} ==")
    for k, (daily, curve, live_n, pdays, npause) in cols.items():
        r = block(k, daily, curve, live_n, sel)
        print(f"  {k:<54} trades {r['n']:4d}  win {r['win']:3.0f}%  avg/day {r['avg']:+.3f}%  return {r['ret']:+8.1f}%  max DD {r['mdd']:5.1f}%  trading on {r['active']:3.0f}% of days")
print("\npauses: " + '; '.join(f"{k.split()[0]} {'+' if k.startswith('NEW+') else ''}: {v[4]} pauses, {v[3]} of {len(days)} days paused" for k, v in cols.items() if k.startswith('NEW')))
for k, (daily, curve, live_n, pdays, npause) in cols.items(): print(f"final equity from $2,000: {k:<54} ${curve[days[-1]]:,.0f}")
