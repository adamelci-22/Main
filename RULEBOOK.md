# Agentic Trading Rulebook

**Canonical source of truth.** Read in full at every checkpoint. Nothing is copied forward between checkpoints — state lives in this file and in `data/`, not in memory.

**Account:** Robinhood `462514035` ("Agentic"), cash account, `agentic_allowed=true`.

**Policy version: 2.1.** Bump on every rule/threshold/limit change; record it in the commit.

---

## 1. Objective

- Losing trades are structural. The goal is positive expectancy, which includes red days.
- Every threshold is a percentage. Dollars appear only where a mechanical constraint forces it (affordability, deposit total).
- Equities and ETFs only — including leveraged and inverse. No options. No short selling (cash account cannot; express bearish views via inverse ETFs bought long).

---

## 2. Daily schedule (ET)

17 checkpoints, plus 7 extended-hours slots only when holding at 4:00pm.

`9:00 · 9:30 · 9:40 · 10:00 · 10:30 · 11:00 · 11:30 · 12:00 · 12:30 · 1:00 · 1:30 · 2:00 · 2:30 · 3:00 · 3:30 · 4:00 · 8:00`

Only if holding at 4:00pm, add: `4:30 · 5:00 · 5:30 · 6:00 · 6:30 · 7:00 · 7:30`.

Cadence is fixed at 30 minutes from 10:00am on, flat or holding. The stall count (§9.1) is measured in checkpoints, so the cadence IS the stall timescale — if the cadence ever changes, re-derive the stall thresholds in the same breath.

| Time | Role | Orders |
|---|---|---|
| 9:00am | Pre-market research | read-only |
| 9:30am | Opening observation | read-only |
| 9:40am | Trading opens — first entry permitted | ✅ |
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
4. Scan for individual stocks clearing the major-move gate (§4) first. Rank sector leadership from pre-market data second, for names where nothing clears that gate but a group is moving together.
5. Confirm settled buying power and unsettled funds. Recompute deposited capital and the floor (§10) — report if either changed.
6. Write a watchlist of at least 5 names: rank the full profiled universe by `mfe_per_stop` first, then mark affordability. Include unaffordable names. Only profiled instruments may be ranked or traded — profile a candidate before shortlisting it if it isn't yet covered.
7. Refresh `data/vol_profile.csv`: pull recent daily bars for the watchlist, recompute median adverse/favourable excursion, rewrite the file. Every risk number derives from it (§6). Commit and push.
8. Refresh the live-context block (§11) against today's tape.

### 9:30am — opening observation, read-only

Test whether the 9:00 thesis survived the open: did pre-market strength hold into real volume, or fade? Check breadth within the leader — one name dragging an ETF is not a sector move. Record the sector proxy's day change; Gate 1 (§4) compares it against the 9:40 reading. Two fixed observations decide Gate 1 — do not add intermediate readings.

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
- Breadth matters for a sector- or index-leveraged trade — the vehicle should reflect a real group move, not one name dragging it. It does not disqualify a single-stock trade: a stock moving alone on its own catalyst is a valid trade in its own right, leveraged or not (see Instrument priority, below). If a single name is doing the moving, trade the name — directly, or through its leveraged wrapper if one exists.
- A catalyst you can name. "It's going up" is not a catalyst — look for one first. Commodities/materials use the trend-structure gate instead (below). Technology and semiconductor names are volatile enough that a clean catalyst often doesn't exist for a real move — look for one, but its absence does not exclude a tech name. If it is the strongest, most stable mover available and nothing more clearly catalyst-backed exists, take it and say plainly that no catalyst was found.
- Trend, not chop. Leveraged ETFs decay in chop.
- Continuation, not prediction.
- No read = no trade.

### Gate 1 — sector must hold a positive trend, 9:30 to 9:40

Applies to a **sector- or index-leveraged trade**, where the thesis is that the sector itself is moving. Record the sector proxy's day change at 9:30 and again at 9:40. All three must hold: positive at 9:30, positive at 9:40, and the 9:40 reading not below the 9:30 reading. Any failure → no entry in that sector's leveraged vehicle.

**Does not gate a single-stock trade.** A stock moving decisively on its own — SMCI ripping while SMH is flat, for example — does not need its sector proxy to pass this. It is evaluated on its own move, and if traded through a leveraged wrapper (SMCX in that example), on Gate 2 instead, which a genuine standalone mover clears easily.

Two fixed observations decide it — no intermediate readings.

### Gate 2 — single-stock leveraged ETF, underlying must lead its sector

Never buy a single-stock leveraged ETF when its underlying is underperforming its sector proxy on the day (both as day change; proxy map in §12). If `underlying_pct < sector_pct` → decline. Does not apply to sector or index leveraged ETFs — those are the group.

### Instrument priority — applies everywhere

Four ranked slots — two of them share a rank, because which one is live depends on what's actually moving:

| Rank | Vehicle | Applies when |
|---|---|---|
| **1** | Individual leveraged stock | A single stock is the mover (major-move gate, below) and a leveraged wrapper for it is affordable |
| **2** | Plain stock, unleveraged | A single stock is the mover, but no leveraged wrapper is available or affordable |
| **2** | Leveraged sector/index ETF | No single name cleared the major-move gate, but a sector or group is genuinely moving together (Gate 1 applies), and the leveraged ETF is affordable |
| **3** | Plain sector/index ETF, unleveraged | A sector is the mover, but the leveraged ETF is not available or affordable |

The two rank-2 rows are parallel, never competing — they are not weighed against each other in the same decision. Which one is live depends entirely on whether the mover turns out to be one stock or a whole sector.

1. **Identify the mover first: individual stock, or sector.** Look for an individual stock making a major, decisive move on its own (major-move gate, below) — that's the first pass, not a fallback for when a sector move can't be found. Only if none clears that gate but a sector or group is genuinely moving together, treat it as a sector move instead.
2. **Within whichever track applies, prefer the leveraged vehicle** if one exists and is affordable as a whole share — it clears Gate 2 first if it's a single-stock leveraged name.
3. **If no leveraged vehicle exists, or none is affordable, do not skip the trade.** Take it unleveraged instead — missing a real move for lack of a leverage wrapper is the wrong trade-off.

### Major-move gate — what qualifies an individual stock as "moving majorly"

Applies to an individual-stock candidate. **Long-only, end to end.** There is no single-stock inverse ETF anywhere in the Universe (§4) — every single-stock name listed is a leveraged-*long* wrapper — so this gate has no mechanism to produce a short or inverse trade, and does not attempt to. An inverse view is expressed through the sector-wide path (Instrument priority step 2, Gate 1, and an inverse sector ETF), never through an individual name.

1. **Magnitude.** Day change ≥ +0.75% from the prior close (up only), measured pre-market at the 9:00 check and re-confirmed live at 9:40. Measure the underlying stock itself, never a leveraged wrapper's move — the wrapper is just the multiple.
2. **Volume confirmation.** Relative volume ≥ 1.75× the recent baseline (10- to 30-session average). A move on light volume is not confirmed.

**Legs 1 and 2 together are sufficient to qualify a candidate on their own.**

3. **Moving-average check — optional, adds weight only, never a trigger by itself.** Once a candidate clears legs 1–2, pull the 50-day and 200-day SMA and check each one's slope over the last 5–10 sessions, only when price is actually testing one of them:
   - MA rising, price bouncing up off it → extra confirmation for the long. Note it as added weight, not a separate entry trigger.
   - MA falling, price rejected downward at it → **not counted at all.** It is not a reason to decline the long, and never a trigger for an inverse or short trade — the check can only ever add confirmation or do nothing, never subtract.
   - Skip if price isn't near either average.

Screen legs 1–2 at 9:00am using the scanner (`% Change` and `Relative volume` filters, or the gainers/losers presets ranked by relative volume). **Re-confirm both fresh at 9:40 before entering** — a 9:00 read goes stale by the open. Check leg 3 against whatever cleared legs 1–2, for extra conviction only.

Fails legs 1–2 → not a major-move candidate. Fall back to a sector-wide read (step 2, above) if one exists, or no trade.

**0.75% and 1.75× are starting defaults, not fixed constants** — not backtested against this account or universe, adjust once there's evidence either way. This bar is intentionally low: it is built to catch momentum early, not to wait until a move is already obvious. It will surface far more candidates than a stricter bar would — the catalyst check, Gate 2 where applicable, and the ranking step downstream carry more of the filtering load as a result.

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

- Preferred window 9:40–11:00am.
- After 11:00am, a new entry must be clearly better than the morning offered, not merely available.
- Never force a trade because the window is closing. No qualifying setup ends the day with no trade.
- One round trip per day exists (T+1, §10).
- Late entries have less time to develop before the mandatory same-day close (§7).

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
- Any liquid high-beta single name with a catalyst, leveraged or not (see Instrument priority, above).

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
| 1 stalled check, price ≥ breakeven | stop → `max(current stop, breakeven)` |
| 1 stalled check, price < breakeven | no stop change (§9.1) |
| 2 stalled checks, either | SELL ALL (§9.1) |
| Any check at or above `target_pct` | SELL |

Up only. Minimum re-placement move: `min_stop_move_pct` from the profile. A structural override (a swing low holding above the trailed level) may be used instead, upward only.

Stop orders are regular-hours only. A stop does not protect against a gap — the only defence for an overnight event is not holding into it, and positions do not carry overnight (§7).

---

## 7. Profit-taking

Target is per-instrument (`target_pct`, §6). At any checkpoint showing a gain at or above it, sell. The target is a ceiling — most trades will not reach it, and the stall ladder (§9.1) closes most positions first.

On reaching target: close the entire position, unless there is named new information supporting more upside. Momentum alone does not qualify. Hitting the target closes the whole position at any share count — no scaling out, no runner.

### Override lifecycle — if new information justifies staying past target

1. Sell half the moment the override is approved, not at the next checkpoint.
2. Raise the stop on the remainder to at least the target price, immediately.
3. Re-justify at every checkpoint, out loud, naming the information again. Silence is expiry — an unrestated override has ended and the remainder gets sold.
4. Sell the remainder the moment any of: the information is exhausted/contradicted/priced in · any §9 exit criterion fires · the ratcheted stop is hit · a pre-commitment fires · the same-day close deadline is reached (§7).
5. One extension per trade — no overriding the override.
6. Log both fills as separate rows in `data/trades.csv`, with the override reason. Report the blended P&L honestly, including if the override earned less than a clean exit at target would have.

Before any partial sell, confirm with `review_equity_order` that a stop on part of a multi-share position leaves the remainder sellable — and remember a clean review is not proof of placement (§13). If refused: cancel the stop, sell half, immediately replace the stop on the remainder, accepting it is briefly unprotected.

### Holding period — every position closes same-day

Every position closes the same trading day it was opened. No overnight or multi-day hold, under any circumstance — this is a cash, day-trading system, full stop. State the intended exit point at entry.

---

## 8. Post-exit review

30 minutes after every exit, check the instrument's price and note the move since the exit. Compare it against the exit price and say plainly whether the exit looks well-timed or early.

If the move suggests a rule is causing early exits or missed continuation, note the observation and the specific rule involved in the report, and suggest a change. This is meant to surface missed opportunities, not to second-guess a single trade in isolation — look for a repeated pattern before proposing a rule change.

The same check applies to a candidate that was declined: 30 minutes after declining, check what it did and note whether the decline was justified.

---

## 9. Exit criteria — any one fires

### 9.1 Momentum stalled

Measured at the checkpoint price only — what happens between checks is ignored.

A stalled check = a checkpoint whose price at that moment failed to exceed `run_high` by more than `stall_threshold_pct`. `run_high` is the highest **checkpoint** price, seeded at the fill, not the highest price traded — it advances only when a check clears the threshold. No volume condition, no bars; one quote per checkpoint is sufficient.

| Stalled checks | Condition | Action |
|---|---|---|
| 1 | price ≥ breakeven (the fill) | stop → `max(current stop, breakeven)` |
| 1 | price < breakeven | no stop change — moving the stop to breakeven here would sit it above the market and force an immediate loss |
| 2 | either | SELL ALL — the market, whatever the result |

SELL means now, not next checkpoint — cancel the resting stop first (a pending sell locks the share), then exit with a marketable limit.

Coupled to the checkpoint cadence: counting checkpoints means the cadence is the stall timescale. If the cadence changes, re-derive the stall thresholds in the same breath.

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
- 24-hour tradability is optionality, not obligation. Never hold just because you can — and positions do not carry overnight regardless (§7).

### Floor

Stop trading and report below 50% of **deposited** cash — not current account value.

`deposited = total_value − all-time realized P&L − unrealized P&L`. Derived, never cached — recompute at the 9:00am check and whenever it changes. The floor does not rise with gains.

### Settlement — T+1 cash account

Sale proceeds are unsettled until the next business day. After an exit, only previously-settled cash is spendable — the account goes flat and **stays flat for the rest of the session.** No same-day rotation.

Buying with settled cash and selling the same day is fine, not a good-faith violation. A GFV is selling something bought with unsettled proceeds — 3 GFVs triggers a 90-day restriction. This cash account is exempt from PDT.

These settlement facts are verified for a **cash** account only. If ever converted to margin, re-verify day-trading and settlement rules from primary sources before the first trade — do not port any assumption here.

---

## 11. Headline check

- 9:00, 9:30 and 10:00am: check headlines broadly — macro, sector, overnight moves. While flat, the previous day's and overnight headlines are what set up today's trades.
- While holding a position, check headlines every hour after that. Only headlines relevant to the position or its thesis — same-day news only, since yesterday's is already in the price.
- If flat past 10:00am, no further scheduled headline check is required.

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

## 15. Rule layers — where a new rule belongs

> **Pending update — content unchanged from the last revision. Flagged for a rewrite; see note to governor.**

| Layer | Scope | Examples |
|---|---|---|
| Universal | Everything, always | Capital protection · order verification · stops ratchet up only · one resting order · loss floor |
| Asset class | Equity · ETF · leveraged/inverse ETF | Daily reset and decay · same-day close · overnight unprotectable |
| Category | Energy · semis · gold miners · crypto · index | Which catalysts matter · which proxy to compare against |
| Instrument | A single ticker | Overnight tradability · spread behaviour · closing-only restrictions |

Place a new rule at the narrowest level where it is actually true.

---

## Current position

Flat. See `data/trades.csv` for closed trades and `archive/` for prior history.

Hard floor: 50% of deposited cash (§10) — recomputed at each 9:00am check.
