#!/usr/bin/env python3
"""LATE continuation: (A) alone as its own account, (B) combined with FADE + PULLBACK, (C) parameter sensitivity, (D) cost stress.
    python3 tools/backtest/late_continuation_study.py > tools/backtest/results/late_continuation_study.txt
LATE rule (trade WITH the first break of the 9:30-10:00 box): the first 5-min close outside the box comes by `brk` (default 10:15); the price then
stays outside the box edge for `hold` bars (never trades back to the edge), and a bar between `start` (11:00) and 12:30 closes above the prior
`lb` bars' high (direction space) -> enter next open. Stop: box midpoint (default) | breakout-consolidation low | opposite box edge.
All out at N x R (default 1.0R), stop, or 13:30. Entries by 12:55. Cost 0.06%. Six FADE proxies/legs. One position at a time. $2,000, 3% risk.
"""
import collections, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, mixed as MXD, twobar as TB, fade_addone as FA, final_system as FS
from third_system_continuation import direction_space, vwap_ok, LAST, KMAX
from lab import get_data

PROX = ('QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'AMD')

def late_signal(raw, brk=9, hold=6, lb=6, start=18, end=36):
    H = max(x[1] for x in raw[:6]); L = min(x[2] for x in raw[:6])
    for j in range(6, brk + 1):
        c = raw[j][3]; side = 1 if c > H else -1 if c < L else 0
        if not side: continue
        b, to_m = direction_space(raw, side)
        Hd = max(x[1] for x in b[:6]); Ld = min(x[2] for x in b[:6]); mid = (Hd + Ld) / 2
        for i in range(j + hold, end + 1):
            if i < start: continue
            if min(b[q][2] for q in range(j + 1, i + 1)) <= Hd: return None
            if b[i][3] > max(b[q][1] for q in range(i - lb, i)):
                k = i + 1
                if k > KMAX: return None
                return k, side, dict(mid=mid, box=Ld, brk=min(b[q][2] for q in range(i - lb, i))), raw[k][0]
        return None
    return None

def late_trade(D, d, p, row, stop='mid', N=1.0, **kw):
    raw = D.bars[p][d]
    if len(raw) < 60: return None
    s = late_signal(raw, **kw)
    if not s: return None
    k, side, stops, e_real = s
    b, to_m = direction_space(raw, side); entry = to_m(e_real); st_ = stops[stop]
    if entry <= st_: return None
    r = entry - st_
    pnl, xbar, why = TB.manage(b, k, entry, st_, entry + N * r, 1.0, False, LAST, True, True)
    bull, lb_, bear, lbe = row; lev = lb_ if side > 0 else lbe
    return dict(day=d, proxy=p, side=side, k=k, xbar=xbar, why=why, pct=lev * pnl / e_real * 100 - TB.LEGCOST, leg_risk=lev * r / e_real * 100)

def late_set(D, days, **kw):
    return [t for p in PROX if p in D.bars for d in days if d in D.bars[p] for t in [late_trade(D, d, p, FA.ROWS[p], **kw)] if t]

def summ(a, days, h, mar):
    dl = a['daily']; tk = a['taken']; w = [x for x in tk if x['usd'] > 0]; l = [x for x in tk if x['usd'] <= 0]
    v = lambda ds: st.mean(dl[d] for d in ds) if ds else 0.0
    return dict(n=len(tk), win=100 * len(w) / max(1, len(tk)), day=v(days), h1=v(days[:h]), h2=v(days[h:]), mar=v([d for d in days if d in mar]),
                ret=a['ret'], dd=a['mdd'], aw=st.mean(x['pct'] for x in w) if w else 0, al=st.mean(x['pct'] for x in l) if l else 0)

def fmt(s): return (f"{s['n']:4d} trades win {s['win']:3.0f}% {s['day']:+.3f}%/day (H1 {s['h1']:+.3f} H2 {s['h2']:+.3f} Mar {s['mar']:+.3f}) ret {s['ret']:+7.1f}% DD {s['dd']:4.1f}%")

def tstat(T):
    pc = [t['pct'] for t in T]
    return st.mean(pc) / (st.pstdev(pc) / math.sqrt(len(pc))) if len(pc) > 2 and st.pstdev(pc) else 0.0

def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]; h = len(days) // 2; mar = {d for d in days if d < '2026-04-07'}
    f, p = FS.cands(D, days); base = MXD.account(D, days, f + p); sb = summ(base, days, h, mar)
    T = late_set(D, days); cont = MXD.norm_px(T, 'LATE')
    print(f"LATE CONTINUATION STUDY  {days[0]}..{days[-1]} ({len(days)} days). Default LATE = break by 10:15, held 6 bars, new 6-bar high 11:00-12:30, stop mid, all out 1.0R, out 13:30.\n")
    print(f"(0) BASE FADE+PULLBACK        {fmt(sb)}")
    # ------------------------------------------------ A: LATE alone
    print("\n(A) LATE ALONE as its own account (one position at a time):")
    for stop in ('mid', 'brk', 'box'):
        for N in (0.75, 1.0, 1.5):
            Ts = late_set(D, days, stop=stop, N=N); a = MXD.account(D, days, MXD.norm_px(Ts, 'LATE')); s = summ(a, days, h, mar)
            print(f"   stop {stop:<4} TP {N:<4}R  signals {len(Ts):3d} (avg leg {st.mean(t['pct'] for t in Ts):+.3f}%, t {tstat(Ts):+.1f})  account: {fmt(s)}")
    a_alone = MXD.account(D, days, cont); sa = summ(a_alone, days, h, mar)
    print(f"\n   HEADLINE LATE alone: {fmt(sa)}   avg win {sa['aw']:+.2f}% / avg loss {sa['al']:+.2f}% on the leg")
    by = collections.defaultdict(lambda: [0, 0.0])
    for x in a_alone['taken']: by[x['proxy']][0] += 1; by[x['proxy']][1] += x['usd']
    print("   by proxy: " + ", ".join(f"{k} {v[0]} trades {v[1]:+.0f}$" for k, v in sorted(by.items(), key=lambda kv: -kv[1][1])))
    mo = collections.defaultdict(lambda: [0, 0.0])
    for x in a_alone['taken']: mo[x['day'][:7]][0] += 1; mo[x['day'][:7]][1] += x['usd']
    print("   by month: " + ", ".join(f"{k[5:]} {v[0]}t {v[1]:+.0f}$" for k, v in sorted(mo.items())))
    # ------------------------------------------------ B: combined
    print("\n(B) ALL THREE: FADE + PULLBACK + LATE (earliest trigger first, one position at a time):")
    a3 = MXD.account(D, days, f + p + cont); s3 = summ(a3, days, h, mar)
    print(f"   BASE      {fmt(sb)}\n   ALL THREE {fmt(s3)}   delta {s3['day'] - sb['day']:+.3f}%/day")
    tk = a3['taken']; print("   trades by system: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(x['sys'] for x in tk).items()) +
                           " | $ by system: " + ", ".join(f"{k} {sum(x['usd'] for x in tk if x['sys'] == k):+.0f}" for k in ('FADE', 'PB', 'LATE')))
    bt = {(x['day'], x['sys'], x['name']) for x in base['taken']}; at = {(x['day'], x['sys'], x['name']) for x in tk}
    print(f"   base trades no longer taken (displaced by LATE): {len(bt - at)}; new LATE trades: {len(at - bt)}")
    dd = [a3['daily'][d] - base['daily'][d] for d in days]; dm, ds = st.mean(dd), st.pstdev(dd)
    print(f"   paired daily difference: mean {dm:+.4f}%  t {dm / (ds / math.sqrt(len(dd))) if ds else 0:+.2f}  (|t|<2 = indistinguishable from noise)  days changed: {sum(1 for x in dd if abs(x) > 1e-9)}")
    mo3 = collections.defaultdict(float); mob = collections.defaultdict(float); e3 = eb = 2000.0
    for d in days:
        pass
    q = lambda a: collections.OrderedDict()
    for lab, a in (('BASE', base), ('ALL3', a3)):
        eq = 2000.0; out = collections.OrderedDict(); byq = collections.defaultdict(float)
        for x in a['taken']: byq[x['day'][:7]] += x['usd']
        for k in sorted(byq): out[k] = (eq + byq[k]) / eq * 100 - 100; eq += byq[k]
        print(f"   monthly {lab}: " + " ".join(f"{k[5:]} {v:+.1f}%" for k, v in out.items()))
    # ------------------------------------------------ C: sensitivity (one parameter at a time)
    print(f"\n(C) SENSITIVITY, one parameter at a time around the default (standalone signals + combined %/day vs base {sb['day']:.3f}):")
    def row(label, **kw):
        Ts = late_set(D, days, **kw)
        if len(Ts) < 10: print(f"   {label:<34} too few ({len(Ts)})"); return
        cm = summ(MXD.account(D, days, f + p + MXD.norm_px(Ts, 'LATE')), days, h, mar)
        h1 = [t['pct'] for t in Ts if t['day'] in set(days[:h])]; h2 = [t['pct'] for t in Ts if t['day'] in set(days[h:])]
        print(f"   {label:<34} n {len(Ts):3d} avg {st.mean(t['pct'] for t in Ts):+.3f}% t {tstat(Ts):+.1f} H1 {st.mean(h1) if h1 else 0:+.3f} H2 {st.mean(h2) if h2 else 0:+.3f} | combined {cm['day']:+.3f} ({cm['day'] - sb['day']:+.3f}) H1 {cm['h1']:+.3f} H2 {cm['h2']:+.3f} Mar {cm['mar']:+.3f}")
    row('default')
    for v in (3, 4, 9, 12): row(f'hold {v} bars', hold=v)
    for v in (3, 4, 10, 12): row(f'lookback {v} bars', lb=v)
    for v, lab in ((12, '10:30'), (24, '11:30')): row(f'window starts {lab}', start=v)
    row('window ends 12:00', end=30); row('first break by 10:30', brk=12); row('first break by 10:00 only', brk=6)
    for N in (0.5, 0.75, 1.25, 1.5, 2.0): row(f'TP {N}R', N=N)
    row('stop brk (consolidation low)', stop='brk'); row('stop box (opposite edge)', stop='box')
    # ------------------------------------------------ D: cost stress
    print("\n(D) COST STRESS on the default LATE trades (extra % per trade, combined ALL THREE %/day; base unaffected):")
    for ex in (0.0, 0.1, 0.2, 0.4, 0.8):
        c2 = [dict(c, pct=c['pct'] - ex) for c in cont]; s = summ(MXD.account(D, days, f + p + c2), days, h, mar)
        print(f"   +{ex:.1f}%: {s['day']:+.3f}%/day ({s['day'] - sb['day']:+.3f}), {sum(1 for x in c2 if x['pct'] is not None)} LATE signals")

if __name__ == '__main__': main()
