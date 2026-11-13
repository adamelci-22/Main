#!/usr/bin/env python3
"""System 4 (governor 2026-11-13): a stock scanner day-trading system - "trade any stock, scan for the best opportunity using signals,
charts and news". Research only. Data: tools/backtest/scan_download.py (Massive): every trading day 2025-10-30..2026-11-12, the top
12 gap-ups (>= +2%) and top 6 gap-downs (<= -3%) by gap/ATR among US common stocks and ADRs (prior close >= $5, 20-day dollar volume
>= $30M), each with its 5-minute bars, premarket volume and the news published since the prior close (with the vendor's sentiment tag).
Long only (the account does not short). Signals are judged on a 5-minute CLOSE and filled at the next bar's open, the way the live
agent works its slots. Cost 0.20% a round trip (stock spread + slip). Nothing overnight: out at the 15:55 open (or 13:30 where said).
Method: TRAIN = first half of the days (pick the entry, the filter and the ranking there), TEST = second half (judged there).
Entries tested:
  ORB5     first 5-minute candle green, a close above its high inside the first hour -> buy, stop at the candle low   (stocks in play)
  ORB30    a close above the 9:30-10:00 high before 11:30 -> buy, stop at the box middle
  PBK      breakout close above the 9:30-9:45 high, then a 2-5 bar dip, then a close above the prior bar's high -> buy, stop under the dip
  R2G      red to green: >= 1 ATR-fraction under the open, then a close back above the open -> buy, stop at the day's low
  VWAPH    10:00: above VWAP and above the open -> buy, stop at the day's low, exit on a close below VWAP
  FADEL    FADE long side: close under the 9:30-10:00 low, first retest closes back inside -> buy, stop under the extreme
  OPENBUY  buy the 9:35 open, stop 1 ATR (daily) under it - the plain bounce
  WASHOUT  a new low >= 0.5 daily ATR under the open, then a close above the prior bar's high -> buy, stop at the low
  HOD      after 10:30: a close above the high of the day so far -> buy, stop at VWAP
    python3 -I tools/backtest/scan_bt.py SCAN_JSON_GZ > tools/backtest/results/scan_bt_2026-11-13.txt"""
import gzip, itertools, json, os, pickle, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, new_systems as NS
END = 77; NOON = 48; COST = 0.20; mg = NS.mg


def grid(raw):
    """78 five-minute slots from 9:30; a missing slot repeats the prior close with zero volume. None if the open bar is missing."""
    m = {int(x[0]): x[1:] for x in raw or []}
    if 570 not in m: return None
    out = []; pc = m[570][0]
    for j in range(78):
        x = m.get(570 + 5 * j)
        if x is None: out.append((pc, pc, pc, pc, 0.0))
        else: out.append(tuple(x)); pc = x[3]
    return out


def vwap(b): return NS.vwap(b)


def rec(c, k, x, e, g, r, tag): return dict(day=c['day'], T=c['T'], k=k, xbar=x, pct=g / e * 100 - COST, risk=max(r / e * 100, 0.2), R=(g / r if r else 0), sys=tag, f=c['f'])


def orb5(c, b, last=END, stop='candle', z=12):
    o, h, l, cl, v = b[0]
    if cl <= o: return None
    for j in range(1, z):
        if b[j][3] > h:
            k = j + 1; e = b[k][0]; s_ = l if stop == 'candle' else e - float(stop) * c['atr$']
            if s_ >= e: return None
            s_ = e - max(e - s_, 0.003 * e); x, g, r = mg(b, k, 1, e, s_, last); return rec(c, k, x, e, g, r, 'ORB5')
    return None


def orb30(c, b, last=END, z=24):
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6]); mid = (H + L) / 2
    for j in range(6, z):
        if b[j][3] > H:
            k = j + 1; e = b[k][0]; s_ = e - max(e - mid, 0.003 * e); x, g, r = mg(b, k, 1, e, s_, last); return rec(c, k, x, e, g, r, 'ORB30')
    return None


def pbk(c, b, last=END, z=42, runner=True):
    H = max(x[1] for x in b[:3]); vw = vwap(b); j = 3; brk = None
    while j < z:
        if brk is None:
            if b[j][3] > H and b[j][4] >= 1.3 * st.mean(x[4] for x in b[:j]): brk = j
        else:
            hi = max(x[1] for x in b[brk:j]); dip = [q for q in range(brk + 1, j) if b[q][1] < hi or b[q][3] < b[q - 1][3]]
            n = j - brk - 1
            if n > 6: brk = None; H = max(x[1] for x in b[:j]); j += 1; continue
            if 2 <= n <= 5 and b[j][3] > b[j - 1][1] and min(x[2] for x in b[brk + 1:j]) < b[brk][3]:
                k = j + 1; e = b[k][0]; lo = min(x[2] for x in b[brk + 1:j + 1]); s_ = e - max(e - lo * 0.9995, 0.0075 * e); T = max(x[1] for x in b[:j + 1])
                if T <= e * 1.003: T = None
                if runner and T:
                    P_R = (T - e) / (e - s_); x, g, r = mg(b, k, 1, e, s_, last, tpR=P_R, frac=1 / 3, out_fn=lambda jj: b[jj][3] < vw[jj])
                else: x, g, r = mg(b, k, 1, e, s_, last, T=T)
                return rec(c, k, x, e, g, r, 'PBK')
        j += 1
    return None


def r2g(c, b, last=END, depth=0.25, z=36):
    o0 = b[0][0]; lo = o0; armed = False
    for j in range(0, z):
        lo = min(lo, b[j][2])
        if o0 - lo >= depth * c['atr$']: armed = True
        if armed and j >= 1 and b[j][3] > o0 and b[j - 1][3] <= o0:
            k = j + 1; e = b[k][0]; s_ = e - max(e - lo, 0.003 * e); x, g, r = mg(b, k, 1, e, s_, last); return rec(c, k, x, e, g, r, 'R2G')
    return None


def vwaph(c, b, last=END, kb=6):
    vw = vwap(b)
    if not (b[kb - 1][3] > vw[kb - 1] and b[kb - 1][3] > b[0][0]): return None
    e = b[kb][0]; lo = min(x[2] for x in b[:kb]); s_ = e - max(e - lo, 0.003 * e)
    x, g, r = mg(b, kb, 1, e, s_, last, out_fn=lambda jj: b[jj][3] < vw[jj]); return rec(c, kb, x, e, g, r, 'VWAPH')


def fadel(c, b, last=END, nb=2, floor=0.15):
    L = min(x[2] for x in b[:6]); at = F.atr_arr(b)
    for j in range(6, 6 + nb):
        if b[j][3] < L:
            ext = b[j][2]
            for q in range(j + 1, min(j + 13, last - 1)):
                ext = min(ext, b[q][2])
                if b[q][1] >= L * 0.999:
                    if b[q][3] <= L: return None
                    k = q + 1; e = b[k][0]; r = max(e - ext, floor * c['atr$'])
                    x, g, r = mg(b, k, 1, e, e - r, last, at=at, tpR=2.0, chand=2.0); return rec(c, k, x, e, g, r, 'FADEL')
            return None
    return None


def hod(c, b, last=END, a=12, z=54):
    vw = vwap(b); H = max(x[1] for x in b[:a])
    for j in range(a, z):
        if b[j][3] > H:
            k = j + 1; e = b[k][0]; s_ = e - max(e - vw[j], 0.004 * e)
            x, g, r = mg(b, k, 1, e, s_, last, out_fn=lambda jj: b[jj][3] < vw[jj]); return rec(c, k, x, e, g, r, 'HOD')
        H = max(H, b[j][1])
    return None


def openbuy(c, b, last=END, stop=1.0, kb=1):
    e = b[kb][0]; x, g, r = mg(b, kb, 1, e, e - stop * c['atr$'], last); return rec(c, kb, x, e, g, r, 'OPENBUY')


def washout(c, b, last=END, z=24, depth=0.5):
    """Gap-down washout: a new low >= depth x ATR under the open, then the first 5-minute close above the prior bar's high -> buy."""
    o0 = b[0][0]; lo = o0
    for j in range(0, z):
        lo = min(lo, b[j][2])
        if j >= 1 and o0 - lo >= depth * c['atr$'] and b[j][3] > b[j - 1][1]:
            k = j + 1; e = b[k][0]; s_ = e - max(e - lo, 0.003 * e); x, g, r = mg(b, k, 1, e, s_, last); return rec(c, k, x, e, g, r, 'WASH')
    return None


ENT = [('OPENBUY 9:35 stop 1 ATR', openbuy, {}), ('OPENBUY stop 0.5 ATR', openbuy, dict(stop=0.5)), ('OPENBUY out 13:30', openbuy, dict(last=NOON)), ('OPENBUY 10:00', openbuy, dict(kb=6)), ('WASHOUT', washout, {}), ('WASHOUT 0.25', washout, dict(depth=0.25)),
       ('ORB5', orb5, {}), ('ORB5 atr stop 0.10', orb5, dict(stop='0.10')), ('ORB5 out 13:30', orb5, dict(last=NOON)), ('ORB30', orb30, {}), ('PBK runner', pbk, {}), ('PBK target', pbk, dict(runner=False)),
       ('PBK runner 13:30', pbk, dict(last=NOON)), ('R2G', r2g, {}), ('R2G deep 0.5', r2g, dict(depth=0.5)), ('VWAPH', vwaph, {}), ('VWAPH 10:30', vwaph, dict(kb=12)), ('FADEL', fadel, {}), ('FADEL 13:30', fadel, dict(last=NOON)), ('HOD', hod, {})]
FILT = [('all', lambda f: True), ('gap up', lambda f: f['gap'] > 0), ('gap down', lambda f: f['gap'] < 0), ('news', lambda f: f['news'] > 0), ('no news', lambda f: f['news'] == 0), ('news positive', lambda f: f['pos'] > 0 and f['neg'] == 0),
        ('news negative', lambda f: f['neg'] > 0), ('up + news', lambda f: f['gap'] > 0 and f['news'] > 0), ('up + news pos', lambda f: f['gap'] > 0 and f['pos'] > 0 and f['neg'] == 0), ('up no news', lambda f: f['gap'] > 0 and f['news'] == 0),
        ('up rv5 >= 8', lambda f: f['gap'] > 0 and f['rv5'] >= 8), ('up rv5 >= 15', lambda f: f['gap'] > 0 and f['rv5'] >= 15), ('up rv5 < 8', lambda f: f['gap'] > 0 and f['rv5'] < 8), ('up pm >= 5%', lambda f: f['gap'] > 0 and f['pmrv'] >= 0.05),
        ('up pm >= 20%', lambda f: f['gap'] > 0 and f['pmrv'] >= 0.2), ('up gap >= 6%', lambda f: f['gap'] >= 6), ('up gap < 6%', lambda f: 0 < f['gap'] < 6), ('up gap/ATR >= 2', lambda f: f['gap'] > 0 and f['gapatr'] >= 2), ('up price >= 20', lambda f: f['gap'] > 0 and f['px'] >= 20),
        ('up adv >= 200M', lambda f: f['gap'] > 0 and f['adv'] >= 2e8), ('up, SPY gap up', lambda f: f['gap'] > 0 and f['spy'] > 0), ('up, SPY gap down', lambda f: f['gap'] > 0 and f['spy'] <= 0), ('up 1st bar strong', lambda f: f['gap'] > 0 and f['b0'] >= 0.6),
        ('up top-3 gap/ATR', lambda f: f['gap'] > 0 and f['rank'] < 3), ('down + news', lambda f: f['gap'] < 0 and f['news'] > 0), ('down no news', lambda f: f['gap'] < 0 and f['news'] == 0), ('down rv5 >= 8', lambda f: f['gap'] < 0 and f['rv5'] >= 8),
        ('down gap <= -6%', lambda f: f['gap'] <= -6), ('down gap > -6%', lambda f: -6 < f['gap'] < 0), ('down gap/ATR >= 2', lambda f: f['gap'] < 0 and f['gapatr'] >= 2), ('down price >= 20', lambda f: f['gap'] < 0 and f['px'] >= 20),
        ('down adv >= 200M', lambda f: f['gap'] < 0 and f['adv'] >= 2e8), ('down, SPY gap up', lambda f: f['gap'] < 0 and f['spy'] > 0), ('down, SPY gap down', lambda f: f['gap'] < 0 and f['spy'] <= 0), ('down news negative', lambda f: f['gap'] < 0 and f['neg'] > 0),
        ('down 1st bar strong', lambda f: f['gap'] < 0 and f['b0'] >= 0.6), ('down pm >= 5%', lambda f: f['gap'] < 0 and f['pmrv'] >= 0.05)]


def load(path):
    z = json.load(gzip.open(path)); days = z['days']; out = {}
    for d in days:
        m = z['meta'][d]; spy = (m['spy'][0] / m['spy_prev'][3] - 1) * 100 if m.get('spy') and m.get('spy_prev') else 0.0; L = []
        ups = sorted([c for c in z['cands'][d] if c['gap'] > 0], key=lambda c: -c['gap'] / c['atrp']); rk = {c['T']: i for i, c in enumerate(ups)}
        for c in z['cands'][d]:
            b = grid(c['bars'])
            if not b or c['advsh'] <= 0: continue
            nw = c['news'] or []; o, h, l, cl, v = b[0]
            c2 = dict(day=d, T=c['T'], b=b, **{'atr$': c['atrp'] / 100 * c['pc']})
            c2['f'] = dict(gap=c['gap'], gapatr=abs(c['gap']) / c['atrp'], atrp=c['atrp'], adv=c['adv'], px=c['o'], pmrv=(c['pm'][0] / c['advsh']) if c['pm'] else 0.0, rv5=v / (c['advsh'] / 78), news=len(nw),
                           pos=sum(x[2] == 'positive' for x in nw), neg=sum(x[2] == 'negative' for x in nw), spy=spy, b0=((cl - l) / (h - l) if h > l else 0.5), rank=rk.get(c['T'], 99))
            L.append(c2)
        out[d] = L
    return days, out


def stat(T):
    if not T: return None
    p = [t['pct'] for t in T]; gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
    return len(p), 100 * sum(x > 0 for x in p) / len(p), st.mean(p), gw / gl if gl else 9.0


def account(days, T, score, risk=3.0, cap=3):
    by = {}
    for t in T: by.setdefault(t['day'], []).append(t)
    daily = []; tk = []
    for d in days:
        cs = sorted(by.get(d, []), key=lambda t: (t['k'], -score(t['f']))); free = 0; eq = 1.0; n = 0
        for t in cs:
            if n >= cap: break
            if t['k'] < free: continue
            f = min(1.0, risk / t['risk']); eq *= 1 + f * t['pct'] / 100; free = t['xbar'] + 1; n += 1; tk.append(dict(t, w=f, acct=f * t['pct']))
        daily.append((eq - 1) * 100)
    return np.array(daily), tk


def curve(r):
    lg = np.log1p(np.array(r) / 100); cum = np.cumsum(lg); dd = 1 - np.exp(cum - np.maximum.accumulate(np.concatenate([[0], cum]))[1:])
    return float(np.expm1(cum[-1]) * 100) if len(r) else 0.0, float(dd.max() * 100) if len(r) else 0.0


def main():
    days, C = load(sys.argv[1]); h = len(days) // 2; TR, TE = set(days[:h]), set(days[h:])
    allc = [c for d in days for c in C[d]]
    print(__doc__.split('\n')[0]); print(f"days {days[0]}..{days[-1]} ({len(days)}); TRAIN ..{days[h - 1]}, TEST {days[h]}..; {len(allc)} stock-days, {sum(c['f']['news'] > 0 for c in allc)} with news; cost {COST:.2f}% a round trip\n")
    base = [np.mean([(c['b'][76][3] / c['b'][0][0] - 1) * 100 for c in allc if (c['f']['gap'] > 0) == up]) for up in (True, False)]
    print(f"baseline, open to 15:55, no cost: gap-ups {base[0]:+.2f}% a stock-day, gap-downs {base[1]:+.2f}%\n")
    TT = {}
    print('PER-TRADE EDGE by entry and filter (every signal taken): n, win %, average net %, profit factor.  TRAIN | TEST')
    cells = []
    for en, fn, kw in ENT:
        T = [t for c in allc for t in [fn(c, c['b'], **kw)] if t]; TT[en] = T
        for fname, ff in FILT:
            a = stat([t for t in T if t['day'] in TR and ff(t['f'])]); b = stat([t for t in T if t['day'] in TE and ff(t['f'])])
            if a and b and a[0] >= 40 and b[0] >= 40: cells.append((en, fname, a, b))
    for en, _, _ in ENT:
        print(f"  {en}")
        for e2, fname, a, b in cells:
            if e2 == en and (fname in ('all', 'gap up', 'gap down', 'up + news', 'up no news', 'down + news', 'down no news') or (a[3] >= 1.15 and a[2] > 0)):
                print(f"     {'KEEP' if a[3] >= 1.15 and b[3] >= 1.15 else '    '} {fname:<18} n{a[0]:5d} w{a[1]:3.0f}% {a[2]:+.2f}% PF{a[3]:5.2f} | n{b[0]:5d} w{b[1]:3.0f}% {b[2]:+.2f}% PF{b[3]:5.2f}")
    good = [x for x in cells if x[2][3] >= 1.15 and x[2][2] > 0]; held = [x for x in good if x[3][3] >= 1.15 and x[3][2] > 0]; pos = [x for x in good if x[3][2] > 0]
    print(f"\nPERSISTENCE: {len(cells)} entry x filter cells with >= 40 trades in each half; {len(good)} had TRAIN PF >= 1.15; of those {len(pos)} stayed positive on TEST and {len(held)} kept PF >= 1.15")
    print(f"   all cells: TRAIN mean PF {np.mean([x[2][3] for x in cells]):.2f}, TEST mean PF {np.mean([x[3][3] for x in cells]):.2f}; correlation of TRAIN and TEST average net % across cells {np.corrcoef([x[2][2] for x in cells], [x[3][2] for x in cells])[0, 1]:+.2f}")
    pickle.dump(dict(TT=TT, days=days, h=h, cells=cells), open(os.path.join(os.path.dirname(sys.argv[1]), 'scan_bt.pkl'), 'wb'))
    # the system: best TRAIN cell (by average net % x sqrt(n), PF >= 1.15), ranked by rv5 when two signals collide; account on TEST
    print('\nACCOUNT (3% risk a trade capped at cash, one position at a time, 3 entries a day, earliest signal first, ties to the higher first-bar relative volume)')
    ranked = sorted(good, key=lambda x: -x[2][2] * x[2][0] ** 0.5)
    for en, fname, a, b in ranked[:12]:
        ff = dict(FILT)[fname]; T = [t for t in TT[en] if ff(t['f'])]
        r1, t1 = account(days[:h], [t for t in T if t['day'] in TR], lambda f: f['rv5']); r2, t2 = account(days[h:], [t for t in T if t['day'] in TE], lambda f: f['rv5'])
        c1 = curve(r1); c2 = curve(r2); s2 = stat(t2)
        print(f"   {en:<18} {fname:<18} TRAIN {c1[0]:+7.1f}% DD {c1[1]:4.1f} n{len(t1):4d} | TEST {c2[0]:+7.1f}% DD {c2[1]:4.1f} n{len(t2):4d} w{s2[1]:3.0f}% avg {s2[2]:+.2f}% PF{s2[3]:5.2f}")


if __name__ == '__main__':
    main()
