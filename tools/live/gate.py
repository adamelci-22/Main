#!/usr/bin/env python3
"""C1 gate snapshot for the eight proxies (RULEBOOK C1/C4, v3.121).

    python3 tools/live/gate.py HISTORICALS.json [K]

HISTORICALS.json = saved get_equity_historicals output (5minute, regular) covering at least
the last day before today plus today. History before that comes from tools/replay/data.
K = number of COMPLETED 5-min bars today (default: all bars in the file whose
volume is final = every bar but the last, which is assumed in progress).
Prints RVOL, opening range, closes outside it, expansion and selection_score.
"""
import gzip, json, os, statistics as st, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = ['QQQ', 'SPY', 'SOXX', 'IWM', 'XLF', 'XLE', 'TLT', 'XBI']


def load(path):
    bars = defaultdict(lambda: defaultdict(dict))            # sym -> day -> ts -> (o,h,l,c,v)
    old = json.load(gzip.open(os.path.join(HERE, '..', 'replay', 'data', 'proxies_5m_v2.json.gz')))
    for s in SYMS:
        for t, o, h, l, c, v, _ in old[s]:
            bars[s][t[:10]][t] = (o, h, l, c, v)
    for r in json.load(open(path))['data']['results']:
        for b in r['bars']:
            bars[r['symbol']][b['begins_at'][:10]][b['begins_at']] = tuple(
                float(b[k]) if k != 'volume' else b[k]
                for k in ('open_price', 'high_price', 'low_price', 'close_price', 'volume'))
    return {s: {d: [v for _, v in sorted(ts.items())] for d, ts in days.items()} for s, days in bars.items()}


def main():
    B = load(sys.argv[1])
    today = max(B['QQQ'])
    k = int(sys.argv[2]) if len(sys.argv) > 2 else len(B['QQQ'][today]) - 1
    rows = []
    for s in SYMS:
        days = sorted(d for d in B[s] if d < today and len(B[s][d]) >= 78)
        prior = days[-20:]
        base = st.mean(sum(b[4] for b in B[s][d][:k]) for d in prior)
        t = B[s][today][:k]
        rvol = sum(b[4] for b in t) / base
        orb = t[:6]
        orh, orl = max(b[1] for b in orb), min(b[2] for b in orb)
        post = [b[3] for b in t[6:]]
        run = 0                                              # consecutive closes outside, latest run
        side = 0
        for c in post:
            sd = 1 if c > orh else -1 if c < orl else 0
            run = run + 1 if sd and sd == side else (1 if sd else 0)
            side = sd
        # ATR14 from daily H/L/C built from 5-min bars
        dd = [(max(b[1] for b in B[s][d]), min(b[2] for b in B[s][d]), B[s][d][-1][3]) for d in days]
        tr = [max(h - l, abs(h - pc), abs(l - pc)) for (h, l, _), (_, _, pc) in zip(dd[1:], dd)]
        atr = st.mean(tr[-14:])
        exp = (max(b[1] for b in t) - min(b[2] for b in t)) / atr
        rows.append((s, rvol, orh, orl, t[-1][3], run * side, exp, (1 - exp) * rvol))
    print(f"{today}, {k} completed 5-min bars")
    print(f"{'sym':5}{'RVOL':>6}{'ORH':>9}{'ORL':>9}{'last':>9}{'closes out':>11}{'expan':>7}{'score':>7}")
    for s, rv, h, l, c, r, e, sc in sorted(rows, key=lambda x: -x[1]):
        print(f"{s:5}{rv:6.2f}{h:9.2f}{l:9.2f}{c:9.2f}{r:+11d}{e:7.2f}{sc:+7.2f}")


if __name__ == '__main__':
    main()
