"""Second round of outside suggestions: (1) passive pullback entry (limit below the trigger close, 'bid+0.01'),
(2) spread-to-ATR blocker (spread > 0.15 x ATR14) under ASSUMED spreads - no real spread history exists."""
import re, inspect, statistics as st
import suggestion_tests as T
from suggestion_tests import *

def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
    march = [d for d in days if d < '2026-04-07']
    f0, p0 = FS.cands(D, days); base = stats(D, days, f0 + p0)
    print("ROUND 2 vs backtest (2026-03-03..10-14, 157 days)\n"); print(HDR); print(row('BASELINE (live rules)', base)); print()
    PBF.TARGET_MODE = 'floor'
    src = inspect.getsource(PBF.scan)
    print("1. PASSIVE PULLBACK ENTRY: limit = trigger close x (1 - offset); fills only if next bar trades down to it")
    for off in (0.0, 0.05, 0.10, 0.20, 0.30):
        ns = dict(PBF.__dict__); exec(src.replace("lim = b[j][3]", f"lim = b[j][3]*(1-{off}/100)"), ns); PBF.scan = ns['scan']
        S = PBF.setups(D, days, FS.PB, True)
        cs = [pb_cands(x) for x in (pb_manage(s, None, 0) for s in S) if x]
        r = stats(D, days, f0 + cs); pb = stats(D, days, f0 + cs, 'PB')
        print(row(f"  offset {off:.2f}% below close", r, base) + f"   | pullback trades {pb['n']}")
    exec(src, PBF.__dict__)  # restore
    print()
    print("2. SPREAD/ATR BLOCKER: skip pullback if assumed spread > 0.15 x ATR14 at signal bar (spread assumed constant % of price)")
    S = PBF.setups(D, days, FS.PB, True)
    for sp in (0.05, 0.10, 0.20, 0.30, 0.50):
        keep = []; blocked = 0
        for s in S:
            a = ORIG_ATR(s['b'], s['sig'])
            if sp / 100 * s['entry'] > 0.15 * a: blocked += 1; continue
            keep.append(s)
        cs = [pb_cands(x) for x in (pb_manage(s, None, 0) for s in keep) if x]
        r = stats(D, days, f0 + cs); pb = stats(D, days, f0 + cs, 'PB')
        print(row(f"  assumed spread {sp:.2f}%: blocked {blocked}/{len(S)} setups", r, base) + f"   | pullback trades {pb['n']}")
    atrs = [ORIG_ATR(s['b'], s['sig']) / s['entry'] * 100 for s in S]
    print(f"   5-min ATR14 as % of price at pullback signals: median {st.median(atrs):.2f}%, 10th pct {sorted(atrs)[len(atrs)//10]:.2f}% -> 0.15x = {0.15*st.median(atrs):.3f}% median allowed spread")
main()
