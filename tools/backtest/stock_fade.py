#!/usr/bin/env python3
"""System 4, second design (governor 2026-11-13): the stock scanner built on the edge the book already has. The gap-scanner test
(scan_bt.py) found no long-only edge in "stocks in play". This test runs the live FADE rules (v5.2.45 entry + exits) on single-stock
proxies that have listed leveraged long AND inverse funds, so both directions stay tradable from a cash account:
  NVDA (NVDL/NVDQ) TSLA (TSLL/TSLQ) MSTR (MSTU/MSTZ) COIN (CONL/CONI) at 2x both ways; AMD (AMDL/AMDD) AMZN (AMZU/AMZD) AAPL (AAPU/AAPD)
  MSFT (MSFU/MSFD) META (METU/METD) at 2x long, 1x inverse.
The scanner = every 5-minute slot, check all proxies (6 ETFs + 9 stocks) for the FADE setup, take the first one that triggers.
Data: Massive 5-minute bars 2021-11..2026-11 (split-adjusted). Leg cost 0.10% a round trip for the single-stock funds (wider spreads).
Blocks: H1 2021-12..2024-03, H2 2024-04..2026-02, 2026 = 2026-03..10. Stop floor tested at 0.5% (live) and 1.0% (stocks move more).
    python3 -I tools/backtest/stock_fade.py DATA_DIR > tools/backtest/results/stock_fade_2026-11-13.txt"""
import datetime as dt, gzip, json, os, statistics as st, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, fade_setup_exits as FS, adaptive_exit as AE
STK = {'NVDA': (2, 2), 'TSLA': (2, 2), 'MSTR': (2, 2), 'COIN': (2, 2), 'AMD': (2, 1), 'AMZN': (2, 1), 'AAPL': (2, 1), 'MSFT': (2, 1), 'META': (2, 1)}
B = 'https://api.massive.com'; KEY = os.environ.get('MASSIVE_API_KEY', '')


def get(url):
    for a in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + ('&' if '?' in url else '?') + 'apiKey=' + KEY, headers={'User-Agent': 'research-client'}), timeout=60) as r: return json.load(r)
        except Exception as e:
            time.sleep(2 + 3 * a)
    raise RuntimeError('download failed')


def download(path):
    raw = json.load(gzip.open(AE.M5, 'rt')); days = sorted(raw['QQQ']); t0 = {d: raw['QQQ'][d][0][0] for d in days if raw['QQQ'][d]}
    for s in STK:
        out = {}; a = dt.date.fromisoformat(days[0])
        while a <= dt.date.fromisoformat(days[-1]):
            z = min(a + dt.timedelta(days=150), dt.date.fromisoformat(days[-1])); url = f"{B}/v2/aggs/ticker/{s}/range/5/minute/{a}/{z}?adjusted=true&sort=asc&limit=50000"
            while url:                                                    # the limit counts 1-minute base bars: follow next_url or days go missing
                j = get(url); url = j.get('next_url')
                for r in j.get('results') or []:
                    u = dt.datetime.fromtimestamp(r['t'] / 1000, dt.timezone.utc); d = u.strftime('%Y-%m-%d'); hm = u.strftime('%H:%M')
                    if d not in t0: continue
                    m0 = int(t0[d][:2]) * 60 + int(t0[d][3:]); m = u.hour * 60 + u.minute
                    if m0 <= m < m0 + 390 and not (out.get(d) and out[d][-1][0] == hm): out.setdefault(d, []).append([hm, r['o'], r['h'], r['l'], r['c'], r['v']])
            a = z + dt.timedelta(days=1)
        raw[s] = out; print(f"# {s}: {len(out)} days", file=sys.stderr, flush=True)
    json.dump(raw, gzip.open(path, 'wt'))


def entries(ds, ctx, days, syms, floor):
    def grab(ds_, p, d, b, k, side, entry, ext, c_, info, ctx_):
        r = (entry - ext) * side
        if r <= 0: return None
        if c_.floor_pct: r = max(r, entry * c_.floor_pct / 100)
        i = ds_.idx[d]; pv = ds_.bars[p].get(ds_.days[i - 1]) if i else None
        if bool(pv) and (b[info['touch']][3] / pv[-1][3] - 1) * 100 * (-side) >= 0.85 * (1 if p in F.LIVE else 2): return None      # runaway skip (stocks: doubled)
        if dt.date.fromisoformat(d).weekday() == 4: return None
        info.update(b=b, k=k, side=side, entry=entry, ext=entry - side * r, r=r, atr=ctx_['atr'][p][d], far_R=None); return info
    old = F._manage; F._manage = grab
    try: return F.trades(ds, days, syms, F.P(floor_pct=floor), ctx)
    finally: F._manage = old


def stat(T):
    if not T: return 'none'
    p = [t['pct'] for t in T]; gw = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
    return f"n{len(p):4d} w{100 * sum(x > 0 for x in p) / len(p):3.0f}% {st.mean(p):+.2f}% PF{(gw / gl if gl else 9):4.2f}"


def main():
    path = os.path.join(sys.argv[1], 'M5S.json.gz')
    if not os.path.exists(path): download(path)
    F.LEV.update(STK); syms = F.LIVE + list(STK); ds = F.DS(path, syms); ctx = F.context(ds, syms)
    dd = [d for d in ds.days[21:] if d <= '2026-10-30']; BL = [('H1 21-24', [d for d in dd if d < '2024-04-01']), ('H2 24-26', [d for d in dd if '2024-04-01' <= d < '2026-03-01']), ('2026 Mar-Oct', [d for d in dd if d >= '2026-03-01'])]
    print(__doc__.split('\n')[0]); print('FADE live rules. Per trade: n, win %, average leg % net, profit factor. Account: 3% risk capped at cash, one position at a time.\n')
    for floor in (0.5, 1.0):
        print(f"STOP FLOOR {floor}% of the proxy for the stocks (ETF proxies stay at 0.5%)")
        res = {}
        for bn, days in BL:
            Te = [FS.manage(t, {}) for t in entries(ds, ctx, days, F.LIVE, 0.5)]
            old = F.LEGCOST; F.LEGCOST = 0.10; FS.F.LEGCOST = 0.10
            try: Ts = [FS.manage(t, {}) for t in entries(ds, ctx, days, list(STK), floor)]
            finally: F.LEGCOST = old
            res[bn] = (days, Te, Ts)
        for s in list(STK) + ['ALL 9 STOCKS', '6 ETF PROXIES']:
            cells = []
            for bn, _ in BL:
                days, Te, Ts = res[bn]; T = Te if s.startswith('6') else Ts if s.startswith('ALL') else [t for t in Ts if t['proxy'] == s]; cells.append(f"{bn} {stat(T)}")
            print(f"   {s:<14} " + ' || '.join(cells))
        for tag, pick in (('ACCOUNT 6 ETF proxies (live)', lambda Te, Ts: Te), ('ACCOUNT 9 stocks alone', lambda Te, Ts: Ts), ('ACCOUNT ETFs + 9 stocks (scanner)', lambda Te, Ts: Te + Ts),
                          ('ACCOUNT ETFs + NVDA TSLA MSTR COIN', lambda Te, Ts: Te + [t for t in Ts if STK[t['proxy']] == (2, 2)])):
            cells = []
            for bn, _ in BL:
                days, Te, Ts = res[bn]; a = F.account(ds, days, pick(Te, Ts)); cells.append(f"{bn} {a['ret']:+7.1f}% DD {a['mdd']:4.1f} n{len(a['taken']):4d}")
            print(f"   {tag:<36} " + ' || '.join(cells))
        print()


if __name__ == '__main__':
    main()
