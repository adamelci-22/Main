#!/usr/bin/env python3
"""Backtest of "The Intraday Strategy Manual" systems on the same 5-minute ETF data (Core Five proxies and their ten 3x legs).
    python3 tools/backtest/manual.py > tools/backtest/results_manual.txt
Mode 'proxy': unlevered proxy ETFs, long AND short (mirror trick) - cleanest read of each signal.
Mode 'legs' : the ten 3x legs, long only (how the account would actually trade; inverse legs stand in for shorts).
Fills: signal on a completed bar -> entry at next bar's open (+cost); stops/targets intrabar, stop first when both are in one bar;
gaps fill at the open. Positions held to the 15:55 bar close unless the strategy exits earlier. Cost 0.03%/side.
"""
import math, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import get_data
from backtest import ROWS

CORE = ('QQQ', 'SPY', 'SOXX', 'IWM', 'TLT')
LEGS = {leg: (p, s) for p in CORE for leg, s in ((ROWS[p][0], 1), (ROWS[p][1], -1))}   # leg -> (proxy, direction)
COST = 0.0003
LAST = 77


def ema(vals, n):
    k = 2 / (n + 1); out = []; e = None
    for v in vals:
        e = v if e is None else e + k * (v - e)
        out.append(e)
    return out


def mirror(b):
    p0 = b[0][0]
    return [(2 * p0 - o, 2 * p0 - l, 2 * p0 - h, 2 * p0 - c, v) for (o, h, l, c, v) in b], p0


def atr(b, j, n=14):
    trs = []
    for i in range(max(1, j - n + 1), j + 1):
        trs.append(max(b[i][1] - b[i][2], abs(b[i][1] - b[i - 1][3]), abs(b[i][2] - b[i - 1][3])))
    return st.mean(trs) if trs else 0.0


def vwap_sd(b, upto):
    sv = svt = svt2 = 0.0
    for i in range(upto + 1):
        tp = (b[i][1] + b[i][2] + b[i][3]) / 3; v = b[i][4]
        sv += v; svt += v * tp; svt2 += v * tp * tp
    if sv <= 0: return b[upto][3], 0.0
    vw = svt / sv
    return vw, math.sqrt(max(svt2 / sv - vw * vw, 0.0))


# ---------------------------------------------------------------- strategies: return a spec or None
# spec: k (entry bar), entry (price before cost), stop, T (target or None), frac (share sold at T), post ('be'|'ema9'|'ema20'|None)
def s1_orb(b, e9, e20, gap, gapmin):
    if gapmin and abs(gap) < gapmin: return None
    bh = max(x[1] for x in b[:3]); bl = min(x[2] for x in b[:3]); h = bh - bl
    if h <= 0: return None
    for j in range(3, 29):
        if b[j][3] > bh:
            entry = b[j + 1][0]; stop = max((bh + bl) / 2, b[j][2])
            if entry <= stop: return None
            return dict(k=j + 1, entry=entry, stop=stop, T=entry + h, frac=0.5, post='ema9', ema=e9)
    return None


def s2_pullback(b, e9, e20):
    bh = max(x[1] for x in b[:3])
    for j in range(8, 41):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[m][4] for m in range(max(0, i - 6), i) or [0]) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre))
            entry = b[j + 1][0]; stop = low - 0.025
            if hod <= entry or entry <= stop: continue
            return dict(k=j + 1, entry=entry, stop=stop, T=hod, frac=0.6, post='ema20', ema=e20)
    return None


def s3_vwap_trend(b):
    for j in range(12, 61):
        vw, sd = vwap_sd(b, j)
        if sum(1 for i in range(j - 8, j) if b[i][3] > vwap_sd(b, i)[0]) < 6: continue
        o, h, l, c, v = b[j]
        rng = h - l
        if rng <= 0 or l > vw * 1.0005 or c <= vw or c <= o: continue
        if (min(o, c) - l) < 0.5 * rng: continue
        if v >= st.mean(b[i][4] for i in range(j - 3, j)): continue
        a = atr(b, j); entry = b[j + 1][0]; stop = vw - a
        if a <= 0 or entry <= stop: continue
        return dict(k=j + 1, entry=entry, stop=stop, T=entry + 2 * (entry - stop), frac=1.0, post=None)
    return None


def s3_vwap_fade(b):
    for j in range(12, 70):
        vw, sd = vwap_sd(b, j)
        if sd <= 0: continue
        o, h, l, c, v = b[j]; rng = h - l
        if rng <= 0 or l > vw - 2 * sd: continue
        if (min(o, c) - l) < 0.5 * rng or c <= o: continue
        if v < 1.5 * st.mean(b[i][4] for i in range(max(0, j - 6), j)): continue
        entry = c; stop = l - 0.02
        if vw <= entry or entry <= stop: continue
        return dict(k=j + 1, entry=entry, stop=stop, T=vw, frac=1.0, post=None, at_close=True)
    return None


def s4_two_bar(b):
    bh = max(x[1] for x in b[:6]); stop = min(x[2] for x in b[3:6])
    for j in range(6, 9):
        if b[j][1] >= bh:
            entry = max(b[j][0], bh)
            if entry <= stop: return None
            return dict(k=j, entry=entry, stop=stop, T=entry + (entry - stop), frac=0.5, post='be', stop_entry=True)
    return None


def s5_parabolic(b, daygain_min):
    """Adapted for ETFs (no +50% days exist): leg up >= daygain_min on the day, RSI14 > 80, volume spike, 14:00-15:30. Short only (proxy mode mirror)."""
    closes = [x[3] for x in b]
    for j in range(54, 67):
        if closes[j] / b[0][0] - 1 < daygain_min: continue
        gains = [max(closes[i] - closes[i - 1], 0) for i in range(j - 13, j + 1)]; loss = [max(closes[i - 1] - closes[i], 0) for i in range(j - 13, j + 1)]
        ag, al = st.mean(gains), st.mean(loss)
        rsi = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        if rsi <= 80: continue
        if b[j][4] < 2 * st.mean(b[i][4] for i in range(j - 6, j)): continue
        # blow-off bar = j; trigger: a later bar closing below its low
        for m in range(j + 1, min(j + 4, 72)):
            if b[m][3] < b[j][2]:
                hod = max(x[1] for x in b[:m + 1]); entry = b[m + 1][0]
                lo_move = (hod - b[0][0])
                if hod <= entry: break
                return dict(k=m + 1, entry=entry, stop=hod + 0.02, T=hod - 0.5 * (hod - b[0][0]), frac=1.0, post=None, short=True)
    return None


# ---------------------------------------------------------------- trade management (long-only in the mirrored space)
def manage(b, spec, ema_arr, cost, orig):
    """orig(p) maps a (possibly mirrored) price back to the real price. Returns (pnl_per_share_net, risk_per_share, exit_bar, why, entry_fill)."""
    k, entry, stop, T, frac, post = spec['k'], spec['entry'], spec['stop'], spec.get('T'), spec.get('frac', 1.0), spec.get('post')
    risk = entry - stop
    if risk <= 0: return None
    start = k
    rem = 1.0; gross = 0.0; cost_tot = cost * orig(entry); hit = False; why = 'eod'; xbar = LAST
    def sell(price, f):
        nonlocal gross, cost_tot, rem
        gross += f * (price - entry); cost_tot += f * cost * orig(price); rem -= f
    for j in range(start, LAST + 1):
        o, h, l, c, v = b[j]
        if l <= stop and not (spec.get('stop_entry') and j == k and False):
            sell(min(stop, o), rem); why = 'stop'; xbar = j; break
        if T is not None and not hit and h >= T:
            sell(max(T, o), frac if frac < 1 else rem); hit = True
            if rem <= 1e-9: why = 'target'; xbar = j; break
            if post == 'be': stop = max(stop, entry)
        if post in ('ema9', 'ema20') and hit and c < ema_arr[j] and j < LAST:
            sell(b[j + 1][0], rem); why = 'trail'; xbar = j + 1; break
        if j == LAST:
            sell(c, rem); why = 'eod'; xbar = j
    if rem > 1e-9: sell(b[LAST][3], rem)
    return gross - cost_tot, risk, xbar, why


def gen_signals(strategy, mode, D, days, variant=None):
    out = []   # dict(day, inst, k, pnl_ps, risk, entry_orig, why, ...)
    syms = list(CORE) if mode == 'proxy' else list(LEGS)
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]
        for s in syms:
            sides = (1, -1) if mode == 'proxy' else (1,)
            for sd in sides:
                raw = D.bars[s][d]; prevraw = D.bars[s][pd_]
                if sd == -1:
                    b, p0 = mirror(raw); pb, _ = mirror(prevraw)
                    orig = lambda p, p0=p0: 2 * p0 - p
                else:
                    b, p0 = raw, raw[0][0]; pb = prevraw; orig = lambda p: p
                ser = [x[3] for x in pb] + [x[3] for x in b]
                e9 = ema(ser, 9)[78:]; e20 = ema(ser, 20)[78:]
                gap = (raw[0][0] / prevraw[LAST][3] - 1) * 100
                if strategy == 'S1 ORB (15-min box, 1x box target, EMA9 trail)': sp = s1_orb(b, e9, e20, gap, None)
                elif strategy == 'S1 ORB + gap filter (|gap|>%s%%)' % ('1' if mode == 'proxy' else '3'): sp = s1_orb(b, e9, e20, gap, 1.0 if mode == 'proxy' else 3.0)
                elif strategy == 'S2 First pullback buy': sp = s2_pullback(b, e9, e20)
                elif strategy == 'S3a VWAP trend (rejection wick, 2R)': sp = s3_vwap_trend(b)
                elif strategy == 'S3b VWAP fade (2 SD tail, to VWAP)': sp = s3_vwap_fade(b)
                elif strategy == 'S4 2-bar compressed ORB (30-min box)': sp = s4_two_bar(b)
                elif strategy == 'S5 Parabolic exhaustion short (adapted: +8% day)':
                    if mode != 'proxy' or sd != -1: sp = None   # short only; run on mirrored legs below
                    else: sp = None
                else: sp = None
                if not sp: continue
                ema_arr = sp.get('ema', e9)
                r = manage(b, sp, ema_arr, COST, orig)
                if not r: continue
                pnl, risk, xbar, why = r
                eo = orig(sp['entry'])
                out.append(dict(day=d, inst=s, side=sd, k=sp['k'], pnl=pnl, risk=risk, entry=eo, why=why, xbar=xbar,
                                pct=pnl / eo * 100, R=pnl / risk))
    return out


def summarize(sig):
    if not sig: return None
    n = len(sig); w = sum(1 for x in sig if x['pnl'] > 0)
    gw = sum(x['pct'] for x in sig if x['pnl'] > 0); gl = -sum(x['pct'] for x in sig if x['pnl'] <= 0)
    m = st.mean(x['pct'] for x in sig); sd = st.pstdev([x['pct'] for x in sig])
    return dict(n=n, win=100 * w / n, avg=m, t=m / (sd / math.sqrt(n)) if sd else 0, R=st.mean(x['R'] for x in sig), pf=gw / gl if gl else 99,
                tp=100 * sum(1 for x in sig if x['why'] == 'target') / n, stp=100 * sum(1 for x in sig if x['why'] == 'stop') / n,
                avgrisk=st.mean(x['risk'] / x['entry'] * 100 for x in sig))


# ---------------------------------------------------------------- account simulation (legs, long only, one position at a time)
def rvol(D, proxy, d, k):
    pri = D.prior(d, 20)
    base = st.mean(D.cum[proxy][x][k] for x in pri)
    return D.cum[proxy][d][k] / base if base else 0.0


def rel_str(D, leg, d, k):
    p, s = LEGS[leg]
    pb = D.bars[p][d]; sb = D.bars['SPY'][d]
    pc = (pb[k - 1][3] / pb[0][0] - 1) * 100; sc = (sb[k - 1][3] / sb[0][0] - 1) * 100
    return s * (pc - sc)


def account(sig, D, rank, seed=1, max_entries=3, risk=0.03, start=2000.0):
    rng = random.Random(seed)
    by = {}
    for x in sig: by.setdefault(x['day'], []).append(x)
    eq = start; peak = start; mdd = 0.0; trades = []
    for d in sorted(by):
        cands = sorted(by[d], key=lambda x: x['k']); free = 0; n = 0
        i = 0
        while i < len(cands) and n < max_entries:
            avail = [x for x in cands if x['k'] >= free]
            if not avail: break
            k0 = min(x['k'] for x in avail); same = [x for x in avail if x['k'] == k0]
            if rank == 'random': pick = rng.choice(same)
            elif rank == 'rvol': pick = max(same, key=lambda x: rvol(D, LEGS[x['inst']][0], d, x['k']))
            elif rank == 'rs': pick = max(same, key=lambda x: rel_str(D, x['inst'], d, x['k']))
            elif rank == 'rvol+rs':
                rv = sorted(same, key=lambda x: rvol(D, LEGS[x['inst']][0], d, x['k'])); rs = sorted(same, key=lambda x: rel_str(D, x['inst'], d, x['k']))
                pick = max(same, key=lambda x: rv.index(x) + rs.index(x))
            else: pick = same[0]
            sh = math.floor(min(eq / pick['entry'], eq * risk / pick['risk']))
            if sh >= 1:
                pnl = sh * pick['pnl']; eq += pnl; n += 1; trades.append(pnl)
                peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
            free = pick['xbar'] + 1; cands = [x for x in cands if x is not pick]
            i = 0
    return dict(ret=(eq / start - 1) * 100, trades=len(trades), mdd=mdd, win=100 * sum(1 for t in trades if t > 0) / len(trades) if trades else 0)


STRATS = ['S1 ORB (15-min box, 1x box target, EMA9 trail)', 'S1 ORB + gap filter (|gap|>%s%%)', 'S2 First pullback buy',
          'S3a VWAP trend (rejection wick, 2R)', 'S3b VWAP fade (2 SD tail, to VWAP)', 'S4 2-bar compressed ORB (30-min box)']


def main():
    D = get_data()
    days = D.days[25:]
    print(f"Manual systems backtest, {days[0]}..{days[-1]} ({len(days)} days), Core Five, cost {COST*100:.2f}%/side\n")
    for mode in ('proxy', 'legs'):
        print('=' * 30, 'MODE', mode, '(unlevered proxies long+short)' if mode == 'proxy' else '(10 x 3x legs, long only)', '=' * 30)
        hdr = f"{'system':<52}{'n':>5}{'win%':>6}{'avg%':>8}{'t':>6}{'avgR':>7}{'PF':>6}{'tgt%':>6}{'stp%':>6}{'risk%':>6}  h1 avg%  h2 avg%"
        print(hdr)
        for name in STRATS:
            nm = name % ('1' if mode == 'proxy' else '3') if '%s' in name else name
            sig = gen_signals(nm, mode, D, days)
            s = summarize(sig)
            if not s: print(f"{nm:<52} no signals"); continue
            half = days[len(days) // 2]
            h1 = [x for x in sig if x['day'] < half]; h2 = [x for x in sig if x['day'] >= half]
            a1 = st.mean(x['pct'] for x in h1) if h1 else 0; a2 = st.mean(x['pct'] for x in h2) if h2 else 0
            print(f"{nm:<52}{s['n']:>5}{s['win']:>6.1f}{s['avg']:>+8.3f}{s['t']:>6.1f}{s['R']:>+7.2f}{s['pf']:>6.2f}{s['tp']:>6.0f}{s['stp']:>6.0f}{s['avgrisk']:>6.2f}  {a1:>+7.3f} {a2:>+7.3f}")
        print()
    print('=' * 30, 'ACCOUNT SIM (legs, long only, one position at a time, 3% risk, max 3 entries/day, $2,000 start)', '=' * 30)
    print(f"{'system':<52}{'rank':<9}{'trd':>5}{'win%':>6}{'ret%':>8}{'maxDD%':>8}")
    for name in STRATS:
        nm = name % '3' if '%s' in name else name
        sig = gen_signals(nm, 'legs', D, days)
        for rank in ('first', 'random', 'rvol', 'rs', 'rvol+rs'):
            r = account(sig, D, rank)
            print(f"{nm:<52}{rank:<9}{r['trades']:>5}{r['win']:>6.1f}{r['ret']:>+8.1f}{r['mdd']:>8.1f}")
        print()
    # S5 note
    big = 0; mx = 0
    for d in days:
        for leg in LEGS:
            b = D.bars[leg][d]; g = max(x[3] for x in b) / b[0][0] - 1; mx = max(mx, g)
            if g >= 0.08: big += 1
    print(f"S5 parabolic afternoon short: the manual wants stocks up >50% on the day. Best intraday gain by any 3x leg in {len(days)} days x 10 legs: {mx*100:.1f}%; leg-days up >= 8%: {big}. Not testable as written on this universe.")


if __name__ == '__main__':
    main()
