#!/usr/bin/env python3
"""Why do FADE trades fail before 2R, and do take-profit ladders ("curtains") help?  /usr/bin/python3 -I tools/backtest/failure_study.py {rh|M5.json.gz}
A: trades taken under LIVE exits, split by what was known at entry -> share reaching 2R and avg R per group, per half.
B: early-exit rules (cut a trade that has not reached X R after N bars).
C: take-profit ladders (sell a slice at each rung as price rises; after each rung the stop moves up).
Same entries, costs, sizing and account rules as the live backtest."""
import os, sys, statistics as st, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
RH = sys.argv[1] == 'rh'
ds = F.DS(None if RH else sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms)
days = ds.days[1:] if RH else ds.days[21:]
SPLIT = sorted(days)[len(days) // 2] if RH else '2024-04-01'
H1 = [d for d in days if d < SPLIT]; H2 = [d for d in days if d >= SPLIT]
SCH = {}

def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    info['risk_pct'] = r / entry * 100
    tr, stv, rat = SCH['tr'], SCH['st'], SCH['rat']; ts = SCH.get('ts'); last = c.last
    at = ctx_['atr'][p][d]
    rem = 1.0; gross = 0.0; i = 0; hic = entry; bestc = 0.0; mfe = 0.0; mae = 0.0; why = 'time'; xbar = last; nh = 0
    early = {}
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0:
            mfe = max(mfe, (fav - entry) * s / r)
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop' if nh == 0 else 'trail'; xbar = j; break
        mfe = max(mfe, (fav - entry) * s / r); mae = max(mae, (entry - adv) * s / r)
        early[j - k + 1] = (mfe, (cl - entry) * s / r)
        while i < len(tr) and (fav - (entry + s * tr[i][0] * r)) * s >= 0:
            T = entry + s * tr[i][0] * r; px = T if (o - T) * s <= 0 else o
            gross += tr[i][1] * (px - entry) * s; rem -= tr[i][1]; nh += 1
            ns = entry + s * stv[i] * r
            if (ns - stop) * s > 0: stop = ns
            i += 1
        if rem <= 1e-9: why = 'target'; xbar = j; rem = 0; break
        if ts and nh == 0 and j - k + 1 == ts[0] and mfe < ts[1]:
            gross += rem * (cl - entry) * s; rem = 0; why = 'timestop'; xbar = j; break
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        bestc = max(bestc, (cl - entry) * s / r)
        if nh and j < last:
            if rat[0] == 'chand': ns = hic - s * rat[1] * at[j]
            elif rat[0] == 'lag': ns = entry + s * (bestc - rat[1]) * r
            else: ns = stop
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    g = ctx_['gap'][p].get(d); trd = ctx_['trend'][p].get(d)
    info.update(xbar=xbar, why=why, hit=nh > 0, R_out=gross / r, mfe=mfe, mae=mae, early=early,
                gapdir=(None if g is None else (1 if g * s > 0 else -1)), gapabs=(abs(g) * 100 if g is not None else None),
                trenddir=(None if trd is None else (1 if trd * s > 0 else -1)), rvol=ds_.rvol(p, d, k),
                pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info

F._manage = manage
base = F.P()
def setp(tr, stv, rat, ts=None): SCH.clear(); SCH.update(tr=tr, st=stv, rat=rat, ts=ts)
def taken(dd):
    T = F.trades(ds, dd, syms, base, ctx); a = F.account(ds, dd, T); return a
LIVE = ([(2.0, 1/3)], [0.0], ('chand', 2.0))
mean = lambda x: sum(x) / len(x) if x else float('nan')
print(f"DATA {'Robinhood cache' if RH else 'Massive full tape'}: {days[0]}..{days[-1]}, {len(days)} days; halves split at {SPLIT}")

# ---------------- A
setp(*LIVE)
TK = {h: taken(dd)['taken'] for h, dd in (('H1', H1), ('H2', H2))}
allt = TK['H1'] + TK['H2']
def hhmm(k): x = 570 + 5 * k; return f"{x//60}:{x%60:02d}"
FEAT = {
 'entry time': lambda t: '10:10-10:20' if t['k'] <= 10 else ('10:25-10:45' if t['k'] <= 15 else '10:50+'),
 'bars from break to retest': lambda t: '1 bar' if t['wait'] <= 1 else ('2-3 bars' if t['wait'] <= 3 else '4+ bars'),
 'retest depth into box': lambda t: 'shallow <10%' if t['depth'] < 0.10 else ('mid 10-30%' if t['depth'] < 0.30 else 'deep 30%+'),
 'box width % of price': None, 'stop distance %': None, 'break extension %': None, 'opening RVOL': None,
 'trade vs opening gap': lambda t: 'no gap data' if t['gapdir'] is None else ('trade WITH gap' if t['gapdir'] > 0 else 'trade AGAINST gap'),
 'trade vs 20-day trend': lambda t: 'n/a' if t['trenddir'] is None else ('WITH trend' if t['trenddir'] > 0 else 'AGAINST trend'),
 'leg bought': lambda t: 'bull leg (fade a down-break)' if t['side'] > 0 else 'bear leg (fade an up-break)',
 'proxy': lambda t: t['proxy'],
 'weekday': lambda t: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][__import__('datetime').date.fromisoformat(t['day']).weekday()],
}
def terc(key):
    vals = sorted(t[key] for t in allt if t[key] is not None)
    a, b = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    return lambda t: f"low <{a:.2f}" if t[key] < a else (f"high >={b:.2f}" if t[key] >= b else f"mid {a:.2f}-{b:.2f}")
FEAT['box width % of price'] = terc('box_pct'); FEAT['stop distance %'] = terc('risk_pct')
FEAT['break extension %'] = terc('ext_pct'); FEAT['opening RVOL'] = terc('rvol')
print(f"\nA. WHAT WAS KNOWN AT ENTRY  ({len(allt)} trades taken, live exits). Each group: reached-2R share / avg R  for first half | second half | all")
print(f"   overall: H1 {100*mean([t['hit'] for t in TK['H1']]):.0f}% {mean([t['R_out'] for t in TK['H1']]):+.2f}R | H2 {100*mean([t['hit'] for t in TK['H2']]):.0f}% {mean([t['R_out'] for t in TK['H2']]):+.2f}R | all {100*mean([t['hit'] for t in allt]):.0f}% {mean([t['R_out'] for t in allt]):+.2f}R")
for name, fn in FEAT.items():
    print(f" {name}")
    groups = sorted(set(fn(t) for t in allt))
    for g in groups:
        cells = []
        for h in ('H1', 'H2'):
            x = [t for t in TK[h] if fn(t) == g]
            cells.append(f"n{len(x):3d} {100*mean([t['hit'] for t in x]) if x else 0:3.0f}% {mean([t['R_out'] for t in x]) if x else 0:+.2f}R")
        x = [t for t in allt if fn(t) == g]
        print(f"   {g:<30} {cells[0]} | {cells[1]} | n{len(x):3d} {100*mean([t['hit'] for t in x]):3.0f}% {mean([t['R_out'] for t in x]):+.2f}R")
# speed after entry
print(" how fast it moved after entry (NOT known at entry; this is what an early-exit rule could use)")
for n in (1, 2, 3, 6):
    for thr in (0.5, 1.0):
        ok = [t for t in allt if n in t['early'] and t['early'][n][0] >= thr]; no = [t for t in allt if n in t['early'] and t['early'][n][0] < thr]
        print(f"   after {n} bar(s) best >= {thr}R: n{len(ok):3d} reach2R {100*mean([t['hit'] for t in ok]):3.0f}% avg {mean([t['R_out'] for t in ok]):+.2f}R  |  not yet: n{len(no):3d} reach2R {100*mean([t['hit'] for t in no]):3.0f}% avg {mean([t['R_out'] for t in no]):+.2f}R")

# ---------------- B + C
def show(tag, tr, stv, rat, ts=None):
    setp(tr, stv, rat, ts); out = []
    for dd in (H1, H2, days):
        a = taken(dd); s = F.stat(a); tk = a['taken']; out.append((s, mean([t['R_out'] for t in tk])))
    print(f"   {tag:<50}" + ''.join(f" | {s['avg']:+.3f}%/d {r:+.2f}R {s['win']:2.0f}%w DD{s['mdd']:4.1f}" for s, r in out))
print("\nB. EARLY-EXIT RULES (live exits otherwise): cut at the close of bar N if the trade has not reached X R.   first half | second half | all")
show('LIVE (no early exit)', *LIVE)
for n in (1, 2, 3, 4, 6, 9):
    for thr in (0.25, 0.5, 1.0):
        show(f'cut if not +{thr}R after {n} bar(s) ({5*n} min)', *LIVE, ts=(n, thr))
print("\nC. TAKE-PROFIT LADDERS ('curtains'). Stop after each rung in brackets; remainder trails a 2-ATR chandelier.   first half | second half | all")
show('LIVE  1/3@2R [BE]', *LIVE)
show('1/4@2,3,4R [BE,1R,2R] + 1/4 trail', [(2, .25), (3, .25), (4, .25)], [0, 1, 2], ('chand', 2.0))
show('1/4@2,3,4R [BE,BE,BE] + 1/4 trail', [(2, .25), (3, .25), (4, .25)], [0, 0, 0], ('chand', 2.0))
show('1/3@2,3,4R [BE,1R,2R] (no runner)', [(2, 1/3), (3, 1/3), (4, 1/3)], [0, 1, 2], ('fix',))
show('1/3@2R, 1/3@4R [BE,2R] + 1/3 trail', [(2, 1/3), (4, 1/3)], [0, 2], ('chand', 2.0))
show('1/5@2,3,4,5,6R [BE,1,2,3,4R]', [(2, .2), (3, .2), (4, .2), (5, .2), (6, .2)], [0, 1, 2, 3, 4], ('fix',))
show('1/5@2,3,4,5R [BE,BE,BE,BE] + 1/5 trail', [(2, .2), (3, .2), (4, .2), (5, .2)], [0, 0, 0, 0], ('chand', 2.0))
show('1/6@2,3,4,5,6R [BE..] + 1/6 trail', [(2, 1/6), (3, 1/6), (4, 1/6), (5, 1/6), (6, 1/6)], [0, 0, 0, 0, 0], ('chand', 2.0))
show('1/4@1.5,2.5,3.5R [BE,1R,2R] + 1/4 trail', [(1.5, .25), (2.5, .25), (3.5, .25)], [0, 1, 2], ('chand', 2.0))
show('1/4@1,2,3R [BE,1R,2R] + 1/4 trail', [(1, .25), (2, .25), (3, .25)], [0, 1, 2], ('chand', 2.0))
