#!/usr/bin/env python3
"""Does 'PULLBACK stop sits inside one typical 5-minute bar range' predict stop-outs on a bigger sample? (governor question 2026-11-05, after SOXS/MSFU on 11-04)
    python3 -I tools/backtest/pb_stop_noise_check.py M5.json.gz
Replays every session with paper.simulate (rules in force, as improve.run_cf), keeps each PULLBACK trade with: stop distance / typical range (median 5-minute range % of the
12 bars before the trigger), reward/risk, upper-wick share of the morning-high bar, entry time. Reports win rate, stopped share and average by bucket, for 2021-11..2026-02 and
2026-03 on, and what a stand-aside on stop < X ranges would have done. In-sample, Massive feed (hypothesis only). Changes no order, rule or state."""
import contextlib, gzip, io, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
M5 = sys.argv[1]
with contextlib.redirect_stdout(io.StringIO()):
    import backtest as BT, lab
    _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
    BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
    lab._DATA = None; D = lab.get_data()
import improve as I, paper


def feats(b, k, entry, stop0, target):
    stop_pct = (entry - stop0) / entry * 100
    rng = st.median((b[i][1] - b[i][2]) / b[i][3] * 100 for i in range(max(0, k - 13), k - 1))
    hi = max(range(k), key=lambda i: b[i][1]); o, h, l, c, _ = b[hi]
    return dict(stop_pct=stop_pct, rr=(target - entry) / (entry - stop0), stop_rng=stop_pct / rng if rng else 99.0, wick=(h - max(o, c)) / (h - l) if h > l else 0.0, k=k)


vals = I.champion_values(I.tun()); saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = vals, '0000-00-00', '0000-00-00', True
rows, eq = [], 2000.0
try:
    for i in range(1, len(D.days)):
        d, pd = D.days[i], D.days[i - 1]
        tod = {s: D.bars[s][d][:48] for s in I.WANT() if d in D.bars.get(s, {})}
        prv = {s: D.bars[s][pd] for s in I.WANT() if pd in D.bars.get(s, {})}
        taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
        for c in taken:
            if c['system'] != 'PB' or c['status'] != 'closed': continue
            f = feats(tod[c['ticker']], c['k'], c['entry'], c['stop0'], c['target']); f.update(day=d, acct=c['usd'] / eq * 100, win=c['usd'] > 0, stopped=c['why'] == 'stop', ticker=c['ticker'])
            rows.append(f)
        eq = e2
finally:
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved


def line(name, r):
    if not r: return f"  {name:<34} n=0"
    return (f"  {name:<34} n={len(r):3d} win {100 * sum(x['win'] for x in r) / len(r):3.0f}%  stopped {100 * sum(x['stopped'] for x in r) / len(r):3.0f}%  "
            f"avg {st.mean(x['acct'] for x in r):+.3f}%  total {sum(x['acct'] for x in r):+7.2f}%")


for tag, sel in (('ALL 2021-11..2026-11', lambda r: True), ('BEFORE 2026-03 (no edge years)', lambda r: r['day'] < '2026-03-01'), ('2026-03 ON (live regime)', lambda r: r['day'] >= '2026-03-01')):
    R = [r for r in rows if sel(r)]
    print(f"\n== {tag}: {len(R)} PULLBACK trades ==")
    print(line('all', R))
    for name, cond in (('stop < 0.8 typical ranges', lambda r: r['stop_rng'] < 0.8), ('stop 0.8 to 1.0', lambda r: 0.8 <= r['stop_rng'] < 1.0), ('stop 1.0 to 1.5', lambda r: 1.0 <= r['stop_rng'] < 1.5),
                       ('stop >= 1.5', lambda r: r['stop_rng'] >= 1.5), ('stop < 1.0 (the candidate rule)', lambda r: r['stop_rng'] < 1.0), ('stop >= 1.0', lambda r: r['stop_rng'] >= 1.0),
                       ('reward/risk < 1.0', lambda r: r['rr'] < 1.0), ('reward/risk >= 1.0', lambda r: r['rr'] >= 1.0),
                       ('upper wick >= 50% (spike high)', lambda r: r['wick'] >= 0.5), ('entry before 11:30', lambda r: r['k'] < 24), ('entry 11:30 or later', lambda r: r['k'] >= 24)):
        print(line(name, [r for r in R if cond(r)]))
print("\nby year, trades with stop < 1.0 typical range against the rest")
for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
    a = [r for r in rows if r['day'].startswith(y) and r['stop_rng'] < 1.0]; b = [r for r in rows if r['day'].startswith(y) and r['stop_rng'] >= 1.0]
    if a and b: print(f"  {y}: stop<1.0 n={len(a):2d} stopped {100 * sum(x['stopped'] for x in a) / len(a):3.0f}% avg {st.mean(x['acct'] for x in a):+.2f}%   |   rest n={len(b):3d} stopped {100 * sum(x['stopped'] for x in b) / len(b):3.0f}% avg {st.mean(x['acct'] for x in b):+.2f}%")
print("\nthe candidate safety as a stand-aside on PULLBACK entries (trades removed, account % they carried)")
for X in (0.8, 1.0, 1.2, 1.5):
    rem = [r for r in rows if r['stop_rng'] < X]; keep = [r for r in rows if r['stop_rng'] >= X]
    print(f"  skip stop < {X:.1f} ranges: removes {len(rem)} of {len(rows)} trades, they netted {sum(x['acct'] for x in rem):+.2f}% of the account (avg {st.mean(x['acct'] for x in rem):+.2f}%); kept {len(keep)} avg {st.mean(x['acct'] for x in keep):+.2f}%")


import random
def perm(sel, n=20000):
    a = [x['acct'] for x in rows if sel(x)]; b = [x['acct'] for x in rows if not sel(x)]
    obs = st.mean(a) - st.mean(b); pool = a + b; rnd = random.Random(3); k = 0
    for _ in range(n):
        rnd.shuffle(pool); k += abs(st.mean(pool[:len(a)]) - st.mean(pool[len(a):])) >= abs(obs)
    return len(a), len(b), st.mean(a), st.mean(b), k / n
print("\nPERMUTATION TESTS on average account % per trade (cut against the rest), 307 trades")
for name, cond in (('stop < 1.0 typical range', lambda x: x['stop_rng'] < 1.0), ('upper wick >= 50% (spike high)', lambda x: x['wick'] >= 0.5),
                   ('entry 11:30 or later', lambda x: x['k'] >= 24), ('reward/risk >= 1.0', lambda x: x['rr'] >= 1.0)):
    na, nb, ma, mb, p = perm(cond); print(f"  {name:<34} cut n={na:3d} avg {ma:+.3f}%   rest n={nb:3d} avg {mb:+.3f}%   p {p:.3f}")
print("  ... of 4 cuts tried (plus the ~10 in the earlier post-mortem), so expect one at p < 0.1 by chance")
