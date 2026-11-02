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
LAST_TRIGGER = 40           # paper.pullback: trigger bar index j < 41 (12:50 bar)


def dip_bar(t, i):
    return t[i][3] < t[i][0] or t[i][1] < t[i - 1][1]


def stage(t, p, K, e9, e20, bh, bo):
    """Where the setup stands for a trigger on the NEXT bar (index K). Returns (text, armed)."""
    if K > LAST_TRIGGER: return 'past the trigger window (last trigger bar 12:50)', False
    if not bo: return 'no volume breakout yet', False
    if K < 9: return 'too early', False
    run = 0
    for i in range(K - 1, 3, -1):
        if dip_bar(t, i): run += 1
        else: break
    trend = e9[K - 1] > e20[K - 1] and t[K - 1][3] > e9[K - 1]
    if run < 2:
        return f'dip {run} bar{"s" if run != 1 else ""} (needs 2 to 5 red or lower-high bars)' + ('' if trend else ', trend off'), False
    notes = []
    for n in (2, 3, 4, 5):
        if n > run or K - n < 4: continue
        low = min(t[i][2] for i in range(K - n, K)); lo_b, hi_b = e20[K - 1] * 0.995, e9[K - 1] * 1.001
        if not (lo_b <= low <= hi_b):
            notes.append(f'{n}-bar dip low {low:.2f} outside EMA band {lo_b:.2f} to {hi_b:.2f}'); continue
        pre = K - n
        if not any(i in bo for i in range(3, pre)): notes.append(f'{n}-bar dip starts before the breakout'); continue
        hod = max(t[i][1] for i in range(0, pre))
        if P.FLOOR_TARGET: hod = math.floor(hod * 100 + 1e-9) / 100
        stop = low * (1 - P.PB_BUF / 100)
        # The trigger bar must close above the last high (paper.pullback: b[j][3] > b[j-1][1]). The skip rules (B3.7, B3.8) then pull in opposite
        # directions on that close (the limit): the stop distance needs it high enough, the reward needs it low enough. So give the window of closes that pass.
        lo = max(t[K - 1][1] + 0.01, stop / (1 - P.PB_MIN_STOP / 100))
        hi = min((hod + 0.75 * stop) / 1.75, hod / 1.0025, hod - 0.01)
        if hod - stop < 0.10 or lo > hi:
            if t[K - 1][1] + 0.01 > hi: why = f'trigger close would have to exceed {t[K - 1][1]:.2f} but the reward rules cap it at {hi:.2f} (morning high {hod:.2f})'
            else: why = f'stop distance needs a close of at least {lo:.2f} but the reward rules cap it at {hi:.2f} (morning high {hod:.2f}, stop {stop:.2f})'
            notes.append(f'{n}-bar dip blocked by skip rules: {why}'); continue
        return (f'ARMED ({n}-bar dip): a bar closing above {t[K - 1][1]:.2f} triggers, and it passes the skip rules only if it closes between {lo:.2f} and {hi:.2f}. '
                f'stop {stop:.2f}, target {hod:.2f}' + ('' if trend else ' (trend off now)')), True
    return 'dip in progress (' + str(run) + ' bars), not armed: ' + '; '.join(notes) if notes else f'dip {run} bars, not armed', False


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
    txt, armed = stage(t, p, K, e9, e20, bh, set(bo))
    print(f"{head} | stage: {txt}")
