#!/usr/bin/env python3
"""2-Bar Compressed ORB on 15-minute bars - full system build for the v3.126 Core Five (see TWO_BAR_SPEC.md).
    python3 tools/backtest/twobar.py > tools/backtest/results_twobar.txt

Signal on the PROXY (QQQ, SOXX, IWM, XLK, IBIT); trade its leveraged leg (TQQQ/SQQQ, SOXL/SOXS, TNA/TZA, TECL/TECS, BTCL/BTCZ).
15-minute bars are built from the 5-minute data: Bar 1 = 9:30-9:45, Bar 2 = 9:45-10:00, Bar 3 = 10:00-10:15, ...
Leg return = leverage x proxy return (intraday approximation) minus a 0.06% round trip on the leg.
"""
import itertools, math, os, statistics as st, sys, collections
from dataclasses import dataclass, replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m
from lab import get_data

ROWS = {'QQQ': ('TQQQ', 'SQQQ', 3), 'SOXX': ('SOXL', 'SOXS', 3), 'IWM': ('TNA', 'TZA', 3), 'XLK': ('TECL', 'TECS', 3), 'IBIT': ('BTCL', 'BTCZ', 2)}
LEGCOST = 0.06      # % round trip on the leg


@dataclass(frozen=True)
class Cfg:
    entry: str = 'ideal'        # 'ideal'  = buy the instant the proxy trades through the box (write-up)
                                # 'checkpoint' = a completed 5-min bar traded through -> buy at the next 5-min open (live 5-min checkpoints)
                                # 'close15' = wait for a 15-min bar to CLOSE outside the box -> buy at the next 15-min open
    window: int = 1             # number of 15-min bars after the box in which a trigger counts (1 = Bar 3 only, as written)
    stop: str = 'bar2'          # 'bar2' = Bar 2's low (long) / high (short), as written; 'trigger' = opposite end of the trigger 15-min bar;
                                # 'box' = opposite box edge; 'mid' = box midpoint
    exit: str = 'half1R_be'     # 'half1R_be' = half off at 1:1, stop to breakeven on the rest (written); 'R1'/'R1.5'/'R2'/'R2.5' = all out; 'time' = time exit only
    time_exit: int = 77         # last 5-min bar held: 77 = 15:55 close, 35 = 12:30 close, 29 = 12:00
    delayed_tp: bool = False    # True = target sale happens at the next 5-min open after a bar trades through it (live checkpoint)
    rows: tuple = tuple(ROWS)


def box(b):
    return max(x[1] for x in b[:6]), min(x[2] for x in b[:6])


def signal(b, cfg):
    """b = proxy 5-min bars (real orientation). Returns (k_entry, side, entry_price, trigger_15min_index) or None."""
    H, L = box(b)
    first, last = 6, 6 + 3 * cfg.window            # 5-min bars inside the trigger window
    if cfg.entry == 'close15':
        for q in range(cfg.window):
            s, e = 6 + 3 * q, 9 + 3 * q
            c = b[e - 1][3]
            if c > H: return e, 1, b[e][0], q
            if c < L: return e, -1, b[e][0], q
        return None
    for j in range(first, last):
        up, dn = b[j][1] >= H, b[j][2] <= L
        if up and dn: return None                      # whipsaw through both edges in one bar: no trade
        if up or dn:
            side = 1 if up else -1
            if cfg.entry == 'ideal':
                return j, side, (max(b[j][0], H) if up else min(b[j][0], L)), (j - 6) // 3
            if j + 1 > 77: return None
            return j + 1, side, b[j + 1][0], (j - 6) // 3
    return None


def manage(b, k, entry, stop, T, frac, be, last, delayed, stop_in_entry_bar):
    """Long-only management in (possibly mirrored) proxy space. Returns (pnl_per_unit, exit_bar, why)."""
    rem = 1.0; gross = 0.0; hit = False; pending = False
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]
        if pending and not hit:
            gross += frac * (o - entry); rem -= frac; hit = True; pending = False
            if be: stop = max(stop, entry)
            if rem <= 1e-9: return gross, j, 'target'
        if l <= stop and (j > k or stop_in_entry_bar):
            gross += rem * (min(stop, o) - entry if j > k else stop - entry); return gross, j, 'stop' if not hit else 'be_stop'
        if T is not None and not hit and h >= T:
            if delayed: pending = True
            else:
                gross += frac * (max(T, o) - entry); rem -= frac; hit = True
                if be: stop = max(stop, entry)
                if rem <= 1e-9: return gross, j, 'target'
    gross += rem * (b[last][3] - entry)
    return gross, last, 'time'


def trade(D, d, p, cfg):
    raw = D.bars[p][d]
    sig = signal(raw, cfg)
    if not sig: return None
    k, side, e_real, q = sig
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    H, L = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])           # box in trade-direction space (L = adverse edge)
    entry = to_m(e_real)
    if cfg.stop == 'bar2': stop = min(x[2] for x in b[3:6])
    elif cfg.stop == 'trigger':
        s = 6 + 3 * q; stop = min(x[2] for x in b[s:s + 3])
    elif cfg.stop == 'box': stop = L
    else: stop = (H + L) / 2
    if entry <= stop: return None
    r = entry - stop
    if cfg.exit == 'half1R_be': T, frac, be = entry + r, 0.5, True
    elif cfg.exit.startswith('R'): T, frac, be = entry + float(cfg.exit[1:]) * r, 1.0, False
    else: T, frac, be = None, 1.0, False
    if k > cfg.time_exit: return None
    pnl, xbar, why = manage(b, k, entry, stop, T, frac, be, cfg.time_exit, cfg.delayed_tp, stop_in_entry_bar=True)
    lev = ROWS[p][2]
    proxy_pct = pnl / e_real * 100; risk_pct = r / e_real * 100
    return dict(day=d, proxy=p, leg=ROWS[p][0] if side > 0 else ROWS[p][1], side=side, k=k, xbar=xbar, why=why,
                proxy_pct=proxy_pct, pct=lev * proxy_pct - LEGCOST, leg_risk=lev * risk_pct)


def rvol(D, p, d, k):
    try:
        pri = D.prior(d, 20); base = st.mean(D.cum[p][x][k] for x in pri); return D.cum[p][d][k] / base
    except Exception: return 0.0


def account(D, days, trades, risk=0.03, start=2000.0, max_entries=3):
    """One position at a time (rulebook E2), highest proxy RVOL among simultaneous triggers, 3% risk capped at cash."""
    by = collections.defaultdict(list)
    for t in trades: by[t['day']].append(t)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []
    for d in days:
        e0 = eq; ts = sorted(by.get(d, []), key=lambda t: t['k']); free = 0; n = 0
        while ts and n < max_entries:
            av = [t for t in ts if t['k'] >= free]
            if not av: break
            k0 = min(t['k'] for t in av)
            t = max((t for t in av if t['k'] == k0), key=lambda t: rvol(D, t['proxy'], d, t['k']))
            notional = min(eq, eq * risk / (t['leg_risk'] / 100)); pnl = notional * t['pct'] / 100
            eq += pnl; taken.append(dict(t, usd=pnl, acct=pnl / (eq - pnl) * 100)); free = t['xbar'] + 1; ts.remove(t); n += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken)


def evaluate(D, days, cfg):
    T = [t for d in days for p in cfg.rows for t in [trade(D, d, p, cfg)] if t]
    return T, account(D, days, T)


def describe(cfg):
    tx = {77: '15:55', 35: '12:30', 29: '12:00', 17: '11:00'}[cfg.time_exit]
    return f"entry={cfg.entry:<10} window={cfg.window} stop={cfg.stop:<7} exit={cfg.exit:<9} out={tx} tp={'next-chk' if cfg.delayed_tp else 'at-level'}"


def fmt(T, a, days, h):
    dl = a['daily']; tk = a['taken']; pc = [t['pct'] for t in T]
    t_ = st.mean(pc) / (st.pstdev(pc) / math.sqrt(len(pc))) if len(pc) > 2 and st.pstdev(pc) else 0
    return (f"sig {len(T):3d} leg avg {st.mean(pc) if pc else 0:+.3f}% t {t_:+.1f} | taken {len(tk):3d} win {100*sum(x['usd']>0 for x in tk)/max(len(tk),1):3.0f}% "
            f"{st.mean(dl.values()):+.3f}%/day ret {a['ret']:+6.1f}% DD {a['mdd']:4.1f}% H1 {st.mean(dl[d] for d in days[:h]):+.3f} H2 {st.mean(dl[d] for d in days[h:]):+.3f}")


def main():
    D = get_data(); days = D.days[25:]; h = len(days) // 2; H1, H2 = days[:h], days[h:]
    print(f"2-Bar Compressed ORB (15-min bars), v3.126 Core Five, {days[0]}..{days[-1]} ({len(days)} days). $2,000, 3% risk capped at cash, one position at a time, max 3/day.")
    print("Reference: pullback buy on the same list, live-realistic = +0.108%/day (H1 +0.145, H2 +0.073).\n")
    written = Cfg()
    live = Cfg(entry='checkpoint', delayed_tp=True)
    print("== As written vs. as it would execute on 5-minute checkpoints ==")
    for name, c in (('AS WRITTEN (instant break of box in Bar 3, Bar-2 stop, half at 1:1 + breakeven, hold to close)', written),
                    ('LIVE-REALISTIC (same rules; entry/target at the next 5-min checkpoint)', live)):
        T, a = evaluate(D, days, c); print(f"{name}\n   {describe(c)}\n   {fmt(T, a, days, h)}")
    T, a = evaluate(D, days, live)
    print("\n   live-realistic by row/side:")
    g = collections.defaultdict(list)
    for t in a['taken']: g[(t['proxy'], 'bull' if t['side'] > 0 else 'bear')].append(t)
    for k in sorted(g):
        v = g[k]; print(f"     {k[0]:<5}{k[1]:<5} n={len(v):3d} win={100*sum(x['usd']>0 for x in v)/len(v):3.0f}% acct {sum(x['acct'] for x in v):+6.2f}%")
    print("   exits:", dict(collections.Counter(t['why'] for t in a['taken'])))

    print("\n== Full grid, live-realistic execution (checkpoint/close15 entries, target at next checkpoint) ==")
    grid = [Cfg(entry=e, window=w, stop=s, exit=x, time_exit=tx, delayed_tp=True)
            for e in ('checkpoint', 'close15') for w in (1, 2, 4) for s in ('bar2', 'trigger', 'box', 'mid')
            for x in ('half1R_be', 'R1', 'R2', 'time') for tx in (77, 35)]
    res = []
    for c in grid:
        T1, a1 = evaluate(D, H1, c); T2, a2 = evaluate(D, H2, c)
        res.append((c, len(a1['taken']), st.mean(a1['daily'].values()), len(a2['taken']), st.mean(a2['daily'].values())))
    res.sort(key=lambda r: -r[2])
    print(f"{'config':<82}{'trd H1':>7}{'H1 %/day':>10}{'trd H2':>7}{'H2 %/day':>10}")
    for c, n1, d1, n2, d2 in res[:15]:
        print(f"{describe(c):<82}{n1:>7}{d1:>+10.3f}{n2:>7}{d2:>+10.3f}")
    print(f"   ... ({len(res)} configs; worst H1 {res[-1][2]:+.3f}%/day)")
    pos1 = sum(1 for r in res if r[2] > 0); pos2 = sum(1 for r in res if r[4] > 0); both = sum(1 for r in res if r[2] > 0 and r[4] > 0)
    print(f"   configs positive in H1: {pos1}/{len(res)}, in H2: {pos2}/{len(res)}, in both: {both}/{len(res)}")
    ok = [r for r in res if r[1] >= 20]
    best = ok[0]
    print(f"\nWALK-FORWARD PICK (best H1, >= 20 trades): {describe(best[0])}")
    print(f"   H1 (chosen here): {best[1]} trades {best[2]:+.3f}%/day  ->  H2 (unseen): {best[3]} trades {best[4]:+.3f}%/day")
    T, a = evaluate(D, days, best[0]); print(f"   full period: {fmt(T, a, days, h)}")

    print("\n== Raw follow-through after the trigger (proxy, signed in breakout direction, no stop) ==")
    for c, lab in ((Cfg(entry='checkpoint'), 'instant/checkpoint trigger in Bar 3'), (Cfg(entry='close15'), '15-min close outside the box (Bar 3)')):
        for hz, hl in ((6, '+30m'), (12, '+60m'), (35, 'to 12:30'), (77, 'to close')):
            v = []
            for d in days:
                for p in ROWS:
                    raw = D.bars[p][d]; s = signal(raw, c)
                    if not s: continue
                    k, side, e, q = s
                    v.append(side * (raw[min(k + hz, 77) if hz != 35 and hz != 77 else hz][3] / e - 1) * 100)
            print(f"   {lab:<40} {hl:<9} n={len(v)} avg {st.mean(v):+.3f}% (se {st.pstdev(v)/math.sqrt(len(v)):.3f})  in profit {100*sum(x>0 for x in v)/len(v):.0f}%")


if __name__ == '__main__':
    main()
