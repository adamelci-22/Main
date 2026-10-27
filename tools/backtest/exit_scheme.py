#!/usr/bin/env python3
"""Tranche exit schemes on live FADE (30-min box), Massive 5y tape.  /usr/bin/python3 -I tools/backtest/exit_scheme.py M5.json.gz > results/exit_scheme.txt
Scheme = list of (target R, fraction) tranches; after tranche i the stop moves to stops[i] (R above entry); the last remainder uses a ratchet:
 ('fix',)      stop stays where the last tranche put it
 ('chand',k)   k x ATR(14) chandelier on closes, never below the current stop
 ('lag',x)     stop = (best close in R) - x R, never below the current stop
 ('step',)     stop = floor(best close in R) - 1 R (locks one R behind each whole R), never below the current stop
Same entries, costs (0.06% round trip), account rules as the live backtest. Compare H1 (< 2024-04) vs H2."""
import os, sys, collections
from dataclasses import replace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fade_diag as F
ds = F.DS(sys.argv[1], F.ALL); syms = [s for s in F.LIVE if s in ds.bars]; ctx = F.context(ds, syms); days = ds.days[21:]
H1 = [d for d in days if d < '2024-04-01']; H2 = [d for d in days if d >= '2024-04-01']
SCH = {}
_orig = F._manage

def manage(ds_, p, d, b, k, side, entry, ext, c, info, ctx_):
    s = side; stop = ext; r = (entry - stop) * s
    if r <= 0: return None
    risk = r / entry * 100; info['risk_pct'] = risk
    tr, st, rat = SCH['tr'], SCH['st'], SCH['rat']
    at = ctx_['atr'][p][d]; last = c.last
    rem = 1.0; gross = 0.0; i = 0; hic = entry; best = 0.0; mfe = 0.0; mae = 0.0; why = 'time'; xbar = last; n_hit = 0
    for j in range(k, last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        mfe = max(mfe, (fav - entry) * s / r); mae = max(mae, (entry - adv) * s / r)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop' if n_hit == 0 else 'trail'; xbar = j; break
        while i < len(tr) and (fav - (entry + s * tr[i][0] * r)) * s >= 0:
            T = entry + s * tr[i][0] * r; px = T if (o - T) * s <= 0 else o
            gross += tr[i][1] * (px - entry) * s; rem -= tr[i][1]; n_hit += 1
            ns = entry + s * st[i] * r
            if (ns - stop) * s > 0: stop = ns
            i += 1
        if rem <= 1e-9: why = 'target'; xbar = j; rem = 0; break
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        best = max(best, (cl - entry) * s / r)
        if n_hit and j < last:
            if rat[0] == 'chand': ns = hic - s * rat[1] * at[j]
            elif rat[0] == 'lag': ns = entry + s * (best - rat[1]) * r
            elif rat[0] == 'step': ns = entry + s * (int(best) - 1) * r if best >= 2 else stop
            else: ns = stop
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[last][3] - entry) * s
    lev = F.LEV[p][0] if s > 0 else F.LEV[p][1]
    info.update(xbar=xbar, why=why, hit=n_hit > 0, R_out=gross / r, mfe=mfe, mae=mae, pct=lev * gross / entry * 100 - F.LEGCOST, leg_risk=lev * r / entry * 100)
    return info

F._manage = manage
base = F.P()
def run(tr, st, rat, dd):
    SCH.update(tr=tr, st=st, rat=rat)
    T = F.trades(ds, dd, syms, base, ctx); a = F.account(ds, dd, T); s = F.stat(a)
    R = [t['R_out'] for t in T]
    return s, (sum(R) / len(R) if R else 0), len(T)
def show(tag, tr, st, rat):
    out = [run(tr, st, rat, d) for d in (H1, H2, days)]
    print(f"{tag:<44}" + ''.join(f" | {s['avg']:+.3f}%/d R{r:+.2f} {s['win']:2.0f}%w DD{s['mdd']:4.1f}" for s, r, n in out))
print(f"{'':<44} | H1 discovery 21-..24-03        | H2 confirmation 24-04..26-10   | whole 5y")
LIVE_TR = [(2.0, 1/3)]; 
show('LIVE: 1/3 at 2R, BE, chandelier 2 ATR', LIVE_TR, [0.0], ('chand', 2.0))
t3 = [(1.0, 1/3), (2.0, 1/3)]; s3 = [0.0, 1.0]
show('YOURS: 1/3@1R BE, 1/3@2R stop 1R, last: fixed 1R', t3, s3, ('fix',))
show('  last 1/3 ratchet: chandelier 1.5 ATR', t3, s3, ('chand', 1.5))
show('  last 1/3 ratchet: chandelier 2 ATR', t3, s3, ('chand', 2.0))
show('  last 1/3 ratchet: chandelier 3 ATR', t3, s3, ('chand', 3.0))
show('  last 1/3 ratchet: lag 1.0R behind best close', t3, s3, ('lag', 1.0))
show('  last 1/3 ratchet: lag 1.5R', t3, s3, ('lag', 1.5))
show('  last 1/3 ratchet: lag 2.0R', t3, s3, ('lag', 2.0))
show('  last 1/3 ratchet: step (floor R - 1)', t3, s3, ('step',))
print('-- other tranche layouts (last part uses chandelier 2 ATR)')
show('1/2@1R BE, rest chand 2', [(1.0, 0.5)], [0.0], ('chand', 2.0))
show('1/3@1R BE, 2/3 chand 2', [(1.0, 1/3)], [0.0], ('chand', 2.0))
show('1/3@1.5R BE, 2/3 chand 2', [(1.5, 1/3)], [0.0], ('chand', 2.0))
show('1/3@2R BE, 1/3@3R stop 1R, last chand 2', [(2.0, 1/3), (3.0, 1/3)], [0.0, 1.0], ('chand', 2.0))
show('1/3@1R stop -0.5R, 1/3@2R stop 1R, chand 2', t3, [-0.5, 1.0], ('chand', 2.0))
show('1/3@1R stop -0.5R, rest chand 2', [(1.0, 1/3)], [-0.5], ('chand', 2.0))
print('-- all-or-nothing reference')
show('all out at 1R (stop at original)', [(1.0, 1.0)], [0.0], ('fix',))
show('all out at 2R', [(2.0, 1.0)], [0.0], ('fix',))
show('no target: BE not used, chand 2 only after 1R', [(1.0, 0.0001)], [0.0], ('chand', 2.0))
