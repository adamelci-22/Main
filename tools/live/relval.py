#!/usr/bin/env python3
"""RELVAL, the afternoon relative-value system (RULEBOOK B8, v5.2.64, governor "Push the relval system" 2026-11-19). Replaces FADE.

Rule (the fade_replace.py / relval_exit.py setting, a=48 z=72 xm=1.0 ksd=2.5, exit unchanged by the exit study):
  For each proxy SOXX IWM XLK DIA XLF, and from 2026-11-25 XLRE and XLE (v5.2.66: DIA replaced XBI; v5.2.70: + XLRE, XLE), at the close of every 5-minute bar from the 13:30 bar to the 15:25 bar (slots 13:35-15:30):
  rp = (proxy close / proxy 9:30 open) - (QQQ close / QQQ 9:30 open). The FIRST bar of the day where |rp| >= 1.0% AND |rp| >= 2.5 x the
  standard deviation of that proxy's last 20 sessions of (proxy open-to-close - QQQ open-to-close) is the proxy's signal (one a day; a
  signal blocked by an open position is spent). rp > 0 (the sector ran ahead of QQQ) -> buy the 3x INVERSE leg; rp < 0 -> the 3x LONG leg.
  Entry at the next bar's open (the slot where the signal bar closed). Stop: the proxy moves one gap (|rp|) further against us
  = leg fill x (1 - 3|rp|). Target: half the gap back toward QQQ = leg fill x (1 + 1.5|rp|). Both as one OCO on all shares.
  XLE's legs ERX/ERY are 2x: its stop is leg fill x (1 - 2|rp|) and its target leg fill x (1 + 1|rp|) (v5.2.70).
  Out at the 15:55 slot. Size: 3% of the account at risk on a 3|rp| leg stop, capped at 100% of cash; from 2026-11-23 (v5.2.69) 100% of cash. Several signals on one bar:
  the highest relative volume (paper.py rvol). One position at a time; no entry while another system holds the account.

    python3 -I tools/live/relval.py prep DUMP...                 # 9:00: the 20-session baseline dump with DIA added (fills archive/relval_daily.json)
    python3 -I tools/live/relval.py signal --now HH:MM DUMP...   # every slot 13:35-15:30 (C1.2 groups 1 and 2 + the RELVAL group DIA UDOW SDOW)
    python3 -I tools/live/relval.py opened PROXY FILL SHARES     # after the real entry filled: records the open trade
    python3 -I tools/live/relval.py skip REASON                  # a signal was not traded
    python3 -I tools/live/relval.py manage --now HH:MM DUMP...   # every slot while open, and 15:55 (logs the model trade)
    python3 -I tools/live/relval.py status
Files: archive/relval_daily.json (daily open and close per proxy), archive/relval_state.json (today's signal and position),
archive/relval_trades.csv (the model record on the proxy chart: 3 x the proxy move minus 0.06%)."""
import csv, json, os, statistics as st, sys
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import paper as P
BASE = ['SOXX', 'IWM', 'XLK', 'DIA', 'XLF']; REF = 'QQQ'             # v5.2.66 (governor 2026-11-19 "push it"): DIA replaces XBI
ADD_FROM = {'XLRE': '2026-11-25', 'XLE': '2026-11-25'}           # v5.2.70 (governor 2026-11-24 "Do these"): XLRE (DRN/DRV 3x) and XLE (ERX/ERY 2x) join
PROXIES = BASE + list(ADD_FROM)                                   # every proxy the store keeps; proxies(day) is the list that trades that day
ROWS = {'SOXX': ('SOXL', 'SOXS'), 'IWM': ('TNA', 'TZA'), 'XLK': ('TECL', 'TECS'), 'DIA': ('UDOW', 'SDOW'), 'XLF': ('FAS', 'FAZ'),
        'XLRE': ('DRN', 'DRV'), 'XLE': ('ERX', 'ERY')}   # proxy: (long leg, inverse leg); 3x except XLE 2x (LEVP)
LEG = {p: ROWS[p][0] for p in PROXIES}; INV = {p: ROWS[p][1] for p in PROXIES}
GROUP = ['SPY', 'SPXL', 'SPXS', 'DIA', 'UDOW', 'SDOW']                 # group 4 (v5.2.67): fetched with C1.2 groups 1 and 2 at 9:35, every RELVAL slot and every IBS-TREND slot
GROUP5 = ['XLRE', 'DRN', 'DRV', 'XLE', 'ERX', 'ERY', 'FXI', 'YINN']    # group 5 (v5.2.70): fetched at every RELVAL slot, at 15:55 and at 9:35 after an FXI overnight entry
LEVP = {'XLE': 2}                                                    # leg leverage when not 3x


def lev(p): return LEVP.get(p, LEV)


def proxies(day): return BASE + [p for p, d in ADD_FROM.items() if day >= d]
A, Z, XM, KSD, NHIST, MINH = 48, 72, 1.0, 2.5, 20, 15       # signal bars A..Z-1 (13:30..15:25 bars); |rp| >= XM% and >= KSD sd
TG, SM, LEV, COST, OUT_BAR, RISK = 0.5, 1.0, 3, 0.06, 77, 3.0
LIVE_FROM = '2026-11-20'
FULL_FROM = '2026-11-23'   # v5.2.69 (governor 2026-11-20 "push RELVAL full size"): 100% of cash on every RELVAL trade
DAILY = os.path.join(ROOT, 'archive', 'relval_daily.json'); STATE = os.path.join(ROOT, 'archive', 'relval_state.json'); LOG = os.path.join(ROOT, 'archive', 'relval_trades.csv')
FIELDS = ['day', 'proxy', 'side', 'ticker', 'rp_pct', 'sd_pct', 'signal_bar', 'entry_time', 'entry_px_proxy', 'stop_proxy', 'target_proxy', 'exit_time', 'exit_px_proxy', 'exit_reason', 'pct_leg']


def jload(path, default):
    try: return json.load(open(path))
    except Exception: return default


def jsave(path, obj): json.dump(obj, open(path, 'w'), indent=1, sort_keys=True)


def persist(what):
    import subprocess
    if os.environ.get('IBS_NO_GIT') or not os.path.isdir(os.path.join(ROOT, '.git')): return
    fs = [f for f in (STATE, DAILY, LOG) if os.path.exists(f)]
    try:
        subprocess.run(['git', '-C', ROOT, 'add'] + fs, capture_output=True, timeout=30)
        if subprocess.run(['git', '-C', ROOT, 'commit', '-qm', f'RELVAL state: {what}', '--'] + fs, capture_output=True, timeout=30).returncode == 0:
            r = subprocess.run(['git', '-C', ROOT, 'push', '-q'], capture_output=True, timeout=60)
            if r.returncode != 0:
                subprocess.run(['git', '-C', ROOT, 'pull', '-q', '--rebase', '--autostash'], capture_output=True, timeout=60); r = subprocess.run(['git', '-C', ROOT, 'push', '-q'], capture_output=True, timeout=60)
            print(f"  (state saved and {'pushed' if r.returncode == 0 else 'committed; PUSH FAILED - push by hand'})")
    except Exception as e: print(f"  WARNING: state not committed ({e})")


# ------------------------------------------------------------------ core (shared with the backtest check)
def rel_sd(hist):
    return (st.pstdev(hist) or 1e-9) if len(hist) >= MINH else None


def first_trigger(pb, qb, sd, last_bar):
    """pb, qb: today's proxy and QQQ bars (o, h, l, c, v) on the 5-minute grid. Scans signal bars A..min(Z-1, last_bar).
    Returns (j, rp) for the first bar that triggers, or None."""
    if sd is None: return None
    for j in range(A, min(Z - 1, last_bar) + 1):
        rp = pb[j][3] / pb[0][0] - qb[j][3] / qb[0][0]
        if abs(rp) * 100 >= XM and abs(rp) >= KSD * sd: return j, rp
    return None


def model_exit(pb, k, rp, upto):
    """The backtest's exit on the proxy chart from entry bar k (its open) through bar `upto` (inclusive of its open at OUT_BAR).
    Returns (exit bar, exit price, reason) or None while still open."""
    s = -1 if rp > 0 else 1; e = pb[k][0]; gap = abs(rp) * e; stop = e - s * SM * gap; T = e + s * TG * gap
    for j in range(k, min(upto, OUT_BAR) + 1):
        o, h, l, c, v = pb[j]
        if j == OUT_BAR: return j, o, 'time 15:55'
        fav, adv = (h, l) if s > 0 else (l, h)
        if (adv - stop) * s <= 0: return j, (stop if (o - stop) * s >= 0 else o), 'stop'
        if (fav - T) * s >= 0: return j, (T if (o - T) * s <= 0 else o), 'target'
    return None


# ------------------------------------------------------------------ data
def store_update(raw, before_day):
    """Adds complete sessions (days before `before_day`) to the daily store: open = 9:30 bar open, close = 15:55 bar close."""
    store = jload(DAILY, {}); n = 0
    for p in PROXIES + [REF]:
        for d, bars in raw.get(p, {}).items():
            if d >= before_day or 570 not in bars or 955 not in bars: continue
            row = [bars[570][0], bars[955][3]]
            if store.setdefault(p, {}).get(d) != row: store[p][d] = row; n += 1
    jsave(DAILY, store); return store, n


def sd_today(store, p, day):
    days = sorted(d for d in store.get(p, {}) if d < day and d in store.get(REF, {}))[-NHIST:]
    hist = [store[p][d][1] / store[p][d][0] - store[REF][d][1] / store[REF][d][0] for d in days]
    return rel_sd(hist), len(hist), (days[-1] if days else None)


def today_bars(raw, day, nb):
    return {p: P.grid(raw[p][day], nb) for p in PROXIES + [REF] if p in raw and day in raw[p]}


def opts_paths(argv):
    o, paths, i = {}, [], 0
    while i < len(argv):
        if argv[i].startswith('--'): o[argv[i][2:]] = argv[i + 1]; i += 2
        else: paths.append(argv[i]); i += 1
    return o, paths


def blocks(day):
    """Day-level blocks from the records: an IBS-TREND trade open or stopped today (B6.6), a RELVAL loss today, 3 entries today."""
    why = []; ibs = jload(os.path.join(ROOT, 'archive', 'ibs_state.json'), {}).get(day, {})
    if ibs.get('status') == 'open': why.append('an IBS-TREND trade holds the account until 15:55 (B4.4)')
    n = 0
    try:
        for r in csv.DictReader(open(os.path.join(ROOT, 'archive', 'live_trades.csv'))):
            if r['date'] != day: continue
            n += 1
            if r['system'] in ('IBS-LONG', 'MIRROR', 'DIP') and r['exit_reason'].startswith('stop'): why.append('an IBS-TREND trade was stopped out today (B6.6)')
            if r['system'] == 'RELVAL' and float(r['pnl_usd'] or 0) <= 0: why.append('RELVAL already lost today (B4.7)')
    except FileNotFoundError: pass
    if n >= 3: why.append('3 entries already today (A1.4)')
    if P.NO_TRADE.get(day): why.append(P.NO_TRADE[day])
    if jload(os.path.join(ROOT, 'archive', 'hwm.json'), {}).get('halted'): why.append('drawdown stop (A1.13)')
    return sorted(set(why))


# ------------------------------------------------------------------ commands
def cmd_prep(argv):
    o, paths = opts_paths(argv); day = o.get('day') or datetime.now(P.ET).date().isoformat()
    store, n = store_update(P.load(paths), day)
    print(f"RELVAL prep for {day} (B8): daily store +{n} rows. Signal when |sector move - QQQ move| >= {XM:.1f}% and >= {KSD} x the 20-session sd:")
    bad = False
    for p in proxies(day):
        sd, nh, last = sd_today(store, p, day)
        if sd is None: bad = True; print(f"  {p:<5} only {nh} sessions (need {MINH}): fetch the 20-session baseline and rerun prep"); continue
        print(f"  {p:<5} sd {sd * 100:.2f}% over {nh} sessions (last {last}) -> trigger at |rp| >= {max(XM, KSD * sd * 100):.2f}%")
    if bad: print("  WARNING: prep INCOMPLETE")


def cmd_signal(argv):
    o, paths = opts_paths(argv); day = o.get('day') or datetime.now(P.ET).date().isoformat(); now = o['now']
    K = P.t2k(now); raw = P.load(paths); store, _ = store_update(raw, day); tb = today_bars(raw, day, K); last = K - 1
    st_ = jload(STATE, {}); rec = st_.get(day, {})
    print(f"RELVAL {day} at {now} ET (bars through {P.k2t(last + 1)}), signal bars {P.k2t(A + 1)}-{P.k2t(Z)} (B8)")
    if day < LIVE_FROM: print(f"  (RELVAL is live from {LIVE_FROM}: information only)")
    if REF not in tb: print("  ERROR: no QQQ bars for today in the dumps: refetch C1.2 group 1"); return
    if last < A: print(f"  before the signal window: nothing to do until {P.k2t(A + 1)}"); return
    if rec.get('status') in ('open', 'closed'): print(f"  today's RELVAL trade is {rec['status']} ({rec.get('proxy')} -> {rec.get('ticker')}): run `relval.py manage`"); return
    base = jload(os.path.join(ROOT, 'archive', f'paper_rvol_{day}.json'), {}).get('base')
    cands, rows = [], []
    for p in proxies(day):
        if p not in tb: rows.append(f"  {p:<5} no bars today: refetch (group 5 for XLRE and XLE)"); continue
        sd, nh, _ = sd_today(store, p, day)
        if sd is None: rows.append(f"  {p:<5} sd needs {MINH} sessions, has {nh}: run `relval.py prep` on the 20-session dump"); continue
        pb, qb = tb[p], tb[REF]; j = min(last, Z - 1)
        rp_now = pb[last][3] / pb[0][0] - qb[last][3] / qb[0][0]
        ft = first_trigger(pb, qb, sd, last)
        if not ft: rows.append(f"  {p:<5} rp {rp_now * 100:+.2f}% vs trigger {max(XM, KSD * sd * 100):.2f}% -> no"); continue
        jj, rp = ft
        if jj < last: rows.append(f"  {p:<5} signalled on the {P.k2t(jj + 1)} bar close (rp {rp * 100:+.2f}%): spent (one signal a proxy a day)"); continue
        side = -1 if rp > 0 else 1; leg = INV[p] if side < 0 else LEG[p]
        cands.append(dict(proxy=p, rp=rp, sd=sd, j=jj, side=side, ticker=leg, rv=P.rvol(tb, base, p, jj + 1), e_proxy=pb[jj][3]))
        rows.append(f"  {p:<5} rp {rp * 100:+.2f}% (sd {sd * 100:.2f}%) -> SIGNAL: buy {leg} ({'sector ahead of QQQ' if rp > 0 else 'sector behind QQQ'})")
    for r in rows: print(r)
    if last > Z - 1: print("  signal window closed (last signal bar 15:25)")
    if not cands:
        print("  LIVE ACTIONS: none"); return
    c = max(cands, key=lambda x: x['rv']); why = blocks(day)
    if len(cands) > 1: print(f"  several signals on this bar: {c['proxy']} has the highest relative volume ({', '.join(f'{x['proxy']} {x['rv']:.2f}' for x in cands)})")
    st_[day] = dict(status='signal', proxy=c['proxy'], ticker=c['ticker'], side=c['side'], rp=round(c['rp'], 6), sd=round(c['sd'], 6), j=c['j'], k=c['j'] + 1)
    L = lev(c['proxy']); gap = abs(c['rp']); lr = L * gap * 100; full = day >= FULL_FROM; frac = 1.0 if full else min(1.0, RISK / lr)
    if why or day < LIVE_FROM:
        st_[day]['status'] = 'blocked'; st_[day]['why'] = '; '.join(why) or 'before LIVE_FROM'; jsave(STATE, st_); persist('blocked ' + day)
        print(f"  LIVE ACTIONS: none. RELVAL signal {c['proxy']} -> {c['ticker']} NOT TRADED: {st_[day]['why']}"); return
    jsave(STATE, st_); persist('signal ' + day)
    print("  LIVE ACTIONS (A1 safety checks first: account flat, no open orders, spread A1.7, daily loss limit A1.2, losing streak A1.1):")
    print(f"    ENTER RELVAL: buy {c['ticker']} now (marketable limit, B5.2 steps). Gap {gap * 100:.2f}% on {c['proxy']} -> leg risk {lr:.2f}%.")
    if full: print(f"      size (v5.2.69 full size): 100% of cash, shares = floor(buying power / ask). Risk to the stop = the {lr:.2f}% leg stop. Whole shares, floor.")
    else: print(f"      size: {RISK:.0f}% of the account at risk on a {lr:.2f}% leg stop = {frac * 100:.0f}% of the account (capped at cash). Whole shares, floor.")
    print(f"      after the fill F: ONE OCO on all shares, GTC: stop F x {1 - L * SM * gap:.4f} (rounded down to the cent), take-profit limit F x {1 + L * TG * gap:.4f} (rounded to the cent). Leg leverage {L}x.")
    print(f"      then `python3 -I tools/live/relval.py opened {c['proxy']} F SHARES`. Exit: cancel the OCO and sell all at the 15:55 slot.")


def cmd_opened(argv):
    day = datetime.now(P.ET).date().isoformat(); p, fill, sh = argv[0], float(argv[1]), int(argv[2]); st_ = jload(STATE, {}); r = st_.get(day)
    if not r or r.get('proxy') != p: print(f"  ERROR: no RELVAL signal for {p} today in {STATE}"); return
    L = lev(p); gap = abs(r['rp']); r.update(status='open', fill=fill, shares=sh, stop_leg=int(fill * (1 - L * SM * gap) * 100) / 100, target_leg=round(fill * (1 + L * TG * gap), 2))
    jsave(STATE, st_); persist('open ' + day); print(f"  RELVAL open: {sh} {r['ticker']} @ {fill}; OCO stop {r['stop_leg']} / target {r['target_leg']}; out at 15:55")


def cmd_skip(argv):
    day = datetime.now(P.ET).date().isoformat(); st_ = jload(STATE, {}); r = st_.setdefault(day, {})
    r.update(status='skipped', why=' '.join(argv)); jsave(STATE, st_); persist('skip ' + day); print(f"  RELVAL {day}: skipped ({r['why']})")


def cmd_manage(argv):
    o, paths = opts_paths(argv); day = o.get('day') or datetime.now(P.ET).date().isoformat(); now = o['now']; K = P.t2k(now)
    st_ = jload(STATE, {}); r = st_.get(day)
    if not r or r.get('status') not in ('open', 'closed', 'blocked', 'signal'): print(f"  RELVAL {day}: no trade today"); return
    raw = P.load(paths); tb = today_bars(raw, day, K); pb = tb.get(r['proxy'])
    if not pb: print(f"  ERROR: no {r['proxy']} bars in the dumps"); return
    x = model_exit(pb, r['k'], r['rp'], K - 1 if K - 1 < OUT_BAR else OUT_BAR)
    if K - 1 >= OUT_BAR - 1 and x is None: x = (OUT_BAR, pb[OUT_BAR][0] if len(pb) > OUT_BAR else pb[-1][3], 'time 15:55')
    s = r['side']; e = pb[r['k']][0]
    if x is None:
        m = pb[K - 1][3]; print(f"  RELVAL {r['proxy']} -> {r['ticker']} model open: proxy {m:.2f} vs entry {e:.2f} ({lev(r['proxy']) * s * (m / e - 1) * 100:+.2f}% on the leg). Keep the OCO; out at 15:55.")
        return
    j, px, why = x; pct = lev(r['proxy']) * s * (px / e - 1) * 100 - COST
    print(f"  RELVAL model CLOSED at {P.k2t(j)} ({why}): {pct:+.2f}% on the leg.")
    if r.get('logged') != day:
        new = not os.path.exists(LOG)
        with open(LOG, 'a', newline='') as f:
            w = csv.DictWriter(f, FIELDS, lineterminator='\n')
            if new: w.writeheader()
            gap = abs(r['rp']) * e
            w.writerow(dict(day=day, proxy=r['proxy'], side=s, ticker=r['ticker'], rp_pct=round(r['rp'] * 100, 3), sd_pct=round(r['sd'] * 100, 3), signal_bar=P.k2t(r['j']),
                            entry_time=P.k2t(r['k']), entry_px_proxy=round(e, 4), stop_proxy=round(e - s * SM * gap, 4), target_proxy=round(e + s * TG * gap, 4),
                            exit_time=P.k2t(j), exit_px_proxy=round(px, 4), exit_reason=why, pct_leg=round(pct, 3)))
        r['logged'] = day
        if r.get('status') == 'open': r['status'] = 'closed'
        jsave(STATE, st_); persist('model ' + day); print("  logged the model trade to archive/relval_trades.csv")
    if r.get('status') in ('open', 'closed') and why == 'time 15:55': print("  LIVE ACTION at 15:55: cancel the OCO, sell all shares (marketable limit), verify flat, log the trade (system RELVAL).")


def cmd_status(argv):
    day = datetime.now(P.ET).date().isoformat(); print(json.dumps(jload(STATE, {}).get(day, {'status': 'none'}), indent=1))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'prep': cmd_prep, 'signal': cmd_signal, 'opened': cmd_opened, 'skip': cmd_skip, 'manage': cmd_manage, 'status': cmd_status}.get(
        cmd, lambda a: print(__doc__))(sys.argv[2:])
