#!/usr/bin/env python3
"""Run every parked suggestion (Suggested Edits doc + ideas from the session) against the baseline on the 7-month data.
    python3 tools/backtest/run_suggestions.py > results_suggestions.txt
Evidence bar from the doc: beats baseline by >0.05%/day, in >=75% of paired day-resamples, and in both halves.
"""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Cfg, Lab, stats, daily_pct, get_data

TP = lambda kind, val, scope, half=False: dict(kind=kind, val=val, scope=scope, half=half)
V = []   # (group, label, Cfg kwargs)
def add(g, label, **kw): V.append((g, label, kw))

# ---- adopted rules: would reverting them have helped? --------------------------------------
add('Adopted rules (revert test)', 'volume test ALL DAY (revert v3.117)', vol_K_end=999)
add('Adopted rules (revert test)', 'volume test OFF entirely', vol_K_end=0)
add('Adopted rules (revert test)', 'no v3.119 momentum rule (revert)', momentum='off')
add('Adopted rules (revert test)', '7% stop ceiling back (skip stop >7% away) (revert v3.116)', stop_cap=7.0)

# ---- entry timing -------------------------------------------------------------------------
for m, n in ((15, 3), (20, 4), (25, 5), (35, 7), (40, 8), (45, 9)):
    add('Entry timing', f'{m}-minute opening range', or_bars=n)
add('Entry timing', '15-min playbook (mid stop, half 1R, rest 2R, out 11:30)', or_bars=3, stop_mode='mid', playbook=True, close_K=24, ratchet=False)
add('Entry timing', '1 close to confirm', confirm=1)
add('Entry timing', '3 closes to confirm', confirm=3)
add('Entry timing', 'index ETFs (SPY/QQQ/IWM) need only 1 close', idx_confirm1=True)
add('Entry timing', 'skip if proxy entry > 1.0x ATR from its range edge', atr_skip=1.0)
add('Entry timing', 'skip if proxy entry > 0.5x ATR from its range edge', atr_skip=0.5)
add('Entry timing', 'volume test off from 10:30 (instead of 11:00)', vol_K_end=12)
add('Entry timing', '2nd-entry check strict (each of last 3 closes beyond prior)', momentum='strict')

# ---- exits and profit-taking ---------------------------------------------------------------
add('Exits', 'first trade: take profit +1.0% of position', tp=TP('pos', 1.0, 'first'))
add('Exits', 'first trade: take profit +0.5% of position', tp=TP('pos', 0.5, 'first'))
add('Exits', 'first trade: take profit +0.5% of account', tp=TP('acct', 0.5, 'first'))
add('Exits', 'first trade: take profit +1.0% of account', tp=TP('acct', 1.0, 'first'))
add('Exits', 'every trade: take profit +0.5% of position', tp=TP('pos', 0.5, 'all'))
add('Exits', 'every trade: take profit +1.0% of position', tp=TP('pos', 1.0, 'all'))
for x in (1.0, 2.0, 3.0):
    add('Exits', f'every trade: take all off at +{x}%', tp=TP('pos', x, 'all'))
for x in (1.0, 2.0):
    add('Exits', f'every trade: half off at +{x}%, trail the rest', tp=TP('pos', x, 'all', True))
add('Exits', 'tighter trail, first trade only (stall 0.10%)', first_stall=0.0010)
add('Exits', 'tighter trail, first trade only (stall 0.06%)', first_stall=0.0006)
add('Exits', 'trail multiplier 2.0 -> 1.5 (10:45) -> 1.0 (11:30)', trail_decay=True)
add('Exits', 'stop to breakeven once up 1R', be_1r=True)
add('Exits', 'breakeven stop after +0.5%', be_after=0.5)
add('Exits', 'breakeven stop after +1.0%', be_after=1.0)
add('Exits', 'exit at 12:00+ if flat (<0.10%) over 4 bars', flat_exit=0.001)
add('Exits', 'exit at 12:00+ if flat (<0.20%) over 4 bars', flat_exit=0.002)
add('Exits', 'day done once closed P&L >= +0.5% of account', day_done=('day', 0.5))
add('Exits', 'day done once closed P&L >= +0.3% of account', day_done=('day', 0.3))
add('Exits', 'day done after one trade >= +0.5% of account', day_done=('trade', 0.5))
for m in (3, 4, 5, 6):
    add('Exits', f'wider trail {m}x stall (vs 2x)', trail_mult=float(m))
add('Exits', 'lock 70% of open gain once up +1%', lock=(1.0, 0.7))
for k, lab in ((18, '11:00'), (24, '11:30'), (30, '12:00')):
    add('Exits', f'close everything at {lab} (vs 12:30)', close_K=k)
for x in (1, 2, 3, 4, 6):
    add('Exits', f'fixed {x}% initial stop (ratchet on)', stop_mode=('pct', float(x)))
add('Exits', '1% stop with 1:1 target', stop_mode=('pct', 1.0), target_R=1.0)
add('Exits', 'far target 3x the stop distance (opening-range stop)', target_R=3.0)

# ---- ranking -------------------------------------------------------------------------------
for r, lab in (('latest_before_1030', 'latest breakout before 10:30, score after (v3.118)'), ('latest_all', 'latest breakout all day'),
               ('most_room', 'most room only (least range used)'), ('widest_stop', 'widest stop'), ('tightest_stop', 'tightest stop'),
               ('highest_rvol', 'highest RVOL only'), ('earliest', 'earliest breakout'), ('most_range', 'most range used (momentum)'),
               ('strongest_break', 'strongest break past the edge'), ('rvol_x_break', 'RVOL x break strength'),
               ('rs_ratio', 'score x (ETF % move / SPY % move)'), ('rs_diff', 'score x (1 + ETF % - SPY %)'),
               ('idx_x1.5', "index ETFs' score x1.5"), ('room_lev', '% room x leverage: (1-exp) x ATR% x lev x RVOL'),
               ('pct_room', '% room: (1-exp) x ATR% x RVOL'), ('speed', 'speed only: ATR% x RVOL'), ('random', 'random pick among qualifiers')):
    add('Ranking', lab, rank=r, seed=1)

# ---- ideas from this session ---------------------------------------------------------------
add('Session ideas', 'hybrid: +1.0% TP on fresh entries, re-entries ratchet only, 4 entries / 2 re-entries',
    tp=TP('pos', 1.0, 'fresh'), max_entries=4, max_reentries=2)
add('Session ideas', 'hybrid: +0.5% TP on fresh entries, re-entries ratchet only, 4 entries / 2 re-entries',
    tp=TP('pos', 0.5, 'fresh'), max_entries=4, max_reentries=2)
add('Session ideas', 'half-sell: half off at +1%, trail rest, 4 entries / 2 re-entries',
    tp=TP('pos', 1.0, 'all', True), max_entries=4, max_reentries=2)
add('Session ideas', 'allow 4 entries / 2 re-entries with no profit-taking', max_entries=4, max_reentries=2)
add('Session ideas', 'only 2 entries a day (no re-entry)', max_entries=2, max_reentries=0)
add('Session ideas', 'entries only until 11:00', entry_end_K=17)
add('Session ideas', 'entries only 10:00-11:30', entry_end_K=23)
add('Session ideas', 'no throttle (always 3% risk)', throttle=False)
add('Session ideas', 'no ratchet (initial stop + 12:30 close)', ratchet=False)
add('Session ideas', 'cost 0.00% per side', cost=0.0)
add('Session ideas', 'cost 0.06% per side', cost=0.0006)
add('Session ideas', 'drop XLE, XLF, XBI rows (worst 3 in sample; IN-SAMPLE pick)', rows=('QQQ', 'SPY', 'SOXX', 'IWM', 'TLT'))
add('Session ideas', 'drop XLE row', rows=('QQQ', 'SPY', 'SOXX', 'IWM', 'XLF', 'TLT', 'XBI'))
add('Session ideas', 'drop XLF row', rows=('QQQ', 'SPY', 'SOXX', 'IWM', 'XLE', 'TLT', 'XBI'))
add('Session ideas', 'drop XBI row', rows=('QQQ', 'SPY', 'SOXX', 'IWM', 'XLF', 'XLE', 'TLT'))
add('Session ideas', 'only the five index/sector rows QQQ SPY SOXX IWM TLT', rows=('QQQ', 'SPY', 'SOXX', 'IWM', 'TLT'))

V = [v for v in V if v is not None]


def paired_p(diff, n=4000, seed=7):
    rng = random.Random(seed); k = len(diff); pos = 0
    for _ in range(n):
        if sum(rng.choice(diff) for _ in range(k)) > 0: pos += 1
    return pos / n


def main():
    get_data()
    base = Lab(Cfg()).run(); bd = daily_pct(base); days = list(bd)
    active = [d for d in days if d >= base.trades[0]['day']]
    h = len(active) // 2; h1, h2 = set(active[:h]), set(active[h:])
    bs = stats(base)
    print(f"Backtest 2026-03-02..2026-10-15, {len(active)} active days from {active[0]}; halves split at {active[h]}")
    print(f"BASELINE (live rules, 0.03%/side): trades {bs['trades']}  win {bs['win']:.1f}%  avg/trade {bs['avg_trade']:+.3f}%  avg/day {bs['avg_day']:+.3f}%  "
          f"return {bs['ret']:+.1f}%  PF {bs['pf']:.2f}  maxDD {bs['mdd']:.1f}%\n")
    oos = [d for d in active if d < '2026-09-01']            # before the Sep-Oct window the parked ideas were chosen on
    hdr = f"{'idea':<78}{'trd':>4}{'win%':>6}{'avg/trd':>8}{'avg/day':>8}{'ret%':>7}{'d/day':>7}{'P(bet)':>7}{'h1':>7}{'h2':>7}{'oos d':>7}{'oosP':>6}  verdict"
    group = None; passed = []
    for g, label, kw in V:
        if g != group:
            group = g; print(f"\n== {g} ==\n{hdr}")
        try:
            L = Lab(Cfg(**kw)).run()
        except Exception as e:
            print(f"{label:<78} ERROR {type(e).__name__}: {e}"); continue
        s = stats(L); vd = daily_pct(L)
        diff = [vd[d] - bd[d] for d in active]
        d1 = st.mean(vd[d] - bd[d] for d in active[:h]); d2 = st.mean(vd[d] - bd[d] for d in active[h:])
        dd = st.mean(diff); p = paired_p(diff)
        od = [vd[d] - bd[d] for d in oos]; odm = st.mean(od); op = paired_p(od)
        ok = dd > 0.05 and p >= 0.75 and d1 > 0 and d2 > 0
        strict = ok and odm > 0.05 and op >= 0.75
        verdict = ('PASSES (also out-of-sample)' if strict else 'PASSES doc bar only' if ok else ('beats base, short of bar' if dd > 0 else 'worse'))
        if ok: passed.append((label, p, op))
        print(f"{label:<78}{s['trades']:>4}{s['win']:>6.1f}{s['avg_trade']:>+8.3f}{s['avg_day']:>+8.3f}{s['ret']:>+7.1f}{dd:>+7.3f}{p:>7.0%}{d1:>+7.3f}{d2:>+7.3f}{odm:>+7.3f}{op:>6.0%}  {verdict}")
    n = len(V)
    print(f"\nVariants tested: {n}. Chance check: with {n} tests, about {n*0.1:.0f} would be expected to show P(better) >= 90% by luck alone if nothing mattered;")
    print("Bonferroni-style, a single test would need P(better) >= %.2f%% to count as significant." % (100 * (1 - 0.05 / n)))
    print("Passing the doc evidence bar:", [(a, f'{b:.0%}', f'oos {c:.0%}') for a, b, c in passed] or 'none')


if __name__ == '__main__':
    main()
