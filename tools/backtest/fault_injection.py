"""Fault-injection study of the proposed checkpoint-data changes (what each would do to the engine if the cached/trimmed data is wrong).
Replays paper.simulate (which reproduces the live backtest: 115 trades, $4,764.36 from $2,000) with deliberately damaged inputs.
Also converts the late-entry result into a cost per second of delay."""
import sys, os, statistics as st, copy
sys.path.insert(0, '/home/user/Main/tools/backtest'); sys.path.insert(0, '/home/user/Main/tools/live')
from lab import get_data
import paper
paper.LOCKOUT_LOSSES = 10**6   # isolate the data effect: the 5-loss lockout (a safety rule that needs the governor to clear it) would otherwise freeze a replay after an unlucky early streak
D = get_data(); days = [d for d in D.days[1:] if '2026-03-03' <= d <= '2026-10-14']
syms = set(paper.FADE_ROWS) | {x for r in paper.FADE_ROWS.values() for x in r[:2]} | set(paper.PB_LIST) | {'NVDA'}
FADE_ONLY_LEGS = sorted({x for r in paper.FADE_ROWS.values() for x in r[:2]} - set(paper.PB_LIST))
def run(mod=None, label=''):
    eq = 2000.0; streak = 0; taken_all = []
    for d in days:
        i = D.days.index(d); pd_ = D.days[i - 1]; pd2 = D.days[i - 2]
        today = {}; prev = {}
        for s in syms:
            if s in D.bars and d in D.bars[s]: today[s] = [tuple(x[:5]) for x in D.bars[s][d]]
            if s in D.bars and pd_ in D.bars[s]: prev[s] = [tuple(x[:5]) for x in D.bars[s][pd_]]
        if mod: today, prev = mod(today, prev, D, d, pd2)
        base = {}
        for p in set(paper.FADE_ROWS) | {'NVDA'}:
            try: pri = D.prior(d, 20); base[p] = [st.mean(D.cum[p][x][k] for x in pri) for k in range(78)]
            except Exception: pass
        taken, skipped, signals, eq2 = paper.simulate(today, prev, 78, eq, base, streak)
        taken_all += taken; eq = eq2; streak = taken[-1]['streak'] if taken else streak
    pb = [t for t in taken_all if t['system'] == 'PB']; fd = [t for t in taken_all if t['system'] == 'FADE']
    print(f"{label:<62}{len(taken_all):>5} trades ({len(fd)} FADE, {len(pb)} PB)  final ${eq:>8,.2f}  ({(eq/2000-1)*100:+.1f}%)")
    return eq
print("Replay with damaged data, $2,000 start, 2026-03-03..10-14 (the live-rule backtest is the first line)\n")
run(None, 'baseline (data complete)')
for sym in paper.PB_LIST:
    def m(today, prev, D, d, pd2, sym=sym): prev.pop(sym, None); return today, prev
    run(m, f'prior-day cache MISSING for {sym} only')
def m_all(today, prev, D, d, pd2): prev.clear(); return today, prev
run(m_all, 'prior-day cache MISSING for all pullback symbols')
def m_wrong(today, prev, D, d, pd2):
    for s in list(prev):
        if s in D.bars and pd2 in D.bars[s]: prev[s] = [tuple(x[:5]) for x in D.bars[s][pd2]]
    return today, prev
run(m_wrong, 'prior-day cache from the WRONG session (two days back)')
def m_short(today, prev, D, d, pd2):
    for s in list(prev): prev[s] = prev[s][-40:] + [prev[s][-1]] * 0   # last 40 bars only; grid() pads the front
    return today, prev
run(m_short, 'prior-day cache TRUNCATED (last 40 of 78 bars)')
def m_nolegs(today, prev, D, d, pd2):
    for s in FADE_ONLY_LEGS: today.pop(s, None); prev.pop(s, None)
    return today, prev
run(m_nolegs, 'FADE-only legs not fetched at all (model record)')
print(f"\nFADE-only legs: {FADE_ONLY_LEGS}")
print("\nTime value of the delay (from late_entry_tests): one bar (5 min) late costs -0.043%/day, two bars -0.109%/day")
per_s = 0.043 / 300
print(f"  linear estimate: {per_s:.5f}%/day per second of delay; saving 10 s = {10*per_s:.4f}%/day = ${2508*10*per_s/100:.3f}/day on $2,508")
