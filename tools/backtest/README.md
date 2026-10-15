# Full-system backtest (2026-03-02 .. 2026-10-15)

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

## Decisions marked (2026-10-15) — NOT yet applied to the live rulebook

- **Remove the XLF, XLE and XBI rows** from the C4 universe (approved by the user in principle; needs a rulebook version bump before it takes effect).
  Baseline 7-month sample: XLF PF 0.24 (16 trades), XLE PF 0.38 (26), XBI PF 0.55 (23). In-sample pick; the 5-row universe was only +0.003%/day vs 8 rows, so this removes drains but creates no edge.
- **Old themes re-tested as extra rows on top of the 5 kept** (5 rows = -13.3%): +XOP (GUSH/DRIP) -6.3%, new-row trades +0.12% avg, 54% win (28 trades); +EEM (EDC/EDZ) -7.8%, +0.03% avg (33 trades); +XLRE (DRN/DRV) -12.2%, -0.26% avg; +XLU (UTSL/SDP) -16.1%, -0.44% avg, 17% win.
  Only XOP is plausibly worth keeping, on small samples. Data caveat: UTSL, SDP, DRV, EDC and EDZ trade ~6-50 five-minute bars a day (median bar volume 200-600 shares), so those legs are barely tradeable and their rows are not credible tests either way. GUSH and DRIP are the only liquid legs of the old themes.
