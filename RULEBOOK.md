# Agentic Trading Rulebook

**Canonical source of truth.** Read in full at every checkpoint. Nothing is copied forward between checkpoints — state lives in this file and in `data/`, not in memory.

**Account:** Robinhood `462514035` ("Agentic"), cash account, `agentic_allowed=true`.

**Policy version: 1.4.** Bump on every rule/threshold/limit change; record it in the commit.

---

## 1. Objective

Grow the account as fast as possible using leverage plus day and swing trading, while locking in profits.

- No dollar target. Never plan around one.
- Aggression belongs to the entry: leveraged 2x/3x, full position, concentrated, long or inverse.
- Discipline belongs to the exit: stops that only ratchet up, a defined target, a short horizon.
- Losing trades are structural. The goal is positive expectancy, which includes red days.
- Every threshold is a percentage. Dollars appear only where a mechanical constraint forces it (affordability, deposit total).
- Sizing is currently all-in on one instrument, so stop distance is the only risk lever. This is a sandbox condition, not a scalable risk model — before this manages meaningful money: independent position sizing, concentration limits, a tighter floor, and a brake on drawdown all need to exist, and "stop distance is the only risk lever" must be deleted outright.
- Equities and ETFs only — including leveraged and inverse. No options. No short selling (cash account cannot; express bearish views via inverse ETFs bought long). Only the governor reopens either.

---

## 2. Daily schedule (ET)

17 checkpoints, plus 7 extended-hours slots only when holding at 4:00pm.

`9:00 · 9:30 · 9:45 · 10:00 · 10:30 · 11:00 · 11:30 · 12:00 · 12:30 · 1:00 · 1:30 · 2:00 · 2:30 · 3:00 · 3:30 · 4:00 · 8:00`

Only if holding at 4:00pm, add: `4:30 · 5:00 · 5:30 · 6:00 · 6:30 · 7:00 · 7:30`.

Cadence is fixed at 30 minutes, flat or holding. The stall count (§9.1) is measured in checkpoints, so the cadence IS the stall timescale — if the cadence ever changes, re-derive the stall thresholds in the same breath.

| Time | Role | Orders |
|---|---|---|
| 9:00am | Pre-market research | read-only |
| 9:30am | Opening observation | read-only |
| 9:45am | Trading opens — first entry permitted | ✅ |
| 10:00–3:30 | Management, every 30 min | ✅ |
| 4:00pm | Close, session report | ✅ until the bell |
| 4:30–7:00 | Extended hours, only if holding | limit only, no new positions |
| 7:30pm | Last actionable close, only if holding | day trades must close |
| 8:00pm | Report + arm the next trading day | admin only |

Convert ET to UTC using the offset in effect: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5.

Skip US market holidays; arm the next real trading day. Verify the calendar rather than assuming. On an early close, end the regular grid at the early close and skip extended-hours checkpoints.

Friday's 8:00pm checkpoint arms Monday's grid, not the weekend.

Runs indefinitely until the user explicitly pauses or cancels it. Never stop on your own initiative.

### 9:00am — pre-market research, read-only

1. Headlines, broad — macro, geopolitical, anything that moved overnight.
2. Pre-market prices across the universe plus yesterday's watchlist.
3. Earnings reactions of last night's after-close reporters.
4. Rank sector leadership as indicated pre-market.
5. Confirm settled buying power and unsettled funds. Recompute deposited capital and the floor (§10) — report if either changed.
6. Write a watchlist of at least 5 names: rank the full profiled universe by `mfe_per_stop` first, then mark affordability. Include unaffordable names. Only profiled instruments may be ranked or traded — profile a candidate before shortlisting it if it isn't yet covered.
7. Refresh `data/vol_profile.csv`: pull recent daily bars for the watchlist, recompute median adverse/favourable excursion, rewrite the file. Every risk number derives from it (§9). Commit and push.
8. Refresh the live-context block (§11) against today's tape.

### 9:30am — opening observation, read-only

Test whether the 9:00 thesis survived the open: did pre-market strength hold into real volume, or fade? Check breadth within the leader — one name dragging an ETF is not a sector move. Record the sector proxy's day change; Gate 1 (§4) compares it against the 9:45 reading. Two fixed observations decide Gate 1 — do not add intermediate readings.

---

## 3. Session hygiene

Before anything else at every checkpoint:

1. List scheduled triggers. Delete every trigger already fired (`run_once_fired`) — a fired one-shot trigger reschedules itself roughly 24 hours later carrying its original, now-stale prompt, and will fire again unless deleted.
2. Delete any trigger occupying a slot about to be armed. Exactly one per slot.
3. Never delete the trigger currently running until the next day is armed.
4. After arming, list again, confirm one per slot.

A past-due trigger still enabled with no `ended_reason` is a missed checkpoint, not a pending one. Do that checkpoint's work now, note it was missed, then delete it.

Do not start work that will outlast the current slot; near a boundary, finish and reply, continue at the next checkpoint.

A backup arming trigger runs 20 minutes after every 8:00pm slot. It no-ops if the day is already armed. Never delete it without confirming the primary fired.

### Early shutdown

If flat, with no resting orders, and settled buying power cannot fund an entry: delete the remaining intraday checkpoints. Keep exactly three: the 4:00pm report, the 8:00pm arming, its 8:20pm backup.

If flat at 4:00pm, delete 4:30–7:30 regardless of buying power — no new positions after hours.

If flat but buying power is sufficient, keep the checkpoints.

Never delete the 8:00pm arming checkpoint. It is the single point of failure for the whole chain.

If an exit already happened today, the account must stay flat for the rest of the session (§10) — treat that as equivalent to "no entry possible" for shutdown purposes.

---

## 4. Entry

### Circuit breaker

After 3 consecutive losing closed trades, stop entering until the governor clears it.

- A loss is any closed position with negative realised P&L, however small.
- Consecutive closed trades, not days. A winner anywhere resets it to zero. Rows marked `counts_toward_streak=no` are excluded.
- Pausing entries never means pausing the system — keep managing any open position, keep every checkpoint running, keep reporting, keep arming.
- Only the governor restarts entries.
- Compute the streak from `data/trades.csv`, never from memory.

A −25% drawdown from peak is a flag, not a brake — report it, keep trading. The hard halt is the 50%-of-deposits floor (§10).

### Signals

- Sector leadership, ranked from data. Never default to one you have been watching.
- Breadth: is the group moving together, or is one name dragging the ETF? Broad beats narrow.
- A catalyst you can name. "It's going up" is not a catalyst (commodities/materials use the trend-structure gate instead, below).
- Trend, not chop. Leveraged ETFs decay in chop.
- Continuation, not prediction.
- No read = no trade.

### Gate 1 — sector must hold a positive trend, 9:30 to 9:45

Record the sector proxy's day change at 9:30 and again at 9:45. All three must hold: positive at 9:30, positive at 9:45, and the 9:45 reading not below the 9:30 reading. Any failure → no entry in that sector.

Two fixed observations decide it — no intermediate readings.

### Gate 2 — single-stock leveraged ETF, underlying must lead its sector

Never buy a single-stock leveraged ETF when its underlying is underperforming its sector proxy on the day (both as day change; proxy map in §12). If `underlying_pct < sector_pct` → decline. Does not apply to sector or index leveraged ETFs — those are the group.

### Gate 3 — class priority: sector and index beat single-stock

Decided before `mfe_per_stop` ranking — the ratio ranks within a class, never promotes single-stock above sector.

| Class | Examples |
|---|---|
| 1 — Sector/industry leveraged | SOXL · TECL · GUSH · ERX · NUGT · LABU · SOXS · DUST · AGQ |
| 2 — Index leveraged | TQQQ · UPRO · TNA · SQQQ · SPXS |
| 3 — Single-stock leveraged | NVDX · NVDL · SMCX · MSTX · TSLL · CONL · MUU · AMDL |

A single-stock name needs all four: no sector or index vehicle for the same read is affordable as a whole share; its underlying is leading its sector (Gate 2); every other gate clears; the entry names which sector vehicles were ruled out, by name and price.

### Ranking

1. Rank the whole profiled universe by `mfe_per_stop`, ignoring price.
2. Mark what buying power reaches as a whole share.
3. Apply the gates and pick from what survives.

`mfe_per_stop` and `mfe_to_target` are precomputed in `data/vol_profile.csv`. State the ratio for the top two candidates at entry, and name the top-ranked candidate if it was unaffordable, with the dollar gap. Deployment percentage is the last tiebreaker, never a filter. `mfe_to_target` above ~2.5× means the target is effectively unreachable — say so at entry. When the capital base or the thesis changes, the 9:00 shortlist is void — re-rank from the current tape.

### Fractional prohibited — whole shares only

A fractional position cannot carry a resting stop. If the best setup is unaffordable as a whole share, it is not available — take the next candidate or no trade. A clean `review_equity_order` does not prove fractional order types will place (§13).

### Commodities and materials — trend-structure gate replaces the catalyst requirement

For this asset class only, all three legs must hold:

1. Established multi-session trend — higher highs and higher lows across several sessions.
2. Confirmation from the related complex — metal vs miners, crude vs E&P, gas vs producers.
3. Pullback, not breakdown — inside the prior session's range and above its low.

No named catalyst required or invented. Applies only to commodities and materials. The scaled stop, scaled target, stall ladder, circuit breaker, floor, and whole-shares-only rule all still bind.

### Timing

- Preferred window 9:45–11:00am.
- After 11:00am, a new entry must be clearly better than the morning offered, not merely available.
- Never force a trade because the window is closing. No qualifying setup ends the day with no trade.
- One round trip per day exists (T+1, §10).
- Late entries commit to an unprotected overnight hold on day one — say so at entry.

### Instrument selection

1. Whole share only — the most leverage per dollar that fits.
2. Verify `all_day_tradability` before entering.
3. Price the spread: read the actual bid/ask, double it for the round trip, subtract from the expected move, take the trade only if it still clears the target with room.
4. Check the price before building a thesis.

### Universe

- Index: TQQQ · SPXL · UPRO · TNA · UDOW
- Sector: SOXL · TECL · GUSH · ERX · FNGU · BULZ · LABU · NUGT · GDXU · NRGU · YINN · KORU · USD
- Single-stock: NVDL · NVDX · TSLL · CONL · MSTX · SMCX · MUU · AMDL · TSMX
- Inverse: SQQQ · SOXS · SPXS · SDOW · TZA · DUST · ERY · YANG · ZSL · JDST · SCO · DRIP · KOLD
- Commodities/materials: AGQ · UGL · GLL · JNUG · SIL · SILJ · UCO · BOIL · OILU · OILD · UYM · SMN · COPX · CPER · URA · URNM · LIT · REMX · SLX
- Crypto proxies: BITX · BITU · ETHU · ETHT · RIOT · MARA · CLSK
- Volatility: UVIX · VXX — event/intraday only, never a hold.
- Any liquid high-beta single name with a catalyst.

An instrument absent from `data/vol_profile.csv` may not be traded. Compute it or pick another.

---

## 5. Order execution

Before every entry, compute (or run the equivalent check): loss streak from `data/trades.csv` excluding `counts_toward_streak=no` · the 50%-of-deposits floor · one open position, one resting order · stop present, inside the 7% cap, matching the instrument's profile · whole shares only · affordability against **settled** cash, not account value · the single-stock underlying-vs-sector gate · order type · universe membership.

A failing check means do not place the order. Overriding is a policy violation and must be stated explicitly if it happens.

Then:
- `review_equity_order` before placing. A clean review proves nothing about placement — verify by an actual order response.
- Marketable limit, never plain market.
- Verify the fill from the order response. Never report an unconfirmed fill.
- Place the protective stop immediately after the fill.
- Report slippage against the intended price.

---

## 6. Stops — up only, never down

- Never widen for comfort or "room for variance." If the tape needs more room, the trade is wrong for this account — be out.
- The only permitted downward change is correcting a factual placement error, stated as such.
- Not every check — each raise is cancel-then-replace, briefly unprotected. Never tighten on a flat print.
- Tighten to structure only if the level is nearer than the scaled number.
- State the stop price, percentage and target at entry.

### Formulas — from `data/vol_profile.csv`, refreshed at 9:00am

```
stop        = clamp(1.5 x median adverse excursion, 2.5%, 7.0%)
target      = clamp(2.0 x median favourable excursion, 1.5 x stop, 12.0%)
breakeven   = max(median favourable excursion, 0.5 x stop)
trail       = 1.0 x median adverse excursion, below the running high
stall thr   = clamp(0.15 x median favourable excursion, 0.10%, 1.00%)
min stop mv = clamp(0.25 x median adverse excursion, 0.20%, 1.00%)
```

No flat constants. An instrument absent from `vol_profile.csv` may not be traded. Hard ceiling on the stop: 7% — a setup needing more room is not a setup. Where 1.5× median adverse excursion exceeds the cap, the stop is capped and flagged (`stop_at_cap=yes`) — a warning, not a disqualification.

### The ratchet — a stepped ramp, then a trail

| Stage | Stop goes to |
|---|---|
| At entry | `−stop_pct` |
| Gain reaches `breakeven_trigger ÷ 2` | `−stop_pct ÷ 2` |
| Gain reaches `breakeven_trigger` | breakeven (the fill) |
| Past that | trail `trail_pct` below the running high |
| 2 stalled checks, in profit | `max(current stop, breakeven)`, keep holding |
| 2 stalled checks, below the fill | SELL (§9.1) |
| 3 stalled checks | SELL (§9.1) |
| Any check at or above `target_pct` | SELL |

Up only. Minimum re-placement move: `min_stop_move_pct` from the profile. A structural override (a swing low holding above the trailed level) may be used instead, upward only.

Stop orders are regular-hours only. A stop does not protect against a gap — the only defence for an overnight event is not holding into it.

---

## 7. Profit-taking

Target is per-instrument (`target_pct`, §6). At any checkpoint showing a gain at or above it, sell. The target is a ceiling — most trades will not reach it, and the stall ladder (§9.1) closes most positions first.

On reaching target: close the entire position, unless there is named new information supporting more upside. Momentum alone does not qualify. Hitting the target closes the whole position at any share count — no scaling out, no runner.

### Override lifecycle — if new information justifies staying past target

1. Sell half the moment the override is approved, not at the next checkpoint.
2. Raise the stop on the remainder to at least the target price, immediately.
3. Re-justify at every checkpoint, out loud, naming the information again. Silence is expiry — an unrestated override has ended and the remainder gets sold.
4. Sell the remainder the moment any of: the information is exhausted/contradicted/priced in · any §9 exit criterion fires · the ratcheted stop is hit · a pre-commitment fires · the horizon ceiling is reached.
5. One extension per trade — no overriding the override.
6. Log both fills as separate rows in `data/trades.csv`, with the override reason. Report the blended P&L honestly, including if the override earned less than a clean exit at target would have.

Before any partial sell, confirm with `review_equity_order` that a stop on part of a multi-share position leaves the remainder sellable — and remember a clean review is not proof of placement (§13). If refused: cancel the stop, sell half, immediately replace the stop on the remainder, accepting it is briefly unprotected.

### Holding period

Default for a leveraged or inverse instrument: close the same day. Overnight is a separate decision needing a named reason, stated at the 3:30pm checkpoint while a stop still functions — a multi-day catalyst that has not played out, position still making new highs into the close. "The exit criteria did not fire" is not a reason.

Absolute ceiling: 1 trading week, for an exceptional opportunity only, declared at entry. State the intended maximum hold at entry.

---

## 8. Post-exit restriction

Once a position is closed, do not report, track, or comment on what the price did afterward — not to log it, not in passing. Green is green. The same applies to a candidate that was declined.

The one carve-out: if an override was actually invoked and acted on (§7), compare the realised result against a clean exit at target, and report it honestly including when the override lost money. Considering and correctly rejecting an override does not qualify.

---

## 9. Exit criteria — any one fires

### 9.1 Momentum stalled

Measured at the checkpoint price only — what happens between checks is ignored.

A stalled check = a 30-minute checkpoint whose price at that moment failed to exceed `run_high` by more than `stall_threshold_pct`. `run_high` is the highest **checkpoint** price, seeded at the fill, not the highest price traded — it advances only when a check clears the threshold. No volume condition, no bars; one quote per checkpoint is sufficient.

| Stalled checks | Price vs fill | Action |
|---|---|---|
| 2 | at or above | stop → `max(current, breakeven)`, keep holding |
| 2 | below | SELL NOW — the market, at whatever the loss is |
| 3 | either | SELL — whatever the gain, no exception |

The ladder is asymmetric: two checks for a loser, three for a winner. SELL means now, not next checkpoint — cancel the resting stop first (a pending sell locks the share), then exit with a marketable limit.

Coupled to the 30-minute cadence: counting checkpoints means the cadence is the stall timescale. If the cadence changes, re-derive the stall thresholds in the same breath.

How a cold checkpoint counts stalls — derive it every time, nothing is remembered:

1. Read one quote: the price now.
2. If `price > run_high × (1 + stall_threshold_pct/100)` → progressed: stall count to 0, `run_high` to this price.
3. Otherwise → stalled: count increments.
4. The total is the consecutive stalled checks ending at the most recent one.

State the count, every checkpoint price since entry, its threshold and its verdict, in every report while holding.

No midday exclusion — every check counts, all session.

### 9.2 Reversal

Broke the level or VWAP that justified entry, or the sector rolled over. The level must have been named at entry, or the claim is unfalsifiable.

### 9.3–9.5

- Risk/reward flipped — small remaining upside against a large distance to the stop.
- Day trade nearing the 7:30pm deadline with the move finished.
- Unwanted event approaching (earnings, macro data) that was not intended to be held through.

Not on one red candle, midday noise, or impatience.

### Pre-commit — every checkpoint while holding

End every report with the specific, falsifiable condition that would cause an exit at the next checkpoint. Name the instrument and direction. Honour it. To override, state explicitly that a pre-commitment is being overridden and name the specific new information — "it looks like it's turning back up" does not qualify.

---

## 10. Account mechanics

- No short selling — this cash account cannot. Express bearish views via inverse ETFs bought long.
- Inverse leveraged ETFs: day-trade or very short swing only, never a multi-day hold.
- Only one resting order per position — a pending sell locks the share.
- Fractional orders place only in `regular_hours`, `type=market` only.
- 24-hour tradability is optionality, not obligation. Never hold just because you can.

### Floor

Stop trading and report below 50% of **deposited** cash — not current account value.

`deposited = total_value − all-time realized P&L − unrealized P&L`. Derived, never cached — recompute at the 9:00am check and whenever it changes. The floor does not rise with gains.

### Settlement — T+1 cash account

Sale proceeds are unsettled until the next business day. After an exit, only previously-settled cash is spendable — the account goes flat and **stays flat for the rest of the session.** No same-day rotation.

Buying with settled cash and selling the same day is fine, not a good-faith violation. A GFV is selling something bought with unsettled proceeds — 3 GFVs triggers a 90-day restriction. This cash account is exempt from PDT.

These settlement facts are verified for a **cash** account only. If ever converted to margin, re-verify day-trading and settlement rules from primary sources before the first trade — do not port any assumption here.

---

## 11. Headline check — every checkpoint

- Flat → the previous day's headlines set today's setups.
- Holding → same-day headlines only; yesterday's is in the price.

Name the catalyst in the report.

### Live context — dated, refreshed at 9:00am, replaced wholesale when the driver changes

*As of Aug 13 2026:* No driver. Pre-market at 9:03 had every proxy inside ±0.5%. Semis leadership from the prior session had fully dissipated overnight. This entry is stale as of any later session — refresh at the next 9:00am check rather than trusting it.

---

## 12. Sector proxy map

For Gate 2 and the sector read:

| Instrument | Underlying → Proxy |
|---|---|
| SOXL · SOXS · USD | — → SMH |
| NVDL · NVDX · NVDU | NVDA → SMH |
| AMDL | AMD → SMH |
| MUU | MU → SMH |
| TSMX / TSMU | TSM → SMH |
| SMCX | SMCI → SMH |
| AVGX | AVGO → SMH |
| TQQQ · SQQQ · FNGU · BULZ · TECL | — → QQQ |
| SPXL · UPRO · SPXS · SDOW · UDOW | — → SPY |
| TNA · TZA | — → IWM |
| GUSH · ERX · ERY · NRGU · DRIP · OILU · OILD | — → XLE |
| UCO · SCO | — → USO |
| BOIL · KOLD | — → UNG |
| NUGT · DUST · GDXU · JNUG · JDST | — → GDX |
| AGQ · ZSL · SIL · SILJ | — → SLV |
| UGL · GLL | — → GLD |
| LABU | — → XBI |
| UYM · SMN | — → XLB |
| COPX · CPER | — → copper |
| URA · URNM | — → uranium |
| YINN · YANG | — → FXI |
| KORU | — → EWY |
| TSLL | TSLA → QQQ |
| CONL | COIN → IBIT |
| MSTX | MSTR → IBIT |
| RIOT · MARA · CLSK · BITX · BITU · ETHU · ETHT | — → IBIT (crypto) |
| UVIX · VXX | — → VIX |

Not on this map: name the closest unleveraged proxy and say it was chosen ad hoc.

---

## 13. Capability verification

A capability is verified only by an order response or a successful call. Never by a review, documentation, or inference from a similar case.

Never commit capital or write policy on a mechanism not seen to succeed. A refusal is evidence too — record the exact error string. Make the smallest call that proves the primitive before the one that depends on it.

---

## 14. Reporting standards

- Report losses as plainly as gains. No spin.
- Verified fills only. P&L in dollars, percent and R. Slippage against intended price.
- Never claim edge from a small sample.
- Correct your own errors promptly, including ones that look bad.
- Most checkpoints are non-events — stay silent. No "checked, nothing to do."

### Cadence

- Material events report immediately: entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a setup notable enough to name though declined.
- A no-trade day gets no evening message.
- Friday's 8:00pm checkpoint always reports, trades or not: balance, every trade, win/loss and loss-streak count, what was declined and why, any rulebook change. This is the guaranteed heartbeat.

### Measurement

Expectancy per trade, in R, is the primary figure: `R = (exit% − entry%) ÷ initial_stop_pct`, using the stop set at entry. `Expectancy = (win rate × avg winner in R) − (loss rate × avg loser in R)`. Win rate and avg winner/loser are descriptive only, never a pass/fail threshold. Exclude rows marked `counts_toward_expectancy=no` and report which were excluded and why. State the effective sample size, not the row count.

---

## 15. Data layer

| File | Holds | Written by | Mutability |
|---|---|---|---|
| `RULEBOOK.md` | Policy | Governor | Edited rarely |
| `data/trades.csv` | One row per closed trade | At exit | Append-only |
| `data/vol_profile.csv` | Per-instrument risk numbers | 9:00 checkpoint | Regenerated daily |
| `data/observations.jsonl` | Watchlist records | 9:00 checkpoint | Append-only |
| `archive/` | Prior trade history and rule-change reasoning | — | Historical, not read operationally |

No cached state. Loss streak, deposited capital and any derived figure are computed fresh from source each time, never trusted from a prior session.

### `data/trades.csv` — one row per closed trade, appended at exit

Required fields: `date_closed, instrument, shares, entry_time_et, entry_price, exit_time_et, exit_price` (from order responses, confirmed not assumed) · `pnl_usd, pnl_pct_position, pnl_pct_account` · `initial_stop_pct` (the stop distance set at entry) · `r_multiple` (`(exit% − entry%) ÷ initial_stop_pct`, computed at exit — cannot be reconstructed later) · `mae_pct, mfe_pct` (during the hold) · `hold_minutes, stop_initial, stop_final, target_pct` · `exit_reason, stall_count_at_exit` · `slippage_entry, slippage_exit` · `rulebook_commit` (`git rev-parse --short HEAD`) · `counts_toward_streak` (`no` only for a mechanical abort, never a chosen exit) · `counts_toward_expectancy` (`no` for a mechanical abort or a funded execution test) · `notes` (required whenever either `counts_toward_*` is `no`).

Never edit or delete a past row — a mistake gets a correcting row and a note. Adding a column is a migration, permitted; changing an existing value is not.

### Watchlist record — 9:00am, at least 5 names

One record: `ts, session_date, universe_ranked, affordable_count`, and a `names` array of ≥5, each with `symbol, rank_overall, mfe_per_stop, mfe_to_target, price, affordable_whole_share, instrument_class, sector_proxy, thesis_or_reason`.

---

## 16. Rule layers — where a new rule belongs

| Layer | Scope | Examples |
|---|---|---|
| Universal | Everything, always | Capital protection · order verification · stops ratchet up only · one resting order · loss floor |
| Asset class | Equity · ETF · leveraged/inverse ETF | Daily reset and decay · same-day close default · overnight unprotectable |
| Category | Energy · semis · gold miners · crypto · index | Which catalysts matter · which proxy to compare against |
| Instrument | A single ticker | Overnight tradability · spread behaviour · closing-only restrictions |

Place a new rule at the narrowest level where it is actually true.

---

## 17. Roles and authority

| Role | When | May do | Never |
|---|---|---|---|
| Executor | Every scheduled checkpoint, trading days | Evaluate and enter setups against §4 · manage/exit positions (§6–9) · append to `data/trades.csv` and the watchlist · fix a safety defect immediately | Look at post-exit prices · change a threshold or limit on its own reasoning · promote anything |
| Governor | Whenever they choose | Edit this file · approve rule changes · clear the circuit breaker · fund the account | — |

None of this is technically enforced — every session holds the same tools. Violations are detected via the transcript, not prevented.

A safety defect (duplicate-order risk, a floor breach, a misreported fill) is fixed immediately, then reported — never queued as a proposal.

Any other rule change: edit this file directly, bump the policy version, commit with the reasoning in the commit message.

**Locked evaluation period:** after a rule changes, it should not change again until at least 20 closed trades have run under the new version, except for safety defects, factual corrections, or an explicit governor override. Changing a rule shortly after a loss under it is curve-fitting on a sample size that cannot support the conclusion — say so rather than supplying the change.

---

## Current position

Flat. See `data/trades.csv` for closed trades and `archive/` for prior history.

Hard floor: 50% of deposited cash (§10) — recomputed at each 9:00am check.
