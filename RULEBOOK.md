# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.54.** Bump on every rule/threshold change; record it in the commit.

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
| **9:35** entry | A · C | The primary entry slot (v3.54 — moved up from 9:40) |
| **9:40–11:00** management ×9 (10-min cadence) | A · B (+ C — entries valid anywhere in this window) | Holding, or flat and open to a fresh opportunity — tighter cadence through the morning's most active stretch |
| **11:15–11:45** management ×3 (15-min cadence) | A · B (+ C — entries valid anywhere in this window) | Same as above, reverting to the wider cadence once the morning settles |
| **12:00** close | A · B4 · D | Exit, report, and arm tomorrow (primary) — pins the stop to current price (v3.54 — moved up from 12:30) |
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

**Most recent governor clearance of the breaker: 2026-08-31** — count only trades closed after that date (E1). (Cleared same-day after tripping on YANG/AFRM/GUSH — governor's explicit read: two of those three were mechanically-forced early exits on real moves, not signal-quality failures; full post-day analysis deferred to the 12:30 close review, not skipped.) The streak is computed fresh from `archive/trades.csv` (plus `get_equity_orders` for manual round trips) at every check — never from a number written here, which goes stale the day after it's written. **A missing or unreadable trade log must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`** — a fired trigger reschedules itself ~24h later carrying its original, now-stale prompt.
2. Delete any trigger on a slot about to be armed. Exactly one per slot.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 12:00pm close checkpoint (primary arming) or the 8:00pm checkpoint (backup verification, D1).** Together they replace what used to be a single point of failure.

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

**Ranges close the observation gap without changing decision frequency.** Checkpoints run every 10 minutes from 9:40 through 11:00, then every 15 minutes from 11:15 through 12:00 (v3.54) — a hard cost constraint, tighter through the morning's most active stretch. Each one knows the true high and low reached since the last, so a spike-and-reverse inside one interval is visible to every rule, even though action still waits for a scheduled checkpoint. Everywhere below, `run_high`, `session_high`/`session_low`, and checkpoint-to-checkpoint comparisons read from this range, never a point.

## B2. Stops — UP ONLY, NEVER DOWN

- **Never widen.** If the tape needs more room the trade is wrong — be out.
- Only permitted downward change: correcting a factual placement error, stated as such.
- Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print.**
- Minimum re-placement move: `min_stop_move_pct`. A structural level (swing low) may substitute **only if nearer**.
- Stops are **regular-hours only** and do not protect a gap.

### The trail — continuous chandelier off `run_high`, stock-scaled (v3.44)

**`run_high` tracks the high since *this position's entry* — a different window than C10's day-anchored `session_high`, even though both reuse the same B1b range-tracking technique.** Initialized to the fill price at entry, then `run_high = max(run_high, bar_high)` at every checkpoint (B1b) — the true highest price reached since the fill, not a lucky-or-unlucky point sample. Advances on any fresh interval high, unconditionally. **Never substitute `session_high` here** — a candidate can legitimately enter below its own day's high (C10 leg 2 allows a confirmed bounce off a pullback), in which case `session_high` at entry sits above the fill and would produce a stop tighter than the hold has actually earned.

**At every management checkpoint (9:40 through 12:00, on whichever cadence is currently in force — 10-min through 11:00, 15-min from 11:15, v3.54), the stop ratchets off the running high itself, discounted by twice the candidate's own noise band — never off the trailing average, never a fixed stage:**

```
run_high = max(run_high, bar_high)                         -- B1b, updated every checkpoint
candidate_stop = run_high × (1 − 2 × stall_threshold_pct)
new_stop = max(current_stop, candidate_stop)      -- up only, never down (B2's own rule, unchanged)
```

`stall_threshold_pct` is the candidate's own fresh JIT profile number (B1) — a calm name gets a wide-enough discount to survive its own normal noise; a choppy name gets pulled in tighter, proportionally. **Anchoring to `run_high` instead of the trailing average is the point:** the average sits close to the entry price right after a fill, so a completely normal early pullback can trip an average-based stop before a real trend has even formed. A high-water mark doesn't move on a pullback — only a fresh high advances it — so the trail gives a genuine trend room to breathe while still tightening every single checkpoint, never waiting on a breakeven gate. No separate spike-detection trigger exists anymore (retired v3.44) — this one rule already reacts to a fast move at the very next checkpoint.

**Why 2× the noise band:** backtested 1×–5× against all trades on record; 2× was the point that improved on the real historical results without giving reversals extra room to run first — full comparison in Current State (v3.44) and the git history, not restated here.

**At the 12:00 checkpoint specifically** — the last of the day (v3.54 — moved up from 12:30) — additionally include the live current price (`bar_close`, B1b) as a stop candidate: `new_stop = max(new_stop, bar_close)`. A position can only still be open at 12:00 if price is at or above its current stop, so this is always a valid *upward* move, never a violation of "up only." It pins the stop to the market, so the very next tick down closes the position — the stop still does the closing, not a forced sell, but the exit becomes effectively immediate. This is what ends the trading day; there is no separate 4:00pm deadline (see B4).

**No fixed profit-taking target — the trail is the only thing that locks in gains.** See B4: removed as a separate rule since v3.40, unchanged by this rewrite.

**`stop_pct` (entry) and `stall_threshold_pct` (every checkpoint after) are the only load-bearing numbers now.** `breakeven_trigger` and `trail_pct` were fully retired (not just unused) — `tools/profile.py` no longer computes them, and C8 no longer asks for them at entry. `target_pct` remains informational, feeding C7's `mfe_to_target` ranking check only.

**Worked example — MSTX, actual fill and bars, Thu 2026-08-27, `stall_threshold_pct` 0.893%, discount 1.786% (2×):**

| Checkpoint | Window | `run_high` | `candidate_stop` (`run_high × 0.98214`) | Stop becomes |
|---|---|---|---|---|
| 1 — entry, 9:43:52 ET | — | — | — | $14.1699 × (1 − 0.0597) = **$13.32** |
| 10:00 | since entry (9:43:52–10:00) | $15.0500 | $15.0500 × 0.98214 = $14.7812 | max($13.32, $14.7812) = **$14.78** |
| 10:15 | 10:00–10:15 | $15.4701 | $15.4701 × 0.98214 = $15.1938 | max($14.78, $15.1938) = **$15.19** |

Price fell to $14.896 shortly after the 10:15 checkpoint, below the $15.19 stop — **exit fires there, +7.23% locked**, well ahead of both the actual same-day trade's velocity-driven exit (+5.37%) and the prior average-based ratchet design's simulated result (+5.79%) — the running-high anchor stayed with the breakout instead of averaging it down. Same execution-risk caveat as E6: the stop can be raised to a level already at or below the live price at the moment it's placed (a fast-moving checkpoint window can do this to either mechanism) — verify the placement landed, same discipline as always.

## B3. Exits — any one fires

**No stall-count ladder** — the continuous trail (B2) already squeezes a stalling position every checkpoint; a second counting mechanism would just risk disagreeing with it. (Retired v3.43 — see Current State / git history for why.) `run_high` stays defined (B2) — entry-anchored, a distinct tracker from C10's day-anchored `session_high`.

### Other exits

- **Reversal** — broke the level or VWAP that justified entry, or (commodity trades only) the complex rolled over. The level must have been **named at entry** or the claim is unfalsifiable.
- **Risk/reward flipped** — small remaining upside against a large distance to the stop.
- **Unwanted event approaching** — earnings or macro data not intended to be held through.
- **Approaching the same-day close deadline** with the move finished.

Not on one red candle, midday noise, or impatience.

### Pre-commit — end every holding report with it

Name the **specific, falsifiable** condition that would exit at the next checkpoint, with instrument and direction. Then honour it. To override, say explicitly that you are overriding a pre-commitment and name the **new** information. *"It looks like it's turning back up" does not qualify.*

## B4. Same-day close — no fixed profit target

**No checkpoint sells purely for hitting a price level.** The continuous chandelier trail (B2) is what locks in gains — a big move is expected to give back at most `2 × stall_threshold_pct` off its running high at any checkpoint. `target_pct` is still computed at entry (B1) and used by C7's `mfe_to_target` ranking check — informational only, never an autonomous trigger.

**Every position closes the same trading day it was opened. No overnight hold, ever.** Enforced structurally, not by a deadline check: the 12:00 checkpoint (B2) pins the stop to the live price, so the position's own stop closes it, almost immediately, rather than a separate forced sell. State the intended exit at entry.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(The trading window (9:00–12:00) is short enough that this may only fire once or twice in a given hold. Don't stop checking just because an earlier trade already closed today — a later opportunity is still tradeable within the window.)*

## B6. Shortlist range snapshot — feeds C10/C11, maintained incrementally, whether or not it's the held position

**Starts at 9:30, not the first management checkpoint.** Every checkpoint that produces a B1b-style range read for a candidate — 9:30's observation, 9:35's entry gate stack, and every management checkpoint from 9:40 through 12:00 (whichever cadence is in force, v3.54) — pulls minute-bar historicals covering only the gap since that candidate's *previous* range read (B1b's own small window — never the whole day) **for every name still on today's shortlist** (the candidates that cleared C3 at 9:40, not the full 25-name watchlist), even while holding something else. One extra minute-bar call per name, the same call already run for the held position, not a new kind of lookup. This is what gives C11's "back to 9:30, whichever is shorter" window real coverage from the day's first read onward, instead of an artificially short one at the first management checkpoint.

**Update the running values, never re-derive them from scratch:**
- `session_high = max(session_high, bar_high)`. If this raises `session_high`, `session_low` clears — a fresh high ends the pullback episode (C10's own rule).
- Else `session_low = min(session_low, bar_low)` — only meaningful while price sits below `session_high`.
- Append one entry to a short rolling log: `(checkpoint_time, bar_close, path_length)`, where `path_length = Σ|close(n) − close(n−1)|` computed *only within this checkpoint's own small pull* — cheap, since the pull is already small. Keep log entries back to ~70 minutes; drop anything older.

**v3.47: this replaces re-pulling and re-summing the full day's minute bars at every checkpoint.** C10's `session_high`/`session_low` and C11's ER (below) now read off these maintained numbers plus a handful of rolling-log entries — never a fresh 40–90-minute pull re-scanned by hand every 15 minutes. A candidate re-considered after a real gap in its own reads (nothing logged since 9:40, say) simply has no running values to update yet — same default-pass-and-flag rule as always, not a new exception.

---

# PART C — ENTRY (9:00 · 9:30 · 9:35 primarily; any 9:40–12:00 checkpoint while flat)

> **No position may be opened outside 9:35–12:00 (v3.54).** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:35, subject to C1's late-entry clause. **A position that closes mid-day gets an accelerated re-check instead of waiting for the next grid slot — see C12.**

## C1. Gate 1 — the commodity must hold, 9:30 → 9:35

**v3.53 — scope narrowed to commodity trades only.** Since sectors are no longer a tradeable category (D2/C4), this gate now applies exclusively to the commodity vehicles named in E3 (energy, gold, silver, copper, uranium, broader materials) — never to an individual stock or its leveraged wrapper, which are judged purely on their own move (C3/C10).

**9:30 is scoped to whatever commodity groups are on today's watchlist — no new market scan.** Record the day change of each commodity's plain proxy (feeds the Gate 1 test below) and note whether the confirming complex (miners, E&P, etc.) is still holding. That's an observational check, not a formal re-run of C3/C6 — the formal re-confirmation happens live at 9:35.

Applies to a **commodity-leveraged trade** only. Record the commodity proxy's day change at **9:30** and again at **9:35**. All three must hold:

1. positive at 9:30, **and**
2. positive at 9:35, **and**
3. the 9:35 reading **not below** the 9:30 reading.

Any failure at 9:35 → no entry **at 9:35** in that commodity's leveraged vehicle.

**Late entry, any checkpoint after 9:35:** the door isn't permanently closed by a 9:35 failure. At any later checkpoint, entry is still allowed if the commodity proxy's live reading at that checkpoint is **strictly higher than the 9:30 baseline** — not merely "not below" (that looser bar is 9:35's own test, leg 3 above; a later checkpoint must clear the higher bar of actually exceeding 9:30, not just matching or nearly matching it). Recovered commodity strength after 9:35 is tradeable, but only past a real, higher threshold — never on a bare return to the 9:30 level.

**Two fixed observations (9:30, 9:35) decide the 9:35 pass/fail — never add intermediate readings there.** The late-entry test above is the one exception, evaluated fresh at whichever checkpoint is asking, using that checkpoint's own live reading against the fixed 9:30 baseline.

**Does not gate an individual-stock trade — nothing does, anymore.** A stock (or its leveraged wrapper) moving decisively on its own is judged purely on its own move (C3, C10, C11) and never needs a group to confirm it, because there is no group. **Every candidate, commodity or individual stock, is still subject to C10's direction/reversal test** — this gate's leg 3 is the commodity-proxy-only version of that same idea, for the one category that still has a proxy.

## C2. [Retired, v3.53]

**Was "Gate 2 — top 3 sector leaders."** Existed to rank several individual companies sharing one leveraged wrapper (crypto miners under BITX/BITU, etc.) before picking which one's move justified the trade. With sectors gone and crypto's group-leveraged products (BITX/BITU/ETHU/ETHT) retired outright (E3), nothing left in the system has more than one candidate per wrapper — each individual stock and its own leveraged ETF (if any) stands entirely on its own merit through C3/C5/C10/C11/C7, with no group to rank against. Number kept, not renumbered, so old trade notes and commits citing "C2" still resolve to this entry.

## C3. Major-move gate — what qualifies an individual stock

**Long-only, end to end.** Every single-stock name in the universe is a leveraged-*long* wrapper, so this gate cannot produce a short or inverse trade and does not try. Inverse views go through the commodity path (C1 + an inverse commodity ETF) — there is no individual-stock inverse path.

1. **Magnitude** — day change **≥ +0.75%** from prior close, up only. Measure the *underlying stock*, never the leveraged wrapper; the wrapper is just the multiple.

**Leg 1 alone is sufficient to qualify a candidate.**

2. **Moving average — optional, adds weight only, never a trigger and never a veto.** When price is actually testing the 50- or 200-day SMA, check its slope over 5–10 sessions. Rising MA + bounce up → extra confirmation for the long. Falling MA + rejection → **not counted at all**, neither as a reason to decline nor as an inverse trigger. Skip if price is not near either average.

Screen leg 1 at **9:00** with the scanner (`% Change`, or the gainers preset). **Re-confirm live at 9:35** — a 9:00 read is stale by the open.

> **Scanner filter values are decimals, not whole percents** (`0.0075` = 0.75%, not `0.75`) — `update_scan_filters` takes the same units. A stray whole-percent value doesn't error, it silently matches nothing (found 2026-08-28: `FILTER_TYPE_PERCENT_CHANGE_FROM_CLOSE` stored as `0.75` returned 0 matches all morning; corrected to `0.0075` returned 250). After any filter edit, verify with a live run before trusting a "no matches" read — zero results is itself a signal to check the filter, not evidence the tape is quiet. `update_scan_filters` also wants wire-format predicate enums (`PREDICATE_GREATER_THAN_OR_EQUAL`, etc.), not the human-readable symbols (`>=`) that `get_scans`/`run_scan` display.

Fails leg 1 → not a major-move candidate; fall back to a commodity read (C1/C6) or no trade.

> +0.75% is a **starting default, not a backtested constant.** The bar is deliberately low to catch momentum early, so it surfaces many candidates — the catalyst check (C5), C10/C11, and C7's ranking carry the filtering load downstream.

## C4. Instrument priority

**v3.53 — sectors dropped entirely; commodities are the one exception, since a physical commodity has no "individual stock" of its own.**

| Rank | Vehicle | When |
|---|---|---|
| **1** | Individual leveraged stock ETF | The mover is one company (C3) and it has its own leveraged wrapper (E3), affordable |
| **2** | Plain stock | The mover is one company, no affordable wrapper exists |
| **1c** | Leveraged commodity/miner-basket ETF | The mover is a commodity (energy, gold, silver, copper, uranium, broader materials — E3), C1/C6 clear, wrapper affordable |
| **2c** | Plain commodity ETF | Commodity is the mover, no affordable leveraged vehicle |

**Two parallel tracks, never competing — individual stock (ranks 1/2) or commodity (ranks 1c/2c), decided purely by what's actually moving, never by picking a "sector" and working down into it.** A single company moving on its own always goes through the individual-stock track, even if it happens to sit in a space (semis, biotech, financials, whatever) that used to have its own sector-leveraged ETF — those broad-sector vehicles are retired outright (E3), not a fallback.

1. **Identify the mover first** — one company, or a commodity. There is no third option; a "sector rotating together" that isn't a commodity is not a tradeable read under this system anymore, however real the move looks (find the specific stock leading it instead, per D2's market-wide scan).
2. **Prefer the leveraged vehicle** within whichever track applies.
3. **No leveraged vehicle affordable → take it plain.** Missing a real move for lack of a wrapper is the wrong trade-off.

## C5. Signals

- **Leadership ranked from data.** Never default to something you have been watching.
- **Breadth** applies to a *commodity* trade — the vehicle should reflect a real complex-wide move (miners confirming metal, E&P confirming crude, etc.). It does **not** disqualify an individual-stock trade.
- **A catalyst you can name.** "It's going up" is not one. *Exceptions:* commodities/materials use C6 instead; **tech and semis** are volatile enough that a clean catalyst often does not exist — look for one, but its absence does not exclude the name. Take it and say plainly none was found.
- **Trend, not chop.** Leveraged ETFs decay in chop.
- **Continuation, not prediction.**
- **No read = no trade.** A flat day is a correct outcome, never a quota to make up.

## C6. Commodities and materials — replaces the catalyst requirement

**Two legs, on top of C10's own intraday trend check** (which already applies to every candidate, commodities included — no separate multi-session requirement here, v3.51: every position closes same-day, never held overnight (B4), so a multi-day chart shape *before* today doesn't bind a trade that opens and closes *within* today's session; only today's own intraday trend matters, and C10 already tests exactly that for every candidate): **(1)** confirmation from the related complex (metal vs miners, crude vs E&P) · **(2)** pullback not breakdown — inside the prior session's range, above its low.

A replacement, not a relaxation — every other rule still binds. (v3.51 dropped the old "multi-session higher highs and higher lows" leg — it was blocking legitimate same-day moves for a reason that doesn't apply to a same-day-only system; a prior downtrend across days is irrelevant here the way it would matter to a multi-day swing system, which this isn't.)

## C7. Ranking

1. Rank candidates by `mfe_per_stop` (B1, computed per candidate), ignoring price.
2. **Then** mark what settled cash reaches as a whole share.
3. **Then** apply the gates and pick from survivors.

Never filter by price first. State the ratio for the **top two** candidates at entry, and name the top-ranked name if it was unaffordable, **with the dollar gap** — that number is what reports whether capital is the binding constraint. Deployment percentage is the last tiebreaker, never a filter. `mfe_to_target` above ~2.5× means the target is effectively unreachable — say so at entry.

If the capital base or the thesis moved, the 9:00 shortlist is **void** — re-rank from the live tape.

## C8. Order execution

**Whole shares only.** A fractional position cannot carry a resting stop. Unaffordable whole → unavailable; take the next candidate or no trade.

**Size to the maximum whole shares settled cash affords for the chosen candidate** — floor(settled cash ÷ ask), not 1 share by default. Only one position is ever open at a time (E2), so this is full deployment into that single candidate, not a per-trade allocation decision. Everything downstream still scales correctly: stop/target/breakeven are percentages of the fill, so dollar risk and reward scale with share count exactly as they should. Recompute the affordable quantity fresh at entry from live settled cash and the live ask — never reuse a quantity implied by an earlier affordability check.

Before placing, confirm every A1 blocking condition is clear, plus: stop present and inside the 7% cap and matching the profile · affordability against **settled** cash, not account value · order type.

Then:
- `review_equity_order` first — **a clean review proves nothing about placement** (E4). **Its response's live quote is also the last chance to re-check C10 leg 1 (v3.50): price must be strictly above the candidate's 9:30 baseline right now, not just at the earlier checkpoint read.** At or below baseline → the candidate is no longer eligible, decline and stop (do not place the order); re-rank the remaining shortlist or pass this checkpoint per C9 rather than forcing a name whose own gate has already flipped.
- **Marketable limit, never plain market.**
- **Verify the fill from the order response.** Never report an unconfirmed fill.
- **Place the protective stop immediately after the fill.**
- Report slippage against the intended price.
- State at entry: fill · **quantity and total cost** · stop price and % · target % · `mfe_per_stop` for the top two · intended exit · the falsifiable pre-commit for the next checkpoint.

## C9. Timing and selection

- **Entries are valid at any checkpoint from 9:35 through 12:00** — no preferred-window distinction inside that range; the whole window is short enough (v3.43) that lateness within it isn't itself a signal.
- **After 12:00, none** — the window is closed for new positions regardless of what's setting up (B2/B4).
- Never force a trade because the window is closing.
- Verify `all_day_tradability` before entering.
- **Price the spread:** read the actual bid/ask, **double it** for the round trip, subtract from the expected move — take it only if it still clears the target with room.
- Check the price before building a thesis. A candidate you cannot buy is not a candidate.

## C10. Momentum direction — decline a fading price, allow a confirmed reversal

**Applies to every candidate, every entry-eligible checkpoint** — commodity proxies, individual stocks, plain or leveraged, in addition to (never instead of) C1–C9. Built to catch a candidate that's fading right now without permanently locking out a genuine second-wave rally later in the same session.

**Track, per candidate, from the day's own range-based checkpoint reads (B1b, via B6's shortlist snapshot)** — not point quotes (9:30 is the first formal read; the 9:00 scan is informal/stale per C3 and does not count here):

- `session_high` — the best `bar_high` reached so far today, across all checkpoints. Advances any time a fresh interval high prints, whether or not that high survived to the interval's close.
- `session_low` — the lowest `bar_low` reached *since* `session_high` was last set. Only exists while price is currently below `session_high`; clears the instant a new `session_high` prints — a fresh high ends the pullback episode outright.

**The checkpoint chain is one continuous chronological sequence, not two separate tracks.** A C12 mini-cycle check (its T+0 read and its T+10 gate stack) is a formal checkpoint in this same chain the instant it runs, exactly like a scheduled grid slot — it feeds `session_high`/`session_low` and B6's range log the same way a 10:00 or 11:30 slot does. Nothing about being ad hoc makes it second-class for this purpose.

**All three must hold, checked fresh at every entry-eligible checkpoint (never cached):**

1. **Not currently falling.** This checkpoint's `bar_close` **strictly above** a fixed baseline price (v3.50 — was `≥`; a flat read, exactly at the baseline, is no longer a pass), for this candidate specifically — **the baseline is 9:30's price, and it moves only once: it resets to the exit's fill-timestamp price the moment any position closes (C12), for every candidate being reconsidered in that re-entry cycle, not just the one that was held.** **Re-verified against the live quote immediately before order placement (v3.50, C8), not just this checkpoint's aggregated `bar_close`** — a gate check computed several minutes before the order actually lands can already be stale by the time of the fill (2026-09-01, XOM: leg 1 passed on a checkpoint-window `bar_close` $0.05 above baseline, but live price had fallen back under the baseline by the time the order filled a few minutes later, unnoticed until after the fact). If the live quote pulled for `review_equity_order` is at or below the baseline, the candidate is no longer eligible this checkpoint — decline rather than force it (C9), even if the checkpoint's own `bar_close` passed. No other event advances it — a checkpoint that merely re-reads a candidate without an entry/exit leaves the baseline exactly where it was, even across several checkpoints (v3.46: previously "immediately prior formal checkpoint," which let a candidate's first-ever entry check drift onto whichever checkpoint ran last instead of staying anchored to 9:30 — see Current State for why this changed). Applies identically to a candidate added to the watchlist after 9:30: pull its actual 9:30 price fresh via minute-bar historicals and compare against that, never treat "whenever we started watching it" as the baseline. (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched. C12 steps 2–4 own the exact mechanics of the post-exit reset — read there for the full rule and worked example.
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** `bar_high` must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − bar_close) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

## C11. Chop filter — Efficiency Ratio, time-scaled

**Applies to every candidate at every entry-eligible checkpoint, in addition to C1–C10.** Catches a candidate that's technically up on the day and technically not falling (passes C10) but is genuinely just chopping sideways rather than trending — leveraged ETFs decay in exactly that shape (C5).

**Efficiency Ratio (ER), read from B6's maintained rolling log (v3.47) — never a fresh full-window pull re-summed by hand.** Take every log entry whose `checkpoint_time` falls inside the trailing 60 minutes (or back to 9:30, whichever is shorter): `ER = |current bar_close − oldest-in-window entry's bar_close| ÷ Σ(those entries' path_length)` — net progress over total path length. Near 1 = clean directional move; near 0 = pure back-and-forth with little net progress. Typically 4–5 log entries, not 40–90 individual minute bars. Fewer than ~20 minutes of logged window available → too little to be meaningful, gate passes by default — never block on a gap, never pretend the check ran.

**Minimum ER required to enter, scaled to how forgiving the moment should be** (early moves are naturally noisier as they establish; entries later in the — now much shorter — window are into an already-maturing move and should be held to a higher bar). **Ranges are continuous — every clock time from 9:35 to 12:00 falls in exactly one row, no gaps.** This matters beyond the regular grid: a C12 mini-cycle check can land at any minute (fill-time-anchored, not just on the quarter hour), and needs an unambiguous minimum wherever it lands:

| Checkpoint time | Minimum ER |
|---|---|
| 9:35 – 10:24 | 0.15 |
| 10:25 – 11:24 | 0.25 |
| 11:25 – 12:00 | 0.30 |

Below the window's minimum → declined as too choppy, regardless of C1–C10 all passing. This is a real, separate failure mode from C10: C10 asks "is it currently falling," C11 asks "is the recent path actually going anywhere, net."

**C11 now depends on B6's rolling log (v3.47)** — a reversal from before, when it self-supplied a fresh full-window pull independent of B6. A candidate with a real gap in its own B6 history (nothing logged since 9:35, say) simply has no window to compute ER from; same default-pass-and-flag rule above, not a special case.

## C12. Re-entry cycle — an exit restarts the entry clock, not the whole day

**Applies whenever a position closes before 12:00, regardless of why** — stop (including the 12:00 pin's near-immediate trigger, if the position is somehow re-entered and stopped again inside the same window), reversal, any other B3 exit. The moment of exit becomes an ad hoc **"9:30-equivalent,"** rather than waiting for the next regular grid slot (whatever cadence is in force there, v3.54).

1. **The exit's fill timestamp is the mini-cycle's actual "9:30-equivalent" moment — not whenever it's later discovered or read.** At the moment the exit is discovered (T+0), same turn, no new trigger needed: run the 9:30-style check (C1, if any commodity is on today's shortlist) against today's existing shortlist — the 25-name individual-stock list and any commodities already built at 9:00, not a fresh market-wide scan. Record any commodity's current day change and note which shortlist names are still holding their move. C7 re-ranks fresh here too — the capital base just changed (the position closed), which by C7's own rule voids the earlier ranking.
2. **T+10 is measured from the exit's actual fill timestamp (from the order response), never from when it happened to be noticed.** Detection lags the real fill whenever the exit fires between scheduled checkpoints — get the real fill time first, then compute `elapsed = now − fill_time`:
   - **`elapsed ≥ 10 minutes`** — the window has already passed. Run the full 9:35-style entry gate stack, C1–C11, immediately, same turn as T+0. No trigger to arm, no further wait.
   - **`elapsed < 10 minutes`** — arm one ad hoc trigger for `10 − elapsed` minutes out (the nearest possible time to exactly `fill_time + 10min`, not a flat 10 minutes from T+0) to run the gate stack then.
   Enter if a candidate clears every gate, exactly as any other entry checkpoint would. This is in addition to, not a replacement for, the regular grid triggers already armed for the rest of the day.
3. **The comparison baseline for this gate stack's first run is each candidate's price *at the fill timestamp itself*, not at whenever the check happens to execute, and not the last regular grid slot.** Pull minute-bar historicals for that exact minute, for every shortlist name — the same one fixed moment for all of them, the same way 9:30 is one fixed moment for the whole watchlist, not something recomputed per candidate. This is what C10 leg 1 ("not currently falling") and C1's baseline reading compare against for this mini-cycle's first pass — whether that pass runs immediately (the `elapsed ≥ 10` branch) or at the armed T+10 trigger (the `elapsed < 10` branch). Being "free to trade" (timing, step 2) and "what you compare against" (this step) are two separate questions — 15 minutes already elapsed since the fill clears you to act *now*, but the price you're judging "still rising since I sold" against is still the price *at the fill*, not the price at whatever minute you happened to look.
4. **After the gate stack runs, whether or not a new position was opened, resume the standard grid at its own next slot — not exit-relative.** Exit at 10:40, discovered and gated promptly → the next check is the regular 10:50 slot, then 11:00, unchanged. This mini-cycle's first read (step 3) is itself a formal checkpoint in the single chronological chain C10 tracks and B6 logs (v3.26) — the regular slot that follows it compares against *that* read's own `bar_close`, not back past it to the fill-timestamp baseline again. The fill-timestamp anchor is a one-time reference for this mini-cycle's opening comparison only, never a standing reference point afterward.

**Worked example, steps 2–4 together (this is the authority C10 leg 1 points back to; v3.52 — times updated for the two-speed cadence, logic unchanged):** a position exits (fill) at 10:32. The 10:40 grid check discovers it; only 8 minutes have passed (`elapsed < 10`), so an ad hoc trigger arms for 10:42 (`fill_time + 10min`). At 10:42 the full gate stack runs — C10 leg 1 there compares 10:42's `bar_close` against the candidate's price *at 10:32* (step 3), not against 10:40's close. Declined → the next check is the regular 10:50 slot, and *that* leg 1 compares against the 10:42 read's own `bar_close` (step 4) — not back against 10:32 again, and not against 10:40. From there it's fully normal: 11:00 vs 10:50, then the cadence widens to 15 minutes — 11:15 vs 11:00, 11:30 vs 11:15, and so on through 12:00.

Fires once per exit, not a new recurring cadence. If T+10 finds nothing that clears every gate, the book just stays flat until the next regular grid slot — same as any other declined entry.

**A chance to re-check, never a mandate to re-enter — everything else already in force still binds at full strength.** C5's "no read = no trade" and C9's "never force a trade" apply to the T+10 check exactly as hard as at 9:35; C9's 9:35–12:00 entry window (v3.54) still governs — a mini-cycle triggered late enough that `fill_time + 10min` would land past 12:00 simply finds no entry available, same as any other post-12:00 moment; A1's one-position gate is untouched. This rule only shortens *when* the next attempt happens, never *whether* one is allowed.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid (ET)

`9:00 · 9:30 · 9:35 · 9:40 · 9:50 · 10:00 · 10:10 · 10:20 · 10:30 · 10:40 · 10:50 · 11:00 · 11:15 · 11:30 · 11:45 · 12:00 · 8:00`

**No extended-hours slots.** As of v3.54 the trading day ends at 12:00 structurally — the 12:00 checkpoint's stop-pin (B2) closes whatever's open almost immediately, so there is nothing left to manage into the afternoon or evening. 8:00pm exists purely to verify tomorrow got armed (below), not to trade.

**Two-speed cadence (v3.54): 10 minutes from 9:40 through 11:00, then 15 minutes from 11:15 through 12:00.** The tighter early cadence targets the morning's most active stretch — closer to entry, closer to the fastest part of most moves, and closer to where the ratchet-breach pattern (E6) has actually bitten. 10:50 → 11:00 is itself a 10-minute gap, so the cadence hands off cleanly with no seam. ET → UTC: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5. Skip market holidays — **verify the calendar, never assume.** On an early close, end the grid at whichever of 12:00 or the early-close time comes first. **Friday arms Monday**, not the weekend.

Runs indefinitely until the governor pauses it. Never stop on your own initiative.

### Arming — primary at 12:00, backup at 8:00

**Tomorrow's full checkpoint chain gets created at the 12:00 close, right after that day's exit/report work (D3) — not held until 8:00.** Skip the weekend the same way as always — Friday's 12:00 arms Monday.

**8:00pm is a verification pass, not a second independent arming.** Check that tomorrow's chain already exists (`list_triggers`, looking for tomorrow's date). If it does, this is a non-event — stay silent per D3, nothing to report. **If it's missing or incomplete — the 12:00 arming failed or was skipped somehow — create it now, and say so explicitly**, the same way A2 already treats any past-due, still-enabled trigger as a missed checkpoint that gets done late and flagged, not silently absorbed.

Never delete either checkpoint (A2's rule, not restated here).

### Early shutdown

Flat · no resting orders · **and** no entry possible (buying power short) → delete remaining intraday checkpoints. **Keep exactly two: 12:00 close (report + primary arming) and 8:00 backup (verify tomorrow is armed; re-arm only if it isn't).** Being flat because an earlier trade already closed today is **not** by itself a reason to shut down — a later opportunity is still tradeable within the window unless one of the two conditions above is actually true.

## D2. 9:00am research — standard work

**v3.53 — sectors dropped. Individual-stock-first, market-wide; commodities are the one exception, tracked separately, never blended into the 25.**

1. **Headlines** — macro, geopolitical, overnight.
2. **Pre-market prices** across the universe and yesterday's watchlist.
3. **Earnings reactions** from last night's after-close reporters.
4. **Market-wide magnitude scan — individual stocks, no sector scoping.** Run the scanner's `% Change` gainers filter (C3's threshold, `≥0.75%`) across the whole market, with a liquidity floor (average volume — `FILTER_TYPE_AVERAGE_VOLUME`, same mechanism as any other scan) to keep the results real and tradeable rather than illiquid noise. No `Sector` filter this time — the point is to find whichever individual names are actually moving today, wherever they sit.
5. **Separately, check the fixed commodity list (E3) for a real move** — the one category still allowed a group vehicle. Energy, gold, silver, copper, uranium, and broader materials each get a quick day-change read on their plain proxy; a commodity only makes today's list provisionally on that premarket read — real qualification still needs C1's formal 9:30→9:35 test and C6's two legs to clear live, same discipline as any other candidate, never assumed from the headline alone.
6. **Confirm settled buying power and unsettled funds.** Recompute deposited capital and the floor; report either if changed.
7. **Write the watchlist — 25 individual-stock names, plus whichever commodities cleared step 5, tracked as a separate short list, not counted against the 25.**
   - **Rank the scan's results by day-change magnitude.** Fill the 25 slots from the top down, but names that carry an existing single-stock leveraged ETF wrapper (E3's lookup table) get priority fill over plain stocks when both clear C3's 0.75% floor — matches C4's own preference for the leveraged vehicle once a name is already a candidate, applied one step earlier at watchlist-build time. A real mover without a wrapper still fills a slot on its own merit (C4 rank-2) once the wrapper-carrying names are placed; never pad the list with a name that isn't a genuine mover today just to reach 25 — a thinner list is a correct outcome, per C5's "no read = no trade."
   - **No pre-grouping, no diversity requirement.** Unlike the retired sector structure, there's no rule capping how many of the 25 can come from one theme (crypto, AI infrastructure, whatever is actually moving) — breadth of *individual* names, not breadth of *themes*, is what the 25 slots buy; C10/C11/C7 still do the real filtering at entry time regardless of how many names share a narrative.
   - Profile every individual just-in-time (B1); mark affordability second, never first — include unaffordable names, they measure what capital is costing. The 25 feed C3 (major-move gate) and C4's rank-1/rank-2 individual-stock track. Any commodity that cleared step 5 feeds C1/C6 and C4's rank-1c/2c track separately.
8. **Refresh the live-context block (E5).** Commit and push.

## D3. Reporting

- **Losses as plainly as gains.** No spin. Never claim edge from a small sample.
- **Verified fills only.** P&L in dollars, percent **and R**. Slippage both sides.
- **Correct your own errors promptly**, including ones that look bad.
- **Most checkpoints are non-events — stay silent.** No "checked, nothing to do."
- **When you do report, state the outcome, not the reasoning already committed to the file.** Full gate-stack reasoning belongs in `archive/trades.csv`'s notes field and E5 — both durable, both re-readable on demand. The chat reply is a line or two: what happened, the key number. It does not re-narrate reasoning that's already been written down. **This session runs every checkpoint indefinitely — Robinhood's connector grant can't be replicated in a fresh session, confirmed 2026-08-25, so there is no periodic reset.** Every word written into a reply becomes permanent, compounding context for the life of the system; duplicating file content into prose is a real, ongoing cost, not a one-time one.
- **Report immediately:** entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a notable setup declined.
- **A no-trade day gets no evening message.**
- **Friday 12:00pm always reports**, trades or not — balance, every trade, loss-streak count, what was declined and why, any rulebook change. The guaranteed heartbeat. (Moved here from 8:00pm under D1's arming restructure — 8:00 is now a silent-unless-broken backup check, even on Fridays; the real weekly data already lives at the 12:00 close, not eight hours later.)

**At exit, append one row to `archive/trades.csv`** — the live append-only log. Compute `r_multiple = (exit% − entry%) ÷ initial_stop_pct` **now**, while the entry stop is known — it cannot be reconstructed later. Set `counts_toward_streak` and `counts_toward_expectancy` (`no` only for a mechanical abort or a funded execution test) and say why in `notes`. **Append-only — never edit a past row**; a mistake gets a correcting row.

**Measurement:** expectancy per trade in R is primary. `Expectancy = (win rate × avg winner R) − (loss rate × avg loser R)`. Win rate and avg winner/loser are descriptive only, never pass/fail. Exclude `counts_toward_expectancy=no` rows and name them. **State the effective sample size, not the row count.**

## D4. Post-exit review — the improvement loop

**30 minutes after every exit**, check the price and say plainly whether the exit was well-timed or early. Same for a candidate declined.

If a pattern suggests a rule is causing early exits or missed continuation, name the rule and propose the change. **Look for a repeated pattern — never rewrite a rule from one trade.** Changing a rule right after a single loss under it is fitting noise, not learning.

---

# PART E — REFERENCE (pull on demand)

## E1. Circuit breaker

**3 consecutive losing closed trades → stop entering until the governor clears it.**

**A loss is a closed trade with `pnl_pct_position` worse than −1.0%** (v3.49 — was "any negative P&L, however small"). A negative print at or above −1.0% is a scratch, not a loss for streak purposes — it resets the streak to zero exactly like a winner would, it just doesn't itself extend one. Consecutive **closed trades**, not days — a winner or a scratch anywhere resets to zero; only a run of sub-(−1.0%) trades builds the count. Rows marked `counts_toward_streak=no` are excluded outright (a mechanical abort is not a trade). **Compute from the trade log, never from memory.**

**Why a magnitude threshold instead of classifying by `exit_reason`:** a small negative print is very often execution friction — a mechanically-forced early exit on a real move, a spread eaten by slippage — not a signal-quality failure, and the two look identical to a bare "negative P&L" count. Classifying case-by-case by `exit_reason` was considered and rejected: it requires a judgment call at every trade about which reasons count as "mechanical," and that judgment is exactly the kind of thing this system tries to make structural rather than discretionary. A flat magnitude cutoff needs no classification and no memory of precedent — it reads directly off `pnl_pct_position`, already in every row.

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

## E3. Vehicle map — commodity groups, and individual-stock leveraged wrappers

**v3.53 — split in two. Commodities are the only category that still gates as a group (C1/C6); everything else is an individual stock judged on its own move, with this table used only to look up whether a leveraged wrapper exists for it — never to confirm against a proxy.**

**Commodity groups — plain and leveraged vehicles together, C1/C6 apply:**

| Instrument(s) | Commodity |
|---|---|
| XLE · GUSH · ERX · ERY · NRGU · DRIP · OILU · OILD | Energy / E&P complex |
| USO · UCO · SCO | Crude oil (direct) |
| UNG · BOIL · KOLD | Natural gas |
| GDX · NUGT · DUST · GDXU · JNUG · JDST | Gold miners |
| GLD · UGL · GLL | Gold (direct) |
| SLV · AGQ · ZSL · SIL · SILJ | Silver |
| COPX · CPER | Copper |
| URA · URNM | Uranium |
| XLB · UYM · SMN | Broader materials/mining ("or such," per the governor's own framing) |

**Individual-stock leveraged-ETF lookup — no proxy, no confirmation gate; exists only to answer "does this mover have a wrapper":**

| Wrapper(s) | Underlying stock |
|---|---|
| NVDL · NVDX · NVDU | NVDA |
| AMDL | AMD |
| MUU | MU |
| TSMX · TSMU | TSM |
| SMCX | SMCI |
| AVGX | AVGO |
| TSLL | TSLA |
| CONL | COIN |
| MSTX | MSTR |

**Retired outright, v3.53 — no longer tradeable vehicles under "individual stocks and individual leveraged ETFs, commodities excepted":** SOXL/SOXS/USD, TQQQ/SQQQ/FNGU/BULZ/TECL, SPXL/UPRO/SPXS/SDOW/UDOW, TNA/TZA, LABU, YINN/YANG, KORU, IBIT, BITX/BITU/ETHU/ETHT, UVIX/VXX — every one was a broad-sector, index, or crypto-group leveraged product with no single-company underlying, or (IBIT) a proxy that no longer confirms anything. **Crypto is individual-stock-only, governor instruction 2026-09-02**: RIOT, MARA, CLSK trade as plain stocks now, no group wrapper; COIN and MSTR keep their real single-stock wrappers (CONL, MSTX) above, unaffected.

**Individual stock not on the wrapper map → trade it plain (C4 rank-2).** There is no proxy fallback anymore; a mover without a listed leveraged wrapper is just a plain-stock candidate, not a reason to substitute some other instrument.

### Known leveraged vehicles

**Index** TQQQ · SPXL · UPRO · TNA · UDOW — **Sector** SOXL · TECL · GUSH · ERX · FNGU · BULZ · LABU · NUGT · GDXU · NRGU · YINN · KORU · USD — **Single-stock** NVDL · NVDX · TSLL · CONL · MSTX · SMCX · MUU · AMDL · TSMX — **Inverse** SQQQ · SOXS · SPXS · SDOW · TZA · DUST · ERY · YANG · ZSL · JDST · SCO · DRIP · KOLD — **Commodity/materials** AGQ · UGL · GLL · JNUG · SIL · SILJ · UCO · BOIL · OILU · OILD · UYM · SMN · COPX · CPER · URA · URNM · LIT · REMX · SLX — **Crypto** BITX · BITU · ETHU · ETHT · RIOT · MARA · CLSK — **Volatility** UVIX · VXX, event/intraday only, never a hold.

This list is a **convenience index, not a boundary** — any liquid name may be traded (C4). Equities and ETFs only: **no options**, no short selling.

## E4. Capability verification

**A capability is verified only by an order response or a successful call.** Never by a review, documentation, or inference from a similar case. A refusal is evidence too — record the exact error string verbatim. Make the smallest call that proves the primitive before the one that depends on it.

Never commit capital or write policy on a mechanism not seen to succeed.

## E5. Live context — dated, refreshed at 9:00, replaced wholesale

A slot, not a fixture. When the driver stops mattering, replace it entirely — its triggers were specific to it. **Stale context asserted confidently is worse than none.**

**Structured, not narrated.** Log facts as compact bullets grouped by checkpoint/event — numbers, gate results, times — not flowing prose paragraphs. Same information, cheaper to write and cheaper to re-read within the day (Part E is pulled on demand, but the pull still costs whatever E5 has grown to since 9:00).

**Thursday 2026-09-03, 9:00 research** (run on time, ~9:00–9:05 ET; first live day under v3.54 — compressed grid, entry moves to 9:35, close moves to 12:00; also the first live run of v3.53's market-wide individual-stock scan workflow):

- **Headlines: hawkish Fed, high yields, Iran tension still simmering.** Fed rate-hike odds for the Sept 16 meeting sit at 60–66% (CME FedWatch) after Chair Warsh's Jackson Hole remarks leaned hard on inflation (12-month PCE 3.7%) over the labor side; 10-year yield ~4.8%, 30-year >5%, both multi-year highs. ADP private payrolls +38K in August, weakest since January, hasn't moved hike odds. Iran/Jordan military exchange from 9/2 still live in the backdrop (Trump: "hit them hard") but crude actually **retreated** overnight (WTI ~$90.70, -0.34%) — not a fresh energy catalyst. Today's data: flash S&P services PMI (9:45 ET), ISM services PMI (10:00 ET), ahead of Friday's jobs report. Earnings after tonight's close: CIEN, ZS, LULU, PATH, CPB — none of these cleared today's magnitude scan, so no same-day conflict for anything on this list yet.
- **Market-wide individual-stock scan (v3.53 D2 step 4), run live: 105 names cleared ≥0.75% day-change with the ≥10M average-volume liquidity floor.** New saved scan `4ceac364-d887-4afc-b3e1-7cfe991001e1` ("D2 market-wide individual-stock gainers"), asset type = STOCK only. An ad hoc $50M market-cap floor was applied on top of the scan's own filters before ranking (excluding thin/shell-looking names: GIPR, DAIC, GPUS, RITR, ZONE, MTNB, IVDA, GSUN, AIXI, GCTK) — flagged explicitly as an unofficial judgment call, not a D2 rule.
- **Governor override, ~9:15 ET: that floor is rescinded — every name that mechanically cleared the scan is a viable shortlist candidate, full stop.** No pre-filtering by market cap, share price, or "shell" appearance at research time; C1/C10/C11 (trend/chop) and C8/C9 (spread, affordability, tradability) remain the real, live filters at entry, same as they are for every other name — this just stops research-stage judgment from removing a name before those gates get a chance to. All 9 previously-excluded names above are back on today's shortlist. **Also explicitly added: the 5-name sub-$5 premarket-momentum list** — GIPR (+48.1%, 0.8x rel-vol), GPUS (+10.0%, 3.6x), GPRO (+2.4%, 7.3x), RITR (+5.9%, 1.3x), CAN (+10.1%, 0.6x, already in the top 25 below) — all five now formal candidates, not a side-list.
- **Real theme today: precious/industrial metals + uranium, not energy.** Commodity proxies (D2 step 5, premarket reads): **XLE +0.20%** (weak, not a mover — matches crude's overnight retreat) · **GLD +2.20%** · **SLV +1.79%** · **COPX +2.58%** · **URA +1.94%** · **XLB +0.49%** (modest, likely just riding the metals names within it). This is corroborated independently by the individual-stock scan itself — five metals/mining names (HL, AG, CDE, EQX, B/Barrick) plus copper (FCX) and uranium (DNN) all cleared the 0.75% floor and rank inside today's own top 16 by magnitude, without being solicited by the commodity check. **Gold/silver/copper/uranium go on today's provisional commodity list; energy does not.** Real C1 qualification (9:30→9:35 test) and C6's two legs still happen live — this is the premarket read only, per D2 step 5's own caveat.
- **Today's 25-name individual-stock watchlist, ranked by day-change magnitude** (symbol, %chg, wrapper note where one exists per E3):
  1. CAN +10.14% · 2. CYCU +5.92% · 3. IAUX +5.68% · 4. PURR +4.51% · 5. HOOD +4.46% · 6. BTG +4.44% · 7. HL +4.38% · 8. AG +4.34% · 9. CDE +4.11% · 10. CPRT +4.10% · 11. EQX +4.04% · **12. MSTR +3.90% (leveraged wrapper MSTX exists — C4 rank-1 track)** · 13. OPEN +3.57% · 14. B (Barrick) +3.47% · 15. DNN +3.42% · 16. NOW +3.31% · 17. RDW +3.09% · 18. COMP +2.93% · 19. BMNR +2.82% · 20. CRCL +2.82% · 21. RKLB +2.81% · 22. FCX +2.76% · 23. BTDR +2.74% · 24. NVO +2.69% · 25. ORBS +2.67%.
  No other name in the 25 carries a single-stock leveraged wrapper per E3's lookup table (NVDA/AMD/MU/TSM/SMCI/AVGO/TSLA/COIN all present in the raw 105 but none cleared today's top 25 by magnitude — TSLA only +1.65%). No pre-grouping applied (v3.53) — metals/miners dominating the top of the list is a real, unforced reflection of where the day's move actually is.
- **Buying power $232.14, unsettled funds $0** (`get_portfolio`/`get_accounts`, limited-margin account, no pending deposits). All-time realized P&L $31.30 over 20 broker-side closing trades (`get_realized_pnl`, span=all) → deposited ≈$200.84, floor ≈$100.42, not binding. **Loss streak: 0 of 3** — most recent governor clearance 2026-08-31; both trades since (XOM 9/1, NUGT 9/2) closed as wins.
- **Position: flat, no resting orders** (`get_equity_positions`/`get_equity_orders`, verified).
- Profiling (`tools/profile.py`) and affordability marking deferred to the 9:30/9:35 live re-checks per D2 step 7 — **today's full shortlist is now all 105 scan names (not just the top-25-by-magnitude cut) plus the 5 sub-$5 momentum names plus the four commodity proxies** (gold/silver/copper/uranium), per the governor override above. Full 105-name list is live via `run_scan` on scan `4ceac364-d887-4afc-b3e1-7cfe991001e1` — not re-pasted here to keep this section a targeted read; the top-25-by-magnitude table above is still a fair starting point for ranking, it's just no longer the *complete* candidate set.

**9:30 observation — C1 Gate-1 baseline recorded (watchlist only, no new scan).** State check: flat, no resting orders (`get_equity_orders`, most recent order still 9/2's NUGT exit).

- **C1 baseline (9:30, first of two fixed observations): all four commodity proxies confirm the premarket read, now with real regular-hours prints.** GLD +1.91% ($410.465 vs $402.78 close) · SLV +1.56% ($59.99 vs $59.07) · COPX +2.11% ($91.795 vs $89.90) · URA +2.48% ($45.42 vs $44.32). All comfortably positive — leg 1 of C1 (positive at 9:30) clears for all four; leg 3 (9:35 not below this baseline) will decide at the next checkpoint.
- **Confirming complex still holding at the open**, same names flagged at 9:00: HL +3.76%, AG +2.85%, CDE +2.43%, EQX +3.48% (silver/gold miners) · FCX +1.38%, DNN +3.18% (copper, uranium). Breadth intact, nothing rolled over between premarket and the open.
- **Energy stays excluded** — XLE +0.15% at the open, essentially flat, consistent with the premarket read (+0.20%) and yesterday's crude retreat. Not a candidate.
- No new scan run (C1's own rule) — the 105-name-plus-sub-$5 shortlist from 9:00 (governor-expanded) stands unchanged into the 9:35 entry checkpoint.

**9:35 entry — ENTER MSTX, 15 shares @ $14.6499 fill.** State check: flat, no resting orders (verified before placing).

- **C1 second observation: only GLD and URA still clear the full 9:30→9:35 test.** GLD +1.95% (9:35) vs +1.91% (9:30, not below — passes) · URA +3.41% vs +2.48% (passes, extending). **SLV and COPX fail leg 3** — both still positive on the day but pulled back below their own 9:30 reading (SLV +1.44% vs +1.56%; COPX +1.39% vs +2.11%) — no entry in a silver- or copper-leveraged vehicle this checkpoint (late-entry clause still open later if either re-exceeds its 9:30 print).
- **The gold-miners complex rolled over hard in the 5 minutes between 9:30 and 9:35 — GDX (NUGT's actual proxy, not GLD) fell from $100.25 (9:30) to $99.95, failing C10 leg 1.** Individually, HL, AG, CDE, EQX, FCX, and Barrick (B) all did the same — every one below its own 9:30 print by 9:35, despite still being positive on the day. **Declined NUGT and every individual miner/copper name on that basis** — this is exactly the kind of quick-pop-then-fade the system has flagged before (E6); C10 correctly kept all of them out rather than chasing a stale reading.
- **DNN (uranium miner, plain stock, no wrapper) barely cleared C10** ($3.365 vs $3.3224 9:30 baseline, a ~1.3% margin) — thin enough to match the exact shape that produced UEC's loss in this week's buffer backtest. Passed over in favor of a cleaner signal rather than force a marginal entry.
- **MSTR cleared everything with real margin.** C3: +5.53% day change at 9:30, +7.21% by placement time. C10 leg 1: $130.00 (9:35 quote) vs $128.42 (9:30 baseline) — comfortably above, leg 2 auto-satisfied (price at/near session high, no pullback active). C11: ER 0.899 computed directly off the six 9:30–9:35 one-minute closes (net progress $2.50 / path length $2.78) — far above the 9:35–10:24 bracket's 0.15 minimum. **C5 catalyst, named and same-day**: B. Riley raised MSTR's price target to $175 from $155 (maintained Buy), published 8:01 AM ET today — an idiosyncratic, MSTR-specific catalyst, not just a crypto-beta ride (Bitcoin itself only +0.35–1.1% overnight). C4: MSTX wrapper exists — rank-1 track.
- **Profiled MSTX** (`tools/profile.py`, 45 daily sessions): stop 6.06%, target 9.08%, stall threshold 0.86%, **mfe_per_stop 0.944**. C7: sole survivor after C1/C10 eliminated the commodity vehicles and the rest of the miners complex — no ranking contest needed.
- **Order execution**: reviewed at $14.42 ask, repriced twice as the tape moved fast (ask ran to $14.65, then $14.72, in under 90 seconds) — final marketable limit $14.85, filled **$14.6499** (price improvement, $0.20/sh better than the limit). 15 shares (floor($232.14 buying power ÷ $14.72 live ask) = 15), total cost $219.75. **C10 re-verified live immediately before placement** (v3.50/C8): MSTR $132.08 (+7.21%), well clear of the $128.42 baseline. **Stop placed and confirmed resting**: stop_market, 15 sh, **$13.76 (−6.06%)**, confirmed via `get_equity_orders` (state=`confirmed`) — no E6 placement-glitch this time. Target 9.08% (~$15.97), `mfe_per_stop` 0.944. **Pre-commit for 9:40**: expect `bar_close` to hold at/above the trail level; a close back below MSTR's own 9:30 baseline ($128.42) would be the falsified case for the "not currently falling" read that got it in.

**9:40 management — HOLD MSTX, stop ratcheted up.** State check: 15 sh MSTX, `shares_held_for_sells=15`. B1b since-entry pull (13:39–13:41 UTC): `run_high` (entry-anchored) touched **$14.7598** at 13:40 ET.

- `candidate_stop = run_high × (1 − 2×0.86%) = 14.7598 × 0.9828 = $14.5066`. `new_stop = max($13.76, $14.5066) = $14.51` — a real upward move. Cancelled the $13.76 stop (verified cancelled), placed and verified resting: stop_market, 15 sh, **$14.51**, confirmed via `get_equity_orders` (state=`confirmed`), safely below the live quote at placement ($14.705).
- B3 exits checked: no reversal (no named level broken — day change still strongly positive), no R/R flip, no event, not near close. **Hold.**
- **Pre-commit for 9:50**: the $14.51 stop is now the live falsifiable line — a close back through it is the exit.

**EXIT MSTX, 15 sh @ $14.5049, resting stop triggered at 9:48:36 ET — fired on its own between checkpoints, ~2 minutes before the scheduled 9:50 check.** Not an E6 incident: the $14.51 stop was correctly computed and confirmed resting at 9:40; price simply fell through it (true low $14.504 at 13:48 UTC) and the resting order did exactly its job. Net: **-$2.18, -0.99% on the position, r=-0.163** — a small loss, the stall-ladder cost of a quick pullback before the 9:40 ratchet could lock in real profit. True MAE/MFE for the full ~9-minute hold: MFE +1.43% ($14.860, 13:43 UTC), MAE +1.00% ($14.504, the exit bar itself). Logged to `archive/trades.csv`, `exit_reason=trailing_stop_hit`. **Loss streak: 1 of 3** — first loss since 8/31 (GUSH/XOM/NUGT ran three straight wins).

**C12 mini-cycle — fill timestamp 13:48:36 UTC is the new "9:30-equivalent" for re-entry purposes.** T+0 baselines recorded (13:48 UTC minute-bar close, for every shortlist name being watched most closely): **MSTR $131.345 · GLD $408.690 · SLV $59.630 · COPX $90.270 · URA $45.780.** At T+0 (~13:52 UTC, ~3.5 min post-fill): MSTR $131.780 (above, +0.33%) · GLD $409.040 (above, +0.09%) · SLV $59.775 (above, +0.24%) · COPX $90.380 (above, +0.12%) · URA $45.750 (**below** baseline, -0.07%) — promising but too early to act on; C12's own rule reserves the actual entry decision for the T+10 gate stack, not this initial read. **Elapsed since fill < 10 minutes**, so per C12 step 2 an ad hoc trigger is armed for `fill_time + 10min` (13:58:36 UTC / 9:58:36 ET, `trig_012cGYhQ84APieCBUUPqVUCu`) rather than running the full gate stack now. Regular grid (10:00 management) still runs on its own schedule regardless.

**C12 T+10 gate stack — RE-ENTER MSTX, 15 sh @ $14.7379 fill.** Full gate stack re-run against fill-timestamp baselines (13:48 UTC):

- **C10 leg 1**: MSTR $132.46 vs $131.345 baseline (comfortably above) — passes; same read at every commodity proxy (GLD/SLV/COPX all above their fill-time baseline; URA still marginally below, excluded). **Individual miners mixed**: HL (+0.21%) and Barrick (+0.31%) passed, AG/EQX/FCX/DNN failed (flat-to-negative since fill). **GDX (NUGT's actual proxy) passed C10 leg 1** ($99.15 → $99.55, +0.41%) but leg 2 (bounce quality) wasn't the deciding factor — **C11 killed it**: ER computed fresh over the full 9:30-to-now window came back **GDX 0.146, below the 9:35–10:24 bracket's 0.15 minimum** — the gold-miners complex is still just chopping/consolidating, not trending, confirming the same read from the 9:35 decline. **MSTR's ER came back 0.285**, comfortably clear. C10 leg 2 (bounce off session low) also confirmed for MSTR: session high $133.01 (13:43 UTC), session low since $130.90 (13:49 UTC), current bar_high $132.19 clears $130.90×1.0086=$132.03.
- **C5 catalyst unchanged and still same-day**: B. Riley's $175 PT (from $155) — nothing has invalidated it in the 10 minutes since the first entry.
- **C7**: MSTX the sole real survivor after GDX/NUGT failed C11 and the individual miners split — no ranking contest.
- **C8 execution**: reviewed at $14.75 ask, marketable limit $14.90, filled **$14.7379** (price improvement). 15 sh (floor($229.96 ÷ $14.75) = 15), total cost $221.07. Live MSTR re-verified immediately before placement: $132.46, well clear of baseline. **Stop placed and confirmed resting**: stop_market, 15 sh, **$13.85 (−6.06%)**, confirmed via `get_equity_orders` (state=`confirmed`). **Pre-commit for 10:00**: expect `bar_close` to hold at/above the trail; a close back below MSTR's $131.345 fill-timestamp baseline would be the falsified case.

**10:00 management — HOLD MSTX, stop ratcheted up.** State check: 15 sh MSTX, `shares_held_for_sells=15`. B1b since-entry (re-entry-anchored) pull (14:00 UTC): `run_high` touched **$14.82**.

- `candidate_stop = run_high × (1 − 2×0.86%) = 14.82 × 0.9828 = $14.5652`. `new_stop = max($13.85, $14.5652) = $14.57` — a real upward move. Live quote checked immediately before acting ($14.630) — safely above the candidate, no E6 risk. Cancelled the $13.85 stop (`get_equity_orders` initially showed `pending_cancelled`, re-checked and confirmed true `cancelled`), placed and verified resting: stop_market, 15 sh, **$14.57**, confirmed via `get_equity_orders` (state=`confirmed`), safely below a fresh quote taken right before placement ($14.650).
- B3 exits checked: no reversal (MSTR still well above its $131.345 fill-timestamp baseline), no R/R flip, no event, not near close. **Hold.**
- **Pre-commit for 10:10**: the $14.57 stop is now the live falsifiable line — a close back through it is the exit.

**10:10 management — HOLD MSTX, stop ratcheted up sharply.** State check: 15 sh MSTX, `shares_held_for_sells=15`, stop confirmed resting at $14.57 going in. B1b since-10:00 pull (14:00–14:10 UTC): `bar_high` reached **$15.07** (14:10 UTC bar) on a strong continuation — MSTX ran from $14.73 to $15.02+ over the ten minutes, volume elevated throughout (no single-bar spike-and-fade shape).

- Live quote checked immediately before acting: **$15.15/$15.17** (14:15:17 UTC) — already above the last bar's high, so `run_high = max($14.82 prior, $15.07 bar_high, $15.15 live) = $15.15`, using the freshest genuine print rather than a stale bar.
- `candidate_stop = run_high × (1 − 2×0.86%) = 15.15 × 0.9828 = $14.8894`. `new_stop = max($14.57, $14.8894) = $14.89` — a large upward move (+$0.32, well above `min_stop_move_pct`). Cancelled the $14.57 stop (verified `cancelled`), re-checked live price ($15.15, safely clear), placed and verified resting: stop_market, 15 sh, **$14.89**, confirmed via `get_equity_orders` (state=`confirmed`).
- B3 exits checked: no reversal (MSTR $133.96, still well above its $131.345 fill-timestamp baseline and its own session high), no R/R flip (stop now locks in real gain — $14.89 vs $14.7379 fill, position is risk-free), no event, not near close. B5 headline check not yet due (next due ~10:35, one hour from 9:35 entry). **Hold.**
- **Pre-commit for 10:20**: the $14.89 stop is now the live falsifiable line — a close back through it is the exit. This stop already sits above the $14.7379 entry fill, so from here the trade cannot close as a loss on this leg.

**10:20 management — HOLD MSTX, stop ratcheted up again, third straight raise.** State check: 15 sh MSTX, `shares_held_for_sells=15`, stop confirmed resting at $14.89 going in. B1b since-10:10 pull (14:10–14:20 UTC): `bar_high` reached **$15.2575** (14:17 UTC bar) — MSTX kept extending, now +4% over the ten minutes on top of the prior leg's move, still with real volume on every bar (no thin spike).

- Live quote checked immediately before acting: **$15.38/$15.39** (14:26:58 UTC), again above the last bar's high — `run_high = max($15.15 prior, $15.2575 bar_high, $15.38 live) = $15.38`.
- `candidate_stop = 15.38 × 0.9828 = $15.1155`, rounded to **$15.12**. `new_stop = max($14.89, $15.12) = $15.12` — another real upward move (+$0.23). Cancelled the $14.89 stop (verified `cancelled`), re-checked live price ($15.38, safely clear), placed and verified resting: stop_market, 15 sh, **$15.12**, confirmed via `get_equity_orders` (state=`confirmed`).
- B3 exits checked: no reversal (MSTR $135.30, still climbing, well above its $131.345 fill-timestamp baseline), no R/R flip (locked gain now $0.38/sh above fill, ~2.6% on the position), no event, not near close. B5 headline check not yet due (next due ~10:35). **Hold.**
- **Pre-commit for 10:30**: the $15.12 stop is now the live falsifiable line — a close back through it is the exit.

**10:30 management — HOLD MSTX, stop ratcheted up again, fourth straight raise.** State check: 15 sh MSTX, `shares_held_for_sells=15`, stop confirmed resting at $15.12 going in. B1b since-10:20 pull (14:20–14:30 UTC): `bar_high` reached **$15.57** (14:30 UTC bar) — MSTX kept extending with no pullback of any real size across the whole ten minutes, volume strong throughout (one 65k-share bar at 14:26).

- Live quote checked immediately before acting: **$15.645/$15.655** (14:30:39 UTC), again above the last bar's high — `run_high = max($15.38 prior, $15.57 bar_high, $15.645 live) = $15.645`.
- `candidate_stop = 15.645 × 0.9828 = $15.3759`, rounded to **$15.38**. `new_stop = max($15.12, $15.38) = $15.38` — another real upward move (+$0.26). Cancelled the $15.12 stop (verified `cancelled`), re-checked live price ($15.645, safely clear), placed and verified resting: stop_market, 15 sh, **$15.38**, confirmed via `get_equity_orders` (state=`confirmed`).
- B3 exits checked: no reversal (MSTR $136.39, still climbing, well above its $131.345 fill-timestamp baseline), no R/R flip (locked gain now $0.64/sh above fill, ~4.3% on the position), no event, not near close. B5 headline check not yet due (first due ~10:35, one hour after the 9:35 entry). **Hold.**
- **Pre-commit for 10:40**: the $15.38 stop is now the live falsifiable line — a close back through it is the exit.

**10:40 management — HOLD MSTX, stop unchanged (min-move gate held).** State check: 15 sh MSTX, `shares_held_for_sells=15`, stop confirmed resting at $15.38 going in. B1b since-10:30 pull (14:30–14:40 UTC): `bar_high` reached **$15.71** (14:32–14:33 UTC), then pulled back — live quote now **$15.47/$15.49** (14:41:06 UTC), off the highs but still well above the fill.

- `run_high = max($15.645 prior, $15.71 bar_high, $15.47 live) = $15.71`. `candidate_stop = 15.71 × 0.9828 = $15.4398`. Move from the current $15.38 stop would be only **0.39%**, below MSTX's `min_stop_move_pct` (1.00%, capped at the ceiling per B1) — **no structural level nearer, so per B2 the stop is left unchanged rather than incurring a cancel/replace for a sub-threshold move.** Verified via `get_equity_orders` that the $15.38 stop is still resting, state=`confirmed` — untouched, no unprotected gap this checkpoint.
- **B5 hourly headline check (first due since the 9:35 entry, now performed)**: pulled `get_equity_news` for MSTX (no articles) and MSTR. Nothing new and MSTR-specific beyond the already-known 8:01 AM B. Riley $175 PT (maintained Buy) — Saylor's 5:42 AM reserve-capital remark is same-day but not a fresh tradeable catalyst, and no negative headline. **Catalyst still stands.**
- B3 exits checked: no reversal (MSTR $135.81, still comfortably above its $131.345 fill-timestamp baseline despite its own pullback from $136.44), no R/R flip, no event, not near close. **Hold.**
- **Pre-commit for 10:50**: the $15.38 stop is still the live falsifiable line — a close back through it is the exit.

**10:50 management — HOLD MSTX, stop ratcheted up sharply, cleared $16.** State check: 15 sh MSTX, `shares_held_for_sells=15`, stop confirmed resting at $15.38 going in. B1b since-10:40 pull (14:40–14:50 UTC): the position kept extending hard — `bar_high` reached **$16.055** (14:49 UTC), the position's first print above $16, on a strong volume bar (54k shares).

- Live quote checked immediately before acting: **$15.95/$15.96** (14:50:40 UTC), a modest pullback off the $16.055 top but still well clear. `run_high = max($15.71 prior, $16.055 bar_high, $15.95 live) = $16.055`.
- `candidate_stop = 16.055 × 0.9828 = $15.7789`, rounded to **$15.78**. `new_stop = max($15.38, $15.78) = $15.78` — a real move (+2.6%, clears the min-move gate easily this time). Cancelled the $15.38 stop (verified `cancelled`), re-checked live price ($15.95, safely clear), placed and verified resting: stop_market, 15 sh, **$15.78**, confirmed via `get_equity_orders` (state=`confirmed`).
- B3 exits checked: no reversal (MSTR $138.30, new highs, well above its $131.345 fill-timestamp baseline), no R/R flip (locked gain now **$1.04/sh above fill, ~7.1% on the position**), no event, not near close. **Hold.**
- Note: this is the last 10-min-cadence slot per the v3.54 grid — **11:00 reverts to 15-min cadence.**
- **Pre-commit for 11:00**: the $15.78 stop is now the live falsifiable line — a close back through it is the exit.

## E6. Known issues — backlog, not yet fixed

**Stop-order placement can fail silently, in more than one way, and the pattern is escalating rather than resolving.**

*Failure mode 1 — silent zero-fill cancellation.* Comes back `cancelled` with zero fill and no error message. First observed 2026-08-24 (twice, MSTX, both resolved on one retry, no real exposure). Escalated 2026-08-25: SMCX's 10:00 checkpoint hit it three times in a row on the same placement — price moved through the intended stop level during the unprotected gap, forcing a manual marketable-limit exit. Real exposure, not a near-miss.

*Failure mode 2 — outright rejection when the stop price is at/above the live market.* First identified 2026-08-25, UUUU's 11:30 checkpoint: the correctly-computed new stop ($15.93) was placed a moment after price had already pulled back below it ($15.87) — the order came back `rejected`, not `cancelled`, with a clear enough pattern to name the likely cause: the broker won't accept a sell-stop whose trigger condition is already satisfied at placement time (it should really be an immediate market order, not a resting stop, and the API appears to refuse rather than convert it). The follow-on manual exit had its own near-miss: the first marketable-limit attempt used a bid that had already gone stale by the time it posted, landed as a passive (non-marketable) resting order instead of an immediate fill, and had to be cancelled and re-priced against a fresh quote before it actually executed — a reminder that "marketable" only holds for as long as the quote it was priced against.

**Mitigation is manual, not systemic — and the governor has explicitly reviewed that trade-off and accepted it, 2026-08-25.** After every stop placement, verify it actually landed via `get_equity_orders` before considering the position protected; retry immediately if it didn't, and if the retry keeps failing, re-check the live price before retrying blind — a rejection can mean the stop level itself is stale, not just that the placement call needs repeating. This has caught every incident so far (2026-08-24 ×2, 2026-08-25 ×2, one per failure mode) with zero losses attributable to the glitch itself — both 2026-08-25 incidents closed as real wins (SMCX +$4.25, UUUU +$6.86), not losses. Governor's read: today's names (SMCX, UUUU) are fundamentally fast-moving instruments, some order-placement friction against that kind of tape isn't itself alarming, and the current catch-verify-retry-or-exit process is working — **keep doing what's been done**, not a directive to build the automatic wrapper urgently.

**Still worth building eventually, no longer treated as urgent.** An automatic retry-and-verify wrapper around stop placement — place, confirm via a follow-up read, re-check price before a blind retry, all without waiting on a manual catch — remains a real improvement over a human-speed read-decide-act loop inside a moving market. But per governor sign-off, this stays a nice-to-have on the backlog, not a same-day priority. Revisit if a future incident actually produces a loss (not just forced friction on a winning trade), or if the failure rate climbs further.

**Watch item hit its third occurrence, 9/2 — raised for real B2 discussion, per the governor's own 9/1 instruction (below, kept for the history).** AFRM (8/28), GUSH (8/31), now **NUGT (9/2)**: three-for-three on the identical shape — `run_high` advances between checkpoints, then the next checkpoint's `candidate_stop` computes *above* live price because the tape already pulled back before that checkpoint ran. NUGT's instance happened at the *second* post-entry checkpoint (not the very first, like AFRM/GUSH) and was independently verified not to be an artifact of that checkpoint's trigger running late — the breach would have hit at an on-time 14:15 read too, since the peak was already 8 minutes old by then. Every instance so far has been handled correctly in the moment (cancel the stale stop, exit immediately via marketable limit) and every instance has closed as a real win (SMCX/UUUU-style, not a loss) — the mechanism isn't losing money, it's giving back real open profit between a checkpoint-frequency peak and the next read that could lock it in. **Open question for the governor, not yet decided unilaterally**: is 15 minutes too coarse a cadence for this trail given how fast this account's names move, or is the give-back an acceptable cost of the current checkpoint budget? No B2 change made — this paragraph is the "real discussion" the 9/1 note asked for, still awaiting a decision.

*(Original watch-item note, 9/1, kept for context):* the AFRM/GUSH pattern was two-for-two with a quick post-entry pop reversing before the trail's first checkpoint could lock any of it in. Per D4, two instances wasn't yet grounds for a unilateral B2 change, but the governor asked it be actively watched rather than left in the log — see above for the third hit. Not resolved by v3.50's C10/C8 fix (2026-09-01) — that closed a different gap (a stale *entry* gate), not this one (a trail that hasn't caught up by its next tick).

---

## Current state

**v3.54 (9/3 premarket, governor session): grid compressed — entry moves up to 9:35, close moves up to 12:00.** Governor instruction, requested before Thursday 9/3's open. New checkpoint chain: `9:00 · 9:30 · 9:35 · 9:40 · 9:50 · 10:00 · 10:10 · 10:20 · 10:30 · 10:40 · 10:50 · 11:00 · 11:15 · 11:30 · 11:45 · 12:00 · 8:00` — 16 intraday checkpoints plus the 8:00pm backup (was 17). **9:35 is the new primary entry slot**, taking over the role 9:40 held under v3.53 — C1's Gate-1 test now reads 9:30/9:35 instead of 9:30/9:40, and C9's entry window is 9:35–12:00. **9:40 becomes the first management checkpoint** (5 minutes after entry rather than 10), starting the same two-speed cadence one notch earlier: 10-minute checkpoints run 9:40 through 11:00 (nine slots, was seven at 9:50–10:50), then 15-minute checkpoints run 11:15 through 11:45 (three slots, was six at 11:00–12:15). **12:00 is the new close** — B2's stop-pin-to-current-price mechanism (`new_stop = max(new_stop, bar_close)`) that used to fire at 12:30 now fires at 12:00, ending the trading day and arming tomorrow's grid there; 12:15 and 12:30 are retired as slots entirely. Updated everywhere the old times were assumed: the READ MAP, B1b/B2/B6's checkpoint-cadence language, C1/C9/C11/C12's entry-window and gate-timing references, D1's grid line and arming section, and D3's Friday-report line. C11's ER-minimum table windows were rescaled proportionally to the shorter 9:35–12:00 span rather than left keyed to the old clock times. Thursday 9/3's already-armed trigger grid gets replaced with the new times before market open — see A2. Historical journal/log entries below (dated records of checkpoints run under earlier policy versions) are left untouched, same convention as v3.53.

**v3.53 (9/2 late evening, governor session): sectors dropped entirely — individual stocks and individual leveraged ETFs only, commodities (metals/energy/etc.) the sole exception.** Governor instruction, prompted by a real miss the same day: NVDA closed +3.2% and its leveraged wrapper NVDL closed +6.3%, but semis (SMH) read -0.41% premarket at 9:00 and never got re-surveyed once the sector-first structure declined it — the old design had no way to notice an individual name running hard inside a sector that failed its own morning read. Rather than patch that one gap, the governor asked for the structural fix: stop organizing research around sectors at all.

**What changed, mechanically:**
- **D2 (9:00 research):** replaced the sector-first survey with a market-wide `%Change` gainers scan (no `Sector` filter, average-volume floor for liquidity), ranked by magnitude, wrapper-carrying names given priority fill. Builds a flat **25-name individual-stock watchlist** — no sector buckets, no 3-per-theme diversity rule, no cap on how many names share one narrative.
- **Commodities carved out as the one group exception**, checked separately from the 25 (energy, gold, silver, copper, uranium, broader materials — E3) since a physical commodity has no individual company to trade instead.
- **C1** rescoped to commodity trades only (was any sector- or index-leveraged trade).
- **C2 retired outright** — it existed to rank several companies sharing one group wrapper; with sectors gone and crypto's group products dropped, nothing has more than one candidate per wrapper anymore. Number kept unused rather than renumbered, so old references still resolve.
- **C4** rewritten around two parallel tracks — individual stock (ranks 1/2) or commodity (ranks 1c/2c) — with the old sector/index-ETF rank-2 row removed completely.
- **E3** split into a commodity-groups table (unchanged in substance, still gates via C1/C6) and a slimmer individual-stock leveraged-wrapper lookup (NVDL/AMDL/MUU/TSMX/SMCX/AVGX/TSLL/CONL/MSTX). **Retired outright**: every broad sector/index-leveraged product (SOXL, TQQQ, SPXL, TNA, LABU, YINN, KORU, UVIX/VXX) and every crypto group-leveraged product (IBIT, BITX/BITU/ETHU/ETHT) — governor's explicit call: **crypto is individual-stock-only** now (RIOT/MARA/CLSK trade plain, COIN/MSTR keep their real wrappers).
- Swept remaining live-rule references to "sector" in B3, C5, C10, C12, B6 to "commodity" or generic wording; historical E5/Current-State log entries left untouched since they're dated records of what was actually done under the rule in force at the time.

**Not yet done, flagged for the next research cycle**: today's actual watchlist-building tools (the scanner, `get_scanner_filter_specs`) haven't been re-verified against this exact new workflow — Thursday 9/3's 9:00 research is the first live run under v3.53 and may surface mechanical wrinkles (filter syntax, liquidity-floor tuning) the same way v3.51's C6 rewrite did; expect to iterate once, not treat this as fully proven yet.

**v3.52 (9/2 evening, governor session): two-speed management cadence — 10 minutes from 9:50 through 10:50, 15 minutes from 11:00 through 12:30.** Governor instruction, direct response to the day's own live experience: the AFRM/GUSH/NUGT ratchet-breach pattern (E6) has now hit three times, and every instance so far has landed in the morning's fastest-moving stretch, where a 15-minute gap is long enough for `run_high` to build real distance before the next checkpoint can lock any of it in. Tightening the cadence exactly where the pattern has actually bitten, while leaving it at 15 minutes once the morning settles, is a direct answer to E6's open question rather than a separate fix. New grid: `9:00 · 9:30 · 9:40 · 9:50 · 10:00 · 10:10 · 10:20 · 10:30 · 10:40 · 10:50 · 11:00 · 11:15 · 11:30 · 11:45 · 12:00 · 12:15 · 12:30 · 8:00` — 17 intraday checkpoints plus the 8:00pm backup (was 15). Updated everywhere the old flat 15-minute cadence was assumed: D1's grid line, the READ MAP's management row (now split in two), B1b's and B2's checkpoint-cadence language, and C12's worked example (times updated to match the new slots, logic unchanged). C11's ER-minimum table needed no change — it's keyed to wall-clock time, not checkpoint count, so it already adapts. Thursday 9/3's already-armed 15-trigger grid gets replaced with the new 18-trigger version before market open. Does not touch E6's still-open question of whether 15 minutes was ever the right cadence for the *later* window too — only the 9:50–10:50 stretch changes for now; revisit the 11:00–12:30 leg separately if the pattern starts showing up there instead.

**Wednesday 2026-09-02 closed flat, $232.14, +$1.59 on the day (one trade, NUGT).** Genuinely eventful day: 9:00 research found no confirmed theme (Energy reversed after two days, metals looked live but failed C6's old multi-session trend leg); the governor corrected that leg live at 9:49 ET (v3.51 — C6 never should have required multi-day trend structure for a system that closes every position same-day), the gate stack was re-run and NUGT entered off-cycle at $186.2099. One clean ratchet followed at 10:00 (stop 180.57→185.82). Then a scheduler delay on the 10:15 trigger (governor caught it live — "you are late," confirmed against a live quote timestamped well past the scheduled fire) led to an off-cycle check that found the trail's `run_high` (peaked $190.13) had already produced a `candidate_stop` above live price — the third occurrence of the AFRM/GUSH ratchet-breach pattern, handled the same way (cancel stale stop, exit immediate via marketable limit) and closing as a real win, +0.85%, r=+0.282, not a loss. That third hit crossed the threshold set 9/1 for raising it as a real B2 discussion rather than logging it — done, in E6, still an open question awaiting a decision, no rule change made unilaterally. C12's mini-cycle at 10:30 correctly found no re-entry (whole complex pulling back off its post-exit peak). Rest of the day flat, non-events. **Loss streak: 0 of 3** — two wins running (XOM 9/1, NUGT 9/2). Deposited ≈$200.84, floor ≈$100.42, not binding. Thursday 9/3's 15-trigger grid armed at the 12:30 close, verified via `list_triggers`.

**v3.50 (9/1, governor session): C10 leg 1 tightened to strictly-above baseline, and now re-verified against the live quote at order placement, not just the checkpoint's `bar_close`.** Direct fix for the XOM entry-process error logged earlier today: the gate passed on a checkpoint-window `bar_close` only $0.05 above the 9:30 baseline, but by the time the order actually filled a few minutes later, live price had already fallen back under baseline — the stale-gate gap flagged in that incident (D4, one occurrence) as worth considering is now a real rule, on explicit governor instruction rather than unilateral action from a single trade. Two changes: (1) the comparison itself is now `>`, not `≥` — a candidate sitting exactly at its 9:30 print no longer passes; (2) C8's pre-placement checklist now requires re-checking that live condition against the quote already being pulled for `review_equity_order`, immediately before the order goes out — if price has slipped to or below baseline since the checkpoint's own gate check, the entry is declined even though the checkpoint-level read passed. No backfill — does not change how the XOM trade itself was already logged; governs from here forward.

**Open item carried from Monday, still not resolved:** AFRM (8/28) and GUSH (8/31) both hit the identical ratchet-breach-before-first-checkpoint shape — a quick post-entry pop reversing before the trail could lock in any of it. Two-for-two is a real pattern, not yet a rule change per D4's "never rewrite from one trade" (here it would be at least two), flagged in both trades' `archive/trades.csv` notes and in Monday's Current State entry below. Worth a look next time it's convenient — nothing today's single XOM trade adds to it either way (XOM's issue was the entry gate, not the trail).

**Tuesday 2026-09-01 closed flat, $230.55, +$0.10 on the day (one trade, XOM).** One entry (XOM, 9:40 ET), closed by the governor manually at 10:07:59 ET before the trail ever got a chance to work — net +$0.10, +0.06%, r=+0.024, `exit_reason=governor_manual_exit`. The entry itself carried a genuine process error (logged in full in the 9:40 E5 entry that day, since overwritten by Wednesday's research): C10's momentum gate was validated against a checkpoint-window `bar_close` that was already stale by the time the order filled a few minutes later, and live price had briefly dipped back below the entry's own baseline in between — caught and owned, not corrected off-cycle since the position stayed protected throughout. No new entries taken for the rest of the day per the governor's "continue tomorrow" sign-off, read as a pause on new positions, not a session shutdown — checkpoints kept running as normal. **Loss streak: 0 of 3** — a win either way, unaffected by v3.49's new threshold. Deposited capital ≈$200.84 (all-time realized P&L ≈$29.71, 19 broker-side closing trades — `trades.csv` now has 18 rows after today's XOM append; the running one-trade gap is the BSX round trip reconciled at 9:00 research, still correctly excluded), floor ≈$100.42, not binding. Wednesday 9/2's 15-trigger grid armed at the 12:30 close, standard schedule, all verified via `list_triggers`.

**v3.49 (9/1, governor session, rulebook edit): E1's loss definition changed from "any negative P&L, however small" to "`pnl_pct_position` worse than −1.0%."** A scratch at or above −1.0% no longer builds the streak — it resets it to zero, same as a winner. Prompted by Monday 8/31's trip (below): the governor's own clearance already judged that two of the three streak trades (YANG, GUSH) were mechanically-forced early exits on real moves, not signal-quality failures, and cleared the breaker same-day on that read. This rule makes that judgment structural instead of re-litigated by hand every time a small loss lands. **Checked against the record, not just asserted:** re-run under the new threshold, only AFRM (8/28, −1.275%) clears −1.0%; YANG (8/27, −0.31%) and GUSH (8/31, −0.9291%) both fall under it and would each have reset the count. The streak would have read 0/3 for the entire 8/27–8/31 stretch instead of tripping to 3/3 on GUSH — the breaker would not have fired Monday at all. Considered and rejected: classifying by `exit_reason` instead (e.g. treat `trail_breached_before_placement`/`governor_manual_exit` as non-loss) — rejected because it requires naming which reasons qualify as "mechanical" up front and re-litigating edge cases as new exit reasons appear; a flat magnitude cutoff needs no such list and reads directly off a number already in every row. No trade decision is retroactively changed — the historical entries below stand as reported under the rule in force at the time; this governs from here forward.

**Monday 2026-08-31 closed flat, $230.45, -$2.12 on the day (one trade, GUSH).** Loss streak reset to 0 by the governor's mid-day breaker clearance (A1, effective 2026-08-31). A second MCP-connector drop cost the entire 10:15–12:30 window and the 8:00pm backup (~8 hours, queue read ~20:01 ET) — account was flat throughout, nothing unprotected, but Tuesday 9/1's grid was found completely unarmed and had to be armed fresh at ~20:02 ET. Full detail in E5. Post-day analysis of the AFRM/GUSH ratchet-breach pattern is still owed, deferred by governor instruction.

**Monday 2026-08-31, 10:02 ET: flat, LOSS STREAK CIRCUIT BREAKER TRIPPED (A1).** GUSH entered 9:42 ET, exited 10:02 ET at the first 10:00 checkpoint when the chandelier trail math computed a stop already breached by live price — the identical mechanical shape as Friday's AFRM exit, now a real two-in-a-row pattern (flagged for governor discussion in `archive/trades.csv`, no rule change made unilaterally). Net -$2.12, r=-0.372. **Three consecutive losses now on record (YANG scratch 8/27, AFRM 8/28, GUSH 8/31)** — A1's breaker is explicit: loss streak ≥3 blocks any new position until governor clearance, same as the standing 2026-08-15 clearance record. **No new entries from here until the governor clears it** — checkpoints continue running (state checks, B5 headlines if holding, reporting) but C1–C12's entry gates are moot while A1 blocks outright. Governor should review both the streak itself and the two-in-a-row ratchet-breach pattern together — they may be related (a mechanically-forced early exit on a real move looks like "a loss" in the streak count even when, per Friday's D4 review, it was actually risk protection working as designed).

**Cleared same-day, ~10:05 ET: governor override.** Explicit instruction — resume the grid, entries authorized again, full post-day analysis deferred to the 12:30 close review rather than done piecemeal now. A1's clearance record updated to 2026-08-31 (E1). Entry gates are live again from the next checkpoint forward.

**v3.48 (pre-open Monday 8/31, governor readiness check): fixed a real bug in v3.47 before it ever ran live.** B6's log-population duty was scoped to "every management checkpoint (10:00–12:30)" only — but C11's own ER window is defined as "trailing 60 minutes, or back to 9:30, whichever is shorter." Under the literal v3.47 wording, the log would have exactly one entry at the 10:00 checkpoint (nothing from 9:30/9:40), giving the very first management checkpoint's ER an artificially short, wrong window instead of the real ~30-minute one. Fixed: B6 now explicitly starts logging at 9:30's observation and 9:40's entry check, not just the 10:00+ management phase — the same checkpoints that already produce B1b range reads for other reasons (C1, C3, C10) now seed the same rolling log, so by 10:00 the shortlist's logs already carry proper 9:30-onward history. No live trading occurred under the unfixed v3.47 (Friday's day was already closed when it was written), so no trade decision was ever affected — caught during a pre-open readiness check, not a live incident.

**v3.47 (evening 8/28, governor session, post-close): B6's `session_high`/`session_low`/ER moved from re-derived-every-checkpoint to incrementally maintained.** Root cause, found while discussing a proposed multi-file architecture split for token cost: the actual expensive pattern today wasn't the rulebook's own size — it was re-pulling and hand-summing the *entire day's* minute bars at nearly every 10:00–12:30 checkpoint to compute `session_high`/`session_low` (C10) and Efficiency Ratio (C11), when B1b already specifies pulling only the small since-last-checkpoint gap. Fixed at the actual point of waste rather than by restructuring files: B6 now updates `session_high`/`session_low` with an O(1) comparison against each checkpoint's own small pull, and keeps a short rolling log of `(checkpoint_time, bar_close, path_length)` — ER is then computed from the ~4–5 log entries inside the trailing 60-minute window, not 40–90 raw minute bars re-summed by hand. Same formulas, same thresholds, same gate outcomes — only how the inputs get computed changes. No backfill needed; Friday's trading day was already closed when this was written, so it takes effect cleanly starting Monday's grid. (The broader RULEBOOK.md/state-file split proposal was discussed and set aside for now — real risk of introducing a new drift-between-files failure mode for a live system, revisit later if this narrower fix isn't enough.)

**v3.46 (10:36 ET, governor session, live mid-day): C10 leg 1's baseline fixed to 9:30, reset only by an exit's fill timestamp (C12) — never by an intervening checkpoint.** Prompted by today's own 10:00 entry, where the five newly-added candidates (ESTC/GAP/SOLS/AFRM/UMC, added ~9:50) had no 9:30 read of their own, so their first C10 check was treated as an ad hoc free pass. Governor's proposed fix, confirmed: a candidate's first-ever entry check of the day always compares against 9:30's real price (pulled fresh via historicals if it joined the watchlist later), no matter which checkpoint that first entry attempt lands on — 9:40, 10:00, or later all compare back to 9:30 alike, since merely re-checking a candidate without entering it doesn't advance the baseline. The one thing that does advance it: an exit (C12), which resets the baseline to that exit's fill-timestamp price for every shortlist candidate being reconsidered, not just the one that closed — already how today's post-AFRM T+0/T+10 mini-cycle worked, now made the general rule rather than a special case. No effect on any decision already made today (AFRM's entry, the 10:00/10:30 checkpoints) — those stand as executed under the rule in force at the time; this governs from here forward.

**Friday 2026-08-28 closed flat, one round trip.** AFRM entered 10:03:55 ET, exited 10:17:21 ET at the 10:15 checkpoint when the chandelier trail math computed a stop already breached by live price — net -$2.18, -1.28%, r=-0.510. D4 review (done late, ~15:35 ET, after a multi-hour MCP-connector drop that also cost the 12:00/12:15 checkpoints): the exit was well-timed — AFRM kept falling to $78.43 by mid-afternoon, well past the $84.40 exit. Loss streak 2 of 3 (YANG scratch, AFRM), not tripped. Cash/buying power **$232.57**. Monday 8/31's full 15-trigger grid is armed. Full day's reasoning in E5; the guaranteed Friday close report is there too.

**Prior to today — flat, governor paused the session mid-day Thursday 2026-08-27 (~10:48 ET) to work on rulebook changes that evening.** Cash/buying power $234.76, no resting orders (verified live). Net **+$10.69 on the partial day**, two trades before the pause: MSTX (+$11.41, r=+0.899, 9:43–10:11 ET, a real ratchet/velocity win — the v3.40 redesign's first live proof, locking gains before a 9.2%-run reversal) and YANG (-$0.72, r=-0.124, 10:34–10:48 ET, entered via C12's re-entry cycle after the MSTX exit, then closed by the governor's manual off-cycle exit to stop for the day — a trivial scratch, not a rule-driven exit, same convention as the 2026-08-20 MSTX governor exit). Today was also the first live day under v3.41/v3.42 (sector-first research, 24-name/6-sector watchlist) — both worked as intended; two brand-new sector themes (Financials-reversal, China-reversal) surfaced specifically because of the sector-first survey. **All of today's remaining checkpoints (11:00 through 8:00pm) were deleted per governor instruction; tomorrow's (Friday 8/28) grid was armed manually since the normal 4:00pm auto-arming didn't run, then rebuilt again that same evening once v3.43 shortened the day — Friday now runs a 15-trigger grid (9:00/9:30/9:40 plus 10:00–12:30 on the new 15-min cadence, plus 8:00pm backup), not the original 17-slot version.**

**v3.38–v3.42 all applied and confirmed working live**: the 8-stage ratchet replacing the old 4-stage structure and B4's fixed profit-target removal (v3.38–v3.40), D2's sector-first/leveraged-priority research methodology (v3.41), and the watchlist expansion to 24 names / 6 sectors of 4 (v3.42).

**v3.43 (evening of 8/27, governor session): a full restructure driven by the data — every profitable entry across the system's history has landed between 9:42 and 10:34 ET, and the one entry after 10:34 (MSTX 8/21, 12:32pm) lost money.** Trading day shortened to 9:00–12:30 (was 9:00–4:00pm); management checkpoints now run every 15 minutes from 10:00–12:30 (was 30 minutes to 4:00pm), net *fewer* total daily checkpoints (15 vs 17) despite the tighter cadence. Entries valid anywhere 9:40–12:30, no preferred-window distinction. **B2's stepped 8-stage ratchet is retired, replaced by a continuous rule**: every 15-min checkpoint ratchets the stop to `avg_price(since last checkpoint) × (1 − stall_threshold_pct)`, per-instrument noise-scaled, up only — validated against MSTX's actual 8/27 bars before adoption (would have exited +5.79% vs. the real trade's velocity-driven +5.37%). The velocity trigger is unchanged, still the faster-reacting override for a single sharp spike. The 12:30 checkpoint additionally pins the stop to live price, which is what now enforces same-day close — no separate 4:00pm deadline. **B3's stall-count ladder is retired entirely** — the continuous ratchet already squeezes a stalling position without a second, potentially-conflicting counting mechanism. C11's chop-filter table compressed to 3 bands fitting 9:40–12:30. No more extended-hours slots (4:30–7:30pm gone) or cadence-reduction rule (both moot with the day already this short).

**v3.44 (evening of 8/27, same governor session, continued): the average-based ratchet replaced by a single continuous chandelier trail anchored to `run_high`, and the separate velocity trigger retired.** Governor's own read of the old (pre-v3.40) system: the entry-time stop was its best feature, but the staged ratchet triggered too rarely and moved too linearly. Backtested against all 13 trades on record (real minute-bar paths, each instrument's own noise band from its real ~40-day history) sweeping a discount multiplier 1×–5× off `run_high`: **`candidate_stop = run_high × (1 − 2 × stall_threshold_pct)`, `new_stop = max(current_stop, candidate_stop)`, checked every 15-min checkpoint** — 2× beat the real historical results on both average captured gain (+1.56% vs. the real system's +1.53%) and win rate (9/12 vs. 7/12), fixing two real reversal losses (UEC 8/26 -2.54%→+0.26% simulated; MSTX 8/20 -1.24%→+1.02% simulated) without giving other reversals extra room, unlike wider multipliers (4×–5×) which scored higher only because of one outlier trend day (MSTX 8/27 continuing to run for hours past its real exit) while making two genuine reversals worse. Anchoring to `run_high` instead of the trailing average is what gives a real trend room to breathe — the average sits close to the entry price right after a fill, so a normal early pullback could trip the old design before a trend had even formed (found via a separate before/after check on UUUU 8/25: the average-based design would have cut a real +$6.86 winner down to roughly breakeven). The velocity trigger is retired — anchoring continuously to `run_high` already gives the fast-reaction behavior it existed for, without a second mechanism running in parallel.

**v3.45 (evening of 8/27, same governor session, continued): lean cleanup — no trading behavior changed.** Two genuinely dead numbers, `breakeven_trigger` and `trail_pct`, are fully retired (not just unused): `tools/profile.py` no longer computes or prints them, B1's formula list drops them, and C8's required entry report no longer asks for them — both had been superseded by the trail redesign but kept getting computed and reported anyway, on every single profile call and every entry. B2/B3/B4's detailed backtest-rationale and retirement-history prose (why 2× not another multiplier, why the stall ladder and average-ratchet were removed) is trimmed to one-line pointers — the full reasoning already lives in this section's own v3.43/v3.44 paragraphs and the git history, so restating it in the text read at every single management checkpoint was pure duplication. D1's "never delete the 12:30/8:00 checkpoints" line, which repeated A2's rule verbatim even though Part A is read at every checkpoint including D1's own readers, is now a one-line cross-reference. Net: same gates, same stop math, same thresholds — fewer tokens read per checkpoint, forever. **Follow-up, same evening:** `archive/EXPERIMENTS.md` swept clean too, on explicit request — all 16 entries (EXP-001–016) dated back to a pre-RULEBOOK.md architecture (`OPERATIONS.md` §-sections, `tools/replay.py`, `tools/calibrate_stops.py`, `tools/preflight.py`, none of which exist anymore) moved from Open to Closed and marked accurately: EXP-007/008's scaled-stop/scaled-target findings are still exactly how B1 works (`LIVE`, kept in full); EXP-015's inverse-vehicle Gate-1 concern turned out to already be resolved in current C1 (real DUST/YANG/ZSL/FAZ trades confirm it evaluates each vehicle's own self-referencing day change); the rest are `KILLED` with a one-line reason each — mechanism retired (stall ladder, old trail), infrastructure gone (preflight's map, replay.py), or premise weakened (target-reachability checks matter less once no exit is target-triggered). 348 lines → 152. **Second follow-up:** a more urgent find while auditing token cost — the 10 already-armed Friday 10:00–12:15 management triggers still carried their original prompt text from before v3.44, describing the retired average-based ratchet formula verbatim. Not just a token cost; if ever followed literally instead of re-reading this file fresh, it would apply the wrong stop math live. All 12 Friday triggers from 10:00 through 8:00pm rewritten to the terse, rulebook-pointing convention already used by 9:00/9:30/9:40 ("read RULEBOOK.md per its own READ MAP — ignore any rule content cached in this prompt"), verified via each `update_trigger` response. Also checked and rejected: pulling full-session minute bars at every checkpoint instead of reading `run_high` back out of E5's log — a 2.5-hour session's bars run ~5,600 tokens raw, more expensive than E5's own compact log for that stretch, so the current design stands.

Prior trades: 2026-08-27 YANG (-$0.72, r=-0.124, governor manual exit); 2026-08-27 MSTX (+$11.41, r=+0.899); 2026-08-26 UEC (-$5.54, r=-0.998); 2026-08-25 UUUU (+$6.86, r=+1.238); 2026-08-25 SMCX (+$4.25, r=+0.293); 2026-08-24 MSTX (+$13.81, r=+1.050); 2026-08-21 MSTX (-$0.14, r=-0.011); 2026-08-21 CONL (+$2.51, r=+0.230); 2026-08-20 MSTX (-$0.54, r=-0.201, governor's off-cycle exit, not rule-triggered); 2026-08-19 GUSH (+$0.22, r=+0.194).

**Loss streak 1 of 3** (the YANG scratch). Deposited capital ≈ $201.48 (all-time realized P&L ≈ +$33.28), floor ≈ $100.74 — not binding.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
