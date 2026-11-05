#!/usr/bin/env python3
"""USDG trigger rule (RULEBOOK B4.8, governor 2026-11-05: "sell at a trigger 5 before predicted trade then immediately buy after position sell").
    python3 -I tools/backtest/usdg_trigger_backtest.py [M5.json.gz]
For every session, at every checkpoint 10:00..12:55, paper.usdg_trigger() is evaluated on the bars known at that checkpoint (rules in force, tunables v4).
  recall      : share of model entries that had a trigger at the checkpoint before the entry (5 minutes ahead). Must be 100%: a miss is a missed trade.
  precision   : share of trigger episodes that ended in an entry
  out of USDG : minutes per session spent in cash (from the first trigger slot of an episode until the position exits, or until the trigger clears with no entry)
  USDG share  : share of the 24 hours spent in USDG, and the interest it earns at 7% APY on a trading day (weekends and holidays held in USDG)
Changes no order, rule or state."""
import contextlib, gzip, io, json, os, sys
from multiprocessing import get_context
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'live')); sys.path.insert(0, HERE)
import add_trades_screen as A, improve as I, paper
M5 = sys.argv[1] if len(sys.argv) > 1 else None
RATE = 7.0


def one_day(i):
    d, pd = A.DAYS[i], A.DAYS[i - 1]
    full = {s: A.D.bars[s][d] for s in A.SYMS if d in A.D.bars.get(s, {})}
    prv = {s: A.D.bars[s][pd] for s in A.SYMS if pd in A.D.bars.get(s, {})}
    paper.OVERRIDE = dict(A.BASE); paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = '0000-00-00', '0000-00-00', True
    with contextlib.redirect_stdout(io.StringIO()):
        taken, _, _, _ = paper.simulate({s: g[:48] for s, g in full.items()}, prv, 48, 2000.0, None, 0, d)
        trig, sigs = {}, {}
        for K in range(6, 42):
            tod = {s: g[:K] for s, g in full.items()}
            tk, _, sg, _ = paper.simulate(tod, prv, K, 2000.0, None, 0, d)
            trig[K] = paper.usdg_trigger(tod, prv, K, tk, sg, d, 0)[0]
            sigs[K] = {(a, b) for a, b, t in sg if t['status'] == 'signal'}
    entries = [c['k'] for c in taken]
    reach = [(c['system'] if c['system'] == 'FADE' else 'PB', c['proxy'] if c['system'] == 'FADE' else c['ticker']) in sigs.get(c['k'], set()) for c in taken]
    hit = [bool(trig.get(k - 1)) if 6 <= k - 1 <= 41 else None for k in entries]
    unreachable = sum(1 for r in reach if not r)
    held = [any(o['k'] < c['k'] and (o['xbar'] >= c['k'] - 1 if o['status'] == 'closed' else True) for o in taken) for c in taken]      # a position was still open at the checkpoint before the entry: the cash is already out of USDG
    hit = [(True if hd else h) if r else 'n/a' for h, r, hd in zip(hit, reach, held)]
    after_exit = sum(1 for hd, r in zip(held, reach) if hd and r)
    # episodes: maximal runs of trigger-active checkpoints while flat; out-of-USDG slots = trigger slots plus slots with a position open
    out = set(K for K, v in trig.items() if v)
    for c in taken:
        end = c['xbar'] if c['status'] == 'closed' else 47
        out |= set(range(c['k'] - 1, end + 1))
    ks = sorted(K for K, v in trig.items() if v); eps = 0; prev_k = None
    for K in ks:
        if prev_k is None or K != prev_k + 1: eps += 1
        prev_k = K
    ep_with_entry = 0
    for e in _episodes(ks):
        if any(e[0] <= c['k'] - 1 <= e[1] + 1 for c in taken): ep_with_entry += 1
    return dict(day=d, entries=len(entries), hit=sum(1 for h in hit if h is True), after_exit=after_exit, reach=sum(1 for r in reach if r), unreach=unreachable, miss=[(d, k) for k, h in zip(entries, hit) if h is False], eps=eps, ep_entry=ep_with_entry, out=len(out) * 5, trigger_slots=len(ks))


def _episodes(ks):
    res = []
    for K in ks:
        if res and K == res[-1][1] + 1: res[-1][1] = K
        else: res.append([K, K])
    return res


def report(title):
    with get_context('fork').Pool(4) as pool: R = pool.map(one_day, range(1, len(A.DAYS)))
    n = len(R); ent = sum(r['entries'] for r in R); hit = sum(r['hit'] for r in R); eps = sum(r['eps'] for r in R); ee = sum(r['ep_entry'] for r in R)
    miss = [m for r in R for m in r['miss']]; out_min = sum(r['out'] for r in R) / n; trig_days = sum(1 for r in R if r['eps'])
    in_usdg = 1 - out_min / (24 * 60); interest = RATE / 365 * (7 / 5) * in_usdg
    print(f"\n{title}: {n} sessions, {ent} model entries")
    rc = sum(r['reach'] for r in R); un = sum(r['unreach'] for r in R)
    print(f"  entries a live signal would show (paper.py prints ENTER at that checkpoint): {rc} of {ent}; the other {un} are model-only entries (the model reprices the fill, the live order does not)")
    ax = sum(r['after_exit'] for r in R)
    print(f"  recall {hit}/{rc} = {100 * hit / max(rc, 1):.1f}% (includes {ax} entries that came right after another position closed: the cash was already out of USDG) | missed: {miss[:8]}")
    print(f"  sessions with a trigger {trig_days} ({100 * trig_days / n:.0f}%, {5 * trig_days / n:.1f} per week) | sell events (episodes) {eps} = {5 * eps / n:.1f} per week | episodes that ended in an entry {ee} ({100 * ee / max(eps, 1):.0f}%)")
    print(f"  out of USDG {out_min:.0f} min per session on average (of 1440) -> in USDG {100 * in_usdg:.1f}% of the time -> {interest:.4f}%/trading day at {RATE:g}% APY (weekends held in USDG); always-in-USDG would earn {RATE / 365 * 7 / 5:.4f}%")


if __name__ == '__main__':
    A.setup(I.load_data()); report('Robinhood')
    if M5:
        with contextlib.redirect_stdout(io.StringIO()):
            import backtest as BT, lab
            _raw = json.load(gzip.open(M5, 'rt')); _daily = json.load(gzip.open(os.path.join(BT.HERE, 'data', 'bt_daily.json.gz')))
            BT.load = lambda live=False: (_raw, _daily); BT.PROXIES = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF']; lab._DATA = None; DM = lab.get_data()
        A.setup(DM, sorted(DM.bars)); report('Massive 2021-11 to 2026-11')
