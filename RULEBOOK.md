# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.22.** Bump on every rule/threshold change; record it in the commit.

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
| **9:40** entry | A · C | The primary entry slot |
| **10:00–3:30** management ×13 | A · B (+ C if flat and a candidate looks live) | Holding, or flat and open to a fresh opportunity |
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
| Weekly day-trade cap reached | ≥15 day trades already in the trailing 7 calendar days (E2) — self-imposed pacing limit |
| Position already open | One position, one resting order (E2) |

**Most recent governor clearance of the breaker: 2026-08-15** — count only trades closed after that date (E1). Both the streak and the weekly day-trade count are computed fresh from `archive/trades.csv` (plus `get_equity_orders` for manual round trips) at every check — never from a number written here, which goes stale the day after it's written. **A missing or unreadable trade log must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

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
target_pct         = clamp(1.25 × median favourable, 1.5 × stop_pct, 12.0%)
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

## B1b. Range-based checkpoint reads — every mechanism below uses this, not a single point quote

**"Checkpoint price" never means one live quote taken at the checkpoint's exact moment.** At every checkpoint from entry onward, pull minute-bar historicals covering the gap since the *previous* checkpoint (or since entry, for the first check) — the same call used to compute honest MAE/MFE after a trade closes, run *during* the hold as well. From that window, derive three numbers:

- `bar_high` — the highest high reached anywhere in the gap.
- `bar_low` — the lowest low reached anywhere in the gap.
- `bar_close` — the window's final close, used wherever a mechanism needs the actual live tradable price (order placement, comparing a proposed stop against where price sits right now) — ranges inform the analysis, but a real order still needs a real current quote.

**Ranges close the observation gap without changing decision frequency.** Checkpoints run every 30 minutes — a hard cost constraint. Each one knows the true high and low reached since the last, so a spike-and-reverse inside one interval is visible to every rule, even though action still waits for a scheduled checkpoint. Everywhere below, `run_high`, `session_high`/`session_low`, and checkpoint-to-checkpoint comparisons read from this range, never a point.

## B2. Stops — UP ONLY, NEVER DOWN

- **Never widen.** If the tape needs more room the trade is wrong — be out.
- Only permitted downward change: correcting a factual placement error, stated as such.
- Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print.**
- Minimum re-placement move: `min_stop_move_pct`. A structural level (swing low) may substitute **only if nearer**.
- Stops are **regular-hours only** and do not protect a gap.

### The ratchet — precise, so a cold checkpoint can't misread "gain"

**One `run_high`, shared with B3 — not a second high-water mark.** Same value, same derivation: `run_high` is `max(run_high, bar_high)` at every checkpoint (B1b) — the true highest price reached in the gap, not a lucky-or-unlucky point sample. Advances only when `bar_high` clears the prior `run_high` by more than `stall_threshold_pct` (B3 steps 1–2); a stalled check does not advance it even if `bar_close` alone would have looked like a new high.

**The three stepped stages below are measured against `run_high`, never the live price.** `run_high` only moves up, so once a stage is reached it cannot un-reach itself on a pullback — that is what "up only" requires. Each is a one-time jump, evaluated fresh every checkpoint, applied only if it raises the stop:

| Stage | Trigger (on `run_high`) | Stop goes to |
|---|---|---|
| 1 — entry | — | `fill × (1 − stop_pct)` |
| 2 — half-risk | `(run_high − fill) ÷ fill` ≥ `breakeven_trigger ÷ 2` | `fill × (1 − stop_pct ÷ 2)` |
| 3 — breakeven | `(run_high − fill) ÷ fill` ≥ `breakeven_trigger` | `fill` (breakeven) |
| 4 — trail | past stage 3 | `run_high × (1 − trail_pct)` — **the only continuous stage**, recomputed every checkpoint as `run_high` climbs |

**Worked example — AGQ's actual profiled numbers, fill at $100.00, `stop_pct` 2.50%, `target_pct` 3.75%, `breakeven_trigger` 1.65%, `trail_pct` 1.45%** (each per B1's formulas above):

| Stage | `run_high` reaches | Stop becomes |
|---|---|---|
| 1 — entry | $100.00 (fill) | $100.00 × (1 − 0.0250) = **$97.50** |
| 2 — half-risk | $100.00 × (1 + 0.0165÷2) = **$100.83** | $100.00 × (1 − 0.0125) = **$98.75** |
| 3 — breakeven | $100.00 × (1 + 0.0165) = **$101.65** | **$100.00** (fill) |
| 4 — trail, e.g. `run_high` runs to $103.00 | — | $103.00 × (1 − 0.0145) = **$101.51** |
| target | live price reaches $100.00 × (1 + 0.0375) = **$103.75** | **SELL ALL** — B4, overrides every stage |

### Velocity trigger — a fast checkpoint move flips the position to a permanent tight trail

**Checked every checkpoint, alongside the staged ratchet above — an independent trigger, not a fifth stage in the sequence.** Compares this interval's `bar_high` (B1b) to the *immediately prior* checkpoint's `bar_close` only (not `run_high`, not the day's total change) — using the true high reached in the gap, not just wherever price settled by the time of the read, so a fast spike still counts even if it's partly faded back by checkpoint time:

`checkpoint_gain = (bar_high − prior_bar_close) ÷ prior_bar_close`

**If `checkpoint_gain ≥ 3 × stall_threshold_pct`, a fast move has occurred and this position is flagged for the rest of the hold** — the flag never clears once set. **From the triggering checkpoint onward, at every checkpoint (fast or not), the stop becomes `max(staged-ratchet stop, run_high × (1 − stall_threshold_pct))`** — a continuous tight trail using the candidate's own noise-calibrated cushion, layered on top of the staged ratchet, never replacing it, always taking whichever is higher. Still subject to B2's own rules: up only, never down, minimum re-placement move applies.

**Why this is its own check, not a fifth stage:** the staged ratchet only unlocks continuous trailing once stage 3 (breakeven) is fully reached — a position that runs hard but stalls just short of that bar gets zero additional protection while it gives the gain back. This check reacts to *how fast* the position moved, not just how far: a jump well past the instrument's own normal noise is proof enough to start locking in gains ahead of the staged schedule. Once a position has shown it can move fast, keeping what's been won outranks giving it room to keep running.

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
| 1 | at or above fill | Stop moves to **whichever is higher: breakeven, or the ratcheting stop's current level** (`max(breakeven, ratchet stop as of this checkpoint)`). Never a third value — just those two, compared, higher one wins. Safe, `bar_close` (the live tradable price, B1b) is still above it. |
| 1 | below fill | **No move.** Moving the stop to breakeven would place it above `bar_close`, forcing an immediate sell — that is rejected, not executed early. Re-check next checkpoint. |
| 2 | either | **SELL ALL — complete.** Overrides every stage above, no exceptions. |

**Crossing noon mid-hold:** apply whichever table matches the *current* checkpoint's clock time to the stall count as derived cold at that same checkpoint (B3) — don't backdate which regime a past stall happened under. A count that's already at 2 when a 12:00 checkpoint runs means SELL ALL immediately under the now-current rule; a count of 1 or 2 left over from the morning is simply read against the afternoon table from that point on.

**Any checkpoint where the live price ≥ `target_pct` → SELL ALL**, overriding everything above (B4).

## B3. Exits — any one fires

### Stall — measured against the interval's range, not a single point (B1b)

A **stalled check** = a checkpoint whose `bar_high` (the true high reached since the prior checkpoint, B1b) failed to exceed `run_high` by more than `stall_threshold_pct`. `run_high` is seeded at the fill and updated from real bar highs each checkpoint — genuinely the highest price traded since entry, not a point sample that might have missed it.

**Derive cold every time — nothing is remembered:**
1. Pull the interval's bars (B1b): `bar_high`, `bar_low`, `bar_close`.
2. `bar_high > run_high × (1 + stall_threshold_pct/100)` → **progressed**: count to 0, `run_high` becomes `bar_high`.
3. Otherwise → **stalled**: count increments, `run_high` unchanged.
4. Total = consecutive stalled checks ending at the most recent.

**Apply the count to B2's noon-gated action table** — 3-stall SELL ALL before noon, 2-stall SELL ALL (with an earlier profit-lock on stall 1) at or after — full detail and the noon-crossing rule there.

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

At any checkpoint showing a `bar_close` gain ≥ `target_pct` → **sell the entire position.** No scaling out, no runner, at any share count. Target is a ceiling; most trades exit on the stall ladder first.

**`target_pct` is variable, not a fixed number — computed once, per candidate, at entry (B1), and does not change for the life of that trade.** A fresh `tools/profile.py` run on the same symbol mid-trade would likely produce a different number, but the trade holds the value locked in at entry, stated at entry (C8) — recomputing it mid-hold would make the exit a moving target.

**Every position closes the same trading day it was opened. No overnight hold, ever.** State the intended exit at entry.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(While flat and no candidate is live, hourly is enough (D1's cadence reduction already drops the check frequency). Don't stop checking just because an earlier trade already closed today — a later opportunity is still tradeable.)*

## B6. Shortlist range snapshot — feeds C10, whether or not it's the held position

**At every management checkpoint (10:00–3:30), log `bar_high`/`bar_low`/`bar_close` (B1b) for every name still on today's shortlist** (the candidates that cleared C3 at 9:40, not the full 20-name watchlist) — not a single point price, the same range-pull technique used for the held position, applied to the rest of the shortlist too, even while holding something else. One extra minute-bar call per name; the same call already run for the held position, not a new kind of lookup.

**Why this is its own duty:** C10's `session_high`/`session_low` need continuous range history *per candidate* — a genuine day-long high-water mark. A candidate re-considered later in the day with no reads since 9:40 has no history for C10 to check, so it default-passes for lack of data rather than genuinely clearing anything. That default-pass is safe (never block on a gap) but silently defeats the gate if the gap becomes routine. When a default-pass does happen, flag it explicitly at entry — never let it look like a deliberate clearance.

---

# PART C — ENTRY (9:00 · 9:30 · 9:40 primarily; any 10:00–3:30 checkpoint while flat)

> **No position may be opened outside 9:40–4:00.** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:40, subject to C1's late-entry clause and the weekly day-trade cap (E2). Check the cap fresh before every entry, not just the first. **A position that closes mid-day gets an accelerated re-check instead of waiting for the next grid slot — see C12.**

## C1. Gate 1 — the sector must hold, 9:30 → 9:40

**9:30 is scoped to the 20-name watchlist only — no new market scan.** Record the day change of the **5 sector proxies** (feeds the Gate 1 test below) and note whether each of the **15 individual candidates** is still holding its move. That's an observational check, not a formal re-run of C3 — the formal re-confirmation of C3's legs happens live at 9:40.

Applies to a **sector- or index-leveraged trade** only. Record the sector proxy's day change at **9:30** and again at **9:40**. All three must hold:

1. positive at 9:30, **and**
2. positive at 9:40, **and**
3. the 9:40 reading **not below** the 9:30 reading.

Any failure at 9:40 → no entry **at 9:40** in that sector's leveraged vehicle.

**Late entry, any checkpoint after 9:40:** the door isn't permanently closed by a 9:40 failure. At any later checkpoint, entry is still allowed if the sector proxy's live reading at that checkpoint is **strictly higher than the 9:30 baseline** — not merely "not below" (that looser bar is 9:40's own test, leg 3 above; a later checkpoint must clear the higher bar of actually exceeding 9:30, not just matching or nearly matching it). Recovered sector strength after 9:40 is tradeable, but only past a real, higher threshold — never on a bare return to the 9:30 level.

**Two fixed observations (9:30, 9:40) decide the 9:40 pass/fail — never add intermediate readings there.** The late-entry test above is the one exception, evaluated fresh at whichever checkpoint is asking, using that checkpoint's own live reading against the fixed 9:30 baseline.

**Does not gate a single-stock trade.** A stock moving decisively on its own does not need its sector to confirm; it is judged on its own move, and on Gate 2 if traded leveraged. **Every candidate, including single stocks, is still subject to C10's direction/reversal test** — this gate's leg 3 is the sector-proxy-only version of that same idea.

## C2. Gate 2 — top 3 sector leaders

**Replaces the old single "must beat the proxy" comparison with a relative shortlist.** For a leveraged single-stock ETF, read the live day change of every name in its **E3** sector group (its own reading where the group has no separate underlying — e.g. RIOT/MARA/CLSK/BITX/BITU/ETHU/ETHT — or the underlying's reading where one exists — COIN for CONL, MSTR for MSTX).

**Normalize for embedded leverage before ranking.** A group member that is itself a leveraged product (BITX/BITU ≈2× bitcoin, ETHU/ETHT ≈2× ether — or any other name in the universe carrying a stated multiple with no separate underlying) gets its day change divided by that multiple first. Comparing raw leveraged-product returns against unleveraged stocks in the same list just rewards whoever already carries a multiplier — it isn't a read on which name is genuinely leading.

Rank the group by (normalized) day change. **Only the top 3 pass Gate 2**; every other group member is declined here regardless of its own day change being positive. Does not apply to sector or index vehicles — those *are* the group.

The top 3 still have to individually clear C3 (magnitude) to be tradeable at all — Gate 2 narrows *which* names in an already-moving group are worth a wrapper, it doesn't waive the move requirement. **C7's `mfe_per_stop` ranking then picks the entry from among the (up to) 3 survivors**, same as it does for any other multi-candidate shortlist.

## C3. Major-move gate — what qualifies an individual stock

**Long-only, end to end.** Every single-stock name in the universe is a leveraged-*long* wrapper, so this gate cannot produce a short or inverse trade and does not try. Inverse views go through the sector path (C1 + an inverse sector ETF).

1. **Magnitude** — day change **≥ +0.75%** from prior close, up only. Measure the *underlying stock*, never the leveraged wrapper; the wrapper is just the multiple.

**Leg 1 alone is sufficient to qualify a candidate.**

2. **Moving average — optional, adds weight only, never a trigger and never a veto.** When price is actually testing the 50- or 200-day SMA, check its slope over 5–10 sessions. Rising MA + bounce up → extra confirmation for the long. Falling MA + rejection → **not counted at all**, neither as a reason to decline nor as an inverse trigger. Skip if price is not near either average.

Screen leg 1 at **9:00** with the scanner (`% Change`, or the gainers preset). **Re-confirm live at 9:40** — a 9:00 read is stale by the open.

Fails leg 1 → not a major-move candidate; fall back to a sector read or no trade.

> +0.75% is a **starting default, not a backtested constant.** The bar is deliberately low to catch momentum early, so it surfaces many candidates — the catalyst check, Gate 2 and ranking carry the filtering load downstream.

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

**Size to the maximum whole shares settled cash affords for the chosen candidate** — floor(settled cash ÷ ask), not 1 share by default. Only one position is ever open at a time (E2), so this is full deployment into that single candidate, not a per-trade allocation decision. Everything downstream still scales correctly: stop/target/breakeven are percentages of the fill, so dollar risk and reward scale with share count exactly as they should. Recompute the affordable quantity fresh at entry from live settled cash and the live ask — never reuse a quantity implied by an earlier affordability check.

Before placing, confirm every A1 blocking condition is clear, plus: stop present and inside the 7% cap and matching the profile · affordability against **settled** cash, not account value · order type · C2 if single-stock leveraged.

Then:
- `review_equity_order` first — **a clean review proves nothing about placement** (E4).
- **Marketable limit, never plain market.**
- **Verify the fill from the order response.** Never report an unconfirmed fill.
- **Place the protective stop immediately after the fill.**
- Report slippage against the intended price.
- State at entry: fill · **quantity and total cost** · stop price and % · target % · breakeven trigger · trail · `mfe_per_stop` for the top two · intended exit · the falsifiable pre-commit for the next checkpoint.

## C9. Timing and selection

- **Preferred window 9:40–11:00.**
- After 11:00 a new entry must be **clearly better** than the morning offered, not merely available. Boredom is not a signal. For a sector-leveraged trade this is concrete, not a feeling: C1's late-entry clause requires the proxy strictly above its 9:30 baseline.
- Never force a trade because the window is closing.
- Verify `all_day_tradability` before entering.
- **Price the spread:** read the actual bid/ask, **double it** for the round trip, subtract from the expected move — take it only if it still clears the target with room.
- Check the price before building a thesis. A candidate you cannot buy is not a candidate.

## C10. Momentum direction — decline a fading price, allow a confirmed reversal

**Applies to every candidate, every entry-eligible checkpoint** — sector proxies, individual stocks, plain or leveraged, in addition to (never instead of) C1–C9. Built to catch a candidate that's fading right now without permanently locking out a genuine second-wave rally later in the same session.

**Track, per candidate, from the day's own range-based checkpoint reads (B1b, via B6's shortlist snapshot)** — not point quotes (9:30 is the first formal read; the 9:00 scan is informal/stale per C3 and does not count here):

- `session_high` — the best `bar_high` reached so far today, across all checkpoints. Advances any time a fresh interval high prints, whether or not that high survived to the interval's close.
- `session_low` — the lowest `bar_low` reached *since* `session_high` was last set. Only exists while price is currently below `session_high`; clears the instant a new `session_high` prints — a fresh high ends the pullback episode outright.

**All three must hold, checked fresh at every entry-eligible checkpoint (never cached):**

1. **Not currently falling.** This checkpoint's `bar_close` ≥ the immediately prior formal checkpoint's `bar_close`, for this candidate specifically. (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched.
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** `bar_high` must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − bar_close) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

## C11. Chop filter — Efficiency Ratio, time-scaled

**Applies to every candidate at every entry-eligible checkpoint, in addition to C1–C10.** Catches a candidate that's technically up on the day and technically not falling (passes C10) but is genuinely just chopping sideways rather than trending — leveraged ETFs decay in exactly that shape (C5).

**Efficiency Ratio (ER), computed from a direct minute-bar pull (B1b's technique), not sparse checkpoint points:** pull the trailing 60 minutes of minute bars for the candidate (or back to 9:30, whichever is shorter, early in the session). `ER = |last close − first close| ÷ Σ|close(n) − close(n−1)|` across every minute in the window — net progress over total path length. Near 1 = clean directional move; near 0 = pure back-and-forth with little net progress. Fewer than ~20 minutes of window available → too little to be meaningful, gate passes by default — never block on a gap, never pretend the check ran.

**Minimum ER required to enter, scaled to how forgiving the hour should be** (early moves are naturally noisier as they establish; afternoon entries into an already-mature move should be held to a materially higher bar):

| Checkpoint window | Minimum ER |
|---|---|
| 9:40 – 10:30 | 0.15 |
| 11:00 – 12:00 | 0.25 |
| 12:30 – 2:00 | 0.30 |
| 2:30 – 3:30 | 0.35 |

Below the window's minimum → declined as too choppy, regardless of C1–C10 all passing. This is a real, separate failure mode from C10: C10 asks "is it currently falling," C11 asks "is the recent path actually going anywhere, net."

C11 self-supplies its window with a fresh pull at the moment of the check — it does not depend on B6 having tracked the candidate at prior checkpoints. (B6 exists for C10, whose `session_high`/`session_low` need day-long continuity a trailing window can't provide.)

## C12. Re-entry cycle — an exit restarts the entry clock, not the whole day

**Applies whenever a position closes before 4:00, regardless of why** — stop, target, stall ladder, reversal, any B3 exit. The moment of exit becomes an ad hoc **"9:30-equivalent,"** rather than waiting for the next half-hour grid slot.

1. **At the exit itself (T+0), same turn, no new trigger needed:** run the 9:30-style check (C1) against today's existing shortlist — the candidates and sector proxies already built at 9:00, not a fresh market-wide scan. Record each sector proxy's current day change and note which shortlist names are still holding their move. C7 re-ranks fresh here too — the capital base just changed (the position closed), which by C7's own rule voids the earlier ranking.
2. **10 minutes later (T+10):** run the full 9:40-style entry gate stack, C1–C11, against whatever T+0 turned up. Enter if a candidate clears every gate, exactly as any other entry checkpoint would. Arm one ad hoc trigger for exactly 10 minutes out to run this — in addition to, not a replacement for, the regular grid triggers already armed for the rest of the day.
3. **After T+10, whether or not a new position was opened, resume the standard grid at its own next slot — not exit-relative.** Exit at 10:45 → mini-cycle at 10:45 and 10:55 → the next check is the regular 11:00 slot, then 11:30, unchanged.

Fires once per exit, not a new recurring cadence. If T+10 finds nothing that clears every gate, the book just stays flat until the next regular grid slot — same as any other declined entry.

**A chance to re-check, never a mandate to re-enter — everything else already in force still binds at full strength.** C5's "no read = no trade" and C9's "never force a trade" apply to the T+10 check exactly as hard as at 9:40; C9's "after 11:00, clearly better than the morning offered" is judged by the mini-cycle's own clock time (a 2:10pm mini-9:40 faces the same bar a regular 2:00pm entry would); the weekly cap (E2) and A1's one-position gate are untouched. This rule only shortens *when* the next attempt happens, never *whether* one is allowed.

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

Flat · no resting orders · **and** no entry possible (buying power short, or the weekly day-trade cap (E2) reached) → delete remaining intraday checkpoints. **Keep exactly three: 4:00 report, 8:00 arming, 8:20 backup.** Being flat because an earlier trade already closed today is **not** by itself a reason to shut down — a later opportunity is still tradeable unless one of the two conditions above is actually true.

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
- **Limited margin, since 2026-08-20** (verified via `get_accounts`: `type: "limited_margin"`; verified via `get_portfolio`: `buying_power` now equals `total_value`, unsettled proceeds usable immediately). This removes the old T+1 settlement gate — same-day rotation across sequential positions is now mechanically possible. It does **not** grant borrowing/leverage beyond the account's own cash, and does **not** by itself confirm anything about GFV exposure beyond what's stated below. If the account type changes again, re-verify from primary sources before the first trade — port nothing forward blind.
- **PDT (Pattern Day Trader) restriction is gone** — FINRA eliminated the framework effective 2026-06-04 (verified from Robinhood's support page, FINRA.org Regulatory Notice 26-10, SEC.gov, and the Federal Register; full sourcing in commits `ebac8c7`/`10d9379`). No 4-in-5-days trigger, no $25,000 minimum. **Residual uncertainty, not fully closed:** whether the replacement intraday-margin standard names `limited_margin` explicitly (inferred covered), and whether the separate $2,000 margin-minimum applies to `limited_margin`'s cash-only operation (inferred not). Both are inference, not citation — treat any broker-side restriction message as the signal that inference was wrong.
- **Weekly day-trade cap — self-imposed pacing, not a compliance requirement.** With PDT gone, this exists purely to bound churn/slippage on a small account, per governor instruction to set an explicit weekly limit. Cap: **no more than 15 day trades in the trailing 7 calendar days** (today inclusive). Count: every `archive/trades.csv` row is a day trade (B4/Part C force same-day entry and same-day close), plus any governor-placed manual round trip visible in `get_equity_orders` that wouldn't appear in the trade log. Recompute fresh at every entry-eligible checkpoint, never cached. Revisit the number if it binds often (too tight) or never binds (too loose).
- **Multiple different candidates per day are explicitly authorized.** Not limited to repeating the same symbol — if a real, gate-clearing opportunity in a *different* instrument appears after an earlier position closed, take it, subject to A1's "position already open" gate (still only one position at a time) and the weekly cap above. Governor instruction, 2026-08-20: *"you now have instant cash with margins and are allowed to trade multiple different things within one day if presented with an opportunity."*
- **No short selling is authorized** — not part of this system's mandate regardless of account type. Bearish views go through inverse ETFs bought long.
- **One resting order per position** — a pending sell locks the shares, so a stop and a take-profit cannot coexist.
- 24-hour tradability is optionality, never obligation.

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

*Friday 2026-08-21 closed: two rule-driven round trips (CONL +$2.51, MSTX -$0.14), account $204.69, flat into the weekend. Full day narrative in git history and `archive/trades.csv`. Next 9:00 research (Monday 2026-08-24) replaces this block wholesale per this section's own rule.*

---

## Current state

**Flat into the weekend (Fri 2026-08-21 close).** Account value **$204.69** — net **+$2.37** on the day across two rule-driven round trips: CONL (+$2.51, r=+0.230), MSTX (-$0.135, r=-0.011). **Weekly day-trade count: 8 of 15** as of Friday close — recompute fresh Monday; GUSH 8/17 and 8/19 age out over the weekend.

**Not yet live-tested, watch their first real firings:** B2's velocity trigger, C11, B1b, and v3.18–v3.22's changes to B4, C2, and C12 all shipped after Friday's close — Monday is their first live session. Full design rationale and backtests in the commit history (v3.11–v3.22), not repeated here.

Prior trades: 2026-08-21 MSTX (-$0.14, r=-0.011); 2026-08-21 CONL (+$2.51, r=+0.230); 2026-08-20 MSTX (-$0.54, r=-0.201, governor's off-cycle exit, not rule-triggered); 2026-08-19 GUSH (+$0.22, r=+0.194); 2026-08-18 no trade.

**Loss streak 1 of 3** — the CONL win reset it to zero; MSTX's small loss (any negative realized P&L counts per E1, regardless of size) starts a fresh count. Buying power: reconfirm live at the next 9:00 checkpoint, don't assume Friday's figure carries forward.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
