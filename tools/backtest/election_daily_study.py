#!/usr/bin/env python3
"""National election results and the market, 2010-2026 (governor question 2026-11-05).
    python3 -I tools/backtest/election_daily_study.py DAILY.json
DAILY.json = {sym: {day: [o,h,l,c,v]}} for QQQ SOXX IWM XLK XBI XLF (Robinhood daily bars, saved by the session; not in the repo).
For every presidential and midterm election: the election day (E), the first session after (R0, when the results are priced), R1 and R2.
Per proxy: opening gap, open-to-close move, and the day's range as a multiple of its own 60-session median. 'faded' = the day closed back against its opening gap.
Daily bars only: it describes the market, it does not test our intraday system. Changes no order, rule or state."""
import json, statistics as st, sys

D = json.load(open(sys.argv[1])); P = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']
ELECT = [('2010-11-02', 'midterm'), ('2012-11-06', 'presidential'), ('2014-11-04', 'midterm'), ('2016-11-08', 'presidential'), ('2018-11-06', 'midterm'),
         ('2020-11-03', 'presidential'), ('2022-11-08', 'midterm'), ('2024-11-05', 'presidential'), ('2026-11-03', 'midterm')]
days = {p: sorted(D[p]) for p in P}


def feat(p, d):
    ds = days[p]; i = ds.index(d)
    if i < 61: return None
    o, h, l, c, _ = D[p][d]; pc = D[p][ds[i - 1]][3]
    rg = [(D[p][x][1] - D[p][x][2]) / D[p][ds[j - 1]][3] * 100 for j, x in enumerate(ds[i - 60:i], i - 60)]
    r = (h - l) / pc * 100
    return dict(gap=(o / pc - 1) * 100, oc=(c / o - 1) * 100, cc=(c / pc - 1) * 100, ratio=r / st.median(rg))


def nxt(p, d, n):
    ds = days[p]; i = ds.index(d); return ds[i + n] if i + n < len(ds) else None


rows = []
print(f"{'election':<24} {'day':<4} {'date':<11} " + ' '.join(f"{p:>16}" for p in P) + "   (each cell: gap / open-to-close %, range x median)")
for ed, kind in ELECT:
    for lab, n in (('E', 0), ('R0', 1), ('R1', 2), ('R2', 3)):
        cells = []; date = nxt('QQQ', ed, n)
        if date is None: continue
        for p in P:
            f = feat(p, date) if date in D[p] else None
            if f is None: cells.append(f"{'n/a':>16}"); continue
            rows.append(dict(kind=kind, lab=lab, p=p, date=date, **f)); cells.append(f"{f['gap']:+5.1f}/{f['oc']:+5.1f} {f['ratio']:3.1f}x ")
        print(f"{ed + ' ' + kind:<24} {lab:<4} {date:<11} " + ' '.join(f"{c:>16}" for c in cells))
    print()


def agg(sel, name):
    r = [x for x in rows if sel(x)]
    if not r: return
    faded = [x for x in r if x['gap'] * x['oc'] < 0]
    big = [x for x in r if abs(x['gap']) >= 0.5]
    print(f"  {name:<34} n={len(r):3d}  range {st.mean(x['ratio'] for x in r):.2f}x median  |gap| {st.mean(abs(x['gap']) for x in r):.2f}%  |open-to-close| {st.mean(abs(x['oc']) for x in r):.2f}%  "
          f"gap faded {100 * len(faded) / len(r):3.0f}%  (gaps >= 0.5%: n={len(big)}, faded {100 * sum(1 for x in big if x['gap'] * x['oc'] < 0) / max(len(big), 1):3.0f}%)")


print("Averages over all six proxies and all elections in range")
for lab in ('E', 'R0', 'R1', 'R2'):
    agg(lambda x, lab=lab: x['lab'] == lab, f"{lab} all elections"); agg(lambda x, lab=lab: x['lab'] == lab and x['kind'] == 'presidential', f"{lab} presidential")
    agg(lambda x, lab=lab: x['lab'] == lab and x['kind'] == 'midterm', f"{lab} midterm")
print("\nReaction day (R0) by proxy")
for p in P: agg(lambda x, p=p: x['lab'] == 'R0' and x['p'] == p, f"R0 {p}")
print("\nR0 direction: did the day continue (close beyond the open in the gap direction) or fade?")
for ed, kind in ELECT:
    date = nxt('QQQ', ed, 1)
    if date is None: continue
    r = [x for x in rows if x['date'] == date]
    if not r: continue
    cont = sum(1 for x in r if x['gap'] * x['oc'] > 0); fad = sum(1 for x in r if x['gap'] * x['oc'] < 0)
    print(f"  {date} {kind:<12} continued {cont}, faded {fad} of {len(r)} proxies; QQQ close-to-close {[x['cc'] for x in r if x['p'] == 'QQQ'][0]:+.2f}%  IWM {[x['cc'] for x in r if x['p'] == 'IWM'][0]:+.2f}%  XLF {[x['cc'] for x in r if x['p'] == 'XLF'][0]:+.2f}%")
