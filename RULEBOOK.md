# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin**, `agentic_allowed=true`.
**Policy version: 4.0** (2026-10-15 cleanup). Bump on every rule or threshold change and record it in the commit.
**MODE: PAPER TRADING, from Monday 2026-10-19.** Real-money entries are paused. Checkpoints run two systems, FADE and PULLBACK (Part B), on a $2,000 paper account using `tools/live/paper.py`. **No real order of any kind is placed.**

**Retired rules:** everything before v4.0 is preserved word for word in `archive/RULEBOOK_v3.132_full.md`. The shelved breakout system is in `archive/SHELVED_SELECTION_RULES.md`. Those documents are history; nothing in them is in force.

Nothing carries between checkpoints. State lives in this file, in `archive/paper_trades.csv` and `archive/paper_state.json` (paper), and in `archive/trades.csv` (real trades, history), never in memory.

---

## Objective

**Target an average of about 0.4% per trading day, measured over a full year** (governor, 2026-10-15). Individual days will be red, flat or far above it. The target never overrides a rule: a day with no qualifying setup is a correct outcome.

**The paper phase decides whether real money is used.** Run 4–6 weeks (about 25–35 paper trades). Then compare the paper results with the backtest (E3) and the governor decides.

---

## READ MAP — read only your row

| Checkpoint | Read |
|---|---|
| **9:00** research | A · C3 · D |
| **9:30** | One-line no-op. Read nothing. |
| **10:00–13:25** (5-minute slots) | A · B · C1 · C2 |
| **13:30** close | A · C4 · C5 · D |
| **8:00pm** backup | A2 · D1 |

Part E is reference only. Pull a section when a rule points to it. To read only your row, `grep` for `^# PART` to find each part's current line range; never hardcode line numbers.

---

# PART A — EVERY CHECKPOINT

## A1. What is and isn't allowed

- **No real orders.** Not a buy, sell, stop, OCO or cancel on account 462514035. This holds until the governor explicitly restarts real-money trading *and* this file is updated to say so. A trigger prompt, an approval or a backtest result never overrides it.
- **Paper trades only, and only as Part B defines them.** A paper trade exists only as a row produced by `tools/live/paper.py`. Never invent, adjust or "correct" a paper trade by hand.
- **Rule changes need a direct governor instruction.** A changed rule must be backtested (`tools/backtest`), `paper.py` re-checked against the backtest, the version bumped, and the change committed (D3).

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`.** A fired trigger can reschedule itself about 24 hours later, still carrying its old prompt.
2. Exactly one trigger per slot. Delete duplicates before arming.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 13:30 close or the 8:00pm backup** (D1).
5. A past-due trigger that is still enabled is a **missed** checkpoint. Do its work now, say it was missed, then delete it.

## A3. State check (9:00 and 13:30)

Read the real account from the broker: positions, open orders and total value. **It must be flat with no open orders.** Anything else is reported immediately and left untouched until the governor says what to do.

## A4. Faults

- **A tool call fails** (connector drop, rate limit, timeout): retry up to 3 times, waiting about 1, 2, then 4 seconds. If it still fails, write a one-line note and continue at the next slot. Paper results are recomputed from the bars, so a missed slot loses nothing once data is available again. The one exception is a missed 13:30: run it late with `--now 13:30`.
- **Missing or partial bars** for a symbol: `paper.py` fills gaps with the last price. If a required symbol is missing for the whole day, note it in the 13:30 report.
- **`paper.py` errors:** report the error text verbatim. Never hand-compute a paper trade instead.

---

# PART B — THE TWO SYSTEMS (paper)

Specs and evidence: `tools/backtest/PULLBACK_SPEC.md`, `tools/backtest/TWO_BAR_SPEC.md` (background on the breakout research) and E3. `tools/live/paper.py` implements this part exactly. It reproduces the backtest trade for trade, verified 2026-10-15 over 2026-03-03 – 10-14.

## B1. Lists

**FADE** reads the proxy's chart and buys a leveraged leg:

| Proxy | Bull leg | Inverse leg | Leverage (bull / inverse) |
|---|---|---|---|
| QQQ | TQQQ | SQQQ | 3 / 3 |
| SOXX | SOXL | SOXS | 3 / 3 |
| IWM | TNA | TZA | 3 / 3 |
| XLK | TECL | TECS | 3 / 3 |
| XBI | LABU | LABD | 3 / 3 |
| AMD | AMDL | AMDD | 2 / 1 |

**PULLBACK** reads each ticker's own chart and buys only: **SOXS, LABD, TECS, UVXY, NVD.**

Thin tickers, where real fills would be worse than the backtest assumes: **TECS, AMDD, LABU** (about $130–260k traded per 5-minute bar).

## B2. FADE — failed-retest fade

1. **Box:** the proxy's 9:30–10:00 high and low.
2. **Break:** a 5-minute bar **closes** outside the box, no later than the 10:10 bar. Only the first break of the day counts.
3. **Retest:** within the next 12 bars, a bar trades back to the broken edge, within 0.10%.
   - That bar **closes back inside** the box → the breakout failed. **Buy the opposite leg at the next bar's open.** A failed upside break buys the inverse leg; a failed downside break buys the bull leg.
   - That bar closes outside the box → no trade for that proxy today.
   - No retest within 12 bars → no trade.
4. **Stop:** beyond the failed breakout's extreme (its highest high for an upside failure, lowest low for a downside one), measured on the proxy. R = the distance from entry to stop.
5. **Exit:**
   - Sell **⅓ at 2R**.
   - The other ⅔ moves to a **breakeven stop**, then ratchets at every checkpoint to the **2-ATR chandelier**: highest close since entry − 2 × ATR(14) of 5-minute bars, on the proxy. It never moves down.
   - **Sell anything left at 13:30.**
6. **P&L:** leg return ≈ leverage × proxy return − 0.06% round trip. Checked against real leg prices: within about 0.1% per trade.

## B3. PULLBACK — inverse list

Checked on each ticker's own 5-minute chart. The 9- and 20-period EMAs carry over from the prior session.
1. **Opening range:** the 9:30–9:45 high.
2. **Breakout on volume:** a later bar closes above that high, on volume above 1.5× the average of the 6 bars before it.
3. **Trend:** at the trigger, the 9-EMA is above the 20-EMA and price closes above the 9-EMA.
4. **Dip:** 2–5 bars, each either red or making a lower high. The dip's lowest low sits between 0.5% below the 20-EMA and 0.1% above the 9-EMA.
5. **Trigger:** a bar closes above the previous bar's high. Trigger bars run from 10:10 to 12:50.
6. **Entry:** a limit buy at the trigger close. It fills only if the next bar trades down to it. If it doesn't fill, keep watching that ticker.
7. **Stop:** dip low × (1 − 0.05%). It must be at least 0.75% below the entry.
8. **Skip** the setup if any of these is true:
   - the morning high (the high before the dip) is less than 0.75 × the stop distance above the entry;
   - the morning high is less than 0.25% above the entry;
   - the stop and the morning high are less than $0.10 apart.
9. **Exit:** sell 100% at the morning high, or at the stop. **Sell anything left at 13:30.**
10. **Costs:** 0.01% to enter, 0.03% to exit.

Only the first qualifying setup per ticker per day counts.

## B4. Shared account rules

1. **Paper account:** starts at $2,000 and compounds. Each trade risks 3% of paper equity at the stop, capped at the paper cash available. With typical stops of 0.5–1.5%, the cash cap usually decides the size.
2. **One position at a time.** The earliest trigger gets it. A setup that triggers while a trade is open is **skipped**, not queued.
3. **At most 3 entries per day**, across both systems together.
4. **Same-bar ties:** the higher proxy RVOL wins (today's cumulative volume against the 20-session average at the same time of day; NVD uses NVDA). Then FADE beats PULLBACK, then list order.
5. **Flat by 13:30.**

## B5. If real money is approved later (not in force)

These are the live-execution facts gathered so far. Turning them into real-order rules is a separate, explicit change.
- **Orders:** a FADE entry is a marketable order at the next checkpoint. A PULLBACK entry is a limit order valid for one bar.
- **Robinhood OCO:** one take-profit limit and one stop-market on the same ticker and quantity, regular hours only.
  - Each price must be at least 0.25% from the current price.
  - The two prices must be at least $0.10 apart.
  - The FADE's ⅓ take-profit needs its own OCO on ⅓ of the shares, plus a plain stop on the other ⅔. The other ⅔ is moved at checkpoints (cancel, then re-place).
- **FADE levels are proxy prices.** Convert each to the leg's price at entry: leg price × (1 + leverage × the proxy's percentage distance).
- **Thin tickers (B1)** need a fill-quality check before real use.

---

# PART C — CHECKPOINT PROCEDURE

## C1. Each 10:00–13:25 slot

1. **Fetch** 5-minute bars from the prior trading day's 9:30 to now, in three `get_equity_historicals` calls:
   - QQQ SOXX IWM XLK XBI AMD TQQQ SQQQ SOXL SOXS
   - TNA TZA TECL TECS LABU LABD AMDL AMDD UVXY NVD
   - NVDA (read-only tie-break)
2. **Run** `python3 tools/live/paper.py --now HH:MM <dump files>`. It uses completed bars only and recomputes the whole day from scratch.
3. **Report only changes:** a new paper entry, the ⅓ take-profit, a stop move on the FADE runner, or an exit. If nothing changed, write one line.

## C2. Cadence and early shutdown

- **Flat, or a FADE paper position is open:** run every 5-minute slot.
- **Only a PULLBACK paper position is open:** run only the :00 and :30 slots. Every other slot is a one-line no-op.
- **Early shutdown:** delete the remaining slots before 13:30, keeping 13:30 and 8:00pm, once either is true:
  - it is 12:55 or later and no paper position is open; or
  - 3 entries are used and the last one has closed.
- **No paper trading on early-close sessions** (13:00 close: Nov 27 and Dec 24, 2026) or market holidays. The 9:00 checkpoint says so, and the day is not armed (D1).

## C3. 9:00 research

1. **Real account** (A3): it must be flat with no open orders.
2. **RVOL baseline:** fetch the 20 prior sessions of 5-minute bars for QQQ SOXX IWM XLK XBI AMD NVDA. Run `paper.py --build-rvol --day <today> --now 09:00 <dump>`. This writes `archive/paper_rvol_<day>.json`. If it is missing, ties fall back to list order.
3. **Paper equity** from `archive/paper_state.json`.
4. **One-line market context.** Note any scheduled event before 13:30 (CPI, FOMC, a major earnings report in the list's names). This is context only; it changes nothing.
5. Refresh E5, commit and push.

## C4. 13:30 close

1. Run `python3 tools/live/paper.py --now 13:30 --close <dumps>`. This appends the day's paper trades to `archive/paper_trades.csv` and updates `archive/paper_state.json`.
2. Real account check (A3).
3. Report (C5), arm the next trading day (D1), then commit and push.

## C5. Reporting

- **Report immediately:**
  - a paper entry, ⅓ take-profit or exit;
  - any real-account surprise (A3);
  - a tool or data fault that cost a checkpoint;
  - a break in the trigger chain.
- **13:30 daily:**
  - each paper trade, the day's paper P&L, paper equity;
  - running totals: trades, win rate, average %/day since the start;
  - the same figures from the backtest (E3) for comparison.
- **Friday 13:30 weekly report:** the week's paper trades, totals since the start, and the paper-vs-backtest comparison. It is always sent, even on a week with no trades.
- **Style:** losses as plainly as gains. Never claim an edge from a small sample. Most checkpoints are one line or silent. A day with no trades gets no evening message.
- **Review point:** after 25–35 paper trades, report:
  - paper vs backtest: win rate, average win and loss, %/day;
  - each system separately;
  - the share of trades on thin tickers;
  - a recommendation: go live, keep paper trading, or change rules.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid and arming (ET)

`9:00 · 9:30 · 10:00 · 10:05 · … every 5 minutes … · 13:25 · 13:30 · 8:00pm` — 46 slots per trading day.

- **Primary arming: the 13:30 close** arms the next trading day.
  - Friday arms Monday. Skip market holidays: the next trading day after a holiday is armed instead.
  - Create triggers in batches. The trigger API allows about 10 creations per minute (E6). Then confirm all 46 with `list_triggers`.
- **Backup at 8:00pm:** check that the next trading day's chain exists. Create it only if it's missing, and say so.
- **Time zone:** triggers take UTC.
  - ET = UTC−4 until Sunday 2026-11-01.
  - ET = UTC−5 from Monday 2026-11-02.
  - Arm with the offset in force on the day being armed.
- **Prompt templates.** Each prompt names its slot and date. Each ends: "RULEBOOK.md governs wherever this prompt differs. Robinhood 462514035 is a real account; in paper mode no order is placed."
  - **9:00:** "Paper mode. Read A, C3, D. Real-account check, RVOL baseline, paper equity, one-line context."
  - **9:30:** "One-line no-op."
  - **10:00–13:25:** "Paper mode. Read A, B, C1, C2. Fetch bars, run `tools/live/paper.py --now <slot>`. Report changes only. Apply C2's cadence and early shutdown."
  - **13:30:** "Paper mode. Read A, C4, C5, D. Run `paper.py --close`, real-account check, report, arm the next trading day, commit and push."
  - **8:00pm:** "Verify the next trading day's chain exists; create it only if missing, and say so."
- **Transition, Friday 2026-10-16:** Friday's chain was armed under the old rules (to 12:30). Every Friday slot is a one-line no-op, because paper mode starts Monday. **Friday's 12:30 slot arms Monday 10/19 with this grid** and sends the Friday report. Friday's 8:00pm verifies Monday.

## D2. Files

| File | What it holds |
|---|---|
| `archive/paper_trades.csv` | Paper trades. Append-only; written by `paper.py --close`. |
| `archive/paper_state.json` | Paper equity and the days logged. |
| `archive/paper_rvol_<day>.json` | The day's RVOL tie-break baseline. |
| `archive/trades.csv` | Real trades. Append-only history; untouched in paper mode. |
| `archive/selection_log.csv` | Retired (old breakout system). No longer appended. |
| `tools/backtest/` | Research code and results. `final_system.py` is the current system's backtest. |

## D3. Changing a rule

1. A direct governor instruction.
2. A backtest of the change, in `tools/backtest` (both halves of the period and the untouched March window).
3. Update `tools/live/paper.py` if the rule is in it, and re-check that it matches the backtest exactly.
4. Edit this file, bump the version, add one line to the change log, then commit and push.

---

# PART E — REFERENCE (pull on demand)

## E1. Account mechanics

- **Limited margin.** Buying power equals total value, and sale proceeds are usable immediately, so same-day rotation is possible. There's no borrowing beyond the account's own cash.
- **PDT restriction gone:** FINRA eliminated it effective 2026-06-04. Full sourcing is in `archive/RULEBOOK_v3.132_full.md`.
- **No short selling.** Bearish views go through inverse ETFs bought long.
- **Floor:** never trade real money below 50% of deposited cash. Deposited = total value − all-time realized P&L − unrealized P&L; it does not rise with gains.

## E2. Capability verification

A broker capability is verified only by a successful call or an order response, never by documentation or inference. Record refusals verbatim. Never write a rule around a mechanism that hasn't been seen to work.

## E3. Evidence: the current system's backtest

`tools/backtest/final_system.py`, 2026-03-03 – 10-14 (157 trading days), $2,000 start, same rules as Part B:

| | Trades | Win % | %/day | Return | Max drawdown |
|---|---|---|---|---|---|
| **Combined** | 116 (3.7/week) | 59% | **+0.576** | +140.5% | 3.8% |
| FADE alone | 74 | 55% | +0.456 | +99.8% | 3.8% |
| PULLBACK alone | 52 | 67% | +0.160 | +28.1% | 1.9% |
| Mar 3 – Apr 6 (never used for tuning) | 22 | 50% | +0.594 | +14.8% | 3.8% |

**Caveats:**
- Lists and exits were chosen on the same months, so the numbers are optimistic.
- The top 5 trades made about 35% of the profit.
- Fills on thin tickers are assumed at the bar price.
- The full weakness test is in `tools/backtest/results_stress.txt`.
- **Plan on +0.2–0.4%/day until paper trading says otherwise.**

## E4. Retired systems (history only)

| Retired | Superseded by | Where |
|---|---|---|
| ORB breakout + RVOL/score ranking + ratchet (live 2026-09 – 10-15) | v3.123 | `archive/SHELVED_SELECTION_RULES.md`, `archive/RULEBOOK_v3.132_full.md` |
| Daily allowance "2 fresh + 1 re-entry", per-instrument caps, RVOL-decay re-entry block, E1 risk throttle / 5-loss lockout, 12:30 close, selection log | v4.0 | — |

None of these are in force. If real money is approved, the governor decides which risk controls (for example a loss-streak throttle) come back. Each one returns only as an explicit new rule.

## E5. Live context — dated, refreshed at 9:00, replaced wholesale

**Thursday 2026-10-15 (cleanup day).**
- **Real account:** flat after Thursday's two trades under the old system (TNA +$9.67, TMV −$0.84). Total value is about $1,993.43. Real entries have been paused since v3.123.
- **Paper account:** $2,000.00, not started. First paper day is **Monday 2026-10-19**.
- **Friday 2026-10-16:** a transition day of no-ops (D1). Its 12:30 slot arms Monday with the paper grid.
- **Bimonthly reminder trigger:** `trig_01Dwv81fMNH5Rw141Uy3wLKP`, next run 2026-11-01.

## E6. Known issues

- **Trigger creation is rate-limited.** About 10 `create_trigger` calls per minute. A refusal loses nothing: wait about 30 seconds, retry, then confirm the whole chain with `list_triggers`.
- **The scheduler can skip or delay a slot.** Seen 2026-10-05: one slot never fired, others fired 1–2 minutes late. Paper results are recomputed from bars, so a skipped slot only delays reporting. Check for missed slots (A2).
- **The MCP connection can drop for hours.** Seen 2026-09-17. The next slot after reconnecting runs normally. A missed 13:30 is run late (A4).
- **Local git can desync from the remote.** Seen 2026-09-09. If `git push` is rejected, fetch and merge; never force-push over the remote.
- **Robinhood stop orders can fail silently** (relevant only for real money): cancelled with no fill, or rejected when the stop is at or above the market price. Verify every placed order's state (E2).
- **Early-close and holiday sessions** aren't handled by `paper.py`. They're skipped (C2).
- **Daylight saving ends 2026-11-01.** Trigger UTC times shift by one hour from Monday 11/02 (D1).

---

## Change log

**v4.0 — 2026-10-15, governor instruction: "push all of these rules, clean up, remove any old and conflicting rules that are no longer in use".**
- The rulebook was rewritten around the paper-trading system (FADE + PULLBACK).
- Removed rules that are no longer in use: the shelved ORB/score system, the old daily allowance and re-entry rules, the risk throttle and lockout, the 12:30 grid, the selection log, and the vehicle-map history.
- The full v3.132 text is preserved in `archive/RULEBOOK_v3.132_full.md`.
- The objective is restated as an average of about 0.4%/day (governor, 2026-10-15).
- Rule content carried forward unchanged from v3.127–v3.132:
  - FADE list: QQQ, SOXX, IWM, XLK, XBI, AMD;
  - PULLBACK list: SOXS, LABD, TECS, UVXY, NVD;
  - one position at a time, 3 entries per day, 13:30 close, the 5- and 30-minute cadence.
- Added: the half-day/holiday rule, the DST note, and the Friday 10/16 transition note.

Earlier versions (v3.0–v3.132): see `archive/RULEBOOK_v3.132_full.md` and git history.
