#!/usr/bin/env python3
"""Fast parametric FADE simulator + diagnostics (loss reasons, filter / holding-rule sweeps).
    python3 tools/backtest/fade_diag.py verify                      # reproduces EX.fade_trades + MXD.account on the Robinhood cache
    /usr/bin/python3 -I tools/backtest/fade_diag.py diag  DB_5M.json.gz > results/fade_diag.txt
    /usr/bin/python3 -I tools/backtest/fade_diag.py sweep DB_5M.json.gz > results/fade_sweep.txt   (also: regime, search N, switch, shortlist)
Defaults of P() are the live rules (v5.2.15): box 9:30-10:00, break close in bars 6-8, first touch within 12 bars at edge +-0.10%,
touch bar closes back inside -> enter next open on the opposite leg; stop = post-break extreme; 1/3 at 2R, stop to breakeven,
2-ATR chandelier on the rest, out at the 13:30 bar close. Legs = leverage x proxy, 0.06% round-trip cost. Account = $2,000, 3% risk
capped at cash, one position at a time, max 3/day, earliest first, ties by proxy RVOL.
"""
import collections, gzip, json, math, os, statistics as st, sys
from dataclasses import dataclass, replace
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LEGCOST = 0.06
LEV = {'QQQ': (3, 3), 'SOXX': (3, 3), 'IWM': (3, 3), 'XLK': (3, 3), 'XBI': (3, 3), 'XLF': (3, 3), 'SPY': (3, 3), 'TLT': (3, 3),
       'GLD': (2, 2), 'KRE': (1.25, 1.25), 'VIXY': (1.5, 1)}
LIVE = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']


@dataclass(frozen=True)
class P:
    box: int = 6            # bars in the opening box
    brk_end: int = 9        # break close must be in bars box..brk_end-1
    wait: int = 12          # bars after the break bar in which the first touch must come
    tol: float = 0.10       # touch tolerance, % beyond the edge (toward the box)
    inside: str = 'edge'    # touch bar must close back inside: 'edge' (past the edge) | 'any' (no close test, enter anyway)
    stop: str = 'post'      # 'post' = post-break extreme | 'box' = far box edge... | ('atr', x) = x ATR from entry
    stop_buf: float = 0.0   # extra stop distance, fraction of R
    R: float = 2.0
    frac: float = 1 / 3
    be: bool = True         # stop to breakeven after the partial
    chand: float = 2.0      # 0 = no chandelier
    last: int = 47          # time exit bar (47 = 13:30 close)
    kmax: int = 99          # latest entry bar
    side: int = 0           # 0 both, +1 = only fade downside breaks (buy bull leg), -1 = only fade upside breaks (buy bear leg)
    minbox: float = 0.0     # box width % of price bounds
    maxbox: float = 99.0
    minrisk: float = 0.0    # proxy stop distance % bounds
    maxrisk: float = 99.0
    gap: str = ''           # '' | 'with' (fade only when break is against the gap... see gapok) | 'against'
    trend: str = ''         # '' | 'with' / 'against' prior 20-day trend (fade direction vs trend)
    maxdepth: float = 99.0  # touch bar must not trade deeper into the box than this fraction of box width
    max_entries: int = 3
    minwait: int = 1        # skip the setup when the touch comes sooner than this many bars after the break bar
    floor_atr: float = 0.0  # stop at least this many 5-min ATRs from entry (0 = off)
    floor_pct: float = 0.0  # stop at least this % of the proxy price from entry (0 = off)
    gapmin: float = 0.0     # with gap filter: |gap| must be at least this % to count as a gap (else allowed)


# ---------------------------------------------------------------- data
class DS:
    def __init__(self, src=None, syms=None):
        if src is None: path = os.path.join(HERE, 'data', 'bt_5m.json.gz')
        else: path = src
        raw = json.load(gzip.open(path, 'rt'))
        syms = [s for s in (syms or LEV) if s in raw]
        q = raw['QQQ']; self.days = []; self.bars = collections.defaultdict(dict)
        for d in sorted(q):
            if len(q[d]) < 78 or any(len(raw[p].get(d, [])) < 78 for p in LIVE if p in raw): continue
            self.days.append(d)
            t0 = q[d][0][0]
            grid = [_add(t0, 5 * i) for i in range(78)]
            for s in syms:
                m = {r[0]: tuple(r[1:]) for r in raw[s].get(d, [])}
                if not m: continue
                out, prev = [], None
                for t in grid:
                    if t in m: b = m[t]; prev = b[3]
                    elif prev is not None: b = (prev, prev, prev, prev, 0)
                    else: b = None
                    out.append(b)
                first = next((b for b in out if b), None)
                if first is None: continue
                self.bars[s][d] = [b if b else (first[0],) * 4 + (0,) for b in out]
        self.cum = {s: {d: _cum(v) for d, v in self.bars[s].items()} for s in self.bars}
        self.idx = {d: i for i, d in enumerate(self.days)}

    def rvol(self, p, d, k):
        i = self.idx[d]; pri = [x for x in self.days[max(0, i - 20):i] if x in self.cum[p]]
        try: return self.cum[p][d][k] / st.mean(self.cum[p][x][k] for x in pri)
        except Exception: return 0.0


def _add(t, mins):
    h, m_ = map(int, t.split(':')[:2]); x = h * 60 + m_ + mins; return f"{x // 60:02d}:{x % 60:02d}"


def _cum(b):
    out = [0]
    for x in b: out.append(out[-1] + x[4])
    return out


def atr_arr(b, n=14):
    tr = [b[0][1] - b[0][2]] + [max(b[i][1] - b[i][2], abs(b[i][1] - b[i - 1][3]), abs(b[i][2] - b[i - 1][3])) for i in range(1, len(b))]
    out = [0.0]
    for j in range(1, len(b)):
        w = tr[max(1, j - n + 1):j + 1]; out.append(sum(w) / len(w))
    return out


# ---------------------------------------------------------------- one proxy-day
def trade(ds, p, d, c, ctx=None):
    b = ds.bars[p][d]; nb = c.box
    H = max(x[1] for x in b[:nb]); L = min(x[2] for x in b[:nb]); W = H - L
    for j in range(nb, min(c.brk_end, 76)):
        cl = b[j][3]; bs = 1 if cl > H else -1 if cl < L else 0   # break side
        if not bs: continue
        E = H if bs > 0 else L
        for i in range(j + 1, min(j + 1 + c.wait, 76)):
            o, h, l, cc, v = b[i]
            touch = l <= E * (1 + c.tol / 100) if bs > 0 else h >= E * (1 - c.tol / 100)
            if not touch: continue
            back = cc < E if bs > 0 else cc > E
            if c.inside == 'edge' and not back: return None
            if i - j < c.minwait: return None
            k = i + 1; side = -bs                                  # trade direction (+1 = bull leg)
            if k >= c.last or k > c.kmax: return None
            entry = b[k][0]
            ext = max(x[1] for x in b[j:i + 1]) if bs > 0 else min(x[2] for x in b[j:i + 1])
            info = dict(day=d, proxy=p, side=side, k=k, brk=j, touch=i, wait=i - j, box_pct=W / E * 100,
                        depth=((E - l) if bs > 0 else (h - E)) / W if W else 0, ext_pct=abs(ext - E) / E * 100)
            return _manage(ds, p, d, b, k, side, entry, ext, c, info, ctx)
        return None
    return None


def _manage(ds, p, d, b, k, side, entry, ext, c, info, ctx):
    s = side
    if c.stop == 'post': stop = ext
    elif isinstance(c.stop, tuple) and c.stop[0] == 'atr': stop = entry - s * c.stop[1] * ctx['atr'][p][d][k - 1]
    elif isinstance(c.stop, tuple) and c.stop[0] == 'pct': stop = entry - s * entry * c.stop[1] / 100
    else: raise ValueError(c.stop)
    r = (entry - stop) * s
    if r <= 0: return None
    if c.floor_atr: r = max(r, c.floor_atr * ctx['atr'][p][d][k - 1])
    if c.floor_pct: r = max(r, entry * c.floor_pct / 100)
    r *= 1 + c.stop_buf; stop = entry - s * r
    risk = r / entry * 100; info['risk_pct'] = risk
    if not (c.minbox <= info['box_pct'] <= c.maxbox) or not (c.minrisk <= risk <= c.maxrisk) or info['depth'] > c.maxdepth: return None
    if c.side and s != c.side: return None
    if c.gap or c.trend:
        g = ctx['gap'][p].get(d); tr = ctx['trend'][p].get(d)
        big = g is not None and abs(g) * 100 >= c.gapmin
        if c.gap and (g is None or (big and ((c.gap == 'with' and g * s <= 0) or (c.gap == 'against' and g * s >= 0)))): return None
        if c.trend and (tr is None or (c.trend == 'with' and tr * s <= 0) or (c.trend == 'against' and tr * s >= 0)): return None
    at = ctx['atr'][p][d]
    T = entry + s * c.R * r
    gross = 0.0; rem = 1.0; hit = False; hic = entry; why = 'time'; xbar = c.last; mfe = 0.0; mae = 0.0
    for j in range(k, c.last + 1):
        o, h, l, cl, v = b[j]
        fav, adv = (h, l) if s > 0 else (l, h)
        mfe = max(mfe, (fav - entry) * s / r); mae = max(mae, (entry - adv) * s / r)
        if (adv - stop) * s <= 0:
            px = stop if (o - stop) * s >= 0 else o
            gross += rem * (px - entry) * s; rem = 0; why = 'stop' if not hit else ('be' if abs(stop - entry) < 1e-12 else 'trail'); xbar = j; break
        if not hit and (fav - T) * s >= 0:
            px = T if (o - T) * s <= 0 else o
            gross += c.frac * (px - entry) * s; rem = 1 - c.frac; hit = True
            if c.be: stop = entry if (entry - stop) * s > 0 else stop
            if rem <= 1e-9: why = 'target'; xbar = j; break
        hic = max(hic, cl) if s > 0 else min(hic, cl)
        if hit and j < c.last and c.chand:
            ns = hic - s * c.chand * at[j]
            if (ns - stop) * s > 0: stop = ns
    if rem > 0: gross += rem * (b[c.last][3] - entry) * s
    lev = LEV[p][0] if s > 0 else LEV[p][1]
    info.update(xbar=xbar, why=why, hit=hit, R_out=gross / r, mfe=mfe, mae=mae,
                pct=lev * gross / entry * 100 - LEGCOST, leg_risk=lev * r / entry * 100)
    return info


def context(ds, syms):
    atr = {p: {d: atr_arr(b) for d, b in ds.bars[p].items()} for p in syms}
    gap = {p: {} for p in syms}; trend = {p: {} for p in syms}
    for p in syms:
        prevc = []
        for d in ds.days:
            b = ds.bars[p].get(d)
            if not b: continue
            if prevc: gap[p][d] = b[0][0] / prevc[-1] - 1
            if len(prevc) >= 20: trend[p][d] = prevc[-1] / prevc[-20] - 1
            prevc.append(b[-1][3])
    return dict(atr=atr, gap=gap, trend=trend)


def trades(ds, days, syms, c, ctx):
    return [t for p in syms for d in days if d in ds.bars[p] for t in [trade(ds, p, d, c, ctx)] if t]


def account(ds, days, T, risk=0.03, max_entries=3):
    by = collections.defaultdict(list)
    for t in T: by[t['day']].append(t)
    daily = {}; taken = []; eq = 1.0; peak = 1.0; mdd = 0.0
    for d in days:
        cs = sorted(by.get(d, []), key=lambda t: t['k']); free = 0; n = 0; e0 = eq
        while cs and n < max_entries:
            av = [t for t in cs if t['k'] >= free]
            if not av: break
            k0 = min(t['k'] for t in av); same = [t for t in av if t['k'] == k0]
            same.sort(key=lambda t: -ds.rvol(t['proxy'], d, t['k']))
            t = same[0]; f = min(1.0, risk * 100 / t['leg_risk'])
            eq *= 1 + f * t['pct'] / 100; taken.append(dict(t, w=f, acct=f * t['pct'])); free = t['xbar'] + 1; cs.remove(t); n += 1
        daily[d] = (eq / e0 - 1) * 100; peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
    return dict(daily=daily, taken=taken, ret=(eq - 1) * 100, mdd=mdd)


def stat(a):
    dl = list(a['daily'].values()); t = a['taken']
    return dict(avg=st.mean(dl) if dl else 0, n=len(t), win=100 * sum(x['pct'] > 0 for x in t) / len(t) if t else 0, mdd=a['mdd'], ret=a['ret'])


# ---------------------------------------------------------------- verify against the engine
def verify():
    import backtest as BT, manual as m, pb_final as PBF, mixed as MXD, expand_lists as EX, fade_addone as FA
    from lab import get_data
    D = get_data(); m.rvol = PBF.rvol(D); days = D.days[1:]
    f = [c for p in LIVE for c in MXD.norm_px(EX.fade_trades(D, days, p, FA.ROWS[p]), 'FADE')]
    a = MXD.account(D, days, f)
    ds = DS(syms=LIVE); ctx = context(ds, LIVE)
    b = account(ds, days, trades(ds, days, LIVE, P(), ctx))
    print(f"engine: {len(a['taken'])} trades {st.mean(a['daily'].values()):+.4f}%/day ret {a['ret']:+.2f}%")
    print(f"fast  : {len(b['taken'])} trades {st.mean(b['daily'].values()):+.4f}%/day ret {b['ret']:+.2f}%")
    e = {(x['day'], x['proxy']): x['pct'] for x in a['taken']}; g = {(x['day'], x['proxy']): x['pct'] for x in b['taken']}
    bad = [k for k in set(e) | set(g) if k not in e or k not in g or abs(e[k] - g[k]) > 1e-6]
    print(f"mismatched trades: {len(bad)} {sorted(bad)[:10]}")


if __name__ == '__main__':
    if sys.argv[1] == 'verify': verify()


# ---------------------------------------------------------------- diagnostics
WIN = {'DESIGN 2023-03..2025-06': ('2023-01-01', '2025-06-30'), 'HOLDOUT 2025-07..2026-02': ('2025-07-01', '2026-02-27'),
       'RECENT 2026-03..10': ('2026-03-01', '2026-12-31')}
ALL = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY', 'TLT', 'GLD', 'KRE', 'VIXY']


def wdays(ds, w): a, b = WIN[w]; return [d for d in ds.days[21:] if a <= d <= b]


def grp(T, key, label, order=None):
    g = collections.defaultdict(list)
    for t in T: g[key(t)].append(t)
    print(f"  {label}")
    for k in (order or sorted(g)):
        v = g.get(k)
        if not v: continue
        r = [x['R_out'] for x in v]; pc = [x['pct'] for x in v]
        print(f"     {str(k):<22} n {len(v):4d}  win {100*sum(x>0 for x in pc)/len(v):3.0f}%  avg R {st.mean(r):+.3f}  avg leg {st.mean(pc):+.3f}%  "
              f"sum R {sum(r):+7.1f}  reach1R {100*sum(x['mfe']>=1 for x in v)/len(v):3.0f}%  reach2R {100*sum(x['mfe']>=2 for x in v)/len(v):3.0f}%")


def tercile(T, f):
    v = sorted(f(t) for t in T); q1, q2 = v[len(v) // 3], v[2 * len(v) // 3]
    return lambda t: f"low <{q1:.2f}" if f(t) < q1 else f"mid {q1:.2f}-{q2:.2f}" if f(t) < q2 else f"high >={q2:.2f}"


def hhmm(k): x = 570 + 5 * k; return f"{x // 60}:{x % 60:02d}"


def diag(src):
    ds = DS(src, ALL); syms = [s for s in ALL if s in ds.bars]; ctx = context(ds, syms)
    print(f"FADE diagnostics on {os.path.basename(src)}: {len(ds.days)} days {ds.days[0]}..{ds.days[-1]}; symbols {' '.join(syms)}")
    print("Live rules unless stated. 'R' = proxy move / initial stop distance (1R loss = full stop). All raw proxy setups, before the one-at-a-time account.\n")
    c = P()
    for w in WIN:
        days = wdays(ds, w); T = trades(ds, days, LIVE, c, ctx); a = stat(account(ds, days, T))
        print(f"== {w}: {len(days)} days, live six: {len(T)} setups, account {a['n']} trades win {a['win']:.0f}% {a['avg']:+.3f}%/day DD {a['mdd']:.1f}%")
    days = [d for d in ds.days[21:] if d <= '2026-02-27']; T = trades(ds, days, LIVE, c, ctx)
    print(f"\n#### OUT-OF-SAMPLE 2023-03..2026-02, live six, {len(T)} setups ####")
    grp(T, lambda t: t['why'], 'exit reason (stop = full loss before 2R; be = partial then breakeven; trail = chandelier; time = 13:30)')
    grp(T, lambda t: 'buy bull leg (fade down-break)' if t['side'] > 0 else 'buy bear leg (fade up-break)', 'side')
    grp(T, lambda t: t['proxy'], 'proxy')
    grp(T, lambda t: hhmm(t['k']), 'entry time', order=[hhmm(k) for k in range(6, 30)])
    grp(T, lambda t: hhmm(t['brk']), 'break bar close time')
    grp(T, lambda t: t['wait'], 'bars from break to touch')
    grp(T, tercile(T, lambda t: t['box_pct']), 'box width % (terciles)')
    grp(T, tercile(T, lambda t: t['risk_pct']), 'stop distance % of proxy (terciles)')
    grp(T, tercile(T, lambda t: t['risk_pct'] / t['box_pct']), 'stop distance / box width (terciles)')
    grp(T, tercile(T, lambda t: t['depth']), 'touch depth into box, fraction of box (terciles)')
    g = ctx['gap']; tr = ctx['trend']
    grp(T, lambda t: 'n/a' if g[t['proxy']].get(t['day']) is None else ('fade in gap direction' if g[t['proxy']][t['day']] * t['side'] > 0 else 'fade against gap'), 'gap (open vs prior close)')
    grp(T, lambda t: 'n/a' if tr[t['proxy']].get(t['day']) is None else ('fade with 20d trend' if tr[t['proxy']][t['day']] * t['side'] > 0 else 'fade against 20d trend'), '20-day trend')
    grp(T, lambda t: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][__import__('datetime').date.fromisoformat(t['day']).weekday()], 'weekday', order=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
    grp(T, lambda t: t['day'][:4], 'year')
    st_ = [t for t in T if t['why'] == 'stop']
    print(f"\n  full-stop losers: {len(st_)} of {len(T)}; of those, reached +1R first {sum(t['mfe']>=1 for t in st_)}, +1.5R {sum(t['mfe']>=1.5 for t in st_)}; "
          f"stopped on entry bar or next {sum(t['xbar']-t['k']<=1 for t in st_)}")
    tm = [t for t in T if t['why'] == 'time']
    if tm: print(f"  time exits: {len(tm)}, avg R {st.mean(t['R_out'] for t in tm):+.3f}, of which hit 2R first {sum(t['hit'] for t in tm)}")
    print(f"  avg MFE {st.mean(t['mfe'] for t in T):.2f}R, median {st.median(t['mfe'] for t in T):.2f}R; avg MAE {st.mean(t['mae'] for t in T):.2f}R")
    # every name alone
    print("\n#### each name alone, live rules (account, that name only) ####")
    for w in list(WIN) + ['OOS']:
        days = [d for d in ds.days[21:] if d <= '2026-02-27'] if w == 'OOS' else wdays(ds, w)
        row = []
        for p in syms:
            T = trades(ds, days, [p], c, ctx); a = stat(account(ds, days, T)); row.append(f"{p} {a['avg']:+.3f}({a['n']})")
        print(f"  {w:<26} " + '  '.join(row))


if __name__ == '__main__' and sys.argv[1] == 'diag': diag(sys.argv[2])


# ---------------------------------------------------------------- sweeps
def evaluator(src):
    ds = DS(src, ALL); syms = [s for s in ALL if s in ds.bars]; ctx = context(ds, syms)
    rh = DS(None, ALL); rsyms = [s for s in ALL if s in rh.bars]; rctx = context(rh, rsyms)
    W = {w: wdays(ds, w) for w in WIN}; rdays = rh.days[1:]
    def ev(c, names=LIVE):
        out = {}
        for w, days in W.items():
            out[w] = stat(account(ds, days, trades(ds, days, [n for n in names if n in syms], c, ctx), max_entries=c.max_entries))
        out['RH'] = stat(account(rh, rdays, trades(rh, rdays, [n for n in names if n in rsyms], c, rctx), max_entries=c.max_entries))
        return out
    return ev, ds, syms, ctx, rh


def line(tag, o):
    k = list(o)
    return f"{tag:<34}" + ''.join(f" | {o[w]['avg']:+.3f} {o[w]['n']:3d}t {o[w]['win']:2.0f}% DD{o[w]['mdd']:4.1f}" for w in k)


HDR = f"{'':<34} | DESIGN 23-03..25-06 (Mini)  | HOLDOUT 25-07..26-02 (Mini) | RECENT 26-03..10 (Mini)     | RH 26-03..10-14 (Robinhood)"


def sweep(src):
    ev, ds, syms, ctx, rh = evaluator(src)
    base = P()
    print("FADE one-at-a-time sweeps, six live proxies. Each cell: %/day (incl. no-trade days)  trades  win%  max DD%.\n" + HDR)
    print(line('LIVE RULES', ev(base)))
    grid = {
        'stop_buf (x R wider)': [('stop_buf', v) for v in (0.25, 0.5, 1.0, 1.5)],
        'stop floor (ATR)': [('floor_atr', v) for v in (0.5, 1.0, 1.5, 2.0, 3.0)],
        'stop = x ATR from entry': [('stop', ('atr', v)) for v in (1.0, 1.5, 2.0, 3.0)],
        'stop = x % from entry': [('stop', ('pct', v)) for v in (0.25, 0.4, 0.6, 0.8)],
        'R target': [('R', v) for v in (1.0, 1.5, 2.5, 3.0, 4.0)],
        'partial fraction': [('frac', v) for v in (0.0, 0.5, 2 / 3, 1.0)],
        'breakeven after partial': [('be', False)],
        'chandelier ATR': [('chand', v) for v in (0, 1.0, 1.5, 3.0, 4.0)],
        'time exit bar': [('last', v) for v in (29, 35, 41, 53, 59, 65, 71, 77)],
        'max wait bars': [('wait', v) for v in (1, 2, 3, 6)],
        'min wait bars': [('minwait', v) for v in (2, 3)],
        'touch tolerance %': [('tol', v) for v in (0.0, 0.05, 0.2, 0.3, 0.5)],
        'close-back-inside test': [('inside', 'any')],
        'break window end bar': [('brk_end', v) for v in (7, 8, 10, 12, 15, 18)],
        'box bars (break window = +3)': [('box', v) for v in (3, 4, 9, 12)],
        'side': [('side', 1), ('side', -1)],
        'gap filter': [('gap', 'with'), ('gap', 'against')],
        'gap filter (only |gap|>=0.3%)': [(('gap', 'gapmin'), ('with', 0.3)), (('gap', 'gapmin'), ('against', 0.3))],
        'trend filter': [('trend', 'with'), ('trend', 'against')],
        'min box %': [('minbox', v) for v in (0.4, 0.6, 0.8)],
        'max box %': [('maxbox', v) for v in (0.8, 1.2, 1.6)],
        'min stop %': [('minrisk', v) for v in (0.1, 0.15, 0.2, 0.3)],
        'max stop %': [('maxrisk', v) for v in (0.3, 0.5, 0.8)],
        'max touch depth (x box)': [('maxdepth', v) for v in (0.15, 0.25, 0.5)],
        'max entries/day': [('max_entries', v) for v in (1, 2)],
    }
    for g, opts in grid.items():
        print(f"-- {g}")
        for k, v in opts:
            if k == 'box': c = replace(base, box=v, brk_end=v + 3)
            elif isinstance(k, tuple): c = replace(base, **dict(zip(k, v)))
            else: c = replace(base, **{k: v})
            print(line(f"   {k}={v if not isinstance(v, float) else round(v, 3)}", ev(c)))
    print("\n-- proxy sets with live rules")
    for names in (ALL, ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SPY'], ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'TLT', 'GLD'], ['IWM', 'XBI', 'XLF', 'TLT', 'GLD', 'KRE']):
        print(line('   ' + ' '.join(names)[:31], ev(base, names)))


if __name__ == '__main__' and sys.argv[1] == 'sweep': sweep(sys.argv[2])


def regime(src):
    ds = DS(src, ALL); syms = [s for s in ALL if s in ds.bars]; ctx = context(ds, syms)
    # per proxy-day features known before 10:00: 20-day avg daily range %, prior VIXY close, 20d realized vol of QQQ, box / avg daily range
    feat = collections.defaultdict(dict)
    for p in syms:
        rng = []; cl = []
        for d in ds.days:
            b = ds.bars[p].get(d)
            if not b: continue
            if len(rng) >= 20:
                f = feat[p].setdefault(d, {}); f['adr'] = st.mean(rng[-20:])
                f['rv'] = st.pstdev([cl[i] / cl[i - 1] - 1 for i in range(len(cl) - 20, len(cl))]) * 100
                f['box_adr'] = (max(x[1] for x in b[:6]) - min(x[2] for x in b[:6])) / b[0][0] * 100 / f['adr']
                f['vol_r'] = sum(x[4] for x in b[:6]) / max(1, st.mean(ds.cum[p][x][6] for x in ds.days[ds.idx[d] - 20:ds.idx[d]] if x in ds.cum[p]))
            rng.append((max(x[1] for x in b) - min(x[2] for x in b)) / b[0][0] * 100); cl.append(b[-1][3])
    vix = {}; prev = None
    for d in ds.days:
        if prev and prev in ds.bars['VIXY']: vix[d] = ds.bars['VIXY'][prev][-1][3]
        prev = d
    days = ds.days[21:]; T = trades(ds, days, LIVE, P(), ctx)
    for t in T:
        f = feat[t['proxy']].get(t['day'], {}); t.update(f); t['vixy'] = vix.get(t['day']); t['qqq_rv'] = feat['QQQ'].get(t['day'], {}).get('rv')
        t['era'] = 'OOS' if t['day'] <= '2026-02-27' else 'R26'
    print(f"Regime features (known by 10:00) vs FADE outcome, live rules, six proxies. Terciles cut on the OOS 2023-03..2026-02 setups; same cuts applied to 2026-03..10.\n")
    for name, fn in (('20d avg daily range % (proxy)', lambda t: t.get('adr')), ('20d realized vol % (proxy)', lambda t: t.get('rv')),
                     ('QQQ 20d realized vol %', lambda t: t.get('qqq_rv')), ('box width / 20d avg range', lambda t: t.get('box_adr')),
                     ('opening 30-min volume / 20d avg', lambda t: t.get('vol_r')), ('stop distance / 20d avg range', lambda t: t['risk_pct'] / t['adr'] if t.get('adr') else None),
                     ('VIXY prior close (split-adj)', lambda t: t.get('vixy'))):
        V = [t for t in T if fn(t) is not None]; o = sorted(fn(t) for t in V if t['era'] == 'OOS')
        q1, q2 = o[len(o) // 3], o[2 * len(o) // 3]
        print(f"  {name}: cuts {q1:.3g} / {q2:.3g}")
        for lab_, lo, hi in (('low', -1e9, q1), ('mid', q1, q2), ('high', q2, 1e9)):
            row = []
            for era in ('OOS', 'R26'):
                v = [t['R_out'] for t in V if t['era'] == era and lo <= fn(t) < hi]
                row.append(f"{era} n {len(v):3d} avg R {st.mean(v) if v else 0:+.3f} sum {sum(v):+6.1f}")
            print(f"     {lab_:<5} " + '   '.join(row))
    print("\n  2026-03..10 vs OOS averages: " + ', '.join(
        f"{k} {st.mean(t[k] for t in T if t['era']=='OOS' and t.get(k) is not None):.3g}->{st.mean(t[k] for t in T if t['era']=='R26' and t.get(k) is not None):.3g}"
        for k in ('adr', 'rv', 'qqq_rv', 'box_adr', 'vol_r', 'box_pct', 'risk_pct')))


if __name__ == '__main__' and sys.argv[1] == 'regime': regime(sys.argv[2])


SPACE = dict(box=[3, 4, 6], brk_extra=[1, 2, 3, 6], wait=[1, 3, 12], tol=[0.0, 0.1, 0.3], stop=['post', ('atr', 1.0), ('atr', 2.0), ('pct', 0.4), ('pct', 0.6)],
             stop_buf=[0.0, 0.5, 1.0], R=[1.0, 1.5, 2.0, 3.0], frac=[0.0, 1 / 3, 0.5, 1.0], chand=[0, 2.0, 3.0], last=[29, 47, 77],
             side=[0, 1, -1], gap=['', 'with'], trend=['', 'with', 'against'], minrisk=[0.0, 0.15], maxrisk=[0.5, 99.0], names=['live', 'all', 'ex_tech'])
NAMES = {'live': LIVE, 'all': ALL, 'ex_tech': ['IWM', 'XBI', 'XLF', 'SPY', 'TLT', 'GLD', 'KRE']}


def search(src, n=2500, seed=7):
    import random
    ev, *_ = evaluator(src); rnd = random.Random(seed); seen = set(); res = []
    for _ in range(n):
        x = {k: rnd.choice(v) for k, v in SPACE.items()}; key = tuple(sorted((k, str(v)) for k, v in x.items()))
        if key in seen: continue
        seen.add(key)
        c = P(box=x['box'], brk_end=x['box'] + x['brk_extra'], wait=x['wait'], tol=x['tol'], stop=x['stop'], stop_buf=x['stop_buf'], R=x['R'], frac=x['frac'],
              chand=x['chand'], last=x['last'], side=x['side'], gap=x['gap'], trend=x['trend'], minrisk=x['minrisk'], maxrisk=x['maxrisk'])
        o = ev(c, NAMES[x['names']]); res.append((x, o))
    def show(title, key, m=15):
        print(f"\n== {title} ==\n" + HDR)
        for x, o in sorted(res, key=key)[:m]:
            print(line('', o) + '   ' + ' '.join(f"{k}={round(v, 2) if isinstance(v, float) else v}" for k, v in x.items()))
    print(f"Random search over {len(res)} FADE variants (Mini data).")
    show('best on DESIGN 2023-03..2025-06 (min 60 trades)', lambda r: -r[1]['DESIGN 2023-03..2025-06']['avg'] if r[1]['DESIGN 2023-03..2025-06']['n'] >= 60 else 9)
    pre = lambda o: (o['DESIGN 2023-03..2025-06']['avg'] * 450 + o['HOLDOUT 2025-07..2026-02']['avg'] * 164) / 614
    show('best on all pre-2026 (design+holdout, min 80 trades)', lambda r: -pre(r[1]) if r[1]['DESIGN 2023-03..2025-06']['n'] + r[1]['HOLDOUT 2025-07..2026-02']['n'] >= 80 else 9)
    show('best worst-window across the three Mini windows (min 30 trades each)', lambda r: -min(r[1][w]['avg'] for w in WIN) if min(r[1][w]['n'] for w in WIN) >= 30 else 9)
    pos = [r for r in res if all(r[1][w]['avg'] > 0 for w in WIN) and r[1]['RH']['avg'] > 0]
    print(f"\nvariants positive in all three Mini windows AND on Robinhood: {len(pos)} of {len(res)}")


if __name__ == '__main__' and sys.argv[1] == 'search': search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2500)


def switch(src):
    ev, ds, syms, ctx, rh = evaluator(src)
    days = ds.days[1:]; c = P()
    allT = trades(ds, days, syms, c, ctx)
    byday = collections.defaultdict(list)
    for t in allT: byday[t['day']].append(t)
    print("Month by month, live rules, every FADE setup on all 11 names (raw, before the account): n, avg R, and the live-six account %/day\n")
    mo = collections.defaultdict(list)
    for t in allT: mo[t['day'][:7]].append(t['R_out'])
    six = account(ds, days, [t for t in allT if t['proxy'] in LIVE])
    md = collections.defaultdict(list)
    for d, v in six['daily'].items(): md[d[:7]].append(v)
    for k in sorted(mo): print(f"   {k}  n {len(mo[k]):3d}  avg R {st.mean(mo[k]):+.2f}  sum R {sum(mo[k]):+6.1f}   live-six {st.mean(md[k]):+.3f}%/day")
    print("\nRegime switch: trade the live six on day d only if the summed R of all setups on the 11 names over the previous N days > X (paper-tracked, known before the open)")
    print(HDR)
    print(line('no switch', ev(c)))
    idx = {d: i for i, d in enumerate(days)}
    for N in (10, 20, 40, 60, 90):
        for X in (0, 5):
            ok = set()
            for d in days:
                i = idx[d]
                if i < N: continue
                if sum(t['R_out'] for x in days[i - N:i] for t in byday.get(x, [])) > X: ok.add(d)
            out = {}
            for w in WIN:
                wd = wdays(ds, w); T = [t for t in trades(ds, wd, LIVE, c, ctx) if t['day'] in ok]
                out[w] = stat(account(ds, wd, T)); out[w]['on'] = sum(d in ok for d in wd) / len(wd)
            print(line(f"N={N} X>{X}", out) + '   on-days ' + ' '.join(f"{100*out[w]['on']:.0f}%" for w in WIN))


if __name__ == '__main__' and sys.argv[1] == 'switch': switch(sys.argv[2])


def shortlist(src):
    ev, ds, syms, ctx, rh = evaluator(src)
    rd = rh.days[1:]; h = len(rd) // 2; mar = [d for d in rd if d < '2026-04-07']
    def rhs(c):
        a = account(rh, rd, trades(rh, rd, LIVE, c, None or context(rh, LIVE)))
        dl = a['daily']; m_ = account(rh, mar, trades(rh, mar, LIVE, c, context(rh, LIVE)))
        return f"RH halves {st.mean(dl[d] for d in rd[:h]):+.3f}/{st.mean(dl[d] for d in rd[h:]):+.3f}  March {st.mean(m_['daily'].values()):+.3f}"
    C = {'LIVE': P()}
    for v in (0.4, 0.5, 0.6, 0.7, 0.8): C[f'stop {v}% fixed'] = P(stop=('pct', v))
    for v in (0.3, 0.4, 0.5, 0.6): C[f'stop floor {v}%'] = P(floor_pct=v)
    for v in (0.5, 1.0): C[f'stop x{1+v:g} post-break'] = P(stop_buf=v)
    C['wait 3'] = P(wait=3)
    for v in (0.4, 0.5, 0.6): C[f'stop floor {v}% + wait 3'] = P(floor_pct=v, wait=3)
    C['stop 0.6% fixed + wait 3'] = P(stop=('pct', 0.6), wait=3)
    C['stop x2 post-break + wait 3'] = P(stop_buf=1.0, wait=3)
    C['floor 0.5% + wait 3 + gap with'] = P(floor_pct=0.5, wait=3, gap='with')
    print("Shortlist: changes that helped in every window one-at-a-time, and combinations. Six live proxies.\n" + HDR)
    for k, c in C.items():
        print(line(k, ev(c)) + '   ' + rhs(c))
    print("\nSame shortlist on all 11 names:")
    for k in ('LIVE', 'stop floor 0.5%', 'stop floor 0.5% + wait 3'):
        print(line(k, ev(C[k], ALL)))


if __name__ == '__main__' and sys.argv[1] == 'shortlist': shortlist(sys.argv[2])
