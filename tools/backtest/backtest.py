#!/usr/bin/env python3
"""Full-system backtest of the live rules (RULEBOOK C1/C4/C8/C12, B1/B2, A1, E1) on real 5-minute bars of
the eight proxies and the sixteen leveraged tickers, 2026-03-02 .. 2026-10-15.

    python3 tools/backtest/backtest.py [--cost 0.03] [--no-throttle] [--no-ratchet] [--csv out.csv] [--quiet]

Timing model (documented approximations -- see README):
  * A checkpoint with K completed 5-min bars acts on bars 0..K-1 only (bar 0 = 9:30). Checkpoints run 10:00 (K=6) .. 12:25.
  * Entry fills at the OPEN of bar K (the checkpoint is ~1 minute into that bar) +cost; exits via stop fill at the stop
    price (or the bar open on a gap) -cost; 12:30 close fills at the open of bar 36 -cost.
  * Ratchet decisions at a checkpoint use the highs of completed bars since entry and the last completed bar's close as the
    live price; a new stop is effective from the next bar.
  * Stops trigger intrabar: bar low <= stop (long legs; every traded ticker is a long ETF).
  * A leg with a missing 5-min bar (no trades) is carried forward flat (o=h=l=c=prev close).
"""
import argparse, csv, gzip, json, math, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = {  # proxy: (long leg, inverse leg)
    'QQQ': ('TQQQ', 'SQQQ'), 'SPY': ('UPRO', 'SPXU'), 'SOXX': ('SOXL', 'SOXS'), 'IWM': ('TNA', 'TZA'),
    'XLF': ('FAS', 'FAZ'), 'XLE': ('ERX', 'ERY'), 'TLT': ('TMF', 'TMV'), 'XBI': ('LABU', 'LABD')}
PROXIES = list(ROWS)
LEGS = [x for p in ROWS.values() for x in p]


def load(live=False):
    raw = json.load(gzip.open(f'{HERE}/data/bt_5m.json.gz'))
    daily = json.load(gzip.open(f'{HERE}/data/bt_daily.json.gz'))
    lf = f'{HERE}/data/live_5m.json.gz'
    if live and os.path.exists(lf):                     # live sessions appended by extend_live.py; a day held there replaces the base day
        for s, days in json.load(gzip.open(lf)).items():
            for d, bars in days.items(): raw.setdefault(s, {})[d] = bars
    return raw, daily


def hhmm_add(t, mins):
    h, m = int(t[:2]), int(t[3:])
    n = h * 60 + m + mins
    return f'{n // 60:02d}:{n % 60:02d}'


class Data:
    def __init__(self, live=False):
        raw, daily = load(live)
        self.daily = {s: {r[0]: r[1:] for r in rows} for s, rows in daily.items()}
        self.days = []                                    # trading days with a full proxy session
        self.bars = defaultdict(dict)                     # sym -> day -> 78 x (o,h,l,c,v)  (None if no data at all)
        alld = sorted(set(raw['QQQ']))
        lf = f'{HERE}/data/live_5m.json.gz'
        live_days = set(json.load(gzip.open(lf))['QQQ']) if live and os.path.exists(lf) else set()
        LIVE6 = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']        # live sessions carry only the six traded FADE proxies (no SPY, XLE, TLT)
        for d in alld:
            q = raw['QQQ'][d]
            if len(q) < 78 or any(len(raw[p].get(d, [])) < 78 for p in (LIVE6 if d in live_days else PROXIES)): continue
            self.days.append(d)
            t0 = q[0][0]
            grid = [hhmm_add(t0, 5 * i) for i in range(78)]
            for s in raw:
                m = {r[0]: r[1:] for r in raw[s].get(d, [])}
                if not m: continue
                out, prev = [], None
                for t in grid:
                    if t in m: b = tuple(m[t]); prev = b[3]
                    elif prev is not None: b = (prev, prev, prev, prev, 0)
                    else: b = None
                    out.append(b)
                # back-fill leading gaps with the first real open
                first = next((b for b in out if b), None)
                if first is None: continue
                out = [b if b else (first[0],) * 4 + (0,) for b in out]
                self.bars[s][d] = out
        # proxy cumulative volume and daily H/L/C for ATR
        EXTRA = [p for p in ('XLU', 'XLRE', 'XOP', 'EEM', 'XLK', 'XLV', 'GDX', 'EWY', 'IBIT', 'DRAM', 'NVDA', 'TSLA', 'MSTR', 'COIN', 'AMD', 'UNG', 'FXI', 'ETHA', 'VIXY', 'SLV', 'KRE', 'SMH', 'AAPL', 'AMZN', 'META', 'MSFT', 'GLD') if p in self.bars]
        self.cum = {p: {d: [sum(b[4] for b in self.bars[p][d][:k]) for k in range(79)] for d in self.days if d in self.bars[p]} for p in PROXIES + EXTRA}
        self.dhlc = {p: {d: (max(b[1] for b in self.bars[p][d]), min(b[2] for b in self.bars[p][d]), self.bars[p][d][-1][3])
                         for d in self.days if d in self.bars[p]} for p in PROXIES + EXTRA}

    def prior(self, d, n):
        i = self.days.index(d)
        return self.days[max(0, i - n):i]


def profile(daily, sym, day):
    """RULEBOOK B1 / tools/profile.py on the last 31 sessions before `day` -> (stall_pct, min_move_pct) as fractions."""
    ks = sorted(k for k in daily[sym] if k < day)[-31:]
    adv = [(daily[sym][k][0] - daily[sym][k][2]) / daily[sym][k][0] for k in ks]
    fav = [(daily[sym][k][1] - daily[sym][k][0]) / daily[sym][k][0] for k in ks]
    ma, mf = st.median(adv), st.median(fav)
    clamp = lambda x, lo, hi: max(lo, min(hi, x))
    return clamp(0.15 * mf, 0.0010, 0.0100), clamp(0.25 * ma, 0.0020, 0.0100)


def floor_tick(x):
    return math.floor(x * 100 + 1e-9) / 100


class Sim:
    def __init__(self, cost=0.0003, throttle=True, ratchet=True, start_equity=2000.0, vol_test=True, momentum=True, rng=None, q=0.07):
        self.D = Data(); self.cost = cost; self.throttle = throttle; self.ratchet = ratchet
        self.eq = start_equity; self.vol_test = vol_test; self.momentum = momentum; self.rng = rng; self.q = q
        self.streak = 0; self.thr_on = False; self.thr_wins = 0
        self.trades = []; self.day_eq = []

    # ---- C1 on the proxies at a checkpoint with K completed bars -------------------------------------------
    def gate(self, d, K):
        D = self.D; pri = D.prior(d, 20); out = {}
        if len(pri) < 20: return None
        rv = {}
        for p in PROXIES:
            base = st.mean(D.cum[p][x][K] for x in pri)
            rv[p] = D.cum[p][d][K] / base if base else 0.0
        passing = [p for p in PROXIES if rv[p] >= 1.0]
        if len(passing) < 3: passing = sorted(PROXIES, key=lambda p: -rv[p])[:3]
        pr14 = D.prior(d, 15)
        for p in PROXIES:
            bars = D.bars[p][d][:K]
            orb = bars[:6]; orh, orl = max(b[1] for b in orb), min(b[2] for b in orb)
            post = [b[3] for b in bars[6:]]
            run = side = 0
            for c in post:
                sd = 1 if c > orh else -1 if c < orl else 0
                run = run + 1 if sd and sd == side else (1 if sd else 0)
                side = sd
            tr = []
            for a, b in zip(pr14, pr14[1:]):
                h, l, _ = D.dhlc[p][b]; pc = D.dhlc[p][a][2]
                tr.append(max(h - l, abs(h - pc), abs(l - pc)))
            atr = st.mean(tr[-14:]) if tr else None
            if not atr: continue
            exp = (max(b[1] for b in bars) - min(b[2] for b in bars)) / atr
            vt = True
            if run >= 2 and self.vol_test and K < 6 + 12:           # volume test applies to checkpoints before 11:00
                i = 6 + len(post) - run
                prev = [b[4] for b in bars[max(0, i - 3):i]]
                vt = bool(prev) and bars[i][4] > sum(prev) / len(prev)
            out[p] = dict(rvol=rv[p], pass1=p in passing, orh=orh, orl=orl, side=side if run >= 2 else 0, run=run,
                          exp=exp, score=(1 - exp) * rv[p], vol_ok=vt, closes=post[-3:])
        return out

    # ---- one trading day ---------------------------------------------------------------------------------
    def run_day(self, d):
        D = self.D
        if len(D.prior(d, 20)) < 20: return
        cash = self.eq; entries = []; pos = None; last_exit = None
        locked = self.streak >= 5
        if locked: self.streak = 0; self.thr_on = True; self.thr_wins = 0     # governor clears next day, resumes throttled
        losers = set(); n_ent = 0; dist = {}; first_rvol = {}; reentries = 0
        for i in range(0, 31):                                  # checkpoint i: K = 6 + i completed bars (10:00 .. 12:25); i=30 -> 12:30 close
            K = 6 + i
            # ---- manage an open position: bars K-1 was just completed; first check whether the stop hit during bars since last check
            if pos:
                res = self.advance(pos, d, K)
                if res:
                    cash = self.close(pos, res, d, cash); last_exit = dict(pos=pos, K=K, win=res[2] > 0, leg=pos['leg'], proxy=pos['proxy'], side=pos['side'], i=i)
                    if res[2] < 0: losers.add(pos['leg'])
                    pos = None
            if i == 30:
                break
            # ---- entry gate (flat, entries 10:00..11:55)
            if pos or i > 23 or locked or n_ent >= 3: continue
            g = self.gate(d, K)
            if g is None: return
            cands = []
            if self.rng:                                        # control: random proxy/direction, same A1 / sizing / exits
                if self.rng.random() < self.q:
                    p = self.rng.choice(PROXIES); sd = self.rng.choice((1, -1)); leg = ROWS[p][0] if sd > 0 else ROWS[p][1]
                    ok = leg not in losers and dist.get(leg, 0) < 2 and not (len(dist) >= 2 and leg not in dist) \
                        and not (leg in first_rvol and reentries >= 1)
                    if ok: cands.append((p, leg, dict(g[p], side=sd, orh=-1e9, orl=1e9)))
                g = {}
            for p, s in g.items():
                if not (s['pass1'] and s['run'] >= 2 and s['side'] and s['vol_ok']): continue
                leg = ROWS[p][0] if s['side'] > 0 else ROWS[p][1]
                if leg in losers or dist.get(leg, 0) >= 2: continue
                if len(dist) >= 2 and leg not in dist: continue
                if n_ent >= 1 and self.momentum:
                    c3 = s['closes']
                    if len(c3) < 3 or s['side'] * (c3[-1] - c3[0]) <= 0: continue
                if leg in first_rvol:
                    if reentries >= 1: continue
                    if (first_rvol[leg] - s['rvol']) / first_rvol[leg] >= 0.30: continue
                cands.append((p, leg, s))
            if not cands: continue
            ordered = sorted(cands, key=lambda x: -x[2]['score'])
            # C12 step 0: profitable exit -> same-leg shortcut needs a fresh extreme (proxy beyond its run extreme)
            if last_exit and last_exit['win'] and last_exit['i'] == i:
                for c in list(ordered):
                    p0, leg0, s0 = c
                    if leg0 == last_exit['leg'] and p0 == last_exit['proxy']:
                        bars = D.bars[p0][d]; ex = last_exit['pos']
                        seg = bars[ex['K0']:ex['exit_bar'] + 1]
                        ext = max(b[1] for b in seg) if s0['side'] > 0 else min(b[2] for b in seg)
                        cl = [b[3] for b in bars[K - 2:K]]
                        fresh = all(x > ext for x in cl) if s0['side'] > 0 else all(x < ext for x in cl)
                        if fresh:
                            ordered.remove(c); ordered.insert(0, c)
            for p, leg, s in ordered:
                # C8 review: proxy still beyond the range at the entry bar's open
                po = D.bars[p][d][K][0]
                if not self.rng:
                    if s['side'] > 0 and po <= s['orh']: continue
                    if s['side'] < 0 and po >= s['orl']: continue
                lb = D.bars[leg].get(d)
                if not lb: continue
                ask = lb[K][0] * (1 + self.cost)
                stop = floor_tick(min(b[2] for b in lb[:6]))
                if stop <= 0 or ask <= stop: continue
                acct = cash
                budget = acct * (0.005 if (self.throttle and self.thr_on) else 0.03)
                sh = math.floor(min(cash / ask, budget / (ask - stop)))
                if sh < 1: continue
                stall, mm = profile(D.daily, leg, d)
                pos = dict(leg=leg, proxy=p, side=s['side'], shares=sh, entry=ask, stop=stop, stop0=stop, stall=stall, mm=mm,
                           K0=K, run_high=ask, rvol=s['rvol'], score=s['score'], i0=i, acct0=acct, exp=s['exp'], thr=bool(self.throttle and self.thr_on))
                cash -= sh * ask
                if leg in dist: reentries += 1
                else: first_rvol[leg] = s['rvol']
                dist[leg] = dist.get(leg, 0) + 1; n_ent += 1
                break
            # (checkpoint ends)
        self.eq = cash

    def advance(self, pos, d, K):
        """Walk bars from the last processed bar up to K-1 (inclusive): stop test, then (at the checkpoint) ratchet. If
        K == 36 close at the open of bar 36."""
        lb = self.D.bars[pos['leg']][d]
        j0 = pos.get('next', pos['K0'])
        for j in range(j0, K):
            o, h, l, c, v = lb[j]
            if l <= pos['stop']:
                fill = min(pos['stop'], o) * (1 - self.cost)
                pos['exit_bar'] = j
                return self._res(pos, fill, 'stop')
            pos['run_high'] = max(pos['run_high'], h)
            pos['last_close'] = c
            pos['next'] = j + 1
        if K == 36:
            fill = lb[36][0] * (1 - self.cost)
            pos['exit_bar'] = 36
            return self._res(pos, fill, 'close')
        # ratchet at this checkpoint (decision off completed bars; effective from bar K)
        if self.ratchet and pos['next'] > pos['K0']:
            live = pos['last_close']
            if live > pos['entry']:
                cand = floor_tick(pos['run_high'] * (1 - 2 * pos['stall']))
                if live > cand and cand - pos['stop'] >= pos['mm'] * pos['entry']:
                    pos['stop'] = cand
        return None

    def _res(self, pos, fill, why):
        pnl = (fill - pos['entry']) * pos['shares']
        return (fill, why, pnl)

    def close(self, pos, res, d, cash):
        fill, why, pnl = res
        cash += pos['shares'] * fill
        pct = (fill - pos['entry']) / pos['entry'] * 100
        win = pnl > 0
        if pnl < 0:
            self.streak += 1
            if self.streak >= 3: self.thr_on = True
            self.thr_wins = 0
        else:
            self.streak = 0
            if self.thr_on:
                self.thr_wins += 1
                if self.thr_wins >= 2: self.thr_on = False; self.thr_wins = 0
        self.trades.append(dict(day=d, leg=pos['leg'], proxy=pos['proxy'], side=pos['side'], shares=pos['shares'],
                                entry=round(pos['entry'], 4), exit=round(fill, 4), pnl=round(pnl, 2), pct=round(pct, 3),
                                acct_pct=round(pnl / pos['acct0'] * 100, 3), why=why, stop0=pos['stop0'], stop_final=pos['stop'],
                                entry_chk=pos['i0'], hold_bars=pos['exit_bar'] - pos['K0'] + 1, rvol=round(pos['rvol'], 2),
                                score=round(pos['score'], 2), thr=pos['thr']))
        return cash

    def run(self):
        for d in self.D.days:
            e0 = self.eq
            self.run_day(d)
            self.day_eq.append((d, self.eq))
        return self


def summarize(sim, label=''):
    t = sim.trades; days = sim.day_eq
    start = 2000.0
    pnls = [x['pnl'] for x in t]; pcts = [x['pct'] for x in t]
    wins = [x for x in pnls if x > 0]; losses = [x for x in pnls if x < 0]
    eqs = [e for _, e in days]; peak = 0; mdd = 0
    for e in [start] + eqs:
        peak = max(peak, e); mdd = max(mdd, (peak - e) / peak)
    dpct = []
    prev = start
    for _, e in days:
        dpct.append((e - prev) / prev * 100); prev = e
    traded_days = len(set(x['day'] for x in t))
    s = dict(label=label, days=len(days), trading_days_with_trade=traded_days, trades=len(t),
             win_rate=len(wins) / len(t) * 100 if t else 0, avg_pos_pct=st.mean(pcts) if t else 0,
             avg_win=st.mean(wins) if wins else 0, avg_loss=st.mean(losses) if losses else 0,
             profit_factor=sum(wins) / -sum(losses) if losses else float('inf'),
             net=sum(pnls), final_eq=eqs[-1] if eqs else start, ret_pct=((eqs[-1] / start - 1) * 100) if eqs else 0,
             avg_day_pct=st.mean(dpct) if dpct else 0, med_day_pct=st.median(dpct) if dpct else 0,
             best_day=max(dpct) if dpct else 0, worst_day=min(dpct) if dpct else 0, max_dd=mdd * 100,
             pos_days=sum(1 for x in dpct if x > 0.0005), neg_days=sum(1 for x in dpct if x < -0.0005),
             stops=sum(1 for x in t if x['why'] == 'stop'), closes=sum(1 for x in t if x['why'] == 'close'))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cost', type=float, default=0.03, help='per-side cost, percent of price')
    ap.add_argument('--no-throttle', action='store_true'); ap.add_argument('--no-ratchet', action='store_true')
    ap.add_argument('--no-volume-test', action='store_true'); ap.add_argument('--no-momentum', action='store_true')
    ap.add_argument('--csv'); a = ap.parse_args()
    sim = Sim(cost=a.cost / 100, throttle=not a.no_throttle, ratchet=not a.no_ratchet, vol_test=not a.no_volume_test,
              momentum=not a.no_momentum).run()
    s = summarize(sim)
    for k, v in s.items(): print(f'{k:>24}: {v:.3f}' if isinstance(v, float) else f'{k:>24}: {v}')
    if a.csv and sim.trades:
        with open(a.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(sim.trades[0])); w.writeheader(); w.writerows(sim.trades)


if __name__ == '__main__':
    main()
