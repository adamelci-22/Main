#!/usr/bin/env python3
"""Does the way the lists were built work going forward? Walk-forward re-selection on Massive bars.
    /usr/bin/python3 -I tools/backtest/massive_walkforward.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_walkforward.txt
At the start of each quarter, look only at the previous 252 trading days. Keep the tickers whose trailing average result is above zero (and at least MIN trades). Trade only those during the quarter. No look-ahead.
FADE: the six live proxies, real-leg trades. PULLBACK: the four live funds plus fourteen others (own chart, live rules).
Reports the average result per trade for: all tickers, the walk-forward pick, and the pick-everything-that-won-last-year baseline by year.
"""
import collections, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import massive_realleg as RL
import pb_final as PBF, pb_inverse as PI
from lab import get_data
LR = RL.LR
FUNDS = ['SOXS', 'LABD', 'TECS', 'UVXY', 'SPXU', 'SDS', 'QID', 'SRTY', 'SDOW', 'ERY', 'DRIP', 'DUST', 'TMV', 'UVIX', 'SVIX', 'TZA', 'SQQQ', 'FAZ']


def walk(trades, key, days, minn, top=None):
    qs = sorted({d[:4] + 'Q' + str((int(d[5:7]) - 1) // 3 + 1) for d in days})
    firstday = {q: min(d for d in days if d[:4] + 'Q' + str((int(d[5:7]) - 1) // 3 + 1) == q) for q in qs}
    out = []
    for q in qs:
        i = days.index(firstday[q])
        if i < 252: continue
        lo, hi = days[i - 252], days[i - 1]
        qd = {d for d in days if d[:4] + 'Q' + str((int(d[5:7]) - 1) // 3 + 1) == q}
        hist = collections.defaultdict(list)
        for t in trades:
            if lo <= t['day'] <= hi: hist[t[key]].append(t['pct'])
        good = {k for k, v in hist.items() if len(v) >= minn and st.mean(v) > 0}
        if top: good = set(sorted(good, key=lambda k: -st.mean(hist[k]))[:top])
        out += [(t['day'], t['pct'], t[key] in good) for t in trades if t['day'] in qd]
    return out


def show(title, out):
    print(f"== {title} ==")
    print(f"{'year':<6}{'all trades':>26}{'walk-forward pick':>30}")
    for y in sorted({d[:4] for d, _, _ in out}):
        a = [p for d, p, g in out if d[:4] == y]; b = [p for d, p, g in out if d[:4] == y and g]
        f = lambda v: f"n={len(v):>4} avg {st.mean(v):+.3f}% win {100*sum(x > 0 for x in v)/len(v):>3.0f}%" if v else 'no trades'
        print(f"{y:<6}{f(a):>26}{f(b):>30}")
    a = [p for _, p, _ in out]; b = [p for _, p, g in out if g]
    print(f"{'ALL':<6}{('n=%d avg %+.3f%%' % (len(a), st.mean(a))):>26}{('n=%d avg %+.3f%%' % (len(b), st.mean(b)) if b else 'none'):>30}\n")


def main():
    D = get_data(); days = D.days[1:]; rows = {p: RL.FA.ROWS[p] for p in LR.BT.PROXIES}
    fade = [t for p in LR.BT.PROXIES for d in days for t in [RL.real_trade(D, d, p, rows[p])] if t]
    show('FADE: re-pick proxies each quarter from the trailing 252 days (keep avg > 0, at least 12 trades)', walk(fade, 'proxy', days, 12))
    show('FADE: keep only the best 2 proxies of the trailing 252 days', walk(fade, 'proxy', days, 12, top=2))
    for f in FUNDS: PI.PROXY.setdefault(f, f)
    pb = [dict(x, name=x['inst']) for x in PBF.run(D, days, [f for f in FUNDS if f in D.bars], oco_gap=True)]
    show('PULLBACK: re-pick funds each quarter from the trailing 252 days (keep avg > 0, at least 8 trades), 18 candidate funds', walk(pb, 'inst', days, 8))
    show('PULLBACK: the four live funds only (no re-picking)', [(t['day'], t['pct'], True) for t in pb if t['inst'] in ('SOXS', 'LABD', 'TECS', 'UVXY') and t['day'] >= days[252]])


if __name__ == '__main__':
    main()
