# Replay tools (month-end re-test)

- `minute_sim.py` — minute-resolution replay of the C1 gate + B2 management on 12 proxies (cadence, confirmation, range-length tests).
- `suggestions.py` — current rules including v3.117 (volume test before 11:00) and v3.119 (second-entry momentum check), with switches for every idea in the "Suggested Edits — Month-End Review" doc. Run: `python3 suggestions.py`.
- `data/` — 1-minute bars 2026-09-01..10-06 and 5-minute bars from 2026-08-18 (Robinhood historicals, gzipped).

To extend: fetch 1-minute bars (Robinhood caps ~5,000 bars per symbol per call — about 12 days), merge into the same JSON shape (sym -> day -> 390 bars of [o,h,l,c,v,interpolated]), append 5-minute bars likewise, and rerun. Judge each idea on the NEW days only (Oct 7 onward), not the 25 days it was chosen on.

## Exit lab (added 2026-10-08)

- `exit_lab.py` / `exit_lab_run.py` — replays EXIT rules on the real 1-minute paths of the live trades in `archive/trades.csv` (entry fixed at the actual fill and initial stop), using each ticker's own stall/min-move profile (the same 31-session formulas as `tools/profile.py`). Baseline = the live B2 trail (2 x stall, checks every 5 min, 1-minute latency). Compares trail widths, breakeven stops, profit-locks, take-profits, half-off, and earlier closes. Run: `python3 tools/replay/exit_lab_run.py`.
- `data/exit_lab_bars_1m.json.gz` — full-session 1-minute bars of the held tickers for each trade day (9/1-10/8); `data/exit_lab_daily.json.gz` — daily bars used for the profiles.
- Baseline vs reality: correlation 0.82 on 57 trades; the lab is a little optimistic (stops fill exactly at the stop, current rules applied to older trades), so compare rules to each other, not to live P&L. QBTX 9/8 is excluded (logged entry price does not match the market).
- To extend with new trades: fetch that day's 1-minute bars (13:30Z-20:00Z) for the held ticker, add to the bars file as `"SYM|YYYY-MM-DD" -> [[ts,o,h,l,c,v,interpolated],...]`, and refresh the daily file.

