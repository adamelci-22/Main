#!/usr/bin/env python3
"""Five-year Massive backtest with the live account rules applied on top of the signal rules (RULEBOOK v5.2.15).
    /usr/bin/python3 -I tools/backtest/massive_live_rules.py MASSIVE_5M.json.gz MASSIVE_DAILY.json.gz SPLITS_DIR > tools/backtest/results/massive_live_rules.txt
Signals, stops, targets and exits are final_system.py's (B2, B3, 13:30 flat, tie-break by RVOL, one position at a time). Added here:
  B4.1  whole shares: shares = floor(min(cash, 3% x equity / stop distance) / leg price at the entry bar open); 0 shares = no trade. FADE legs use the real Massive leg prices.
        The bars are split-adjusted, so the price a buyer paid on the day is adjusted price / (product of split ratios executed after that day), from the Massive splits files.
  A1.1  5 losing trades in a row -> no entries for the rest of the day; assumed cleared the next trading day (the governor clears it by hand).
  A1.2  account down 3% on the day (against the day's opening equity) -> no more entries that day.
  A1.3  at most 6 entries a day (final_system.py used 3).
  A1.4  floor: no trading once equity is below 50% of the $2,000 deposit (permanent here; a deposit would restart it).
  Costs: the signal model already charges 0.06% round trip on the leg. Scenarios add 0%, 0.10% or 0.30% more per round trip (spread and slippage; Massive has no quotes).
Not modelled (no historical quotes or order-state data): A1.6 late-entry band, A1.7 spread skip, B4.6 liquidity cap (dormant below $100,000), OCO rejection fallbacks.
"""
import collections, gzip, json, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as BT
_raw = json.load(gzip.open(sys.argv[1], 'rt')); _daily = json.load(gzip.open(sys.argv[2], 'rt'))
BT.load = lambda: (_raw, _daily)
import glob
SPL = {os.path.basename(f)[:-5]: sorted((x['execution_date'], x['split_from'] / x['split_to']) for x in json.load(open(f))) for f in glob.glob(os.path.join(sys.argv[3], '*.json'))}
BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
import manual as m, pb_final as PBF, mixed as MXD, twobar as TB
import final_system as FS
from lab import get_data
LEG = {'QQQ': ('TQQQ', 'SQQQ'), 'SOXX': ('SOXL', 'SOXS'), 'IWM': ('TNA', 'TZA'), 'XLK': ('TECL', 'TECS'), 'XBI': ('LABU', 'LABD'), 'XLF': ('FAS', 'FAZ')}


LAST = max(max(v) for v in _raw['QQQ'].values()) and max(_raw['QQQ'])


def leg_px(D, c):
    leg = c['name'] if c['sys'] == 'PB' else LEG[c['proxy']][0 if c['name'].endswith('+') else 1]
    b = D.bars.get(leg, {}).get(c['day'])
    if not (b and c['k'] < len(b)): return None
    fac = 1.0
    for ex, r in SPL.get(leg, []):
        if c['day'] < ex <= LAST: fac *= r
    return b[c['k']][0] / fac


def live_account(D, days, cands, extra_rt=0.0, gates=True, whole=True, max_entries=6, start=2000.0, risk=0.03):
    by = collections.defaultdict(list)
    for c in cands: by[c['day']].append(c)
    eq = start; peak = start; mdd = 0.0; daily = {}; taken = []; streak = 0; halted = None
    cnt = collections.Counter()
    for d in days:
        e0 = eq; cs = sorted(by.get(d, []), key=lambda c: c['k']); n = 0; free = 0
        if gates: streak = 0                                           # A1.1 cleared at the start of each day
        while cs and n < max_entries:
            if gates and halted: cnt['floor days'] += 1; break
            av = [c for c in cs if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq, eq * risk / (c['risk'] / 100))
            if whole:
                px = c['px']
                if not px: cs.remove(c); cnt['no price'] += 1; continue
                sh = math.floor(notional / px)
                if sh < 1: cs.remove(c); cnt['under one share'] += 1; continue
                notional = sh * px
            pnl = notional * (c['pct'] - extra_rt) / 100
            eq += pnl; taken.append(dict(c, usd=pnl)); free = c['xbar'] + 1; cs.remove(c); n += 1
            streak = streak + 1 if pnl < 0 else (0 if pnl > 0 else streak)
            if gates:
                if streak >= 5: cnt['A1.1 lockout days'] += 1; break
                if eq / e0 - 1 <= -0.03: cnt['A1.2 day-loss stops'] += 1; break
                if eq < 0.5 * start and not halted: halted = d; cnt['A1.4 floor hit'] += 1; break
        if cs and n >= max_entries: cnt['A1.3 cap days'] += 1
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100); daily[d] = (eq / e0 - 1) * 100
    return dict(ret=(eq / start - 1) * 100, mdd=mdd, daily=daily, taken=taken, cnt=cnt, halted=halted, eq=eq)


def line(tag, days, a):
    t = a['taken']
    if not t: return f"{tag:<46}{len(days):>5} days  no trades"
    w = sum(x['usd'] > 0 for x in t); dl = a['daily']
    return (f"{tag:<46}{len(days):>5} days  trades {len(t):>4}  win {100*w/len(t):>3.0f}%  {st.mean(dl.values()):+.3f}%/day  ret {a['ret']:+8.1f}%  DD {a['mdd']:>5.1f}%  end ${a['eq']:>9,.0f}"
            + (f"  halted {a['halted']}" if a['halted'] else ''))


def main():
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    f, p = FS.cands(D, days)
    cs = [dict(c, px=leg_px(D, c)) for c in f + p]
    win = [('ALL 2021-11-02..2026-10-23', days), ('OUT OF SAMPLE ..2026-02-27', [d for d in days if d <= '2026-02-27']), ('RULES WINDOW 2026-03-03..10-14', [d for d in days if '2026-03-03' <= d <= '2026-10-14'])]
    scen = [('S0 signal model only (3 entries/day, no gates, continuous $)', dict(gates=False, whole=False, max_entries=3)),
            ('S1 + live rules, whole shares, cost +0.00%', dict(extra_rt=0.0)),
            ('S2 + live rules, whole shares, cost +0.10%', dict(extra_rt=0.10)),
            ('S3 + live rules, whole shares, cost +0.30%', dict(extra_rt=0.30))]
    for wn, ds in win:
        S = set(ds); sub = [c for c in cs if c['day'] in S]
        print(f"== {wn} ==")
        for sn, kw in scen:
            a = live_account(D, ds, sub, **kw); print(line(sn, ds, a))
            if sn.startswith('S2') or sn.startswith('S1'): print(f"      rule counters: {dict(a['cnt'])}")
        for sn, flt in (('   S2 FADE only', 'FADE'), ('   S2 PULLBACK only', 'PB')):
            a = live_account(D, ds, [c for c in sub if c['sys'] == flt], extra_rt=0.10); print(line(sn, ds, a))
        print()
    print("== By calendar year, S2 (live rules, +0.10%), each year restarted at $2,000 ==")
    for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
        ds = [d for d in days if d.startswith(y)]; S = set(ds)
        print(line(f'{y} COMBINED', ds, live_account(D, ds, [c for c in cs if c['day'] in S], extra_rt=0.10)))
    print("\n== Raw edge per trade, no sizing, no compounding (signal model, before extra cost): average % on the leg and win rate ==")
    for lab, a_, b_ in (('2021-11..2023-12', '2021-11-01', '2023-12-31'), ('2024', '2024-01-01', '2024-12-31'), ('2025', '2025-01-01', '2025-12-31'),
                        ('2026-01..02', '2026-01-01', '2026-02-27'), ('2026-03..10', '2026-03-03', '2026-10-14')):
        for sy in ('FADE', 'PB'):
            v = [c['pct'] for c in cs if c['sys'] == sy and a_ <= c['day'] <= b_]
            if v: print(f"   {lab:<18}{sy:<6}{len(v):>5} signals  win {100*sum(x>0 for x in v)/len(v):>3.0f}%  avg {st.mean(v):+.3f}%  median {st.median(v):+.3f}%  avg win {st.mean([x for x in v if x>0]):+.2f}%  avg loss {st.mean([x for x in v if x<=0]):+.2f}%")


if __name__ == '__main__':
    main()
