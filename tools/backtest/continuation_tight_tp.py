#!/usr/bin/env python3
"""Continuation (retest HOLDS -> trade with the break) with a tight all-out take-profit, vs the failed-retest fade.
    python3 tools/backtest/continuation_tight_tp.py > tools/backtest/results/continuation_tight_tp.txt
Reuses retest.py (same entries, same account: $2,000, 3% risk, one position, highest RVOL first). Exit = sell 100% at N x R, stop, or time exit.
"""
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retest as R
from lab import get_data

D = get_data(); days = D.days[25:]; h = len(days) // 2
print(f"Continuation + tight all-out TP, {days[0]}..{days[-1]} ({len(days)} days), same engine and window as retest.py. Exit 13:30 (bar 48) unless noted.\n")
def run(label, c):
    T, a = R.evaluate(D, days, c)
    print(f"{label:<62} {R.line(T, a, days, h)}")
for mode in ('hold', 'reclaim'):
    for stop in ('retest', 'mid'):
        for ex in ('R0.5', 'R0.75', 'R1.0', 'R1.5'):
            run(f"CONT {mode:<7} stop {stop:<6} all out at {ex[1:]}R", R.RC(mode=mode, stop=stop, exit=ex, time_exit=48))
print()
run("CONT hold retest-stop all out at 1R, time exit 15:55", R.RC(mode='hold', stop='retest', exit='R1.0', time_exit=77))
run("CONT hold+confirm retest-stop all out at 0.5R", R.RC(mode='hold', confirm=True, stop='retest', exit='R0.5', time_exit=48))
print()
run("FADE (failed retest), all out at 1R, 13:30", R.RC(fade=True, exit='R1.0', time_exit=48))
run("FADE (failed retest), all out at 0.5R, 13:30", R.RC(fade=True, exit='R0.5', time_exit=48))
run("FADE (failed retest), half 1R + BE, 13:30", R.RC(fade=True, exit='half1R_be', time_exit=48))
