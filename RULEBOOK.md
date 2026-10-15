# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin**, `agentic_allowed=true`, trade approvals off.
**Policy version: 5.0.2** (2026-10-15). Bump on every rule or threshold change and record it in the commit.
**MODE: LIVE — real money, from Friday 2026-10-16** (direct governor instruction, 2026-10-15). Two systems trade the real account: FADE and PULLBACK (Part B). Orders follow B5, and the safety controls in A1 bind every entry.

**Retired rules:** everything before v4.0 is preserved word for word in `archive/RULEBOOK_v3.132_full.md`. The shelved breakout system is in `archive/SHELVED_SELECTION_RULES.md`. Nothing in either document is in force.

Nothing carries between checkpoints. State lives in this file, `archive/live_trades.csv`, `archive/paper_trades.csv` (the model's own record) and the broker, never in memory. **The broker is the truth about positions and orders.**

---

## Objective

**Target an average of about 0.4% per trading day, measured over a full year** (governor, 2026-10-15). Individual days will be red, flat or far above it. **The target never overrides a rule.** A day with no qualifying setup is a correct outcome, and no trade is ever forced.

**Evidence status:** the system has a backtest (E3) but no forward record yet. The first 25–35 live trades are the test. C5's review compares them with the model (E3 and `paper_trades.csv`).

---

## READ MAP — read only your row

| Checkpoint | Read |
|---|---|
| **9:00** research | A · C3 · D |
| **9:30** | A1.8 (overnight check) only; otherwise a one-line no-op |
| **10:00–13:25** (5-minute slots) | A · B · C1 · C2 |
| **13:30** close | A · B5.7 · C4 · C5 · D |
| **8:00pm** backup | A2 · D1 |

Part E is reference only. Pull a section when a rule points to it. `grep` for `^# PART` to find each part's current line range; never hardcode line numbers.

---

# PART A — EVERY CHECKPOINT

## A1. Safety controls — check before every real entry

**An entry is allowed only if every line below is clear. These are not judgement calls.**

| # | Control | Rule | How to check |
|---|---|---|---|
| 1 | **Losing streak** | **5 losing trades in a row → no new entries until the governor clears it.** A loss is any closed trade with net P&L below $0. A win resets the count; a trade at exactly $0.00 does not count either way. | `archive/live_trades.csv`, counted after the most recent clearance (A1 note below) |
| 2 | **Daily loss limit** | **Account down 3% or more on the day → no new entries for the rest of the day.** "Down on the day" = current total value against the 9:00 total value. Any open position keeps being managed normally. | `get_portfolio` total value against the 9:00 value recorded in E5 |
| 3 | **Bug fuse** | **No more than 6 entries in a day.** A 7th is blocked and reported at once. This is not a strategy rule; it guards against a software error. | Count today's entry fills |
| 4 | **Floor** | Never trade below **50% of deposited cash** (E1). | Recompute; never cache |
| 5 | **One position** | No entry while any position or entry order is open. | `get_equity_positions`, `get_equity_orders` (open), `get_advanced_orders` |
| 6 | **Fresh data** | `paper.py` must show bars through this slot (or say why not), and the order review's quote must agree with the last bar within 0.5%. Stale or contradictory data → no entry. | paper.py output, `review_equity_order` |
| 7 | **Spread** | Skip the entry if the leg's bid–ask spread is wider than **0.30% of its price**. | Order review quote |
| 8 | **Overnight** | **Nothing is held overnight.** A position found at 9:00 or 9:30 is sold at the 9:30 checkpoint (marketable limit) and reported. | Positions |
| 9 | **Earnings** | **Skip the AMD fade row on any session where AMD has reported since the prior close** (next: Tue 2026-11-03 after the close → skip Wed 11-04). Same for NVD on NVIDIA's report. | `get_earnings_calendar` at 9:00 |
| 10 | **Session** | Entries only between 10:00 and 12:55. No trading on early-close days (Nov 27, Dec 24) or market holidays. | Calendar |
| 11 | **Halt** | Never send an order into a halted ticker (A4). | Broker response |
| 12 | **Kill switch** | **If the governor says "stop", "halt" or "flatten":** cancel every open order, sell every position (marketable limit), and take no entries until the governor says to resume. This overrides everything else in this file. | — |

**Losing-streak clearances:** none yet. The live record starts 2026-10-16. Old-system trades in `archive/trades.csv` don't count.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`.**
2. Exactly one trigger per slot. Delete duplicates before arming.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 13:30 close or the 8:00pm backup** (D1).
5. A past-due trigger that is still enabled is a **missed** checkpoint. Do its work now, say it was missed, then delete it.

## A3. State check

At 9:00 and 13:30, and before every order, read from the broker: positions, open orders (equity and advanced/OCO), total value and buying power. **When the broker and the model disagree, the broker wins:**
- **The model shows a position the account doesn't have** (for example, a real stop filled earlier than the model's): do nothing, and never re-enter to match the model.
- **The account has something the model doesn't:** report it immediately, make sure a stop protects it (B5.5), and sell it by 13:30 at the latest (B5.7).

## A4. Faults

1. **A broker or tool call fails** (rate limit, timeout, connector drop):
   - Retry up to 3 times, waiting about 1, 2, then 4 seconds.
   - **Before retrying any order placement, check `get_equity_orders`.** A slow call may have gone through, and a blind retry would duplicate the order.
   - If it still fails: with a position open, the resting stop or OCO protects it. Report, and try again at the next slot.
2. **Halted ticker:** don't send orders. The resting stop stays. Re-check at the next slot. If the halt runs past 13:30, sell at the first checkpoint after it reopens.
3. **Partial fills:** share counts always come from `get_equity_positions`. Cancel any unfilled remainder of an entry. Protective orders are sized to the live share count exactly.
4. **Order rejected or cancelled unexpectedly** (Robinhood stops can fail silently, E6): re-check the state. A position without a confirmed protective order is handled by B5.5.
5. **`paper.py` error or missing data:** no new entry at that slot. Manage any open position from the broker state and the last good levels.

---

# PART B — THE SYSTEMS

Specs and evidence: `tools/backtest/PULLBACK_SPEC.md`, E3. `tools/live/paper.py` implements B1–B4 exactly; it reproduces the backtest trade for trade. Run it with `--live` and it prints the order instructions for each checkpoint.

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

**Thin tickers: TECS, AMDD, LABU** (about $130–260k traded per 5-minute bar). The spread check (A1.7) applies with extra force to these.

## B2. FADE — failed-retest fade (signal rules)

1. **Box:** the proxy's 9:30–10:00 high and low.
2. **Break:** a 5-minute bar **closes** outside the box, no later than the 10:10 bar. Only the first break of the day counts.
3. **Retest:** within the next 12 bars, a bar trades back to the broken edge, within 0.10%.
   - It **closes back inside** the box → the breakout failed. **Buy the opposite leg at the next checkpoint.** A failed upside break buys the inverse leg; a failed downside break buys the bull leg.
   - It closes outside the box → no trade for that proxy today.
4. **Stop:** beyond the failed breakout's extreme, on the proxy. R = the distance from entry to stop.
5. **Exit:**
   - Sell **⅓ at 2R**.
   - The other ⅔ goes to **breakeven**, then ratchets at every checkpoint to the **2-ATR chandelier**: highest proxy close since entry − 2 × ATR(14) of 5-minute bars. It never moves down.
   - **Sell anything left at 13:30.**

## B3. PULLBACK — inverse list (signal rules)

1. **Opening range:** the 9:30–9:45 high.
2. **Breakout on volume:** a later bar closes above that high, on volume above 1.5× the average of the 6 bars before it.
3. **Trend:** the 9-EMA is above the 20-EMA, and price closes above the 9-EMA. Both EMAs carry over from the prior session.
4. **Dip:** 2–5 red or lower-high bars. The dip's lowest low sits between 0.5% below the 20-EMA and 0.1% above the 9-EMA.
5. **Trigger:** a bar closes above the previous bar's high. Trigger bars run from 10:10 to 12:50.
6. **Entry:** a limit buy at the trigger close, valid for the next bar only.
7. **Stop:** dip low × (1 − 0.05%). It must be at least 0.75% below the entry.
8. **Skip** the setup if:
   - the morning high is less than 0.75 × the stop distance above the entry; or
   - the morning high is less than 0.25% above the entry; or
   - the stop and the morning high are less than $0.10 apart.
9. **Exit:** sell 100% at the morning high, or at the stop. **Sell anything left at 13:30.**

Only the first qualifying setup per ticker per day counts.

## B4. Shared rules

1. **Sizing:**
   - `shares = floor( min( buying_power ÷ ask , 3% × total_value ÷ (ask − leg_stop) ) )`.
   - Whole shares only. 0 shares → no trade.
   - With typical stops of 0.5–1.5%, buying power usually decides the size, so real risk is about 0.5–1.5% of the account.
2. **One position at a time.** The earliest trigger takes it. A setup that triggers while a position is open is **skipped**, not queued. **Real entries follow the model:** enter only on a signal `paper.py --live` prints for *this* checkpoint, and only if A1 is clear.
3. **No daily entry cap** beyond the bug fuse (A1.3).
4. **Same-bar ties:** the higher proxy RVOL wins. Then FADE beats PULLBACK, then list order.
5. **Flat by 13:30.**

## B5. Live order procedure

**B5.1 Every order:**
1. `review_equity_order` first. A clean review doesn't prove the order will be placed (E2).
2. Then place the order.
3. Then **verify its state** with `get_equity_orders` (or `get_advanced_orders` for an OCO).
4. Buys and sells are **marketable limits**, never plain market orders: buy at ask + 0.10%, sell at bid − 0.10%.
5. Protective orders (stops and OCOs) are **GTC**, so a missed 13:30 can't leave a position unprotected overnight.
6. Record the order IDs.

**B5.2 FADE entry**

`paper.py --live` prints `ENTER FADE` with the conversion factors.
1. **Buy** the leg (marketable limit, B4.1 sizing). Verify the fill F and the live share count N.
2. **Leg levels from the fill** (printed by `paper.py`):
   - `stop = F × (1 − lev × R%)`
   - `target = F × (1 + 2 × lev × R%)`
   - R% is the proxy's percentage distance from entry to its stop. Round the stop down and the target up to the cent.
3. **Protect, in the same checkpoint:**
   - **OCO** (sell, GTC) on **⅓ of the shares** (floor(N/3)): take-profit = target, stop = stop.
   - Plain **stop-market** (sell, GTC) on the other ⅔, at the stop.
   - **If N < 3:** one OCO on all shares (target and stop as above); there is no ⅔ runner.
   - **If the OCO is rejected** (it needs the stop and target each at least 0.25% from the price and at least $0.10 apart): place a stop-market on all N shares instead. Then sell ⅓ at a checkpoint once the proxy reaches 2R, using `paper.py`'s "take-profit DONE".
4. **Verify both protective orders are resting.** Otherwise apply B5.5.

**B5.3 FADE before the ⅓ take-profit:** leave the entry stop and the OCO exactly as placed. Don't re-place them because the leg's price has drifted relative to the proxy.

**B5.4 FADE runner after the ⅓ take-profit** (the OCO's take-profit filled, or the fallback sale was done):
1. Move the ⅔ stop to **breakeven (F)**: cancel → verify cancelled → place → verify resting.
2. At every later 5-minute checkpoint, `paper.py --live` prints the chandelier level converted to the leg. Raise the stop to it **only if** it's at least 0.10% above the current stop and never below F. Same cancel/verify/place/verify sequence.
3. **If the new stop would be at or above the current bid,** the stop has effectively been hit: sell the runner (marketable limit) instead.

**B5.5 A position without a confirmed protective order:** retry placing the protection once. If it still isn't resting, **sell the position now** (marketable limit) and report it. A position is never left unprotected past the checkpoint it was found in.

**B5.6 PULLBACK entry and exit**
1. `paper.py --live` prints `ENTER PULLBACK`. Place a **limit buy** (GFD) at the trigger close, sized by B4.1.
2. **At the next checkpoint:**
   - **Filled:** place **one OCO** (sell, GTC) on all shares, take-profit = the morning high, stop = the B3.7 stop. Verify it's resting.
   - **Partly filled:** cancel the remainder, then the OCO on the filled shares.
   - **Not filled:** cancel the order and verify. The setup is gone.
3. **If the OCO is rejected:** a stop-market on all shares, and sell at a checkpoint when the target trades.
4. While the OCO rests, check in at :00 and :30 only (C2).

**B5.7 13:30 close and any emergency exit:**
1. Cancel every open order on the position (OCO legs and stops) → verify cancelled.
2. Sell the live share count (marketable limit) → verify filled.
3. If it isn't filled within about a minute, re-price to the bid. If it's still unfilled, use a market order and report it.

**B5.8 Record** each closed trade in `archive/live_trades.csv` (D2), with the model's result for the same trade beside it.

---

# PART C — CHECKPOINT PROCEDURE

## C1. Each 10:00–13:25 slot

1. **State check** (A3).
2. **Fetch** 5-minute bars from the prior trading day's 9:30 to now, in three `get_equity_historicals` calls:
   - QQQ SOXX IWM XLK XBI AMD TQQQ SQQQ SOXL SOXS
   - TNA TZA TECL TECS LABU LABD AMDL AMDD UVXY NVD
   - NVDA (read-only tie-break)
3. **Run** `python3 tools/live/paper.py --live --now HH:MM <dump files>`.
4. **Act on the `LIVE ACTIONS` lines** under A1 and B5. If the newest bar isn't published yet, `paper.py` steps back up to two bars and says so.
5. **Report only changes:** an entry, a take-profit, a stop move, an exit, or a blocked entry and why. If nothing changed, write one line.

## C2. Cadence and early shutdown

- **Flat, or a FADE position is open:** run every 5-minute slot.
- **Only a PULLBACK position is open** (its OCO resting): run only the :00 and :30 slots. Every other slot is a one-line no-op.
- **Early shutdown:** delete the remaining slots before 13:30, keeping 13:30 and 8:00pm, once any of these is true:
  - it is 12:55 or later and the account is flat with no open orders;
  - the daily loss limit (A1.2) has fired and the account is flat;
  - the losing-streak lockout (A1.1) is on and the account is flat.

## C3. 9:00 research

1. **State check** (A3). Record **total value at 9:00** in E5; the daily loss limit (A1.2) is measured from it. Any position found → sell it at 9:30 (A1.8).
2. **Controls:**
   - the losing streak from `live_trades.csv` (lockout status);
   - earnings for AMD and NVIDIA (A1.9);
   - whether today is an early-close day or a holiday (A1.10).
3. **RVOL baseline:** fetch the 20 prior sessions of 5-minute bars for QQQ SOXX IWM XLK XBI AMD NVDA. Run `paper.py --build-rvol --day <today> --now 09:00 <dump>`.
4. **One line of context:** any scheduled event before 13:30, such as CPI, FOMC or a major earnings report.
5. Refresh E5, commit and push.

## C4. 13:30 close

1. **Flatten** the real account (B5.7). Verify it's flat with no open orders.
2. **Model record:** run `paper.py --now 13:30 --close <dumps>`. This appends the model's trades to `paper_trades.csv`.
3. **Log** each real trade in `live_trades.csv`.
4. **Report** (C5), **arm** the next trading day (D1), then commit and push.

## C5. Reporting

- **Report immediately:** every real entry, take-profit, stop move and exit (with the fill price and slippage against the model). Also report:
  - any safety control that fires (A1), and every blocked entry;
  - any broker or tool fault that left a position unprotected or cost a checkpoint;
  - any disagreement between broker and model (A3);
  - a break in the trigger chain.
- **13:30 daily:**
  - each trade: real P&L in dollars and %, and the model's result;
  - the day's P&L and the account value;
  - the losing-streak count;
  - running totals since 2026-10-16: trades, win rate, average %/day, real against model.
- **Friday 13:30:** the week's summary, always sent.
- **Style:** losses as plainly as gains. Never claim an edge from a small sample. Most checkpoints are one line or silent.
- **Review after 25–35 live trades:**
  - real against model against backtest: win rate, average win and loss, %/day, slippage;
  - each system separately;
  - fills on the thin tickers;
  - a recommendation to keep, resize or change.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid and arming (ET)

`9:00 · 9:30 · 10:00 · 10:05 · … every 5 minutes … · 13:25 · 13:30 · 8:00pm` — 46 slots per trading day.

- **Primary arming at the 13:30 close.**
  - Friday arms Monday. Skip market holidays.
  - Create in batches; the trigger API allows about 10 creations per minute. Then confirm all 46 with `list_triggers`.
- **Backup at 8:00pm:** check that the next trading day's chain exists. Create it only if it's missing, and say so.
- **Time zone:** triggers take UTC. ET = UTC−4 until Sun 2026-11-01, and UTC−5 from Mon 2026-11-02. Use the offset in force on the day being armed.
- **Prompt templates.** Each prompt names its slot and date, and ends: "RULEBOOK.md governs wherever this prompt differs. This is a real live trading account (Robinhood 462514035) acting on real capital."
  - **9:00:** "Live mode. Read A, C3, D. State check, record the 9:00 value, controls (streak, earnings, session), RVOL baseline, context."
  - **9:30:** "Live mode. Overnight check (A1.8): sell anything held. Otherwise a one-line no-op."
  - **10:00–13:25:** "Live mode. Read A, B, C1, C2. State check, fetch bars, run `tools/live/paper.py --live --now <slot>`, act on LIVE ACTIONS under A1/B5, report changes only, apply C2."
  - **13:30:** "Live mode. Read A, B5.7, C4, C5, D. Flatten and verify, `paper.py --close`, log the live trades, report, arm the next trading day, commit and push."
  - **8:00pm:** "Verify the next trading day's chain exists; create it only if missing, and say so."

## D2. Files

| File | What it holds |
|---|---|
| `archive/live_trades.csv` | Real trades from 2026-10-16. Append-only. Columns: `date, system, proxy, ticker, entry_time, shares, entry_px, stop_px, target_px, exit_time, exit_px, exit_reason, pnl_usd, pnl_pct_position, acct_pct, model_pct, slippage_note, order_ids, notes` |
| `archive/paper_trades.csv`, `archive/paper_state.json` | The model's own record (`paper.py --close`), for comparison |
| `archive/paper_rvol_<day>.json` | The day's RVOL tie-break baseline |
| `archive/trades.csv` | Old-system real trades (history, closed 2026-10-15) |
| `archive/` (other files), `archive/old_system_tools/` | Old-system rulebook, experiments, selection log and tools. History only; nothing in them is in force |
| `tools/backtest/` | Research code. `final_system.py` = this system's backtest; `stress.py` = its stress tests |

## D3. Changing a rule

1. A direct governor instruction.
2. A backtest in `tools/backtest`, covering both halves and the untouched March window.
3. Re-check `paper.py` against the backtest.
4. Edit this file, bump the version, add one line to the change log, then commit and push.

---

# PART E — REFERENCE (pull on demand)

## E1. Account mechanics

- **Limited margin.** Buying power equals total value, and sale proceeds are usable immediately. No borrowing beyond the account's own cash.
- **PDT restriction gone:** FINRA eliminated it effective 2026-06-04 (sourcing in `archive/RULEBOOK_v3.132_full.md`).
- **No short selling.** Inverse ETFs are bought long.
- **Floor:** 50% of deposited cash, where deposited = total value − all-time realized P&L − unrealized P&L. It does not rise with gains.

## E2. Capability verification

A broker capability is verified only by a successful call or an order response, never by documentation or inference. Record refusals verbatim.

**Not yet verified live, and confirmed on the first trade:**
1. An OCO on ⅓ of the shares alongside a separate stop on the other ⅔ (two sell orders on one position). If refused: B5.2's fallback (a stop on all shares, ⅓ sold at a checkpoint), and record the error.
2. GTC on stop and OCO orders. If refused, use GFD and rely on the 13:30 flatten and A1.8.

## E3. Evidence: backtest of this system

`tools/backtest/final_system.py`, 2026-03-03 – 10-14 (157 trading days), $2,000 start:

| | Trades | Win % | %/day | Return | Max drawdown |
|---|---|---|---|---|---|
| Combined | 116 | 59% | +0.576 | +140.5% | 3.8% |
| FADE alone | 74 | 55% | +0.456 | +99.8% | 3.8% |
| PULLBACK alone | 52 | 67% | +0.160 | +28.1% | 1.9% |
| Mar 3 – Apr 6 (never used for tuning) | 22 | 50% | +0.594 | +14.8% | 3.8% |

- **Stress tests** (`results_stress.txt`): break-even at about 0.80% extra cost per trade. +0.43%/day with 0.20% extra cost.
- **Concentration:** without the SOXX fade row, +0.40%/day. Without the 10 best days, +0.25%/day.
- **Longest losing streak:** 4. The 5-loss lockout never fired.
- **Lists and exits were chosen on the same months,** so the numbers are optimistic. Plan on +0.2–0.4%/day.

## E4. Retired systems (history only)

| Retired | Where |
|---|---|
| ORB breakout + RVOL/score ranking + ratchet (live 2026-09 – 10-15) | `archive/SHELVED_SELECTION_RULES.md`, `archive/RULEBOOK_v3.132_full.md` |
| "2 fresh + 1 re-entry" allowance, per-instrument caps, RVOL-decay block, the 3-entry daily cap (v4.0 – 4.1), the 0.5% risk throttle, the 12:30 close, the selection log | `archive/RULEBOOK_v3.132_full.md`, git history |

Only the **5-loss lockout** carries over from the old rules (A1.1, governor 2026-10-15).

## E5. Live context — dated, refreshed at 9:00, replaced wholesale

**Thursday 2026-10-15, evening (rules change).**
- **Real account:** flat, no open orders, **total value $1,993.43** (verified 19:00 ET via `get_portfolio` and `get_equity_positions`). The old-system day ended TNA +$9.67 and TMV −$0.84.
- **Live trading under v5.0 starts Friday 2026-10-16.**
- **Losing streak:** 0 (new count from 10-16).
- **Earnings:** AMD reports Tue 2026-11-03 after the close (skip the AMD fade row Wed 11-04). No NVIDIA report in the next 3 weeks.
- **Friday's chain:** re-armed under v5.0 tonight with the D1 templates; all 46 slots confirmed with `list_triggers` at 19:09 ET (13:30 = close + Friday report + arm Monday 10-19). Thursday's and Friday's 8:00pm backups use the v5.0 wording.
- **Bimonthly reminder trigger:** `trig_01Dwv81fMNH5Rw141Uy3wLKP`, next 2026-11-01.

## E6. Known issues

- **Trigger creation is rate-limited.** About 10 `create_trigger` calls per minute. Wait about 30 seconds and retry, then confirm the chain with `list_triggers`.
- **The scheduler can skip or delay a slot.** Resting protective orders cover an open position. Check for missed slots (A2).
- **The MCP connection can drop for hours.** GTC protective orders cover an open position. A missed 13:30 means flattening at the first checkpoint after reconnecting, and at 9:30 the next day at the latest (A1.8).
- **Robinhood stop orders can fail silently:** cancelled with no fill, or rejected when the stop is at or above the market price. Always verify the state (B5.1, B5.5).
- **Local git can desync from the remote.** If a push is rejected, fetch and merge; never force-push.
- **Early-close days and holidays** aren't handled by `paper.py`, so they're not traded (A1.10).
- **Daylight saving ends 2026-11-01.** Trigger UTC times shift one hour from 11-02.
- **Stress findings:**
  - semis carry the most;
  - a few big days matter;
  - Fridays were flat in the backtest (−0.05%/day; probably noise);
  - fine up to about $10k per position; at $50k the thin tickers would be too large a share of volume.
- **FADE P&L in the model** is leverage × proxy return. It tracks real leg prices within about 0.1% per trade, but real fills will differ. That's why `live_trades.csv` records both.

---

## Change log

**v5.0.2 — 2026-10-15:** `paper.py` no longer crashes when a leg's bars are missing from the dump (prints a blocked/refetch line instead) or when a dump holds no 5-minute bars. Backtest and stress results re-run identical. Friday's RVOL baseline pre-built (`archive/paper_rvol_2026-10-16.json`; 9:00 rebuilds it).

**v5.0.1 — 2026-10-15:** cleanup, no rule change. READ MAP points the 13:30 row at B5.7; A3 says how to handle an unknown position; old-system tools moved to `archive/old_system_tools/`.

**v5.0 — 2026-10-15, governor instructions:**
- **Real money starts Friday 2026-10-16** with the FADE + PULLBACK system.
- **3-entry cap removed;** a 6-entry bug fuse added.
- **5-loss lockout kept** from the old rules.
- **New:** daily loss limit −3%, full size from day one.
- **New live order procedure (B5):** the ⅓ OCO plus a ⅔ stop; proxy-to-leg conversion; GTC protection; flatten at 13:30.
- **New safety controls (A1):** spread, fresh data, overnight, earnings, session and kill switch.
- `paper.py --live` now prints the order instructions. It still reproduces the backtest exactly; the lockout logic doesn't change any backtest trade.

**v4.1 — 2026-10-15:** stress tests; `paper.py` guard against bars not yet published.

**v4.0 — 2026-10-15:** rulebook rewritten around the new system; all retired rules removed (full v3.132 archived).

Earlier versions: `archive/RULEBOOK_v3.132_full.md` and git history.
