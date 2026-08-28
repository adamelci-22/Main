# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.45.** Bump on every rule/threshold change; record it in the commit.

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

**One `run_high`, shared with C10 — not a second high-water mark.** `run_high` is `max(run_high, bar_high)` at every checkpoint (B1b) — the true highest price reached in the gap, not a lucky-or-unlucky point sample. Advances on any fresh interval high, unconditionally.

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

**No stall-count ladder** — the continuous trail (B2) already squeezes a stalling position every checkpoint; a second counting mechanism would just risk disagreeing with it. (Retired v3.43 — see Current State / git history for why.) `run_high` stays defined (B2, shared with C10).

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

1. **Not currently falling.** This checkpoint's `bar_close` ≥ the immediately prior formal checkpoint's `bar_close`, for this candidate specifically — **"immediately prior" means whichever checkpoint actually ran last in real time, grid or C12 ad hoc, never a reach-back past it to the last *scheduled* slot.** One exception, owned by C12 not restated here: a C12 mini-cycle's own opening gate-stack pass compares against the candidate's price at the exit's fill timestamp instead (C12 steps 3–4 have the full rule and worked example — read there, not here, if this exception is in play). (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched.
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

**Thursday 2026-08-27, 9:00 research** (run on time, ~9:01–9:07 ET; first day under v3.41 sector-first/leveraged-priority methodology and v3.42's 24-name/6-sector structure):

- Headlines: Nasdaq futures +~1% premarket on Nvidia's bullish FY28 sales-growth guidance from its CFO — semis the dominant story. SPY flattish, gold -0.45%, Brent crude -0.63%. Earnings today: RBC, TD Bank, Dollar General, Best Buy. [Bloomberg](https://www.bloomberg.com/news/articles/2026-08-26/nasdaq-futures-rise-on-bullish-nvidia-sales-growth-markets-wrap), [TheStreet](https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-aug-26-2026)
- **Sector-first survey (v3.41): 20+ proxies checked premarket** (SMH/QQQ/SPY/IWM/XLE/USO/UNG/GDX/SLV/GLD/XBI/XLB/COPX/URA/FXI/EWY/IBIT/VXX/XLF/XLI/XLU/XLY/TLT). Standouts: SMH +2.41% (dominant, Nvidia-driven), XLF -0.77% (confirmed real by JPM/BAC/GS/MS/WFC all down), FXI -0.65% (confirmed by BABA/JD/PDD all down), GDX -0.78% (confirmed by DUST/JDST/ZSL premarket strength), XLB/COPX -0.66%/-0.98% (confirmed by FCX/SCCO down, but vehicle SMN/UYM showing broken premarket spreads — **dropped for liquidity, not magnitude**). EWY +2.08% looked live but its only real constituent checked (CPNG +0.24%) didn't confirm it — likely thin premarket noise, **dropped**. Uranium (URA/URNM) and nat-gas E&P (EQT/EXE/RRC) both flat today — dropped. Crypto (IBIT +1.03%) confirmed strongly by MSTR +2.10%/CLSK +2.38%/RIOT +1.99%/MARA +1.95%/COIN +1.30%. Biotech (XBI -0.41%, doesn't gate individuals) — live scan found VEEV +8.06% real and liquid despite the proxy being negative.
- **6 sectors selected, full 24-name structure:**
  - **Semis** — proxy SMH +2.41%. Individuals (leveraged, ranked by underlying group move): NVDL (NVDA +6.03%), MUU (MU +3.60%), SMCX (SMCI +3.50%) — AVGO +1.34%/TSM +1.20%/AMD +0.73% ranked lower, not top-3.
  - **Crypto** — proxy IBIT +1.03%. Individuals (leveraged, normalized for embedded 2x): MSTX (MSTR, raw +4.23%→norm +2.12%), CONL (COIN, raw +2.70%→norm +1.35%), BITU (raw +2.10%→norm +1.05%) — BITX/ETHU/ETHT all ~+1.0% or lower, not top-3.
  - **Precious metals reversal** (inverse-long) — formal proxy GDX -0.78% (vehicles move opposite by design, self-referencing day change like yesterday). Vehicles: DUST +1.10%, JDST +1.01%, ZSL +0.56%.
  - **Biotech** — proxy XBI -0.41% (doesn't gate individuals). Plain-stock individuals, real gainers via live scan: VEEV +8.06% (Veeva Systems, $39.8B cap, liquid), GENB +5.95% (Generate Biomedicines), SMMT +3.37%. ARCT was down today (-0.88%, dropped); ZYME +1.90% ranked below the top 3.
  - **Financials reversal** (inverse-long, new theme) — proxy XLF -0.77%. Vehicle FAZ +1.92% (self-referencing, liquid). Plain-stock individuals (top 2 decliners, confirming the thesis): JPM -0.74%, GS -0.52%.
  - **China reversal** (inverse-long, new theme) — proxy FXI -0.65%. Vehicle YANG +1.87% (self-referencing, liquid). Plain-stock individuals (top 2 decliners): BABA -1.60%, JD -0.70%.
  - **6 sectors × 3 names = 18 individuals, plus the 6 proxies = 24 total (6 groups of 4).**
- Profiles (`tools/profile.py`, 40 daily sessions each), ranked by `mfe_per_stop`: MSTX 0.997 · VEEV 0.940 · BITU 0.818 · CONL 0.799 · GENB 0.733 · SMCX 0.695 · MUU 0.606 · SMMT 0.586 · ZSL 0.549 · DUST 0.542 · FAZ 0.534 · JDST 0.523 · BABA 0.485 · NVDL 0.404 · JD 0.396 · YANG 0.367 · GS 0.321 · JPM 0.300. **VEEV (~$265), JPM (~$354), GS (~$1035) are unaffordable at whole-share level** against $224.07 settled cash — included anyway per rule, they measure what capital is costing.
- Buying power $224.07 (unchanged from yesterday's close), unsettled funds $0. Deposited ≈$201.48, floor ≈$100.74, not binding.
- **Today's watchlist: 24 names (6 proxies + 18 individuals)** — SMH/NVDL/MUU/SMCX, IBIT/MSTX/CONL/BITU, GDX/DUST/JDST/ZSL, XBI/VEEV/GENB/SMMT, XLF/FAZ/JPM/GS, FXI/YANG/BABA/JD.
- All premarket reads (9:01–9:07 ET) — informal/stale per C3, first formal read is 9:30.
- **9:30 observation (C1 baseline, first formal read).** Proxies: SMH +2.71% (holding, even stronger) · IBIT +1.06% · GDX **+0.32%, flipped positive** — inverse vehicles now negative, metals-reversal thesis reversed at the open · XBI -0.45% (doesn't gate) · XLF -0.70% · FXI -0.72%. Individuals: NVDL +13.34% ✓ · MUU +5.46% ✓ · SMCX +5.95% ✓ · MSTX +6.28% ✓ · CONL +2.01% ✓ · BITU +2.17% ✓ · **DUST -0.55%, JDST -0.81%, ZSL -0.47% — all flipped negative, not holding** · VEEV +12.44% ✓ (stronger) · GENB +1.64% (weaker but still positive) · SMMT +2.46% (weaker but still positive) · FAZ +2.34% ✓ (stronger) · JPM -0.61% · GS -0.21% · YANG +2.11% ✓ (stronger) · BABA -1.98% · JD -1.02%. **Precious-metals reversal's C1 leg 1 already fails** (vehicles negative at 9:30, not positive) — dead for the formal 9:40 entry, late-entry clause only if a vehicle later exceeds its own 9:30 print. Semis, Crypto, Financials-reversal, China-reversal all holding cleanly. 9:40 re-confirms live.
- **9:40 entry.** **C1 re-run for the 3 sector-leveraged trades**: Financials-reversal (FAZ) **fails leg 3** — faded from +2.34% at 9:30 to +0.55% at 9:40, below its own baseline. China-reversal (YANG) **clears all 3 legs** — +2.11%→+2.15%, still positive and not below 9:30. Metals-reversal stays dead (already failed leg 1 at 9:30). **C2 Gate 2 re-ranked live for Semis and Crypto** (full E3 group, not just this morning's picks): Semis top 3 = NVDA(+7.42%)/SMCI(+2.82%)/AVGO(+2.64%) — **MU dropped out of top 3** (+0.52%, now also fails C3 magnitude outright), AMD negative. Crypto top 3 = MARA(+4.59%)/CLSK(+4.27%)/MSTR→MSTX(+3.32%) — **COIN/CONL and BITU both dropped out of top 3**. **AVGX, MARA, CLSK were never profiled this morning (picked MUU/CONL/BITU instead based on premarket ranking) — no risk numbers, so no trade regardless of today's ranking (A1: no profile → no trade)**, a real, disclosed gap from this morning's pre-open picks not matching the live 9:40 group re-rank. Actionable survivors (profiled + gates clear): NVDL, SMCX (Semis); MSTX (Crypto); VEEV, GENB (Biotech, SMMT failed C3 at 0.00%); YANG (China-reversal). C10 checked for all six via B1b (13:30–13:41 ET range, first formal window): all six clear — NVDL/YANG at fresh session highs, SMCX/MSTX/VEEV/GENB show real pullback-and-bounce (GENB's giveback 46%, an early-spike pattern like PLAB's but well under the 65% ceiling). C11 auto-passes for all (only ~11min of window, under the ~20min meaningful threshold, flagged not genuine). Ranked by `mfe_per_stop`: **MSTX 0.997** · VEEV 0.940 · GENB 0.733 · SMCX 0.695 · NVDL 0.404 · YANG 0.367. **Entered MSTX 9:43:52 ET, 15sh @ $14.1699 avg ($212.55 total), stop $13.32 (-5.97%) confirmed resting on the first attempt** — target $15.44 (+8.96%, mfe_to_target 1.51, well reachable), breakeven trigger +5.95%, trail 3.98%, mfe_per_stop 0.997 (top-ranked, VEEV 0.940 second — VEEV unaffordable at whole-share level anyway, ~$287/share vs $224 cash). Spread priced: bid/ask $14.15/$14.16 at review, ~0.07%, trivial against target. Pre-commit: exit at next checkpoint if bar_close falls back below today's session_low with no fresh bounce, or if the stall ladder/velocity trigger fires per B2/B3.
- **10:00 management (holding MSTX).** Strong run already: `run_high` $15.075 (+6.39% from fill), now $15.13. **Velocity trigger fired** — checkpoint_gain 6.39% vs the 2.67% threshold (3×0.89% stall_pct), well past. Ratchet is past stage 7 (breakeven, needed +5.95%) into stage 8 continuous trail: trail-stop $14.475 (3.98% trail). Velocity's own trail (0.89%) is tighter and wins: $14.9408. **Stop moved $13.32→$14.94**, cancelled old / placed new, confirmed resting on the first attempt — locks in a real gain (+5.44% floor) this early in the hold. B4 target ($15.44) not reached yet, no longer a forced-sell trigger regardless (v3.40). B5 headlines not due (next due ~10:32). **B6 shortlist snapshot** (bar_high/low/close, 13:43–14:02 ET): NVDL $36.530/$35.464/$36.400 · SMCX $13.447/$12.799/$12.890 · VEEV $296.155/$286.640/$294.955 · GENB $16.925/$16.500/$16.750 · YANG $29.220/$29.030/$29.190 — all still holding roughly their 9:40 levels, nothing dramatic. Pre-commit: exit at 10:30 if bar_close falls back below the new $14.94 floor (stop does that automatically) or below `run_high` by more than a real reversal, or if a 2nd consecutive stall occurs post-velocity per B2/B3.
- **MSTX stop fired 10:11:31 ET** — 11 min after the 10:00 checkpoint. Price ran to a true high of $15.470 at 10:04 ET (+9.18% MFE) then reversed; the ratchet's raised stop ($14.94, set at 10:00) caught it cleanly, filled $14.9303 ($0.0097 below trigger, normal stop-market slippage). **Net +$11.41, +5.37%, r=+0.899 — a real win**, exactly the behavior the v3.40 redesign (8-stage ratchet + velocity, no fixed profit target) was built for: locking in gains before a round-trip back to breakeven. True MAE for the full 28min hold was trivial (-0.21%, the entry bar's own low). Loss streak resets to 0 of 3. Full detail in `archive/trades.csv`.
- **10:30 management / C12 gate stack (fill-anchored 14:11:31Z baseline, elapsed 19min ≥10 — ran immediately, same as this checkpoint).** **C1 re-checked**: Financials-reversal (FAZ) now exceeds its 9:30 baseline (+2.53% vs +2.34%) — late-entry clears — but then **fails C12's own leg 1** (14:11Z baseline $31.616 vs now $31.610, essentially flat/marginally down). China-reversal (YANG) clears both C1 and C12 leg 1 cleanly (14:11Z $29.12 vs now $29.12+, not below). Metals-reversal stays dead. **C2 re-ranked**: Semis top 3 unchanged (NVDA/AVGO/SMCI — AVGX still unprofiled, excluded); Crypto top 3 = MSTR→MSTX/MARA/CLSK (MARA/CLSK still unprofiled, excluded — same disclosed gap as 9:40). Biotech: **SMMT newly clears C3** (+0.81%, recovered above the 0.75% floor). **C10 (fill-timestamp baseline) run for all 8 profiled survivors**: SMCX, VEEV, GENB, FAZ all **fail leg 1 outright** (falling since 14:11Z). NVDL, MSTX, SMMT, YANG pass leg 1. Of those, **MSTX fails leg 2** (bounce not yet confirmed — only 1min since its own fresh high, a genuine "wait, don't force it" case per C10's own text, not a permanent block). NVDL, SMMT, YANG clear C10 fully (SMMT's giveback a real 58.9%, worth flagging as close to the 65% ceiling though still under it). **C11 (trailing 60min, script-computed) decides it**: NVDL 0.0481 and SMMT 0.0059 both **fail decisively** against the 0.15 minimum (9:40–10:59 window) despite clean C10 — genuinely choppy. **YANG clears at 0.1998** — the only full-stack survivor. **Entered YANG 10:34:19 ET, 8sh @ $29.11 avg ($232.88 total), stop $28.38 (-2.50%) confirmed resting on the first attempt** — target $29.20→$30.20 (+3.75%), breakeven trigger +1.25%, trail 1.49%, mfe_per_stop 0.367 (only survivor, no ranking needed). Spread priced: bid/ask $29.11/$29.12 at review, ~0.03%, trivial. Pre-commit: exit at 11:00 if bar_close falls back below today's session_low with no fresh bounce, or if the stall ladder/velocity trigger fires per B2/B3.
- **Governor evening session, v3.43 rollout complete.** Rulebook rewritten and pushed (commit `9fb8d87`) per the shortened 9:00–12:30 day / 15-min continuous-ratchet redesign discussed above. Friday 8/28's trigger grid — armed earlier that evening under the old 30-min/4:00pm schedule — rebuilt to match: kept the content-unaffected 9:00/9:30/9:40 triggers, deleted the 14 stale 10:00am–8:00pm triggers, created 12 new ones on the v3.43 15-min grid (10:00 · 10:15 · 10:30 · 10:45 · 11:00 · 11:15 · 11:30 · 11:45 · 12:00 · 12:15 management, 12:30 close+primary-arming instructing Monday 8/31's grid to be armed per D1, 8:00pm backup verification). Verified via `list_triggers`: 15 Friday-dated checkpoint triggers total, one per slot, no gaps or duplicates. Friday's session is live under v3.43 from the open.

## E6. Known issues — backlog, not yet fixed

**Stop-order placement can fail silently, in more than one way, and the pattern is escalating rather than resolving.**

*Failure mode 1 — silent zero-fill cancellation.* Comes back `cancelled` with zero fill and no error message. First observed 2026-08-24 (twice, MSTX, both resolved on one retry, no real exposure). Escalated 2026-08-25: SMCX's 10:00 checkpoint hit it three times in a row on the same placement — price moved through the intended stop level during the unprotected gap, forcing a manual marketable-limit exit. Real exposure, not a near-miss.

*Failure mode 2 — outright rejection when the stop price is at/above the live market.* First identified 2026-08-25, UUUU's 11:30 checkpoint: the correctly-computed new stop ($15.93) was placed a moment after price had already pulled back below it ($15.87) — the order came back `rejected`, not `cancelled`, with a clear enough pattern to name the likely cause: the broker won't accept a sell-stop whose trigger condition is already satisfied at placement time (it should really be an immediate market order, not a resting stop, and the API appears to refuse rather than convert it). The follow-on manual exit had its own near-miss: the first marketable-limit attempt used a bid that had already gone stale by the time it posted, landed as a passive (non-marketable) resting order instead of an immediate fill, and had to be cancelled and re-priced against a fresh quote before it actually executed — a reminder that "marketable" only holds for as long as the quote it was priced against.

**Mitigation is manual, not systemic — and the governor has explicitly reviewed that trade-off and accepted it, 2026-08-25.** After every stop placement, verify it actually landed via `get_equity_orders` before considering the position protected; retry immediately if it didn't, and if the retry keeps failing, re-check the live price before retrying blind — a rejection can mean the stop level itself is stale, not just that the placement call needs repeating. This has caught every incident so far (2026-08-24 ×2, 2026-08-25 ×2, one per failure mode) with zero losses attributable to the glitch itself — both 2026-08-25 incidents closed as real wins (SMCX +$4.25, UUUU +$6.86), not losses. Governor's read: today's names (SMCX, UUUU) are fundamentally fast-moving instruments, some order-placement friction against that kind of tape isn't itself alarming, and the current catch-verify-retry-or-exit process is working — **keep doing what's been done**, not a directive to build the automatic wrapper urgently.

**Still worth building eventually, no longer treated as urgent.** An automatic retry-and-verify wrapper around stop placement — place, confirm via a follow-up read, re-check price before a blind retry, all without waiting on a manual catch — remains a real improvement over a human-speed read-decide-act loop inside a moving market. But per governor sign-off, this stays a nice-to-have on the backlog, not a same-day priority. Revisit if a future incident actually produces a loss (not just forced friction on a winning trade), or if the failure rate climbs further.

---

## Current state

**Flat, governor paused the session mid-day Thursday 2026-08-27 (~10:48 ET) to work on rulebook changes that evening.** Cash/buying power $234.76, no resting orders (verified live). Net **+$10.69 on the partial day**, two trades before the pause: MSTX (+$11.41, r=+0.899, 9:43–10:11 ET, a real ratchet/velocity win — the v3.40 redesign's first live proof, locking gains before a 9.2%-run reversal) and YANG (-$0.72, r=-0.124, 10:34–10:48 ET, entered via C12's re-entry cycle after the MSTX exit, then closed by the governor's manual off-cycle exit to stop for the day — a trivial scratch, not a rule-driven exit, same convention as the 2026-08-20 MSTX governor exit). Today was also the first live day under v3.41/v3.42 (sector-first research, 24-name/6-sector watchlist) — both worked as intended; two brand-new sector themes (Financials-reversal, China-reversal) surfaced specifically because of the sector-first survey. **All of today's remaining checkpoints (11:00 through 8:00pm) were deleted per governor instruction; tomorrow's (Friday 8/28) grid was armed manually since the normal 4:00pm auto-arming didn't run, then rebuilt again that same evening once v3.43 shortened the day — Friday now runs a 15-trigger grid (9:00/9:30/9:40 plus 10:00–12:30 on the new 15-min cadence, plus 8:00pm backup), not the original 17-slot version.**

**v3.38–v3.42 all applied and confirmed working live**: the 8-stage ratchet replacing the old 4-stage structure and B4's fixed profit-target removal (v3.38–v3.40), D2's sector-first/leveraged-priority research methodology (v3.41), and the watchlist expansion to 24 names / 6 sectors of 4 (v3.42).

**v3.43 (evening of 8/27, governor session): a full restructure driven by the data — every profitable entry across the system's history has landed between 9:42 and 10:34 ET, and the one entry after 10:34 (MSTX 8/21, 12:32pm) lost money.** Trading day shortened to 9:00–12:30 (was 9:00–4:00pm); management checkpoints now run every 15 minutes from 10:00–12:30 (was 30 minutes to 4:00pm), net *fewer* total daily checkpoints (15 vs 17) despite the tighter cadence. Entries valid anywhere 9:40–12:30, no preferred-window distinction. **B2's stepped 8-stage ratchet is retired, replaced by a continuous rule**: every 15-min checkpoint ratchets the stop to `avg_price(since last checkpoint) × (1 − stall_threshold_pct)`, per-instrument noise-scaled, up only — validated against MSTX's actual 8/27 bars before adoption (would have exited +5.79% vs. the real trade's velocity-driven +5.37%). The velocity trigger is unchanged, still the faster-reacting override for a single sharp spike. The 12:30 checkpoint additionally pins the stop to live price, which is what now enforces same-day close — no separate 4:00pm deadline. **B3's stall-count ladder is retired entirely** — the continuous ratchet already squeezes a stalling position without a second, potentially-conflicting counting mechanism. C11's chop-filter table compressed to 3 bands fitting 9:40–12:30. No more extended-hours slots (4:30–7:30pm gone) or cadence-reduction rule (both moot with the day already this short).

**v3.44 (evening of 8/27, same governor session, continued): the average-based ratchet replaced by a single continuous chandelier trail anchored to `run_high`, and the separate velocity trigger retired.** Governor's own read of the old (pre-v3.40) system: the entry-time stop was its best feature, but the staged ratchet triggered too rarely and moved too linearly. Backtested against all 13 trades on record (real minute-bar paths, each instrument's own noise band from its real ~40-day history) sweeping a discount multiplier 1×–5× off `run_high`: **`candidate_stop = run_high × (1 − 2 × stall_threshold_pct)`, `new_stop = max(current_stop, candidate_stop)`, checked every 15-min checkpoint** — 2× beat the real historical results on both average captured gain (+1.56% vs. the real system's +1.53%) and win rate (9/12 vs. 7/12), fixing two real reversal losses (UEC 8/26 -2.54%→+0.26% simulated; MSTX 8/20 -1.24%→+1.02% simulated) without giving other reversals extra room, unlike wider multipliers (4×–5×) which scored higher only because of one outlier trend day (MSTX 8/27 continuing to run for hours past its real exit) while making two genuine reversals worse. Anchoring to `run_high` instead of the trailing average is what gives a real trend room to breathe — the average sits close to the entry price right after a fill, so a normal early pullback could trip the old design before a trend had even formed (found via a separate before/after check on UUUU 8/25: the average-based design would have cut a real +$6.86 winner down to roughly breakeven). The velocity trigger is retired — anchoring continuously to `run_high` already gives the fast-reaction behavior it existed for, without a second mechanism running in parallel.

**v3.45 (evening of 8/27, same governor session, continued): lean cleanup — no trading behavior changed.** Two genuinely dead numbers, `breakeven_trigger` and `trail_pct`, are fully retired (not just unused): `tools/profile.py` no longer computes or prints them, B1's formula list drops them, and C8's required entry report no longer asks for them — both had been superseded by the trail redesign but kept getting computed and reported anyway, on every single profile call and every entry. B2/B3/B4's detailed backtest-rationale and retirement-history prose (why 2× not another multiplier, why the stall ladder and average-ratchet were removed) is trimmed to one-line pointers — the full reasoning already lives in this section's own v3.43/v3.44 paragraphs and the git history, so restating it in the text read at every single management checkpoint was pure duplication. D1's "never delete the 12:30/8:00 checkpoints" line, which repeated A2's rule verbatim even though Part A is read at every checkpoint including D1's own readers, is now a one-line cross-reference. Net: same gates, same stop math, same thresholds — fewer tokens read per checkpoint, forever. **Follow-up, same evening:** `archive/EXPERIMENTS.md` swept clean too, on explicit request — all 16 entries (EXP-001–016) dated back to a pre-RULEBOOK.md architecture (`OPERATIONS.md` §-sections, `tools/replay.py`, `tools/calibrate_stops.py`, `tools/preflight.py`, none of which exist anymore) moved from Open to Closed and marked accurately: EXP-007/008's scaled-stop/scaled-target findings are still exactly how B1 works (`LIVE`, kept in full); EXP-015's inverse-vehicle Gate-1 concern turned out to already be resolved in current C1 (real DUST/YANG/ZSL/FAZ trades confirm it evaluates each vehicle's own self-referencing day change); the rest are `KILLED` with a one-line reason each — mechanism retired (stall ladder, old trail), infrastructure gone (preflight's map, replay.py), or premise weakened (target-reachability checks matter less once no exit is target-triggered). 348 lines → 152.

Prior trades: 2026-08-27 YANG (-$0.72, r=-0.124, governor manual exit); 2026-08-27 MSTX (+$11.41, r=+0.899); 2026-08-26 UEC (-$5.54, r=-0.998); 2026-08-25 UUUU (+$6.86, r=+1.238); 2026-08-25 SMCX (+$4.25, r=+0.293); 2026-08-24 MSTX (+$13.81, r=+1.050); 2026-08-21 MSTX (-$0.14, r=-0.011); 2026-08-21 CONL (+$2.51, r=+0.230); 2026-08-20 MSTX (-$0.54, r=-0.201, governor's off-cycle exit, not rule-triggered); 2026-08-19 GUSH (+$0.22, r=+0.194).

**Loss streak 1 of 3** (the YANG scratch). Deposited capital ≈ $201.48 (all-time realized P&L ≈ +$33.28), floor ≈ $100.74 — not binding.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
