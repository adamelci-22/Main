# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), cash, `agentic_allowed=true`.
**Policy version: 3.6.** Bump on every rule/threshold change; record it in the commit.

Nothing carries between checkpoints. State lives in this file and in `archive/trades.csv`, never in memory.

---

## Objective

**Grow with intent.** Target at least 1% daily, with an ambition of roughly 15% a month. Take calculated risks to build and prove the system — this capital is tuition for developing something better, and losing it is an accepted cost of that education, not a failure to be avoided at all costs. As the account grows, hold the same targets but shift toward a lower risk profile: the return goal doesn't shrink, but the risk taken to reach it should.

**The target guides sizing and conviction — it never overrides the gates.** "No read = no trade" (C5) and "never force a trade because the window is closing" (C9) stand above the daily number. A day that ends flat because nothing qualified is a correct outcome, not a shortfall to make up on the next one.

---

## READ MAP — read only your row

Each checkpoint reads **Part A**, plus the parts its row names. Reading more is waste; reading less is a defect.

| Checkpoint | Read | Why |
|---|---|---|
| **9:00** research | A · C · D | Builds the day's candidates |
| **9:30** observation | A · C1 | Watchlist only — no new scan; records the Gate-1 baseline |
| **9:40** entry | A · C | The only slot that may open a position |
| **10:00–3:30** management ×13 | A · B | Holding or flat-with-nothing-to-do |
| **4:00** close | A · B4 · D3 | Exit and report |
| **8:00** arming | A · D | Report and arm tomorrow |

**Part E is reference — pull it only when a rule in A–D sends you there.** Never read it front to back.

---

# PART A — EVERY CHECKPOINT

## A1. Blocking conditions — check before anything else

**Any of these true → no new position may be opened. Not a judgement call.**

| Blocked when | Verify by |
|---|---|
| Loss streak ≥ 3 | Count closed trades in `archive/trades.csv` (E1) |
| Account below 50% of deposited cash | Recompute; never cache (E2) |
| Candidate's risk numbers not computed | No profile → no stop → no trade (B1) |
| An exit already happened today | Cash settlement: flat and **stays flat** all session (E2) |
| Position already open | One position, one resting order (E2) |

**⚠ CURRENT STATE — streak 1 of 3.** Governor cleared the breaker **2026-08-15**; count only trades closed after that date. One loss since: GUSH, closed 2026-08-17 (-$0.0199). The streak is computed from `archive/trades.csv`, the **live append-only log** — new rows go there. **A missing or unreadable file must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`** — a fired trigger reschedules itself ~24h later carrying its original, now-stale prompt.
2. Delete any trigger on a slot about to be armed. Exactly one per slot.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 8:00pm arming checkpoint.** Single point of failure for the whole chain.

A past-due trigger still enabled = a **missed** checkpoint, not a pending one. Do its work now, say it was missed, then delete it.

Do not start work that outlasts the current slot.

## A3. State check

Read from the broker, never assume: position · resting orders · settled cash · unsettled funds.

---

# PART B — HOLDING (management checkpoints)

## B1. Risk numbers — computed just-in-time, per candidate

**Profiled at the moment a candidate clears its gate, never in advance.** Pull ~20–30 daily bars for that one symbol and run:

```
printf '<open>,<high>,<low>\n...' | python3 tools/profile.py SYMBOL
```

It returns every number below. **Never compute these by hand** — a transposed digit becomes a mispriced stop.

```
median adverse    = median of (open − low)  / open      across the window
median favourable = median of (high − open) / open

stop_pct           = clamp(1.5 × median adverse,    2.5%, 7.0%)
target_pct         = clamp(2.0 × median favourable, 1.5 × stop_pct, 12.0%)
breakeven_trigger  = max(median favourable, 0.5 × stop_pct)
trail_pct          = 1.0 × median adverse, below the running high
stall_threshold_pct = clamp(0.15 × median favourable, 0.10%, 1.00%)
min_stop_move_pct   = clamp(0.25 × median adverse,    0.20%, 1.00%)
mfe_per_stop  = median favourable ÷ stop_pct     (the ranking metric, C7)
mfe_to_target = target_pct ÷ median favourable   (>2.5 → target unreachable)
```

No flat constants, and **nothing is pre-computed or cached** — volatility moves, and a profile written last night is a different instrument by this morning. Recompute per candidate, per session.

**Hard ceiling 7%.** A setup needing more room is not a setup. Where 1.5 × median adverse exceeds the cap, the stop is capped and flagged — a warning that noise is wider than the stop, not a disqualification.

Fewer than ~15 sessions available → the sample is thin; treat the numbers as provisional and say so at entry.

## B2. Stops — UP ONLY, NEVER DOWN

- **Never widen.** If the tape needs more room the trade is wrong — be out.
- Only permitted downward change: correcting a factual placement error, stated as such.
- Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print.**
- Minimum re-placement move: `min_stop_move_pct`. A structural level (swing low) may substitute **only if nearer**.
- Stops are **regular-hours only** and do not protect a gap.

### The ratchet — precise, so a cold checkpoint can't misread "gain"

**One `run_high`, shared with B3 — not a second high-water mark.** Same value, same derivation: checkpoint-price only, advances only when a check clears it by more than `stall_threshold_pct` (B3 steps 1–2). A stalled check does not advance it.

**The three stepped stages below are measured against `run_high`, never the live price.** `run_high` only moves up, so once a stage is reached it cannot un-reach itself on a pullback — that is what "up only" requires. Each is a one-time jump, evaluated fresh every checkpoint, applied only if it raises the stop:

| Stage | Trigger (on `run_high`) | Stop goes to |
|---|---|---|
| 1 — entry | — | `fill × (1 − stop_pct)` |
| 2 — half-risk | `(run_high − fill) ÷ fill` ≥ `breakeven_trigger ÷ 2` | `fill × (1 − stop_pct ÷ 2)` |
| 3 — breakeven | `(run_high − fill) ÷ fill` ≥ `breakeven_trigger` | `fill` (breakeven) |
| 4 — trail | past stage 3 | `run_high × (1 − trail_pct)` — **the only continuous stage**, recomputed every checkpoint as `run_high` climbs |

**Worked example — AGQ's actual profiled numbers, fill at $100.00:**

```
median adverse = 1.45%   median favourable = 1.65%

stop_pct          = clamp(1.5 × 1.45, 2.5, 7.0)        = 2.50%
target_pct        = clamp(2.0 × 1.65, 1.5 × 2.50, 12.0) = 3.75%
breakeven_trigger = max(1.65, 0.5 × 2.50)               = 1.65%
trail_pct         = 1.0 × 1.45                          = 1.45%
```

| Stage | `run_high` reaches | Stop becomes |
|---|---|---|
| 1 — entry | $100.00 (fill) | $100.00 × (1 − 0.0250) = **$97.50** |
| 2 — half-risk | $100.00 × (1 + 0.0165÷2) = **$100.83** | $100.00 × (1 − 0.0125) = **$98.75** |
| 3 — breakeven | $100.00 × (1 + 0.0165) = **$101.65** | **$100.00** (fill) |
| 4 — trail, e.g. `run_high` runs to $103.00 | — | $103.00 × (1 − 0.0145) = **$101.51** |
| target | live price reaches $100.00 × (1 + 0.0375) = **$103.75** | **SELL ALL** — B4, overrides every stage |

**The stall consequences below are a separate, faster-acting check against the *live* price, not `run_high`** — they can fire before stage 3 is reached by the ramp. **Time-gated at 12:00pm ET**, evaluated by the checkpoint's own clock time, not entry time:

**Before 12:00pm ET — more room to develop.** SELL ALL needs **3** stalls, not 2, and stalls 1–2 force **no stop move at all**; the stop can only rise via the percentage-based ratchet stages above. A pause in the first couple hours doesn't trigger an early breakeven lock — it only has to not go on for three checks straight. Trade-off, stated plainly: this accepts more downside room in exchange for not shaking a real move out on its first pause.

| Stall count, before noon | Action |
|---|---|
| 1 | No stop move. Only the ratchet stages above can raise the stop. |
| 2 | No stop move. Same. |
| 3 | **SELL ALL — complete.** Overrides every stage above, no exceptions. |

**At or after 12:00pm ET — the tighter rule.** SELL ALL needs **2** stalls, and the first one locks in profit immediately:

| Stall count, noon or later | Live price vs. fill | Action |
|---|---|---|
| 1 | at or above fill | Stop moves to **whichever is higher: breakeven, or the ratcheting stop's current level** (`max(breakeven, ratchet stop as of this checkpoint)`). Never a third value — just those two, compared, higher one wins. Safe, the live price is still above it. |
| 1 | below fill | **No move.** Moving the stop to breakeven would place it above the live price, forcing an immediate sell — that is rejected, not executed early. Re-check next checkpoint. |
| 2 | either | **SELL ALL — complete.** Overrides every stage above, no exceptions. |

**Crossing noon mid-hold:** apply whichever table matches the *current* checkpoint's clock time to the stall count as derived cold at that same checkpoint (B3) — don't backdate which regime a past stall happened under. A count that's already at 2 when a 12:00 checkpoint runs means SELL ALL immediately under the now-current rule; a count of 1 or 2 left over from the morning is simply read against the afternoon table from that point on.

**Any checkpoint where the live price ≥ `target_pct` → SELL ALL**, overriding everything above (B4).

## B3. Exits — any one fires

### Stall — measured at the checkpoint price only

A **stalled check** = a checkpoint whose price failed to exceed `run_high` by more than `stall_threshold_pct`. `run_high` is the highest **checkpoint** price, seeded at the fill — not the highest price traded. No bars, no volume condition; one quote is enough.

**Derive cold every time — nothing is remembered:**
1. Read one quote.
2. `price > run_high × (1 + stall_threshold_pct/100)` → **progressed**: count to 0, `run_high` to this price.
3. Otherwise → **stalled**: count increments.
4. Total = consecutive stalled checks ending at the most recent.

**Before 12:00pm ET:** stalls 1–2 do nothing to the stop; **3 stalls → SELL ALL.** **At or after 12:00pm ET:** 1 stall moves the stop to whichever is higher — breakeven, or the ratcheting stop's current level; **2 stalls → SELL ALL.** Full detail and the noon-crossing rule in B2 — whatever the result.

**SELL means now, not next checkpoint.** Cancel the resting stop first — a pending sell locks the share — then exit on a marketable limit.

State the count, every checkpoint price since entry, the threshold and the verdict, in every report while holding.

No midday exclusion. Every check counts.

> Counting *checkpoints* means the cadence **is** the stall timescale. Change the cadence and you must re-derive the stall thresholds in the same breath.

### Other exits

- **Reversal** — broke the level or VWAP that justified entry, or the sector rolled over. The level must have been **named at entry** or the claim is unfalsifiable.
- **Risk/reward flipped** — small remaining upside against a large distance to the stop.
- **Unwanted event approaching** — earnings or macro data not intended to be held through.
- **Approaching the same-day close deadline** with the move finished.

Not on one red candle, midday noise, or impatience.

### Pre-commit — end every holding report with it

Name the **specific, falsifiable** condition that would exit at the next checkpoint, with instrument and direction. Then honour it. To override, say explicitly that you are overriding a pre-commitment and name the **new** information. *"It looks like it's turning back up" does not qualify.*

## B4. Profit-taking

At any checkpoint showing a live-price gain ≥ `target_pct` → **sell the entire position.** No scaling out, no runner, at any share count. Target is a ceiling; most trades exit on the stall ladder first.

**`target_pct` is variable, not a fixed number — computed once, per candidate, at entry (B1: `clamp(2.0 × median favourable, 1.5 × stop_pct, 12.0%)`), and it does not change for the life of that trade.** A different candidate gets a different target; a fresh `tools/profile.py` run on the same symbol mid-trade would likely produce a different number too, but the trade holds the value locked in at entry, stated at entry (C8) — recomputing it mid-hold would make the exit a moving target.

**Every position closes the same trading day it was opened. No overnight hold, ever.** State the intended exit at entry.

> **Override (dormant — needs 2+ shares, currently unreachable at one share/position).** Staying past target requires *named new information*; momentum does not qualify. If invoked: sell half immediately, raise the remainder's stop to ≥ target, re-justify aloud every checkpoint (silence = expiry), sell the remainder when the information dies or any exit fires. One extension per trade. Log both fills; report blended P&L honestly including when the override lost money.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(While flat: 9:00, 9:30 and 10:00 only. Nothing scheduled after 10:00 if still flat.)*

---

# PART C — ENTRY (9:00 · 9:30 · 9:40 only)

> **No position may be opened outside 9:40–4:00, and only one round trip per day exists.** Spend it well, not merely spend it.

## C1. Gate 1 — the sector must hold, 9:30 → 9:40

**9:30 is scoped to the 20-name watchlist only — no new market scan.** Record the day change of the **5 sector proxies** (feeds the Gate 1 test below) and note whether each of the **15 individual candidates** is still holding its move. That's an observational check, not a formal re-run of C3 — the formal re-confirmation of C3's legs happens live at 9:40.

Applies to a **sector- or index-leveraged trade** only. Record the sector proxy's day change at **9:30** and again at **9:40**. All three must hold:

1. positive at 9:30, **and**
2. positive at 9:40, **and**
3. the 9:40 reading **not below** the 9:30 reading.

Any failure at 9:40 → no entry **at 9:40** in that sector's leveraged vehicle.

**Late entry, any checkpoint after 9:40:** the door isn't permanently closed by a 9:40 failure. At any later checkpoint, entry is still allowed if the sector proxy's live reading at that checkpoint is **strictly higher than the 9:30 baseline** — not merely "not below" (that looser bar is 9:40's own test, leg 3 above; a later checkpoint must clear the higher bar of actually exceeding 9:30, not just matching or nearly matching it). This is the resolution to the gap flagged 2026-08-18: recovered sector strength after 9:40 is tradeable, but only past a real, higher threshold — never on a bare return to the 9:30 level.

**Two fixed observations (9:30, 9:40) decide the 9:40 pass/fail — never add intermediate readings there.** The late-entry test above is the one exception, evaluated fresh at whichever checkpoint is asking, using that checkpoint's own live reading against the fixed 9:30 baseline.

**Does not gate a single-stock trade.** A stock moving decisively on its own does not need its sector to confirm; it is judged on its own move, and on Gate 2 if traded leveraged.

## C2. Gate 2 — a leveraged single-stock ETF's underlying must lead its sector

Both as day change; proxy map in **E3**. If `underlying_pct < sector_pct` → **decline.** Buying the laggard with leverage turns a correct sector call into a losing trade. Does not apply to sector or index vehicles — those *are* the group.

## C3. Major-move gate — what qualifies an individual stock

**Long-only, end to end.** Every single-stock name in the universe is a leveraged-*long* wrapper, so this gate cannot produce a short or inverse trade and does not try. Inverse views go through the sector path (C1 + an inverse sector ETF).

1. **Magnitude** — day change **≥ +0.75%** from prior close, up only. Measure the *underlying stock*, never the leveraged wrapper; the wrapper is just the multiple.
2. **Volume** — relative volume **≥ 1.25×** the 10–30 session baseline. A move on light volume is not confirmed.

**Legs 1–2 together are sufficient to qualify a candidate.**

3. **Moving average — optional, adds weight only, never a trigger and never a veto.** When price is actually testing the 50- or 200-day SMA, check its slope over 5–10 sessions. Rising MA + bounce up → extra confirmation for the long. Falling MA + rejection → **not counted at all**, neither as a reason to decline nor as an inverse trigger. Skip if price is not near either average.

Screen legs 1–2 at **9:00** with the scanner (`% Change` + `Relative volume`, or the gainers preset ranked by relative volume). **Re-confirm both live at 9:40** — a 9:00 read is stale by the open.

Fails legs 1–2 → not a major-move candidate; fall back to a sector read or no trade.

> 0.75% / 1.25× are **starting defaults, not backtested constants.** The bar is deliberately low to catch momentum early, so it surfaces many candidates — the catalyst check, Gate 2 and ranking carry the filtering load downstream.

## C4. Instrument priority

| Rank | Vehicle | When |
|---|---|---|
| **1** | Individual leveraged stock | A single stock is the mover (C3) and its wrapper is affordable |
| **2** | Plain stock | Single stock is the mover, no affordable wrapper |
| **2** | Leveraged sector/index ETF | No single name cleared C3, but a group is moving together (C1 applies), wrapper affordable |
| **3** | Plain sector/index ETF | Sector is the mover, no affordable leveraged vehicle |

The two rank-2 rows are **parallel, never competing** — which is live depends only on whether the mover is one name or a group.

1. **Identify the mover first** — individual stock, then sector. Individual is the first pass, not a fallback.
2. **Prefer the leveraged vehicle** within whichever track applies.
3. **No leveraged vehicle affordable → take it plain.** Missing a real move for lack of a wrapper is the wrong trade-off.

## C5. Signals

- **Leadership ranked from data.** Never default to something you have been watching.
- **Breadth** applies to a *sector* trade — the vehicle should reflect a real group move. It does **not** disqualify a single-stock trade.
- **A catalyst you can name.** "It's going up" is not one. *Exceptions:* commodities/materials use C6 instead; **tech and semis** are volatile enough that a clean catalyst often does not exist — look for one, but its absence does not exclude the name. Take it and say plainly none was found.
- **Trend, not chop.** Leveraged ETFs decay in chop.
- **Continuation, not prediction.**
- **No read = no trade.** A flat day is a correct outcome, never a quota to make up.

## C6. Commodities and materials — replaces the catalyst requirement

All three legs must hold: **(1)** multi-session higher highs *and* higher lows · **(2)** confirmation from the related complex (metal vs miners, crude vs E&P) · **(3)** pullback not breakdown — inside the prior session's range, above its low.

A replacement, not a relaxation — every other rule still binds.

## C7. Ranking

1. Rank candidates by `mfe_per_stop` (B1, computed per candidate), ignoring price.
2. **Then** mark what settled cash reaches as a whole share.
3. **Then** apply the gates and pick from survivors.

Never filter by price first. State the ratio for the **top two** candidates at entry, and name the top-ranked name if it was unaffordable, **with the dollar gap** — that number is what reports whether capital is the binding constraint. Deployment percentage is the last tiebreaker, never a filter. `mfe_to_target` above ~2.5× means the target is effectively unreachable — say so at entry.

If the capital base or the thesis moved, the 9:00 shortlist is **void** — re-rank from the live tape.

## C8. Order execution

**Whole shares only.** A fractional position cannot carry a resting stop. Unaffordable whole → unavailable; take the next candidate or no trade.

Before placing, confirm every A1 blocking condition is clear, plus: stop present and inside the 7% cap and matching the profile · affordability against **settled** cash, not account value · order type · C2 if single-stock leveraged.

Then:
- `review_equity_order` first — **a clean review proves nothing about placement** (E4).
- **Marketable limit, never plain market.**
- **Verify the fill from the order response.** Never report an unconfirmed fill.
- **Place the protective stop immediately after the fill.**
- Report slippage against the intended price.
- State at entry: fill · stop price and % · target % · breakeven trigger · trail · `mfe_per_stop` for the top two · intended exit · the falsifiable pre-commit for the next checkpoint.

## C9. Timing and selection

- **Preferred window 9:40–11:00.**
- After 11:00 a new entry must be **clearly better** than the morning offered, not merely available. Boredom is not a signal. For a sector-leveraged trade this is concrete, not a feeling: C1's late-entry clause requires the proxy strictly above its 9:30 baseline.
- Never force a trade because the window is closing.
- Verify `all_day_tradability` before entering.
- **Price the spread:** read the actual bid/ask, **double it** for the round trip, subtract from the expected move — take it only if it still clears the target with room.
- Check the price before building a thesis. A candidate you cannot buy is not a candidate.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid (ET)

`9:00 · 9:30 · 9:40 · 10:00 · 10:30 · 11:00 · 11:30 · 12:00 · 12:30 · 1:00 · 1:30 · 2:00 · 2:30 · 3:00 · 3:30 · 4:00 · 8:00`

Add `4:30 · 5:00 · 5:30 · 6:00 · 6:30 · 7:00 · 7:30` **only if holding at 4:00pm** — a flat book never arms them. Extended hours: limit orders only, no new positions. **7:30pm is the last actionable close.**

Cadence is 30 minutes from 10:00 on. ET → UTC: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5. Skip market holidays — **verify the calendar, never assume.** On an early close, end the grid there and skip extended hours. **Friday arms Monday**, not the weekend.

Runs indefinitely until the governor pauses it. Never stop on your own initiative.

### Cadence reduction — flat and idle

If flat at **11:00** with no candidate that cleared C3 or C1, drop to **hourly** (12:00 · 1:00 · 2:00 · 3:00 · 4:00) and delete the half-hour slots. The preferred window has closed and the bar for a late entry is already "clearly better" — half-hourly checks past that point produce nothing but cost.

Resume the 30-minute grid immediately on any entry.

### Early shutdown

Flat · no resting orders · **and** no entry possible (buying power short, or an exit already spent the day's round trip) → delete remaining intraday checkpoints. **Keep exactly three: 4:00 report, 8:00 arming, 8:20 backup.**

Flat at 4:00 → delete 4:30–7:30 regardless.

## D2. 9:00am research — standard work

1. **Headlines** — macro, geopolitical, overnight.
2. **Pre-market prices** across the universe and yesterday's watchlist.
3. **Earnings reactions** from last night's after-close reporters.
4. **Scan for individual movers clearing C3 first.** Rank sector leadership second, only where nothing cleared C3 but a group is moving.
5. **Confirm settled buying power and unsettled funds.** Recompute deposited capital and the floor; report either if changed.
6. **Write the watchlist — 20 names: 5 sector/index vehicles + 15 individual stocks.** Profile each just-in-time (B1) and rank by `mfe_per_stop`; mark affordability second, never first. Include unaffordable names — they measure what capital is costing. The 5 sectors feed C1 (Gate 1); the 15 individuals feed C3 (major-move gate) and C4's rank-1/rank-2 tracks.
7. **Refresh the live-context block (E5).** Commit and push.

## D3. Reporting

- **Losses as plainly as gains.** No spin. Never claim edge from a small sample.
- **Verified fills only.** P&L in dollars, percent **and R**. Slippage both sides.
- **Correct your own errors promptly**, including ones that look bad.
- **Most checkpoints are non-events — stay silent.** No "checked, nothing to do."
- **Report immediately:** entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a notable setup declined.
- **A no-trade day gets no evening message.**
- **Friday 8:00pm always reports**, trades or not — balance, every trade, loss-streak count, what was declined and why, any rulebook change. The guaranteed heartbeat.

**At exit, append one row to `archive/trades.csv`** — the live append-only log. Compute `r_multiple = (exit% − entry%) ÷ initial_stop_pct` **now**, while the entry stop is known — it cannot be reconstructed later. Set `counts_toward_streak` and `counts_toward_expectancy` (`no` only for a mechanical abort or a funded execution test) and say why in `notes`. **Append-only — never edit a past row**; a mistake gets a correcting row.

**Measurement:** expectancy per trade in R is primary. `Expectancy = (win rate × avg winner R) − (loss rate × avg loser R)`. Win rate and avg winner/loser are descriptive only, never pass/fail. Exclude `counts_toward_expectancy=no` rows and name them. **State the effective sample size, not the row count.**

## D4. Post-exit review — the improvement loop

**30 minutes after every exit**, check the price and say plainly whether the exit was well-timed or early. Same for a candidate declined.

If a pattern suggests a rule is causing early exits or missed continuation, name the rule and propose the change. **Look for a repeated pattern — never rewrite a rule from one trade.** Changing a rule right after a single loss under it is fitting noise, not learning.

---

# PART E — REFERENCE (pull on demand)

## E1. Circuit breaker

**3 consecutive losing closed trades → stop entering until the governor clears it.**

A loss is any negative realised P&L, however small. Consecutive **closed trades**, not days — a winner anywhere resets to zero. Rows marked `counts_toward_streak=no` are excluded (a mechanical abort is not a trade). **Compute from the trade log, never from memory.**

**Counting starts after the most recent governor clearance** (dated in A1). Trades closed before it are history, not streak. The log stays append-only — a clearance is recorded as a date in A1, never by editing or deleting a past row.

Pausing entries never means pausing the system — keep managing any open position, keep every checkpoint, keep reporting, **keep arming.**

A −25% drawdown from peak is a **flag**, not a brake: report it loudly, keep trading. The hard halt is the floor.

## E2. Account mechanics

- **Floor: stop trading below 50% of *deposited* cash** — not account value. `deposited = total_value − all-time realized P&L − unrealized P&L`. Derived, never cached. **The floor does not rise with gains.**
- **T+1 settlement.** Sale proceeds are unsettled until the next business day. After an exit the account is flat and **stays flat for the session** — no same-day rotation. Buying with *settled* cash and selling the same day is fine; selling something bought with *unsettled* proceeds is a GFV, and 3 GFVs = 90-day restriction. This cash account is **PDT-exempt**.
- **No short selling** — a cash account cannot. Bearish views go through inverse ETFs bought long.
- **One resting order per position** — a pending sell locks the share, so a stop and a take-profit cannot coexist.
- 24-hour tradability is optionality, never obligation.
- **Settlement facts are verified for a *cash* account only.** If ever converted to margin, re-verify from primary sources before the first trade — port nothing.

## E3. Sector proxy map

| Instrument | Underlying → Proxy |
|---|---|
| SOXL · SOXS · USD | → SMH |
| NVDL · NVDX · NVDU | NVDA → SMH |
| AMDL | AMD → SMH |
| MUU | MU → SMH |
| TSMX · TSMU | TSM → SMH |
| SMCX | SMCI → SMH |
| AVGX | AVGO → SMH |
| TQQQ · SQQQ · FNGU · BULZ · TECL | → QQQ |
| SPXL · UPRO · SPXS · SDOW · UDOW | → SPY |
| TNA · TZA | → IWM |
| GUSH · ERX · ERY · NRGU · DRIP · OILU · OILD | → XLE |
| UCO · SCO | → USO |
| BOIL · KOLD | → UNG |
| NUGT · DUST · GDXU · JNUG · JDST | → GDX |
| AGQ · ZSL · SIL · SILJ | → SLV |
| UGL · GLL | → GLD |
| LABU | → XBI |
| UYM · SMN | → XLB |
| COPX · CPER | → copper |
| URA · URNM | → uranium |
| YINN · YANG | → FXI |
| KORU | → EWY |
| TSLL | TSLA → QQQ |
| CONL | COIN → IBIT |
| MSTX | MSTR → IBIT |
| RIOT · MARA · CLSK · BITX · BITU · ETHU · ETHT | → IBIT (crypto) |
| UVIX · VXX | → VIX |

Not on the map → name the closest unleveraged proxy and say it was chosen ad hoc.

### Known leveraged vehicles

**Index** TQQQ · SPXL · UPRO · TNA · UDOW — **Sector** SOXL · TECL · GUSH · ERX · FNGU · BULZ · LABU · NUGT · GDXU · NRGU · YINN · KORU · USD — **Single-stock** NVDL · NVDX · TSLL · CONL · MSTX · SMCX · MUU · AMDL · TSMX — **Inverse** SQQQ · SOXS · SPXS · SDOW · TZA · DUST · ERY · YANG · ZSL · JDST · SCO · DRIP · KOLD — **Commodity/materials** AGQ · UGL · GLL · JNUG · SIL · SILJ · UCO · BOIL · OILU · OILD · UYM · SMN · COPX · CPER · URA · URNM · LIT · REMX · SLX — **Crypto** BITX · BITU · ETHU · ETHT · RIOT · MARA · CLSK — **Volatility** UVIX · VXX, event/intraday only, never a hold.

This list is a **convenience index, not a boundary** — any liquid name may be traded (C4). Equities and ETFs only: **no options**, no short selling.

## E4. Capability verification

**A capability is verified only by an order response or a successful call.** Never by a review, documentation, or inference from a similar case. A refusal is evidence too — record the exact error string verbatim. Make the smallest call that proves the primitive before the one that depends on it.

Never commit capital or write policy on a mechanism not seen to succeed.

## E5. Live context — dated, refreshed at 9:00, replaced wholesale

A slot, not a fixture. When the driver stops mattering, replace it entirely — its triggers were specific to it. **Stale context asserted confidently is worse than none.**

*As of Aug 19 2026, ~9:08am ET (premarket):* **Mixed, no dominant driver — semis/tech still soft after yesterday's rout, but gold miners are the real story.** Bond yields and oil remain elevated, pressuring valuations broadly (30-year Treasury yield near a two-decade high per overnight coverage). FOMC minutes and earnings from ADI, TJX, LOW, TGT and EL land today — none of that maps to anything in this watchlist. **Gold is the genuine catalyst:** bullion is at/near $4,400/oz, GDX has surged ~21% over five sessions on heavy retail inflows ($419M into GDX in August alone) hitting decade-highs — a real, sourced, multi-day story, not a single headline. Broadcom (AVGO) is down hard on valuation reassessment ahead of its Sept 2 earnings, unrelated to the gold move. **Caution on secondary web sources today:** one search result claimed MU traded at $921.63 overnight (down ~2%), which directly contradicts the broker's own premarket quote (+2.1%, $960.86) — treating that as noise and trusting the broker feed, not the web article, for anything price-specific.

**Premarket individual moves** (vs. adjusted previous close, broker quotes): MU **+2.14%**, MSTR +1.95%, TSM +1.10%, COIN +1.10%, NVDA +0.62%, AMD +0.61%, AMZN +0.64%, META +0.30%, TSLA +0.17%, AAPL +0.05%, GOOGL −0.41%, PLTR −0.42%, MSFT −0.55%, SMCI −1.28%, **AVGO −3.09%** (worst, valuation-driven per above). MU is the standout — real memory-sector tailwind (SK Hynix +3.9% premarket on a buyback) plus a sharp reversal off yesterday's -7% session.

**Sector proxies (premarket, informational only — not the C1 baseline):** SPY +0.36% · QQQ +0.38% · SMH +1.14% · XLE +0.39% · **GDX +4.55%** — gold miners far and away the leader, consistent with the sourced rally above.

**20-name watchlist**, re-profiled just-in-time (B1) fresh this morning on 38 sessions through Aug 18 close (`tools/profile.py`, never reused from yesterday) — ✓ = affordable as 1 whole share against **$61.99** buying power (unchanged, still flat, verified via `get_portfolio`):

*15 individuals:*
| Rank | Symbol | Underlying | Premarket chg | mfe_per_stop | Price | Afford |
|---|---|---|---|---|---|---|
| 1 | MSTX | MSTR | +1.95%* | 0.918 | $7.98 | ✓ |
| 2 | PLTR | — | −0.42% | 0.901 | $171.60 | ✗ |
| 3 | TSLL | TSLA | +0.17%* | 0.879 | $8.51 | ✓ |
| 4 | SMCX | SMCI | −1.28%* | 0.744 | $12.10 | ✓ |
| 5 | CONL | COIN | +1.10%* | 0.714 | $4.01 | ✓ |
| 6 | MUU | MU | **+4.42%** | 0.663 | $31.50 | ✓ |
| 7 | NVDL | NVDA | +0.62%* | 0.614 | $35.46 | ✓ |
| 8 | TSMU | TSM | +1.93%* | 0.539 | $67.19 | ✗ ($5.20 short) |
| 9 | AMDL | AMD | +0.61%* | 0.511 | $52.78 | ✓ |
| 10 | META | — | +0.30% | 0.511 | $545.70 | ✗ |
| 11 | MSFT | — | −0.55% | 0.451 | $479.07 | ✗ |
| 12 | GOOGL | — | −0.41% | 0.432 | $342.83 | ✗ |
| 13 | AMZN | — | +0.64% | 0.431 | $261.22 | ✗ |
| 14 | AVGX | AVGO | **−5.65%** | 0.391 | $42.79 | ✓ |
| 15 | HD | — | n/a (no live quote pulled) | 0.353 | ~$337+ | ✗ |
| — | AAPL | — | +0.05% | 0.350 | $310.17 | ✗ |

*Wrapper premarket % shown as the underlying's own move (proxy — the ETN itself gapped further, e.g. MUU +4.42% vs MU's +2.14%, leverage as expected). AVGX moved further than AVGO (−5.65% vs −3.09%) for the same reason.

*5 sector/index vehicles* (feed C1; leveraged form noted for C4 rank-2/3):
| Symbol | Proxy | Premarket chg | Leveraged form | mfe_per_stop | Price | Afford |
|---|---|---|---|---|---|---|
| GDX | Gold miners | **+4.55%** | NUGT | 0.673 | $171.37 | ✗ ($109 short) |
| SMH | Semis | +1.14% | SOXL | 0.521 | $134.18 | ✗ |
| XLE | Energy | +0.39% | GUSH | 0.974 | $43.90 | ✓ |
| QQQ | Tech/index | +0.38% | TQQQ | 0.487 | $73.47 | ✗ |
| SPY | Broad market | +0.36% | SPXL | 0.469 | $292.47 | ✗ |

**GUSH ranks #1 of all 21 profiled instruments (0.974) and is the only sector-leveraged vehicle affordable today** — same instrument as both prior sessions, though today's driver (modest energy strength) is far weaker than yesterday's Hormuz escalation; no fresh energy catalyst overnight. **The real story — gold/GDX — has no affordable vehicle:** NUGT at $171.37 is more than 2.7x the account's buying power, so the week's biggest, most sourced move is untradeable here regardless of how C1 reads at 9:30/9:40. Top-ranked affordable individual: **MSTX (0.918)**, MSTR premarket-strong (+1.95%) — plausible thesis, unconfirmed until 9:40. Also notable: **MUU (0.663, rank 6)** is up a real +4.42% premarket on the memory/SK Hynix tailwind, well clear of C3's +0.75% bar if it holds into the open. **Nothing decided yet — re-confirm everything live at 9:30/9:40 per C1/C3/C7; this is the 9:00 shortlist, void if capital or thesis moves.**

**Stale for any later session; refresh before trusting.**

### C1 Gate-1 baseline — formal 9:30 reading

**Recorded 9:30 checkpoint, read time 2026-08-19T13:31:02Z (~9:31am ET).** Compare against the 9:40 reading; two fixed observations decide C1, no intermediate reads.

| Proxy | 9:30 day change | vs. premarket |
|---|---|---|
| GDX | **+6.487%** | strengthened sharply (+4.55%→+6.49%) — the standout, but NUGT is unaffordable regardless |
| SMH | +0.709% | weakened somewhat (+1.14%→+0.71%) |
| QQQ | +0.343% | ~flat |
| SPY | +0.374% | ~flat |
| XLE | +0.267% | weakened (+0.39%→+0.27%) |

**Unlike yesterday, all five sector proxies are positive at 9:30** — a genuinely different tape (broad, mild strength vs. yesterday's broad risk-off). Leg 1 ("positive at 9:30") passes for every proxy; all five stay alive into 9:40, though only XLE (via GUSH) is actually affordable and tradeable if C1 completes — GDX/SMH/QQQ/SPY all gate to unaffordable leveraged forms (NUGT/SOXL/TQQQ/SPXL).

**Individual candidates — wrapper prices at 9:30, holding vs. premarket:**

*Strengthened or flipped positive:* MSTX +4.10% (MSTR premarket +1.95%, extended), CONL +4.07% (COIN +1.10%→+4.07%), MUU +3.02% (MU +2.14%→+3.02%, still clear of C3's bar), TSMU +2.65% (TSM +1.10%→+2.65%), NVDL +2.09% (NVDA +0.62%→+2.09%), TSLL +1.89% (TSLA +0.17%→+1.89%), PLTR +1.10% (**flipped from −0.42% premarket**), AMZN +0.87%, AAPL +0.17%.

*Weakened or flipped negative:* AVGX −4.48% (AVGO −3.09%→−4.48%, still the weakest by far), META −0.60% (**flipped from +0.30% premarket**), AMDL −1.61% (**flipped from +0.61% premarket**), SMCX −1.95% (SMCI −1.28%→−1.95%), GOOGL −0.31%, MSFT −0.15% (both still negative, marginal change).

**Several individual candidates (MSTX, CONL, MUU, TSMU, NVDL, TSLL) are already well past C3's +0.75% magnitude bar at 9:30** — informational only, C3's formal re-confirmation is the 9:40 live check, not this reading. AMDL and META flipping negative removes them from contention unless they recover. This is a markedly more bullish, broader-based morning than yesterday across both the sector and individual sides — the opposite problem from Tuesday (too little qualified) may be too many qualifying, which makes C4/C7's ranking discipline the real work at 9:40.

### 9:40 entry — GUSH, sector-leveraged (C4 rank 2), individual path shut out entirely on volume

**A1 confirmed fresh: no positions, no resting orders, streak 1/3, floor unaffected.**

**C3 re-confirmed live via the updated scanner (0.75%/1.25× filters, verified in `filters_applied`): 0 of 15 watchlist candidates qualify.** The scan returned only 4 matches market-wide (RDAC, YJ, TNON, MRNA — none on this list). Every one of yesterday's promising 9:30 movers (MSTX, CONL, MUU, TSMU, NVDL, TSLL) had real price legs but **none cleared the relative-volume leg** this early in the session — price without confirming volume, exactly what leg 2 exists to filter out. **No individual candidate today, full stop.**

**C1 re-checked at 9:40 (read time ~2026-08-19T13:42:00Z):** XLE +0.683% (up from +0.267% at 9:30 — strengthens, passes all three legs). GDX +7.160% (up from +6.487% — also passes, but stays untradeable, no affordable vehicle at any C4 rank: NUGT $171+, GDX itself $95.32, both over the $61.99 buying power). SPY +0.248% (below 9:30's +0.374% — fails leg 3). QQQ −0.017% (flipped negative — fails). SMH −0.582% (flipped negative — fails). **XLE is the only proxy that both passes C1 and gates an affordable vehicle.**

**C6 checked in place of a named catalyst** (energy/materials replacement gate): (1) multi-session higher highs/higher lows — GUSH closes $41.27→$42.61→$43.50 over the last three sessions, lows $40.70→$41.055→$42.17, highs $42.155→$42.665→$43.75, clean uptrend. (2) Related-complex confirmation — USO (crude) +0.485% today, same direction. (3) Not a breakdown — today's price ($44.20+) is trading **above** the entire prior session's range (high $43.75), a continuation, not a pullback threatening the low. All three legs hold.

**C4/C7:** rank 2 (leveraged sector ETF, no individual cleared C3) is the only populated rank. Single surviving candidate, so no ranking dispute — `mfe_per_stop` 0.974 stated for the record, `mfe_to_target` 2.00 (comfortably under the 2.5 unreachable-target flag).

**Entry executed:** BUY 1 GUSH, marketable limit $44.25 (ask was $44.22 at review), **filled $44.25** (order `6a85b2f9`, verified via order response, 09:43:21 ET). Slippage: $0.03 above the review-time ask, ordinary marketable-limit cost. Spread priced before entry: bid/ask $44.16/$44.22 (4¢ wide), round-trip ~8¢ against a $2.16 expected move to target — trivial. `all_day_tradability` confirmed tradable beforehand.

**Protective stop placed immediately, confirmed resting** (order `6a85b312`, state `confirmed`): stop_market, $43.14 (stage 1 = fill × (1 − 2.50%)).

**Full ratchet schedule for this fill ($44.25), from this morning's fresh profile (stop_pct 2.50%, target_pct 4.87%, breakeven_trigger 2.43%, trail_pct 1.38%, stall_threshold 0.37%, min_stop_move 0.34%):**

| Stage | `run_high` reaches | Stop becomes |
|---|---|---|
| 1 — entry | $44.25 (fill) | **$43.14** ← resting now |
| 2 — half-risk | $44.79 | $43.70 |
| 3 — breakeven | $45.33 | $44.25 (fill) |
| 4 — trail | past stage 3 | `run_high × (1 − 1.38%)`, recomputed every checkpoint |
| target | $46.41 | **SELL ALL** |

**Pre-commit for 10:00:** derive the stall count cold from checkpoint prices per B3; before noon, 3 stalls needed to sell and stalls 1–2 don't move the stop (only the ratchet stages above can). No individual-stock re-entry considered today — C3 is shut out market-wide, not just for this list, so nothing to re-check there barring a fresh scan.

### 10:00 management checkpoint — 1 stall, no stop move, position and stop confirmed

**A1 confirmed fresh: position 1 GUSH @ $44.25 avg cost, stop resting confirmed** (`6a85b312`, state `confirmed`, $43.14).

**Stall derivation, cold, per B3:** `run_high` seeded at fill $44.25. Checkpoint price at 10:00 (read ~2026-08-19T14:01:06Z): **$44.00**. Progression threshold: $44.25 × 1.0037 = $44.41. $44.00 is below both `run_high` and the threshold → **stalled**. **Count: 1.** Before noon, 1–2 stalls do nothing to the stop — only the percentage ratchet stages can move it, and `run_high` hasn't advanced past $44.25, so no stage has triggered. **Stop stays at $43.14, unchanged.**

**B5 headlines:** same driver, still escalating — Brent $91.52 (+0.55% today, +4.5% over three sessions), a fourth straight up day. A vessel was reportedly attacked leaving the Strait of Hormuz with a reported crew casualty; Trump confirmed no talks planned and the naval blockade stays in place. The fundamental thesis behind this trade is intact and, if anything, strengthening — today's small pullback in GUSH itself ($44.25→$44.00) reads as normal noise against that backdrop, not a reversal.

**Pre-commit for 10:30:** re-derive the stall count cold against `run_high` $44.25 and the same $44.41 progression threshold. 2 consecutive stalls still does nothing before noon (3 needed to sell). No stop move expected unless price clears $44.79 (stage 2, half-risk) or a fresh high resets `run_high`.

---

## Current state

**Holding GUSH.** 1 share, filled $44.25 at 09:43:21 ET 2026-08-19, stop resting $43.14 — full detail and the ratchet schedule in E5's 9:40 entry note, not repeated here. Last close 2026-08-18: no trade. Prior close 2026-08-17: one trade (GUSH, -$0.02, r=-0.02) — full detail lives in `archive/trades.csv` and the commit history.

**Loss streak 1 of 3** (cleared 2026-08-15, unchanged today — a flat day neither adds to nor clears a streak). Floor: **$30.42** (50% of deposited cash, recomputed each 9:00 — reconfirm live, don't trust this number past the next research checkpoint).

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
