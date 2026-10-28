# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin**, `agentic_allowed=true`, trade approvals off.
**Policy version: 5.2.25** (2026-10-28; scorecard dashboard refreshed at each 13:30 close, C5, no trading rule changed; v5.2.23 same day: health tracker adds execution gap and trade frequency for both systems, C5, no trading rule changed; v5.2.22 same day: FADE frozen trail removed, B2.5/B5.3; v5.2.21 same day: PULLBACK list + NVDQ NVD MSFU SSG with the A1.9 earnings skip back, PULLBACK health tracker, B1/A1.9/C1.2/C5; v5.2.20 same day: FADE health tracker in the 13:30 report, no trading rule changed; v5.2.19 2026-10-27: FADE +0.15R lock at the first +0.5R close and early cut 15 min after entry at -0.5R, B2.5/B5.3; v5.2.18 2026-10-27: FADE frozen 1R trail before 2R, capped at +0.75R, B2.5/B5.3; v5.2.17 same day: no FADE entries on Fridays, A1.10; v5.2.16 2026-10-26: A1.13 hard drawdown stop at -15% from the all-time high, nothing else changed; v5.2.15 2026-10-24: DST-proof tooling, 2027 calendar, deposit check, no trading rule changed; v5.2.14 NVD removed from PULLBACK; v5.2.13 AMD fade row replaced by XLF; the take-profit rounding in B3.9/B5 from 2026-10-16; the take-profit rounding in B3.9/B5 applies from Mon 2026-10-19). Bump on every rule or threshold change and record it in the commit.
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
| 6 | **Fresh data** | `paper.py` must show bars through this slot (or say why not). **PULLBACK:** the order review's quote must agree with the last bar within 0.5%. **FADE (v5.2.3, band widened v5.2.9):** the leg's quote must be within **1.5%** of the leg price at the signal bar (two-sided), and the order must be sent **no later than 6 minutes after the slot** (counted when the order is sent). A late FADE signal inside both limits is a valid entry: marketable limit (B5.1), stop and target re-set from the actual fill with the same R (B5.2), normal sizing. Later than 6 minutes, or outside 1.5% → no entry, logged as skipped. Stale or contradictory data → no entry. | paper.py output, `review_equity_order` |
| 7 | **Spread** | Skip the entry if the leg's bid–ask spread is wider than **0.30% of its price**. | Order review quote |
| 8 | **Overnight** | **Nothing is held overnight.** A position found at 9:00 or 9:30 is sold at the 9:30 checkpoint (marketable limit) and reported. | Positions |
| 9 | **Earnings** | **Single-stock funds (v5.2.21: NVD and NVDQ = Nvidia, MSFU = Microsoft): no real entry on any session where the company reported since the prior close** (a pm report bars the next session). `paper.py` applies it from its `EARNINGS_SKIP` dates (MSFU 2026-10-29, NVD/NVDQ 2026-11-18, MSFU 2027-01-28, NVD/NVDQ 2027-02-25; prints `EARNINGS SKIP`); the model is unchanged. | `get_earnings_results` for MSFT and NVDA at 9:00 (C3): if a date moved, pass `--skip` and update `EARNINGS_SKIP` |
| 10 | **Session** | Entries only between 10:00 and 12:55. No trading on early-close days (Nov 27, Dec 24) or market holidays. **No FADE entries on Fridays (v5.2.17, from Fri 2026-10-30); PULLBACK still trades Fridays.** | Calendar; `paper.py` blocks entries on the dates in its `NO_TRADE` list (through 2027-12-31) and blocks FADE on Fridays (prints `FRIDAY: no FADE entries today`) |
| 11 | **Halt** | Never send an order into a halted ticker (A4). | Broker response |
| 12 | **Kill switch** | **If the governor says "stop", "halt" or "flatten":** cancel every open order, sell every position (marketable limit), and take no entries until the governor says to resume. This overrides everything else in this file. | — |
| 13 | **Drawdown stop (v5.2.16)** | **If total value is 15% or more below its all-time high → HARD STOP: cancel every open order, sell any position (marketable limit), take no entries, and stay stopped until the governor clears it** (`hwm.py clear`). The all-time high is the highest total value ever recorded at a checkpoint, kept in `archive/hwm.json` (starts at $2,535.56, the 2026-10-24 close). Deposits and withdrawals move the high by the same dollars (`hwm.py deposit`), so they never count as a drawdown or a new high. Measured at every state check on the live total value, including the mark of an open position, so it can fire mid-day. The system is otherwise unchanged. | `python3 tools/live/hwm.py check <total value>` at **every** state check (exit 2 = stopped). `paper.py --live` also blocks entries while `hwm.json` says halted |

**Losing-streak clearances:** none yet. The live record starts 2026-10-16. Old-system trades in `archive/trade_history/old_system_trades.csv` don't count.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`.**
2. Exactly one trigger per slot. Delete duplicates before arming.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 13:30 close or the 8:00pm backup** (D1).
5. A past-due trigger that is still enabled is a **missed** checkpoint. Do its work now, say it was missed, then delete it.

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
- **Early shutdown:** delete the remaining slots before 13:30, keeping 13:30 and 8:00pm, once any of these is true:
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

## D1. The grid and arming (ET)

`9:00 · 9:30 · 10:00 · 10:05 · … every 5 minutes … · 13:25 · 13:30 · 8:00pm` — 46 slots per trading day.

- **Primary arming at the 13:30 close.**
  - Friday arms Monday. Skip market holidays.
  - Create in batches; the trigger API allows about 10 creations per minute. Then confirm all 46 with `list_triggers`.
- **Slot backups: removed (v5.2.10, governor instruction 2026-10-22).** The 19 backups (v5.2.8) could not cover a scheduler delay: they were delayed with their primaries (11:05 primary +154 s, its backup +638 s). The slot waiters below replace them. Arming a trading day is the 46 primaries only; confirm all 46 with `list_triggers`. The scheduled primaries stay as the fallback and are the duplicates when a waiter has already run the slot.
- **Slot waiters (v5.2.10, governor instruction 2026-10-22; replaces the v5.2.9 monitor).** The scheduler fires late (E6), and a Monitor dies after 30 minutes, so the entry window is covered by one-shot waiters. `tools/live/slot_clock.sh HH:MM` (v5.2.15: no offset argument; it reads America/New_York from the system tz database, so the daylight-saving change needs nothing) sleeps on the system clock until HH:MM:06 ET and exits, which wakes the session (about 7 s measured). Start each with Bash `run_in_background`, `timeout` 7200000 (the 2-hour cap). **Batch 1, at the 9:30 checkpoint:** one waiter for each slot 10:00, 10:05, ... 11:25 (18). **Batch 2, when the 11:25 waiter fires:** one for each slot 11:30 ... 13:25 (24). 13:30 stays the scheduled close trigger; **do not start a 13:30 waiter in batch 2 (v5.2.16 note: a waiter started at 11:25 hits the 2-hour cap at 13:25 and is killed, as happened 2026-10-26)**; the 13:20 checkpoint starts a fresh 13:30 waiter with `timeout` 900000. Each waiter is a checkpoint trigger: run the slot (C1) at once. If the scheduled primary for that slot already ran, or the waiter did, answer with one line. A waiter that did not fire at its slot, or batch 2 not started, is a missed checkpoint (C1.6): say so and use the scheduled triggers. The early shutdown (C2) deletes the 13:00-13:25 scheduled triggers and may leave their waiters running; a waiter that fires with the account flat and entries over is a one-line no-op.
- **Delete the scheduled twin after a waiter completes (v5.2.11, governor instruction 2026-10-22).** When arming a day (13:30 close), save each 10:00-13:25 primary's trigger id to `archive/chain_ids.json` (`{"YYYY-MM-DD": {"10:00": "trig_...", ...}}`, committed with the arming). When a waiter's checkpoint has run **completely** (state check, fetch, engine, any orders placed and verified, report sent, execution log written) **and the account is flat**, call `delete_trigger` on that slot's id, so the late primary never fires. Do not delete while a position or an open order exists: keep the scheduled fallback armed until flat. If the checkpoint errored, was partial, or the waiter did not fire, do not delete: the scheduled primary is then the fallback. A delete that fails because the trigger already fired is harmless (answer the duplicate with one line). Never delete 9:00, 9:30, 13:30 or 8:00pm.
- **Success-rate tracking (v5.2.12, governor instruction 2026-10-22).** Start every waiter with the description `Slot waiter HH:MM` so its completion shows in the transcript. Each waiter appends `date,slot,due_epoch,fired_epoch` to `archive/waiter_log.csv` itself (commit it at each 13:30). `python3 tools/live/slot_report.py --from 2026-10-23` reports, for the entry window 10:00-12:55: slots covered, missed, first-wake lag (the earlier of the waiter and the scheduled primary; median, p90, max, share over 15/60/300 s), how often the scheduled fallback was needed, and a per-day table, against the scheduler-only baseline of 2026-10-16..22 (median 66 s, p90 233 s, 6.7% of slots over 300 s). **Criteria to delete the scheduled 10:00-12:55 primaries (review Fri 2026-11-06, scheduled one-shot):** at least 10 trading days, 0 missed slots, p90 first wake 20 s or less, fallback used in 2% of slots or fewer. Only the governor decides; the review changes nothing by itself.
- **Backup at 8:00pm:** check that the next trading day's chain exists (the 46 primaries). Create it only if it's missing, and say so.
- **Time zone (v5.2.15):** triggers take UTC. **Never hard-code the offset.** Convert every ET time with `bash tools/live/et2utc.sh "YYYY-MM-DD HH:MM"` (ET = UTC−4 until Sun 2026-11-01, UTC−5 from Mon 2026-11-02, back to UTC−4 on Sun 2027-03-14). A one-shot check (`DST check`, Fri 2026-10-30 8:15 PM ET) verifies Monday 2026-11-02's chain times.
- **Next trading day (v5.2.15):** the 13:30 arming picks the next trading day, skipping weekends and every date in `paper.py`'s `NO_TRADE`. In 2026: after Wed 11-25 arm Mon 11-30 (Thu 11-26 closed, Fri 11-27 early close); after Wed 12-23 arm Mon 12-28 (Thu 12-24 early close, Fri 12-25 closed). In 2027 the closures are listed in `NO_TRADE`.
- **Deposits and withdrawals (v5.2.15):** nothing is held overnight, so at 9:00 compare total value with the previous 13:30 value. An unexplained change is a deposit or withdrawal: record it in E1 and E5, run `python3 tools/live/hwm.py deposit <+/-amount>` so the A1.13 high moves with it, recompute the floor (A1.4 recomputes it from total value and P&L, so it moves by itself), and add the amount to the model equity in `archive/paper_state.json` so the model's dollars stay comparable (percentages are unaffected).
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

**Wednesday 2026-10-28 (before the open), v5.2.22 (governor: "lets remove the frozen trail").** FADE exits from today: +0.15R lock at the first +0.5R close, early cut at 15 min at −0.5R, ⅓ at 2R with the stop to breakeven, 2-ATR chandelier on the rest, out 13:30. The frozen trail never traded live.

**Wednesday 2026-10-28 (before the open), v5.2.21 (governor: "push it").** PULLBACK adds NVDQ NVD MSFU SSG (B1); C1.2 fetches a third group (NVDQ NVD MSFU SSG); the A1.9 earnings skip is back: **MSFT reports today (10-28) after the close, so no MSFU entry on Thu 10-29**; NVDA reports 11-17 pm, so no NVD/NVDQ on 11-18. PULLBACK health tracker added (C5).

**Wednesday 2026-10-28 (early, before the open), v5.2.20 (governor):** FADE health tracker added to the 13:30 report (C5, `tools/live/health.py`, `archive/health_log.csv`, new `reached_2R` column in `archive/live_trades.csv`, backfilled: 10-27 TNA = yes). No trading rule changed. Seed row 2026-10-27: 1 FADE trade, drawdown 0.1%, HEALTHY (provisional).

**Tuesday 2026-10-27 (8:50 PM ET), v5.2.19 adopted (governor: "lets push B + C").** FADE +0.15R lock at the first +0.5R close and early cut at 15 minutes if the close is −0.5R or worse (B2.5, B5.3), from Wed 2026-10-28. Same commit fixes `paper.py`, which never switched the v5.2.18 frozen trail on (`FROZEN_ON` stayed False); both now switch on by date in `simulate()`. The Wednesday chain prompts say v5.2.17; RULEBOOK governs.

**Tuesday 2026-10-27, v5.2.18 adopted (governor).** FADE frozen 1R trail before 2R, capped at +0.75R (B2.5, B5.3), from Wed 2026-10-28. The Wednesday chain prompts say v5.2.17; RULEBOOK governs.

**Tuesday 2026-10-27, 13:30 close (v5.2.17).** Flat, no open orders, **$2,568.92** (+$33.36, +1.32% on the day). One real trade: FADE TNA (fade of IWM), 44 sh @ 56.8299 at 10:10; 14 sh take-profit @ 57.61 (10:53); 30 sh closed by the governor by hand @ 57.58 (11:07). Model: +1.89% (runner out on the chandelier 12:40). Losing streak 0/5; A1.13 clear (high $2,571.81). Entries stopped at 11:40 on the governor's word. Running total since 2026-10-16: 3 real trades, all green, +$75.49. **Wednesday 2026-10-28 chain armed (v5.2.17 wording): all 46 confirmed with list_triggers; ids in `archive/chain_ids.json`.** The 12:00-13:25 waiters of today were killed by the app at about 11:55 (account flat, day ended; no slot lost that mattered).

**Tuesday 2026-10-27, v5.2.17 adopted (governor: "let's skip fridays").** No FADE entries on Fridays from Fri 2026-10-30 (A1.10); PULLBACK unchanged. `paper.py` enforces it.

**Tuesday 2026-10-27, 11:40 (governor: "Let's end the day").** No new entries for the rest of the day (treated as a stop for today only, not a kill-switch for tomorrow). The real account is flat at $2,568.92 with no open orders; the model's TNA runner is a ghost (run slots with `--real-free`). Result so far: one real trade, FADE TNA, +$33.36 (see `live_trades.csv`). The remaining waiters, the 13:30 close and Wednesday's arming are left as they are until the governor says otherwise.

**Wednesday 2026-10-28, 9:00 research (v5.2.25).**
- **Real account:** flat, no positions, no open equity or OCO orders, **total value $2,568.92** (cash $2,568.92, no pending deposit, unchanged from Tuesday's 13:30 value, so no deposit or withdrawal). Daily loss limit (-3%) = $77.07, stop at $2,491.85.
- **Controls:** losing streak 0/5. **A1.13 drawdown stop: clear**, high $2,571.81, stop level $2,186.04, value -0.11% from the high (`hwm.py check 2568.92`). No A1.10 restriction; normal full session. Friday FADE skip starts Fri 10-30.
- **Corporate actions (C3.2):** clean. All 13 funds, NVDQ NVD MSFU SSG and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.4% vs TQQQ +1.1% / SQQQ -1.1%; SOXX +0.8% vs SOXL +2.3% / SOXS -2.3%; IWM +0.1% vs TNA +0.3%; XLK +0.5% vs TECL +1.4% / TECS -1.1%; XBI -0.3% vs LABU -1.4% / LABD +1.1%; XLF -0.3% vs FAS -1.1% / FAZ +0.8%); none near 20%. Wide premarket spread on SSG (10.71 / 12.83) and TECL, LABU (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-30..2026-10-27) -> `archive/paper_rvol_2026-10-28.json`.
- **Context:** large reports before the open include BIIB, BSX, GE Vernova, ADP, GRMN, PSX, VRT; after the close MSFT, GOOGL, GOOG, KLAC, NOW, EBAY, FTNT, F, FDX, TMUS (none are traded proxies; MSFT is MSFU's underlying, so no MSFU entry Thu 10-29, A1.9). The Fed meets today (Wed 10-28). No scheduled macro release found before 13:30 in the data available.

**Tuesday 2026-10-27, 9:00 research (v5.2.16).**
- **Real account:** flat, no positions, no open equity or OCO orders, **total value $2,535.56** (cash $2,535.56, no pending deposit, unchanged from Monday's close; the $2,500 deposit has not landed). Daily loss limit (-3%) = $76.07, stop at $2,459.49.
- **Controls:** losing streak 0/5. **A1.13 drawdown stop: clear**, value = the high $2,535.56, stop level $2,155.23 (`hwm.py check 2535.56`). No A1.10 restriction; normal full session.
- **Corporate actions (C3.2):** clean. All 13 funds and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.4% vs TQQQ +1.3% / SQQQ -1.3%; SOXX +1.7% vs SOXL +5.1% / SOXS -4.9%; IWM +0.4% vs TNA +1.5%; XLK +0.7% vs TECL +2.3% / TECS -1.7%; XBI -0.2% vs LABU +0.8% / LABD +0.1%; XLF +0.5% vs FAS +1.2%; UVXY -1.2%); none near 20%. Wide premarket spreads on TECL, TECS, LABU, LABD (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-29..2026-10-26) -> `archive/paper_rvol_2026-10-27.json`.
- **Context:** large reports before the open include UPS, KO, PYPL, BA, SPGI, FCX, RCL, HCA; after the close V, STX, NXPI, TER, HOOD, ENPH (none are proxies). The Fed meets Wed 10-28. No scheduled macro release found before 13:30.

**Monday 2026-10-26, 13:30 close (v5.2.16).**
- **Real account:** flat all day, no positions, no open equity or OCO orders at 13:30, total value **$2,535.56** (unchanged; no trade, no deposit yet). Losing streak 0/5. No safety control fired. A1.13 drawdown stop clear (high $2,535.56, stop level $2,155.23).
- **Signals:** none. FADE: XLF and IWM broke up but their retests held (no close back inside), the other four never broke in the window; PULLBACK: TECS volume breakout (10:05) failed the trend test, UVXY broke out at 12:45 but never dipped. Early shutdown at 12:55 (account flat). Model: 0 trades, equity $2,520.60.
- **Waiters:** 72 of 72 entry slots (2 days) covered by the waiter first, lag 7 s every time (`slot_report.py`). **Fault found:** the 13:30 waiter started at 11:25 hit the 2-hour cap and was killed at 13:25 before it could fire. Fix in D1: batch 2 is 11:30-13:25 only, and the 13:20 checkpoint starts a fresh 13:30 waiter (timeout 900000); the scheduled 13:30 close trigger stays the primary.
- **Tuesday 2026-10-27 chain armed:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids in `archive/chain_ids.json`. ET is UTC-4 until Sun 11-01; the DST check runs Fri 10-30 8:15 PM ET.
- **Research this session (no live rule changed):** FADE diagnosis on Databento 2023-03..2026-10 (`results/fade_*.txt`) and PULLBACK-only run (`results/db_pb.txt`): the edge is absent 2023-03..2026-02 on the Mini feed and present Mar-Oct 2026; Mini bars are not a fair test of the thin funds (`results/db_feed_compare.txt`). Candidate (not adopted, waits for the governor): stop floor 0.3% + touch within 3 bars. Governor instruction 2026-10-26: A1.13 hard stop at -15% from the all-time high (added, v5.2.16). A Massive (Polygon) consolidated-tape download was run in another session; not yet in this repo.

**Monday 2026-10-26, 9:00 research (v5.2.16).**
- **Real account:** flat, no positions, no open equity or OCO orders at 9:00, **total value $2,535.56** (cash $2,535.56, no pending deposit, unchanged from Friday's close; the $2,500 deposit has not landed). Daily loss limit (-3%) = $76.07, stop at $2,459.49. Floor 50% of deposited cash.
- **Controls:** losing streak 0/5 (2 real trades, both wins). **A1.13 drawdown stop (new, v5.2.16): clear**, high $2,535.56, stop level $2,155.23 (`archive/hwm.json`, `hwm.py check 2535.56`). No A1.10 restriction; normal full session. No single stock is traded, so no earnings skip applies.
- **Corporate actions (C3.2):** clean. All 13 funds and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.5% vs TQQQ +1.4% / SQQQ -1.4%; SOXX +1.3% vs SOXL +3.7% / SOXS -3.4%; XLK +0.6% vs TECL +1.7% / TECS -1.8%; IWM +0.1% vs TNA +0.3%; XBI +0.3% vs LABU +0.8% / LABD -1.1%; XLF flat vs FAS +0.3%; UVXY -2.6%); none near 20%. Wide premarket spreads on TECL, TECS, LABU (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-28..2026-10-23) -> `archive/paper_rvol_2026-10-26.json`.
- **Context:** first session on the v5.2.13/14 lists (XLF in, AMD and NVD out). Futures higher premarket (QQQ +0.5%, semis +1.3%). Before 13:30: VZ reported before the open; large reports after the close include CDNS, NUE, WELL, HIG (not proxies). The Fed meets Wed 10-28. No scheduled macro release found before 13:30.

**Friday 2026-10-23, 9:00 research (v5.2.12).**
- **Real account:** flat, no positions, no open or recent orders, **total value $2,508.09** (all cash, buying power $2,508.09). The daily loss limit (A1.2) is measured from it: a close at or below **$2,432.85** blocks entries.
- **Controls:** losing streak 0/5. No AMD or NVIDIA earnings today (AMD reports Tue 2026-11-03 after the close: skip the AMD fade row Wed 11-04). Regular full session, no holiday.
- **Corporate actions (C3.2):** clean. All 14 funds and 7 proxies active. Premarket moves match their underlyings at the stated leverage (TQQQ -0.8% vs QQQ -0.2%, SOXL +0.7% vs SOXX +0.2%, TNA -1.9% vs IWM -0.6%, LABU -2.6% vs XBI -0.8%); nothing near 20%.
- **RVOL baseline:** 20 sessions (2026-09-25..2026-10-22) -> `archive/paper_rvol_2026-10-23.json`.
- **Context:** futures slightly lower after Thursday's tech sell-off (S&P about -0.2%, Nasdaq 100 about -0.1%). AI-infrastructure financing worries, high oil, French bond turmoil; the Fed meets next week (Oct 28), hike bets have faded. No scheduled data release found before 13:30.
- **Model:** equity $2,087.46. Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46.
- **Today is the first day of the slot waiters (v5.2.10-12):** 9:30 starts batch 1 (10:00-11:25), the 11:25 waiter starts batch 2 (11:30-13:25); waiter fire times log to `archive/waiter_log.csv`; scheduled twins deleted after flat completions via `archive/chain_ids.json`.
- **Still unverified live:** the 1/3 OCO + 2/3 stop together on one FADE position (E2 item 1); no test order was run (governor, 2026-10-22).

**Thursday 2026-10-22, 9:00 research (v5.2.7).**
- **Real account:** flat, no positions, no open equity or OCO orders at 9:00, **total value $2,508.09** (cash $2,508.09; deposited cash $2,493.43, floor $1,246.72). Daily loss limit (-3%) = $75.24, stop at $2,432.85.
- **Controls:** losing streak 0 (1 real trade, a win). AMD reports Tue 2026-11-03 after the close (skip AMD fade row Wed 11-04); no AMD or NVIDIA report today; normal full session (`paper.py` calendar ends 2026-12-31).
- **Corporate actions (C3.2):** clean. All 14 funds and 7 proxies active; premarket moves match their underlyings at the stated leverage (SOXX -4.2% vs SOXL -12.5% and SOXS +12.7%; QQQ -1.6% vs TQQQ -4.9% and SQQQ +5.0%; XLK -2.2% vs TECL -5.9% and TECS +6.4%; AMD -4.7% vs AMDL -9.5% and AMDD +4.4%); none more than 20% off yesterday's close.
- **RVOL baseline:** 20 sessions (2026-09-24..2026-10-21) -> `archive/paper_rvol_2026-10-22.json`.
- **Context:** sharp risk-off premarket, semis hardest hit (SOXX -4.2%, AMD -4.7%, NVDA -2.4%, QQQ -1.6%, IWM -0.6%, XBI -0.5%). A web search did not confirm a cause for today; none is assumed. Earnings before 13:30 are large non-proxy names only (HON, UNP, PG, LMT, NSC, SPOT, CMCSA and similar); WDC reports after the close. Wide premarket spreads on thin legs (TECL, LABU, TECS), so expect the spread check (A1.6) to matter at the open.
- **Model:** equity $2,087.46 (excludes the $500 deposit). Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46. Yesterday (Wed 10-21): no signals either system, early shutdown at 12:55.
- **Routine for today:** fetch all three C1.2 groups every slot (incl. NVDA); `--real-free` only if the governor closes a position by hand; reports lead with FADE status and a one-line PULLBACK status (governor, 2026-10-20). If a slot fires before its bar closes, the newest bar is one short (E6); refetch if a signal is near trigger.
- **Still unverified live:** the 1/3 OCO + 2/3 stop together on one FADE position (E2 item 1).
- **Chain:** Thursday's 46 slots verified complete at the Wednesday 8:00 PM backup. Slot backups (D1, v5.2.8) armed by hand for the rest of today: 16 one-shots at 10:17, 10:22, ... 11:32 ET (2 minutes after the 10:15-11:30 primaries). The 10:05 primary arrived 7:27 late (14:12:27 UTC), after a manual 10:10 run had covered it; the 10:10 primary was likewise a duplicate. This day's 13:30 close arms Friday 2026-10-23. Bimonthly reminder `trig_01Dwv81fMNH5Rw141Uy3wLKP`, next 2026-11-01.

**Thursday 2026-10-22, 13:30 close (v5.2.12).**
- **Real account:** flat, no positions, no open orders at 13:30, total value **$2,508.09**, unchanged on the day. No real trade today. Losing streak 0/5.
- **Day:** no real or model trades. FADE: no entries (AMD and XLK retests expired or held). PULLBACK: TECS (11:30) and NVD (11:25, 12:25) formed setups that failed the room-to-target and stop-distance filters (B3.8); nothing qualified. Early shutdown done at 12:55 (13:00-13:25 triggers deleted).
- **Model:** equity $2,087.46 (no trades today). Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46.
- **Changes today:** v5.2.9 FADE late band 1.5%; v5.2.10 no slot backups, one-shot slot waiters (`slot_clock.sh`); v5.2.11 delete the scheduled twin after a flat waiter checkpoint (`archive/chain_ids.json`); v5.2.12 success-rate tracking (`archive/waiter_log.csv`, `slot_report.py`), review set for Fri 2026-11-06 (`trig_018N3oepVLFhbBuPwtwcTWJ1`).
- **Friday 2026-10-23 chain armed and verified:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids of the 10:00-12:55 primaries in `archive/chain_ids.json`. Monday arms Fri 13:30 with UTC-4 (UTC-5 from Mon 2026-11-02).
- **Scheduler lag (E6):** median 62 s, :05/:10/:15 slots worst; clock waiter wake measured 4-10 s.

**Friday 2026-10-23, 13:30 close (v5.2.12).**
- **Real account:** flat, no positions, no open orders at 13:30, total value **$2,535.56**. 9:00 value was $2,508.09. Losing streak 0/5. No safety control fired.
- **Real trade:** UVXY PULLBACK, 131 sh, 19.0599 -> 19.2701, **+$27.47** (1.100% of position); model +$17.21 (0.824%). Entered at the last entry slot, closed by the 13:30 time exit.
- **Model reset (governor instruction, 2026-10-23):** the model/real comparison restarts at v5.2.12, from 2026-10-23. Model history before today is archived in `archive/paper_trades_pre_v5.2.12.csv` and `archive/paper_state_pre_v5.2.12.json` (3 trades, +$104.67, equity $2,104.67). The model is re-based to the $2,500 account base at the start of 2026-10-23 (`paper.py` default); today's UVXY trade is re-sized to that base: +$20.60 (0.824%), equity **$2,520.60**, streak 0. Real trades stay in `archive/live_trades.csv` (2 trades, +$42.13 since 2026-10-16); the comparison counts real trades from 2026-10-23 only (1 trade, +$27.47 vs model +$20.60). No trading rule changed.
- **Waiters, first day:** all slots fired 4-10 s after the clock; a container restart at 11:46 ET killed 20 waiters, re-created at once (see E6). Log in `archive/waiter_log.csv`.
- **Monday 2026-10-26 chain armed:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids of the 10:00-13:25 primaries in `archive/chain_ids.json`. Verified by the Friday 8:00pm check.

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
