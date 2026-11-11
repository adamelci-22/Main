#!/usr/bin/env python3
"""ODTE-FADE checkpoint tool (tools/odte/ODTE_SPEC.md). Places no orders. Prints what the session does at this checkpoint.

    python3 tools/odte/odte_live.py --now 10:35 DUMP [DUMP ...]              # signal / position status
    python3 tools/odte/odte_live.py --now 10:35 --ask 3.10 DUMP [DUMP ...]   # also size the order from the contract's ask
    python3 tools/odte/odte_live.py --verify                                 # check the signal matches paper.py FADE on history

DUMPs are the same get_equity_historicals 5-minute dumps the FADE/PULLBACK checkpoint already saves (QQQ is in them).
Only completed bars are used: at --now HH:MM the last bar used is the one that ended at HH:MM.
The bucket lives in tools/odte/state.json (mode paper|live, bucket dollars). The bucket is separate from FADE/PULLBACK money.
"""
import argparse, json, math, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'tools', 'live'))
import odte_backtest as ob
import paper as P

STATE = os.path.join(HERE, 'state.json')
SYMS = ('QQQ',)                         # v1: QQQ only (SPY has no edge, IWM is weak; see results/odte_backtest.txt)


def state():
    return json.load(open(STATE))


def manage(b, K, k, dirn, stop, tgt_R=2.0, time_exit=48):
    """Replay an open trade over completed bars k..K-1 on the underlying. Returns (status, detail)."""
    S0 = b[k][0]; R = abs(S0 - stop); tgt = S0 + dirn * tgt_R * R
    for i in range(k, min(K, 78)):
        o, h, l, cl, v = b[i]
        if i >= time_exit: return 'EXIT', f'time exit 13:30: sell at market'
        adverse = l if dirn > 0 else h; favor = h if dirn > 0 else l
        if (adverse <= stop) if dirn > 0 else (adverse >= stop): return 'EXIT', f'stop hit at {P.k2t(i)} bar ({stop:.2f}): sell at market'
        if (favor >= tgt) if dirn > 0 else (favor <= tgt): return 'EXIT', f'target {tgt:.2f} (2R) reached at {P.k2t(i)} bar: sell at market'
        if i == k + 2 and (cl - S0) * dirn <= -0.5 * R: return 'EXIT', f'EARLY CUT: {P.k2t(i)} bar close {cl:.2f} is -0.5R or worse: sell at market'
    return 'HOLD', f'hold. stop {stop:.2f}, target {tgt:.2f} (2R), early cut checked at the {P.k2t(k + 2)} bar close, time exit 13:30'


def size(bucket, ask, est_loss, risk=0.35, max_prem=1.0):
    per = (ask + 0.0004) * 100
    q = min(math.floor(bucket * risk / (est_loss * 100)), math.floor(bucket * max_prem / per))
    return max(q, 0)


def checkpoint(args):
    raw = P.load(args.dumps)
    K = P.t2k(args.now)
    st = state()
    print(f"ODTE-FADE  mode {st['mode'].upper()}  bucket ${st['bucket']:.2f}  now {args.now} ({K} completed bars)")
    if st.get('halted'): print('HALTED (bucket stop). No entries. Governor clears it.'); return
    for s in SYMS:
        if s not in raw: print(f'{s}: no bars in the dumps'); continue
        days = sorted(raw[s]); today = days[-1]; prev_day = days[-2] if len(days) > 1 else None
        b = P.grid(raw[s][today], 78)
        prev_close = P.grid(raw[s][prev_day], 78)[-1][3] if prev_day else None
        sig = ob.fade_signal(b[:K] + [None] * (78 - K), prev_close, K=K)
        if sig is None: print(f'{s}: no setup today (or setup dead). Nothing to do.'); continue
        if sig == 'watching': print(f'{s}: watching (box/break/retest still open)'); continue
        k, dirn, stop = sig
        cp = 'CALL' if dirn > 0 else 'PUT'
        if k == K:                                         # the signal bar just closed: entry is at this checkpoint
            S = b[K - 1][3]; strike = round(S)
            vix = ob.load_vix(); v = vix.get(today, (args.vix or 20.0,))[0] if not args.vix else args.vix
            sigma = ob.iv_at(ob.Cfg(), v / 100 * 1.2, K)
            fill_est = ob.bs(S, strike, ob.t_left(K), sigma, dirn)
            stop_val = ob.bs(stop, strike, ob.t_left(K + 1), ob.iv_at(ob.Cfg(), v / 100 * 1.2, K + 1), dirn)
            est_loss = max(fill_est - stop_val + 0.02, 0.05)
            print(f'{s}: SIGNAL. Buy {s} {today} {strike} {cp} (0DTE, nearest-the-money strike to {S:.2f}).')
            print(f'   Limit: the ask, or mid + 0.02 if the spread is wider than 0.03. Underlying stop {stop:.2f}. '
                  f'R {abs(S - stop):.2f}. Target {S + dirn * 2 * abs(S - stop):.2f} (2R). Model premium about {fill_est:.2f}, est. loss at stop {est_loss:.2f}.')
            if args.ask:
                q = size(st['bucket'], args.ask, max(est_loss, args.ask - stop_val))
                print(f'   Size at ask {args.ask:.2f}: {q} contract(s)' + ('  -> 0: SKIP (bucket too small for the risk cap)' if q < 1 else ''))
            else:
                print('   Size: rerun with --ask <price> after get_option_quotes.')
        else:
            stat, txt = manage(b, K, k, dirn, stop)
            print(f'{s}: POSITION {cp} from the {P.k2t(k)} open ({b[k][0]:.2f}). {stat}: {txt}')


def verify():
    """Every historical day: odte signal (entry bar, side, stop) == paper.py fade() at the same bar."""
    bars = ob.load_bars(); days = sorted(bars['QQQ']); bad = n = 0
    for i, d in enumerate(days[1:], 1):
        b = bars['QQQ'][d]; prev = bars['QQQ'][days[i - 1]][-1][3]
        mine = ob.fade_signal(b, prev, runaway=None)
        theirs = None
        for K in range(8, 78):
            t = P.fade(b, K)
            if t and t.get('status') == 'signal': theirs = (t['k'], t['side'], round(t['stop'], 4)); break
            if t and t.get('status') not in (None, 'watching', 'signal'): break
        m = (mine[0], mine[1], round(mine[2], 4)) if mine and mine != 'watching' else None
        if m or theirs: n += 1
        if m != theirs: bad += 1; print('MISMATCH', d, m, theirs)
    print(f'verify: {n} signal days, {bad} mismatches (runaway skip off on both sides; paper.py applies it in simulate())')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--now'); ap.add_argument('--ask', type=float); ap.add_argument('--vix', type=float)
    ap.add_argument('--verify', action='store_true'); ap.add_argument('dumps', nargs='*')
    a = ap.parse_args()
    verify() if a.verify else checkpoint(a)
