#!/usr/bin/env python3
"""Failed-retest fade: the governor's proposed exit and the neighbourhood around it (v3.126 Core Five).
    python3 tools/backtest/fade_combo.py > tools/backtest/results_fade_combo.txt
Proposed: initial stop beyond the failed breakout's extreme; half off at 2R (OCO, fills at the level); held part starts at
breakeven and ratchets with a 2-ATR chandelier (proxy, highest close since entry - 2 x ATR14 of 5-min bars, never down,
moved at checkpoints); sell whatever is left at 12:00.
Grid: target R x fraction sold x runner stop x sell-by time. Judged on both halves; walk-forward pick shown.
"""
import itertools, math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, retest as RT, twobar as TB
from lab import get_data
FADE = RT.RC(fade=True)
TN = {17: '11:00', 23: '11:30', 29: '12:00', 35: '12:30', 47: '13:30', 77: '15:55'}


def run_trade(D, d, p, R=2.0, frac=0.5, runner='chand2', last=29, detail=False):
    raw = D.bars[p][d]; s = RT.setup(raw, FADE)
    if not s: return None
    k, side, e_real, stop_real = s
    if k >= last: return None
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry, stop = to_m(e_real), to_m(stop_real)
    if entry <= stop: return None
    r = entry - stop; T = entry + R * r
    pd_ = D.days[D.days.index(d) - 1]; prev = D.bars[p][pd_] if side > 0 else m.mirror(D.bars[p][pd_])[0]
    e9 = m.ema([x[3] for x in prev] + [x[3] for x in b], 9)[78:]
    gross = 0.0; rem = 1.0; hit = False; hic = entry; why = 'time'; xbar = last; log = []
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross += rem * (px - entry); log.append((j, 'stop' if not hit else 'runner stop', to_m(px), rem)); rem = 0
            why = 'stop' if not hit else 'runner_stop'; xbar = j; break
        if not hit and h >= T:
            px = max(T, o); gross += frac * (px - entry); rem = 1 - frac; hit = True; stop = max(stop, entry)
            log.append((j, f'take profit {R}R', to_m(px), frac))
            if rem <= 1e-9: why = 'target'; xbar = j; break
        hic = max(hic, c)
        if hit and j < last:
            if runner.startswith('chand'): stop = max(stop, hic - float(runner[5:]) * m.atr(b, j))
            elif runner == 'ema9' and c < e9[j]:
                gross += rem * (b[j + 1][0] - entry); log.append((j + 1, 'runner 9-EMA exit', to_m(b[j + 1][0]), rem)); rem = 0; why = 'runner_ema'; xbar = j + 1; break
    if rem > 0: gross += rem * (b[last][3] - entry); log.append((last, 'time exit', to_m(b[last][3]), rem))
    lev = TB.ROWS[p][2]
    out = dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, pct=lev * gross / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100, hit=hit)
    if detail: out.update(entry=e_real, stop=stop_real, target=to_m(T), log=log)
    return out


def evaluate(D, days, h, **kw):
    T = [t for d in days for p in TB.ROWS for t in [run_trade(D, d, p, **kw)] if t]
    a = TB.account(D, days, T); H1 = set(days[:h])
    d1 = st.mean(TB.account(D, days[:h], [t for t in T if t['day'] in H1])['daily'].values())
    d2 = st.mean(TB.account(D, days[h:], [t for t in T if t['day'] not in H1])['daily'].values())
    return T, a, d1, d2


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2
    tm = lambda k: f"{(570 + 5 * k) // 60}:{(570 + 5 * k) % 60:02d}"
    print(f"Failed-retest fade exit study, {days[0]}..{days[-1]} ({len(days)} days), $2,000, cash-capped, one position at a time.\n")
    T, a, d1, d2 = evaluate(D, days, h)
    tk = a['taken']
    print("PROPOSED: stop beyond the failed breakout's extreme; half at 2R (OCO); runner breakeven -> 2-ATR chandelier; sell all at 12:00")
    print(f"   trades {len(tk)}, win {100*sum(x['usd']>0 for x in tk)/len(tk):.0f}%, {st.mean(a['daily'].values()):+.3f}%/day, return {a['ret']:+.1f}%, max DD {a['mdd']:.1f}%, H1 {d1:+.3f} H2 {d2:+.3f}")
    print(f"   exits: {dict(collections.Counter(x['why'] for x in tk))};  reached 2R: {sum(x['hit'] for x in tk)}")
    print(f"   avg winner {st.mean(x['acct'] for x in tk if x['usd']>0):+.2f}% of account, avg loser {st.mean(x['acct'] for x in tk if x['usd']<=0):+.2f}%; "
          f"latest exit {tm(max(x['xbar'] for x in tk))}")
    mo = collections.defaultdict(float)
    for x in tk: mo[x['day'][:7]] += x['usd']
    print('   by month: ' + ', '.join(f"{k} {v:+.0f}$" for k, v in sorted(mo.items())))
    print("\n== Grid around it (target R x fraction sold x runner x sell-by) ==")
    rows = []
    for R, frac, runner, last in itertools.product((1.5, 2.0, 2.5, 3.0), (0.33, 0.5, 0.67, 1.0), ('be', 'chand1.5', 'chand2', 'chand3', 'ema9'), (23, 29, 35, 47, 77)):
        if frac == 1.0 and runner != 'be': continue
        T, a, d1, d2 = evaluate(D, days, h, R=R, frac=frac, runner=runner, last=last)
        rows.append(((R, frac, runner, last), st.mean(a['daily'].values()), a['ret'], a['mdd'], d1, d2))
    lab = lambda c: f"{'all' if c[1] == 1 else f'{int(round(c[1]*100))}%'} at {c[0]}R, runner {c[2]:<8} sell-by {TN[c[3]]}"
    print(f"{'exit':<46}{'%/day':>8}{'ret%':>8}{'DD':>6}{'H1':>8}{'H2':>8}")
    for c, dd, ret, mdd, a1, a2 in sorted(rows, key=lambda r: -r[1])[:20]:
        print(f"{lab(c):<46}{dd:>+8.3f}{ret:>+8.1f}{mdd:>6.1f}{a1:>+8.3f}{a2:>+8.3f}{'   <- proposed' if c == (2.0, 0.5, 'chand2', 29) else ''}")
    prop = [r for r in rows if r[0] == (2.0, 0.5, 'chand2', 29)][0]
    rank = sorted(rows, key=lambda r: -r[1]).index(prop) + 1
    print(f"   ... {len(rows)} combinations; proposed ranks #{rank}; positive in both halves: {sum(r[4] > 0 and r[5] > 0 for r in rows)} of {len(rows)}")
    print("\n   Averages by each choice (all other settings mixed), %/day overall / H2:")
    for i, name in enumerate(('target R', 'fraction sold', 'runner', 'sell-by')):
        g = collections.defaultdict(list)
        for r in rows: g[r[0][i]].append(r)
        print(f"     {name:<14}" + '  '.join(f"{(TN[k] if i == 3 else k)}: {st.mean(x[1] for x in v):+.3f}/{st.mean(x[5] for x in v):+.3f}" for k, v in g.items()))
    best = max(rows, key=lambda r: r[4])
    print(f"\n   WALK-FORWARD: best on H1 = {lab(best[0])} (H1 {best[4]:+.3f}) -> H2 {best[5]:+.3f};  proposed H2 {prop[5]:+.3f}")
    print("\n== Example trades under the proposed exit ==")
    shown = 0
    for d in days:
        for p in TB.ROWS:
            t = run_trade(D, d, p, detail=True)
            if t and t['hit'] and shown < 3 and len(t['log']) >= 2:
                leg = TB.ROWS[p][0] if t['side'] > 0 else TB.ROWS[p][1]
                print(f"   {d} {p} fade -> buy {leg} at {tm(t['k'])} (proxy {t['entry']:.2f}); stop {t['stop']:.2f}; 2R target {t['target']:.2f}")
                for j, what, px, f in t['log']:
                    print(f"       {tm(j)} {what:<14} {int(round(f*100))}% at proxy {px:.2f}")
                print(f"       trade result on {leg}: {t['pct']:+.2f}%")
                shown += 1
    for d in reversed(days):
        for p in TB.ROWS:
            t = run_trade(D, d, p, detail=True)
            if t and not t['hit'] and t['why'] == 'stop' and shown < 4:
                leg = TB.ROWS[p][0] if t['side'] > 0 else TB.ROWS[p][1]
                print(f"   {d} {p} fade -> buy {leg} at {tm(t['k'])} (proxy {t['entry']:.2f}); stop {t['stop']:.2f}  -> stopped at {tm(t['xbar'])}, {t['pct']:+.2f}%  (a loser, for balance)")
                shown += 1


if __name__ == '__main__':
    main()
