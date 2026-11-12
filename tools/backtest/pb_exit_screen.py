#!/usr/bin/env python3
"""PULLBACK exit research (governor 2026-11-11: "find the best types of exits for consistent trends").
Entries = the live PULLBACK signal (paper.pullback, tunables in force 2026-11-12: breakout volume 1.3x, stop dip low -0.05%, min stop 0.75%).
Only the exit changes. Exits tested come from trend-following practice: fixed R targets, partial at the morning high plus a runner
trailed by Le Beau's ATR chandelier, an EMA close exit, a Donchian/Turtle N-bar low, Wilder's Parabolic SAR, Kaufman's efficiency ratio;
breakeven and lock stops; time stops; and an ADAPTIVE breakout mode (at the morning high, a strong-volume close above it switches
the trade to trend mode, a weak touch sells).
    python3 -I tools/backtest/pb_exit_screen.py > tools/backtest/results/pb_exit_screen_2026-11-12.txt
Blocks: Robinhood 2026-03-03..10-14 (8 live legs) and the Massive tape 2021-11..2026-10 (the 4 legs it holds: SOXS LABD TECS UVXY), halves split 2024-04-01.
PULLBACK alone, $2,000-style account: 3% risk capped at cash, one position at a time, 3 entries a day. A rule PASSES only if avg R per trade beats the live exit in all three blocks."""
import math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'live'))
import fade_diag as F
import paper as PP
M5 = '/tmp/claude-0/-home-user-Main/25e526f4-e830-5567-84f8-7b0fb1f877cc/scratchpad/m5/M5.json.gz'
LEGS_RH = ['SOXS', 'LABD', 'TECS', 'UVXY', 'NVDQ', 'NVD', 'MSFU', 'SSG']; LEGS_M = ['SOXS', 'LABD', 'TECS', 'UVXY']
LAST = 47; COST = (PP.PB_IN + PP.PB_OUT) * 100


class Block:
    def __init__(self, name, ds, days, legs):
        self.name, self.ds, self.days = name, ds, days
        PP.apply_tunables('2026-11-12'); PP.FLOOR_TARGET = True
        E = []; cap = {}
        def grab(b, K, k, entry, stop, T, e20=None): cap.update(k=k, entry=entry, stop=stop, T=T); return dict(status="closed")
        old = PP.pb_manage; PP.pb_manage = grab
        try:
            for s in legs:
                for d in days:
                    i = ds.idx[d]
                    if s not in ds.bars or d not in ds.bars[s] or i == 0 or ds.days[i - 1] not in ds.bars[s]: continue
                    b = ds.bars[s][d]; cap.clear()
                    if PP.pullback(b, ds.bars[s][ds.days[i - 1]], 78) and cap:
                        E.append(dict(day=d, proxy=s, b=b, prev=ds.bars[s][ds.days[i - 1]], **cap))
        finally: PP.pb_manage = old
        for t in E: prep(t)
        self.E = E


def prep(t):
    b = t['b']; ser = [x[3] for x in t['prev']] + [x[3] for x in b]
    t['e9'] = PP.ema(ser, 9)[len(t['prev']):]; t['e20'] = PP.ema(ser, 20)[len(t['prev']):]; t['atr'] = F.atr_arr(b)
    t['r'] = t['entry'] - t['stop']; t['hodR'] = (t['T'] - t['entry']) / t['r']
    k = t['k']; sar = [None] * len(b); af, ep, sv = 0.02, b[k][1], b[k - 1][2]
    for j in range(k, len(b)):
        sar[j] = sv
        if b[j][1] > ep: ep = b[j][1]; af = min(0.2, af + 0.02)
        sv = min(sv + af * (ep - sv), b[j][2], b[j - 1][2])
    t['sar'] = sar


def manage(t, c):
    """c keys: tgt ('hod' | R float | None), frac (share sold at the target), run (runner exit: None=hold to 13:30 | ('chand', x) |
    ('ema', 9|20) | ('nlow', n) | 'psar' | ('er', n)), be (R close that moves stop to breakeven), lock (trigger R, level R),
    tstop (bars: sell all at the next open if the target has not filled), adapt (vol multiple: at the morning high, a close above it
    on that volume keeps everything as a runner, otherwise sell all at the high)."""
    b, k, e, r = t['b'], t['k'], t['entry'], t['r']; stop = t['stop']
    T = t['T'] if c.get('tgt', 'hod') == 'hod' else (e + c['tgt'] * r if c.get('tgt') is not None else None)
    frac = c.get('frac', 1.0); rem, g, hit, hic, bestc, pend, out = 1.0, 0.0, False, e, 0.0, None, False; run = c.get('run'); mode = None
    j = k
    for j in range(k, LAST + 1):
        o, h, l, cl, v = b[j]
        if out: g += rem * (o - e); rem = 0; break
        if pend is not None:
            stop = max(stop, pend); pend = None
        if l <= stop: px = min(stop, o); g += rem * (px - e); rem = 0; break
        if T is not None and not hit and h >= T:
            if c.get('adapt') or c.get('hybrid'):    # adaptive: no limit rests on the adaptive shares; judge the touch bar at its close
                avgv = st.mean(x[4] for x in b[max(0, j - 6):j]) or 1
                if c.get('hybrid'):                  # hybrid: a limit at the high sells this share on the touch (real resting order)
                    px = max(T, o); q = min(c['hybrid'][0], rem); g += q * (px - e); rem -= q
                    vm = c['hybrid'][1]
                else: vm = c['adapt']
                hit = True; stop = max(stop, e)
                if cl > T and v >= vm * avgv: mode = 'trend'                  # breakout confirmed: the rest becomes a trend runner
                elif rem > 0: out = True                                      # weak touch: sell the rest at the NEXT open (no look-ahead)
                if rem <= 1e-9: break
            else:
                px = max(T, o); q = min(frac, rem); g += q * (px - e); rem -= q; hit = True
                if rem <= 1e-9: break
                stop = max(stop, e)
        cr = (cl - e) / r; bestc = max(bestc, cr); hic = max(hic, cl)
        if c.get('be') is not None and bestc >= c['be']: pend = max(pend or -1e9, e)
        if c.get('lock') and bestc >= c['lock'][0]: pend = max(pend or -1e9, e + c['lock'][1] * r)
        if c.get('tstop') and not hit and j - k + 1 >= c['tstop'] and j < LAST: out = True
        if hit and run and j < LAST:                 # runner management after the target (or in trend mode)
            if run[0] == 'chand': pend = max(pend or -1e9, hic - run[1] * t['atr'][j])
            elif run[0] == 'ema' and cl < (t['e9'] if run[1] == 9 else t['e20'])[j]: out = True
            elif run[0] == 'nlow': pend = max(pend or -1e9, min(x[2] for x in b[max(k, j - run[1] + 1):j + 1]))
            elif run[0] == 'psar' and t['sar'][j] is not None and l < t['sar'][j]: out = True
            elif run[0] == 'er' and j - k >= run[1]:
                d = sum(abs(b[i][3] - b[i - 1][3]) for i in range(j - run[1] + 1, j + 1))
                if d and (cl - b[j - run[1]][3]) / d < 0: out = True
    if rem > 0: g += rem * (b[j][3] - e)
    return dict(day=t['day'], proxy=t['proxy'], k=k, xbar=j, R_out=g / r, pct=g / e * 100 - COST, leg_risk=r / e * 100, hit=hit)


def run(B, c):
    T = [manage(t, c) for t in B.E]; a = F.account(B.ds, B.days, T); tk = a['taken']
    if not tk: return dict(n=0, ret=0, pf=0, R=0, win=0, aw=0, al=0)
    g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
    w = [x['acct'] for x in tk if x['acct'] > 0]; ls = [x['acct'] for x in tk if x['acct'] <= 0]
    return dict(n=len(tk), ret=a['ret'], pf=g / l if l else 99, R=st.mean(x['R_out'] for x in tk), win=100 * len(w) / len(tk),
                aw=st.mean(w) if w else 0, al=st.mean(ls) if ls else 0, mdd=a['mdd'])


def load():
    out = []
    ds = F.DS(None, LEGS_RH + F.LIVE)
    out.append(Block('RH 26-03..10 (8 legs)', ds, [d for d in ds.days if '2026-03-03' <= d <= '2026-10-14'], LEGS_RH))
    if os.path.exists(M5):
        dm = F.DS(M5, LEGS_M + F.LIVE); days = dm.days[21:]
        out.append(Block('MASSIVE H1 21-12..24-03 (4 legs)', dm, [d for d in days if d < '2024-04-01'], LEGS_M))
        out.append(Block('MASSIVE H2 24-04..26-10 (4 legs)', dm, [d for d in days if d >= '2024-04-01'], LEGS_M))
    return out


RUNNERS = {'hold to 13:30': None, 'chandelier 2 ATR': ('chand', 2.0), 'chandelier 3 ATR': ('chand', 3.0), 'EMA9 close': ('ema', 9),
           'EMA20 close': ('ema', 20), '3-bar low': ('nlow', 3), '6-bar low': ('nlow', 6), 'PSAR': ('psar',), 'ER6 < 0': ('er', 6)}


def configs():
    C = [('LIVE: 100% at the morning high', dict())]
    for R in (1.0, 1.5, 2.0): C.append((f'100% at {R:g}R (no morning high)', dict(tgt=R)))
    for fr in (0.5, 1 / 3):
        for rn, rv in RUNNERS.items():
            C.append((f'{"1/2" if fr == 0.5 else "1/3"} at morning high, runner {rn}', dict(frac=fr, run=rv)))
    for rn in ('chandelier 2 ATR', 'chandelier 3 ATR', 'EMA9 close', 'EMA20 close', '3-bar low', 'PSAR', 'hold to 13:30'):
        for vm in (1.0, 1.3, 2.0):
            C.append((f'ADAPTIVE: close above high on {vm:g}x vol -> trend ({rn}), else sell next open', dict(adapt=vm, run=RUNNERS[rn])))
    for fr in (0.5, 1 / 3):
        for rn in ('chandelier 2 ATR', 'chandelier 3 ATR', 'EMA20 close', 'hold to 13:30'):
            for vm in (1.0, 1.3):
                C.append((f'HYBRID: {"1/2" if fr == 0.5 else "1/3"} limit at high, rest trend ({rn}) if close above on {vm:g}x vol, else sell next open', dict(hybrid=(fr, vm), run=RUNNERS[rn])))
    for be in (0.5, 1.0): C.append((f'morning high + breakeven at +{be:g}R close', dict(be=be)))
    for lk in ((0.5, 0.15), (0.75, 0.25)): C.append((f'morning high + lock +{lk[1]:g}R at +{lk[0]:g}R close', dict(lock=lk)))
    for ts in (6, 12, 18): C.append((f'morning high + time stop {ts * 5} min', dict(tstop=ts)))
    C.append(('1/2 at high, runner chandelier 2 ATR, + lock +0.15R at +0.5R', dict(frac=0.5, run=('chand', 2.0), lock=(0.5, 0.15))))
    C.append(('ADAPTIVE 1.3x -> chandelier 2 ATR, + lock +0.15R at +0.5R', dict(adapt=1.3, run=('chand', 2.0), lock=(0.5, 0.15))))
    C.append(('1/3 at high, runner EMA20 close, + lock +0.15R at +0.5R', dict(frac=1 / 3, run=('ema', 20), lock=(0.5, 0.15))))
    return C


def main():
    BL = load(); C = configs(); base = None; rows = []
    for name, c in C:
        res = [run(B, c) for B in BL]
        if base is None: base = res
        ok = all(x['R'] > b['R'] + 1e-9 for x, b in zip(res, base)) and name != C[0][0]
        rows.append((ok, sum(x['R'] - b['R'] for x, b in zip(res, base)), name, res))
    print(__doc__.split('\n')[0])
    print('signals: ' + ' | '.join(f"{B.name}: {len(B.E)} setups" for B in BL))
    print('columns per block: total % (change vs live) | avg R per trade (change) | PF | win % | avg win / avg loss (account %). PASS = avg R better in every block\n')
    f = lambda x, b: f"{x['ret']:+7.1f}% ({x['ret'] - b['ret']:+6.1f}) R {x['R']:+.3f} ({x['R'] - b['R']:+.3f}) PF {x['pf']:4.2f} w{x['win']:3.0f}% {x['aw']:+.2f}/{x['al']:+.2f}"
    print(f"{'exit':<72} " + ' | '.join(f"{B.name:<70}" for B in BL))
    live = rows[0]; rest = sorted(rows[1:], key=lambda z: (-z[0], -z[1]))
    for ok, sc, name, res in [live] + rest:
        print(f"{('PASS ' if ok else '     ') + name:<72} " + ' | '.join(f"{f(x, b):<70}" for x, b in zip(res, base)))


if __name__ == '__main__':
    main()
