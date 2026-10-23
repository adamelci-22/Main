import sys, statistics as st
sys.path.insert(0, 'tools/live')
import paper as P, datetime
raw = P.load(sys.argv[1:]); day = max(d for s in raw.values() for d in s); prevday = max(d for d in {d for s in raw.values() for d in s} if d < day)
for leg in P.PB_LIST:
    last = max(m for s_ in raw.values() if day in s_ for m in s_[day])           # newest bar start (minutes) across all symbols
    K = (last - 570) // 5 + 1
    t = P.grid(raw[leg][day], K); p = P.grid(raw[leg][prevday], 78)
    ser = [x[3] for x in p] + [x[3] for x in t]
    e9 = P.ema(ser, 9)[len(p):]; e20 = P.ema(ser, 20)[len(p):]
    bh = max(x[1] for x in t[:3])
    bo = [i for i in range(3, K) if t[i][3] > bh and t[i][4] > 1.5 * st.mean(t[q][4] for q in range(max(0, i-6), i))]
    print(f"{leg:5} close {t[-1][3]:.2f} {(t[-1][3]/bh-1)*100:+.1f}% vs range high {bh:.2f} | vol breakout: {'yes at '+P.k2t(bo[0]) if bo else 'no'} | trend ok: {e9[-1]>e20[-1] and t[-1][3]>e9[-1]}")
