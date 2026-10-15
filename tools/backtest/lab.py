#!/usr/bin/env python3
"""Configurable version of backtest.py used to test every parked suggestion on the same data.
`Cfg()` with defaults reproduces the live rules (and backtest.py's baseline). See run_suggestions.py.
"""
import math, random, statistics as st
from dataclasses import dataclass, field
from backtest import Data, ROWS as ROWS8, PROXIES as P8, profile, floor_tick

IDX = {'SPY', 'QQQ', 'IWM'}
LEV = {'QQQ': 3, 'SPY': 3, 'SOXX': 3, 'IWM': 3, 'XLF': 3, 'XLE': 2, 'TLT': 3, 'XBI': 3,
       'XLU': 3, 'XLRE': 3, 'XOP': 2, 'EEM': 3}
_DATA = None
_FEAT = {}


def get_data():
    global _DATA
    if _DATA is None: _DATA = Data()
    return _DATA


@dataclass
class Cfg:
    cost: float = 0.0003
    rows: tuple = tuple(P8)
    extra_rows: dict = field(default_factory=dict)       # proxy -> (long, inverse) for added themes
    or_bars: int = 6
    confirm: int = 2
    idx_confirm1: bool = False
    vol_K_end: int = 18          # volume test applies while K < this (18 = before 11:00); 0 = never; 999 = all day
    momentum: str = 'v319'       # 'v319' | 'off' | 'strict'
    atr_skip: float = None
    rank: str = 'score'
    throttle: bool = True
    ratchet: bool = True
    trail_mult: float = 2.0
    trail_decay: bool = False
    first_stall: float = None    # fixed stall (fraction) for the first trade of the day
    tp: dict = None              # {'kind':'pos'|'acct','val':%,'scope':'first'|'all'|'fresh','half':bool}
    be_after: float = None       # % gain trigger -> stop to entry
    be_1r: bool = False
    lock: tuple = None           # (trigger %, fraction of gain)
    close_K: int = 36
    flat_exit: float = None
    day_done: tuple = None       # ('day', pct) | ('trade', pct)
    stop_mode: object = 'or_low' # 'or_low' | ('pct', x) | 'mid'
    target_R: float = None
    max_entries: int = 3
    max_reentries: int = 1
    entry_end_K: int = 29
    seed: int = None
    stop_cap: float = None       # v3.74-style ceiling: skip if stop is further than this % below the entry
    playbook: bool = False       # 15-min playbook: half at 1R, rest at 2R, no ratchet


def feat(d, K, nb, proxies):
    """Cached per-proxy raw features at checkpoint (d,K) for opening range nb bars."""
    key = (d, K, nb, proxies)
    if key in _FEAT: return _FEAT[key]
    D = get_data(); pri = D.prior(d, 20); pr14 = D.prior(d, 15)
    out = {}
    if len(pri) < 20 or len(pr14) < 15: _FEAT[key] = None; return None
    rv = {}
    for p in proxies:
        base = st.mean(D.cum[p][x][K] for x in pri)
        rv[p] = D.cum[p][d][K] / base if base else 0.0
    for p in proxies:
        bars = D.bars[p][d][:K]
        orb = bars[:nb]; orh, orl = max(b[1] for b in orb), min(b[2] for b in orb)
        post = [b[3] for b in bars[nb:]]
        run = side = 0
        for c in post:
            sd = 1 if c > orh else -1 if c < orl else 0
            run = run + 1 if sd and sd == side else (1 if sd else 0)
            side = sd
        tr = []
        for a, b in zip(pr14, pr14[1:]):
            h, l, _ = D.dhlc[p][b]; pc = D.dhlc[p][a][2]
            tr.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = st.mean(tr[-14:])
        hi, lo = max(b[1] for b in bars), min(b[2] for b in bars)
        trig = nb + len(post) - run if run else None
        vol_pass = None
        if run:
            prev = [b[4] for b in bars[max(0, trig - 3):trig]]
            vol_pass = bool(prev) and bars[trig][4] > sum(prev) / len(prev)
        dayopen = D.bars[p][d][0][0]
        out[p] = dict(rvol=rv[p], orh=orh, orl=orl, run=run, side=side if run else 0, trig=trig, vol_pass=vol_pass,
                      exp=(hi - lo) / atr, atr=atr, last=bars[-1][3], pct=bars[-1][3] / dayopen - 1, c3=post[-3:], hi=hi, lo=lo)
    passing = [p for p in proxies if rv[p] >= 1.0]
    if len(passing) < 3: passing = sorted(proxies, key=lambda p: -rv[p])[:3]
    for p in proxies: out[p]['pass1'] = p in passing
    _FEAT[key] = out
    return out


def rank_key(cfg, c, K, rng):
    r = cfg.rank
    if r == 'score': return c['score']
    if r == 'latest_before_1030': return (c['trig'] if K < 12 else 0, c['score'])
    if r == 'latest_all': return (c['trig'], c['score'])
    if r == 'most_room': return 1 - c['exp']
    if r == 'widest_stop': return c['stopd']
    if r == 'tightest_stop': return -c['stopd']
    if r == 'highest_rvol': return c['rvol']
    if r == 'earliest': return -c['trig']
    if r == 'most_range': return c['exp']
    if r == 'strongest_break': return c['brk']
    if r == 'rvol_x_break': return c['rvol'] * c['brk']
    if r == 'rs_ratio':
        sp = c['spct'] if abs(c['spct']) > 0.0005 else 0.0005 * (1 if c['spct'] >= 0 else -1)
        return c['score'] * ((c['side'] * c['pct']) / (c['side'] * sp) if c['proxy'] != 'SPY' else 1.0)
    if r == 'rs_diff': return c['score'] * (1 + 100 * c['side'] * (c['pct'] - c['spct']))
    if r == 'idx_x1.5': return c['score'] * (1.5 if c['proxy'] in IDX else 1.0)
    if r == 'room_lev': return (1 - c['exp']) * c['atr_pct'] * c['lev'] * c['rvol']
    if r == 'pct_room': return (1 - c['exp']) * c['atr_pct'] * c['rvol']
    if r == 'speed': return c['atr_pct'] * c['rvol']
    if r == 'random': return rng.random()
    raise ValueError(r)


class Lab:
    def __init__(self, cfg, start_equity=2000.0):
        self.cfg = cfg; self.D = get_data(); self.eq = start_equity
        self.rows = {p: ROWS8.get(p) or cfg.extra_rows[p] for p in cfg.rows}
        self.proxies = tuple(cfg.rows)
        self.streak = 0; self.thr_on = False; self.thr_wins = 0
        self.trades = []; self.day_eq = []; self.rng = random.Random(cfg.seed or 0)

    # ------------------------------------------------------------------------------------
    def run(self):
        for d in self.D.days:
            self.run_day(d)
            self.day_eq.append((d, self.eq))
        return self

    def run_day(self, d):
        c = self.cfg; D = self.D
        if len(D.prior(d, 20)) < 20: return
        cash = self.eq; day_start = self.eq; day_pnl = 0.0
        locked = self.streak >= 5
        if locked: self.streak = 0; self.thr_on = True; self.thr_wins = 0
        pos = None; last_exit = None
        losers = set(); n_ent = 0; dist = {}; first_rvol = {}; reentries = 0; done = False
        for K in range(c.or_bars, c.close_K + 1):
            if pos:
                res = self.advance(pos, d, K)
                if res:
                    pnl = res['pnl']; cash += res['cash']
                    self.record(pos, res, d)
                    day_pnl += pnl
                    last_exit = dict(pos=pos, K=K, win=pnl > 0, leg=pos['leg'], proxy=pos['proxy'], tp=res['why'] == 'tp')
                    if pnl < 0: losers.add(pos['leg'])
                    if c.day_done:
                        kind, x = c.day_done
                        if kind == 'day' and day_pnl / day_start * 100 >= x: done = True
                        if kind == 'trade' and pnl / pos['acct0'] * 100 >= x: done = True
                    pos = None
            if K >= c.close_K: break
            if pos or locked or done or n_ent >= c.max_entries or K > c.entry_end_K: continue
            F = feat(d, K, c.or_bars, self.proxies)
            if F is None: return
            cands = []
            for p in self.proxies:
                s = F[p]
                if not (s['pass1'] and s['side']): continue
                need = 1 if (c.idx_confirm1 and p in IDX) else c.confirm
                if s['run'] < need: continue
                if s['run'] >= 2 and 0 < K < c.vol_K_end and not s['vol_pass']: continue
                if need == 1 and s['run'] == 1 and K < c.vol_K_end and not s['vol_pass']: continue
                leg = self.rows[p][0] if s['side'] > 0 else self.rows[p][1]
                if leg in losers or dist.get(leg, 0) >= 2: continue
                if len(dist) >= 2 and leg not in dist: continue
                if n_ent >= 1 and c.momentum != 'off':
                    c3 = s['c3']
                    if len(c3) < 3: continue
                    if c.momentum == 'v319' and s['side'] * (c3[-1] - c3[0]) <= 0: continue
                    if c.momentum == 'strict' and not (s['side'] * (c3[2] - c3[1]) > 0 and s['side'] * (c3[1] - c3[0]) > 0): continue
                if leg in first_rvol:
                    if reentries >= c.max_reentries: continue
                    if (first_rvol[leg] - s['rvol']) / first_rvol[leg] >= 0.30: continue
                far = s['orl'] if s['side'] > 0 else s['orh']; edge = s['orh'] if s['side'] > 0 else s['orl']
                spy = F['SPY'] if 'SPY' in F else None
                cd = dict(proxy=p, leg=leg, side=s['side'], rvol=s['rvol'], exp=s['exp'], score=(1 - s['exp']) * s['rvol'],
                          trig=s['trig'], brk=s['side'] * (s['last'] - edge) / s['atr'], atr=s['atr'], atr_pct=s['atr'] / s['last'] * 100,
                          stopd=abs(s['last'] - far) / s['last'] * 100 * LEV[p], lev=LEV[p], pct=s['pct'],
                          spct=spy['pct'] if spy else 0.0, orh=s['orh'], orl=s['orl'], last=s['last'])
                cands.append(cd)
            if not cands: continue
            ordered = sorted(cands, key=lambda x: rank_key(c, x, K, self.rng), reverse=True)
            if last_exit and last_exit['win'] and last_exit['K'] == K:          # C12 step 0 (fresh extreme)
                for cd in list(ordered):
                    if cd['leg'] == last_exit['leg'] and cd['proxy'] == last_exit['proxy']:
                        ex = last_exit['pos']; seg = D.bars[cd['proxy']][d][ex['K0']:ex['exit_bar'] + 1]
                        ext = max(b[1] for b in seg) if cd['side'] > 0 else min(b[2] for b in seg)
                        cl = [b[3] for b in D.bars[cd['proxy']][d][K - 2:K]]
                        if (all(x > ext for x in cl) if cd['side'] > 0 else all(x < ext for x in cl)):
                            ordered.remove(cd); ordered.insert(0, cd)
            for cd in ordered:
                p, leg = cd['proxy'], cd['leg']
                po = D.bars[p][d][K][0]
                if cd['side'] > 0 and po <= cd['orh']: continue
                if cd['side'] < 0 and po >= cd['orl']: continue
                if c.atr_skip is not None and abs(po - (cd['orl'] if cd['side'] > 0 else cd['orh'])) > c.atr_skip * cd['atr']: continue
                lb = D.bars[leg].get(d)
                if not lb: continue
                ask = lb[K][0] * (1 + c.cost)
                orl_leg = min(b[2] for b in lb[:c.or_bars]); orh_leg = max(b[1] for b in lb[:c.or_bars])
                if c.stop_mode == 'or_low': stop = floor_tick(orl_leg)
                elif c.stop_mode == 'mid': stop = floor_tick((orl_leg + orh_leg) / 2)
                else: stop = floor_tick(ask * (1 - c.stop_mode[1] / 100))
                if stop <= 0 or ask <= stop: continue
                if c.stop_cap and (ask - stop) / ask * 100 > c.stop_cap: continue
                budget = cash * (0.005 if (c.throttle and self.thr_on) else 0.03)
                sh = math.floor(min(cash / ask, budget / (ask - stop)))
                if sh < 1: continue
                stall, mm = profile(D.daily, leg, d)
                if c.first_stall and n_ent == 0: stall = c.first_stall
                pos = dict(leg=leg, proxy=p, side=cd['side'], shares=sh, sh0=sh, entry=ask, stop=stop, stop0=stop, stall=stall,
                           mm=mm, K0=K, run_high=ask, rvol=cd['rvol'], score=cd['score'], i0=K - c.or_bars, acct0=cash,
                           thr=bool(c.throttle and self.thr_on), next=K, realized=0.0, fresh=(leg not in dist), nth=n_ent,
                           flat_hist=[], hist_hi=[])
                self.make_targets(pos, cash)
                cash -= sh * ask
                if leg in dist: reentries += 1
                else: first_rvol[leg] = cd['rvol']
                dist[leg] = dist.get(leg, 0) + 1; n_ent += 1
                break
        self.eq = cash

    # ------------------------------------------------------------------------------------
    def make_targets(self, pos, acct):
        c = self.cfg; e = pos['entry']; r = e - pos['stop']; tps = []
        if c.playbook:
            tps = [(e + r, 0.5), (e + 2 * r, 1.0)]
        elif c.tp:
            t = c.tp
            applies = (t['scope'] == 'all' or (t['scope'] == 'first' and pos['nth'] == 0) or (t['scope'] == 'fresh' and pos['fresh']))
            if applies:
                if t['kind'] == 'pos': price = e * (1 + t['val'] / 100)
                else: price = e + (t['val'] / 100 * acct) / pos['shares']
                tps.append((price, 0.5 if t.get('half') else 1.0))
        if c.target_R: tps.append((e + c.target_R * r, 1.0))
        pos['tps'] = sorted(tps)

    def advance(self, pos, d, K):
        c = self.cfg; lb = self.D.bars[pos['leg']][d]
        for j in range(pos['next'], K):
            o, h, l, cl, v = lb[j]
            if l <= pos['stop']:
                return self.finish(pos, min(pos['stop'], o), j, 'stop')
            for tp in list(pos['tps']):
                price, frac = tp
                if h >= price:
                    fill = max(price, o) * (1 - c.cost)
                    if frac >= 1.0 or pos['shares'] <= 1:
                        return self.finish(pos, max(price, o), j, 'tp')
                    q = max(1, int(pos['shares'] * frac))
                    pos['realized'] += (fill - pos['entry']) * q; pos['cashback'] = pos.get('cashback', 0.0) + q * fill
                    pos['shares'] -= q; pos['tps'].remove(tp)
                    if pos['shares'] <= 0: return self.finish(pos, price, j, 'tp')
                    if c.playbook: pos['stop'] = max(pos['stop'], pos['entry'])
            pos['run_high'] = max(pos['run_high'], h); pos['last_close'] = cl; pos['next'] = j + 1
            pos['hist_hi'].append(pos['run_high'])
        if K >= c.close_K:
            return self.finish(pos, lb[c.close_K][0], c.close_K, 'close', pre_cost=True)
        # ---- checkpoint management (decision off completed bars; effective from bar K)
        if pos['next'] > pos['K0']:
            live = pos['last_close']; e = pos['entry']
            if c.be_after is not None and pos['run_high'] >= e * (1 + c.be_after / 100): pos['stop'] = max(pos['stop'], e)
            if c.be_1r and pos['run_high'] - e >= (e - pos['stop0']): pos['stop'] = max(pos['stop'], e)
            if c.lock and pos['run_high'] >= e * (1 + c.lock[0] / 100):
                pos['stop'] = max(pos['stop'], floor_tick(e + c.lock[1] * (pos['run_high'] - e)))
            if c.ratchet and not c.playbook and live > e:
                mult = c.trail_mult
                if c.trail_decay: mult = 2.0 if K < 15 else 1.5 if K < 24 else 1.0
                cand = floor_tick(pos['run_high'] * (1 - mult * pos['stall']))
                if live > cand and cand - pos['stop'] >= pos['mm'] * e: pos['stop'] = cand
            if c.flat_exit and K >= 30:
                cls = [lb[j][3] for j in range(K - 4, K)]
                if (max(cls) - min(cls)) / e < c.flat_exit:
                    return self.finish(pos, lb[K][0], K, 'flat', pre_cost=True)
        return None

    def finish(self, pos, price, j, why, pre_cost=False):
        c = self.cfg
        fill = price * (1 - c.cost)
        pnl = (fill - pos['entry']) * pos['shares'] + pos['realized']
        cashback = pos['shares'] * fill + pos.get('cashback', 0.0)
        pos['exit_bar'] = j; pos['final_fill'] = fill
        return dict(pnl=pnl, cash=cashback, why=why, fill=fill)

    def record(self, pos, res, d):
        pnl = res['pnl']; cost_basis = pos['entry'] * pos['sh0']
        pct = pnl / cost_basis * 100
        if pnl < 0:
            self.streak += 1
            if self.streak >= 3: self.thr_on = True
            self.thr_wins = 0
        else:
            self.streak = 0
            if self.thr_on:
                self.thr_wins += 1
                if self.thr_wins >= 2: self.thr_on = False; self.thr_wins = 0
        self.trades.append(dict(day=d, leg=pos['leg'], proxy=pos['proxy'], side=pos['side'], shares=pos['sh0'], pnl=round(pnl, 2),
                                pct=round(pct, 3), acct_pct=round(pnl / pos['acct0'] * 100, 3), why=res['why'], entry_chk=pos['i0'],
                                nth=pos['nth'], thr=pos['thr']))


def daily_pct(lab, start=2000.0):
    prev = start; out = {}
    for d, e in lab.day_eq:
        out[d] = (e - prev) / prev * 100; prev = e
    return out


def stats(lab, start=2000.0):
    t = lab.trades; dp = list(daily_pct(lab, start).values())
    pn = [x['pnl'] for x in t]; w = [x for x in pn if x > 0]; ls = [x for x in pn if x < 0]
    eqs = [e for _, e in lab.day_eq]; peak = start; mdd = 0
    for e in [start] + eqs: peak = max(peak, e); mdd = max(mdd, (peak - e) / peak)
    return dict(trades=len(t), win=(len(w) / len(t) * 100 if t else 0), avg_trade=(st.mean(x['pct'] for x in t) if t else 0),
                avg_day=st.mean(dp) if dp else 0, ret=(eqs[-1] / start - 1) * 100 if eqs else 0, pf=(sum(w) / -sum(ls) if ls else 9.99),
                mdd=mdd * 100, worst=min(dp) if dp else 0)
