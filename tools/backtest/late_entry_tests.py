"""Late-entry and limit-order tests for FADE entries (2026-03-03..10-14, live rules, same account).
d = number of 5-minute bars the order is late (d=0 is the model: buy at the open of the entry bar).
Fill rules at bar k+d: 'market' = buy at that bar's open. 'limit +a%' = limit at (model entry price x (1+a%)) in proxy terms: fills at the open if the open is
at or below the limit, at the limit if the bar trades down to it, otherwise no trade. After the fill the stop and the 2R target are re-set from the fill with the
SAME R distance (rulebook B5.2). PULLBACK entries are unchanged (they are already limit orders at the trigger close)."""
import statistics as st, math, collections
import final_system as FS, mixed as MXD, manual as m, retest as RT, twobar as TB, expand_lists as EX, fade_addone as FA, fade_combo as FC, pb_final as PBF
from lab import get_data

def trade(D, d, p, late, a, R=2.0, frac=1 / 3, last=47):
    raw = D.bars[p][d]; s = RT.setup(raw, FC.FADE)
    if not s: return None
    k, side, e_real, stop_real = s
    if k >= last: return None
    b, p0 = (raw, None) if side > 0 else m.mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry0, stop0 = to_m(e_real), to_m(stop_real)
    if entry0 <= stop0: return None
    r = entry0 - stop0
    kk = k + late
    if kk >= last: return None
    o = b[kk][0]
    if a is None: entry = o
    else:
        L = entry0 * (1 + a / 100)
        if o <= L: entry = o
        elif b[kk][2] <= L: entry = L
        else: return None
    if entry - r <= 0: return None
    stop = entry - r; T = entry + R * r
    gross = 0.0; rem = 1.0; hit = False; hic = entry; xbar = last
    for j in range(kk, last + 1):
        oo, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, oo) if j > kk else stop; gross += rem * (px - entry); rem = 0; xbar = j; break
        if not hit and h >= T:
            px = max(T, oo) if j > kk else T; gross += frac * (px - entry); rem = 1 - frac; hit = True; stop = max(stop, entry)
            if rem <= 1e-9: xbar = j; break
        hic = max(hic, c)
        if hit and j < last: stop = max(stop, hic - 2.0 * m.atr(b, j))
    if rem > 0: gross += rem * (b[last][3] - entry)
    real_entry = entry if side > 0 else 2 * p0 - entry
    lev = TB.ROWS[p][2]
    return dict(day=d, proxy=p, side=side, k=kk, xbar=xbar, pct=lev * gross / real_entry * 100 - TB.LEGCOST, leg_risk=lev * r / real_entry * 100, hit=hit)

def fade_cands(D, days, late, a):
    out = []
    for p in FS.FADE:
        row = FA.ROWS[p]; bull, lb, bear, lbe = row
        saved = TB.ROWS.get(p); TB.ROWS[p] = (bull, bear, lb)
        for d in days:
            if d not in D.bars.get(p, {}): continue
            t = trade(D, d, p, late, a)
            if not t: continue
            if t['side'] < 0 and lbe != lb: t['pct'] = (t['pct'] + TB.LEGCOST) / lb * lbe - TB.LEGCOST; t['leg_risk'] = t['leg_risk'] / lb * lbe
            out.append(t)
        if saved: TB.ROWS[p] = saved
        else: del TB.ROWS[p]
    return MXD.norm_px(out, 'FADE')

def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = [x for x in D.days[1:] if '2026-03-03' <= x <= '2026-10-14']
    f0, p0 = FS.cands(D, days)
    base = MXD.account(D, days, f0 + p0)
    def stats(fc, tag, ref=None):
        a = MXD.account(D, days, fc + p0); tk = a['taken']; fd = [t for t in tk if t['sys'] == 'FADE']; dl = list(a['daily'].values())
        w = 100 * sum(t['usd'] > 0 for t in tk) / max(len(tk), 1)
        print(f"{tag:<38}{len(tk):>5}{len(fd):>6}{w:>6.0f}%{st.mean(dl):>+9.3f}%{a['ret']:>+9.1f}%{a['mdd']:>6.1f}%{(st.mean(dl)-ref) if ref is not None else 0:>+9.3f}")
        return st.mean(dl)
    print(f"Check: FADE d=0 market reproduces the live backtest -> {len(f0)} fade candidates; account {len(base['taken'])} trades {st.mean(base['daily'].values()):+.3f}%/day\n")
    print(f"{'':<38}{'trd':>5}{'fade':>6}{'win':>7}{'%/day':>10}{'return':>10}{'DD':>7}{'vs live':>9}")
    ref = None
    for late in (0, 1, 2, 3):
        print(f"-- order {late} bar(s) = {5*late} min late --")
        for a, tag in ((None, 'market fill at that bar open'), (0.30, 'limit +0.30% (proxy)'), (0.17, 'limit +0.17% (~0.5% on a 3x leg)'), (0.10, 'limit +0.10%'), (0.05, 'limit +0.05%'), (0.0, 'limit at model price (+0.00%)')):
            if late == 0 and a is not None and a != 0.0: continue
            v = stats(fade_cands(D, days, late, a), '  ' + tag, ref)
            if late == 0 and a is None: ref = v
    print("\nHow often does the proxy move away from the model price by the time of a late order? (all fade setups, proxy move in the adverse direction, %)")
    for late in (1, 2):
        mv = []
        for p in FS.FADE:
            for d in days:
                if d not in D.bars.get(p, {}): continue
                s = RT.setup(D.bars[p][d], FC.FADE)
                if not s: continue
                k, side, e_real, _ = s
                if k + late >= 47: continue
                x = D.bars[p][d][k + late][0]; mv.append((x / e_real - 1) * 100 * side)
        mv.sort(); n = len(mv)
        print(f"  {late} bar late: median {mv[n//2]:+.3f}%, 75th pct {mv[3*n//4]:+.3f}%, 90th pct {mv[9*n//10]:+.3f}% (positive = price already ran in the trade's favour direction); share beyond +0.17%: {100*sum(x>0.17 for x in mv)/n:.0f}%")
main()
