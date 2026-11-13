#!/usr/bin/env python3
"""IBS-TREND, the third live system (RULEBOOK B6, v5.2.48, governor "push IBS-TREND" 2026-11-13).

Rule: a FADE proxy (QQQ SOXX IWM XLK XBI XLF) closed yesterday ABOVE its 20-session average close AND in the bottom 10% of
yesterday's range (IBS = (close - low) / (high - low) < 0.10) -> buy its 3x LONG leg at 9:35, stop 1% of the proxy (3% on the leg),
sell at 15:55. MIRROR (v5.2.49, governor 2026-11-13): it closed AT OR BELOW that average AND in the top 5% of the range (IBS > 0.95)
-> buy its 3x INVERSE leg, same clock, stop 1% of the proxy above the entry.
DIP (v5.2.50, governor 2026-11-13): it closed ABOVE its 50-session average close with a 2-day RSI of closes below 10 -> the 3x LONG leg,
same clock and stop. One trade a day from the three signal kinds. Several signals: the highest first-5-minute relative volume.
While the position is open no FADE or PULLBACK entry is taken (one position at a time, B4.4): paper.py reads archive/ibs_state.json.

    python3 -I tools/live/ibs_trend.py signal [--day D] DUMP...             # 8:41 research: the 20-session baseline dump (C3)
    python3 -I tools/live/ibs_trend.py enter  [--day D] [--now HH:MM] DUMP...  # the 9:35 slot (the C1.2 group with the six proxies)
    python3 -I tools/live/ibs_trend.py manage [--day D] [--now HH:MM] DUMP...  # every slot while it is open, and the 15:55 exit slot
    python3 -I tools/live/ibs_trend.py replay CACHE.json.gz [FROM] [TO]     # research check: the same code on a 5-minute cache

Files: archive/ibs_daily.json (daily high, low, close, first-bar volume per proxy), archive/ibs_state.json (today's signal and
position; read by paper.py), archive/ibs_trades.csv (the model record, on the proxy chart: 3 x the proxy move minus 0.06%).
Evidence: archive/systems_split_2026-11-13.md (train 2022/2024/2026, test 2023/2025)."""
import csv, gzip, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import paper as P
LEG = {p: r[0] for p, r in P.FADE_ROWS.items()}          # proxy -> 3x long leg
INV = {p: r[1] for p, r in P.FADE_ROWS.items()}          # proxy -> 3x inverse leg (the mirror, v5.2.49)
LO, HI, SMA, STOP_PCT, LEV, COST = 0.10, 0.95, 20, 1.0, 3, 0.06
DIP_RSI, DIP_SMA, DIP_FROM = 10, 50, '2026-11-16'            # v5.2.50: dip-buy in an uptrend (needs 50 closes in the daily store)
MIRROR_FROM = '2026-11-16'                               # the mirror trades from this day (replays before it: long side only unless --mirror)
OUT_BAR = 77                                            # the 15:55 bar: the position is sold at its open
DAILY = os.path.join(ROOT, 'archive', 'ibs_daily.json'); STATE = os.path.join(ROOT, 'archive', 'ibs_state.json'); LOG = os.path.join(ROOT, 'archive', 'ibs_trades.csv')
FIELDS = ['day', 'system', 'side', 'proxy', 'ticker', 'ibs', 'entry_time', 'entry_px_proxy', 'stop_proxy', 'exit_time', 'exit_px_proxy', 'exit_reason', 'pct_leg']


def jload(path, default):
    try: return json.load(open(path))
    except Exception: return default


def jsave(path, obj): json.dump(obj, open(path, 'w'), indent=1, sort_keys=True)


def day_row(bars):
    """bars: completed 5-minute bars of one full session -> [high, low, close, first-bar volume]."""
    return [max(x[1] for x in bars), min(x[2] for x in bars), bars[-1][3], bars[0][4]]


def rsi2(c):
    """2-period RSI of the closes c (the last 12 are used, as in the backtest)."""
    ag = al = 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 2: ag += g / 2; al += lo / 2
        else: ag = (ag + g) / 2; al = (al + lo) / 2
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def check(store, day):
    """Signals for `day` from the daily store. Returns {proxy: dict(ok, side, above, ibs, close, sma, n)}; side +1 long leg, -1 inverse leg."""
    out = {}
    for p in LEG:
        allp = sorted(d for d in store.get(p, {}) if d < day); prior = allp[-SMA:]
        if len(prior) < SMA: out[p] = dict(ok=False, n=len(prior)); continue
        c = [store[p][d][2] for d in prior]; h, l, cl, _ = store[p][prior[-1]]
        ibs = (cl - l) / (h - l) if h > l else 0.5; sma = st.mean(c)
        side = 1 if (cl > sma and ibs < LO) else -1 if (cl <= sma and ibs > HI and day >= MIRROR_FROM) else 0
        kind = 'long' if side > 0 else 'mirror' if side < 0 else None; rsi = None; n50 = len(allp)
        if n50 >= DIP_SMA:
            c50 = [store[p][d][2] for d in allp[-DIP_SMA:]]; rsi = rsi2(c50[-12:])
            if side <= 0 and day >= DIP_FROM and c50[-1] > st.mean(c50) and rsi < DIP_RSI: side = 1; kind = 'dip'      # a dip signal outranks a mirror signal on the same proxy (as in the backtest)
        out[p] = dict(ok=side != 0, side=side, kind=kind, rsi=rsi, n50=n50, above=cl > sma, ibs=ibs, close=cl, sma=sma, n=len(prior), last=prior[-1], v0=st.mean(store[p][d][3] for d in prior))
    return out


def model(b, K, side=1):
    """b: today's proxy bars (completed bars 0..K-1). Entry at the 9:35 open; side +1 = long leg, -1 = inverse leg (the proxy stop is above).
    Returns dict(status, side, entry, stop, xbar, px, why)."""
    e = b[1][0]; stop = e * (1 - side * STOP_PCT / 100)
    for j in range(1, min(K, OUT_BAR)):
        o, h, l = b[j][0], b[j][1], b[j][2]
        if (l <= stop) if side > 0 else (h >= stop):
            return dict(status='closed', side=side, entry=e, stop=stop, xbar=j, px=min(stop, o) if side > 0 else max(stop, o), why='stop')
    if K >= OUT_BAR:
        return dict(status='closed', side=side, entry=e, stop=stop, xbar=OUT_BAR - 1, px=b[OUT_BAR][0] if K > OUT_BAR else b[OUT_BAR - 1][3], why='time')
    return dict(status='open', side=side, entry=e, stop=stop, xbar=None, px=b[K - 1][3], why=None)


def pct_leg(m): return LEV * m.get('side', 1) * (m['px'] / m['entry'] - 1) * 100 - COST


def leg_of(p, side): return LEG[p] if side > 0 else INV[p]


def args_days(argv):
    opts = {}
    while argv and argv[0].startswith('--'): opts[argv[0][2:]] = argv[1]; argv = argv[2:]
    raw = P.load(argv); days = sorted({d for s in raw.values() for d in s})
    return opts, raw, days


def update_store(raw, upto):
    """Add every full session before `upto` found in the dumps to the daily store."""
    store = jload(DAILY, {}); n = 0
    for p in LEG:
        for d, bars in raw.get(p, {}).items():
            if d >= upto or len(bars) < 70: continue
            g = P.grid(bars, 78)
            if g:
                n += d not in store.setdefault(p, {}); store[p][d] = day_row(g)        # broker bars overwrite seeded rows
    jsave(DAILY, store); return store, n


def blocked(day):
    why = P.NO_TRADE.get(day)
    if jload(os.path.join(ROOT, 'archive', 'hwm.json'), {}).get('halted'): why = 'drawdown stop (A1.13)'
    return why


def cmd_signal(argv):
    opts, raw, days = args_days(argv); day = opts.get('day') or __import__('datetime').datetime.now(P.ET).date().isoformat()
    store, n = update_store(raw, day); sig = check(store, day)
    print(f"IBS-TREND signal check for {day} (B6): LONG = above the {SMA}-session average close and prior-day IBS below {LO:.2f}; MIRROR = at or below it and IBS above {HI:.2f}. Daily store +{n} rows.")
    for p, s in sig.items():
        if s['n'] < SMA: print(f"  {p:<5} only {s['n']} prior sessions in the store, need {SMA}: fetch the 20-session baseline (C3) and rerun"); continue
        print(f"  {p:<5} {s['last']} close {s['close']:.2f} vs average {s['sma']:.2f} ({'above' if s['above'] else 'below'}), IBS {s['ibs']:.2f} RSI2 {('%.0f' % s['rsi']) if s['rsi'] is not None else 'n/a (' + str(s['n50']) + ' closes)'} -> {'SIGNAL ' + s['kind'] + ' -> ' + leg_of(p, s['side']) if s['ok'] else 'no'}")
    ok = [p for p, s in sig.items() if s['ok']]; state = jload(STATE, {})
    state[day] = dict(signals={p: dict(ibs=round(sig[p]['ibs'], 4), v0=sig[p]['v0'], side=sig[p]['side'], kind=sig[p]['kind']) for p in ok}, status='signal' if ok else 'none')
    jsave(STATE, state); why = blocked(day)
    if not ok: print("  NO IBS-TREND SIGNAL today. FADE and PULLBACK run as usual.")
    elif why: print(f"  IBS-TREND SIGNAL ({', '.join(ok)}) NOT TRADED: {why}.")
    else:
        print(f"  IBS-TREND SIGNAL TODAY: {', '.join(ok)}. Start a 9:35 waiter. Sell all USDG at 9:31 (B4.8 peg check). At 9:35 fetch C1.2 groups 1 and 2 (the proxies and every leg) and run "
              f"`python3 -I tools/live/ibs_trend.py enter --now 09:35 <dump>`. Start the afternoon waiters (B6.6).")


def cmd_enter(argv):
    opts, raw, days = args_days(argv); day = opts.get('day') or days[-1]; K = P.t2k(opts['now']) if 'now' in opts else None
    state = jload(STATE, {}); s = state.get(day)
    if not s or not s.get('signals'): print(f"IBS-TREND: no signal recorded for {day} (run `signal` in the morning research). No entry."); return
    if s.get('status') in ('open', 'closed', 'skipped'): print(f"IBS-TREND: today's trade is already {s['status']} ({s.get('proxy')} -> {s.get('ticker')}). No second entry."); return
    why = blocked(day)
    if why: print(f"IBS-TREND: signal not traded today: {why}."); s['status'] = 'skipped'; jsave(STATE, state); return
    best = None
    for p, g in s['signals'].items():
        b = P.grid(raw.get(p, {}).get(day, {}), 2)
        if not b: print(f"  {p}: no 9:30 bar in the dump - refetch the proxies before acting (A1.6)"); continue
        k = K if K is not None else (max(raw[p][day]) - 570) // 5 + 1
        if k != 1: print(f"IBS-TREND: the entry slot is 9:35 only (bars completed {k}). Signal skipped today."); s['status'] = 'skipped'; jsave(STATE, state); return
        rv = b[0][4] / g['v0'] if g['v0'] else 0.0
        print(f"  {p:<5} IBS {g['ibs']:.2f}, first-bar relative volume {rv:.2f}, 9:30 bar close {b[0][3]:.2f}")
        if best is None or rv > best[1]: best = (p, rv, b[0][3], g.get('side', 1))
    if not best: return
    p, rv, ref, side = best; leg = leg_of(p, side); lb = P.grid(raw.get(leg, {}).get(day, {}), 1)
    s.update(status='open', proxy=p, ticker=leg, side=side, kind=s['signals'][p].get('kind'), k=1, xbar=None, ref=ref); jsave(STATE, state)
    print(f"  LIVE ACTIONS (only if the real account is flat; A1 safety checks first):")
    print(f"    ENTER IBS-TREND: buy {leg} now (marketable limit, B5.2 steps). {'Long' if side > 0 else 'MIRROR (inverse leg)'}: proxy {p} {ref:.2f}, proxy stop about {ref * (1 - side * STOP_PCT / 100):.2f} (1% of the proxy {'below' if side > 0 else 'above'} = {LEV * STOP_PCT:g}% on {leg}).")
    print(f"      size (B4.1): 3% of the account at risk on a {LEV * STOP_PCT:g}% leg stop = 100% of cash (the cap). Whole shares, floor.")
    print(f"      after the fill F: one stop-market for ALL shares at F x {1 - LEV * STOP_PCT / 100:.2f}, rounded down to the cent" + (f" (est. at {leg} {lb[0][3]:.2f}: stop {lb[0][3] * (1 - LEV * STOP_PCT / 100):.2f})" if lb else '') + ". No take-profit order.")
    print(f"      exit: sell everything at the 15:55 slot (B6.5). No FADE or PULLBACK entry while it is open (B4.4).")


def cmd_manage(argv):
    opts, raw, days = args_days(argv); day = opts.get('day') or days[-1]
    state = jload(STATE, {}); s = state.get(day)
    if not s or s.get('status') not in ('open', 'closed'): print(f"IBS-TREND: no position today ({s.get('status') if s else 'no signal'})."); return
    p, leg = s['proxy'], s['ticker']; bars = raw.get(p, {}).get(day)
    if not bars: print(f"IBS-TREND: no {p} bars for {day} in the dump - refetch; the resting stop protects the position (A4.5)."); return
    K = P.t2k(opts['now']) if 'now' in opts else (max(bars) - 570) // 5 + 1
    if K < 2: print(f"IBS-TREND {leg}: entered at 9:35, first management at 9:40."); return
    b = P.grid(bars, min(K, 78)); m = model(b, min(K, 78), s.get('side', 1)); lnow = None
    if leg in raw and day in raw[leg]: lg = P.grid(raw[leg][day], min(K, 78)); lnow = lg[-1][3] if lg else None
    if m['status'] == 'open':
        print(f"  HOLD IBS-TREND {leg} (proxy {p} entry {m['entry']:.2f}, model stop {m['stop']:.2f}, now {m['px']:.2f}, {pct_leg(m) + COST:+.2f}% on the leg)"
              + (f", {leg} {lnow:.2f}" if lnow else '') + f". Stop-market rests at F x {1 - LEV * STOP_PCT / 100:.2f}. Sell at the 15:55 slot. No new entries.")
        return
    first = s.get('status') == 'open'
    if first:
        s.update(status='closed', xbar=m['xbar'], why=m['why']); jsave(STATE, state)
        new = not os.path.exists(LOG)
        with open(LOG, 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new: w.writeheader()
            w.writerow(dict(day=day, system='IBS', side=s.get('kind') or ('long' if s.get('side', 1) > 0 else 'mirror'), proxy=p, ticker=leg, ibs=s['signals'][p]['ibs'], entry_time='9:35', entry_px_proxy=f"{m['entry']:.4f}", stop_proxy=f"{m['stop']:.4f}",
                            exit_time=P.k2t(m['xbar'] + (1 if m['why'] == 'time' else 0)), exit_px_proxy=f"{m['px']:.4f}", exit_reason=m['why'], pct_leg=f"{pct_leg(m):.3f}"))
    if m['why'] == 'time':
        print(f"  IBS EXIT (15:55, B6.5): cancel the resting stop, sell ALL {leg} now (marketable limit), verify flat, then buy USDG (B4.8). Model {pct_leg(m):+.2f}% on the leg.")
    else:
        print(f"  IBS-TREND model STOPPED at {P.k2t(m['xbar'])} (proxy {p} touched {m['stop']:.2f}); model {pct_leg(m):+.2f}% on the leg. Check the real stop filled (get_equity_orders). "
              f"If the real position is still open, leave the resting stop and sell at 15:55. No new entry today (B6.6): once flat, buy USDG and the remaining slots are one-line checks.")
    if first: print(f"  logged the model trade to archive/ibs_trades.csv")


def cmd_replay(argv):
    global MIRROR_FROM, DIP_FROM
    if '--dip' in argv: argv = [x for x in argv if x != '--dip']; DIP_FROM = '0000'
    if '--mirror' in argv: argv = [x for x in argv if x != '--mirror']; MIRROR_FROM = '0000'
    raw = json.load(gzip.open(argv[0], 'rt')); a = argv[1] if len(argv) > 1 else '0000'; z = argv[2] if len(argv) > 2 else '9999'
    days = sorted(d for d in raw['QQQ'] if len(raw['QQQ'][d]) >= 78); store = {p: {} for p in LEG}; by = {}; n = 0

    def bars(p, d):
        r = raw[p].get(d)
        if not r or len(r) < 78: return None
        return [tuple(x[1:]) for x in r[:78]]
    for d in days:
        sig = check(store, d); best = None
        if a <= d <= z:
            for p, s in sig.items():
                b = bars(p, d)
                if s['ok'] and b:
                    rv = b[0][4] / s['v0'] if s['v0'] else 0.0
                    if best is None or rv > best[1]: best = (p, rv, b, s['side'])
            if best:
                m = model(best[2], 78, best[3]); g = pct_leg(m); by[d[:4]] = by.get(d[:4], 1.0) * (1 + min(1.0, 3.0 / (LEV * STOP_PCT)) * g / 100); n += 1
        for p in LEG:
            b = bars(p, d)
            if b: store[p][d] = day_row(b)
    print(f"IBS-TREND replay {a}..{z}: {n} trades (one a day). Year returns, full cash: " + ', '.join(f"{y} {(v - 1) * 100:+.1f}%" for y, v in sorted(by.items())))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'signal': cmd_signal, 'enter': cmd_enter, 'manage': cmd_manage, 'replay': cmd_replay}.get(cmd, lambda a: print(__doc__))(sys.argv[2:])
