#!/usr/bin/env python3
"""Backtest of the full mixed system as it stands for paper trading (rulebook v3.132, C13).
    python3 tools/backtest/final_system.py > tools/backtest/results/final_system.txt
FADE: QQQ SOXX IWM XLK XBI XLF (v5.2.13; AMD out; failed-retest fade; 1/3 at 2R, 2-ATR chandelier, out 13:30).
PULLBACK: SOXS LABD TECS UVXY (v5.2.14; NVD out; PULLBACK_SPEC.md; 100% at morning high; out 13:30).
$2,000, 3% risk capped at cash, one position at a time, max 3 entries/day, earliest trigger first, ties by proxy RVOL.
Identical to tools/live/paper.py (verified). Period 2026-03-03..10-14; 03-03..04-06 was never used to choose any rule or list.
"""
import math, os, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
from lab import get_data

FADE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
PB = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVDQ', 'NVD', 'MSFU', 'SSG']     # v5.2.21
PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'NVD': 'NVDA', 'LABD': 'LABD', 'UVXY': 'UVXY', 'NVDQ': 'NVDQ', 'MSFU': 'MSFU', 'SSG': 'SSG'})


def cands(D, days):
    f = [c for p in FADE for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')]
    s = PBF.run(D, days, PB, oco_gap=True)
    p = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    return f, p


def summary(title, D, days, cs):
    a = MXD.account(D, days, cs); tk = a['taken']; dl = a['daily']; h = len(days) // 2
    w = [x for x in tk if x['usd'] > 0]; l = [x for x in tk if x['usd'] <= 0]
    sd = st.pstdev(dl.values())
    print(f"{title}: {days[0]}..{days[-1]} ({len(days)} trading days)")
    print(f"   trades {len(tk)} ({len(tk)/len(days)*5:.1f}/week), win {100*len(w)/len(tk):.0f}%, avg win {st.mean(x['pct'] for x in w):+.2f}% / avg loss {st.mean(x['pct'] for x in l):+.2f}% (on the ticker)")
    print(f"   {st.mean(dl.values()):+.3f}%/day, return {a['ret']:+.1f}% ($2,000 -> ${2000*(1+a['ret']/100):,.0f}), max drawdown {a['mdd']:.1f}%, "
          f"Sharpe~{st.mean(dl.values())/sd*math.sqrt(252) if sd else 0:.1f}, halves {st.mean(dl[d] for d in days[:h]):+.3f} / {st.mean(dl[d] for d in days[h:]):+.3f}")
    return a


def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = D.days[1:]
    f, p = cands(D, days)
    print("FULL MIXED SYSTEM (paper setup v3.132)\n")
    a = summary('Combined', D, days, f + p)
    summary('Fade alone', D, days, f)
    summary('Pullback alone', D, days, p)
    mar = [d for d in days if d < '2026-04-07']
    fm, pm = cands(D, mar)
    summary('Untouched window (never used for tuning)', D, mar, fm + pm)
    summary('Tuning window', D, [d for d in days if d >= '2026-04-07'], [c for c in f + p if c['day'] >= '2026-04-07'])
    tk = a['taken']; dl = a['daily']
    print("\nMonth by month (combined):")
    mo = collections.defaultdict(lambda: [0, 0.0, 0]); eq = 2000.0
    for x in tk: mo[x['day'][:7]][0] += 1; mo[x['day'][:7]][1] += x['usd']; mo[x['day'][:7]][2] += x['usd'] > 0
    for k in sorted(mo):
        n, u, wn = mo[k]; print(f"   {k}: {n:2d} trades, {wn:2d} won, {u:+7.0f}$ ({u/eq*100:+5.1f}%), equity end ${eq+u:,.0f}"); eq += u
    print("\nBy system and ticker:")
    g = collections.defaultdict(list)
    for x in tk: g[(x['sys'], x['proxy'] if x['sys'] == 'FADE' else x['name'])].append(x)
    for (s, n), v in sorted(g.items(), key=lambda kv: -sum(x['usd'] for x in kv[1])):
        print(f"   {s:<4} {n:<5} {len(v):2d} trades, win {100*sum(x['usd']>0 for x in v)/len(v):3.0f}%, avg {st.mean(x['pct'] for x in v):+.2f}%, total {sum(x['usd'] for x in v):+6.0f}$")
    fd = [x for x in tk if x['sys'] == 'FADE']
    print(f"   fade by side: bull leg {sum(1 for x in fd if x['name'].endswith('+'))} trades {sum(x['usd'] for x in fd if x['name'].endswith('+')):+.0f}$, "
          f"inverse leg {sum(1 for x in fd if x['name'].endswith('-'))} trades {sum(x['usd'] for x in fd if x['name'].endswith('-')):+.0f}$")
    dd = list(dl.values())
    seq = ''.join('L' if x['usd'] <= 0 else 'W' for x in tk)
    print(f"\nDays: traded {sum(1 for v in dd if v != 0)} of {len(dd)}; winning {sum(1 for v in dd if v > 0)}, losing {sum(1 for v in dd if v < 0)}; "
          f"best {max(dd):+.2f}%, worst {min(dd):+.2f}%; longest losing streak {max(len(s) for s in seq.split('W'))} trades")
    wk = collections.defaultdict(float)
    import datetime as dt
    for d, v in dl.items(): wk[dt.date.fromisoformat(d).isocalendar()[1]] += v
    print(f"Weeks: {len(wk)}, positive {sum(1 for v in wk.values() if v > 0)}, negative {sum(1 for v in wk.values() if v < 0)}, worst week {min(wk.values()):+.2f}%, best week {max(wk.values()):+.2f}%")
    top = sorted(tk, key=lambda x: -x['usd']); tot = sum(x['usd'] for x in tk)
    print(f"Profit concentration: top 5 trades {sum(x['usd'] for x in top[:5]):+.0f}$, top 10 {sum(x['usd'] for x in top[:10]):+.0f}$ of {tot:+.0f}$ total")
    print(f"Without the top 5 trades the return would be about {(tot - sum(x['usd'] for x in top[:5]))/2000*100:+.0f}% (non-compounded)")
    ent = collections.Counter(f"{(570+5*x['k'])//60}:{'00' if (570+5*x['k'])%60 < 30 else '30'}" for x in tk)
    print("Entries by half hour: " + ', '.join(f"{k} {v}" for k, v in sorted(ent.items(), key=lambda kv: tuple(map(int, kv[0].split(':'))))))


if __name__ == '__main__':
    main()
