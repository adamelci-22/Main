# Backtests

**The live system (RULEBOOK v5.0) is tested by `final_system.py`** (FADE + PULLBACK, results in `results_final_system.txt`), with stress tests in `stress.py` (`results_stress.txt`). `tools/live/paper.py` reproduces it trade for trade. Specs: `PULLBACK_SPEC.md`; the FADE rules are RULEBOOK B2 (research in `retest.py`, `fade_*.py`). `TWO_BAR_SPEC.md` is a rejected candidate.

Shared data: `data/bt_5m.json.gz` (real Robinhood 5-minute bars from 2026-03-02), loaded through `lab.get_data()`.

Everything below documents the **retired ORB system's** backtest (`backtest.py`, `report.py`). It is history only.

---

## Retired ORB-system backtest (2026-03-02 .. 2026-10-15)

Real Robinhood 5-minute bars (earlier dates are synthetic flat fill and unusable; real data starts 2026-03-02).
Eight proxies + sixteen leveraged tickers, ~158 sessions; first tradable day 2026-03-30 (20 prior sessions for RVOL).

    python3 tools/backtest/backtest.py [--cost 0.03] [--no-throttle] [--no-ratchet] [--csv trades.csv]
    python3 tools/backtest/report.py        # sensitivity grid + breakdowns
    data/bt_5m.json.gz, data/bt_daily.json.gz   # compact bars; rebuilt by build_data.py from saved historicals dumps

Implements: C1 (RVOL>=1.0 w/ top-3 floor, 30-min ORB with 2 closes, volume test before 11:00, selection_score), v3.119
momentum for later entries, C4 leg mapping, B1 profile on the last 31 daily sessions, initial stop at the leg's own 9:30-10:00
low, C8 sizing (3% risk, 0.5% throttled; cash-capped), B2 ratchet (2x stall, min move, live>fill guard), 12:30 close, A1
allowance (2 fresh + 1 re-entry, 2/instrument, loser exclusion, rvol-decay 30%), E1 throttle (3 losses on, 2 wins off),
5-loss lockout (assumed cleared next day), C12 step-0 shortcut.

Approximations (see backtest.py docstring): entry at the open of the bar after the checkpoint +cost; stops trigger on 5-min
bar lows (gap -> open); ratchet uses completed 5-min bars; missing leg bars carried flat; thin legs (ERX, LABU, TMV) have
unrealistically clean fills; no partial fills or spread widening; costs default 0.03%/side.

**Superseded:** the ORB-system universe decisions recorded here on 2026-10-15 were never applied; the ORB system was retired the same day (RULEBOOK E4).
