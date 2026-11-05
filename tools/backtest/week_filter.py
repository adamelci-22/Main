#!/usr/bin/env python3
"""What if the system sat out every week with national election results or a Fed rate-hike decision? (governor question 2026-11-05)
    python3 -I tools/backtest/week_filter.py M5.json.gz CACHE.json
Same replay as event_study.py (improve.run_cf on Massive 5-minute bars, rules in force). A 'week' is Monday to Friday. Election week = the week of election day (results
come that night and the next sessions). Hike week = the week of each FOMC decision that raised the rate (the 11 hikes of 2022-03-16 to 2023-07-26; the dates are from the
session's own knowledge of the Fed's actions, not read from a page). The replay is cached in CACHE.json so reruns are instant. In-sample, tiny samples.
Changes no order, rule or state."""
import contextlib, gzip, io, json, os, random, statistics as st, sys
from datetime import date, timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
M5, CACHE = sys.argv[1], sys.argv[2]
HIKES = ['2022-03-16', '2022-05-04', '2022-06-15', '2022-07-27', '2022-09-21', '2022-11-02', '2022-12-14', '2023-02-01', '2023-03-22', '2023-05-03', '2023-07-26']
ELECT = ['2022-11-08', '2024-11-05', '2026-11-03']
FOMC = json.load(open(sys.argv[3]))['fomc'] if len(sys.argv) > 3 else []
if os.path.exists(CACHE): c = json.load(open(CACHE)); daily, trades = c['daily'], c['trades']
else:
    with contextlib.redirect_stdout(io.StringIO()):
        import backtest as BT, lab
        _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
        BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
        lab._DATA = None; D = lab.get_data()
    import improve as I
    daily, trades = I.run_cf(D, I.champion_values(I.tun()))
    json.dump(dict(daily=daily, trades=[list(t) for t in trades]), open(CACHE, 'w'))
days = [d for d, _ in daily]; ret = dict(daily)
tr = {}
for d, usd, pct, sysm, r2 in trades: tr.setdefault(d, []).append((sysm, pct))


def week(d): x = date.fromisoformat(d); m = x - timedelta(days=x.weekday()); return m.isoformat()
def wk_days(anchors): ws = {week(a) for a in anchors}; return {d for d in days if week(d) in ws}


def curve(skip):
    eq = peak = 1.0; dd = 0.0; r = []
    for d in days:
        x = 0.0 if d in skip else ret[d]; r.append(x); eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    h = len(r) // 2
    return (eq - 1) * 100, dd, st.mean(r), st.mean(r[:h]), st.mean(r[h:])


def perm(sel, n=20000):
    a = [ret[d] for d in sel]; b = [ret[d] for d in days if d not in sel]
    if len(a) < 3: return None
    obs = st.mean(a) - st.mean(b); pool = a + b; rnd = random.Random(7); k = 0
    for _ in range(n):
        rnd.shuffle(pool); k += abs(st.mean(pool[:len(a)]) - st.mean(pool[len(a):])) >= abs(obs)
    return k / n


E = wk_days(ELECT); H = wk_days(HIKES); A = E | H; F = wk_days([x for x in FOMC if x in days or True]) if FOMC else set()
print(f"{len(days)} sessions {days[0]}..{days[-1]}  base {st.mean(ret.values()):+.3f}%/day\n")
print(f"{'sit out':<46} {'days':>5} {'weeks':>5} {'ret%':>8} {'DD%':>6} {'%/day':>7} {'H1':>7} {'H2':>7} {'p':>6}  removed trades")
b = curve(set()); print(f"{'(nothing)':<46} {0:5d} {0:5d} {b[0]:8.1f} {b[1]:6.2f} {b[2]:+7.3f} {b[3]:+7.3f} {b[4]:+7.3f}")
for name, s in (('election weeks', E), ('rate-hike weeks', H), ('election weeks + rate-hike weeks', A), ('every FOMC decision week (hike, hold or cut)', F)):
    if not s: continue
    c = curve(s); rem = [x for d in s for x in tr.get(d, [])]; p = perm(s)
    w = 100 * sum(1 for x in rem if x[1] > 0) / len(rem) if rem else 0
    print(f"{name:<46} {len(s):5d} {len({week(d) for d in s}):5d} {c[0]:8.1f} {c[1]:6.2f} {c[2]:+7.3f} {c[3]:+7.3f} {c[4]:+7.3f} {('%.3f' % p) if p is not None else ' n/a':>6}  n={len(rem)} win {w:3.0f}% avg {st.mean(x[1] for x in rem) if rem else 0:+.2f}% total {sum(x[1] for x in rem):+.2f}%")
print("\nelection weeks, day by day (account %, trades)")
for d in sorted(E): print(f"  {d} {date.fromisoformat(d).strftime('%a')} {ret[d]:+6.2f}%  " + ', '.join(f"{x[0]} {x[1]:+.2f}%" for x in tr.get(d, [])))
print("\nrate-hike weeks: account % for the whole week, by hike")
for h in HIKES:
    ds = sorted(d for d in days if week(d) == week(h));
    if ds: print(f"  hike {h}: week of {ds[0]}  {sum(ret[d] for d in ds):+6.2f}%  trades " + ', '.join(f"{x[0]} {x[1]:+.2f}%" for d in ds for x in tr.get(d, [])))
print("\nthe same hike weeks in the last two years of the data, other weeks of equal length for comparison")
ws = sorted({week(d) for d in days}); import collections
wr = {w: sum(ret[d] for d in days if week(d) == w) for w in ws}
hw = {week(h) for h in HIKES}
print(f"  hike weeks: n={len(hw & set(ws))} mean {st.mean(wr[w] for w in hw if w in wr):+.3f}%/week   all other weeks: n={len(ws) - len(hw & set(ws))} mean {st.mean(wr[w] for w in ws if w not in hw):+.3f}%/week")
ew = {week(d) for d in ELECT}
print(f"  election weeks: n={len(ew & set(ws))} mean {st.mean(wr[w] for w in ew if w in wr):+.3f}%/week")
