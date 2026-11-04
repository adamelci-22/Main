#!/usr/bin/env python3
"""PULLBACK post-mortem for the two stop-outs of 2026-11-04 (SOXS 11:25, MSFU 12:45), governor question 2026-11-04.
    python3 -I tools/backtest/pb_postmortem_1104.py <the three C1.2 dump files of the 13:30 close>
Part 1: bar-by-bar story of each trade.  Part 2: features of every PULLBACK trade in the dataset (base + live sessions, rule set in force),
split into thirds, and where today's two trades sit.  In-sample, small buckets: a guide, never a rule.  Changes no order, rule or state."""
import os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import improve as I, paper

DAY = '2026-11-04'
def hhmm(k): m = 570 + 5 * k; return f"{m // 60}:{m % 60:02d}"
raw = paper.load(sys.argv[1:])


def feats(b, k, entry, stop0, target, prev_close):
    """b = the leg's 5-minute bars (o,h,l,c,v); k = entry bar index; trigger bar = k-1."""
    stop_pct = (entry - stop0) / entry * 100
    rr = (target - entry) / (entry - stop0)
    rng = st.median((b[i][1] - b[i][2]) / b[i][3] * 100 for i in range(max(0, k - 13), k - 1))
    hi = max(range(k), key=lambda i: b[i][1]); o, h, l, c, _ = b[hi]
    wick = (h - max(o, c)) / (h - l) if h > l else 0.0
    return dict(stop_pct=stop_pct, rr=rr, rng=rng, stop_rng=stop_pct / rng, since_high=k - hi, wick=wick, hi_bar=hhmm(hi),
                day_move=(entry / prev_close - 1) * 100, entry_k=k)


# ---- Part 2 history
D = I.load_data(); t = I.tun(); vals = I.champion_values(t)
saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
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
            f = feats(tod[c['ticker']], c['k'], c['entry'], c['stop0'], c['target'], prv[c['ticker']][-1][3])
            f.update(day=d, ticker=c['ticker'], acct=c['usd'] / eq * 100, win=c['usd'] > 0, why=c['why'])
            rows.append(f)
        eq = e2
finally:
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved

today = []
for leg, k, entry, stop0, target in (('SOXS', 23, 59.64, 58.51, 61.81), ('MSFU', 39, 45.39, 45.04, 45.72)):
    b = paper.grid(raw[leg][DAY], 78); pb = paper.grid(raw[leg][max(d for d in raw[leg] if d < DAY)], 78)
    f = feats(b, k, entry, stop0, target, pb[-1][3]); f['ticker'] = leg; today.append(f)

# ---- Part 1 story
print("PART 1  bar-by-bar (5-minute bars: open high low close, time = bar start ET)")
ctx = {'SOXS': 'SOXX', 'MSFU': 'XLK'}
for f, (leg, lo, hi_) in zip(today, (('SOXS', 17, 29), ('MSFU', 33, 44))):
    b = paper.grid(raw[leg][DAY], 78); cx = paper.grid(raw[ctx[leg]][DAY], 78); cq = paper.grid(raw['QQQ'][DAY], 78)
    print(f"\n{leg}: morning high bar {f['hi_bar']} (upper wick {f['wick']:.0%} of its range, {f['since_high']} bars before entry), stop {f['stop_pct']:.2f}% below entry, "
          f"reward/risk {f['rr']:.2f}, typical 5-minute range {f['rng']:.2f}% so the stop sits {f['stop_rng']:.2f} ranges away, leg is {f['day_move']:+.1f}% on the day")
    for i in range(lo, hi_):
        o, h, l, c, v = b[i]
        print(f"  {hhmm(i):>5}  {o:8.2f} {h:8.2f} {l:8.2f} {c:8.2f}   {ctx[leg]} {cx[i][3]:8.2f} ({(cx[i][3] / cx[i - 1][3] - 1) * 100:+.2f}%)  QQQ {(cq[i][3] / cq[i - 1][3] - 1) * 100:+.2f}%"
              + ('   <- trigger bar' if i == (23 if leg == 'SOXS' else 39) - 1 else '') + ('   <- entry bar' if i == (23 if leg == 'SOXS' else 39) else '')
              + ('   <- stop traded' if (leg == 'SOXS' and i == 24) or (leg == 'MSFU' and i == 41) else ''))

# ---- Part 2 tables
def line(name, r):
    if not r: return f"  {name:<30} n=0"
    return (f"  {name:<30} n={len(r):3d} win {100 * sum(x['win'] for x in r) / len(r):3.0f}%  avg {st.mean(x['acct'] for x in r):+.3f}%  total {sum(x['acct'] for x in r):+7.2f}%  "
            f"stopped {100 * sum(1 for x in r if x['why'] == 'stop') / len(r):3.0f}%")


print(f"\nPART 2  {len(rows)} PULLBACK trades, {D.days[0]}..{D.days[-1]}, rules in force")
print(line('all', rows))
for fname, label in (('stop_rng', 'stop distance / typical 5-minute range'), ('rr', 'reward / risk'), ('stop_pct', 'stop distance, %'),
                     ('wick', 'upper wick share of the morning-high bar'), ('since_high', 'bars from morning high to entry'), ('entry_k', 'entry bar (time of day)'),
                     ('day_move', 'leg move since prior close, %')):
    v = sorted(r[fname] for r in rows); a, b2 = v[len(v) // 3], v[2 * len(v) // 3]
    print(f"{label}: thirds split at {a:.2f} / {b2:.2f}  (today: " + ', '.join(f"{x['ticker']} {x[fname]:.2f}" for x in today) + ")")
    print(line('  low third', [r for r in rows if r[fname] < a])); print(line('  middle third', [r for r in rows if a <= r[fname] < b2])); print(line('  high third', [r for r in rows if r[fname] >= b2]))
print("\nsingle cuts")
for name, cond in (('reward/risk < 1.0', lambda r: r['rr'] < 1.0), ('reward/risk >= 1.0', lambda r: r['rr'] >= 1.0),
                   ('stop < 1 typical range', lambda r: r['stop_rng'] < 1.0), ('stop >= 1 typical range', lambda r: r['stop_rng'] >= 1.0),
                   ('stop < 1.5 typical ranges', lambda r: r['stop_rng'] < 1.5), ('stop >= 1.5 typical ranges', lambda r: r['stop_rng'] >= 1.5),
                   ('wick >= 50% (spike high)', lambda r: r['wick'] >= 0.5), ('wick < 50%', lambda r: r['wick'] < 0.5),
                   ('entry before 11:30', lambda r: r['entry_k'] < 24), ('entry 11:30 to 12:30', lambda r: 24 <= r['entry_k'] < 36), ('entry 12:30 or later', lambda r: r['entry_k'] >= 36)):
    print(line(name, [r for r in rows if cond(r)]))
