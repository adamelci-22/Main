#!/usr/bin/env python3
"""Signal and model engine for the fade + pullback systems (RULEBOOK Part B, v5.0). No orders are ever placed by this tool;
with --live it prints the real-order instructions that RULEBOOK B5 carries out.

Usage at a checkpoint (after saving today's + the prior session's 5-minute bars with get_equity_historicals):
    python3 tools/live/paper.py --now 10:35 DUMP [DUMP ...]            # status: what the paper account holds / did today
    python3 tools/live/paper.py --live --now 10:35 DUMP [DUMP ...]     # live checkpoint: status + LIVE ACTIONS (RULEBOOK C1)
    python3 tools/live/paper.py --now 13:30 --close DUMP [DUMP ...]    # 13:30 close: append today's trades to archive/paper_trades.csv
    python3 tools/live/paper.py --build-rvol --day YYYY-MM-DD --now 09:00 DUMP   # 9:00: RVOL baseline (RULEBOOK C3)
Symbols needed in the dumps (three calls, max 10 symbols each):
    QQQ SOXX IWM XLK XBI XLF TQQQ SQQQ SOXL SOXS
    TNA TZA TECL TECS LABU LABD FAS FAZ UVXY NVD
    NVDA   (read-only: RVOL tie-break for NVD pullbacks)
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
             'XBI': ('LABU', 'LABD', 3, 3), 'XLF': ('FAS', 'FAZ', 3, 3)}     # proxy: (bull leg, inverse leg, bull leverage, inverse leverage)
PB_LIST = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVD']     # tie order for same-bar pullback triggers
SELL_BY = 47            # bar index of the 13:25-13:30 bar; positions are sold at its close (13:30)
REAL_FREE = False       # --real-free: list LIVE signals even while the MODEL's own position is open (the governor closed the real one by hand; RULEBOOK A3/B4.2)
FLOOR_TARGET = True     # pullback take-profit = morning high rounded down to the cent; main() turns it off for days before FLOOR_FROM
FLOOR_FROM = '2026-10-19'   # RULEBOOK v5.1 effective date (2026-10-16's real LABD order was placed at the rounded-up 8.87)
LOCKOUT_LOSSES = 5      # 5 losing trades in a row -> no new entries until the governor clears it (RULEBOOK A1)
RISK = 0.03
FADE_COST = 0.06        # % round trip on the leg
PB_IN, PB_OUT = 0.0001, 0.0003
# RULEBOOK A1.10: no entries on early-close days or market holidays (NYSE). Extend each year from nyse.com/markets/hours-calendars.
NO_TRADE = {'2026-11-26': 'Thanksgiving (closed)', '2026-11-27': 'early close 13:00', '2026-12-24': 'early close 13:00', '2026-12-25': 'Christmas (closed)'}
CALENDAR_THROUGH = '2026-12-31'
EXPECTED = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'TQQQ', 'SQQQ', 'SOXL', 'SOXS', 'TNA', 'TZA', 'TECL', 'TECS', 'LABU', 'LABD',
            'FAS', 'FAZ', 'UVXY', 'NVD', 'NVDA']      # the three C1.2 fetch groups
SKIP = set()            # --skip: proxies/legs barred from REAL entries today (RULEBOOK A1.9 earnings); the model is unchanged


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
    # runner level the real account uses if ITS 1/3 take-profit filled before the model's (B5.4): breakeven, then the chandelier
    chand = max(entry, hic - 2 * atr(b, end)) if end >= k else entry
    return dict(status='closed' if closed else 'open', side=side, k=k, xbar=xbar, why=why, entry=e_real, stop0=stop_real,
                stop_now=to_m(stop), chand_if_done=to_m(chand), target=to_m(T), gross=gross, rem=rem, events=events, risk_pct=r / e_real * 100)


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
            if FLOOR_TARGET: hod = math.floor(hod * 100 + 1e-9) / 100      # the real take-profit limit: morning high rounded DOWN to the cent (RULEBOOK B3.9)
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
PB_PROXY = {'SOXS': 'SOXX', 'TECS': 'XLK', 'NVD': 'NVDA'}     # proxy RVOL used only to break same-bar ties


def rvol(today, base, p, k):
    """Proxy RVOL at bar k: today's cumulative volume through bar k-1 / the 20-session average of the same (tie-break only)."""
    if not base or p not in base or p not in today or not base[p][k]: return 0.0
    return sum(b[4] for b in today[p][:k]) / base[p][k]


def simulate(today, prev, K, equity, base=None, streak=0):
    """today/prev: {sym: [bars]}; base = {proxy: [avg cumulative volume through bar k]} for the RVOL tie-break.
    streak = consecutive losing trades carried in from earlier days (lockout at LOCKOUT_LOSSES).
    Returns (taken, skipped, signals, equity_after); each taken trade carries the streak after it in c['streak']."""
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
        if streak >= LOCKOUT_LOSSES:
            c['why_skipped'] = 'LOCKOUT (5 losses in a row)'; skipped.append(c); continue
        if c['k'] < free:
            c['why_skipped'] = 'account busy'; skipped.append(c); continue
        if c['system'] == 'FADE':
            leg_risk = c['lev'] * c['risk_pct']
            pct = (c['lev'] * c['gross'] / c['entry'] * 100 - FADE_COST) if c['status'] == 'closed' else None
        else:
            leg_risk = c['risk_pct']; pct = c['gross'] / c['entry'] * 100 if c['status'] == 'closed' else None
        notional = min(eq, eq * RISK / (leg_risk / 100))
        c.update(leg_risk=leg_risk, notional=notional, pct=pct, usd=notional * pct / 100 if pct is not None else None)
        if pct is not None:
            eq += c['usd']; streak = streak + 1 if c['usd'] < 0 else 0
        c['streak'] = streak
        taken.append(c)
        free = (c['xbar'] + 1) if c['status'] == 'closed' else 10 ** 6
    # a signal is only actionable if the account would be free for it
    signals = [s for s in signals if streak < LOCKOUT_LOSSES and (REAL_FREE or s[2].get('k', K) >= free)]
    return taken, skipped, signals, eq


def to_leg(leg_now, proxy_now, proxy_level, side, lev):
    """Convert a proxy price level to the leveraged leg's price. side = +1 if the leg rises with the proxy, -1 if it rises when the proxy falls.
    The leg moves about lev x the proxy's percentage move in the leg's favourable direction."""
    move = side * (proxy_level / proxy_now - 1)        # proxy move to the level, in the leg's favourable direction
    return leg_now * (1 + lev * move)


def live_actions(today, taken, signals, K, base=None, day=None):
    """Print the real-order instructions for this checkpoint (RULEBOOK B5). Prices are estimates from the last completed bar;
    recompute stop/target from the actual fill with the same formula."""
    print("  LIVE ACTIONS (only if the real account matches; A1 safety checks first):")
    any_ = False
    live = [s for s in signals if s[2]['status'] == 'signal']
    # B4.4: one position at a time -> rank simultaneous entries exactly like the model (earliest, higher proxy RVOL, FADE before PULLBACK, list order)
    def key(s):
        sysn, sym, t = s
        prox = sym if sysn == 'FADE' else PB_PROXY.get(sym, '')
        return (t['k'], -rvol(today, base, prox, t['k']), 0 if sysn == 'FADE' else 1 + PB_LIST.index(sym))
    live.sort(key=key)
    blocked = NO_TRADE.get(day) if day else None
    if blocked:
        print(f"    NO ENTRIES TODAY (A1.10): {day} is {blocked}. Manage any open position only.")
    elif day and day > CALENDAR_THROUGH:
        print(f"    WARNING: paper.py's holiday/early-close calendar ends {CALENDAR_THROUGH}: check the NYSE calendar by hand (A1.10) and extend NO_TRADE.")
    first = True
    for sysn, sym, t in live:
        any_ = True
        legs = (FADE_ROWS[sym][0] if t['side'] > 0 else FADE_ROWS[sym][1]) if sysn == 'FADE' else sym
        if blocked:
            print(f"    (signal {sysn} {sym} -> {legs} not entered: A1.10 no-trade day)"); continue
        if sym in SKIP or legs in SKIP:
            print(f"    SKIP {sysn} {sym} -> {legs}: barred today by --skip (A1.9 earnings). Log it as skipped."); continue
        if not first:
            print(f"    SKIP {sysn} {sym} -> {legs}: lost the same-bar tie (B4.4) to the entry above - one position at a time."); continue
        first = False
        if sysn == 'FADE':
            bull, bear, lb, lbe = FADE_ROWS[sym]; side = t['side']; leg = bull if side > 0 else bear; lev = lb if side > 0 else lbe
            pnow = today[sym][K - 1][3]; r = abs(pnow - t['stop']) / pnow
            if leg not in today:
                print(f"    ENTER FADE blocked: {leg} has no bars in the dump (fetch list C1.2) - refetch and rerun before acting (A1.6 fresh data). "
                      f"Proxy {sym} {pnow:.2f}, proxy stop {t['stop']:.2f}, R {r*100:.2f}% proxy = {lev*r*100:.2f}% on {leg}."); continue
            lnow = today[leg][K - 1][3]
            ls = to_leg(lnow, pnow, t['stop'], side, lev)
            lt = lnow * (1 + lev * 2 * r)
            print(f"    ENTER FADE: buy {leg} now (marketable limit). Proxy {sym} {pnow:.2f}, proxy stop {t['stop']:.2f} (R {r*100:.2f}% proxy = {lev*r*100:.2f}% on {leg}).")
            print(f"      est. at {leg} {lnow:.2f}: stop {ls:.2f}, 2R target {lt:.2f}. From the fill F: stop = F x (1 - {lev*r:.5f}), target = F x (1 + {2*lev*r:.5f}).")
        else:
            print(f"    ENTER PULLBACK: limit buy {sym} at {t['limit']:.2f}, valid for the next bar only. Stop {t['stop']:.2f}, target {t['target']:.2f} (one OCO for 100% after the fill).")
    for c in taken:
        if c['status'] != 'open': continue
        if REAL_FREE:
            print(f"    (model position {c['system']} {c['ticker']} is open in the model only; the real account is flat - ignored under --real-free)"); continue
        any_ = True
        print(f"    [model holds {c['system']} {c['ticker']} since {k2t(c['k'])}. If the REAL account does NOT hold it (entry skipped/blocked), do nothing: "
              f"it is a ghost position and no new entries come until the model exits (A3). Use --real-free ONLY if the governor closed it by hand.]")
        if c['system'] == 'FADE':
            bull, bear, lb, lbe = FADE_ROWS[c['proxy']]; leg = c['ticker']; side = c['side']; lev = lb if side > 0 else lbe
            pnow = today[c['proxy']][K - 1][3]; lnow = today[leg][K - 1][3] if leg in today else None
            hit = any('take profit' in e[1] for e in c['events'])
            if lnow is None:
                print(f"    MANAGE FADE {leg}: no {leg} bars in the dump - refetch; until then leave the resting orders alone and manage from the broker state (A4.5). "
                      f"Model: 1/3 take-profit {'DONE' if hit else 'not yet'}, runner stop on the proxy {c['stop_now']:.2f}")
            elif not hit:
                print(f"    MANAGE FADE {leg}: 1/3 take-profit not yet in the model - keep the entry stop and OCO exactly as placed (B5.3). "
                      f"If the REAL 1/3 already filled: runner stop = breakeven (the fill), raised to the chandelier {leg} "
                      f"{to_leg(lnow, pnow, c['chand_if_done'], side, lev):.2f} if that is higher (B5.4)")
            else:
                print(f"    MANAGE FADE {leg}: 1/3 take-profit DONE in the model; runner stop on the proxy {c['stop_now']:.2f} -> {leg} "
                      f"{to_leg(lnow, pnow, c['stop_now'], side, lev):.2f}. Never below breakeven (the fill); raise only, and only if >= 0.10% higher (B5.4)")
        else:
            print(f"    MANAGE PULLBACK {c['ticker']}: OCO resting (target {c['target']:.2f} / stop {c['stop0']:.2f}); nothing to change")
    if not any_: print("    none")


def px(v, nd=2):
    """Format a leg price; None means the leg's bars were missing from the dump (the model's P&L is unaffected: it uses the proxy)."""
    return f"{v:.{nd}f}" if v is not None else 'n/a (leg bars missing)'


def state():
    if os.path.exists(STATE): return json.load(open(STATE))
    return {'equity': 2500.0, 'start': None, 'days_logged': [], 'loss_streak': 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumps', nargs='+'); ap.add_argument('--now', required=True, help='ET time of the checkpoint, HH:MM')
    ap.add_argument('--day', help='ET date (default: latest date in the dumps)'); ap.add_argument('--close', action='store_true')
    ap.add_argument('--real-free', action='store_true', help='the real account is flat although the model still holds a position (governor closed it by hand): list new signals anyway; the broker check (A1.5) still guards entries')
    ap.add_argument('--live', action='store_true', help='also print the real-order instructions for this checkpoint (RULEBOOK B5)')
    ap.add_argument('--skip', default='', help='comma list of proxies/legs barred from real entries today (A1.9 earnings), e.g. --skip NVD')
    ap.add_argument('--build-rvol', action='store_true', help='9:00: build the 20-session RVOL baseline for --day from the dumps (5-min bars of the 6 FADE proxies + NVDA, prior 20 sessions)')
    a = ap.parse_args()
    raw = load([f for g in a.dumps for f in glob.glob(g)])
    days = sorted({d for s in raw.values() for d in s})
    if not days: sys.exit('no 5-minute bars found in the dumps (expected get_equity_historicals output, interval 5minute, bounds regular)')
    day = a.day or days[-1]
    if a.build_rvol:
        prior = [d for d in days if d < day][-20:]
        base = {p: [st.mean(sum(b[4] for b in g[:k]) for d in prior for g in [grid(raw[p][d], 78)] if g) for k in range(79)]
                for p in list(FADE_ROWS) + ['NVDA'] if p in raw and all(d in raw[p] for d in prior)}
        out = os.path.join(ROOT, 'archive', f'paper_rvol_{day}.json'); json.dump({'day': day, 'sessions': prior, 'base': base}, open(out, 'w'))
        print(f"RVOL baseline for {day} from {len(prior)} sessions ({prior[0]}..{prior[-1]}), proxies {sorted(base)} -> {out}"); return
    prevday = max(d for d in days if d < day)
    K = min(78, t2k(a.now))
    # Guard: never use a bar Robinhood hasn't published yet. If the most recent bar is missing for most proxies,
    # step back one bar (at most two) and say so; the next checkpoint will pick it up.
    def published(k):
        have = sum(1 for p in FADE_ROWS if p in raw and day in raw[p] and (570 + 5 * (k - 1)) in raw[p][day])
        return have >= max(1, len(FADE_ROWS) - 1)
    K0 = K
    while K > 1 and K0 - K < 2 and not published(K): K -= 1
    if K != K0:
        print(f"  NOTE: the bar ending {k2t(K0)} is not published yet - using bars through {k2t(K)}")
        if a.close: sys.exit('13:30 bar not published yet: wait a minute and run --close again')
    today = {s: g for s in raw if day in raw[s] for g in [grid(raw[s][day], K)] if g}
    prev = {s: g for s in raw if prevday in raw[s] for g in [grid(raw[s][prevday], 78)] if g}
    S = state(); eq0 = S['equity']
    global FLOOR_TARGET, REAL_FREE, SKIP
    REAL_FREE = a.real_free
    SKIP = {x.strip().upper() for x in a.skip.split(',') if x.strip()}
    missing = [s for s in EXPECTED if s not in today]
    if missing:
        print(f"  WARNING: no {day} bars for {' '.join(missing)} - fetch all three C1.2 groups"
              + (" (NVDA missing: NVD loses every same-bar RVOL tie)" if 'NVDA' in missing else '') + ". A missing leg blocks its entry.")
    stale = [s for s in EXPECTED if s in today and today[s][K - 1][4] == 0 and s in ('TECS', 'FAZ', 'LABU', 'LABD', 'UVXY', 'NVD', 'SOXS')]
    if stale: print(f"  note: no trade printed in the last bar for {' '.join(stale)} (filled flat, as the backtest does) - confirm with a quote before any order on them")
    if REAL_FREE: print("  --real-free is ON: use it ONLY when the governor closed the real position by hand (A3); a skipped/blocked entry keeps the ghost position.")
    FLOOR_TARGET = day >= FLOOR_FROM
    bf = os.path.join(ROOT, 'archive', f'paper_rvol_{day}.json')
    base = json.load(open(bf))['base'] if os.path.exists(bf) else None
    if not base: print("  (no RVOL baseline for today - same-bar ties fall back to list order; run --build-rvol at 9:00)")
    streak0 = S.get('loss_streak', 0)
    if streak0 >= LOCKOUT_LOSSES: print(f"  LOCKOUT: {streak0} losing trades in a row - no new paper entries until the governor clears it")
    taken, skipped, signals, eq = simulate(today, prev, K, eq0, base, streak0)
    print(f"PAPER {day} at {a.now} ET (bars through {k2t(K)}), paper equity at open ${eq0:,.2f}")
    if not taken and not signals: print("  no paper trades or live signals")
    for c in taken:
        head = f"  {c['system']:<4} {c['ticker']:<5}" + (f" (fade of {c['proxy']})" if c['system'] == 'FADE' else '') + \
               f" entered {k2t(c['k'])} @ {px(c['leg_entry'])}" + (f" [proxy {c['entry']:.2f}]" if c['system'] == 'FADE' else '') + \
               f", stop {c['stop0']:.2f}{' (proxy)' if c['system'] == 'FADE' else ''}, target {c['target']:.2f}, notional ${c['notional']:,.0f}"
        print(head)
        for e in c['events']: print(f"       {e[0]} {e[1]} at {e[2]:.2f}" + (f" ({e[3]:.0%})" if len(e) > 3 else ''))
        if c['status'] == 'open':
            print(f"       OPEN: " + (f"current stop {c['stop_now']:.2f} (proxy), remaining {c['rem']:.0%}" if c['system'] == 'FADE' else 'OCO resting (target / stop)'))
        else:
            print(f"       CLOSED {c['why']}: {c['pct']:+.2f}% on {c['ticker']} = ${c['usd']:+.2f}")
    for s in skipped: print(f"  skipped ({s.get('why_skipped', 'account busy')}): {s['system']} {s['ticker']} at {k2t(s['k'])}")
    for sysn, sym, t in signals: print(f"  SIGNAL {sysn} {sym}: {t['note']}")
    if a.live: live_actions(today, taken, signals, K, base, day)
    open_ = [] if REAL_FREE else [c for c in taken if c['status'] == 'open']
    cadence = '5 min (fade open: ratchet the stop)' if any(c['system'] == 'FADE' for c in open_) else \
              ('30 min (pullback OCO resting)' if open_ else ('5 min (flat, scanning)' if K < 41 and streak0 < LOCKOUT_LOSSES else 'none needed until 13:30'))
    st_now = taken[-1]['streak'] if taken and taken[-1].get('pct') is not None else (taken[-2]['streak'] if len(taken) > 1 else streak0)
    print(f"  entries today {len(taken)}; losing streak {st_now}/{LOCKOUT_LOSSES}; next check-in: {cadence}; paper equity now ${eq:,.2f}")
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
                w.writerow([day, c['system'], c['proxy'], c['ticker'], k2t(c['k']), px(c['leg_entry'], 4), f"{c['stop0']:.4f}", f"{c['target']:.4f}",
                            k2t(c['xbar']), c['why'], f"{c['pct']:.3f}", f"{c['notional']:.2f}", f"{c['usd']:.2f}", f"{e:.2f}"])
        S['equity'] = round(eq, 2); S['days_logged'].append(day); S['start'] = S['start'] or day
        S['loss_streak'] = taken[-1]['streak'] if taken else streak0
        json.dump(S, open(STATE, 'w'), indent=1)
        print(f"  logged {len(taken)} trade(s) to archive/paper_trades.csv; paper equity ${eq:,.2f}")


if __name__ == '__main__':
    main()
