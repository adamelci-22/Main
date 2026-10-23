#!/usr/bin/env python3
"""Best FADE list and best PULLBACK list, searched separately from the governor's 22-row table plus the live lists.
    python3 tools/backtest/combo_search.py > tools/backtest/results/combo_search.txt
Engine = final_system.py (live rules v5.2.12), 2026-03-03..10-14, $2,000, one position at a time.
FADE search: PULLBACK fixed at the live list. PULLBACK search: FADE fixed at the live list.
Leverage = measured (5-min beta vs the 1x ticker), not the nominal label: single-stock bulls ~2x, single-stock bears ~1x, KRE via FAS/FAZ ~1.25x.
Liquidity screen: median 5-min $ volume >= MIN_DV on every leg traded.
Method A: greedy forward selection on the full sample (optimistic: chosen and judged on the same data).
Method B: walk-forward. Greedy on H1 only, judged on H2; greedy on H2 only, judged on H1. This is the honest number.
"""
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA
import final_system as FS
from lab import get_data

MIN_DV = 100_000
FADE_ROWS = dict(FA.ROWS)
FADE_ROWS.update({'AAPL': ('AAPU', 2, 'AAPD', 1), 'AMZN': ('AMZU', 2, 'AMZD', 1), 'META': ('METU', 2, 'METD', 1), 'MSFT': ('MSFU', 2, 'MSFD', 1),
                  'SMH': ('SOXL', 3, 'SOXS', 3), 'XLV': ('CURE', 3, 'RXD', 2), 'KRE': ('FAS', 1.25, 'FAZ', 1.25)})
FA.ROWS.update(FADE_ROWS)
FADE_POOL = FS.FADE + ['NVDA', 'AAPL', 'AMZN', 'META', 'MSFT', 'SPY', 'SMH', 'XLV', 'XLF', 'KRE', 'GDX', 'XLE', 'XOP', 'TLT']
PB_MAP = {'NVDU': 'NVDA', 'NVDD': 'NVDA', 'AAPU': 'AAPL', 'AAPD': 'AAPL', 'AMZU': 'AMZN', 'AMZD': 'AMZN', 'METU': 'META', 'METD': 'META',
          'MSFU': 'MSFT', 'MSFD': 'MSFT', 'NFLU': 'NFLU', 'TQQQ': 'QQQ', 'SQQQ': 'QQQ', 'UPRO': 'SPY', 'SPXU': 'SPY', 'TNA': 'IWM', 'TZA': 'IWM',
          'SOXL': 'SOXX', 'TECL': 'XLK', 'LABU': 'XBI', 'CURE': 'XLV', 'RXD': 'XLV', 'FAS': 'XLF', 'FAZ': 'XLF', 'NUGT': 'GDX', 'DUST': 'GDX',
          'ERX': 'XLE', 'ERY': 'XLE', 'GUSH': 'XOP', 'DRIP': 'XOP', 'TMF': 'TLT', 'TMV': 'TLT'}
PI.PROXY.update(PB_MAP)
PB_POOL = FS.PB + list(PB_MAP)


def stats(a, days):
    dl = a['daily']; h = len(days) // 2
    return st.mean(dl.values()), st.mean(dl[d] for d in days[:h]), st.mean(dl[d] for d in days[h:]), a['mdd'], len(a['taken'])


def greedy(D, days, pool, cand, fixed):
    """Forward selection on `days`: add the ticker that raises %/day most; stop when nothing helps."""
    dd = set(days); sub = {q: [c for c in cand[q] if c['day'] in dd] for q in pool}; fx = [c for c in fixed if c['day'] in dd]
    val = lambda L: st.mean(MXD.account(D, days, fx + [c for q in L for c in sub[q]])['daily'].values())
    chosen, path, cur = [], [], val([])
    while True:
        rest = [q for q in pool if q not in chosen]
        if not rest: break
        sc = {q: val(chosen + [q]) for q in rest}; q = max(sc, key=sc.get)
        if sc[q] <= cur: break
        chosen.append(q); path.append((q, sc[q], sc[q] - cur)); cur = sc[q]
    return chosen, path


def judge(D, days, L, cand, fixed):
    dd = set(days)
    return st.mean(MXD.account(D, days, [c for c in fixed if c['day'] in dd] + [c for q in L for c in cand[q] if c['day'] in dd])['daily'].values())


def run(label, D, days, pool, cand, fixed, live, dv):
    h = len(days) // 2; H1, H2 = days[:h], days[h:]; mar = [d for d in days if d < '2026-04-07']
    print(f"\n===== {label} =====")
    print("Pool (liquidity, trades alone over 157 days):")
    for q in pool:
        n = len(cand[q]); w = sum(c['pct'] > 0 for c in cand[q])
        print(f"   {q:<5} {'LIVE ' if q in live else '     '}$vol {dv[q]/1e3:>7,.0f}k  setups {n:3d}  win {100*w/n if n else 0:3.0f}%  avg {st.mean(c['pct'] for c in cand[q]) if n else 0:+.2f}%")
    ok = [q for q in pool if dv[q] >= MIN_DV and cand[q]]
    print(f"Passing liquidity (>= ${MIN_DV/1e3:.0f}k/bar) and with setups: {ok}")
    print(f"Dropped for liquidity or no setups: {[q for q in pool if q not in ok]}")
    print(f"\nLive list {live}: full {judge(D, days, live, cand, fixed):+.3f}  H1 {judge(D, H1, live, cand, fixed):+.3f}  H2 {judge(D, H2, live, cand, fixed):+.3f}  March {judge(D, mar, live, cand, fixed):+.3f}")
    L, path = greedy(D, days, ok, cand, fixed)
    print("\nA. Greedy on the full sample (in-sample, optimistic):")
    for i, (q, v, g) in enumerate(path, 1): print(f"   {i:2d}. +{q:<5} {v:+.3f}%/day  (step {g:+.3f})")
    best10 = [q for q, v, g in path if g >= 0.01]; best10 = [q for q, _, _ in path][:len(best10)] if best10 else []
    # prefix of the path while every step >= 0.01
    pre = []
    for q, v, g in path:
        if g < 0.01: break
        pre.append(q)
    for tag, LL in (('max %/day', L), ('every step >= 0.01', pre)):
        print(f"   -> {tag}: {LL}  full {judge(D, days, LL, cand, fixed):+.3f}  H1 {judge(D, H1, LL, cand, fixed):+.3f}  H2 {judge(D, H2, LL, cand, fixed):+.3f}  March {judge(D, mar, LL, cand, fixed):+.3f}")
    print("\nB. Walk-forward (choose on one half, judge on the other):")
    for nm, tr, te in (('choose H1 -> judge H2', H1, H2), ('choose H2 -> judge H1', H2, H1)):
        Lw, _ = greedy(D, tr, ok, cand, fixed)
        print(f"   {nm}: chose {Lw}")
        print(f"      out-of-sample {judge(D, te, Lw, cand, fixed):+.3f}  vs live list on the same half {judge(D, te, live, cand, fixed):+.3f}")
    return L, pre


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    f_live, p_live = FS.cands(D, days)
    fc = {q: MXD.norm_px(EX.fade_trades(D, days, q, FADE_ROWS[q]), 'FADE') for q in FADE_POOL if q in D.bars}
    pc = {}
    for q in PB_POOL:
        s = PBF.run(D, days, [q], oco_gap=True)
        pc[q] = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
    fdv = {q: min(EX.dollar_vol(D, FADE_ROWS[q][0], days), EX.dollar_vol(D, FADE_ROWS[q][2], days)) for q in fc}
    pdv = {q: EX.dollar_vol(D, q, days) for q in pc}
    base = stats(MXD.account(D, days, f_live + p_live), days)
    print(f"LIVE SYSTEM: {base[0]:+.3f}%/day  H1 {base[1]:+.3f}  H2 {base[2]:+.3f}  DD {base[3]:.1f}%  trades {base[4]}")
    print("Not testable (no such ETF on Robinhood / wrong ticker): GOOGL (GOOU absent; GOOD is Gladstone Commercial, a REIT), AVGO (AVGL/AVGD absent), "
          "NFLX bear (NFLD absent; NFLU tested on PULLBACK only), QCOM (QCL/QCD absent), XLV bear SICK absent (RXD -2x used instead).")
    FL, Fpre = run('FADE (PULLBACK fixed at the live list)', D, days, [q for q in FADE_POOL if q in fc], fc, p_live, FS.FADE, fdv)
    PL, Ppre = run('PULLBACK (FADE fixed at the live list)', D, days, PB_POOL, pc, f_live, FS.PB, pdv)
    print("\n===== Both best lists together (in-sample) =====")
    for tag, F_, P_ in (('max %/day lists', FL, PL), ('every-step>=0.01 lists', Fpre, Ppre)):
        cs = [c for q in F_ for c in fc[q]] + [c for q in P_ for c in pc[q]]
        s = stats(MXD.account(D, days, cs), days); mar = [d for d in days if d < '2026-04-07']
        sm = st.mean(MXD.account(D, mar, [c for c in cs if c['day'] < '2026-04-07'])['daily'].values())
        print(f"   {tag}: FADE {F_} | PB {P_}\n      {s[0]:+.3f}%/day  H1 {s[1]:+.3f}  H2 {s[2]:+.3f}  March {sm:+.3f}  DD {s[3]:.1f}%  trades {s[4]}")


if __name__ == '__main__':
    main()
