#!/usr/bin/env python3
"""Pullback buy - current candidate rules (governor's choices, 2026-10-15). Backtest only; NOT in RULEBOOK.md.
    python3 tools/backtest/pb_final.py > tools/backtest/results_pb_final.txt
Rules (see PULLBACK_SPEC.md):
  Setup on each inverse ticker's own chart (pullback.scan logic): 9:30-9:45 high; later close above it on > 1.5x the prior 6 bars' volume;
  9-EMA > 20-EMA and close > 9-EMA; 2-5 red / lower-high bars whose low sits in the EMA zone; trigger = close above the prior bar's high
  (10:10-12:50); limit buy at the trigger close, filled only if the next bar trades down to it.
  Stop = dip low x (1 - 0.05%).  Skip if stop < 0.75% below entry.  Skip if (morning high - entry) < 0.75 x (entry - stop) or < 0.25%.
  Optional: skip if stop and target are < $0.10 apart (Robinhood OCO minimum; only bites on BTCZ).
  Exit: one OCO - sell 100% at the morning high, or the stop.  Sell anything left at 13:30.
  Account: $2,000, 3% risk capped at cash, one position at a time, max 3 entries/day, earliest trigger first, ties -> higher RVOL.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, pb_inverse as PI
from lab import get_data

BUFFER_PCT, MIN_ROOM, MIN_RR, SELL_BY = 0.05, 0.75, 0.75, 47      # 47 = sell at the 13:30 bar close
TARGET_MODE = 'floor'    # 'floor' = RULEBOOK v5.1 (morning-high WICK rounded DOWN to the cent). Research variants: 'wick' (exact, pre-v5.1), 'body' (top of the body of the high bar), 'mid' (middle of the high bar), 'close' (highest close before the dip)


def target_level(b, pre, hod):
    fl = lambda x: math.floor(x * 100 + 1e-9) / 100
    ih = max(range(pre), key=lambda i: b[i][1])
    if TARGET_MODE == 'wick': return hod
    if TARGET_MODE == 'floor': return fl(hod)
    if TARGET_MODE == 'body': return fl(max(b[ih][0], b[ih][3]))
    if TARGET_MODE == 'mid': return fl((b[ih][1] + b[ih][2]) / 2)
    if TARGET_MODE == 'close': return fl(max(b[i][3] for i in range(pre)))
    raise ValueError(TARGET_MODE)


def scan(b, e9, e20, oco_gap):
    bh = max(x[1] for x in b[:3])
    for j in range(8, 41):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre)); stop = low * (1 - BUFFER_PCT / 100)
            hod = target_level(b, pre, hod)
            lim = b[j][3]
            if b[j + 1][2] > lim: continue
            entry = min(b[j + 1][0], lim)
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < MIN_ROOM: continue
            if (hod - entry) < MIN_RR * (entry - stop) or (hod - entry) / entry * 100 < 0.25: continue
            if oco_gap and hod - stop < 0.10: continue
            return dict(k=j + 1, entry=entry, stop=stop, hod=hod, sig=j)
    return None


def setups(D, days, legs, oco_gap):
    out = []
    for leg in legs:
        for d in days:
            i = D.days.index(d); pd_ = D.days[i - 1]
            if d not in D.bars.get(leg, {}) or pd_ not in D.bars.get(leg, {}): continue
            b = D.bars[leg][d]; pb = D.bars[leg][pd_]
            ser = [x[3] for x in pb] + [x[3] for x in b]; e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
            s = scan(b, e9, e20, oco_gap)
            if s: s.update(day=d, inst=leg, b=b, e20=e20); out.append(s)
    return out


def rvol(D):
    def f(_, p, d, k):
        try:
            pri = D.prior(d, 20); return D.cum[p][d][k] / st.mean(D.cum[p][x][k] for x in pri)
        except Exception: return 0.0
    return f


def run(D, days, legs, oco_gap=False):
    m.rvol = rvol(D); m.LEGS = {l: (PI.PROXY[l], 1) for l in legs}
    S = setups(D, days, legs, oco_gap)
    return [t for s in S for t in [PI.manage(s, 1.0, 'be', SELL_BY)] if t]


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"Pullback candidate rules, {days[0]}..{days[-1]} ({len(days)} days). H1 {H1[0]}..{H1[-1]}, H2 {H2[0]}..{H2[-1]}.")
    print("Stop = dip low - 0.05%; one OCO 100% at the morning high; sell rest 13:30; skip target < 0.75x stop distance.\n")
    for lname, legs in (('A: SOXS SQQQ TZA TECS BTCZ', PI.A), ('B: A + LABD + UVXY', PI.B)):
        for gap in (False, True):
            sig = run(D, days, legs, gap)
            a = P.account(sig, D, days); tk = a['taken']
            d1 = st.mean(P.account([x for x in sig if x['day'] in set(H1)], D, H1)['daily'].values())
            d2 = st.mean(P.account([x for x in sig if x['day'] in set(H2)], D, H2)['daily'].values())
            w = [x['pct'] for x in tk if x['usd'] > 0]; l = [x['pct'] for x in tk if x['usd'] <= 0]
            print(f"List {lname} {'+ skip OCO $0.10 gap' if gap else '':<21} trades {len(tk):3d} win {100*len(w)/len(tk):3.0f}% avg win {st.mean(w):+.2f}% "
                  f"avg loss {st.mean(l):+.2f}% | {st.mean(a['daily'].values()):+.3f}%/day ret {a['ret']:+.1f}% maxDD {a['mdd']:.1f}% | H1 {d1:+.3f} H2 {d2:+.3f}")
            if not gap:
                g = collections.defaultdict(lambda: [0, 0.0])
                for x in tk: g[x['inst']][0] += 1; g[x['inst']][1] += x['usd']
                print('      by ticker: ' + ', '.join(f"{k} {n}tr {u:+.0f}$" for k, (n, u) in sorted(g.items(), key=lambda kv: -kv[1][1])))
                print('      exits: ' + str(dict(collections.Counter('target' if x['hit'] else ('stop' if x['xbar'] < SELL_BY else '13:30') for x in tk))))
        print()


if __name__ == '__main__':
    main()
