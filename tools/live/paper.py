#!/usr/bin/env python3
"""Paper-trading engine for the fade + pullback systems (RULEBOOK C13, v3.127). No orders are ever placed by this tool.

Usage at a checkpoint (after saving today's + the prior session's 5-minute bars with get_equity_historicals):
    python3 tools/live/paper.py --now 10:35 DUMP [DUMP ...]            # status: what the paper account holds / did today
    python3 tools/live/paper.py --now 13:30 --close DUMP [DUMP ...]    # 13:30 close: append today's trades to archive/paper_trades.csv
Symbols needed in the dumps (three calls, max 10 symbols each):
    QQQ SOXX IWM XLK XBI AMD TQQQ SQQQ SOXL SOXS
    TNA TZA TECL TECS LABU LABD AMDL AMDD BTCZ UVXY
    IBIT   (read-only: RVOL tie-break for BTCZ pullbacks)
Range: from the prior trading day's 9:30 ET to now, interval 5minute.

Everything is recomputed from the bars on every run (deterministic, no intraday state), exactly as tools/backtest computes it:
  FADE (tools/backtest/retest.py fade + fade_combo.py exit) and PULLBACK (tools/backtest/pb_final.py), one shared paper account.
Only COMPLETED 5-minute bars are used: at --now HH:MM the last bar used is the one that ended at HH:MM.
"""
import argparse, csv, glob, json, math, os, statistics as st, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
LOG = os.path.join(ROOT, 'archive', 'paper_trades.csv')
STATE = os.path.join(ROOT, 'archive', 'paper_state.json')

FADE_ROWS = {'QQQ': ('TQQQ', 'SQQQ', 3, 3), 'SOXX': ('SOXL', 'SOXS', 3, 3), 'IWM': ('TNA', 'TZA', 3, 3), 'XLK': ('TECL', 'TECS', 3, 3),
             'XBI': ('LABU', 'LABD', 3, 3), 'AMD': ('AMDL', 'AMDD', 2, 1)}     # proxy: (bull leg, inverse leg, bull leverage, inverse leverage)
PB_LIST = ['SOXS', 'SQQQ', 'TZA', 'TECS', 'BTCZ', 'LABD', 'UVXY']     # tie order for same-bar pullback triggers
SELL_BY = 47            # bar index of the 13:25-13:30 bar; positions are sold at its close (13:30)
MAX_ENTRIES = 3
RISK = 0.03
FADE_COST = 0.06        # % round trip on the leg
PB_IN, PB_OUT = 0.0001, 0.0003


def t2k(hhmm):
    h, m = map(int, hhmm.split(':')); return (h * 60 + m - 570) // 5


def k2t(k):
    n = 570 + 5 * k; return f"{n // 60}:{n % 60:02d}"


# ------------------------------------------------------------------ data
def load(paths):
    raw = {}
    for f in paths:
        res = json.load(open(f))['data']['results']
        for r in res:
            if r.get('interval') != '5minute': continue
            for b in r['bars']:
                if b.get('interpolated') or not b['volume']: continue
                t = datetime.fromisoformat(b['begins_at'].replace('Z', '+00:00')).astimezone(ET)
                if not (570 <= t.hour * 60 + t.minute < 960): continue
                raw.setdefault(r['symbol'], {}).setdefault(t.date().isoformat(), {})[t.hour * 60 + t.minute] = (
                    float(b['open_price']), float(b['high_price']), float(b['low_price']), float(b['close_price']), b['volume'])
    return raw


def grid(day_bars, nbars):
    out, prev = [], None
    for k in range(nbars):
        b = day_bars.get(570 + 5 * k)
        if b: prev = b[3]; out.append(b)
        elif prev is not None: out.append((prev, prev, prev, prev, 0))
        else: out.append(None)
    first = next((b for b in out if b), None)
    if first is None: return None
    return [b if b else (first[0],) * 4 + (0,) for b in out]


def ema(vals, n):
    k = 2 / (n + 1); out = []; e = None
    for v in vals:
        e = v if e is None else e + k * (v - e); out.append(e)
    return out


def atr(b, j, n=14):
    trs = [max(b[i][1] - b[i][2], abs(b[i][1] - b[i - 1][3]), abs(b[i][2] - b[i - 1][3])) for i in range(max(1, j - n + 1), j + 1)]
    return st.mean(trs) if trs else 0.0


def mirror(b):
    p0 = b[0][0]
    return [(2 * p0 - o, 2 * p0 - l, 2 * p0 - h, 2 * p0 - c, v) for (o, h, l, c, v) in b], p0


# ------------------------------------------------------------------ FADE
def fade(b, K):
    """b = proxy bars (completed bars 0..K-1). Returns a trade dict (possibly still open) or None."""
    if K < 8: return None
    H, L = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
    for j in range(6, min(9, K)):
        cl = b[j][3]; bside = 1 if cl > H else -1 if cl < L else 0
        if not bside: continue
        bb, p0 = (b, None) if bside > 0 else mirror(b)
        to_m = (lambda x: x) if bside > 0 else (lambda x, p0=p0: 2 * p0 - x)
        E = to_m(H if bside > 0 else L)
        for i in range(j + 1, min(j + 13, 76)):
            if i >= K: return dict(status='watching', note=f'break {"up" if bside > 0 else "down"} at {k2t(j)}, waiting for a retest')
            o, h, l, cc, v = bb[i]
            if l <= E * (1 + 0.10 / 100):
                if cc < E:
                    side = -bside
                    stop_real = to_m(max(bb[q][1] for q in range(j, i + 1)))
                    if i + 1 >= K:
                        return dict(status='signal', side=side, k=i + 1, stop=stop_real,
                                    note=f'failed retest at {k2t(i)}: paper-buy the {"bull" if side > 0 else "inverse"} leg at the {k2t(i + 1)} open (this checkpoint)')
                    return fade_manage(b, K, i + 1, side, b[i + 1][0], stop_real)
                return None
        return None
    return None


def fade_manage(raw, K, k, side, e_real, stop_real, R=2.0, frac=1 / 3):
    b, p0 = (raw, None) if side > 0 else mirror(raw)
    to_m = (lambda x: x) if side > 0 else (lambda x, p0=p0: 2 * p0 - x)
    entry, stop = to_m(e_real), to_m(stop_real)
    if entry <= stop or k >= SELL_BY: return None
    r = entry - stop; T = entry + R * r
    gross = 0.0; rem = 1.0; hit = False; hic = entry; events = []
    end = min(SELL_BY, K - 1); closed = False; xbar = None; why = None
    for j in range(k, end + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross += rem * (px - entry); events.append((k2t(j), 'stop' if not hit else 'ratchet stop', to_m(px), rem)); rem = 0
            closed = True; xbar = j; why = 'stop' if not hit else 'ratchet stop'; break
        if not hit and h >= T:
            px = max(T, o); gross += frac * (px - entry); rem -= frac; hit = True; stop = max(stop, entry)
            events.append((k2t(j), 'take profit 1/3 at 2R', to_m(px), frac))
        hic = max(hic, c)
        if hit and j < SELL_BY: stop = max(stop, hic - 2 * atr(b, j))
    if not closed and K - 1 >= SELL_BY:
        px = b[SELL_BY][3]; gross += rem * (px - entry); events.append(('13:30', 'time exit', to_m(px), rem)); rem = 0
        closed = True; xbar = SELL_BY; why = 'time'
    lev = None
    return dict(status='closed' if closed else 'open', side=side, k=k, xbar=xbar, why=why, entry=e_real, stop0=stop_real,
                stop_now=to_m(stop), target=to_m(T), gross=gross, rem=rem, events=events, risk_pct=r / e_real * 100)


# ------------------------------------------------------------------ PULLBACK
def pullback(b, prev, K):
    """b = leg bars (completed 0..K-1), prev = prior session's bars. Returns a trade dict or None."""
    ser = [x[3] for x in prev] + [x[3] for x in b[:K]]
    e9 = ema(ser, 9)[len(prev):]; e20 = ema(ser, 20)[len(prev):]
    bh = max(x[1] for x in b[:3])
    for j in range(8, min(41, K)):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = max(b[i][1] for i in range(0, pre)); stop = low * (1 - 0.05 / 100); lim = b[j][3]
            if j + 1 >= K:
                if hod <= lim or lim <= stop or (lim - stop) / lim * 100 < 0.75: continue
                if (hod - lim) < 0.75 * (lim - stop) or (hod - lim) / lim * 100 < 0.25 or hod - stop < 0.10: continue
                return dict(status='signal', k=j + 1, limit=lim, stop=stop, target=hod,
                            note=f'trigger at {k2t(j)}: limit buy {lim:.2f}, valid for the {k2t(j + 1)} bar only')
            if b[j + 1][2] > lim: continue
            entry = min(b[j + 1][0], lim)
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < 0.75: continue
            if (hod - entry) < 0.75 * (entry - stop) or (hod - entry) / entry * 100 < 0.25: continue
            if hod - stop < 0.10: continue
            return pb_manage(b, K, j + 1, entry, stop, hod)
    return None


def pb_manage(b, K, k, entry, stop, T):
    if k > SELL_BY: return None
    end = min(SELL_BY, K - 1); gross = 0.0; cost = PB_IN * entry; closed = False; xbar = None; why = None; ev = []
    for j in range(k, end + 1):
        o, h, l, c, v = b[j]
        if l <= stop:
            px = min(stop, o); gross = px - entry; cost += PB_OUT * px; closed = True; xbar = j; why = 'stop'; ev.append((k2t(j), 'stop', px)); break
        if h >= T:
            px = max(T, o); gross = px - entry; cost += PB_OUT * px; closed = True; xbar = j; why = 'target'; ev.append((k2t(j), 'take profit 100%', px)); break
    if not closed and K - 1 >= SELL_BY:
        px = b[SELL_BY][3]; gross = px - entry; cost += PB_OUT * px; closed = True; xbar = SELL_BY; why = 'time'; ev.append(('13:30', 'time exit', px))
    return dict(status='closed' if closed else 'open', k=k, xbar=xbar, why=why, entry=entry, stop0=stop, target=T,
                gross=gross - cost if closed else None, events=ev, risk_pct=(entry - stop) / entry * 100)


# ------------------------------------------------------------------ day simulation (one shared paper account)
PB_PROXY = {'SOXS': 'SOXX', 'SQQQ': 'QQQ', 'TZA': 'IWM', 'TECS': 'XLK', 'BTCZ': 'IBIT'}


def rvol(today, base, p, k):
    """Proxy RVOL at bar k: today's cumulative volume through bar k-1 / the 20-session average of the same (tie-break only)."""
    if not base or p not in base or p not in today or not base[p][k]: return 0.0
    return sum(b[4] for b in today[p][:k]) / base[p][k]


def simulate(today, prev, K, equity, base=None):
    """today/prev: {sym: [bars]}; base = {proxy: [avg cumulative volume through bar k]} for the RVOL tie-break.
    Returns (taken, skipped, signals, equity_after)."""
    cands, signals = [], []
    for p, (bull, bear, lev_bull, lev_bear) in FADE_ROWS.items():
        if p not in today: continue
        t = fade(today[p], K)
        if not t: continue
        if t['status'] in ('watching', 'signal'): signals.append(('FADE', p, t)); continue
        leg = bull if t['side'] > 0 else bear; lev = lev_bull if t['side'] > 0 else lev_bear
        t.update(system='FADE', proxy=p, ticker=leg, lev=lev, order=0, leg_entry=today[leg][t['k']][0] if leg in today else None)
        cands.append(t)
    for i, leg in enumerate(PB_LIST):
        if leg not in today or leg not in prev: continue
        t = pullback(today[leg], prev[leg], K)
        if not t: continue
        if t['status'] == 'signal': signals.append(('PB', leg, t)); continue
        t.update(system='PB', proxy='-', ticker=leg, lev=1, order=1 + i, leg_entry=t['entry'])
        cands.append(t)
    cands.sort(key=lambda c: (c['k'], -rvol(today, base, c['proxy'] if c['system'] == 'FADE' else PB_PROXY.get(c['ticker'], ''), c['k']), c['order']))
    taken, skipped, free, eq = [], [], 0, equity
    for c in cands:
        if len(taken) >= MAX_ENTRIES or c['k'] < free:
            skipped.append(c); continue
        if c['system'] == 'FADE':
            leg_risk = c['lev'] * c['risk_pct']
            pct = (c['lev'] * c['gross'] / c['entry'] * 100 - FADE_COST) if c['status'] == 'closed' else None
        else:
            leg_risk = c['risk_pct']; pct = c['gross'] / c['entry'] * 100 if c['status'] == 'closed' else None
        notional = min(eq, eq * RISK / (leg_risk / 100))
        c.update(leg_risk=leg_risk, notional=notional, pct=pct, usd=notional * pct / 100 if pct is not None else None)
        if pct is not None: eq += c['usd']
        taken.append(c)
        free = (c['xbar'] + 1) if c['status'] == 'closed' else 10 ** 6
    # a signal is only actionable if the account would be free for it
    signals = [s for s in signals if len(taken) < MAX_ENTRIES and s[2].get('k', K) >= free]
    return taken, skipped, signals, eq


def state():
    if os.path.exists(STATE): return json.load(open(STATE))
    return {'equity': 2000.0, 'start': None, 'days_logged': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumps', nargs='+'); ap.add_argument('--now', required=True, help='ET time of the checkpoint, HH:MM')
    ap.add_argument('--day', help='ET date (default: latest date in the dumps)'); ap.add_argument('--close', action='store_true')
    ap.add_argument('--build-rvol', action='store_true', help='9:00: build the 20-session RVOL baseline for --day from the dumps (5-min bars of the 5 proxies, prior 20 sessions)')
    a = ap.parse_args()
    raw = load([f for g in a.dumps for f in glob.glob(g)])
    days = sorted({d for s in raw.values() for d in s})
    day = a.day or days[-1]
    if a.build_rvol:
        prior = [d for d in days if d < day][-20:]
        base = {p: [st.mean(sum(b[4] for b in g[:k]) for d in prior for g in [grid(raw[p][d], 78)] if g) for k in range(79)]
                for p in list(FADE_ROWS) + ['IBIT'] if p in raw and all(d in raw[p] for d in prior)}
        out = os.path.join(ROOT, 'archive', f'paper_rvol_{day}.json'); json.dump({'day': day, 'sessions': prior, 'base': base}, open(out, 'w'))
        print(f"RVOL baseline for {day} from {len(prior)} sessions ({prior[0]}..{prior[-1]}), proxies {sorted(base)} -> {out}"); return
    prevday = max(d for d in days if d < day)
    K = min(78, t2k(a.now))
    today = {s: g for s in raw if day in raw[s] for g in [grid(raw[s][day], K)] if g}
    prev = {s: g for s in raw if prevday in raw[s] for g in [grid(raw[s][prevday], 78)] if g}
    S = state(); eq0 = S['equity']
    bf = os.path.join(ROOT, 'archive', f'paper_rvol_{day}.json')
    base = json.load(open(bf))['base'] if os.path.exists(bf) else None
    if not base: print("  (no RVOL baseline for today - same-bar ties fall back to list order; run --build-rvol at 9:00)")
    taken, skipped, signals, eq = simulate(today, prev, K, eq0, base)
    print(f"PAPER {day} at {a.now} ET (bars through {k2t(K)}), paper equity at open ${eq0:,.2f}")
    if not taken and not signals: print("  no paper trades or live signals")
    for c in taken:
        head = f"  {c['system']:<4} {c['ticker']:<5}" + (f" (fade of {c['proxy']})" if c['system'] == 'FADE' else '') + \
               f" entered {k2t(c['k'])} @ {c['leg_entry']:.2f}" + (f" [proxy {c['entry']:.2f}]" if c['system'] == 'FADE' else '') + \
               f", stop {c['stop0']:.2f}{' (proxy)' if c['system'] == 'FADE' else ''}, target {c['target']:.2f}, notional ${c['notional']:,.0f}"
        print(head)
        for e in c['events']: print(f"       {e[0]} {e[1]} at {e[2]:.2f}" + (f" ({e[3]:.0%})" if len(e) > 3 else ''))
        if c['status'] == 'open':
            print(f"       OPEN: " + (f"current stop {c['stop_now']:.2f} (proxy), remaining {c['rem']:.0%}" if c['system'] == 'FADE' else 'OCO resting (target / stop)'))
        else:
            print(f"       CLOSED {c['why']}: {c['pct']:+.2f}% on {c['ticker']} = ${c['usd']:+.2f}")
    for s in skipped: print(f"  skipped (account busy or 3 entries used): {s['system']} {s['ticker']} at {k2t(s['k'])}")
    for sysn, sym, t in signals: print(f"  SIGNAL {sysn} {sym}: {t['note']}")
    open_ = [c for c in taken if c['status'] == 'open']
    cadence = '5 min (fade open: ratchet the stop)' if any(c['system'] == 'FADE' for c in open_) else \
              ('30 min (pullback OCO resting)' if open_ else ('5 min (flat, scanning)' if K < 41 and len(taken) < MAX_ENTRIES else 'none needed until 13:30'))
    print(f"  entries used {len(taken)}/{MAX_ENTRIES}; next check-in: {cadence}; paper equity now ${eq:,.2f}")
    if a.close:
        if K - 1 < SELL_BY: sys.exit('--close needs --now 13:30 or later')
        if day in S['days_logged']: print('  already logged'); return
        new = not os.path.exists(LOG)
        with open(LOG, 'a', newline='') as f:
            w = csv.writer(f)
            if new: w.writerow(['day', 'system', 'proxy', 'ticker', 'entry_time', 'entry_px_leg', 'stop', 'target', 'exit_time', 'exit_reason',
                                'pct_leg', 'notional_usd', 'pnl_usd', 'equity_after'])
            e = eq0
            for c in taken:
                e += c['usd']
                w.writerow([day, c['system'], c['proxy'], c['ticker'], k2t(c['k']), f"{c['leg_entry']:.4f}", f"{c['stop0']:.4f}", f"{c['target']:.4f}",
                            k2t(c['xbar']), c['why'], f"{c['pct']:.3f}", f"{c['notional']:.2f}", f"{c['usd']:.2f}", f"{e:.2f}"])
        S['equity'] = round(eq, 2); S['days_logged'].append(day); S['start'] = S['start'] or day
        json.dump(S, open(STATE, 'w'), indent=1)
        print(f"  logged {len(taken)} trade(s) to archive/paper_trades.csv; paper equity ${eq:,.2f}")


if __name__ == '__main__':
    main()
