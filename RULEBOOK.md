# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.46.** Bump on every rule/threshold change; record it in the commit.

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
| **10:00–12:15** management ×10 (15-min cadence) | A · B (+ C — entries valid anywhere in this window) | Holding, or flat and open to a fresh opportunity |
| **12:30** close | A · B4 · D | Exit, report, and arm tomorrow (primary) |
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
4. **Never delete the 12:30pm close checkpoint (primary arming) or the 8:00pm checkpoint (backup verification, D1).** Together they replace what used to be a single point of failure.

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

**Ranges close the observation gap without changing decision frequency.** Checkpoints run every 15 minutes from 10:00 through 12:30 — a hard cost constraint. Each one knows the true high and low reached since the last, so a spike-and-reverse inside one interval is visible to every rule, even though action still waits for a scheduled checkpoint. Everywhere below, `run_high`, `session_high`/`session_low`, and checkpoint-to-checkpoint comparisons read from this range, never a point.

## B2. Stops — UP ONLY, NEVER DOWN

- **Never widen.** If the tape needs more room the trade is wrong — be out.
- Only permitted downward change: correcting a factual placement error, stated as such.
- Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print.**
- Minimum re-placement move: `min_stop_move_pct`. A structural level (swing low) may substitute **only if nearer**.
- Stops are **regular-hours only** and do not protect a gap.

### The trail — continuous chandelier off `run_high`, stock-scaled (v3.44)

**`run_high` tracks the high since *this position's entry* — a different window than C10's day-anchored `session_high`, even though both reuse the same B1b range-tracking technique.** Initialized to the fill price at entry, then `run_high = max(run_high, bar_high)` at every checkpoint (B1b) — the true highest price reached since the fill, not a lucky-or-unlucky point sample. Advances on any fresh interval high, unconditionally. **Never substitute `session_high` here** — a candidate can legitimately enter below its own day's high (C10 leg 2 allows a confirmed bounce off a pullback), in which case `session_high` at entry sits above the fill and would produce a stop tighter than the hold has actually earned.

**At every 15-minute management checkpoint (10:00 through 12:30), the stop ratchets off the running high itself, discounted by twice the candidate's own noise band — never off the trailing average, never a fixed stage:**

```
run_high = max(run_high, bar_high)                         -- B1b, updated every checkpoint
candidate_stop = run_high × (1 − 2 × stall_threshold_pct)
new_stop = max(current_stop, candidate_stop)      -- up only, never down (B2's own rule, unchanged)
```

`stall_threshold_pct` is the candidate's own fresh JIT profile number (B1) — a calm name gets a wide-enough discount to survive its own normal noise; a choppy name gets pulled in tighter, proportionally. **Anchoring to `run_high` instead of the trailing average is the point:** the average sits close to the entry price right after a fill, so a completely normal early pullback can trip an average-based stop before a real trend has even formed. A high-water mark doesn't move on a pullback — only a fresh high advances it — so the trail gives a genuine trend room to breathe while still tightening every single checkpoint, never waiting on a breakeven gate. No separate spike-detection trigger exists anymore (retired v3.44) — this one rule already reacts to a fast move at the very next checkpoint.

**Why 2× the noise band:** backtested 1×–5× against all trades on record; 2× was the point that improved on the real historical results without giving reversals extra room to run first — full comparison in Current State (v3.44) and the git history, not restated here.

**At the 12:30 checkpoint specifically** — the last of the day — additionally include the live current price (`bar_close`, B1b) as a stop candidate: `new_stop = max(new_stop, bar_close)`. A position can only still be open at 12:30 if price is at or above its current stop, so this is always a valid *upward* move, never a violation of "up only." It pins the stop to the market, so the very next tick down closes the position — the stop still does the closing, not a forced sell, but the exit becomes effectively immediate. This is what ends the trading day; there is no separate 4:00pm deadline (see B4).

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

- **Reversal** — broke the level or VWAP that justified entry, or the sector rolled over. The level must have been **named at entry** or the claim is unfalsifiable.
- **Risk/reward flipped** — small remaining upside against a large distance to the stop.
- **Unwanted event approaching** — earnings or macro data not intended to be held through.
- **Approaching the same-day close deadline** with the move finished.

Not on one red candle, midday noise, or impatience.

### Pre-commit — end every holding report with it

Name the **specific, falsifiable** condition that would exit at the next checkpoint, with instrument and direction. Then honour it. To override, say explicitly that you are overriding a pre-commitment and name the **new** information. *"It looks like it's turning back up" does not qualify.*

## B4. Same-day close — no fixed profit target

**No checkpoint sells purely for hitting a price level.** The continuous chandelier trail (B2) is what locks in gains — a big move is expected to give back at most `2 × stall_threshold_pct` off its running high at any checkpoint. `target_pct` is still computed at entry (B1) and used by C7's `mfe_to_target` ranking check — informational only, never an autonomous trigger.

**Every position closes the same trading day it was opened. No overnight hold, ever.** Enforced structurally, not by a deadline check: the 12:30 checkpoint (B2) pins the stop to the live price, so the position's own stop closes it, almost immediately, rather than a separate forced sell. State the intended exit at entry.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(The trading window (9:00–12:30) is short enough that this may only fire once or twice in a given hold. Don't stop checking just because an earlier trade already closed today — a later opportunity is still tradeable within the window.)*

## B6. Shortlist range snapshot — feeds C10, whether or not it's the held position

**At every management checkpoint (10:00–12:30), log `bar_high`/`bar_low`/`bar_close` (B1b) for every name still on today's shortlist** (the candidates that cleared C3 at 9:40, not the full 24-name watchlist) — not a single point price, the same range-pull technique used for the held position, applied to the rest of the shortlist too, even while holding something else. One extra minute-bar call per name; the same call already run for the held position, not a new kind of lookup.

**Why this is its own duty:** C10's `session_high`/`session_low` need continuous range history *per candidate* — a genuine day-long high-water mark. A candidate re-considered later in the day with no reads since 9:40 has no history for C10 to check, so it default-passes for lack of data rather than genuinely clearing anything. That default-pass is safe (never block on a gap) but silently defeats the gate if the gap becomes routine. When a default-pass does happen, flag it explicitly at entry — never let it look like a deliberate clearance.

---

# PART C — ENTRY (9:00 · 9:30 · 9:40 primarily; any 10:00–12:30 checkpoint while flat)

> **No position may be opened outside 9:40–12:30 (v3.43).** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:40, subject to C1's late-entry clause. **A position that closes mid-day gets an accelerated re-check instead of waiting for the next grid slot — see C12.**

## C1. Gate 1 — the sector must hold, 9:30 → 9:40

**9:30 is scoped to the 24-name watchlist only — no new market scan.** Record the day change of the **6 sector proxies** (feeds the Gate 1 test below) and note whether each of the **18 individual candidates** is still holding its move. That's an observational check, not a formal re-run of C3 — the formal re-confirmation of C3's legs happens live at 9:40.

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

> **Scanner filter values are decimals, not whole percents** (`0.0075` = 0.75%, not `0.75`) — `update_scan_filters` takes the same units. A stray whole-percent value doesn't error, it silently matches nothing (found 2026-08-28: `FILTER_TYPE_PERCENT_CHANGE_FROM_CLOSE` stored as `0.75` returned 0 matches all morning; corrected to `0.0075` returned 250). After any filter edit, verify with a live run before trusting a "no matches" read — zero results is itself a signal to check the filter, not evidence the tape is quiet. `update_scan_filters` also wants wire-format predicate enums (`PREDICATE_GREATER_THAN_OR_EQUAL`, etc.), not the human-readable symbols (`>=`) that `get_scans`/`run_scan` display.

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
- State at entry: fill · **quantity and total cost** · stop price and % · target % · `mfe_per_stop` for the top two · intended exit · the falsifiable pre-commit for the next checkpoint.

## C9. Timing and selection

- **Entries are valid at any checkpoint from 9:40 through 12:30** — no preferred-window distinction inside that range; the whole window is short enough (v3.43) that lateness within it isn't itself a signal.
- **After 12:30, none** — the window is closed for new positions regardless of what's setting up (B2/B4).
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

1. **Not currently falling.** This checkpoint's `bar_close` ≥ a fixed baseline price, for this candidate specifically — **the baseline is 9:30's price, and it moves only once: it resets to the exit's fill-timestamp price the moment any position closes (C12), for every candidate being reconsidered in that re-entry cycle, not just the one that was held.** No other event advances it — a checkpoint that merely re-reads a candidate without an entry/exit leaves the baseline exactly where it was, even across several checkpoints (v3.46: previously "immediately prior formal checkpoint," which let a candidate's first-ever entry check drift onto whichever checkpoint ran last instead of staying anchored to 9:30 — see Current State for why this changed). Applies identically to a candidate added to the watchlist after 9:30: pull its actual 9:30 price fresh via minute-bar historicals and compare against that, never treat "whenever we started watching it" as the baseline. (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched. C12 steps 2–4 own the exact mechanics of the post-exit reset — read there for the full rule and worked example.
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** `bar_high` must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − bar_close) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

## C11. Chop filter — Efficiency Ratio, time-scaled

**Applies to every candidate at every entry-eligible checkpoint, in addition to C1–C10.** Catches a candidate that's technically up on the day and technically not falling (passes C10) but is genuinely just chopping sideways rather than trending — leveraged ETFs decay in exactly that shape (C5).

**Efficiency Ratio (ER), computed from a direct minute-bar pull (B1b's technique), not sparse checkpoint points:** pull the trailing 60 minutes of minute bars for the candidate (or back to 9:30, whichever is shorter, early in the session). `ER = |last close − first close| ÷ Σ|close(n) − close(n−1)|` across every minute in the window — net progress over total path length. Near 1 = clean directional move; near 0 = pure back-and-forth with little net progress. Fewer than ~20 minutes of window available → too little to be meaningful, gate passes by default — never block on a gap, never pretend the check ran.

**Minimum ER required to enter, scaled to how forgiving the moment should be** (early moves are naturally noisier as they establish; entries later in the — now much shorter — window are into an already-maturing move and should be held to a higher bar). **Ranges are continuous — every clock time from 9:40 to 12:30 falls in exactly one row, no gaps.** This matters beyond the regular grid: a C12 mini-cycle check can land at any minute (fill-time-anchored, not just on the quarter hour), and needs an unambiguous minimum wherever it lands:

| Checkpoint time | Minimum ER |
|---|---|
| 9:40 – 10:29 | 0.15 |
| 10:30 – 11:29 | 0.25 |
| 11:30 – 12:30 | 0.30 |

Below the window's minimum → declined as too choppy, regardless of C1–C10 all passing. This is a real, separate failure mode from C10: C10 asks "is it currently falling," C11 asks "is the recent path actually going anywhere, net."

C11 self-supplies its window with a fresh pull at the moment of the check — it does not depend on B6 having tracked the candidate at prior checkpoints. (B6 exists for C10, whose `session_high`/`session_low` need day-long continuity a trailing window can't provide.)

**Fetch once when B1b/B6 also apply to this candidate this checkpoint.** C11's window (60 min, or back to 9:30) always contains B1b/B6's shorter since-prior-checkpoint gap. Pull the larger window a single time and derive both from it — C11's ER from the full pull, B1b's `bar_high`/`bar_low`/`bar_close` from its tail subset — rather than two overlapping minute-bar calls for the same symbol. Same numbers either way; this only removes a duplicate call.

## C12. Re-entry cycle — an exit restarts the entry clock, not the whole day

**Applies whenever a position closes before 12:30, regardless of why** — stop (including the 12:30 pin's near-immediate trigger, if the position is somehow re-entered and stopped again inside the same window), reversal, any other B3 exit. The moment of exit becomes an ad hoc **"9:30-equivalent,"** rather than waiting for the next 15-minute grid slot.

1. **The exit's fill timestamp is the mini-cycle's actual "9:30-equivalent" moment — not whenever it's later discovered or read.** At the moment the exit is discovered (T+0), same turn, no new trigger needed: run the 9:30-style check (C1) against today's existing shortlist — the candidates and sector proxies already built at 9:00, not a fresh market-wide scan. Record each sector proxy's current day change and note which shortlist names are still holding their move. C7 re-ranks fresh here too — the capital base just changed (the position closed), which by C7's own rule voids the earlier ranking.
2. **T+10 is measured from the exit's actual fill timestamp (from the order response), never from when it happened to be noticed.** Detection lags the real fill whenever the exit fires between scheduled checkpoints — get the real fill time first, then compute `elapsed = now − fill_time`:
   - **`elapsed ≥ 10 minutes`** — the window has already passed. Run the full 9:40-style entry gate stack, C1–C11, immediately, same turn as T+0. No trigger to arm, no further wait.
   - **`elapsed < 10 minutes`** — arm one ad hoc trigger for `10 − elapsed` minutes out (the nearest possible time to exactly `fill_time + 10min`, not a flat 10 minutes from T+0) to run the gate stack then.
   Enter if a candidate clears every gate, exactly as any other entry checkpoint would. This is in addition to, not a replacement for, the regular grid triggers already armed for the rest of the day.
3. **The comparison baseline for this gate stack's first run is each candidate's price *at the fill timestamp itself*, not at whenever the check happens to execute, and not the last regular grid slot.** Pull minute-bar historicals for that exact minute, for every shortlist name — the same one fixed moment for all of them, the same way 9:30 is one fixed moment for the whole watchlist, not something recomputed per candidate. This is what C10 leg 1 ("not currently falling") and C1's baseline reading compare against for this mini-cycle's first pass — whether that pass runs immediately (the `elapsed ≥ 10` branch) or at the armed T+10 trigger (the `elapsed < 10` branch). Being "free to trade" (timing, step 2) and "what you compare against" (this step) are two separate questions — 15 minutes already elapsed since the fill clears you to act *now*, but the price you're judging "still rising since I sold" against is still the price *at the fill*, not the price at whatever minute you happened to look.
4. **After the gate stack runs, whether or not a new position was opened, resume the standard grid at its own next slot — not exit-relative.** Exit at 10:45, discovered and gated promptly → the next check is the regular 11:00 slot, then 11:30, unchanged. This mini-cycle's first read (step 3) is itself a formal checkpoint in the single chronological chain C10 tracks and B6 logs (v3.26) — the regular slot that follows it compares against *that* read's own `bar_close`, not back past it to the fill-timestamp baseline again. The fill-timestamp anchor is a one-time reference for this mini-cycle's opening comparison only, never a standing reference point afterward.

**Worked example, steps 2–4 together (this is the authority C10 leg 1 points back to):** a position exits (fill) at 10:42. The 10:45 grid check discovers it; only 3 minutes have passed (`elapsed < 10`), so an ad hoc trigger arms for 10:52 (`fill_time + 10min`). At 10:52 the full gate stack runs — C10 leg 1 there compares 10:52's `bar_close` against the candidate's price *at 10:42* (step 3), not against 10:45's close. Declined → the next check is the regular 11:00 slot, and *that* leg 1 compares against the 10:52 read's own `bar_close` (step 4) — not back against 10:42 again, and not against 10:45. From there it's fully normal: 11:15 vs 11:00, 11:30 vs 11:15, and so on through 12:30.

Fires once per exit, not a new recurring cadence. If T+10 finds nothing that clears every gate, the book just stays flat until the next regular grid slot — same as any other declined entry.

**A chance to re-check, never a mandate to re-enter — everything else already in force still binds at full strength.** C5's "no read = no trade" and C9's "never force a trade" apply to the T+10 check exactly as hard as at 9:40; C9's 9:40–12:30 entry window (v3.43) still governs — a mini-cycle triggered late enough that `fill_time + 10min` would land past 12:30 simply finds no entry available, same as any other post-12:30 moment; A1's one-position gate is untouched. This rule only shortens *when* the next attempt happens, never *whether* one is allowed.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid (ET)

`9:00 · 9:30 · 9:40 · 10:00 · 10:15 · 10:30 · 10:45 · 11:00 · 11:15 · 11:30 · 11:45 · 12:00 · 12:15 · 12:30 · 8:00`

**No extended-hours slots.** As of v3.43 the trading day ends at 12:30 structurally — the 12:30 checkpoint's stop-pin (B2) closes whatever's open almost immediately, so there is nothing left to manage into the afternoon or evening. 8:00pm exists purely to verify tomorrow got armed (below), not to trade.

Cadence is 15 minutes from 10:00 through 12:30. ET → UTC: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5. Skip market holidays — **verify the calendar, never assume.** On an early close, end the grid at whichever of 12:30 or the early-close time comes first. **Friday arms Monday**, not the weekend.

Runs indefinitely until the governor pauses it. Never stop on your own initiative.

### Arming — primary at 12:30, backup at 8:00

**Tomorrow's full checkpoint chain gets created at the 12:30 close, right after that day's exit/report work (D3) — not held until 8:00.** Skip the weekend the same way as always — Friday's 12:30 arms Monday.

**8:00pm is a verification pass, not a second independent arming.** Check that tomorrow's chain already exists (`list_triggers`, looking for tomorrow's date). If it does, this is a non-event — stay silent per D3, nothing to report. **If it's missing or incomplete — the 12:30 arming failed or was skipped somehow — create it now, and say so explicitly**, the same way A2 already treats any past-due, still-enabled trigger as a missed checkpoint that gets done late and flagged, not silently absorbed.

Never delete either checkpoint (A2's rule, not restated here).

### Early shutdown

Flat · no resting orders · **and** no entry possible (buying power short) → delete remaining intraday checkpoints. **Keep exactly two: 12:30 close (report + primary arming) and 8:00 backup (verify tomorrow is armed; re-arm only if it isn't).** Being flat because an earlier trade already closed today is **not** by itself a reason to shut down — a later opportunity is still tradeable within the window unless one of the two conditions above is actually true.

## D2. 9:00am research — standard work

1. **Headlines** — macro, geopolitical, overnight.
2. **Pre-market prices** across the universe and yesterday's watchlist.
3. **Earnings reactions** from last night's after-close reporters.
4. **Survey sector proxies (E3) to find distinct, genuinely moving themes — sector-first, not individual-stock-first.** Scan across sector proxies, not a market-wide list of individual tickers, to identify which themes are actually active today. Individual names are pulled only from within a sector once that sector is provisionally selected (step 6) — never from an open-ended market-wide hunt for movers.
5. **Confirm settled buying power and unsettled funds.** Recompute deposited capital and the floor; report either if changed.
6. **Write the watchlist — 6 sectors, each genuinely different, 3 individual stocks per sector.** Structured, not just ranked:
   - **Pick 6 sector proxies that don't overlap.** No two from the same correlated complex — GDX and GLD and SLV are one theme (precious metals), not three; XLE and USO are one theme (energy), not two. Choose the 6 most active, most distinct themes the morning's scan and headlines actually support. A single dominant story (today: crypto) still gets only one of the six slots, however many names in it are moving — concentration in one theme is exactly what this structure exists to prevent, since a reversal in that one theme otherwise leaves nothing uncorrelated to fall back on. **Leveraged coverage is a real factor in which 6 themes win a slot, not just a detail decided afterward** — when two candidate themes are similarly active, prefer the one with genuine leveraged-vehicle coverage (E3) over one that would need plain-stock substitutes for its individuals.
   - **For each of the 6 sectors, take its 3 best individual names — leveraged wrappers are the priority, plain stocks only fill what leveraged coverage can't.** Prefer E3's own grouping (by mfe_per_stop, never by price) — most sectors have real leveraged single-stock coverage there (semis, crypto). Where E3's group can't supply 3 leveraged names on its own, fill the remaining slots with plain (unleveraged) stocks from that same sector — real, liquid, currently-moving names found via a live sector-scoped scan (the scanner's Sector filter, or direct quotes on known sector constituents), never invented from memory and never padded with a name that isn't a genuine mover today. Profile every individual the same way regardless (B1) — a plain stock isn't a lesser candidate, C4's rank-2 path already exists for exactly this case, this just extends that same logic to which names make the watchlist in the first place, not only which vehicle gets traded once a name is already shortlisted. A sector only gets skipped entirely if it can't produce 3 real candidates even counting plain stocks — C5's "no read = no trade" still governs which names are real, leveraged or not.
   - 6 sectors × 3 names = 18 individuals, plus the 6 sector proxies themselves = 24 total (6 groups of 4).
   - Profile every individual just-in-time (B1); mark affordability second, never first — include unaffordable names, they measure what capital is costing. The 6 sectors feed C1 (Gate 1); the 18 individuals feed C3 (major-move gate) and C4's rank-1/rank-2 tracks.
7. **Refresh the live-context block (E5).** Commit and push.

## D3. Reporting

- **Losses as plainly as gains.** No spin. Never claim edge from a small sample.
- **Verified fills only.** P&L in dollars, percent **and R**. Slippage both sides.
- **Correct your own errors promptly**, including ones that look bad.
- **Most checkpoints are non-events — stay silent.** No "checked, nothing to do."
- **When you do report, state the outcome, not the reasoning already committed to the file.** Full gate-stack reasoning belongs in `archive/trades.csv`'s notes field and E5 — both durable, both re-readable on demand. The chat reply is a line or two: what happened, the key number. It does not re-narrate reasoning that's already been written down. **This session runs every checkpoint indefinitely — Robinhood's connector grant can't be replicated in a fresh session, confirmed 2026-08-25, so there is no periodic reset.** Every word written into a reply becomes permanent, compounding context for the life of the system; duplicating file content into prose is a real, ongoing cost, not a one-time one.
- **Report immediately:** entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a notable setup declined.
- **A no-trade day gets no evening message.**
- **Friday 12:30pm always reports**, trades or not — balance, every trade, loss-streak count, what was declined and why, any rulebook change. The guaranteed heartbeat. (Moved here from 8:00pm under D1's arming restructure — 8:00 is now a silent-unless-broken backup check, even on Fridays; the real weekly data already lives at the 12:30 close, not seven-and-a-half hours later.)

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

**Friday 2026-08-28, 9:00 research** (run on time, 9:01–9:07 ET; first live day under v3.45 — 15-min chandelier trail, 9:00–12:30 day):

- **Headlines: FOMC Chair Kevin Warsh gives his first Jackson Hole speech as Chair at 10:00am ET today** — lands exactly on the first management checkpoint. First-ever speech from this Chair, no track record to calibrate against; treat as the dominant risk factor for the whole session, not an ordinary B5 hourly check. Nasdaq-100 futures -0.32% (Marvell/Rubrik both -7%+ premarket on earnings, dragging the index), S&P 500 futures flat, on course for a weekly advance. PayPal -16% (Advent/Stripe both dropped their acquisition pursuit — single-name, not sectorwide). [Bloomberg](https://www.bloomberg.com/news/articles/2026-08-27/stock-market-today-dow-s-p-live-updates), [ts2.tech](https://ts2.tech/en/stock-market-today-08-28-2026/), [Yahoo Finance](https://finance.yahoo.com/economy/live/jackson-hole-fed-summit-live-kevin-warsh-keynote-speech-180442096.html)
- **Sector-first survey: 23 proxies checked premarket** (SMH/QQQ/SPY/IWM/XLE/USO/UNG/GDX/SLV/GLD/XBI/XLB/COPX/URA/FXI/EWY/IBIT/VXX/XLF/XLI/XLU/XLY/TLT). Standouts: XLB +1.13%/COPX +0.92% (materials/copper, confirmed real by FCX +1.11%/SCCO +0.80% individually — not just proxy noise), SLV +1.78% (silver outpacing GDX +0.44% and GLD -0.13%, folded into materials rather than split into a third precious-metals bucket per the correlated-complex rule). SMH -0.72% was almost entirely MRVL's earnings drop (AVGO actually +1.28%, NVDA flat, MU/AMD only mildly red) — not a broad semis move, dropped. IBIT -0.62% confirmed broadly bearish by COIN/MSTR/MARA/CLSK/RIOT all down 0.9–1.8%, but **no inverse-crypto vehicle exists in the universe (E3) and shorting isn't authorized** — a real, disclosed theme with no tradeable expression, dropped. FXI +0.74% not confirmed by its own constituents (BABA +0.05%, JD -0.04%, PDD +0.66% — flat/noise), dropped. Energy (USO -1.25%, UNG -1.44%) not confirmed by majors (XOM/CVX flat, COP's premarket quote had a broken spread) or by GUSH itself (-0.92%), dropped. XLF/XLI/XLU/XLY all under ±0.35%, no signal.
- **CORRECTION, ~9:27 ET: the "unusually quiet tape, zero matches" read above was wrong — the market-wide momentum scan (`Agentic $20 - momentum`) had a broken filter, not a real signal.** Its `% Change` threshold was stored as `0.75` (screening for ≥75% single-day gainers) instead of `0.0075` (≥0.75%) — percentage filters take decimals, and the stray whole-percent value silently matched nothing rather than erroring, exactly the failure mode `get_scanner_filter_specs` itself warns about. **Fixed via `update_scan_filters`**, corrected value `0.0075`, verified live: 250 real matches, not 0. The individual-name checks against SMH/IBIT/FXI/energy above are unaffected (those used direct quotes, not this scan) and still stand. **Real movers this scan should have caught at 9:00, found on re-run**: ESTC +27% (Elastic, clean Q1 FY27 earnings beat — EPS beat $0.12, revenue beat, guidance raised), GAP +20% (Gap Inc, Q2 beat + raised full-year EPS guidance to $2.35–$2.45), SOLS +17% (Solstice Advanced Materials, specialty materials — would reinforce today's Materials group), AFRM +14% (Affirm), UMC +9% (United Microelectronics, Taiwan chip foundry, catalyst not yet traced). **Not yet added to today's watchlist or profiled — governor to confirm which of these to pull in before they're treated as candidates.**
- **2 sectors selected** (fewer than the usual 6 — the tape genuinely doesn't support more this morning; not forced per C5's "no read = no trade"):
  - **Materials/Metals** — proxy XLB +1.13%. Individuals (plain stocks — no leveraged single-stock wrapper exists for copper miners in E3, UYM is the group's only leveraged vehicle and was untraded/illiquid premarket): FCX +1.11%, SCCO +0.80%, SBSW +3.18% (Sibanye-Stillwater, platinum group, from the materials scan).
  - **Biotech** — proxy XBI -0.14% (doesn't gate individuals per C5's exception). Individuals, from a live scan (>3% gainers, Healthcare sector, real liquidity): NVCR +3.45% (NovoCure, $2.1B cap), RGNX +8.31% (REGENXBIO, $619M cap), ORIC +3.71% (Oric Pharmaceuticals, $1.4B cap). AEMD (+28%) excluded — $1.5M cap, 27x relative volume, classic thin-stock spike, not tradeable.
  - **2 sectors × 3 names = 6 individuals, plus 2 proxies = 8 total (2 groups of 4).**
- Profiles (`tools/profile.py`, 51 daily sessions each), ranked by `mfe_per_stop`: **NVCR 1.094** · ORIC 1.064 · RGNX 0.973 · SCCO 0.659 · FCX 0.532 · XBI 0.512 · COPX 0.418 · UYM 0.278 · XLB 0.248. FCX and COPX both flag `mfe_to_target` above 2.5 (target effectively unreachable per B1) — informational only, doesn't affect entry per v3.40.
- Buying power $234.75, unsettled funds $0. **Deposited recomputed fresh (never cached)**: total_value $234.75 − all-time realized P&L $33.91 (verified via `get_realized_pnl`, not the prior session's cached $33.28) − unrealized $0 = **deposited ≈$200.84, floor ≈$100.42**, not binding.
- **Today's watchlist: 8 names (2 proxies + 6 individuals)** — XLB/FCX/SCCO/SBSW, XBI/NVCR/RGNX/ORIC.
- **Added ~9:50 ET, governor-directed: ESTC, GAP, SOLS, AFRM, UMC** — the five real movers the broken scan (see correction above) missed at 9:00, now profiled and confirmed still live at ~9:45: ESTC +22.9% (Elastic, Q1 FY27 beat — EPS/revenue beat, guidance raised), GAP +16.1% (Q2 beat, FY EPS guidance raised to $2.35–$2.45), SOLS +16.8% (Solstice Advanced Materials — folds into today's Materials group alongside XLB/FCX/SCCO/SBSW), AFRM +12.1% (fiscal Q4 beat, $4.62 EPS vs. estimate, upbeat Q1 revenue guide, reported after-market Thursday), UMC +6.4% (United Microelectronics, Taiwan foundry — **tech/semis catalyst exception (C5)**: no same-day catalyst found, taken anyway per rule, noted plainly). All confirmed `tradeable=true`, regular-hours tradable. No single-stock leveraged wrapper verified for any of the five in this account (a brand-new `UMCU` 2× UMC ETF was found in a news search but its liquidity/availability here is unverified — **not traded on an unverified mechanism, per E4**); C4 rank-2 plain-stock applies to all five.
  - Profiles (`tools/profile.py`, 51 daily sessions each): **ESTC 0.941** (stop 2.50% · target 3.75%) · **AFRM 0.800** (stop 2.50% · target 3.75%) · **SOLS 0.588** (stop 2.74% · target 4.10%, `mfe_to_target` 2.55 flagged) · **UMC 0.555** (stop 3.35% · target 5.02%) · **GAP 0.550** (stop 2.50% · target 3.75%, `mfe_to_target` 2.73 flagged).
  - **Combined watchlist ranking by `mfe_per_stop`, all 13 names**: NVCR 1.094 · ORIC 1.064 · RGNX 0.973 · ESTC 0.941 · AFRM 0.800 · SCCO 0.659 · SOLS 0.588 · UMC 0.555 · GAP 0.550 · FCX 0.532 · XBI 0.512 · UYM 0.278 · XLB 0.248.
  - **Today's watchlist, updated: 13 names** — Materials/Metals (XLB/FCX/SCCO/SBSW/SOLS), Biotech (XBI/NVCR/RGNX/ORIC), standalone earnings/momentum movers (ESTC/GAP/AFRM/UMC).
- All premarket reads (9:01–9:07 ET) — informal/stale per C3, first formal read is 9:30. **Plan for the 10am collision with the Fed speech: the checkpoint still runs as scheduled** (verify state, manage or gate-check per the normal stack) — but treat any position entered before 10am as one to watch extra closely into the speech, and treat a 10am-adjacent entry signal skeptically until the immediate post-speech volatility has had at least one checkpoint to settle, per C9's "never force a trade" and B3's "unwanted event approaching" exit.

**9:30 observation** (first formal read, watchlist only, no new scan — C1 Gate-1 baseline, no gating decision at this checkpoint):

- Materials: XLB +0.93% (holding) · FCX -0.89% (flipped negative from premarket +1.11%) · SCCO -0.55% (flipped negative from premarket +0.80%) · SBSW +3.18% (holding, ~flat vs premarket)
- Biotech: XBI -1.49% (weaker than premarket -0.14%, doesn't gate individuals per C5) · NVCR +0.61% (weakened sharply from premarket +3.45%) · RGNX +6.30% (still strong, down from premarket +8.31%) · ORIC -1.64% (flipped negative from premarket +3.71%)
- **Real divergence from the 9:00 read**: FCX, SCCO, and ORIC all reversed to negative at the open. Only SBSW and RGNX are still clearly holding their premarket strength; NVCR faded to barely positive. 9:40's gate stack will need to weigh this — the open didn't confirm most of premarket's move.

**9:40 entry — no trade.** State check: flat, no resting orders (verified live). Day-change vs prior close: XLB +0.42% · FCX -0.77% · SCCO -0.20% · SBSW +2.86% · XBI -1.40% · NVCR -0.02% · RGNX +3.58% · ORIC -0.44%.

- **C3 (individual magnitude, ≥+0.75%)**: only SBSW and RGNX pass; FCX, SCCO, NVCR, ORIC all declined — negative or sub-threshold vs prior close.
- **C10 leg 1 (not currently falling vs the prior formal checkpoint's close)**: SBSW's 9:40 bar_close $12.61 < its 9:30 read $12.65 → **fails, blocked outright.** RGNX's 9:40 bar_close ~$9.70 < its 9:30 read $9.96 → **fails, blocked outright.** Both were real day-change winners but faded within the session since 9:30 (per B1b minute-bar pull, 13:30–13:40 UTC: SBSW range $12.585–$12.758, RGNX range $9.680–$10.100).
- **C1 Gate 1 (sector proxies)**: XLB passes legs 1–2 but fails leg 3 (9:40 +0.42% below 9:30 +0.93%) — no Materials sector-leveraged entry. XBI fails leg 1 outright (negative at 9:30) — no Biotech sector-leveraged entry. Neither gates the individual-stock declines above (C1 doesn't gate single stocks), just forecloses the sector-vehicle path too.
- **No candidate cleared the full stack.** Correct flat outcome per C5/C9 — nothing forced. Re-check resumes at the next 10:00–12:30 grid slot (management, C applies while flat) or sooner via C12 if this changes; ESTC/GAP/SOLS/AFRM/UMC remain un-added, still awaiting governor confirmation.

**10:00 management (flat, entry gate stack run fresh) — ENTRY: AFRM.** State check: flat, no resting orders going in (verified live). Day-change re-check on all 13 watchlist names: C3 (≥+0.75%) passed by SBSW, RGNX, SOLS, ESTC, GAP, AFRM, UMC — FCX/SCCO/NVCR/ORIC declined (negative or sub-threshold). C10 leg 1 (not falling vs. prior formal checkpoint): SBSW passed, **RGNX failed again** (now $9.48 vs its 9:40 read $9.70 — declined outright, second consecutive fade). The five newly-added names had no prior formal checkpoint yet, so this 10:00 read stood as their first formal baseline (leg 1 satisfied by definition) — legs 2/3 (real bounce off `session_low`, giveback ceiling) evaluated fresh from a 9:30–10:00 minute-bar pull and all five held. **C11 chop filter (ER, min 0.15 in the 9:40–10:29 band) then cut three**: SBSW 0.135, SOLS 0.057, ESTC 0.079 — all big movers but genuinely choppy on a 30-min net-progress basis (ESTC's own $108→$101.77 one-minute spike-reverse at 13:34 UTC dominated its path length). **Survivors: GAP (ER 0.339), AFRM (ER 0.266), UMC (ER 0.214).** Ranked by `mfe_per_stop`: **AFRM 0.800** · UMC 0.555 · GAP 0.550 — AFRM top-ranked and affordable (floor($234.75÷$85.58 ask) = 2 shares), so no capital-gap tiebreak needed.
- **Entry: AFRM, 2 shares @ $85.4899 fill (marketable limit $85.65, reviewed clean, no alerts) — total cost $170.98.** Slippage: filled *inside* the spread, $0.04/sh better than the $85.53 ask at review (price improvement, not slippage cost). **Stop placed and verified resting**: stop_market, 2 sh, **$83.35 (−2.50%)**, confirmed via `get_equity_orders` (state=`confirmed`). Target **3.75%** (~$88.70), `mfe_per_stop` 0.800 (top two: AFRM 0.800, UMC 0.555 — UMC named as next-best, unaffordable-gap n/a since AFRM cleared on its own rank). Catalyst: fiscal Q4 beat, $4.62 EPS vs. estimate, upbeat Q1 revenue guide (reported after-market Thursday). Intended exit: v3.44 chandelier trail off `run_high`, ratcheted every 15-min checkpoint (B2), or target, or the 12:30 close pin — whichever comes first. **Pre-commit for 10:15**: expect AFRM's `bar_close` to hold at/above the day's trail level given the post-earnings-gap trend still intact at entry (down only ~5.5% off today's $90.44 high); a close back toward the $83–84 stop zone before 10:15 would be the falsified case. **Falsified.**

**10:15 management — EXIT AFRM, pre-commit failed.** B1b since-entry pull (14:03:55–14:15 UTC) showed `run_high` never advanced past the $85.4899 fill — price fell immediately and monotonically after entry. `candidate_stop = run_high × (1−2×0.30%) = $84.98`, already **above** a fresh live quote ($84.535) by the time this checkpoint's math ran — a new mechanical edge case, distinct from both E6 failure modes: not a broker glitch, the ratchet formula itself correctly computed a level price had already fallen through, because the 2×-stall discount band is far tighter than the initial 2.5% entry cushion. Cancelled the stale $83.35 resting stop (verified cancelled), exited immediately on a marketable limit — 2sh @ $84.40 (vs. $84.50 review bid) — rather than attempt to place a stop already at/above market. **Net: -$2.18, -1.28% on the position, r=-0.510.** Full detail and the candidate E6-addendum question (whether 15-min cadence itself is the gap for a position that never advances past entry) logged in `archive/trades.csv`. Loss streak now 2 of 3 (YANG scratch, AFRM) — not tripped.
- **C12 re-entry cycle, T+0** (same turn as the exit, fill 10:03:55 ET): sector proxies both falling vs. their fill-time reads (XLB $53.29→$53.08, XBI $164.87→$164.53) and broadly negative now — no sector-leveraged path. Individual shortlist re-check vs. prior (10:00) reads: **broad pullback across the board** — SBSW/RGNX/FCX/SCCO/NVCR/ORIC all now sub-threshold or negative; SOLS/ESTC/GAP/UMC still positive but faded (ESTC 23.6%→18.2%, GAP 14.7%→15.5%, UMC 7.0%→6.5%). C7 re-ranked fresh (capital base changed on the exit) — unchanged order: UMC 0.555/GAP 0.550 next. **T+10 gate stack armed for 10:27:21 ET** (exit fill_time+10min, elapsed <10min at T+0 per C12 step 2) rather than run now — comparison baseline for that check is fixed at the **10:17:21 ET exit fill-time price** per C12 step 3, not this T+0 read. (Correction: the armed trigger's own prompt text mislabeled this as the 10:03:55 ET entry time — caught and corrected before acting on it, see below.)

**C12 T+10 mini-cycle result: no re-entry.** Re-verified against the *exit* fill timestamp (10:17:21 ET, $84.40) — the armed trigger had mislabeled this as the entry timestamp; corrected before running the check. C3 still passed by SOLS/ESTC/GAP/UMC (all comfortably above +0.75%), but **C10 leg 1 failed for all four** versus their 14:17 UTC bar-close price: SOLS $65.925→$65.520, ESTC $98.900→$98.230, GAP $23.985→$23.948, UMC $20.315→$20.220 — the broad pullback flagged at T+0 continued through T+10 rather than reversing. Correctly flat. Resume the regular grid at 10:30.

**10:30 management (flat) — no trade.** C3 still passed by SOLS/ESTC/GAP/UMC. C10 leg 1 (vs. the T+10 mini-cycle's own read, the prior formal checkpoint in the chain): ESTC and GAP still falling (declined outright); **SOLS and UMC turned — both now rising** vs. their 10:27 ET reads, cleared legs 2/3 too (real bounces off fresh session lows, giveback well under 65%). **C11 chop filter tightens to min ER 0.25 in the 10:30–11:29 band (was 0.15 before 10:30)** — both failed it: SOLS 0.076, UMC 0.198, neither making genuine net progress over the trailing 60-minute window despite real intraday range. No candidate cleared the full stack. Correctly flat, per C5/C9. Next check: 10:45.

## E6. Known issues — backlog, not yet fixed

**Stop-order placement can fail silently, in more than one way, and the pattern is escalating rather than resolving.**

*Failure mode 1 — silent zero-fill cancellation.* Comes back `cancelled` with zero fill and no error message. First observed 2026-08-24 (twice, MSTX, both resolved on one retry, no real exposure). Escalated 2026-08-25: SMCX's 10:00 checkpoint hit it three times in a row on the same placement — price moved through the intended stop level during the unprotected gap, forcing a manual marketable-limit exit. Real exposure, not a near-miss.

*Failure mode 2 — outright rejection when the stop price is at/above the live market.* First identified 2026-08-25, UUUU's 11:30 checkpoint: the correctly-computed new stop ($15.93) was placed a moment after price had already pulled back below it ($15.87) — the order came back `rejected`, not `cancelled`, with a clear enough pattern to name the likely cause: the broker won't accept a sell-stop whose trigger condition is already satisfied at placement time (it should really be an immediate market order, not a resting stop, and the API appears to refuse rather than convert it). The follow-on manual exit had its own near-miss: the first marketable-limit attempt used a bid that had already gone stale by the time it posted, landed as a passive (non-marketable) resting order instead of an immediate fill, and had to be cancelled and re-priced against a fresh quote before it actually executed — a reminder that "marketable" only holds for as long as the quote it was priced against.

**Mitigation is manual, not systemic — and the governor has explicitly reviewed that trade-off and accepted it, 2026-08-25.** After every stop placement, verify it actually landed via `get_equity_orders` before considering the position protected; retry immediately if it didn't, and if the retry keeps failing, re-check the live price before retrying blind — a rejection can mean the stop level itself is stale, not just that the placement call needs repeating. This has caught every incident so far (2026-08-24 ×2, 2026-08-25 ×2, one per failure mode) with zero losses attributable to the glitch itself — both 2026-08-25 incidents closed as real wins (SMCX +$4.25, UUUU +$6.86), not losses. Governor's read: today's names (SMCX, UUUU) are fundamentally fast-moving instruments, some order-placement friction against that kind of tape isn't itself alarming, and the current catch-verify-retry-or-exit process is working — **keep doing what's been done**, not a directive to build the automatic wrapper urgently.

**Still worth building eventually, no longer treated as urgent.** An automatic retry-and-verify wrapper around stop placement — place, confirm via a follow-up read, re-check price before a blind retry, all without waiting on a manual catch — remains a real improvement over a human-speed read-decide-act loop inside a moving market. But per governor sign-off, this stays a nice-to-have on the backlog, not a same-day priority. Revisit if a future incident actually produces a loss (not just forced friction on a winning trade), or if the failure rate climbs further.

---

## Current state

**v3.46 (10:36 ET, governor session, live mid-day): C10 leg 1's baseline fixed to 9:30, reset only by an exit's fill timestamp (C12) — never by an intervening checkpoint.** Prompted by today's own 10:00 entry, where the five newly-added candidates (ESTC/GAP/SOLS/AFRM/UMC, added ~9:50) had no 9:30 read of their own, so their first C10 check was treated as an ad hoc free pass. Governor's proposed fix, confirmed: a candidate's first-ever entry check of the day always compares against 9:30's real price (pulled fresh via historicals if it joined the watchlist later), no matter which checkpoint that first entry attempt lands on — 9:40, 10:00, or later all compare back to 9:30 alike, since merely re-checking a candidate without entering it doesn't advance the baseline. The one thing that does advance it: an exit (C12), which resets the baseline to that exit's fill-timestamp price for every shortlist candidate being reconsidered, not just the one that closed — already how today's post-AFRM T+0/T+10 mini-cycle worked, now made the general rule rather than a special case. No effect on any decision already made today (AFRM's entry, the 10:00/10:30 checkpoints) — those stand as executed under the rule in force at the time; this governs from here forward.

**Friday 2026-08-28, 10:17 ET: flat again.** AFRM entered 10:03:55 ET, exited 10:17:21 ET at the 10:15 checkpoint when the chandelier trail math computed a stop already breached by live price — net -$2.18, r=-0.510. Full detail in E5/`archive/trades.csv`. C12 re-entry T+10 check armed for 10:27:21 ET. Buying power ~$232.57 (unsettled AFRM proceeds usable immediately, limited-margin account).

**Prior to today — flat, governor paused the session mid-day Thursday 2026-08-27 (~10:48 ET) to work on rulebook changes that evening.** Cash/buying power $234.76, no resting orders (verified live). Net **+$10.69 on the partial day**, two trades before the pause: MSTX (+$11.41, r=+0.899, 9:43–10:11 ET, a real ratchet/velocity win — the v3.40 redesign's first live proof, locking gains before a 9.2%-run reversal) and YANG (-$0.72, r=-0.124, 10:34–10:48 ET, entered via C12's re-entry cycle after the MSTX exit, then closed by the governor's manual off-cycle exit to stop for the day — a trivial scratch, not a rule-driven exit, same convention as the 2026-08-20 MSTX governor exit). Today was also the first live day under v3.41/v3.42 (sector-first research, 24-name/6-sector watchlist) — both worked as intended; two brand-new sector themes (Financials-reversal, China-reversal) surfaced specifically because of the sector-first survey. **All of today's remaining checkpoints (11:00 through 8:00pm) were deleted per governor instruction; tomorrow's (Friday 8/28) grid was armed manually since the normal 4:00pm auto-arming didn't run, then rebuilt again that same evening once v3.43 shortened the day — Friday now runs a 15-trigger grid (9:00/9:30/9:40 plus 10:00–12:30 on the new 15-min cadence, plus 8:00pm backup), not the original 17-slot version.**

**v3.38–v3.42 all applied and confirmed working live**: the 8-stage ratchet replacing the old 4-stage structure and B4's fixed profit-target removal (v3.38–v3.40), D2's sector-first/leveraged-priority research methodology (v3.41), and the watchlist expansion to 24 names / 6 sectors of 4 (v3.42).

**v3.43 (evening of 8/27, governor session): a full restructure driven by the data — every profitable entry across the system's history has landed between 9:42 and 10:34 ET, and the one entry after 10:34 (MSTX 8/21, 12:32pm) lost money.** Trading day shortened to 9:00–12:30 (was 9:00–4:00pm); management checkpoints now run every 15 minutes from 10:00–12:30 (was 30 minutes to 4:00pm), net *fewer* total daily checkpoints (15 vs 17) despite the tighter cadence. Entries valid anywhere 9:40–12:30, no preferred-window distinction. **B2's stepped 8-stage ratchet is retired, replaced by a continuous rule**: every 15-min checkpoint ratchets the stop to `avg_price(since last checkpoint) × (1 − stall_threshold_pct)`, per-instrument noise-scaled, up only — validated against MSTX's actual 8/27 bars before adoption (would have exited +5.79% vs. the real trade's velocity-driven +5.37%). The velocity trigger is unchanged, still the faster-reacting override for a single sharp spike. The 12:30 checkpoint additionally pins the stop to live price, which is what now enforces same-day close — no separate 4:00pm deadline. **B3's stall-count ladder is retired entirely** — the continuous ratchet already squeezes a stalling position without a second, potentially-conflicting counting mechanism. C11's chop-filter table compressed to 3 bands fitting 9:40–12:30. No more extended-hours slots (4:30–7:30pm gone) or cadence-reduction rule (both moot with the day already this short).

**v3.44 (evening of 8/27, same governor session, continued): the average-based ratchet replaced by a single continuous chandelier trail anchored to `run_high`, and the separate velocity trigger retired.** Governor's own read of the old (pre-v3.40) system: the entry-time stop was its best feature, but the staged ratchet triggered too rarely and moved too linearly. Backtested against all 13 trades on record (real minute-bar paths, each instrument's own noise band from its real ~40-day history) sweeping a discount multiplier 1×–5× off `run_high`: **`candidate_stop = run_high × (1 − 2 × stall_threshold_pct)`, `new_stop = max(current_stop, candidate_stop)`, checked every 15-min checkpoint** — 2× beat the real historical results on both average captured gain (+1.56% vs. the real system's +1.53%) and win rate (9/12 vs. 7/12), fixing two real reversal losses (UEC 8/26 -2.54%→+0.26% simulated; MSTX 8/20 -1.24%→+1.02% simulated) without giving other reversals extra room, unlike wider multipliers (4×–5×) which scored higher only because of one outlier trend day (MSTX 8/27 continuing to run for hours past its real exit) while making two genuine reversals worse. Anchoring to `run_high` instead of the trailing average is what gives a real trend room to breathe — the average sits close to the entry price right after a fill, so a normal early pullback could trip the old design before a trend had even formed (found via a separate before/after check on UUUU 8/25: the average-based design would have cut a real +$6.86 winner down to roughly breakeven). The velocity trigger is retired — anchoring continuously to `run_high` already gives the fast-reaction behavior it existed for, without a second mechanism running in parallel.

**v3.45 (evening of 8/27, same governor session, continued): lean cleanup — no trading behavior changed.** Two genuinely dead numbers, `breakeven_trigger` and `trail_pct`, are fully retired (not just unused): `tools/profile.py` no longer computes or prints them, B1's formula list drops them, and C8's required entry report no longer asks for them — both had been superseded by the trail redesign but kept getting computed and reported anyway, on every single profile call and every entry. B2/B3/B4's detailed backtest-rationale and retirement-history prose (why 2× not another multiplier, why the stall ladder and average-ratchet were removed) is trimmed to one-line pointers — the full reasoning already lives in this section's own v3.43/v3.44 paragraphs and the git history, so restating it in the text read at every single management checkpoint was pure duplication. D1's "never delete the 12:30/8:00 checkpoints" line, which repeated A2's rule verbatim even though Part A is read at every checkpoint including D1's own readers, is now a one-line cross-reference. Net: same gates, same stop math, same thresholds — fewer tokens read per checkpoint, forever. **Follow-up, same evening:** `archive/EXPERIMENTS.md` swept clean too, on explicit request — all 16 entries (EXP-001–016) dated back to a pre-RULEBOOK.md architecture (`OPERATIONS.md` §-sections, `tools/replay.py`, `tools/calibrate_stops.py`, `tools/preflight.py`, none of which exist anymore) moved from Open to Closed and marked accurately: EXP-007/008's scaled-stop/scaled-target findings are still exactly how B1 works (`LIVE`, kept in full); EXP-015's inverse-vehicle Gate-1 concern turned out to already be resolved in current C1 (real DUST/YANG/ZSL/FAZ trades confirm it evaluates each vehicle's own self-referencing day change); the rest are `KILLED` with a one-line reason each — mechanism retired (stall ladder, old trail), infrastructure gone (preflight's map, replay.py), or premise weakened (target-reachability checks matter less once no exit is target-triggered). 348 lines → 152. **Second follow-up:** a more urgent find while auditing token cost — the 10 already-armed Friday 10:00–12:15 management triggers still carried their original prompt text from before v3.44, describing the retired average-based ratchet formula verbatim. Not just a token cost; if ever followed literally instead of re-reading this file fresh, it would apply the wrong stop math live. All 12 Friday triggers from 10:00 through 8:00pm rewritten to the terse, rulebook-pointing convention already used by 9:00/9:30/9:40 ("read RULEBOOK.md per its own READ MAP — ignore any rule content cached in this prompt"), verified via each `update_trigger` response. Also checked and rejected: pulling full-session minute bars at every checkpoint instead of reading `run_high` back out of E5's log — a 2.5-hour session's bars run ~5,600 tokens raw, more expensive than E5's own compact log for that stretch, so the current design stands.

Prior trades: 2026-08-27 YANG (-$0.72, r=-0.124, governor manual exit); 2026-08-27 MSTX (+$11.41, r=+0.899); 2026-08-26 UEC (-$5.54, r=-0.998); 2026-08-25 UUUU (+$6.86, r=+1.238); 2026-08-25 SMCX (+$4.25, r=+0.293); 2026-08-24 MSTX (+$13.81, r=+1.050); 2026-08-21 MSTX (-$0.14, r=-0.011); 2026-08-21 CONL (+$2.51, r=+0.230); 2026-08-20 MSTX (-$0.54, r=-0.201, governor's off-cycle exit, not rule-triggered); 2026-08-19 GUSH (+$0.22, r=+0.194).

**Loss streak 1 of 3** (the YANG scratch). Deposited capital ≈ $201.48 (all-time realized P&L ≈ +$33.28), floor ≈ $100.74 — not binding.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
