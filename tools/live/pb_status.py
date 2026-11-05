"""PULLBACK status per leg (reporting only, RULEBOOK C1 / handoff 2026-11-02 'close to entry' update).

Usage: python3 -I tools/live/pb_status.py [--day YYYY-MM-DD] [--now HH:MM] <the three C1.2 dump files>

Prints, for each PULLBACK leg: breakout, trend, and the stage of the dip/trigger setup, using paper.py's own constants, EMA, grid and
skip rules, so it matches the model. It changes no order, signal, size or rule. --day/--now replay an earlier slot from the same dumps
(bars through HH:MM, as paper.py --now). Without them it uses the newest bar in the dumps.
"""
import sys, math, statistics as st
sys.path.insert(0, 'tools/live')
import paper as P

args = sys.argv[1:]; opts = {}
while args and args[0].startswith('--'):
    opts[args[0][2:]] = args[1]; args = args[2:]
raw = P.load(args)
days = sorted({d for s in raw.values() for d in s})
day = opts.get('day') or days[-1]
prevday = max(d for d in days if d < day)
P.apply_tunables(day)      # RULEBOOK D4: the version in force for this day (breakout volume multiple, stop rules)
if 'now' in opts: K = P.t2k(opts['now'])
else: K = (max(m for s_ in raw.values() if day in s_ for m in s_[day]) - 570) // 5 + 1
for leg in P.PB_LIST:
    if day not in raw.get(leg, {}) or prevday not in raw.get(leg, {}):
        print(f"{leg:<5} no bars for {day} or {prevday} in the dumps - fetch all three C1.2 groups"); continue
    t = P.grid(raw[leg][day], K)[:K]; p = P.grid(raw[leg][prevday], 78)
    ser = [x[3] for x in p] + [x[3] for x in t]
    e9 = P.ema(ser, 9)[len(p):]; e20 = P.ema(ser, 20)[len(p):]
    bh = max(x[1] for x in t[:3])
    bo = [i for i in range(3, K) if t[i][3] > bh and t[i][4] > P.PB_VOL * st.mean(t[q][4] for q in range(max(0, i - 6), i))]
    trend = e9[-1] > e20[-1] and t[-1][3] > e9[-1]
    model = P.pullback(t, p, K)
    head = (f"{leg:5} close {t[-1][3]:.2f} {(t[-1][3] / bh - 1) * 100:+.1f}% vs range high {bh:.2f} | vol breakout: {'yes at ' + P.k2t(bo[0]) if bo else 'no'}"
            f" | trend ok: {trend}")
    if model and model['status'] == 'signal':
        print(f"{head} | MODEL SIGNAL: {model['note']} stop {model['stop']:.2f} target {model['target']:.2f}"); continue
    if model:
        print(f"{head} | model trade already {model['status']} (entry {model['entry']:.2f}, stop {model['stop0']:.2f}, target {model['target']:.2f})"); continue
    txt, armed = P.pb_stage(t, p, K, e9, e20, bh, set(bo))
    print(f"{head} | stage: {txt}")
