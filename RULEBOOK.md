# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin**, `agentic_allowed=true`, trade approvals off.
**Policy version: 5.2.39** (v5.2.39 2026-10-29: FADE runaway skip, B2.3, live from 2026-10-29 ~10:55 ET by the governor's direct instruction. Every earlier version is in the change log at the end.) Bump on every rule or threshold change and record it in the commit.
**MODE: LIVE — real money, from Friday 2026-10-16** (direct governor instruction, 2026-10-15). Two systems trade the real account: FADE and PULLBACK (Part B). Orders follow B5, and the safety controls in A1 bind every entry.

**Retired rules:** everything before v4.0 is preserved word for word in `archive/former_systems/RULEBOOK_v3.132_full.md`. The shelved breakout system is in `archive/former_systems/SHELVED_SELECTION_RULES.md`. Nothing in either document is in force.

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
| **13:30 loop trigger** | C4 steps 5-6 · D4 |

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
| 6 | **Fresh data** | `paper.py` must show bars through this slot (or say why not). **PULLBACK:** the order review's quote must agree with the last bar within 0.5%. **FADE (v5.2.3, band widened v5.2.9):** the leg's quote must be within **1.5%** of the leg price at the signal bar (two-sided), and the order must be sent **no later than 6 minutes after the slot** (counted when the order is sent). A late FADE signal inside both limits is a valid entry: marketable limit (B5.1), stop and target re-set from the actual fill with the same R (B5.2), normal sizing. Later than 6 minutes, or outside 1.5% → no entry, logged as skipped. Stale or contradictory data → no entry. | paper.py output, `review_equity_order` |
| 7 | **Spread** | Skip the entry if the leg's bid–ask spread is wider than **0.30% of its price**. | Order review quote |
| 8 | **Overnight** | **Nothing is held overnight.** A position found at 9:00 or 9:30 is sold at the 9:30 checkpoint (marketable limit) and reported. | Positions |
| 9 | **Earnings** | **Single-stock funds (v5.2.21: NVD and NVDQ = Nvidia, MSFU = Microsoft): no real entry on any session where the company reported since the prior close** (a pm report bars the next session). `paper.py` applies it from its `EARNINGS_SKIP` dates (MSFU 2026-10-29, NVD/NVDQ 2026-11-18, MSFU 2027-01-28, NVD/NVDQ 2027-02-25; prints `EARNINGS SKIP`); the model is unchanged. | `get_earnings_results` for MSFT and NVDA at 9:00 (C3): if a date moved, pass `--skip` and update `EARNINGS_SKIP` |
| 10 | **Session** | Entries only between 10:00 and 12:55. No trading on early-close days (Nov 27, Dec 24) or market holidays. **No FADE entries on Fridays (v5.2.17, from Fri 2026-10-30); PULLBACK still trades Fridays.** | Calendar; `paper.py` blocks entries on the dates in its `NO_TRADE` list (through 2027-12-31) and blocks FADE on Fridays (prints `FRIDAY: no FADE entries today`) |
| 11 | **Halt** | Never send an order into a halted ticker (A4). | Broker response |
| 12 | **Kill switch** | **If the governor says "stop", "halt" or "flatten":** cancel every open order, sell every position (marketable limit), and take no entries until the governor says to resume. This overrides everything else in this file. | — |
| 13 | **Drawdown stop (v5.2.16)** | **If total value is 15% or more below its all-time high → HARD STOP: cancel every open order, sell any position (marketable limit), take no entries, and stay stopped until the governor clears it** (`hwm.py clear`). The all-time high is the highest total value ever recorded at a checkpoint, kept in `archive/hwm.json` (starts at $2,535.56, the 2026-10-24 close). Deposits and withdrawals move the high by the same dollars (`hwm.py deposit`), so they never count as a drawdown or a new high. Measured at every state check on the live total value, including the mark of an open position, so it can fire mid-day. The system is otherwise unchanged. | `python3 tools/live/hwm.py check <total value>` at **every** state check (exit 2 = stopped). `paper.py --live` also blocks entries while `hwm.json` says halted |

**Losing-streak clearances:** none yet. The live record starts 2026-10-16. Old-system trades in `archive/trade_history/old_system_trades.csv` don't count.

## A2. Trigger hygiene (v5.2.34)

1. The standing scheduled triggers are the **8:41 ET weekday morning wake** (v5.2.35, governor instruction 2026-10-28) and the **13:30 ET weekday loop trigger** (D1). Slot checkpoints are never armed as scheduled triggers (v5.2.26).
2. List triggers at 9:00. Report and delete any one-shot that already fired (`ended_reason='run_once_fired'`), and report any trigger you do not recognise; never delete the 8:41 morning or 13:30 loop trigger.
3. A scheduled message that arrives while a waiter already ran the same step is answered in one line.

## A3. State check

At 9:00 and 13:30, and before every order, read from the broker: positions, open orders (equity and advanced/OCO), total value and buying power. **When the broker and the model disagree, the broker wins:**
- **The model shows a position the account doesn't have:** never re-enter to match the model. If a real stop or target filled earlier than the model's, the account just waits for the model's next signal. **If the governor closed the real position by hand** (governor 2026-10-16), the real account is **free for new signals from that moment**: run `paper.py --live --real-free`, which lists new signals even while the model's own position is open. The broker check (A1.5) still guards every entry, and the model's open trade is simply not matched by a real one (log `model_pct` from the model at the close).
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
| XLF | FAS | FAZ | 3 / 3 |

**PULLBACK** reads each ticker's own chart and buys only: **SOXS, LABD, TECS, UVXY, NVDQ, NVD, MSFU, SSG** (v5.2.21; NVDQ and NVD are inverse Nvidia, MSFU is 2x Microsoft, SSG is −2x semiconductors). Same-bar tie order: this list order after RVOL (B4.4).

**Thin tickers: TECS, FAZ, LABU, SSG** (about $55–270k traded per 5-minute bar; SSG and FAZ are the thinnest). The spread check (A1.7) applies with extra force to these.

## B2. FADE — failed-retest fade (signal rules)

1. **Box:** the proxy's 9:30–10:00 high and low.
2. **Break:** a 5-minute bar **closes** outside the box, no later than the 10:10 bar. Only the first break of the day counts.
3. **Retest:** within the next 12 bars, a bar trades back to the broken edge, within 0.10%.
   - It **closes back inside** the box → the breakout failed. **Buy the opposite leg at the next checkpoint.** A failed upside break buys the inverse leg; a failed downside break buys the bull leg.
   - It closes outside the box → no trade for that proxy today.
   - **Runaway skip (v5.2.39, governor 2026-10-29):** no trade if, at the retest bar's close, the proxy is already **0.85% or more** past the prior session's close in the breakout direction (an upside break of a proxy up 0.85%+ on the day, or a downside break of one down 0.85%+). Do not fade a runaway. `paper.py` applies it from tunables v2 (`x.fade_max_trend` 0.85).
4. **Stop:** beyond the failed breakout's extreme, on the proxy. R = the distance from entry to stop.
5. **Exit:**
   - *(v5.2.18's frozen 1R trail was removed by v5.2.22 before it ever traded live.)*
   - **+0.15R lock (v5.2.19, from Wed 2026-10-28):** at the first 5-minute bar that **closes** at +0.5R or better, the stop goes to **+0.15R** (raised only). It stays there until the ⅓ at 2R; nothing else moves the stop before 2R.
   - **Early cut (v5.2.19, from Wed 2026-10-28):** at the close of the **3rd bar after entry** (15 minutes in), if that close is at **−0.5R or worse**, **sell everything at the next checkpoint** (`paper.py --live` prints `EARLY CUT`).
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
9. **Exit:** sell 100% at the morning high, or at the stop. **Sell anything left at 13:30.** The take-profit limit is **the morning high rounded DOWN to the cent** (e.g. high 8.8687 → limit 8.86), so a retest of the high fills. The skip rules in step 8 use that rounded price. *(Effective Mon 2026-10-19; Fri 10-16's LABD order is at 8.87.)*

Only the first qualifying setup per ticker per day counts.

## B4. Shared rules

1. **Sizing:**
   - `shares = floor( min( buying_power ÷ ask , 3% × total_value ÷ (ask − leg_stop) ) )`.
   - **Version in force (D4):** the 3% is `risk.pct`. A third term `floor(cap% × total_value ÷ ask)` joins the `min` only while `size.cap_pct` is below 100; in v1 it is 100, so the term is off and today's sizing is unchanged. Both are percentages of the account, never dollars, and the loop may only lower them.
   - Whole shares only. 0 shares → no trade.
   - With typical stops of 0.5–1.5%, buying power usually decides the size, so real risk is about 0.5–1.5% of the account.
2. **One position at a time.** The earliest trigger takes it. A setup that triggers while a position is open is **skipped**, not queued. **Real entries follow the model:** enter only on a signal `paper.py --live` prints for *this* checkpoint, and only if A1 is clear.
3. **No daily entry cap** beyond the bug fuse (A1.3).
4. **Same-bar ties:** the higher proxy RVOL wins. Then FADE beats PULLBACK, then list order.
5. **Flat by 13:30.**
6. **Liquidity cap (DORMANT below $100,000).** Active only while `total_value` (read at the checkpoint) is **≥ $100,000**; it switches off by itself whenever the value is under $100,000 and back on when it is at or above it. While active, after B4.1 sizes the order: `shares = min(shares, floor(0.10 × signal-bar dollar volume ÷ ask))`, where signal-bar dollar volume = close × volume of the 5-minute bar that gave the signal, for the leg being bought. If the cap cuts the order, log `cap` in the notes and the execution log (B5.9). The cap only reduces size; it never adds a trade or changes a stop or target. Evidence: `tools/backtest/results/cap_best.txt`, `scale_500k.txt` (impact is an assumption; tune the 10% from logged slippage). `paper.py` does not enforce it: apply it by hand at B4.1 until the code is updated before the account nears $100k.

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
   - R% is the proxy's percentage distance from entry to its stop. Round the stop down **and the target down** to the cent (target rounding: from Mon 2026-10-19; before that, up).
3. **Protect, in the same checkpoint:**
   - **OCO** (sell, GTC) on **⅓ of the shares** (floor(N/3)): take-profit = target, stop = stop.
   - Plain **stop-market** (sell, GTC) on the other ⅔, at the stop.
   - **If N < 3:** one OCO on all shares (target and stop as above); there is no ⅔ runner.
   - **If the OCO is rejected** (it needs the stop and target each at least 0.25% from the price and at least $0.10 apart): place a stop-market on all N shares instead. Then sell ⅓ at a checkpoint once the proxy reaches 2R, using `paper.py`'s "take-profit DONE".
4. **Verify both protective orders are resting.** Otherwise apply B5.5.

**B5.3 FADE before the ⅓ take-profit (v5.2.19, v5.2.22):** leave the entry stop and the OCO as placed **until `paper.py --live` prints `STOP RAISE`** (the model's proxy close has reached +0.5R, which locks +0.15R; v5.2.22 removed the frozen trail, so +0.15R is the only raise before 2R). Then raise the stop on **all** shares to the printed level: real stop = F × (1 + lock × lev × R%), where lock is the printed R level (+0.15) and R% the proxy risk %, rounded down to the cent. Raise only, and only if at least 0.10% above the resting stop. Sequence: cancel the OCO → verify → re-place the OCO (same ⅓ take-profit, new stop) → verify; cancel the ⅔ stop-market → verify → place it at the new stop → verify. If the OCO is rejected (stop within 0.25% of the price), use one stop-market on all shares and sell ⅓ at a checkpoint when the target trades (as B5.2). If the new stop is at or above the bid, sell everything (marketable limit). Otherwise don't re-place orders just because the leg's price has drifted relative to the proxy. **Early cut (v5.2.19):** when `paper.py --live` prints `EARLY CUT` (15 minutes after entry the proxy closed at −0.5R or worse), sell the whole position at that checkpoint by the B5.7 steps: cancel the OCO and the ⅔ stop → verify → marketable limit sell of every share → verify flat.

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

**B5.9 Execution log (data only — changes no entry, exit or filter).** For every real order placed (entry, OCO/stop, exit), append one row to `archive/execution_log.csv` at the time: `date, ticker, system, side, purpose, checkpoint_et, sent_et_sec, ack_et_sec, bid, ask, spread_pct, ref_px, limit_px, fill_px, slippage_pct, shares, notes, delay_min, fire_et` (`delay_min` = minutes from the slot to when the order was sent; `fire_et` = the ET time, to the second, that the checkpoint's trigger fired, taken from the trigger message, so scheduler lateness = `fire_et` − slot and processing time = send time − `fire_et`). `bid/ask` = the live quote just before sending; `ref_px` = the trigger close (PULLBACK) or the signal price; `slippage_pct` = (fill − ref) / ref for buys, (ref − fill) / ref for sells. Also log the bid/ask/spread for every PULLBACK or FADE signal that is **skipped** (blocked, not filled, or ignored) with `purpose=skipped`. Review after about 15 pullback fills, or when the account passes $5,000, whichever is first; look at UVXY and LABD slippage first.

**B5.8 Record** each closed trade in `archive/live_trades.csv` (D2), with the model's result for the same trade beside it.

**B5.8a Dashboard right after each exit (v5.2.27, governor instruction 2026-10-28).** As soon as a real position is fully closed (take-profit, stop, early cut or hand close), in that same checkpoint: log the trade (B5.8), run `python3 tools/live/dash_data.py <tmp dir>`, upload `live_trades.json`, `live_days.json` and the merged `periods.json` to the scorecard artifact, and update `datasets/live_trades`, `datasets/live_days` and `datasets/periods` (C5). `health.json` only changes at the 13:30 `health.py` run. Reporting only; the 13:30 refresh still runs and covers the full day.

---

# PART C — CHECKPOINT PROCEDURE

## C1. Each 10:00–13:25 slot

1. **State check** (A3).
2. **Fetch** 5-minute bars from the prior trading day's 9:30 to now, in three `get_equity_historicals` calls (v5.2.21):
   - QQQ SOXX IWM XLK XBI XLF TQQQ SQQQ SOXL SOXS
   - TNA TZA TECL TECS LABU LABD FAS FAZ UVXY
   - NVDQ NVD MSFU SSG
3. **Run** `python3 tools/live/paper.py --live --now HH:MM <dump files>` (`--skip TICKER` bars a ticker from real entries for the day, e.g. after a corporate-action flag in C3). **Never add `--real-free` routinely:** only after the governor closed a real position by hand (A3). A skipped or blocked entry leaves a ghost position that correctly blocks new entries until the model exits (tested: `results/recheck_all.txt` §2).
4. **Act on the `LIVE ACTIONS` lines** under A1 and B5. If the newest bar isn't published yet, `paper.py` steps back up to two bars and says so.
5. **Report only changes:** an entry, a take-profit, a stop move, an exit, or a blocked entry and why. If nothing changed, write one line.
6. **Heartbeat (v5.2.6).** Put one line in every checkpoint report: the ET time the trigger fired (`fire_et`) and the gap since the previous checkpoint's fire time, e.g. `fired 10:15:02 (+5:01)`. **Flag it at once** if the gap is more than 7 minutes, or if a slot between 10:00 and 12:55 has no earlier run today (a missed checkpoint). On a flag: say so in that report, run the missed slot's scan now (C1.3, with the late-entry limits of A1.6), and note it in the execution log. The heartbeat changes no order, signal or size.

## C2. Cadence and early shutdown

- **Flat, or a FADE position is open:** run every 5-minute slot.
- **Only a PULLBACK position is open** (its OCO resting): run only the :00 and :30 slots. Every other slot is a one-line no-op.
- **Early shutdown:** the remaining slot waiters before 13:30 answer in one line (13:30 still runs), once any of these is true:
  - it is 12:55 or later and the account is flat with no open orders;
  - the daily loss limit (A1.2) has fired and the account is flat;
  - the losing-streak lockout (A1.1) is on and the account is flat.

## C3. 9:00 research

1. **State check** (A3). Run `python3 tools/live/hwm.py check <total value>` (A1.13). Record **total value at 9:00** in E5; the daily loss limit (A1.2) is measured from it. Any position found → sell it at 9:30 (A1.8).
2. **Controls:**
   - the losing streak from `live_trades.csv` (lockout status);
   - whether today is an early-close day or a holiday (A1.10).
   - **corporate actions (v5.2.6):** for the 13 traded funds (TQQQ SQQQ SOXL SOXS TNA TZA TECL TECS LABU LABD FAS FAZ UVXY) and the proxies, check for a split or reverse split, ticker change, halt or delisting notice, and compare each fund's current quote with yesterday's close. If a fund is more than **20%** off yesterday's close without the underlying index having moved anywhere near that, or any notice is found, **exclude that fund for the day** (no entries, and use the proxy-based exit if it is held), note it in E5 and the 9:00 report. If everything is clean, write one line.
3. **RVOL baseline:** fetch the 20 prior sessions of 5-minute bars for QQQ SOXX IWM XLK XBI XLF. Run `paper.py --build-rvol --day <today> --now 09:00 <dump>`.
4. **One line of context:** any scheduled event before 13:30, such as CPI, FOMC or a major earnings report.
5. Refresh E5, commit and push.

## C4. 13:30 close

1. **Flatten** the real account (B5.7). Verify it's flat with no open orders.
2. **Model record:** run `paper.py --now 13:30 --close <dumps>`. This appends the model's trades to `paper_trades.csv`.
3. **Log** each real trade in `live_trades.csv`.
4. **Report** (C5), then commit and push. Nothing is armed for the next day (D1: the session starts its waiters at 9:30).
5. After `paper.py --close`, fetch the watchlist research group (the symbols in `tools/live/watchlist.json` not in the C1.2 groups, at most 10 per call, 5-minute bars from the prior trading day's 9:30), then run `python3 tools/live/improve.py tick <the day's dump files, watchlist dumps included>` and paste its output into the report, with any CHANGE DUE, SCRAPPED or PUSH REQUEST line at the top (D4). On CHANGE DUE or SCRAPPED, pick and start the next trial in the same close (D4 step 2). A scheduled trigger fires this at 13:30 ET each weekday, after the last exit; it first checks that the account is flat and that the C4 close has run, and is a one-line no-op on a non-trading day.
6. **Extend the research dataset (v5.2.30):** run `python3 tools/backtest/extend_live.py <the day's dump files, watchlist dumps included>` (a dump without QQQ only adds its symbols to sessions already in the file) (it adds every complete session in the dumps, so each close adds the prior day) and commit `tools/backtest/data/live_5m.json.gz`. `improve.py` reads the base file plus this one; old research scripts read the base file only.

## C5. Reporting

- **Report immediately:** every real entry, take-profit, stop move and exit (with the fill price and slippage against the model). Also report:
  - any safety control that fires (A1), and every blocked entry;
  - any broker or tool fault that left a position unprotected or cost a checkpoint;
  - any disagreement between broker and model (A3);
  - a missed slot or a waiter that did not fire (D1).
- **13:30 daily:**
  - each trade: real P&L in dollars and %, and the model's result;
  - the day's P&L and the account value;
  - the losing-streak count;
  - running totals since 2026-10-16: trades, win rate, average %/day, real against model;
  - **FADE health (v5.2.20):** after the day's trades are in `archive/live_trades.csv`, run `python3 tools/live/health.py <total value>` and paste its table and verdict. It tracks, rolling: profit factor of the last 30 FADE trades (healthy > 1.5, warning 1.0–1.5, ACT < 1.0); % of the last 30 FADE trades reaching +2R (healthy > 40%, warning 30–40%, ACT < 30%); drawdown from the all-time high (healthy < 7%, warning 7–10%, ACT ≥ 10%; A1.13 stops at 15%). Below 30 trades the trade measures are provisional; below 10 they never count as ACT. **Two or more ACT → tell the governor plainly; the governor decides** (switch FADE to the S1 stretch-filter version, or pause and review). The tracker changes no order or rule; one row per day goes to `archive/health_log.csv`. **PULLBACK health (v5.2.21)** is printed below it: profit factor of the last 30 PULLBACK trades (> 1.5 / 1.0–1.5 / < 1.0), win rate (> 60% / 50–60% / < 50%), average trade as % of position (> +0.20% / 0–0.20% / < 0); two or more ACT → the governor decides between going back to SOXS LABD TECS UVXY and dropping PULLBACK; the probation review is at 30 live PULLBACK trades. **Both systems also show (v5.2.23):** execution gap = average (real − model) per trade over the last 30, % of position (healthy > −0.10%, warning −0.10 to −0.25%, ACT < −0.25%; counts toward the two-ACT rule; a trade marked `exclude_from_gap = yes` in `archive/live_trades.csv`, i.e. a governor hand close, is left out of the gap only); trade frequency = trades in the last 30 trading days against the Robinhood backtest pace (FADE 0.40, PULLBACK 0.32 trades per trading day; healthy ≥ 60%, warning 30–60%, below 30% = CHECK TOOLING, which never counts as ACT: check fetch groups, waiters and data first); and the since-launch profit factor (information). The window stays at 30 trades (governor, 2026-10-28). **Scorecard dashboard (v5.2.25):** after the health step, refresh the live rows of https://claude.ai/artifact/L32g69SPjyXnfqaCKh7p6R: `python3 tools/live/dash_data.py <tmp dir>`, upload `live_trades.json`, `live_days.json`, `health.json` and `periods_live.json` merged as `periods.json` with the Artifact tool (`asset: true`, `url` above; `periods.json` = the backtest row from the existing file plus the live row), then `update` `datasets/live_trades`, `datasets/live_days`, `datasets/health` and `datasets/periods` (`source.url` = the new `/_blob/...`, `updated.at`). Reporting only. When logging a FADE trade, fill `reached_2R`: `yes` if the position reached +2R while held (the ⅓ take-profit filled), else `no`; blank for PULLBACK.
- **Friday 13:30:** the week's summary, always sent.
- **Style:** losses as plainly as gains. Never claim an edge from a small sample. Most checkpoints are one line or silent.
- **Review after 25–35 live trades:**
  - real against model against backtest: win rate, average win and loss, %/day, slippage;
  - each system separately;
  - fills on the thin tickers;
  - a recommendation to keep, resize or change.

---

# PART D — SCHEDULE & ADMIN

## D1. The trading day and its waiters (ET, v5.2.34)

The checkpoint chain of scheduled triggers was retired by v5.2.26 (governor, 2026-10-28: "remove all the scheduled checks forever, only keep the waiters"); its text is in `archive/former_systems/D1_A2_scheduled_chain_v5.2.25.md`. The day runs from the session's own waiters:

| Time | What runs it | What happens |
|---|---|---|
| 8:41 | the scheduled morning wake (weekdays; before 9:00 because the scheduler runs late from 9 to 12 ET) | C3 research (the pre-open value is the day's 9:00 value), A2, then start the 9:30 waiter |
| 9:30 | the 9:30 waiter | A1.8 overnight check; then start **batch 1** waiters 10:00 ... 11:25 (18) |
| 10:00-13:25 | slot waiters | C1 at each slot; the 11:25 checkpoint starts **batch 2** (11:30 ... 13:25, 24); the 13:20 checkpoint starts a fresh **13:30** waiter with `timeout` 900000 |
| 13:30 | the 13:30 waiter | C4 close and C5 report |
| 13:30 (about 13:37) | the scheduled loop trigger (weekdays) | checks flat, runs the close if the waiter did not, then C4 steps 5-6 (shadow tick, dataset); a one-line no-op when already done |

- **Waiters.** `tools/live/slot_clock.sh HH:MM` sleeps on the system clock until HH:MM:06 ET (it reads America/New_York, so daylight saving needs nothing) and exits, which wakes the session (about 7 s). Start each with Bash `run_in_background`, description `Slot waiter HH:MM`, `timeout` 7200000 (the 2-hour cap: never start a waiter more than 2 hours before its slot). Each waiter appends `date,slot,due_epoch,fired_epoch` to `archive/waiter_log.csv` (commit it at 13:30); `python3 tools/live/slot_report.py --from 2026-10-23` reports coverage and lag.
- **A missed slot** (a waiter that did not fire, or batch 2 not started) is reported at once (C1.6) and its scan run late within A1.6's limits.
- **Waking the session (v5.2.35):** waiters live only while the session runs, so the 8:41 morning trigger wakes it each weekday and starts the 9:30 waiter, and the 13:30 trigger is the back-up close. If the 8:41 wake is missed, the day has no trades until the session is woken; the trade-frequency measure (C5) flags it.
- **Early shutdown (C2):** once it applies, the remaining waiters before 13:30 answer in one line.
- **Time zone:** convert any ET time for a trigger with `bash tools/live/et2utc.sh "YYYY-MM-DD HH:MM"` (ET = UTC−4 until Sun 2026-11-01, UTC−5 from Mon 2026-11-02, back to UTC−4 on Sun 2027-03-14). Never hard-code the offset.
- **Trading days:** weekdays not in `paper.py`'s `NO_TRADE` (holidays and the early closes Nov 27 and Dec 24, through 2027).
- **Deposits and withdrawals (v5.2.15):** nothing is held overnight, so at 9:00 compare total value with the previous 13:30 value. An unexplained change is a deposit or withdrawal: record it in E1 and E5, run `python3 tools/live/hwm.py deposit <+/-amount>` so the A1.13 high moves with it, and add the amount to the model equity in `archive/paper_state.json` so the model's dollars stay comparable.

## D2. Files

| File | What it holds |
|---|---|
| `archive/live_trades.csv` | Real trades from 2026-10-16. Append-only. Columns: `date, system, proxy, ticker, entry_time, shares, entry_px, stop_px, target_px, exit_time, exit_px, exit_reason, pnl_usd, pnl_pct_position, acct_pct, model_pct, slippage_note, order_ids, notes` |
| `archive/execution_log.csv` | Per-order spread, timestamps and slippage (B5.9). Append-only; data only, no rule reads it |
| `archive/paper_trades.csv`, `archive/paper_state.json` | The model's own record (`paper.py --close`), for comparison |
| `archive/paper_rvol_<day>.json` | The day's RVOL tie-break baseline |
| `archive/trade_history/`, `archive/former_systems/` | Old-system trades, selection log, rulebook and shelved rules. History only; nothing in them is in force. Map: `archive/README.md` |
| `tools/backtest/` | Research code. `final_system.py` = this system's backtest; `stress.py` = its stress tests; outputs in `results/` (`research_results_former.txt` holds every other experiment) |

## D3. Changing a rule

1. A direct governor instruction.
2. A backtest in `tools/backtest`, covering both halves and the untouched March window.
3. Re-check `paper.py` against the backtest.
4. Edit this file, bump the version, add one line to the change log, then commit and push.
5. **Rulebook artifact (v5.2.28, governor instruction 2026-10-28):** https://claude.ai/artifact/LLqr3TUXyCcESFwfc19EYf shows this file and the live and backtest code as one page. After ANY change to `RULEBOOK.md` or to a file listed in `tools/live/rulebook_artifact.py`, in the same checkpoint run `python3 tools/live/rulebook_artifact.py <out.html>` and publish the output to that URL with the Artifact tool (`url` set, read it first if this session has not; no icon). Reporting only.

**D4. Improvement cycle (v5.2.36, governor instruction 2026-10-28; replaces the forward-shadow gate of v5.2.31-35, whose text is in `archive/former_systems/D4_loop_v5.2.31-35.md`).** FADE and PULLBACK are improved as if they were completely separate systems, each with its own cycle in `archive/improve/cycle.json`, run by `improve.py tick` at every close (C4 step 5). Continuous:
1. **Wait for 5 trades** of the system (the model record, `archive/paper_trades.csv`). Then look at the goals of the whole system: the real account since launch, mean %/day against the 0.4% target and drawdown against the 15% limit (`tunables.json` goals).
2. **Goal met:** no change; wait for the next 5 trades. **Goal not met:** `tick` prints CHANGE DUE and the session picks ONE change for that system that it thinks will help, based on that system's last 5 trades: `improve.py review fade|pb` lists the last 5 trades, the goals and every change available for the system (its tunables, ideas and watchlist tickers) with its effect, on its own, on those trades' days and on the whole dataset; then `improve.py trial fade|pb <id> "why"`. A change touches only that system, except the two shared sizing numbers `risk.pct` and `size.cap_pct` (one step down at a time, v5.2.37): they can be trialled in either cycle but are pushed only when **both** cycles have passed the same change (governor 2026-10-28). A1 is never part of a cycle.
3. **Paper trade the changed system in parallel with the live system for 10 trades** of the system, from the next trading day: each close, both versions run on the day's real bars, each system on its own, with no orders (`archive/improve/trial_log.csv`).
4. **Judge:** changed minus live, summed over the trial, as % of the account. **+0.20% or more = better:** `tick` prints PUSH REQUEST and the session asks the governor. **−0.20% or worse:** scrapped. **In between (not different):** 5 more trades; still not different = scrapped. A scrapped or declined change is written to `tools/live/research_ledger.json` and is not offered again under the same live version; the session picks the next change at once.
5. **Push:** only on the governor's instruction, `improve.py push fade|pb --effective <future trading day> --note "<governor's words>"`; then the system waits for its next 5 trades. **Decline:** `improve.py decline fade|pb`, then the next change.

**Information printed at every close (decides nothing):** the regime line with the edge monitor, the stressed chance of the −15% stop (`improve.py risk`, `defensive`), Friday live-vs-model attribution (`improve.py attrib`). The watchlist (`tools/live/watchlist.json`, `screen`, `watch-add`) supplies ticker changes for step 2; trading a pushed ticker also needs the D3 steps in `improve.py add-checklist`. The old commands (`evidence`, `prune`, `submit`, `approve`, `promote`, `defend`) are kept for history and are not part of the cycle.

**D4 session rules.** The session may run `review`, `trial` (step 2), `screen` and `watch-add`. It never runs `push`, `decline`, `approve`, `promote`, `discard`, `rollback` or `reject`, and never edits `tools/live/tunables.json` by hand, unless the governor gives that exact instruction in writing in the chat. CHANGE DUE, SCRAPPED and PUSH REQUEST go at the top of the 13:30 report; on CHANGE DUE or SCRAPPED the session picks and starts the next trial in that same close and says which and why; on PUSH REQUEST it tells the governor at once and waits.

---

# PART E — REFERENCE (pull on demand)

## E1. Account mechanics

- **Limited margin.** Buying power equals total value, and sale proceeds are usable immediately. No borrowing beyond the account's own cash.
- **PDT restriction gone:** FINRA eliminated it effective 2026-06-04 (sourcing in `archive/former_systems/RULEBOOK_v3.132_full.md`).
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
| Combined | 111 | 61% | +0.548 | +130.9% | 3.1% |
| FADE alone | 75 | 57% | +0.419 | +88.8% | 4.5% |
| PULLBACK alone | 45 | 69% | +0.158 | +27.7% | 1.9% |
| Mar 3 – Apr 6 (never used for tuning) | 20 | 55% | +0.613 | +15.3% | 2.8% |
| Halves of the 157 days | | | +0.562 / +0.535 | | |

(v5.2.14 lists: FADE QQQ SOXX IWM XLK XBI XLF; PULLBACK SOXS LABD TECS UVXY. v5.2.13 with NVD: combined +0.544, PULLBACK alone +0.153 (67% wins), drawdown 4.4%. Why NVD went: single stock; 5 trades taken, +$16, negative without its best trade; dropping it raised PULLBACK alone from +0.153 to +0.158 with March unchanged. See `results/pb_alone_search.txt` (all 33.5M PULLBACK lists from the governor's table) and `results/drip_check.txt`.)

(v5.2.13 list: XLF replaces AMD. The v5.2.12 list with AMD scored +0.570%/day, 115 trades, 59% wins, +138.2%, drawdown 4.1%, halves +0.553 / +0.586, March window +0.594; it is kept in `tools/backtest/results/final_system.txt`. Why AMD went: single stock, 198% bull run over the window, 9 of its 10 shorts lost; without its own best two signals it was negative on the leg; 12 of its 19 signals shared a day with the other five. See `results/amd_check.txt`, `results/fade_etf_only.txt`, `results/xle_vs_xlf.txt`.)

- **Stress tests** (`tools/backtest/results/stress.txt`, measured on the v5.2.12 list): break-even at about 0.80% extra cost per trade. +0.42%/day with 0.20% extra cost.
- **Concentration:** without the SOXX fade row, +0.39%/day. Without the 10 best days, +0.24%/day.
- **Longest losing streak:** 4. The 5-loss lockout never fired.
- **Lists and exits were chosen on the same months,** so the numbers are optimistic. Plan on +0.2–0.4%/day.

## E4. Retired systems (history only)

| Retired | Where |
|---|---|
| ORB breakout + RVOL/score ranking + ratchet (live 2026-09 – 10-15) | `archive/former_systems/SHELVED_SELECTION_RULES.md`, `archive/former_systems/RULEBOOK_v3.132_full.md` |
| "2 fresh + 1 re-entry" allowance, per-instrument caps, RVOL-decay block, the 3-entry daily cap (v4.0 – 4.1), the 0.5% risk throttle, the 12:30 close, the selection log | `archive/former_systems/RULEBOOK_v3.132_full.md`, git history |

Only the **5-loss lockout** carries over from the old rules (A1.1, governor 2026-10-15).

## E5. Live context — dated, refreshed at 9:00, replaced wholesale

Earlier E5 text is kept in `archive/e5_history.md`.

**Thursday 2026-10-29, 9:00 research (run at 8:44 ET by the 8:41 morning trigger, v5.2.37).**
- **9:00 value (A1.2 base): $2,573.22**, flat, no open orders. Drawdown stop clear: high $2,596.99, stop $2,207.44, −0.92% from the high. Daily loss limit fires at $2,496.02 (−3%).
- **Controls:** losing streak 0 (4 live trades, all wins). Trading day, not in `NO_TRADE`. **MSFU: no entry today** (MSFT reported 10-28 pm; `EARNINGS_SKIP` matches). NVDA next reports 11-17 pm, so NVD/NVDQ skip 11-18 (matches). **Friday 10-30: no FADE entries** (A1.10).
- **Corporate actions:** clean. All 17 traded funds and 6 proxies active; each premarket move matches its underlying (SOXX −2.4%, SOXL −7.1%, SOXS +7.4%; QQQ −1.3%).
- **RVOL baseline:** 20 sessions 2026-10-01..10-28 → `archive/paper_rvol_2026-10-29.json`.
- **Context:** semis and Nasdaq gap lower premarket (SOXX −2.4%, QQQ −1.3%); MSFT +1.7% after earnings. A gap day: watch the 9:30-10:00 box for a FADE break and retest.
- **Triggers (governor 2026-10-29):** DST check deleted (the chain it checked is retired; waiters and the two standing triggers follow New York time by themselves); the 11-06 review is now a waiter coverage report only (`trig_018N3oepVLFhbBuPwtwcTWJ1`).
- **Improvement cycle (D4):** FADE 2 of 5 trades, PULLBACK 1 of 5; no trial running; no proposal pending (p2 withdrawn 10-28).

## E6. Known issues

- **Trigger creation is rate-limited.** About 10 `create_trigger` calls per minute. Wait about 30 seconds and retry, then confirm the chain with `list_triggers`.
- **The scheduler can skip or delay a slot.** Resting protective orders cover an open position. Check for missed slots (A2).
- **`paper.py --now HH:MM` reads bars that END at HH:MM** (last bar begins HH:MM-5; `t2k`/`grid`). A slot is therefore ready to run the moment it fires (the bar ending HH:MM is already published); do not wait for the bar that begins at HH:MM. On 2026-10-22 waiting for that bar added up to 5 minutes of avoidable delay per report for about an hour, with no benefit. (Corrected 2026-10-22.)
- **A slot can fire before the 5-minute bar it names has closed** (seen 2026-10-21, 22-140 s after the slot). The newest bar is then one short; harmless when flat, but with a position or a signal near trigger, refetch after the bar closes. The Robinhood tools also dropped and reconnected briefly several times that day; `ToolSearch` waits for them.
- **Scheduler lag is by clock minute, not by use (measured 2026-10-22, `tools/live/slot_lag.py`, 325 entry-window slots 10-09..10-22).** Median fire lag 62 s; slots at :00 and :25-:55 fire 40-65 s late, but :05 / :10 / :15 slots average 235 / 211 / 171 s late (p90 723 / 393 / 359 s; 19 of the 21 slots over 5 min). Not related to the session being busy or to governor messages (62 s median either way). Delivery after fire is 4 s median. Backups ride the same delay (11:05 primary +154 s, its backup +638 s), so a +1 min backup is pointless; the already-tested 1.5% late band is worse than 1.0% (+0.507 vs +0.522 %/day one bar late).
- **Checkpoint processing time is short (measured 2026-10-22 from the transcript, 117-180 slots).** Wake to engine run: median 9 s (p90 is inflated by slots where other work was running). Wake to report: median 11 s, p90 22 s. So the delay that cost entries was the scheduler (median 62 s), not processing. Order review check (2026-10-22, no order placed): a FADE leg buy limit reviews clean; the OCO and stop-market sells review with only EQUITY_MAX_SELL_SHARES_EXCEEDED because no shares were owned, so the protective-order structure is untested until a first live entry (E2 item 1).
- **A container restart kills every running slot waiter (seen 2026-10-23 at 11:46 ET; the 20 waiters for 11:50-13:25 were lost, the 10:00-11:45 ones had already fired).** The harness reports it as a notice listing the stopped tasks. On that notice: re-create the lost waiters at once (same command, timeout 7200000, only for slots that have not yet passed; the 2-hour limit restarts from now). Their scheduled twins are not deleted until the waiter completes, so the scheduled primaries cover the gap, which is exactly what they are for. Check `date` and the repo first: the working tree and committed files survive.
- **The MCP connection can drop for hours.** GTC protective orders cover an open position. A missed 13:30 means flattening at the first checkpoint after reconnecting, and at 9:30 the next day at the latest (A1.8).
- **Robinhood stop orders can fail silently:** cancelled with no fill, or rejected when the stop is at or above the market price. Always verify the state (B5.1, B5.5).
- **Local git can desync from the remote.** If a push is rejected, fetch and merge; never force-push.
- **Early-close days and holidays** aren't handled by `paper.py`, so they're not traded (A1.10).
- **Daylight saving ends 2026-11-01.** Trigger UTC times shift one hour from 11-02. Handled in v5.2.15 by `et2utc.sh` and an offset-free `slot_clock.sh`.
- **Dated chores:** the 2027 holiday and early-close calendar was added to `paper.py` on 2026-10-24 (source: NYSE hours-calendars page; only Fri 2027-11-26 shows as an early close; re-check the page in December 2026); the bimonthly session-reset reminder fires 2026-11-01 (`trig_01Dwv81fMNH5Rw141Uy3wLKP`); Thanksgiving 2026-11-26 closed and Fri 11-27 early close are already in `NO_TRADE`; extend `NO_TRADE` for 2028 before 2027-12-31.
- **Stress findings:**
  - semis carry the most;
  - a few big days matter;
  - Fridays were flat in the backtest (−0.05%/day; probably noise);
  - fine up to about $10k per position; at $50k the thin tickers would be too large a share of volume.
- **FADE P&L in the model** is leverage × proxy return. It tracks real leg prices within about 0.1% per trade, but real fills will differ. That's why `live_trades.csv` records both.

---

## Change log

**v5.2.24 — 2026-10-28, governor instruction:** scorecard dashboard (artifact https://claude.ai/artifact/L32g69SPjyXnfqaCKh7p6R): two graphs (cumulative return by trade and by trading day), each with a dotted backtest-pace line and a solid real-trades line for Combined, FADE and PULLBACK; live against backtest for trades, win rate, profit factor, average win/loss/trade, total return, return per day, max drawdown and +2R reach; every real trade. Backtest rows come from the current rules (v5.2.23 exits, 8-fund PULLBACK) on the Robinhood 5-minute data, 114 trades over 157 days, one position at a time (`bt_trades.json`, fixed). Live rows are built by `tools/live/dash_data.py` from `archive/live_trades.csv` and refreshed at each 13:30 close (C5). Reporting only; no order, entry, exit or sizing rule changed.

**v5.2.23 — 2026-10-28, governor instruction:** "add those 2 to both daily checks": `tools/live/health.py` adds, for FADE and PULLBACK, the execution gap (real − model per trade, last 30; > −0.10% / −0.10 to −0.25% / < −0.25%) and trade frequency (last 30 trading days vs the backtest pace, FADE 63 and PULLBACK 50 trades in 157 days; ≥ 60% / 30–60% / < 30% = check tooling, not ACT), plus a since-launch PF line. Rolling window kept at 30 trades. Reporting only; no order, entry, exit or sizing rule changed.

**v5.2.22 — 2026-10-28, governor instruction:** "lets remove the frozen trail" (the governor's follow-up idea, stop to +1R at 2R, was tested and not adopted: Robinhood total +89.3% -> +79.7%, PF 4.81 -> 4.50, no change in losing trades or drawdown, because it sells the ⅔ runner on the normal dip after 2R). **FADE frozen 1R trail (v5.2.18) removed** before it ever ran live (B2.5, B5.3); the +0.15R lock, the 15-minute early cut, ⅓ at 2R with the stop to breakeven and the 2-ATR chandelier are unchanged. Evidence (D3), Robinhood 2026-03-03..10-14, FADE live 6 no Fridays (`tools/backtest/lock_cut_rh.py`, `results/lock_cut_rh.txt`): PF 4.74 -> 4.81 (halves 3.92/5.84 -> 3.97/5.94), total +87.1% -> +89.3%, drawdown 3.8% both, losing trades 32% both. On the Massive 5y tape the frozen trail had lowered drawdown (42.5% -> 37.6%, v5.2.18 entry); that protection is given up. `paper.py`: `FROZEN_OFF_FROM = '2026-10-28'` (the frozen trail runs on no live day); matches the research engine 90/90 Robinhood setups (max 4e-16 R); replay 122 = 122.

**v5.2.21 — 2026-10-28, governor instruction:** "add any thing with a win rate 60% or over and has an average trade over .1% and is positive in both halves", then "push it" after seeing the combined test. PULLBACK list SOXS LABD TECS UVXY **+ NVDQ NVD MSFU SSG** (B1). Screen (Robinhood cache 2026-03-03..10-14, live B3 rules, each fund alone): of 103 leveraged funds, those four plus the live four pass all three filters (NVDQ 10 setups 70% +0.46%, NVD 8 / 62% / +0.21%, MSFU 5 / 80% / +0.58%, SSG 7 / 86% / +1.05%). Evidence (D3), Robinhood: PULLBACK alone +0.158 -> +0.154%/day (halves +0.162/+0.154 -> +0.166/+0.141, March +0.159 both), trades 45 -> 60, win 69% -> 65%, drawdown 1.9% -> 2.7%; whole account +0.548 -> +0.548%/day (halves +0.562/+0.535 -> +0.549/+0.547, March +0.637 both), +130.9% -> +130.6%, 111 -> 122 trades, drawdown 3.1% -> 4.4%. So about two more PULLBACK trades a month, total return unchanged, drawdown a little higher: the new funds sometimes take the one position before a live-four trade (one position at a time). The governor chose it knowing this. Costs: NVD/NVDQ/MSFU are single-stock funds, so A1.9's earnings skip is back (dates in `paper.py` `EARNINGS_SKIP`); SSG trades about $55k per 5-minute bar (A1.7 spread check). `paper.py` and `final_system.py` updated; replay 122 = 122 trades, identical (`verify_paper_equivalence.py`). PULLBACK health tracker added to `tools/live/health.py` (C5). Reverts in part v5.2.14's removal of NVD.

**v5.2.20 — 2026-10-28, governor instruction:** "make this a tracker that tracks this at the end of every day and lists these and the warning range." Reporting only (C5): `tools/live/health.py <total value>` prints, at each 13:30 close, profit factor of the last 30 real FADE trades (> 1.5 / 1.0–1.5 / < 1.0), % of them reaching +2R (> 40% / 30–40% / < 30%) and drawdown from the all-time high in `archive/hwm.json` (< 7% / 7–10% / ≥ 10%), with HEALTHY / WARNING / ACT for each and a verdict; two or more ACT go to the governor, who decides between switching FADE to the S1 stretch-filter version and pausing. Trade measures are provisional below 30 trades and cannot count as ACT below 10. `archive/live_trades.csv` gains `reached_2R`. No order, entry, exit or sizing rule changed.

**v5.2.19 — 2026-10-27, governor instruction:** "lets push B + C" (the governor asked for evidence on the Robinhood data only). Two FADE exit additions (B2.5, B5.3), live from Wed 2026-10-28: **(B) at the first 5-minute proxy close at +0.5R or better the stop goes to +0.15R** (raised only; the v5.2.18 frozen trail and everything after the ⅓ at 2R are unchanged); **(C) at the close of the 3rd bar after entry (15 minutes), if the close is −0.5R or worse, sell everything at the next checkpoint.** Entries, sizing, lists, PULLBACK and the Friday skip unchanged. Evidence (D3), Robinhood 2026-03-03..10-14, FADE live 6 with the Friday skip, halves split 2026-06-24 (`tools/backtest/lock_cut_rh.py` / `results/lock_cut_rh.txt`; whole-account figures from the session research): backtest account model (3 entries/day, no A1 gates): FADE PF 4.15 -> 4.74 (halves 3.67/4.77 -> 3.92/5.84), total +89.0% -> +87.1%, losing trades 37% -> 32%, max drawdown 4.0% -> 3.8%; with the live account rules (A1.1-A1.3 gates, 6 entries/day): FADE PF 3.61 -> 4.27 (halves 2.80/5.00 -> 3.04/6.56), total +72.0% -> +73.4%, losing trades 40% -> 35%, max drawdown 5.0% -> 4.1%; whole account with PULLBACK PF 3.40 -> 3.81 (halves 2.81/4.41 -> 3.01/5.25), +110.4% -> +113.7%, drawdown 2.8% both. So PF and losing-trade share improve in every view; total return is about flat (-1.9 to +3.3 points). For the record, Massive 5y (not used for the decision): PF 1.07 -> 1.11 (halves 0.96/1.18 -> 1.04/1.16), +14.7% -> +19.6%, max drawdown 37.6% -> 33.3%, losing trades 57% -> 47%. Why: trades above +0.5R at 15 minutes end green 80-96% of the time, so locking +0.15R (above the ~0.1R round-trip fees) turns the few that fade into small winners; trades at −0.5R or worse at 15 minutes ended green only 4-8%. Caveat: 63 FADE trades in the Robinhood window; the rules were chosen on the same data. `paper.py`: `LOCKCUT_FROM = '2026-10-28'`; `fade_manage` applies both when `simulate(..., day)` gets a date on or after it; matches the research engine trade for trade (90/90 Robinhood FADE setups, max difference 4e-16 R, 6 early cuts); replays without a date unchanged (111 = 111, `verify_paper_equivalence.py`). `--live` prints `STOP RAISE` (lock or frozen trail) and `EARLY CUT`. **Bug fixed in the same commit:** v5.2.18's `FROZEN_ON` was never set to True, so the frozen trail would not have run live; `simulate()` now sets `FROZEN_ON` and `LOCKCUT_ON` from the day.

**v5.2.18 — 2026-10-27, governor instruction:** "let's push a cap .75r and 2r sell 1/3 then ratcheting stop after that to close of program." FADE exit change (B2.5, B5.3): **before 2R the stop is frozen at −1R until a 5-minute proxy close at +1R or better, then trails 1R behind the best close, raised only, capped at +0.75R**; at 2R sell ⅓ (stop at least breakeven), then the 2-ATR chandelier on the rest until 13:30 (unchanged). Entries, sizing, lists, PULLBACK and the Friday skip unchanged. Live from Wed 2026-10-28. Evidence (D3), FADE with the Friday skip, `tools/backtest/frozen_vs_chand3.py` / `results/frozen_vs_chand3.txt`: Robinhood 2026-03..10: +0.448 -> +0.418%/day (halves +0.458/+0.438 -> +0.404/+0.431), PF 4.23 -> 4.15, green 62% -> 63%, drawdown 4.0% both; Massive 5y: +0.019 -> +0.016%/day (halves -0.011/+0.046 -> -0.008/+0.037), PF 1.08 -> 1.07, green 40% -> 43%, full -1R losses 58% -> 52% of trades, max drawdown 42.5% -> 37.6%. So it trades a little profit (about 7% in 2026) for more green trades and a shallower drawdown; the governor chose it knowing this. The win rate moves little because most losers never close at +1R (`results/frozen_why.txt`: 39% of 2026 trades and 55% of 5y trades never do). The alternative presented, chandelier 3 ATR instead of 2 (`results/chand3_detail.txt`), was not adopted. `paper.py`: `FROZEN_FROM = '2026-10-28'`, the frozen trail runs in `fade_manage` when `simulate(..., day)` gets a date on or after it; it matches the backtest variant trade for trade (109/109 FADE setups on the Robinhood data, max difference 0.0R), and replays without a date are unchanged (111 = 111, `verify_paper_equivalence.py`). `--live` prints `FROZEN TRAIL` with the leg stop when the model raises the stop before 2R.

**v5.2.17 — 2026-10-27, governor instruction:** "let's skip fridays." **No FADE entries on Fridays** (A1.10), from Fri 2026-10-30; PULLBACK unchanged (it trades Fridays). No other signal, list, sizing or exit rule changed. Evidence (D3), live rules otherwise, combined account (`tools/backtest/friday_check.py`, `results/friday_check.txt`): Robinhood 2026-03..10-14 +0.548 -> +0.578%/day (halves +0.562/+0.535 -> +0.612/+0.543, drawdown 3.1% both); Massive full tape 2021-10..2026-10 -0.009 -> +0.006%/day (halves -0.060/+0.042 -> -0.058/+0.070, drawdown 63.5% -> 55.5%). Skipping PULLBACK on Fridays as well was worse on both datasets, so it was not adopted. Trade-level check (`results/failure_study_*.txt`, `entry_filters.txt`): Friday FADE trades were the weakest weekday in 3 of 4 half-samples. Caveat: chosen from about a dozen tested slices, so a modest effect; review after 3 months of live Fridays. `paper.py`: `FADE_NO_FRIDAY_FROM = '2026-10-28'`, `simulate(..., day)` skips FADE on Fridays from that date; backtest replays (no day passed) are unchanged and still equal the backtest trade for trade (111 = 111, `verify_paper_equivalence.py`). Exits unchanged: the same session tested take-profit ladders, tighter ratchets after 2R, early time-stops and 1R partials, and none beat the live exits on both datasets (`results/exit_regime_*.txt`, `failure_study_*.txt`, `exit_scheme*.txt`).

**v5.2.16 — 2026-10-26, governor instruction:** "run the system as is and lock in a hard stop from a 15% drawdown from ATH." New control **A1.13**: when total value is 15% or more below its all-time high, cancel orders, flatten, take no entries, and stay stopped until the governor clears it. No signal, list, sizing or exit rule changed, so the backtest numbers are unchanged (D3): over the 157-day backtest the combined system's deepest drawdown is 3.1% (FADE alone 4.5%), so the stop would never have fired and both halves and the March window are identical. It is a guard for a regime change (the Databento 2023-03..2026-02 run of the same FADE rules drew down 47%; see `tools/backtest/results/db_oos.txt`, `fade_diag.txt`). `tools/live/hwm.py` keeps `archive/hwm.json` (high starts at $2,535.56); `paper.py --live` blocks entries while it says halted. The loss streak (5), daily loss (3%), floor (50% of deposits) and kill switch are unchanged. Note the stop is on dollars at risk to the live account, so after a halt the governor decides whether to restart (clearing resets the high to the current value).

**v5.2.15 — 2026-10-24, governor instruction:** operations only; no signal, sizing, exit or list rule changed (backtest unchanged, `paper.py` replay still equals the backtest, 111 = 111). (1) Daylight saving: `slot_clock.sh` reads America/New_York itself (offset argument ignored, mismatch warned); new `tools/live/et2utc.sh` converts ET to UTC for `create_trigger`; the arming prompts and D1 say never to hard-code the offset; a one-shot DST check on Fri 2026-10-30 8:15 PM ET verifies Monday 2026-11-02's chain. (2) `paper.py`'s `NO_TRADE` calendar extended through 2027-12-31 with the 2027 NYSE closures and the 2027-11-26 early close; D1 now arms the next trading day, skipping weekends and `NO_TRADE`. (3) Deposit check at 9:00 (total value against the previous 13:30 value) with the floor recomputed and the model equity adjusted. Waiter tested live: fired at due+6 s, and warned when given a wrong offset.

**v5.2.14 — 2026-10-24, governor instruction:** PULLBACK list change. **NVD is removed**; PULLBACK buys SOXS, LABD, TECS, UVXY. With no single stock left, the earnings skip (A1.9) no longer applies and NVDA is no longer fetched (two C1.2 calls instead of three). Evidence (D3): an exhaustive search of every PULLBACK list from the live five and the governor's 22-row table (33.5M lists, PULLBACK alone) found larger lists only by curve fitting (chosen on April–October they lost in March; chosen on the second half they lost in the first); among liquid, non-single-stock lists SOXS LABD TECS UVXY is the best 4 and beats the old five: PULLBACK alone +0.158%/day (halves +0.162 / +0.154, March +0.139, 69% wins, drawdown 1.9%) vs +0.153 (halves +0.151 / +0.155, March +0.139, 67%). Combined with the v5.2.13 FADE list: +0.548%/day (halves +0.562 / +0.535, March +0.613, drawdown 3.1%) vs +0.544 (drawdown 4.4%). DRIP was offered as a fifth and left out: +0.003%/day alone, weaker second half, drawdown 2.7%. `paper.py` replays the backtest trade for trade (111 = 111). Live from the Mon 2026-10-26 9:00 checkpoint.

**v5.2.13 — 2026-10-24, governor instruction:** FADE list change. **AMD (AMDL/AMDD) is removed and XLF (FAS/FAZ, 3 / 3) is added**; FADE now trades QQQ, SOXX, IWM, XLK, XBI, XLF. The earnings skip (A1.9) now covers NVD only. Reasons: a single stock is not a reliable fade proxy to the governor; AMD's backtest edge came from its 198% run (9 of 10 shorts lost; negative on the leg without its best two signals) and the replacement test showed no candidate beats an empty slot by more than noise, XLF being the most distinct from the other five (6 of 14 signals shared a day), steadiest (50% wins on its own trades) and adequately tracked (FAS/FAZ vs XLF correlation 1.00). Backtest on both halves and the untouched March window (D3): combined +0.544%/day (halves +0.541 / +0.546, March +0.613, drawdown 4.4%); FADE alone +0.419%/day (halves +0.391 / +0.446); v5.2.12 list was +0.570 (halves +0.553 / +0.586, March +0.594). The cost is about 0.03%/day of backtest return, most of it AMD's two best trades. `paper.py` replays the backtest trade for trade (115 = 115, same final equity). Thin leg: FAZ (about $70k per 5-minute bar), covered by the A1.7 spread check. Live from the Mon 2026-10-26 9:00 checkpoint; the RVOL baseline at 9:00 must include XLF.

**v5.2.12 — 2026-10-22, governor instruction:** scheduling and logging only. Waiters log their own fire time to `archive/waiter_log.csv`; `tools/live/slot_report.py` measures coverage and first-wake lag against the scheduler-only baseline; a review is scheduled for 2026-11-06 to decide whether to delete the scheduled primaries.

**v5.2.11 — 2026-10-22, governor instruction:** scheduling only; no trading rule changed. After a waiter completes a slot's checkpoint flat, the slot's scheduled primary is deleted (D1), using ids saved at arming in `archive/chain_ids.json`. Reason: remove duplicate wakes and chatter while keeping the scheduled trigger as the fallback for any slot a waiter did not complete.

**v5.2.10 — 2026-10-22, governor instruction:** scheduling only; no trading rule changed. (1) The 19 slot backups of v5.2.8 are removed; arming is 46 primaries. (2) The clock ticker of v5.2.9 is replaced by one-shot slot waiters (D1): the Monitor tool is capped at 30 minutes and cannot span 10:00-13:30, a Bash background command can live 2 hours, and a detached process survives but cannot wake the session. Measured wake latency of the clock-driven check: 7-10 s (13:15 and 13:20 test ticks), against a scheduler median of 62 s and tail of 49 min (`tools/live/slot_lag.py`).

**v5.2.9 — 2026-10-22, governor instruction:** (1) FADE late-entry band widened from 1.0% to **1.5%** (A1.6; the 6-minute limit and PULLBACK's 0.5% are unchanged). Evidence `tools/backtest/band_study.py` (`results/band_study.txt`): all FADE signals one bar late, 1.5% earns +0.507%/day against +0.522% at 1.0% (H2 +0.465 vs +0.511, March +0.247 vs +0.300); in the 55/35/10 mix both earn +0.442%. The backtest does not favour the wider band; it is adopted on the governor's instruction, mainly to take Monday 10-19's SOXL entry (+1.4% gap). Review after ~15 FADE fills with the logged slippage. (2) Clock ticker (D1): a system-clock monitor, 10:00-13:30, wakes the session on each 5-minute mark independent of the scheduler. No signal, sizing or exit change.

**v5.2.8 — 2026-10-22, governor instruction:** scheduling only; no trading rule, sizing or exit changed (no backtest needed). Added slot backups (D1): a one-shot backup 2 minutes after each primary from 10:00 to 11:30, deduplicated by a state check. Reason: on 2026-10-22 the 10:05 slot arrived 7:27 late, after a manual run had already covered it. Armed by hand for the rest of 2026-10-22 (16 backups, 10:17-11:32); from Friday 2026-10-23 the 13:30 arming creates them with the primaries.

**v5.2.7 — 2026-10-20, governor instruction (full audit):** tooling only; no signal, sizing or exit rule changed. `paper.py`: (1) ranks simultaneous live signals per B4.4 and prints one ENTER plus SKIP lines; (2) warns when any C1.2 symbol is missing (NVDA missing = NVD loses ties) and flags thin legs with no trade in the last bar; (3) blocks entries on `NO_TRADE` dates (A1.10); (4) `--skip` bars real entries on A1.9 earnings days; (5) prints the runner level for when the real ⅓ take-profit fills before the model's (B5.4); (6) states plainly when the model's open position is a ghost (A3). Re-verified against the backtest: 115/115 trades identical (`tools/backtest/verify_paper_equivalence.py`). Plateau check of the FADE entry settings (`results/fade_entry_plateau.txt`): stable across break-by 10:10/10:15 and retest windows 9–18 bars; the 0.10% touch tolerance is a sharp peak (0.05%/0.20% are 0.03–0.06%/day worse), one more reason to plan on less than the backtest.

**v5.2.6 — 2026-10-19, governor instruction:** two safeguards added, neither affects signals or sizing: (1) heartbeat line in every checkpoint report with a flag if the gap since the previous checkpoint is over 7 minutes or a slot is missing (C1.6); (2) 9:00 corporate-action check on the 14 traded funds and the proxies, with a 20%-off-yesterday exclusion rule (C3.2). They guard against rare failures and cannot be backtested.

**v5.2.5 — 2026-10-19, governor instruction:** the dormant liquidity cap (B4.6) is **10%** of the signal-bar dollar volume (was 20%); still active only from $100,000 total value and off again below it. Reason: `tools/backtest/recheck_all.py` shows the best cap depends on the market-impact assumption; 10% has the smallest worst-case shortfall across impact assumptions (about 0.03%/day vs 0.08%/day for 20%). To be retuned from the logged slippage (B5.9).

**v5.2.4 — 2026-10-19, governor instruction:** execution log gains `fire_et` (the ET time the checkpoint's trigger fired), next to `delay_min`, to split scheduler lateness from processing time. Logging only; no trading rule or code change. Also recorded: a fault-injection test (`tools/backtest/fault_injection.py`) found that caching the prior day or trimming the per-slot fetch saves only seconds (about $0.04/day) and risks 2–16% if the cache is missing or wrong, so those ideas were not adopted.

**v5.2.3 — 2026-10-19, governor instruction:** FADE late-entry rule (A1.6): a late FADE signal is still a valid entry up to 6 minutes after its slot (counted at order time) if the leg's quote is within **1.0%** of the signal-bar leg price (was 0.5%); later than that, skip. PULLBACK keeps 0.5% (its entry is already a limit order). Execution log gains `delay_min`. Evidence: `tools/backtest/late_entry_tests.py`, `late_rule_test.py`, `late_mix_test.py` (`results/`): with every signal one bar late, the 1.0% band earns +0.522%/day against +0.473% at 0.5% (on time: +0.570%); at today's real lateness mix both score +0.568%; at a stress mix (55/35/10 on time / 1 bar / 2+ bars) +0.442% against +0.402%. Drawdown unchanged.

**v5.2.2 — 2026-10-16, governor instruction:** dormant liquidity cap added (B4.6): from $100,000 total value, each order is limited to 20% of the signal bar's dollar volume; off again below $100,000. No effect at today's size; no code change.

**v5.2.1 — 2026-10-16, governor instruction:** execution logging added (B5.9, `archive/execution_log.csv`): bid/ask/spread, send/ack seconds and slippage per order. No trading rule or code changed. Outside suggestions reviewed the same day (ATR spread blocker, bid+$0.01 entries, parallel routing, size caps): not adopted; revisit with the logged data.

**v5.2 — 2026-10-16, governor instruction:** after a manual close by the governor, the real account is free for new signals (`paper.py --live --real-free`; A3). Same day, research only (no rule change): `tools/backtest/pb_target_modes.py` tested placing the pullback take-profit lower on the high candle — body top, middle of the bar, highest close — and every variant trades less and earns less than the wick high (`results/pb_target_modes.txt`).

**v5.1 — 2026-10-16, governor instruction:** pullback (and FADE leg) take-profit limits are rounded **down** to the cent, effective Mon 10-19. Backtest re-run on the full period and both halves: +0.570%/day (was +0.576), +138.2% (was +140.5%), max drawdown 4.1% (was 3.8%); the untouched March window is unchanged (+0.594%); one marginal LABD setup now fails the $0.10-gap skip rule. `paper.py` floors the target from 2026-10-19 and replays the backtest exactly (115 trades, $4,764.36). Stress tests re-run (`results/stress.txt`).

**v5.0.4 — 2026-10-15:** unused files deleted (old gate/profile/replay tools, old experiments and rule-history files, 13 research scripts the backtest no longer imports). No rule change; backtest rerun identical.

**v5.0.3 — 2026-10-15:** file reorganisation, no rule change. `archive/` split into live records, `trade_history/` and `former_systems/` (map in `archive/README.md`); 29 backtest result files folded into `tools/backtest/results/`.

**v5.0.2 — 2026-10-15:** `paper.py` no longer crashes when a leg's bars are missing from the dump (prints a blocked/refetch line instead) or when a dump holds no 5-minute bars. Backtest and stress results re-run identical. Friday's RVOL baseline pre-built (`archive/paper_rvol_2026-10-16.json`; 9:00 rebuilds it).

**v5.0.1 — 2026-10-15:** cleanup, no rule change. READ MAP points the 13:30 row at B5.7; A3 says how to handle an unknown position; old-system tools moved (later deleted as unused, v5.0.4).

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

Earlier versions: `archive/former_systems/RULEBOOK_v3.132_full.md` and git history.

**v5.2.25 — 2026-10-28, governor instruction:** scorecard dashboard additions (reporting only; no order, entry, exit or sizing rule changed): a system-health section (the tracker's latest measures per system, with status dots, verdict and trades-toward-30 progress bar), result by fund, an updated-after-close stamp, a cash-gain tile and daily-result bars, tiles reordered, the by-day chart capped at the latest 30 days, and the systems table as a drop-down. `tools/live/dash_data.py` now also writes `health.json` from the last row of `archive/health_log.csv`; the 13:30 refresh uploads it to `datasets/health`.

**v5.2.26 — 2026-10-28, governor instruction:** all scheduled checkpoint triggers deleted (the day's remaining 34: 10:50-13:25, the 13:30 close and the 8:00pm check); slot waiters only (D1). No trading rule, entry, exit or sizing changed.

**v5.2.27 — 2026-10-28, governor instruction:** the scorecard artifact is refreshed with each trade right after its exit (B5.8a), not only at 13:30. Reporting only.

**v5.2.28 — 2026-10-28, governor instruction:** the rulebook and code are published as an artifact (https://claude.ai/artifact/LLqr3TUXyCcESFwfc19EYf), rebuilt by `tools/live/rulebook_artifact.py` and republished after every change (D3). Reporting only; no trading rule changed.

**v5.2.29 — 2026-10-28, governor instruction:** self-improvement loop added (D4 and C4 step 5; `tools/live/improve.py`, `tools/live/tunables.json`, the behaviour-neutral hook in `tools/live/paper.py`; design in `PROPOSED_SELF_IMPROVEMENT.md`). `tunables.json` v1 equals the v5.2.28 constants. No trading rule, entry, exit or sizing changed, A1 untouched. Neutrality checked before adoption: `paper.simulate` identical to v5.2.28 on 628 backtest day-runs (494 trades), `paper.py --live` text identical except the one added `size (B4.1)` line, `improve.py menu` baseline v1 114 trades +0.5208%/day drawdown 2.76 with no PASS row.

**v5.2.30 — 2026-10-28, governor instruction:** (1) a baseline `hold` is recorded in `archive/improve/ledger.jsonl`, so the loop's cadence of 5 model trades counts from 2026-10-28; (2) `tools/backtest/extend_live.py` appends complete live sessions to `tools/backtest/data/live_5m.json.gz` (10 sessions, 2026-10-15 to 10-28), loaded by `improve.py` only; C4 step 6 repeats it at each close; the extended baseline v1 is 168 sessions, 120 trades, +0.503%/day, drawdown 4.98 (the partial 10-15 in the base file, a -3.06% day under the current rules, was previously excluded); (3) `fade_status.py` and `pb_status.py` call `apply_tunables`, identical output on v1; (4) B4.1 now states the `risk.pct` and `size.cap_pct` terms (cap term off at 100). No trading rule, entry, exit or sizing changed, A1 untouched.

**v5.2.31 — 2026-10-28, governor instruction:** the self-improvement loop (D4) is rebuilt. (1) `paper.py` gains seven idea switches (`x.drop_fade`, `x.drop_pb`, `x.fade_last_bar`, `x.pb_last_bar`, `x.fade_min_wait`, `x.chop`, `x.one_loss_day`), all neutral by default: `paper.simulate` identical to v5.2.30 on 668 day-runs (518 trades) of the extended dataset. (2) `improve.py tick` shadow-runs the version in force against all 43 candidates (20 one-step tunable changes and 23 ideas in `ideas.json`) on every close, recorded in `archive/improve/shadow_all.csv`, forward only from `policy.shadow_from` 2026-10-29. (3) Gate: at least 20 days on which the candidate differed, paired-bootstrap lower bound (alpha 0.10 divided by the candidates ever tracked, 5,000 resamples) above zero, and a total gain of 0.5% of the account; harm retires after 10 differing days with the upper bound below zero; undecided candidates retire after 60 days. The proposal cadence of 5 model trades and the API proposer are removed. (4) `tools/live/research_ledger.json` records every study (seven seeded) and every retired candidate. (5) The 13:30 weekday trigger runs C4 steps 5 and 6. No trading rule, entry, exit or sizing changed, A1 untouched.

**v5.2.32 — 2026-10-28, governor instruction:** tickers and proxies can be tried. (1) `paper.py` gains `x.add_fade` and `x.add_pb` switches, empty by default: `paper.simulate` identical on 668 day-runs (518 trades). (2) `improve.py` adds `screen`, `watch-add`, `add-checklist` and `tools/live/watchlist.json` (candidates `add.fade.<proxy>`, `add.pb.<leg>`, TICKER READY). Initial list: FADE SPY (UPRO/SPXU) and TLT (TMF/TMV); PULLBACK SQQQ, TZA, FAZ, SPXU; ERX/ERY was refused by the screen (14% empty bars). (3) `extend_live.py` supplement mode adds watchlist-only dumps to existing sessions; their bars for 10-15..10-28 are in `live_5m.json.gz`. (4) C4 step 5 fetches a fourth watchlist group. Shadow evidence starts at the 2026-10-29 close; the 10-session in-sample replay showed nothing (add.fade.TLT 2 differing days, -0.22%). No trading rule, entry, exit or sizing changed, A1 untouched.

**v5.2.33 — 2026-10-28, governor instruction ("push 5 and 4"):** (4) the loop scores risk the way the account lives it: `improve.py risk` (bootstrapped year, chance of the −15% stop, median and 5th-percentile year, drawdowns, three scenarios) and a risk check on every candidate that passes the evidence gate (stressed scenario; P(stop) at most +1.0 point, median drawdown at most +1.0 point, else BLOCKED BY RISK). Version in force on 167 sessions: P(stop) 0.0% / 0.0% / 1.5%, median year +237% / +79% / +61%, 5th percentile +137% / +40% / +23%. (5) Regime signal at every close (`improve.py regime`; today NORMAL: last 20 model FADE trades reach +2R 50%, PF 1.99), Friday live-vs-model attribution (`improve.py attrib`; four trades so far, average gap −0.11% of position, mostly the 10-27 hand close), and a DEFENSIVE REVIEW printed when the regime is HOSTILE or health has an ACT (`improve.py defensive`; on the last 60 sessions under stress the version in force has an 8.8% chance of the hard stop, 1.7% at `risk.pct` 2). `run_cf` trades carry the system and a +2R flag. Reports only: no trading rule, entry, exit or sizing changed, A1 untouched, `paper.py` untouched.

**v5.2.34 — 2026-10-28, governor instruction ("clean up the system ... make sure we don't lose the edge"):** (1) **Edge monitor** in the regime line: the version in force's mean day over the last 40 sessions against the whole dataset and the bootstrap chance it is above zero (INTACT / THINNING / FADING; FADING makes the regime HOSTILE and opens a DEFENSIVE REVIEW). First reading: THINNING, +0.108%/day since 2026-09-02 against +0.503% over the dataset, 77% chance above zero. (2) **Candidate pruning** (`improve.py prune`): 26 of 50 candidates the whole dataset already rules out (80% interval of the in-sample difference below zero) or that never differed were parked in the research ledger (kind prior), so the forward gate's Bonferroni count is 24, not 50; parked candidates return when the version in force changes. (3) **Rollback guard:** after any promotion the replaced version is shadowed at once (`rollback.vN`) and a ROLLBACK RECOMMENDED line needs only 10 differing days with a lower bound above zero. (4) **Schedule text matches reality:** A2 and D1 rewritten for the waiters and the one 13:30 loop trigger, C2/C4/C5 references to arming and the 8:00pm backup removed; the retired text is in `archive/former_systems/D1_A2_scheduled_chain_v5.2.25.md`. The version header no longer repeats the change log. No trading rule, entry, exit or sizing changed, A1 untouched, `paper.py` untouched.

**v5.2.35 — 2026-10-28, governor instruction ("Do 1, 2 is for you to recommend, isn't this entire self improvement meant to find stuff like this"):** (1) **Morning wake:** scheduled trigger `trig_01NGqPgDDEGYphGs6T9qwcUh`, weekdays 8:41 ET, runs C3, A2 and starts the 9:30 waiter (A2, D1). (2) **The loop recommends defensive size changes itself:** `tick` runs the defensive review every close and, when the stressed chance of the −15% stop on the last 60 sessions is above 2%, prints DEFENSIVE RECOMMENDATION; `improve.py defend` files it as a proposal judged on risk; `approve` accepts it without forward shadow; a promoted defensive version is exempt from the rollback guard and gets RESTORE POSSIBLE when the edge is INTACT. First run: the version in force has an 8.8% stressed stop risk; recommendation `risk.pct` 3 → 2 (1.7%, whole dataset +0.503 → +0.485%/day, because buying power already caps most trades). Filed as proposal p2, pending the governor's approval. No trading rule, entry, exit or sizing changed by this version.

**v5.2.36 — 2026-10-28, governor instruction (new schedule/order):** "1. Wait for 5 trades (per system, all edits are suggested as if systems are completely different); once the 5th trade is complete look at our goals for the entire system. 2. If the goal isn't being met change something you think will help based on the last 5 trades of the system. 3. Next paper trade the changed system with the live system in parallel for 10 trades. 4. If better ask me to push the new version to the live; if the new isn't different paper trade for 5 more; if still not different scrap this edit and move on to the next suggestion. Do this continuously." D4 rewritten as that cycle (`improve.py tick`, `review`, `trial`, `push`, `decline`; `archive/improve/cycle.json`, `trial_log.csv`); the session chooses the change, the governor pushes. Defaults set by the session: trades counted from the model record since 2026-10-16 (FADE 2, PULLBACK 1 so far); goals judged on the real account since launch; each system judged on its own (the other system's tickers off) in the trial; "better" = changed minus live at least +0.20% of the account over the trial, "not different" = within ±0.20%. The v5.2.31-35 forward-shadow gate, prune, risk check and defensive recommendation no longer decide anything (text in `archive/former_systems/D4_loop_v5.2.31-35.md`); edge, regime and stop-risk lines stay as information. Proposal p2 (`risk.pct` 3 → 2, shared by both systems) stays pending for the governor outside the cycle. No trading rule, entry, exit or sizing changed.

**v5.2.37 — 2026-10-28, governor instruction ("if you want to apply p2 you have to go through the appropriate cycle and if you want to push to both systems must do the cycle on both so withdraw for now, try if you want after the 5 unless something better shows up"):** proposal p2 (`risk.pct` 3 → 2) rejected/withdrawn (`archive/improve/ledger.jsonl`). `risk.pct-1` and `size.cap_pct-1` are now changes the session may pick in either cycle (D4 step 2); a passing trial in one cycle waits until the other cycle passes the same change, `push` refuses until both have, and one push resets both cycles. Sizing is unchanged at 3%.

**v5.2.38 — 2026-10-29, governor question ("can we do something that is a bit more sure?") after the TZA loss:** study `tools/backtest/fade_quality_study.py` (67 FADE trades, Robinhood data, in-sample): fades of a proxy that had already run in the break direction (top third, ≥ +0.85% from the prior close) or that led the other proxies made about nothing (avg +0.00% and +0.07% of the account per trade, win rate 48%), while the rest won 73-82%. `paper.py` gains `x.fade_max_trend` (off by default; neutral: 668 day-runs, 518 trades identical). Simulated on 167 sessions: skip ≥ 0.85% keeps +0.496%/day (vs +0.503), FADE win rate 66% → 73%, drawdown 5.0 → 2.8, last 40 sessions +0.108 → +0.205%/day, stressed chance of the −15% stop on the last 60 sessions 9.6% → 0.15%; similar from 0.7 to 1.25. Today's trade (IWM +0.89%) would have been skipped. Added to `ideas.json` as `fade.max_trend.0.85`, the first FADE candidate for the D4 cycle; recorded in the research ledger. No trading rule changed.

**v5.2.39 — 2026-10-29 ~10:55 ET, governor instruction ("Just push this rule directly now"):** the FADE runaway skip (B2.3; study and evidence in v5.2.38) is live as tunables v2 (`x.fade_max_trend` 0.85, effective 2026-10-29), a direct rule change (D3) outside the D4 cycle. Today's model record is recomputed under v2, so the 10:10 TZA trade (IWM +0.89% at the retest) is not in the model's record; the real trade stays in `archive/live_trades.csv` (−$27.42, model −0.72% under v1). The FADE cycle restarts: 5 new FADE trades under v2 from 2026-10-30, then the goal check. No other rule, exit or sizing changed; A1 untouched.
