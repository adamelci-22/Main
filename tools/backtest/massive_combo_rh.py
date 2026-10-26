#!/usr/bin/env python3
"""The new mix on the Robinhood bars only (repo data/bt_5m.json.gz, real Robinhood 5-minute bars 2026-03-02..10-15), against the live system.
    /usr/bin/python3 -I tools/backtest/massive_combo_rh.py > tools/backtest/results/massive_combo_rh.txt
NEW   = FADE on QQQ SOXX IWM XLK XBI XLF + SPY, PULLBACK on SOXS LABD TECS DRIP UVIX FAZ.
LIVE  = FADE on the six, PULLBACK on SOXS LABD TECS UVXY.
Window 2026-03-03..2026-10-14 (157 days), the same as final_system.py. Account 1: mixed.account ($2,000, 3% risk capped at cash, one position, 3 entries a day).
Account 2: whole shares at the real Robinhood leg price on the entry bar open, A1 gates (5 losses in a row, 3% day stop, 6 entries a day), extra cost 0.10% per round trip.
Untouched sub-window 2026-03-03..04-06 is shown separately (no rule or list was chosen on it for the live system).
"""
import collections, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY']
import manual as m, pb_final as PBF, pb_inverse as PI, mixed as MXD, expand_lists as EX, fade_addone as FA, twobar as TB
from lab import get_data
LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
ROWS = {p: FA.ROWS[p] for p in LIVE6}; ROWS['SPY'] = ('UPRO', 3, 'SPXU', 3)
LEG = {p: (r[0], r[2]) for p, r in ROWS.items()}
PBLIVE = ['SOXS', 'LABD', 'TECS', 'UVXY']; PBNEW = ['SOXS', 'LABD', 'TECS', 'DRIP', 'UVIX', 'FAZ']


def acct2(D, days, cands, extra=0.10, risk=0.03, start=2000.0):
    by = collections.defaultdict(list)
    for c in cands: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; taken = []; daily = {}
    for d in days:
        e0 = eq; cs = sorted(by.get(d, []), key=lambda c: c['k']); free = 0; n = 0; streak = 0
        while cs and n < 6:
            av = [c for c in cs if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq, eq * risk / (c['risk'] / 100))
            leg = c['name'] if c['sys'] == 'PB' else LEG[c['proxy']][0 if c['name'].endswith('+') else 1]
            b = D.bars.get(leg, {}).get(d); px = b[c['k']][0] if b and c['k'] < len(b) else None
            if not px: cs.remove(c); continue
            sh = math.floor(notional / px)
            if sh < 1: cs.remove(c); continue
            pnl = sh * px * (c['pct'] - extra) / 100; eq += pnl; taken.append(dict(c, usd=pnl)); free = c['xbar'] + 1; cs.remove(c); n += 1
            streak = streak + 1 if pnl < 0 else (0 if pnl > 0 else streak)
            if streak >= 5 or eq / e0 - 1 <= -0.03: break
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken, eq=eq)


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
    for f in PBNEW + PBLIVE: PI.PROXY.setdefault(f, f)
    PI.PROXY.update({'SOXS': 'SOXX', 'TECS': 'XLK', 'LABD': 'LABD', 'UVXY': 'UVXY'})
    allf = sorted(set(PBNEW + PBLIVE)); S = PBF.run(D, D.days[1:], allf, oco_gap=True)
    pb = {f: [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S if x['inst'] == f] for f in allf}
    fd = {p: MXD.norm_px(EX.fade_trades(D, D.days[1:], p, ROWS[p]), 'FADE') for p in ROWS}
    f6 = [x for p in LIVE6 for x in fd[p]]; f7 = f6 + fd['SPY']
    sysm = {'LIVE   (FADE 6, PB SOXS LABD TECS UVXY)': f6 + [x for f in PBLIVE for x in pb[f]],
            'NEW    (FADE 6+SPY, PB SOXS LABD TECS DRIP UVIX FAZ)': f7 + [x for f in PBNEW for x in pb[f]],
            'FADE 6+SPY only change (PB live)': f7 + [x for f in PBLIVE for x in pb[f]],
            'PB change only (FADE 6)': f6 + [x for f in PBNEW for x in pb[f]]}
    wins = (('FULL 2026-03-03..10-14', days), ('UNTOUCHED 03-03..04-06', [d for d in days if d <= '2026-04-06']), ('TUNING 04-07..10-14', [d for d in days if d >= '2026-04-07']))
    print(f"Robinhood bars only, {len(days)} days {days[0]}..{days[-1]}\n")
    for title, fn in (('Account 1 (continuous sizing, signal-model costs)', lambda ds, cs: MXD.account(D, ds, [c for c in cs if c['day'] in set(ds)])),
                      ('Account 2 (whole shares, A1 gates, +0.10% cost)', lambda ds, cs: acct2(D, ds, [c for c in cs if c['day'] in set(ds)]))):
        print(f"== {title} ==")
        for nm, cs in sysm.items():
            row = []
            for _, ds in wins:
                a = fn(ds, cs); t = a['taken']
                row.append(f"{st.mean(a['daily'].values()):+.3f}%/d {a['ret']:+5.0f}% DD{a['mdd']:>4.1f}% n={len(t):>3} w{100*sum(x['usd']>0 for x in t)/max(len(t),1):>3.0f}%")
            print(f"  {nm:<52}" + ' | '.join(row))
        print("  " + ' ' * 52 + ' | '.join(f"{n:<42}" for n, _ in wins) + "\n")
    cs = sysm['NEW    (FADE 6+SPY, PB SOXS LABD TECS DRIP UVIX FAZ)']; a = MXD.account(D, days, [c for c in cs if c['day'] in set(days)])
    cl = sysm['LIVE   (FADE 6, PB SOXS LABD TECS UVXY)']; al = MXD.account(D, days, [c for c in cl if c['day'] in set(days)])
    def by(a_):
        g = collections.defaultdict(list)
        for x in a_['taken']: g[(x['sys'], x['proxy'] if x['sys'] == 'FADE' else x['name'])].append(x)
        return g
    print("== By system and ticker, account 1, full window: trades, win%, total $ (NEW | LIVE) ==")
    gn, gl = by(a), by(al)
    for k in sorted(set(gn) | set(gl), key=lambda k: (k[0], -sum(x['usd'] for x in gn.get(k, [])))):
        f_ = lambda g: f"{len(g[k]):>2} tr win {100*sum(x['usd']>0 for x in g[k])/len(g[k]):>3.0f}% ${sum(x['usd'] for x in g[k]):>+6.0f}" if k in g else '--'
        print(f"   {k[0]:<5}{k[1]:<6}NEW {f_(gn):<24}LIVE {f_(gl)}")
    print("\n== Month by month, account 1 (compounding from $2,000): NEW | LIVE ==")
    for lab, aa in (('NEW', a), ('LIVE', al)):
        mo = collections.OrderedDict(); eq = 2000.0
        for d in days:
            e0 = eq; eq *= 1 + aa['daily'][d] / 100; mo.setdefault(d[:7], [e0, eq])[1] = eq
        print(f"   {lab:<5}" + ', '.join(f"{k[5:]} {100*(v[1]/v[0]-1):+.1f}%" for k, v in mo.items()) + f"   end ${eq:,.0f}")


if __name__ == '__main__':
    main()
