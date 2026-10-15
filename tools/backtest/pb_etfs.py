#!/usr/bin/env python3
"""Which leveraged ETFs suit the pullback buy? Same setup/exit on each ticker's own chart.
    python3 tools/backtest/pb_etfs.py > tools/backtest/results_pb_etfs.txt
Setup: pullback.scan rules (room >= 0.75%, entries to 13:00, limit entry). Exit: 60% at the morning high (OCO), rest trails on a
20-EMA close, sell what's left by 13:30. Costs 0.01% in / 0.03% out (optimistic for thin tickers - see bar volume).
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pullback as P, pb_v2 as V
from lab import get_data

GROUPS = {
    'current list': ['SOXL', 'SOXS', 'TECL', 'TECS', 'TQQQ', 'SQQQ', 'TNA', 'TZA', 'BTCL', 'BTCZ'],
    'single stocks': ['NVDL', 'NVDQ', 'TSLL', 'TSLQ', 'MSTU', 'MSTZ', 'CONL', 'AMDL'],
    'crypto': ['ETHU', 'ETHD', 'BITX', 'SBIT'],
    'commodities/vol': ['BOIL', 'KOLD', 'UVXY', 'SVIX'],
    'sectors/countries': ['FNGU', 'FNGD', 'USD', 'DPST', 'YINN', 'YANG', 'LABU', 'LABD', 'NUGT', 'DUST', 'KORU', 'GUSH', 'DRIP', 'ERX', 'ERY', 'FAS', 'FAZ'],
}


def setups_for(D, days, leg):
    out = []
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]
        if d not in D.bars.get(leg, {}) or pd_ not in D.bars.get(leg, {}): continue
        b = D.bars[leg][d]; pb = D.bars[leg][pd_]
        ser = [x[3] for x in pb] + [x[3] for x in b]; e9 = m.ema(ser, 9)[78:]; e20 = m.ema(ser, 20)[78:]
        s = V.scan(b, e9, e20, lambda j: True)
        if s: s.update(day=d, inst=leg, b=b, e20=e20); out.append(s)
    return out


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1 = set(days[:h])
    m.rvol = lambda *a: 0.0
    print(f"Pullback buy per ticker, {days[0]}..{days[-1]} ({len(days)} days). Exit: 60% at morning high, rest 20-EMA trail, out by 13:30.\n")
    print(f"{'group':<18}{'ticker':<7}{'5m range':>9}{'$ per 5m bar':>14}{'setups':>7}{'win%':>6}{'avg%':>8}{'t':>6}{'H1 avg':>8}{'H2 avg':>8}{'both+':>7}{'alone %/day':>12}")
    res = {}
    for g, tick in GROUPS.items():
        for leg in tick:
            if leg not in D.bars: print(f"{g:<18}{leg:<7} no data"); continue
            dd = [d for d in days if d in D.bars[leg]]
            rng = st.median((x[1] - x[2]) / x[3] * 100 for d in dd for x in D.bars[leg][d][6:47] if x[3])
            dv = st.median(x[4] * x[3] for d in dd for x in D.bars[leg][d][6:47])
            S = setups_for(D, days, leg)
            sig = [t for s in S for t in [V.manage(s, 'hod', 0.6, 'ema20', 47)] if t]
            if not sig:
                print(f"{g:<18}{leg:<7}{rng:>8.2f}%{dv:>14,.0f}{0:>7}"); continue
            a = [x['pct'] for x in sig]; mu = st.mean(a); sd = st.pstdev(a)
            t = mu / (sd / math.sqrt(len(a))) if sd and len(a) > 2 else 0
            a1 = [x['pct'] for x in sig if x['day'] in H1]; a2 = [x['pct'] for x in sig if x['day'] not in H1]
            m1 = st.mean(a1) if a1 else float('nan'); m2 = st.mean(a2) if a2 else float('nan')
            m.LEGS = {leg: (leg, 1)}
            acc = P.account(sig, D, days); ad = st.mean(acc['daily'].values())
            both = 'yes' if a1 and a2 and m1 > 0 and m2 > 0 else ''
            res[leg] = dict(g=g, n=len(sig), mu=mu, t=t, m1=m1, m2=m2, both=both, ad=ad, dv=dv, rng=rng, sig=sig)
            print(f"{g:<18}{leg:<7}{rng:>8.2f}%{dv:>14,.0f}{len(sig):>7}{100*sum(x>0 for x in a)/len(a):>6.0f}{mu:>+8.3f}{t:>6.1f}{m1:>+8.3f}{m2:>+8.3f}{both:>7}{ad:>+12.3f}")
    print("\nTickers positive in BOTH halves with >= 8 setups and median $ per 5-min bar >= $250k (liquid enough to trade):")
    good = [k for k, v in res.items() if v['both'] and v['n'] >= 8 and v['dv'] >= 250_000]
    for k in sorted(good, key=lambda k: -res[k]['mu']):
        v = res[k]; print(f"   {k:<6} ({v['g']}) setups {v['n']}, avg {v['mu']:+.3f}%/trade (t {v['t']:+.1f}), H1 {v['m1']:+.3f} H2 {v['m2']:+.3f}, 5-min range {v['rng']:.2f}%")
    # does 5-min range predict pullback quality?
    xs = [(v['rng'], v['mu']) for v in res.values() if v['n'] >= 8]
    mx = st.mean(x for x, _ in xs); my = st.mean(y for _, y in xs)
    cor = sum((x - mx) * (y - my) for x, y in xs) / math.sqrt(sum((x - mx) ** 2 for x, _ in xs) * sum((y - my) ** 2 for _, y in xs))
    print(f"\nCorrelation across tickers between typical 5-min range and pullback avg/trade: {cor:+.2f}")


if __name__ == '__main__':
    main()
