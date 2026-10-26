# PROPOSED: A1 drawdown stop (draft, not in force)

Status: draft for the governor. `RULEBOOK.md`, `paper.py` and every live setting are unchanged. Nothing here applies until the governor approves it and the version is bumped.

## 1. Rule text to add to Part A1 (new row 13)

| # | Control | Rule | How to check |
|---|---|---|---|
| 13 | **Drawdown stop** | **Account value 15% or more below its high-water mark → no new entries until the governor clears it.** The high-water mark (HWM) is the highest value of `total_value − net deposits + net withdrawals` seen at any 9:00 or 13:30 check or after any closed trade, starting at the deposit. Drawdown = 1 − current value ÷ HWM, on the same adjusted basis. An open position keeps being managed normally (stops, OCOs, the 13:30 close). | `get_portfolio` total value, the deposit log (E1), `archive/live_trades.csv` |

## 2. Clearance procedure (add under "Losing-streak clearances")

The drawdown stop is cleared only by the governor, never by time. Before clearing:

1. Run the re-test: `paper.py` replay against the broker record for every live trade since the HWM, and `massive_realleg.py` on the latest data.
2. Report to the governor: live trades since the HWM, win rate, average result per trade, the model's result for the same trades, and fill slippage from `archive/execution_log.csv`.
3. The governor decides one of three things. Clear and continue. Clear at reduced size (state the size). Stay stopped.
4. On clearance, reset the HWM to the current adjusted value and record the date, the drawdown at the stop, and the decision in E5.

A1.4 (floor at 50% of deposited cash) stays as the last line. A1.13 binds first.

## 3. Evidence to cite in E3

`tools/backtest/results/massive_dd_stop.txt` (`massive_dd_stop.py`). Real-leg FADE plus PULLBACK with the live account rules, cost +0.10% per round trip, Massive bars 2021-11 to 2026-10.

- Each calendar year restarted at $2,000. End value and maximum drawdown with no drawdown stop, then with a 15% stop and a 20-day pause:

| Year | No stop | 15% stop, 20 days |
|---|---|---|
| 2022 | $1,355, DD 35% | $1,391, DD 33% |
| 2023 | $1,406, DD 31% | $1,462, DD 27% |
| 2024 | $1,443, DD 30% | $1,504, DD 27% |
| 2025 | $1,219, DD 47% | $1,627, DD 30% |
| 2026-03 to 10 | $3,237, DD 7% | $3,237, DD 7% (never triggers) |

- A time-based restart does not fix a losing run. All five years in one account, the 15% stop with a 20-day or 40-day pause still hits the 50% floor (halted 2023-06 and 2024-01).
- A hard stop with no restart ends at $1,798 with a maximum drawdown of 15% (10% stop: $1,899, 10%). This is why clearance is by the governor and not by time.
- The stop never triggered in 2026-03 to 10 (maximum drawdown 7%), so it removes none of the profit seen in that window.

## 4. Version and change-log line

Version: **5.2.16** (governor to confirm the number). A1 gains a 13th control. No signal, sizing, exit or list rule changes.

Change-log text: **v5.2.16 — YYYY-MM-DD, governor instruction:** safety control only. New A1.13 drawdown stop (15% below the high-water mark, governor clears). Evidence: `results/massive_dd_stop.txt`. `paper.py` records the HWM and blocks entries while the stop is active; the replay of the backtest is unchanged (111 = 111).

## 5. Implementation notes for `tools/live/paper.py` (not done)

- Add `hwm`, `dd_stop_active`, `dd_stop_date` to `archive/paper_state.json`.
- Read net deposits from the E1 log so deposits and withdrawals do not move the HWM.
- Update the HWM after each closed trade and at the 9:00 and 13:30 checks. Print `BLOCKED A1.13` for every entry while active.
- Add `--clear-dd` for the governor, which resets the HWM and logs the decision.
- Test with a replay: a synthetic 15% loss must block the next entry, and a clearance must resume it.

## 6. Decisions for the governor

- Threshold: 15% is the draft. 10% would stop earlier and cut more of the loss (hard stop ends at $1,899). 20% would allow more (measured: 2022 ends at $1,298, DD 37%).
- Basis: the real account. The model account (`paper_state.json`) would use its own equity. State which.
- Whether to add the 30-trade review (separate draft) alongside this rule.
