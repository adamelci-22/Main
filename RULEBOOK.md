# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.37.** Bump on every rule/threshold change; record it in the commit.

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
| **10:00–3:30** management ×12 | A · B (+ C if flat and a candidate looks live) | Holding, or flat and open to a fresh opportunity |
| **4:00** close | A · B4 · D | Exit, report, and arm tomorrow (primary) |
| **8:00** backup | A · D | Verify tomorrow is armed; re-arm only if missing |

**Part E is reference — pull it only when a rule in A–D sends you there.** Never read it front to back. **The same on-demand pattern applies to any inline pointer that lands outside your row's named part(s), not only ones into Part E** — C7/C8/C10's `(B1)`, C10/C11's `(B1b)`, D2's `(B1)`/`(E3)`/`(E5)`, and every other parenthetical citation. A row's letter code names the part(s) it reads in full; a pointer found while reading sends you to grep and pull just the one subsection it names — never the whole part the pointer lands in, and never skip it because it's outside your row's headline letters.

**How to read only your row — this file is ~600 lines; a full read costs roughly 30k tokens, a targeted one costs 2k–14k.** `Grep` this file for `^# PART` (and `^---$` if narrowing further) to get each Part's current line span — **never hardcode line numbers**, edits shift them every commit. Then `Read` with `offset`/`limit` bounded to Part A plus only the part(s) your row names; for a single named subsection (9:30's C1, 4:00's B4), grep that subsection's own `^## ` heading instead of pulling its whole Part. A plain whole-file `Read` is the single largest token cost in running this system — do it only when genuinely unsure which span you need, and even then prefer a fresh `Grep` over repeating it.

---

# PART A — EVERY CHECKPOINT

## A1. Blocking conditions — check before anything else

**Any of these true → no new position may be opened. Not a judgement call.**

| Blocked when | Verify by |
|---|---|
| Loss streak ≥ 3 | Count closed trades in `archive/trades.csv` (E1) |
| Account below 50% of deposited cash | Recompute; never cache (E2) |
| Candidate's risk numbers not computed | No profile → no stop → no trade (B1) |
| Position already open | One position, one resting order (E2) |

**Most recent governor clearance of the breaker: 2026-08-15** — count only trades closed after that date (E1). The streak is computed fresh from `archive/trades.csv` (plus `get_equity_orders` for manual round trips) at every check — never from a number written here, which goes stale the day after it's written. **A missing or unreadable trade log must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`** — a fired trigger reschedules itself ~24h later carrying its original, now-stale prompt.
2. Delete any trigger on a slot about to be armed. Exactly one per slot.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 4:00pm close checkpoint (primary arming) or the 8:00pm checkpoint (backup verification, D1).** Together they replace what used to be a single point of failure.

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

> **No position may be opened outside 9:40–4:00.** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:40, subject to C1's late-entry clause. **A position that closes mid-day gets an accelerated re-check instead of waiting for the next grid slot — see C12.**

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

**The checkpoint chain is one continuous chronological sequence, not two separate tracks.** A C12 mini-cycle check (its T+0 read and its T+10 gate stack) is a formal checkpoint in this same chain the instant it runs, exactly like a scheduled grid slot — it feeds `session_high`/`session_low` and B6's range log the same way a 10:00 or 11:30 slot does. Nothing about being ad hoc makes it second-class for this purpose.

**All three must hold, checked fresh at every entry-eligible checkpoint (never cached):**

1. **Not currently falling.** This checkpoint's `bar_close` ≥ the immediately prior formal checkpoint's `bar_close`, for this candidate specifically — **"immediately prior" means whichever checkpoint actually ran last in real time, grid or C12 ad hoc, never a reach-back past it to the last *scheduled* slot.** One exception, owned by C12 not restated here: a C12 mini-cycle's own opening gate-stack pass compares against the candidate's price at the exit's fill timestamp instead (C12 steps 3–4 have the full rule and worked example — read there, not here, if this exception is in play). (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched.
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** `bar_high` must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − bar_close) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

## C11. Chop filter — Efficiency Ratio, time-scaled

**Applies to every candidate at every entry-eligible checkpoint, in addition to C1–C10.** Catches a candidate that's technically up on the day and technically not falling (passes C10) but is genuinely just chopping sideways rather than trending — leveraged ETFs decay in exactly that shape (C5).

**Efficiency Ratio (ER), computed from a direct minute-bar pull (B1b's technique), not sparse checkpoint points:** pull the trailing 60 minutes of minute bars for the candidate (or back to 9:30, whichever is shorter, early in the session). `ER = |last close − first close| ÷ Σ|close(n) − close(n−1)|` across every minute in the window — net progress over total path length. Near 1 = clean directional move; near 0 = pure back-and-forth with little net progress. Fewer than ~20 minutes of window available → too little to be meaningful, gate passes by default — never block on a gap, never pretend the check ran.

**Minimum ER required to enter, scaled to how forgiving the hour should be** (early moves are naturally noisier as they establish; afternoon entries into an already-mature move should be held to a materially higher bar). **Ranges are continuous — every clock time from 9:40 to end of day falls in exactly one row, no gaps.** This matters beyond the regular grid: a C12 mini-cycle check can land at any minute (fill-time-anchored, not just on the half hour), and needs an unambiguous minimum wherever it lands, not just at :00/:30:

| Checkpoint time | Minimum ER |
|---|---|
| 9:40 – 10:59 | 0.15 |
| 11:00 – 12:29 | 0.25 |
| 12:30 – 2:29 | 0.30 |
| 2:30 – end of day | 0.35 |

Below the window's minimum → declined as too choppy, regardless of C1–C10 all passing. This is a real, separate failure mode from C10: C10 asks "is it currently falling," C11 asks "is the recent path actually going anywhere, net."

C11 self-supplies its window with a fresh pull at the moment of the check — it does not depend on B6 having tracked the candidate at prior checkpoints. (B6 exists for C10, whose `session_high`/`session_low` need day-long continuity a trailing window can't provide.)

**Fetch once when B1b/B6 also apply to this candidate this checkpoint.** C11's window (60 min, or back to 9:30) always contains B1b/B6's shorter since-prior-checkpoint gap. Pull the larger window a single time and derive both from it — C11's ER from the full pull, B1b's `bar_high`/`bar_low`/`bar_close` from its tail subset — rather than two overlapping minute-bar calls for the same symbol. Same numbers either way; this only removes a duplicate call.

## C12. Re-entry cycle — an exit restarts the entry clock, not the whole day

**Applies whenever a position closes before 4:00, regardless of why** — stop, target, stall ladder, reversal, any B3 exit. The moment of exit becomes an ad hoc **"9:30-equivalent,"** rather than waiting for the next half-hour grid slot.

1. **The exit's fill timestamp is the mini-cycle's actual "9:30-equivalent" moment — not whenever it's later discovered or read.** At the moment the exit is discovered (T+0), same turn, no new trigger needed: run the 9:30-style check (C1) against today's existing shortlist — the candidates and sector proxies already built at 9:00, not a fresh market-wide scan. Record each sector proxy's current day change and note which shortlist names are still holding their move. C7 re-ranks fresh here too — the capital base just changed (the position closed), which by C7's own rule voids the earlier ranking.
2. **T+10 is measured from the exit's actual fill timestamp (from the order response), never from when it happened to be noticed.** Detection lags the real fill whenever the exit fires between scheduled checkpoints — get the real fill time first, then compute `elapsed = now − fill_time`:
   - **`elapsed ≥ 10 minutes`** — the window has already passed. Run the full 9:40-style entry gate stack, C1–C11, immediately, same turn as T+0. No trigger to arm, no further wait.
   - **`elapsed < 10 minutes`** — arm one ad hoc trigger for `10 − elapsed` minutes out (the nearest possible time to exactly `fill_time + 10min`, not a flat 10 minutes from T+0) to run the gate stack then.
   Enter if a candidate clears every gate, exactly as any other entry checkpoint would. This is in addition to, not a replacement for, the regular grid triggers already armed for the rest of the day.
3. **The comparison baseline for this gate stack's first run is each candidate's price *at the fill timestamp itself*, not at whenever the check happens to execute, and not the last regular grid slot.** Pull minute-bar historicals for that exact minute, for every shortlist name — the same one fixed moment for all of them, the same way 9:30 is one fixed moment for the whole watchlist, not something recomputed per candidate. This is what C10 leg 1 ("not currently falling") and C1's baseline reading compare against for this mini-cycle's first pass — whether that pass runs immediately (the `elapsed ≥ 10` branch) or at the armed T+10 trigger (the `elapsed < 10` branch). Being "free to trade" (timing, step 2) and "what you compare against" (this step) are two separate questions — 15 minutes already elapsed since the fill clears you to act *now*, but the price you're judging "still rising since I sold" against is still the price *at the fill*, not the price at whatever minute you happened to look.
4. **After the gate stack runs, whether or not a new position was opened, resume the standard grid at its own next slot — not exit-relative.** Exit at 10:45, discovered and gated promptly → the next check is the regular 11:00 slot, then 11:30, unchanged. This mini-cycle's first read (step 3) is itself a formal checkpoint in the single chronological chain C10 tracks and B6 logs (v3.26) — the regular slot that follows it compares against *that* read's own `bar_close`, not back past it to the fill-timestamp baseline again. The fill-timestamp anchor is a one-time reference for this mini-cycle's opening comparison only, never a standing reference point afterward.

**Worked example, steps 2–4 together (this is the authority C10 leg 1 points back to):** a position exits (fill) at 11:15. The 11:30 grid check discovers it; 15 minutes have already passed (`elapsed ≥ 10`), so the full gate stack runs immediately at 11:30 — C10 leg 1 there compares 11:30's `bar_close` against the candidate's price *at 11:15* (step 3), not against 11:00's close. Declined → the next check is the regular 12:00 slot, and *that* leg 1 compares against the 11:30 read's own `bar_close` (step 4) — not back against 11:15 again, and not against 11:00. From there it's fully normal: 12:30 vs 12:00, 1:00 vs 12:30, and so on.

Fires once per exit, not a new recurring cadence. If T+10 finds nothing that clears every gate, the book just stays flat until the next regular grid slot — same as any other declined entry.

**A chance to re-check, never a mandate to re-enter — everything else already in force still binds at full strength.** C5's "no read = no trade" and C9's "never force a trade" apply to the T+10 check exactly as hard as at 9:40; C9's "after 11:00, clearly better than the morning offered" is judged by the mini-cycle's own clock time (a 2:10pm mini-9:40 faces the same bar a regular 2:00pm entry would); A1's one-position gate is untouched. This rule only shortens *when* the next attempt happens, never *whether* one is allowed.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid (ET)

`9:00 · 9:30 · 9:40 · 10:00 · 10:30 · 11:00 · 11:30 · 12:00 · 12:30 · 1:00 · 1:30 · 2:00 · 2:30 · 3:00 · 3:30 · 4:00 · 8:00`

Add `4:30 · 5:00 · 5:30 · 6:00 · 6:30 · 7:00 · 7:30` **only if holding at 4:00pm** — a flat book never arms them. Extended hours: limit orders only, no new positions. **7:30pm is the last actionable close.**

Cadence is 30 minutes from 10:00 on. ET → UTC: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5. Skip market holidays — **verify the calendar, never assume.** On an early close, end the grid there and skip extended hours. **Friday arms Monday**, not the weekend.

Runs indefinitely until the governor pauses it. Never stop on your own initiative.

### Arming — primary at 4:00, backup at 8:00

**Tomorrow's full checkpoint chain gets created at the 4:00 close, right after that day's exit/report work (D3) — not held until 8:00.** This runs regardless of whether the book is flat or still holding into extended hours; a still-open position doesn't delay next-day arming, it just means 4:30–7:30 also run alongside it. Skip the weekend the same way as always — Friday's 4:00 arms Monday.

**8:00pm is a verification pass, not a second independent arming.** Check that tomorrow's chain already exists (`list_triggers`, looking for tomorrow's date). If it does, this is a non-event — stay silent per D3, nothing to report. **If it's missing or incomplete — the 4:00 arming failed or was skipped somehow — create it now, and say so explicitly**, the same way A2 already treats any past-due, still-enabled trigger as a missed checkpoint that gets done late and flagged, not silently absorbed.

**Together these replace what used to be a single point of failure.** Never delete either the 4:00 close checkpoint or the 8:00 backup checkpoint.

### Cadence reduction — flat and idle

If flat at **11:00** with no candidate that cleared C3 or C1, drop to **hourly** (12:00 · 1:00 · 2:00 · 3:00 · 4:00) and delete the half-hour slots. The preferred window has closed and the bar for a late entry is already "clearly better" — half-hourly checks past that point produce nothing but cost.

Resume the 30-minute grid immediately on any entry.

### Early shutdown

Flat · no resting orders · **and** no entry possible (buying power short) → delete remaining intraday checkpoints. **Keep exactly two: 4:00 close (report + primary arming) and 8:00 backup (verify tomorrow is armed; re-arm only if it isn't).** Being flat because an earlier trade already closed today is **not** by itself a reason to shut down — a later opportunity is still tradeable unless one of the two conditions above is actually true.

Flat at 4:00 → delete 4:30–7:30 regardless.

## D2. 9:00am research — standard work

1. **Headlines** — macro, geopolitical, overnight.
2. **Pre-market prices** across the universe and yesterday's watchlist.
3. **Earnings reactions** from last night's after-close reporters.
4. **Scan for individual movers clearing C3 first.** Rank sector leadership second, only where nothing cleared C3 but a group is moving.
5. **Confirm settled buying power and unsettled funds.** Recompute deposited capital and the floor; report either if changed.
6. **Write the watchlist — 5 sectors, each genuinely different, 3 individual stocks per sector.** Structured, not just ranked:
   - **Pick 5 sector proxies that don't overlap.** No two from the same correlated complex — GDX and GLD and SLV are one theme (precious metals), not three; XLE and USO are one theme (energy), not two. Choose the 5 most active, most distinct themes the morning's scan and headlines actually support. A single dominant story (today: crypto) still gets only one of the five slots, however many names in it are moving — concentration in one theme is exactly what this structure exists to prevent, since a reversal in that one theme otherwise leaves nothing uncorrelated to fall back on.
   - **For each of the 5 sectors, take its 3 best individual names — leveraged wrappers first, plain stocks to fill what's left.** Prefer E3's own grouping (by mfe_per_stop, never by price) — most sectors have real leveraged single-stock coverage there (semis, crypto). Where E3's group can't supply 3 leveraged names on its own, fill the remaining slots with plain (unleveraged) stocks from that same sector — real, liquid, currently-moving names found via a live sector-scoped scan (the scanner's Sector filter, or direct quotes on known sector constituents), never invented from memory and never padded with a name that isn't a genuine mover today. Profile every individual the same way regardless (B1) — a plain stock isn't a lesser candidate, C4's rank-2 path already exists for exactly this case, this just extends that same logic to which names make the watchlist in the first place, not only which vehicle gets traded once a name is already shortlisted. A sector only gets skipped entirely if it can't produce 3 real candidates even counting plain stocks — C5's "no read = no trade" still governs which names are real, leveraged or not.
   - 5 sectors × 3 names = 15 individuals, plus the 5 sector proxies themselves = 20 total, same overall count as before.
   - Profile every individual just-in-time (B1); mark affordability second, never first — include unaffordable names, they measure what capital is costing. The 5 sectors feed C1 (Gate 1); the 15 individuals feed C3 (major-move gate) and C4's rank-1/rank-2 tracks.
7. **Refresh the live-context block (E5).** Commit and push.

## D3. Reporting

- **Losses as plainly as gains.** No spin. Never claim edge from a small sample.
- **Verified fills only.** P&L in dollars, percent **and R**. Slippage both sides.
- **Correct your own errors promptly**, including ones that look bad.
- **Most checkpoints are non-events — stay silent.** No "checked, nothing to do."
- **When you do report, state the outcome, not the reasoning already committed to the file.** Full gate-stack reasoning belongs in `archive/trades.csv`'s notes field and E5 — both durable, both re-readable on demand. The chat reply is a line or two: what happened, the key number. It does not re-narrate reasoning that's already been written down. **This session runs every checkpoint indefinitely — Robinhood's connector grant can't be replicated in a fresh session, confirmed 2026-08-25, so there is no periodic reset.** Every word written into a reply becomes permanent, compounding context for the life of the system; duplicating file content into prose is a real, ongoing cost, not a one-time one.
- **Report immediately:** entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a notable setup declined.
- **A no-trade day gets no evening message.**
- **Friday 4:00pm always reports**, trades or not — balance, every trade, loss-streak count, what was declined and why, any rulebook change. The guaranteed heartbeat. (Moved here from 8:00pm under D1's arming restructure — 8:00 is now a silent-unless-broken backup check, even on Fridays; the real weekly data already lives at the 4:00 close, not four hours later.)

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
- **No weekly day-trade cap.** A self-imposed pacing limit (15 day trades / trailing 7 calendar days) was in force from 2026-08-20 through 2026-08-25 and is now removed by explicit governor instruction, 2026-08-25 — it never bound in practice (peak observed: 7 of 15) and the governor decided the extra bookkeeping wasn't earning its keep. PDT itself is already gone (below), so nothing regulatory replaces it. Frequency of entry is still bounded by the real gates — C9's timing/selection discipline, C5's "no read = no trade," A1's one-position-at-a-time — not by a count.
- **Multiple different candidates per day are explicitly authorized.** Not limited to repeating the same symbol — if a real, gate-clearing opportunity in a *different* instrument appears after an earlier position closed, take it, subject to A1's "position already open" gate (still only one position at a time). Governor instruction, 2026-08-20: *"you now have instant cash with margins and are allowed to trade multiple different things within one day if presented with an opportunity."*
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

**Structured, not narrated.** Log facts as compact bullets grouped by checkpoint/event — numbers, gate results, times — not flowing prose paragraphs. Same information, cheaper to write and cheaper to re-read within the day (Part E is pulled on demand, but the pull still costs whatever E5 has grown to since 9:00).

**Wednesday 2026-08-26, 9:00 research** (run ~9:32 ET, ~32min late per A2 — trigger fired late, no prior work missed, first checkpoint of the day):

- Headlines: broad market flat/mixed, no dominant theme. SPY -0.08%, QQQ -0.06%, DIA +0.06%, IWM -0.32%. Isolated earnings-driven moves only: Intuit -11% (FY27 guidance miss), Zoom -7% (guidance miss), Kohl's -5% (comps miss); Smucker +5.6% (beat), SolarEdge +7% (UBS upgrade). Software broadly soft (IGV -1%+, ServiceNow -2.5%, Workday/Salesforce -2%).
- MRNA -5.90% today — continuing to give back a prior-week cancer-vaccine-trial rally spike, not a fresh catalyst.
- Sector-proxy survey (18 ETFs checked): nothing clears a clean single-theme bar except precious metals falling together (GDX -1.43%, GLD -1.07%, SLV -0.87%) and mild uranium/nat-gas positives (URA +1.58%, UNG +0.78%).
- **Correction, same checkpoint (governor flagged the first pass stopped short):** a live Technology-sector scan (0.75% filter, missed by manual spot-checking) surfaced real semis names beyond the large-cap list, and nat-gas E&P plain stocks were never checked directly — both real, both verified via quotes, not invented. **5 sectors qualified**, full 20-name structure:
  - **Semis** — proxy SMH +0.10%. Individuals: AMDL (AMD +1.06%), TSMX (TSM +1.30%), **PLAB** (Photronics +7.03%, live Tech-scan find, semis-equipment).
  - **Biotech** — proxy XBI -0.69% (doesn't gate individual stocks). Plain-stock individuals: SMMT +9.99%, ARCT +4.83%, ZYME +4.20%.
  - **Uranium** — proxy URA +1.58%. Individuals: UUUU +0.78%, UEC +0.30%, DNN +0.27%.
  - **Precious metals reversal** (inverse-long) — formal E3 proxy GDX -1.43% (the traded vehicles move opposite GDX by design). Vehicles: DUST +3.04%, ZSL +1.80%, **JDST** +2.89% (junior miners inverse, live-quote find) — C1's own gate reading uses each vehicle's own day change (self-referencing, same convention as crypto's no-underlying names), since GDX's raw reading runs opposite the trade thesis.
  - **Nat gas** (new 5th sector) — proxy UNG +0.98%. Plain-stock individuals, real E&P names, all verified up today: EQT +2.41%, EXE +2.29%, RRC +1.72% (also checked, real but not top-3: AR +1.37%). Leveraged vehicle BOIL (+1.47%) exists but the sector structure here is proxy+plain-stocks like biotech/uranium, not vehicle-only like metals.
- Profiles (`tools/profile.py`, 32 daily sessions each), ranked by `mfe_per_stop`: UUUU 1.072 · ARCT 0.946 · UEC 0.935 · DNN 0.903 · ZSL 0.590 · SMMT 0.587 · ZYME 0.558 · RRC 0.540 · PLAB 0.524 · JDST 0.523 · DUST 0.456 · EXE 0.421 · EQT 0.416 · TSMX 0.388 · AMDL 0.376.
- **Today's watchlist: 20 names (5 proxies + 15 individuals/vehicles)** — SMH/AMDL/TSMX/PLAB, XBI/SMMT/ARCT/ZYME, URA/UUUU/UEC/DNN, GDX/DUST/ZSL/JDST, UNG/EQT/EXE/RRC.
- Buying power $229.61 (unchanged from yesterday's close), unsettled funds $0. Deposited ≈$201.48, floor ≈$100.74, not binding.
- **9:30 observation (C1 baseline, pre-correction reads still valid — corrected names not yet at a formal 9:30 print, use 9:00 reads above as their baseline).** Proxies: SMH -0.25% (faded negative) · XBI -1.21% · URA +2.58% (strengthening) · DUST +3.89% · GDX -1.77%. Individuals: AMDL +2.38% ✓ · TSMX **-0.18%, faded negative, no longer holding** · SMMT +8.01% ✓ · ARCT +4.66% ✓ · ZYME +4.23% ✓ · UUUU +2.04% ✓ · UEC +2.41% ✓ · DNN +2.14% ✓ · ZSL +1.94% ✓ · JDST +2.89% ✓. Only TSMX flagged as not holding. 9:40 re-confirms live for all 15, including the corrected 5.
- **9:40 entry.** C2 (AMDL): AMD +1.74% ranks #1 in SMH group (MU +0.60%, AVGO +0.30%, TSM +0.22%, NVDA -0.07%, SMCI -2.08%) — AMDL clears Gate 2. C3 re-confirm: TSMX +0.61% now fails magnitude (recovered off its 9:30 dip but still under +0.75%) — excluded. DUST/ZSL/JDST all fail C1 leg 3 (9:40 reading below 9:30 for each, e.g. DUST +3.23% vs +3.89% at 9:30) — metals-reversal blocked at 9:40, late-entry clause available later if any exceeds its 9:30 print. Ranked by `mfe_per_stop` among C1–C3 survivors: UUUU(1.072) and ARCT(0.946) both **fail C10 leg 1** — real intraday pullback below 9:30 level, confirmed via minute bars, not a marginal call. DNN fails leg 1 narrowly (bar_close $3.7891 vs 9:30's $3.7991). **UEC (0.935) clears C10** (leg 1 passes narrowly, $13.600 vs $13.590; leg 2 bounce off session_low confirmed; leg 3 giveback 28%, well under 65%) — flagged as thin data, only ~15min of session history exists (first entry-eligible checkpoint after 9:30). C11: window auto-passes, under the ~20min meaningful threshold, flagged not genuine clearance. **Entered UEC 9:46:30 ET, 16sh @ $13.6665 avg ($218.66 total), stop $13.32 (-2.54%) confirmed resting on the first attempt** — target $14.19 (+3.80%), breakeven trigger +2.37%, trail 1.69%, mfe_per_stop 0.935 (2nd-ranked overall behind UUUU 1.072, which failed C10). Spread priced: bid/ask $13.65/$13.66 at review, ~0.07%, trivial against target. Pre-commit: exit at next checkpoint if bar_close falls back below today's session_low with no fresh bounce, or if the stall ladder/velocity trigger fires per B2/B3.
- **10:00 management (holding UEC).** Range since entry: ran to a high of $13.80 (+0.98%) then faded to $13.50 now (-1.22% from fill). `run_high` progressed to $13.80 (cleared old run_high by >stall threshold) — stall count 0, not stalled. Velocity check: checkpoint_gain 0.98% vs 1.08% threshold (3×stall_pct) — did not fire. Ratchet: still stage 1 (half-risk needs +1.19%, only +0.98% reached) — stop unchanged at $13.32, confirmed still resting. B4 target ($14.19) not close. B5 headlines not due (next due ~10:32). **B6 shortlist snapshot** (bar_high/low/close, 13:40–14:01 ET): AMDL $53.00/$51.72/$52.61 · PLAB $31.99/$30.22/$31.07 · SMMT $15.10/$14.30/$14.85 · ARCT $16.14/$15.34/$15.71 · ZYME $30.11/$28.40/$30.08 · UUUU $16.50/$16.05/$16.11 · DNN $3.845/$3.770/$3.785 · EQT $56.27/$54.99/$56.21 · EXE $98.10/$96.67/$97.99 · RRC $42.26/$41.51/$42.26. Pre-commit: exit at 10:30 if a 2nd consecutive stall occurs (3 needed before noon) combined with a real reversal below today's low, or if velocity/target/stall-3 fires outright per B2/B3/B4.
- **Stop fired 10:13:10 ET** — 13 min after the 10:00 checkpoint, 17 min before 10:30. The resting stage-1 stop ($13.32, never advanced) did its job: price kept falling after the 10:00 snapshot and hit it. Confirmed filled, clean, no E6 issue. **Net -$5.54, -2.54%, r=-0.998 — first loss of the week**, streak resets to 1 of 3, no breaker concern. True range for the 27min hold: high $13.80 (+0.98%, MFE, at 9:48 ET), low $13.30 (the exit bar itself, MAE +2.68%). **Process gap caught writing the trade-log row: C6 (commodities/materials gate) was never explicitly run for UEC** — it's Basic Materials (uranium mining), which per C5 uses C6 instead of a named catalyst. C1–C3/C10/C11 all genuinely cleared so entry wasn't mechanically invalid, but a real required check was skipped. Same applies to today's EQT/EXE/RRC (Energy/E&P). Full detail in `archive/trades.csv`.
- **C12 T+0** (fill 14:13:10Z, elapsed 3m4s at read <10min — T+10 armed for 14:23:10Z, not run immediately). Proxies: SMH -0.37% · XBI -0.67% · URA +1.37% (still positive but individuals rolling over) · GDX -1.65% · UNG +1.29% (strengthening). Still holding/clearing C3: AMDL +1.43% · PLAB +8.49% · SMMT +7.86% · ARCT +4.66% · ZYME +9.72% (accelerating) · EQT +4.20% · EXE +3.49% · RRC +3.11% (nat-gas trio all strengthening). Rolled over: TSMX -0.24% · UUUU -0.63% · DNN +0.13% (uranium individuals faded together, consistent with the stop-out). Metals: DUST +3.37%/ZSL +1.55%/JDST +2.21% — none exceed their 9:30 baseline yet (late-entry bar), still blocked. T+10 gate stack will explicitly run C6 for the materials/energy names this time.

## E6. Known issues — backlog, not yet fixed

**Stop-order placement can fail silently, in more than one way, and the pattern is escalating rather than resolving.**

*Failure mode 1 — silent zero-fill cancellation.* Comes back `cancelled` with zero fill and no error message. First observed 2026-08-24 (twice, MSTX, both resolved on one retry, no real exposure). Escalated 2026-08-25: SMCX's 10:00 checkpoint hit it three times in a row on the same placement — price moved through the intended stop level during the unprotected gap, forcing a manual marketable-limit exit. Real exposure, not a near-miss.

*Failure mode 2 — outright rejection when the stop price is at/above the live market.* First identified 2026-08-25, UUUU's 11:30 checkpoint: the correctly-computed new stop ($15.93) was placed a moment after price had already pulled back below it ($15.87) — the order came back `rejected`, not `cancelled`, with a clear enough pattern to name the likely cause: the broker won't accept a sell-stop whose trigger condition is already satisfied at placement time (it should really be an immediate market order, not a resting stop, and the API appears to refuse rather than convert it). The follow-on manual exit had its own near-miss: the first marketable-limit attempt used a bid that had already gone stale by the time it posted, landed as a passive (non-marketable) resting order instead of an immediate fill, and had to be cancelled and re-priced against a fresh quote before it actually executed — a reminder that "marketable" only holds for as long as the quote it was priced against.

**Mitigation is manual, not systemic — and the governor has explicitly reviewed that trade-off and accepted it, 2026-08-25.** After every stop placement, verify it actually landed via `get_equity_orders` before considering the position protected; retry immediately if it didn't, and if the retry keeps failing, re-check the live price before retrying blind — a rejection can mean the stop level itself is stale, not just that the placement call needs repeating. This has caught every incident so far (2026-08-24 ×2, 2026-08-25 ×2, one per failure mode) with zero losses attributable to the glitch itself — both 2026-08-25 incidents closed as real wins (SMCX +$4.25, UUUU +$6.86), not losses. Governor's read: today's names (SMCX, UUUU) are fundamentally fast-moving instruments, some order-placement friction against that kind of tape isn't itself alarming, and the current catch-verify-retry-or-exit process is working — **keep doing what's been done**, not a directive to build the automatic wrapper urgently.

**Still worth building eventually, no longer treated as urgent.** An automatic retry-and-verify wrapper around stop placement — place, confirm via a follow-up read, re-check price before a blind retry, all without waiting on a manual catch — remains a real improvement over a human-speed read-decide-act loop inside a moving market. But per governor sign-off, this stays a nice-to-have on the backlog, not a same-day priority. Revisit if a future incident actually produces a loss (not just forced friction on a winning trade), or if the failure rate climbs further.

---

## Current state

**Flat into the close, Tuesday 2026-08-25.** Cash/buying power $229.61, no resting orders (verified live). Net **+$11.11 on the day**, two trades: SMCX (+$4.25, r=+0.293, 9:44–10:04 ET) and UUUU (+$6.86, r=+1.238, 10:20–11:32 ET) — both real, rule-cleared entries, both exits mechanically forced by the E6 stop-placement glitch (two distinct failure modes, both closed as wins, see E6) rather than by a rule firing. Five management checkpoints after the second exit (12:00 through 3:30) correctly stayed flat as nothing cleared the full C10/C11 gate stack; the 4:00 close/report checkpoint itself was skipped when the governor paused the session for the day (credit-conservation reason, not a rule event) — no position was open at the time, so nothing was left unprotected.

**v3.30–v3.37 all confirmed working live**: D2's leveraged-first/plain-stock-fallback watchlist rule, the weekly day-trade cap's removal (v3.33, no longer tracked), the targeted-read/pointer-following discipline (v3.34–v3.35), and the fetch-once/E5-structure/reply-terseness token reductions (v3.36–v3.37, first applied this file).

Prior trades: 2026-08-25 UUUU (+$6.86, r=+1.238); 2026-08-25 SMCX (+$4.25, r=+0.293); 2026-08-24 MSTX (+$13.81, r=+1.050); 2026-08-21 MSTX (-$0.14, r=-0.011); 2026-08-21 CONL (+$2.51, r=+0.230); 2026-08-20 MSTX (-$0.54, r=-0.201, governor's off-cycle exit, not rule-triggered); 2026-08-19 GUSH (+$0.22, r=+0.194).

**Loss streak 0 of 3.** Deposited capital ≈ $201.48 (all-time realized P&L ≈ +$28.13), floor ≈ $100.74 — not binding.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
