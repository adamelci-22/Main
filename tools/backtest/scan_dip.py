#!/usr/bin/env python3
"""System 4, third design (governor 2026-11-13): a DAILY-SIGNAL stock scanner. Every morning rank all liquid US common stocks and
ADRs on signals known at the prior close, buy the best at the open, sell at the close (day trade, nothing overnight, long only).
Data: Massive grouped daily bars (all US stocks), split-adjusted. Universe each day: price >= $10, 20-day average dollar volume >= $50M,
ticker listed today as common stock or ADR (mild survivorship bias). Cost 0.15% a round trip. No intraday stop (daily bars).
TRAIN = first half of the days, TEST = second half. Signals:
  DIP      close above the 50-day average, RSI(2) < 10      -> rank by lowest RSI(2)            (the proxy rule that passed)
  DIPDEEP  DIP and a 3-day fall of at least 1.5 x ATR%      -> rank by fall / ATR
  IBS      close above the 50-day average, IBS < 0.1        -> rank by lowest IBS
  MOMO     yesterday up >= 5% on >= 2x volume, close in the top 10% of the range -> rank by volume multiple (day-two continuation)
  WEAK     close below the 50-day average, RSI(2) < 10      -> control: the dip without the uptrend
    python3 -I tools/backtest/scan_dip.py CACHE_DIR START END > tools/backtest/results/scan_dip_2026-11-13.txt"""
import concurrent.futures as cf, gzip, json, os, pickle, re, statistics as st, sys, time, urllib.error, urllib.request
from datetime import date, timedelta
import numpy as np
K = os.environ.get('MASSIVE_API_KEY', ''); B = 'https://api.massive.com'; COST = 0.15


def get(url):
    for i in range(6):
        try: return json.loads(urllib.request.urlopen(url + ('&' if '?' in url else '?') + 'apiKey=' + K, timeout=90).read())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(1.5 * 2 ** i); continue
            return {}
        except Exception: time.sleep(2 ** i)
    return {}


def daily(d):
    j = get(f"{B}/v2/aggs/grouped/locale/us/market/stocks/{d}?adjusted=true")
    return d, {r['T']: (r['o'], r['h'], r['l'], r['c'], r['v']) for r in j.get('results', []) or [] if re.fullmatch(r'[A-Z]{1,5}', r['T']) and r.get('c', 0) >= 5 and r['c'] * r['v'] >= 5e6}


def load(cache, start, end):
    path = os.path.join(cache, f"daily_{start}_{end}.pkl.gz")
    if os.path.exists(path): return pickle.load(gzip.open(path, 'rb'))
    types = {}; url = f"{B}/v3/reference/tickers?market=stocks&active=true&limit=1000"
    while url:
        j = get(url)
        for r in j.get('results', []) or []: types[r['ticker']] = r.get('type')
        url = j.get('next_url')
    ds = []; d = date.fromisoformat(start)
    while d <= date.fromisoformat(end):
        if d.weekday() < 5: ds.append(d.isoformat())
        d += timedelta(days=1)
    with cf.ThreadPoolExecutor(8) as ex: got = dict(ex.map(daily, ds))
    D = {d: {t: v for t, v in got[d].items() if types.get(t) in ('CS', 'ADRC')} for d in ds if len(got[d]) > 500}
    pickle.dump(D, gzip.open(path, 'wb')); return D


def rsi2(c):
    ag = al = 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 2: ag += g / 2; al += lo / 2
        else: ag = (ag + g) / 2; al = (al + lo) / 2
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def main():
    D = load(*sys.argv[1:4]); days = sorted(D); H = {}
    for d in days:
        for t, v in D[d].items(): H.setdefault(t, {})[d] = v
    sig = {k: {} for k in ('DIP', 'DIPDEEP', 'IBS', 'MOMO', 'WEAK')}; base = {}
    for i in range(60, len(days)):
        d = days[i]; win = days[i - 51:i]; today = D[d]; allr = []
        for t, bar in today.items():
            h = H[t]
            if any(x not in h for x in win[-21:]) or sum(x in h for x in win) < 48: continue
            rows = [h[x] for x in win if x in h]; c = [r[3] for r in rows]; pc = c[-1]
            if pc < 10 or st.mean(r[3] * r[4] for r in rows[-20:]) < 5e7: continue
            o, hi, lo, cl, v = bar
            if abs(o / pc - 1) > 0.5: continue
            ret = (cl / o - 1) * 100 - COST; allr.append(ret + COST)
            up = pc > st.mean(c[-50:]); r2 = rsi2(c[-12:]); ph, pl = rows[-1][1], rows[-1][2]; ibs = (pc - pl) / (ph - pl) if ph > pl else 0.5
            atrp = st.mean((r[1] - r[2]) / r[3] * 100 for r in rows[-14:]); fall = -(pc / c[-4] - 1) * 100 / atrp; chg = (pc / c[-2] - 1) * 100; vm = rows[-1][4] / st.mean(r[4] for r in rows[-21:-1])
            if up and r2 < 10: sig['DIP'].setdefault(d, []).append((r2, ret, t))
            if up and r2 < 10 and fall >= 1.5: sig['DIPDEEP'].setdefault(d, []).append((-fall, ret, t))
            if up and ibs < 0.1: sig['IBS'].setdefault(d, []).append((ibs, ret, t))
            if chg >= 5 and vm >= 2 and ibs >= 0.9: sig['MOMO'].setdefault(d, []).append((-vm, ret, t))
            if (not up) and r2 < 10: sig['WEAK'].setdefault(d, []).append((r2, ret, t))
        base[d] = st.mean(allr) if allr else 0.0
    T = days[60:]; h = len(T) // 2; TR, TE = T[:h], T[h:]
    print(__doc__.split('\n')[0]); print(f"days {T[0]}..{T[-1]} ({len(T)}); TRAIN ..{TR[-1]}, TEST {TE[0]}..; cost {COST:.2f}% a round trip")
    print(f"baseline: the average liquid stock, open to close, no cost: TRAIN {st.mean(base[d] for d in TR):+.3f}% a day, TEST {st.mean(base[d] for d in TE):+.3f}%\n")
    def line(rs):
        if not rs: return 'none'
        gw = sum(x for x in rs if x > 0); gl = -sum(x for x in rs if x <= 0); return f"n{len(rs):6d} w{100 * sum(x > 0 for x in rs) / len(rs):3.0f}% {st.mean(rs):+.3f}% PF{(gw / gl if gl else 9):5.2f}"
    def port(name, ds_, n):
        r = []
        for d in ds_:
            pk = sorted(sig[name].get(d, []))[:n]; r.append(sum(x[1] for x in pk) / n if pk else 0.0)
        lg = np.log1p(np.array(r) / 100); cum = np.cumsum(lg); dd = 1 - np.exp(cum - np.maximum.accumulate(np.concatenate([[0], cum]))[1:])
        return f"{np.expm1(cum[-1]) * 100:+7.1f}% DD {dd.max() * 100:4.1f} days traded {sum(bool(sig[name].get(d)) for d in ds_):3d}"
    for name in sig:
        print(f"{name}")
        print(f"   every signal        TRAIN {line([x[1] for d in TR for x in sig[name].get(d, [])])} | TEST {line([x[1] for d in TE for x in sig[name].get(d, [])])}")
        for n in (1, 3, 5):
            print(f"   top {n} by rank       TRAIN {line([x[1] for d in TR for x in sorted(sig[name].get(d, []))[:n]])} | TEST {line([x[1] for d in TE for x in sorted(sig[name].get(d, []))[:n]])}")
        for n in (1, 3):
            print(f"   account, top {n} equal weight, full cash:  TRAIN {port(name, TR, n)} | TEST {port(name, TE, n)}")


if __name__ == '__main__':
    main()
