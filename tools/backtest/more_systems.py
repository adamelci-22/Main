#!/usr/bin/env python3
"""More practitioner systems as a possible third system (governor 2026-11-12: "deep dive, other systems people use").
Same data and constraints as other_systems.py / afternoon_systems.py: proxies QQQ SOXX IWM XLK XBI XLF SPY, 3x leg, cost 0.06%,
one proxy-day <= one trade, nothing overnight. MORNING versions run 10:00-13:30 and are judged ALONE and SHARED with the live book;
AFTERNOON versions run 13:30-15:55 and add to the book with no interference (the book is flat by 13:30).
  NR7ORB   Crabel: 30-min ORB continuation only after an NR7 day (narrowest daily range of the last 7)
  RELVAL   sector vs QQQ relative-value reversion: a sector that lags/leads QQQ by >= x% since the open (and >= 2.5 sd of its
           20-day daily relative move) is bought/sold toward QQQ, target half the gap closed, stop 1 gap further
  RSI2     Connors-style RSI(2) on 15-minute closes: < 5 buy, > 95 sell, exit when RSI(2) crosses 50 or out
  CLIMAX   volume climax reversal: a 5-min bar >= 3x the 20-bar average volume, range >= 2 ATR, closing in its opposite third -> fade
  BOLL     Bollinger(20, 2.5 sd) on 5-min closes: close outside the band fades back to the middle
  LEADER   relative strength: at 11:00 buy the leg of the proxy with the biggest move from the open in the direction of QQQ's move
    python3 -I tools/backtest/more_systems.py > tools/backtest/results/more_systems_2026-11-12.txt"""
import os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, other_systems as OS, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PX = OS.PX
def run(b, k, s, e, stop, last, T=None, out_fn=None):
    for j in range(k, last + 1):
        o, h, l, c, v = b[j]; adv = l if s > 0 else h; fav = h if s > 0 else l
        if (adv - stop) * s <= 0: return j, ((stop if (o - stop) * s >= 0 else o) - e) * s
        if T is not None and (fav - T) * s >= 0: return j, ((T if (o - T) * s <= 0 else o) - e) * s
        if j == last: return j, (c - e) * s
        if out_fn and out_fn(j): return j + 1, (b[j + 1][0] - e) * s
    return last, (b[last][3] - e) * s
def fin(d, p, k, x, e, g, r): return dict(day=d, proxy=p, k=k, xbar=x, R_out=g / r if r else 0, pct=3 * g / e * 100 - F.LEGCOST, leg_risk=3 * r / e * 100 if r else 3.0)
def W(pm): return (47, 75) if pm else (6, 46)          # entry bar window (inclusive start, exclusive end); exit bar = 47 or 76
def LAST(pm): return 76 if pm else 47
def nr7orb(ds, ctx, p, d, b, pm=False):
    i = ds.idx[d]; prior = [ds.bars[p].get(x) for x in ds.days[max(0, i - 7):i]]
    if len(prior) < 7 or any(x is None for x in prior): return None
    rg = [max(y[1] for y in x) - min(y[2] for y in x) for x in prior]
    if rg[-1] > min(rg): return None
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6]); mid = (H + L) / 2
    for j in range(6, 42):
        c = b[j][3]; s = 1 if c > H else -1 if c < L else 0
        if s:
            k = j + 1; e = b[k][0]
            if (e - mid) * s <= 0: return None
            x, g = run(b, k, s, e, mid, 47, T=e + s * 2 * abs(e - mid)); return fin(d, p, k, x, e, g, abs(e - mid))
    return None
_rel = {}
def relval(ds, ctx, p, d, b, pm=False, xm=0.5):
    if p == 'QQQ': return None
    q = ds.bars['QQQ'].get(d)
    if not q: return None
    key = (id(ds), p)
    if key not in _rel:
        _rel[key] = {x: (ds.bars[p][x][-1][3] / ds.bars[p][x][0][0] - ds.bars['QQQ'][x][-1][3] / ds.bars['QQQ'][x][0][0]) for x in ds.days if x in ds.bars[p] and x in ds.bars['QQQ']}
    i = ds.idx[d]; hist = [_rel[key][x] for x in ds.days[max(0, i - 20):i] if x in _rel[key]]
    if len(hist) < 15: return None
    sd = st.pstdev(hist) or 1e-9; a, z = W(pm)
    for j in range(a, z):
        rp = b[j][3] / b[0][0] - q[j][3] / q[0][0]
        if abs(rp) * 100 >= xm and abs(rp) >= 2.5 * sd:
            s = -1 if rp > 0 else 1; k = j + 1; e = b[k][0]; gap = abs(rp) * e
            x, g = run(b, k, s, e, e - s * gap, LAST(pm), T=e + s * gap / 2); return fin(d, p, k, x, e, g, gap)
    return None
def rsi(cs, n=2):
    out = [50.0] * len(cs); ag = al = 0.0
    for i in range(1, len(cs)):
        ch = cs[i] - cs[i - 1]; g, l = max(ch, 0), max(-ch, 0)
        if i <= n: ag += g / n; al += l / n
        else: ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out
def rsi2(ds, ctx, p, d, b, pm=False):
    c15 = [b[j][3] for j in range(2, 78, 3)]; r = rsi(c15); a, z = W(pm)
    for q in range(len(c15)):
        j = 2 + 3 * q
        if j < a or j >= z: continue
        s = 1 if r[q] < 5 else -1 if r[q] > 95 else 0
        if s:
            k = j + 1; e = b[k][0]; stop = e - s * 2 * ctx['atr'][p][d][j]
            def out_fn(jj, s=s):
                if (jj - 2) % 3: return False
                qq = (jj - 2) // 3; return (r[qq] - 50) * s > 0
            x, g = run(b, k, s, e, stop, LAST(pm), out_fn=out_fn); return fin(d, p, k, x, e, g, abs(e - stop))
    return None
def climax(ds, ctx, p, d, b, pm=False):
    at = ctx['atr'][p][d]; a, z = W(pm)
    for j in range(max(a, 20), z):
        o, h, l, c, v = b[j]; av = st.mean(x[4] for x in b[j - 20:j]) or 1; rng = h - l
        if v < 3 * av or rng < 2 * at[j] or rng <= 0: continue
        pos = (c - l) / rng; dn = c < o
        s = 1 if (dn and pos >= 0.67) else -1 if ((not dn) and pos <= 0.33) else 0
        if s:
            k = j + 1; e = b[k][0]; stop = (l if s > 0 else h) - s * 0.1 * at[j]
            if (e - stop) * s <= 0: continue
            x, g = run(b, k, s, e, stop, LAST(pm), T=e + s * 1.5 * abs(e - stop)); return fin(d, p, k, x, e, g, abs(e - stop))
    return None
def boll(ds, ctx, p, d, b, pm=False):
    cs = [x[3] for x in b]; a, z = W(pm)
    for j in range(max(a, 20), z):
        w = cs[j - 19:j + 1]; m = st.mean(w); sd = st.pstdev(w)
        if sd <= 0: continue
        s = -1 if cs[j] > m + 2.5 * sd else 1 if cs[j] < m - 2.5 * sd else 0
        if s:
            k = j + 1; e = b[k][0]; stop = e - s * 1.5 * sd * 2.5 / 2.5
            x, g = run(b, k, s, e, e - s * 2.5 * sd, LAST(pm), T=m); return fin(d, p, k, x, e, g, 2.5 * sd)
    return None
_lead = {}
def leader(ds, ctx, p, d, b, pm=False):
    key = (id(ds), d)
    if key not in _lead:
        q = ds.bars['QQQ'].get(d); best = None
        if q:
            qs = 1 if q[17][3] > q[0][0] else -1
            for x in PX:
                bx = ds.bars[x].get(d)
                if not bx: continue
                m = (bx[17][3] / bx[0][0] - 1) * qs
                if best is None or m > best[0]: best = (m, x, qs)
        _lead[key] = best
    best = _lead[key]
    if not best or best[1] != p or best[0] <= 0.3 / 100: return None
    s = best[2]; k = 18; e = b[k][0]; stop = e - s * 2 * ctx['atr'][p][d][17]
    x, g = run(b, k, s, e, stop, 47); return fin(d, p, k, x, e, g, abs(e - stop))
SYS = [('NR7ORB (morning)', nr7orb, False), ('RELVAL morning', relval, False), ('RELVAL afternoon', relval, True),
       ('RSI2 morning', rsi2, False), ('RSI2 afternoon', rsi2, True), ('CLIMAX morning', climax, False), ('CLIMAX afternoon', climax, True),
       ('BOLL morning', boll, False), ('BOLL afternoon', boll, True), ('LEADER at 11:00', leader, False)]
def curve(d):
    eq = pk = 1.0; mdd = 0.0
    for x in d: eq *= 1 + x / 100; pk = max(pk, eq); mdd = max(mdd, (pk - eq) / pk * 100)
    return (eq - 1) * 100, mdd
def main():
    FB = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); RUN = dict(frac=1 / 3, run=('ema', 20))
    ds_rh = F.DS(None, PX + PS.LEGS_RH); cx_rh = F.context(ds_rh, PX); dm = F.DS(OS.AE.M5, PX + PS.LEGS_M); cm = F.context(dm, PX); H = [(ds_rh, cx_rh), (dm, cm), (dm, cm)]
    bookT = [[FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, RUN) for t in PB[b].E] for b in range(3)]
    book = [F.account(PB[b].ds, PB[b].days, bookT[b])['daily'] for b in range(3)]
    names = ['RH 2026', 'M H1 21-24', 'M H2 24-26']
    print(__doc__.split('\n')[0])
    print('per block: ALONE n, win, avg leg %, PF, total | WITH BOOK total (change vs book alone) DD.  Morning = shared account; afternoon = compounded after 13:30')
    for name, fn, pm in SYS:
        cells = []; ok = True
        for b in range(3):
            d_, c_ = H[b]; days = PB[b].days
            T = [x for p in PX if p in d_.bars for d in days if d in d_.bars[p] for x in [fn(d_, c_, p, d, d_.bars[p][d], pm=pm)] if x]
            if not T: cells.append(f"{names[b]} no trades"); ok = False; continue
            a = F.account(d_, days, T); tk = a['taken']
            g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
            bk = curve([book[b].get(d, 0.0) for d in days])
            if pm: cmb = curve([((1 + book[b].get(d, 0.0) / 100) * (1 + a['daily'].get(d, 0.0) / 100) - 1) * 100 for d in days])
            else:
                sh = F.account(d_, days, bookT[b] + T); cmb = curve([sh['daily'].get(d, 0.0) for d in days])
            ok &= cmb[0] > bk[0]
            cells.append(f"{names[b]} n{len(tk):4d} w{100*sum(x['acct'] > 0 for x in tk)/len(tk):3.0f}% {st.mean(x['pct'] for x in tk):+.2f}% PF{(g/l if l else 9):4.2f} {a['ret']:+7.1f}% | +BOOK {cmb[0]:+7.1f}% ({cmb[0] - bk[0]:+6.1f}) DD{cmb[1]:5.1f}")
        print(f"  {'PASS ' if ok else '     '}{name:<20} " + ' || '.join(cells))
if __name__ == '__main__':
    main()
