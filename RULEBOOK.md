# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.68.** Bump on every rule/threshold change; record it in the commit.

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
| **9:40** entry | A · C | The primary entry slot (v3.56 — moved back to 9:40, reverting v3.54's shift to 9:35) |
| **9:45–11:15** management ×19 (5-min cadence, v3.64) | A · B (+ C — entries valid anywhere in this window) | Holding, or flat and open to a fresh opportunity — a single uniform 5-minute cadence throughout (v3.64 — tightened from the 10-min cadence, 9:45's own first-slot special status is now moot since every slot is 5 minutes from the last) |
| **11:30** close | A · B4 · D | Exit, report, and arm tomorrow (primary) — direct market sell if still open (v3.58; v3.60 — close moved from 11:00 to 11:30; v3.64 — management cadence between 9:45 and 11:15 tightened to 5 minutes, the close mechanic itself unchanged). The 15-min-cadence 11:15–11:45 stretch and the old 12:00 slot remain retired outright, not revived. |
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

**Most recent governor clearance of the breaker: 2026-09-14** — count only trades closed after that date (E1). (Tripped 9/11 on AAPU (-1.19%, 9/10) / MVLL (-1.01%, 9/11) / MSTX (-2.42%, 9/11). Root-caused to the stale-`run_high` defect (E6) — confirmed the mechanism behind AAPU and MVLL specifically, and fixed via v3.62 (live staleness guard) + v3.63 (profit-gated ratchet, replaces v3.59 outright); both retrospectively verified to have prevented both losses. MSTX was a separate, discretionary governor manual exit, not a signal-quality failure. Governor's explicit clearance, given the root-cause fix and the tightened 5-min management cadence (v3.64) landing the same session: resume live trading 2026-09-14 under the new rules.) The streak is computed fresh from `archive/trades.csv` (plus `get_equity_orders` for manual round trips) at every check — never from a number written here, which goes stale the day after it's written. **A missing or unreadable trade log must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

## A2. Trigger hygiene

1. List triggers. **Delete every one with `ended_reason='run_once_fired'`** — a fired trigger reschedules itself ~24h later carrying its original, now-stale prompt.
2. Delete any trigger on a slot about to be armed. Exactly one per slot.
3. Never delete the trigger you are running from until tomorrow is armed.
4. **Never delete the 11:30am close checkpoint (primary arming, v3.60) or the 8:00pm checkpoint (backup verification, D1).** Together they replace what used to be a single point of failure.

A past-due trigger still enabled = a **missed** checkpoint, not a pending one. Do its work now, say it was missed, then delete it.

Do not start work that outlasts the current slot.

## A3. State check

Read from the broker, never assume: position · resting orders · settled cash · unsettled funds.

---

# PART B — HOLDING (management checkpoints)

## B1. Risk numbers — computed just-in-time, per candidate

**Always profile the exact instrument being traded — never a proxy, never an underlying standing in for its own wrapper.** Found missing 2026-09-04 (KLAG): profiled KLAC (the underlying) and applied its stop/stall percentages directly to KLAG's (the 2x leveraged wrapper's) own price — a real, live mistake, not a hypothetical one. A leveraged wrapper's own daily bars carry its own real volatility (leverage plus its own liquidity/tracking noise, which is not simply "2× the underlying" in a clean way) — KLAG's own profile came out roughly double KLAC's borrowed numbers. **If the traded symbol has its own tradeable history, profile that symbol, full stop** — this applies exactly as much to a leveraged single-stock wrapper as it did to MSTX (always profiled on MSTX's own bars, never MSTR's, the correct precedent this KLAG entry deviated from without noticing).

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

**Ranges close the observation gap without changing decision frequency.** Checkpoints run every 5 minutes from 9:45 through 11:15 (v3.64 — tightened from the prior 10-minute cadence; the old 5-minutes-after-entry special-casing of the first slot is moot now that every slot is 5 minutes from the last) — a single uniform cadence, with the day still ending at 11:30 (v3.60); the old 15-minute afternoon stretch stays retired along with the slots it covered. Each one knows the true high and low reached since the last, so a spike-and-reverse inside one interval is visible to every rule, even though action still waits for a scheduled checkpoint. Everywhere below, `run_high`, `session_high`/`session_low`, and checkpoint-to-checkpoint comparisons read from this range, never a point.

## B2. Stops — UP ONLY, NEVER DOWN

- **Never widen.** If the tape needs more room the trade is wrong — be out.
- Only permitted downward change: correcting a factual placement error, stated as such.
- Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print.**
- Minimum re-placement move: `min_stop_move_pct`. A structural level (swing low) may substitute **only if nearer**.
- Stops are **regular-hours only** and do not protect a gap.

### The trail — continuous chandelier off `run_high`, stock-scaled (v3.44)

**`run_high` tracks the high since *this position's entry* — a different window than C10's day-anchored `session_high`, even though both reuse the same B1b range-tracking technique.** Initialized to the fill price at entry, then `run_high = max(run_high, bar_high)` at every checkpoint (B1b) — the true highest price reached since the fill, not a lucky-or-unlucky point sample. Advances on any fresh interval high, unconditionally. **Never substitute `session_high` here** — a candidate can legitimately enter below its own day's high (C10 leg 2 allows a confirmed bounce off a pullback), in which case `session_high` at entry sits above the fill and would produce a stop tighter than the hold has actually earned.

**At every management checkpoint (9:45 through 11:15, one uniform 5-min cadence throughout, v3.64), the stop ratchets off the running high itself, discounted by twice the candidate's own noise band — but only while the position is currently in profit (v3.63, below) — never off the trailing average, never a fixed stage:**

```
run_high = max(run_high, bar_high)                         -- B1b, updated every checkpoint
candidate_stop = run_high × (1 − 2 × stall_threshold_pct)
live_price = fresh live quote, pulled now, not the B1b range read          -- v3.62
if live_price <= candidate_stop: new_stop = current_stop                   -- v3.62 staleness guard, skip this ratchet
else: new_stop = max(current_stop, candidate_stop)      -- up only, never down (B2's own rule, unchanged)
```

**Live staleness guard on every ratchet (v3.62).** Immediately before finalizing `candidate_stop`, pull one fresh live quote for the current price — not the B1b range read, which can already be several minutes old by the time a 10-minute checkpoint runs. If that live price is already at or below the computed `candidate_stop`, the ratchet is skipped this checkpoint (`new_stop = current_stop`, unchanged) rather than placing — or even reporting — a stop that's already effectively breached the moment it would rest. Not scoped to any particular checkpoint number; applies for the life of the hold. Direct governor instruction, 2026-09-14, targeting the mechanism behind E6's repeated stale-`run_high` breaches (AAPU 9/10, MVLL 9/11, and the AFRM/GUSH/NUGT/USAR/IONX/METU line before them) at its root: a discount-rate softening (v3.63, below) reduces how far the stop tightens, but doesn't by itself stop a stale peak from producing an already-broken stop — this closes that gap directly.

`stall_threshold_pct` is the candidate's own fresh JIT profile number (B1) — a calm name gets a wide-enough discount to survive its own normal noise; a choppy name gets pulled in tighter, proportionally. **Anchoring to `run_high` instead of the trailing average is the point:** the average sits close to the entry price right after a fill, so a completely normal early pullback can trip an average-based stop before a real trend has even formed. A high-water mark doesn't move on a pullback — only a fresh high advances it — so the trail gives a genuine trend room to breathe while still tightening every single checkpoint, never waiting on a breakeven gate. No separate spike-detection trigger exists anymore (retired v3.44) — this one rule already reacts to a fast move at the very next checkpoint.

**Why 2× the noise band:** backtested 1×–5× against all trades on record; 2× was the point that improved on the real historical results without giving reversals extra room to run first — full comparison in Current State (v3.44) and the git history, not restated here.

**Ratchet gated on being in profit, not on checkpoint count (v3.63 — retires v3.59's two-checkpoint entry grace outright, not an addition on top of it).** Direct governor instruction, 2026-09-14, given as part of a full reassessment after the loss streak that tripped the circuit breaker on 9/11 — two of the three losses (AAPU 9/10, MVLL 9/11) shared the identical stale-`run_high` mechanism (E6), and v3.59's softer early-checkpoint discount rates hadn't stopped it from recurring. **At every management checkpoint, for the entire life of the hold — not just the first two — the stop only ratchets if the live price is currently above the entry fill price:**

```
if live_price > entry_fill_price:
    candidate_stop = run_high × (1 − 2 × stall_threshold_pct)   -- full rate, always, no half-rate stage
    new_stop = max(current_stop, candidate_stop)                -- subject to v3.62's staleness guard above
else:
    new_stop = current_stop                                     -- unconditionally unchanged
```

If live price is at or below the entry fill, `new_stop = current_stop` no matter how high `run_high` has run — ratcheting up while a position is underwater locks in a stop the price has already fallen through, which is exactly the shape of every stale-`run_high` breach on record (E6). The instant live price is back above the entry fill, the full-rate formula applies immediately — there is no separate half-rate stage and no checkpoint-number tracking at all anymore. B3's other exit conditions (reversal, headline, risk/reward flip) are untouched — this only governs the ratchet mechanic. Applies to every fresh entry — primary, off-cycle, or a C12 re-entry — using that entry's own fill price as the reference, never a checkpoint count or clock time.

*Retrospective check against the two real breaches that prompted this change* (the same discipline as every prior B2 rewrite — check against real data before adopting): **AAPU (9/10)** — entry fill $41.45, checkpoint 2 (10:00) live price $41.01, *below* entry. Under the new rule, `new_stop` stays at the original $40.41 — no ratchet, no breach, the false stop-out never happens. **MVLL (9/11)** — entry fill $29.8107, checkpoint 2 (9:50) live price $29.61, also *below* entry. Same result: stop stays at $27.82, no breach. Both of the two real stale-`run_high` losses this rule was written in response to would have been directly prevented, not just softened. Whether either position would have later gone on to win or lose on its original wider stop is a separate, unknowable question — the rule's job is to stop the mechanism from forcing an exit on a stop that was never really earned, not to guarantee an outcome.

**At the 11:30 checkpoint specifically** — the last of the day (v3.60 — moved from 11:00; v3.57 had moved it up from 12:00 before that) — if a position is still open, **close it with a direct market sell, immediately (v3.58 — direct governor instruction, "From now on just market sell at 11").** This replaces the old stop-pin mechanism (`new_stop = max(new_stop, bar_close)`), which was found structurally broken the same day it was introduced: pinning a stop_market at/near the live price gets rejected or silently cancelled by the broker rather than resting (E6, first hit UUUU 8/25, recurred and identified as structural on MUU 9/9) — the close was depending on a mechanism that doesn't actually work at the moment it matters most. No more ratchet, no more resting order, no more verify-then-fallback dance: place the market sell, verify the fill from the order response (same discipline as any entry, C8), done. **Every checkpoint from 9:45 through 11:15 is a plain management checkpoint, ratcheting exactly the same way, 5 minutes apart (v3.60's extra 30 minutes, v3.64's tightened cadence)** — the extra room past the old 11:00 cutoff gives a genuine trend more room to finish (checked against METU's 9/9 bars, which were still running well past 11:00 the day this was decided) without giving up any stop protection to get it, unlike an earlier version of this idea that would have suspended ratcheting for the extra window — that version was rejected on the same data (see D4/E6). This is what ends the trading day; there is no separate 4:00pm deadline (see B4).

**No fixed profit-taking target — the trail is the only thing that locks in gains.** See B4: removed as a separate rule since v3.40, unchanged by this rewrite.

**`stop_pct` (entry) and `stall_threshold_pct` (every checkpoint after) are the only load-bearing numbers now.** `breakeven_trigger` and `trail_pct` were fully retired (not just unused) — `tools/profile.py` no longer computes them, and C8 no longer asks for them at entry. `target_pct` remains informational, feeding C7's `mfe_to_target` ranking check only.

**Worked example — MSTX, actual fill and bars, Thu 2026-08-27, `stall_threshold_pct` 0.893%, discount 1.786% (2×):**

| Checkpoint | Window | `run_high` | `candidate_stop` (`run_high × 0.98214`) | Stop becomes |
|---|---|---|---|---|
| 1 — entry, 9:43:52 ET | — | — | — | $14.1699 × (1 − 0.0597) = **$13.32** |
| 10:00 | since entry (9:43:52–10:00) | $15.0500 | $15.0500 × 0.98214 = $14.7812 | max($13.32, $14.7812) = **$14.78** |
| 10:15 | 10:00–10:15 | $15.4701 | $15.4701 × 0.98214 = $15.1938 | max($14.78, $15.1938) = **$15.19** |

Price fell to $14.896 shortly after the 10:15 checkpoint, below the $15.19 stop — **exit fires there, +7.23% locked**, well ahead of both the actual same-day trade's velocity-driven exit (+5.37%) and the prior average-based ratchet design's simulated result (+5.79%) — the running-high anchor stayed with the breakout instead of averaging it down. Same execution-risk caveat as E6: the stop can be raised to a level already at or below the live price at the moment it's placed (a fast-moving checkpoint window can do this to either mechanism) — verify the placement landed, same discipline as always.

**Entry+5 catch-up check (v3.55).** What changes is *when* the first post-entry read happens, not the ratchet rule above — this read is governed by the same profit-gated logic as any other checkpoint (v3.63), no special first-checkpoint case anymore. See C8: immediately after any fresh fill, if the regular grid's next scheduled checkpoint is more than 5 minutes away, one ad hoc read runs at `fill_time + 5min` instead of waiting for it. Directly closes the AFRM/GUSH/NUGT gap (E6) — every instance of that pattern was a fast pop-then-reverse landing entirely inside the interval between a fill and the first checkpoint able to catch it. **Effectively dormant since v3.64's 5-min cadence**: with every checkpoint at most 5 minutes from the last, no entry can ever be *more* than 5 minutes from the next scheduled one, so the "more than 5 minutes away" trigger condition can no longer fire. Left in place rather than deleted — harmless as written, and it becomes live again automatically if the cadence is ever widened back out.

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

**Every position closes the same trading day it was opened. No overnight hold, ever.** Enforced structurally, not by a deadline check: the 11:30 checkpoint (B2, v3.60) closes anything still open with a direct market sell (v3.58). State the intended exit at entry.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(The trading window (9:00–11:30, v3.60) is short enough that this may only fire once or twice in a given hold. Don't stop checking just because an earlier trade already closed today — a later opportunity is still tradeable within the window.)*

## B6. Shortlist range snapshot — feeds C10/C11, maintained incrementally, whether or not it's the held position

**Starts at 9:30, not the first management checkpoint.** Every checkpoint that produces a B1b-style range read for a candidate — 9:30's observation, 9:40's entry gate stack, and every management checkpoint from 9:45 through 11:15 (uniform 5-min cadence, v3.64) — pulls minute-bar historicals covering only the gap since that candidate's *previous* range read (B1b's own small window — never the whole day) **for every name still on today's shortlist** (the candidates that cleared C3 at 9:40, not the full 25-name watchlist), even while holding something else. One extra minute-bar call per name, the same call already run for the held position, not a new kind of lookup. This is what gives C11's "back to 9:30, whichever is shorter" window real coverage from the day's first read onward, instead of an artificially short one at the first management checkpoint.

**Update the running values, never re-derive them from scratch:**
- `session_high = max(session_high, bar_high)`. If this raises `session_high`, `session_low` clears — a fresh high ends the pullback episode (C10's own rule).
- Else `session_low = min(session_low, bar_low)` — only meaningful while price sits below `session_high`.
- Append one entry to a short rolling log: `(checkpoint_time, bar_close, path_length)`, where `path_length = Σ|close(n) − close(n−1)|` computed *only within this checkpoint's own small pull* — cheap, since the pull is already small. Keep log entries back to ~70 minutes; drop anything older.

**v3.47: this replaces re-pulling and re-summing the full day's minute bars at every checkpoint.** C10's `session_high`/`session_low` and C11's ER (below) now read off these maintained numbers plus a handful of rolling-log entries — never a fresh 40–90-minute pull re-scanned by hand every 15 minutes. A candidate re-considered after a real gap in its own reads (nothing logged since 9:40, say) simply has no running values to update yet — same default-pass-and-flag rule as always, not a new exception.

---

# PART C — ENTRY (9:00 · 9:30 · 9:40 primarily; any 9:45–11:15 checkpoint while flat)

> **No position may be opened outside 9:40–11:15 (v3.60 extended the window to 11:20 when the close moved to 11:30; v3.64 tightens the management cadence to 5 minutes, moving the last checkpoint — and so the last entry opportunity — to 11:15).** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:40, subject to C1's late-entry clause. **A position that closes mid-day gets an accelerated re-check instead of waiting for the next grid slot — see C12.**

## C1. Gate 1 — the commodity must hold, 9:30 → 9:40

**v3.53 — scope narrowed to commodity trades only.** Since sectors are no longer a tradeable category (D2/C4), this gate now applies exclusively to the commodity vehicles named in E3 (energy, gold, silver, copper, uranium, broader materials) — never to an individual stock or its leveraged wrapper, which are judged purely on their own move (C3/C10).

**9:30 is scoped to whatever commodity groups are on today's watchlist — no new market scan.** Record the day change of each commodity's plain proxy (feeds the Gate 1 test below) and note whether the confirming complex (miners, E&P, etc.) is still holding. That's an observational check, not a formal re-run of C3/C6 — the formal re-confirmation happens live at 9:40 (v3.56 — the second observation now coincides with the entry checkpoint, same as pre-v3.54).

Applies to a **commodity-leveraged trade** only. Record the commodity proxy's day change at **9:30** and again at **9:40**. All three must hold:

1. positive at 9:30, **and**
2. positive at 9:40, **and**
3. the 9:40 reading **not below** the 9:30 reading.

Any failure at 9:40 → no entry **at 9:40** in that commodity's leveraged vehicle.

**Late entry, any checkpoint after 9:40:** the door isn't permanently closed by a 9:40 failure. At any later checkpoint, entry is still allowed if the commodity proxy's live reading at that checkpoint is **strictly higher than the 9:30 baseline** — not merely "not below" (that looser bar is 9:40's own test, leg 3 above; a later checkpoint must clear the higher bar of actually exceeding 9:30, not just matching or nearly matching it). Recovered commodity strength after 9:40 is tradeable, but only past a real, higher threshold — never on a bare return to the 9:30 level.

**Two fixed observations (9:30, 9:40) decide the 9:40 pass/fail — never add intermediate readings there.** The late-entry test above is the one exception, evaluated fresh at whichever checkpoint is asking, using that checkpoint's own live reading against the fixed 9:30 baseline.

**Inverse leg — the same test, mirrored (v3.61).** A commodity trending down all morning is exactly as tradeable as one trending up, via the group's own inverse vehicle (E3) — bought long, never short-sold (E2 forbids short selling outright; an inverse ETF is how a bearish view gets expressed here, same mechanic as any other position). Direct governor instruction, prompted by a live question on a day where every commodity proxy read negative and the system had no path to act on it. Record the same day-change numbers already being tracked — no new data collection, just a second test applied to them. All three must hold:

1. negative at 9:30, **and**
2. negative at 9:40, **and**
3. the 9:40 reading **not above** the 9:30 reading (the decline hasn't eased).

Any failure at 9:40 → no inverse entry at 9:40 in that commodity's inverse vehicle — exactly mirrors the long side's own leg 3 failure. **Late entry, mirrored**: at any later checkpoint, an inverse entry is allowed if the live reading is **strictly lower than the 9:30 baseline** — a fresh, deeper decline past the original baseline, not just matching it. A commodity can clear the long test, the inverse test, or neither in a given window — it cannot clear both at once (they're mutually exclusive by construction), and clearing neither (chopping around flat) is a correct no-trade outcome for that commodity, same as always.

**Held and managed identically to any other position once entered** — B2's trail, B3's exits, B4's same-day close all apply unchanged, because the traded instrument (the inverse ETF itself) is still just a long position whose price needs to go up to win. Nothing about the ratchet, the stop math, or the close mechanic cares which direction the underlying commodity was moving; they only ever look at the price of what's actually held.

**Does not gate an individual-stock trade — nothing does, anymore.** A stock (or its leveraged wrapper) moving decisively on its own is judged purely on its own move (C3, C10, C11) and never needs a group to confirm it, because there is no group. **Every candidate, commodity or individual stock, is still subject to C10's direction/reversal test** — this gate's leg 3 is the commodity-proxy-only version of that same idea, for the one category that still has a proxy.

## C2. [Retired, v3.53]

**Was "Gate 2 — top 3 sector leaders."** Existed to rank several individual companies sharing one leveraged wrapper (crypto miners under BITX/BITU, etc.) before picking which one's move justified the trade. With sectors gone and crypto's group-leveraged products (BITX/BITU/ETHU/ETHT) retired outright (E3), nothing left in the system has more than one candidate per wrapper — each individual stock and its own leveraged ETF (if any) stands entirely on its own merit through C3/C5/C10/C11/C7, with no group to rank against. Number kept, not renumbered, so old trade notes and commits citing "C2" still resolve to this entry.

## C3. Major-move gate — what qualifies an individual stock

**Long-only, end to end.** Every single-stock name in the universe is a leveraged-*long* wrapper, so this gate cannot produce a short or inverse trade and does not try. Inverse views go through the commodity path (C1 + an inverse commodity ETF) — there is no individual-stock inverse path.

1. **Magnitude** — day change **≥ +0.75%** from prior close, up only. Measure the *underlying stock*, never the leveraged wrapper; the wrapper is just the multiple.

**Leg 1 alone is sufficient to qualify a candidate.**

2. **Moving average — optional, adds weight only, never a trigger and never a veto.** When price is actually testing the 50- or 200-day SMA, check its slope over 5–10 sessions. Rising MA + bounce up → extra confirmation for the long. Falling MA + rejection → **not counted at all**, neither as a reason to decline nor as an inverse trigger. Skip if price is not near either average.

Screen leg 1 at **9:00** with the scanner (`% Change`, or the gainers preset). **Re-confirm live at 9:40** — a 9:00 read is stale by the open.

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
| **1i** | Leveraged inverse commodity/miner-basket ETF | Commodity is moving down, C1's inverse leg / C6's inverse leg clear (v3.61), wrapper affordable |
| **2i** | Plain inverse commodity ETF | Commodity moving down, no affordable leveraged inverse vehicle |

**Three parallel tracks, never competing — individual stock (ranks 1/2), commodity long (ranks 1c/2c), or commodity inverse (ranks 1i/2i, v3.61) — decided purely by what's actually moving and which direction, never by picking a "sector" and working down into it.** **No plain-short fallback below 2i** — E2 forbids short selling outright, so if a commodity group has no listed (or no live-verified) inverse vehicle, is illiquid, or is unaffordable, there is simply no trade on that side, full stop, the same dead end as a stock with no wrapper and no affordable plain shares. Verify a group's inverse vehicle actually exists and is liquid with a live `search` before relying on E3's table alone — same standing discipline as individual-stock wrappers (E3), and E3 itself flags which groups currently have no listed inverse product. A single company moving on its own always goes through the individual-stock track, even if it happens to sit in a space (semis, biotech, financials, whatever) that used to have its own sector-leveraged ETF — those broad-sector vehicles are retired outright (E3), not a fallback.

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

**Leg 2, mirrored for an inverse trade (v3.61): real breakdown, not just a red day — below the prior session's range, under its low.** The long side's leg 2 exists to keep from buying a name that's actually broken structurally; the inverse mirror exists to keep from shorting (via the inverse ETF) a name that's merely pulling back inside an otherwise-intact uptrend — that's a bounce setup for longs, not a breakdown worth being on the other side of. Leg 1 (complex confirmation) applies to an inverse trade unchanged — the same complex moving down together is exactly as real a signal as moving up together.

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
- **Arm the entry+5 catch-up check (v3.55).** Once the stop is confirmed resting, check how far away the next regularly-scheduled grid checkpoint is. **If more than 5 minutes**, arm one ad hoc trigger for `fill_time + 5min` — a B1b/B2 ratchet-only read on this position, nothing more (not a full gate-stack re-run). This is separate from C12's own `fill_time + 10min` trigger, which decides whether to open a *different* position after an *exit* — this one manages the position just opened, regardless of which path opened it (primary 9:40 slot, an off-cycle entry, or a C12 re-entry). If the next grid checkpoint is already ≤5 minutes out (true for every entry now, v3.64 — the 5-min cadence means this is always the case, so this ad hoc trigger is never actually armed anymore), skip it — nothing to add. **Real-world note (v3.56, USAR 9/4):** this check is scoped to the gap *between checkpoints*, not the gap between the fill and the position's own peak — a reversal that happens inside the first minute or two after the fill can still outrun even a 5-minute catch-up. It closes the AFRM/GUSH/NUGT-style multi-checkpoint gap; it doesn't guarantee catching every fast spike-and-reverse.
- Report slippage against the intended price.
- State at entry: fill · **quantity and total cost** · stop price and % · target % · `mfe_per_stop` for the top two · intended exit · the falsifiable pre-commit for the next checkpoint.

## C9. Timing and selection

- **Entries are valid at any checkpoint from 9:40 through 11:15** (v3.60 extended the entry window to 11:20 along with the close; v3.64's tightened 5-min cadence moves the last checkpoint, and so the last entry opportunity, to 11:15) — no preferred-window distinction inside that range; the whole window is short enough (v3.43) that lateness within it isn't itself a signal. **11:30 itself is exit-only** — the close checkpoint doesn't take new entries, same as it didn't when it was the double-duty slot at 11:00 (v3.57).
- **After 11:15, none** — the window is closed for new positions regardless of what's setting up (B2/B4).
- Never force a trade because the window is closing.
- Verify `all_day_tradability` before entering.
- **Price the spread:** read the actual bid/ask, **double it** for the round trip, subtract from the expected move — take it only if it still clears the target with room.
- Check the price before building a thesis. A candidate you cannot buy is not a candidate.

## C10. Momentum direction — decline a fading price, allow a confirmed reversal

**Applies to every candidate, every entry-eligible checkpoint** — commodity proxies, individual stocks, plain or leveraged, in addition to (never instead of) C1–C9. Built to catch a candidate that's fading right now without permanently locking out a genuine second-wave rally later in the same session.

**Track, per candidate, from the day's own range-based checkpoint reads (B1b, via B6's shortlist snapshot)** — not point quotes (9:30 is the first formal read; the 9:00 scan is informal/stale per C3 and does not count here):

- `session_high` — the best `bar_high` reached so far today, across all checkpoints. Advances any time a fresh interval high prints, whether or not that high survived to the interval's close.
- `session_low` — the lowest `bar_low` reached *since* `session_high` was last set. Only exists while price is currently below `session_high`; clears the instant a new `session_high` prints — a fresh high ends the pullback episode outright.

**The checkpoint chain is one continuous chronological sequence, not two separate tracks.** A C12 mini-cycle check (its T+0 read and its T+10 gate stack) is a formal checkpoint in this same chain the instant it runs, exactly like a scheduled grid slot — it feeds `session_high`/`session_low` and B6's range log the same way a 10:00 or 10:50 slot does. Nothing about being ad hoc makes it second-class for this purpose.

**All three must hold, checked fresh at every entry-eligible checkpoint (never cached):**

1. **Not currently falling, and never below the actual 9:30 open (v3.66 — a hard floor, not a moving target).** This checkpoint's `bar_close` **strictly above** a fixed baseline price (v3.50 — was `≥`; a flat read, exactly at the baseline, is no longer a pass), for this candidate specifically — **the baseline is 9:30's price, and it moves only once: it resets to the exit's fill-timestamp price the moment any position closes (C12), for every candidate being reconsidered in that re-entry cycle, not just the one that was held — but only ever upward.** `effective_baseline = max(true 9:30 open, C12's fill-timestamp reset price)`. A candidate that's simply been declining since 9:30, with no rally of its own to justify a higher reset, must still clear its real 9:30 open — a reset caused by some *other* position's unrelated exit can tighten this leg, never loosen it. **Found live 2026-09-14: RIG entered via a C12 mini-cycle at a fill-timestamp baseline ($5.570) that was itself below RIG's own 9:30 open ($5.700) — RIG had been falling all morning and never once cleared its actual open, but the reset (triggered by RBLX's unrelated exit) made a small bounce off RIG's own low look like "not falling." A real, live entry, not a hypothetical — see Current State.** **Re-verified against the live quote immediately before order placement (v3.50, C8), not just this checkpoint's aggregated `bar_close`** — a gate check computed several minutes before the order actually lands can already be stale by the time of the fill (2026-09-01, XOM: leg 1 passed on a checkpoint-window `bar_close` $0.05 above baseline, but live price had fallen back under the baseline by the time the order filled a few minutes later, unnoticed until after the fact). If the live quote pulled for `review_equity_order` is at or below the baseline, the candidate is no longer eligible this checkpoint — decline rather than force it (C9), even if the checkpoint's own `bar_close` passed. No other event advances it — a checkpoint that merely re-reads a candidate without an entry/exit leaves the baseline exactly where it was, even across several checkpoints (v3.46: previously "immediately prior formal checkpoint," which let a candidate's first-ever entry check drift onto whichever checkpoint ran last instead of staying anchored to 9:30 — see Current State for why this changed). Applies identically to a candidate added to the watchlist after 9:30: pull its actual 9:30 price fresh via minute-bar historicals and compare against that, never treat "whenever we started watching it" as the baseline. (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.) Uses `bar_close`, not `bar_high`, here — this leg asks where the candidate actually settled, not the fastest point it touched. C12 steps 2–4 own the exact mechanics of the post-exit reset — read there for the full rule and worked example.
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** `bar_high` must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − bar_close) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

**Inverse leg — the same three tests, mirrored (v3.65).** Exactly like C1's own inverse leg (v3.61), this checks the commodity's **plain proxy** — never the inverse vehicle's own price — to decide whether the inverse vehicle is a valid entry; `session_high`/`session_low` here are the same proxy-tracked fields above (B6), read with the comparison flipped, not a second tracked pair. Closes the gap found live 2026-09-10 and left open since (E6): v3.61 built C1/C6's inverse legs but never gave C10 one, so an inverse candidate — falling by construction — could clear C1/C6 and still be silently blocked at C10's long-only leg 1. All three, checked fresh at every entry-eligible checkpoint:

1. **Not currently rising, and never above the actual 9:30 open (v3.66's floor, mirrored into a ceiling here).** This checkpoint's proxy `bar_close` **strictly below** the fixed baseline (the same 9:30/exit-reset baseline leg 1 above uses, tracked on the proxy). `effective_baseline = min(true 9:30 open, C12's fill-timestamp reset price)` — a reset can tighten this leg (push the ceiling lower), never loosen it by raising the ceiling above the real open. Re-verify against a live quote immediately before order placement, same as leg 1 — decline this checkpoint if the live proxy quote is at or above the baseline even though the aggregated `bar_close` passed.
2. **If above `session_low`, the pullback off `session_high` must be real, not noise.** `bar_low` must clear `session_high × (1 − stall_threshold_pct)`, using the proxy's own fresh JIT profile `stall_threshold_pct`. Automatically satisfied when price is at or below `session_low` (no relief bounce active, nothing to confirm).
3. **Giveback ceiling, mirrored.** Decline regardless of a qualifying pullback if `(bar_close − session_low) / (prior_close − session_low) > 65%` — more than roughly two-thirds of the day's decline already recovered reads as a broken decline, not a fresh leg down.

Fails leg 1 → blocked outright. Fails leg 2 or 3 while leg 1 passes → the pullback off the low isn't confirmed yet or the decline's too far gone; wait for the next checkpoint, same discipline as the long side. A commodity can clear the long-side legs, the inverse legs, or neither — never both at once, mirroring C1's own mutual-exclusivity note.

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

## C11. Chop filter — Efficiency Ratio, time-scaled

**Applies to every candidate at every entry-eligible checkpoint, in addition to C1–C10.** Catches a candidate that's technically up on the day and technically not falling (passes C10) but is genuinely just chopping sideways rather than trending — leveraged ETFs decay in exactly that shape (C5).

**Efficiency Ratio (ER), read from B6's maintained rolling log (v3.47) — never a fresh full-window pull re-summed by hand.** Take every log entry whose `checkpoint_time` falls inside the trailing 60 minutes (or back to 9:30, whichever is shorter): `ER = |current bar_close − oldest-in-window entry's bar_close| ÷ Σ(those entries' path_length)` — net progress over total path length. Near 1 = clean directional move; near 0 = pure back-and-forth with little net progress. Typically 4–5 log entries, not 40–90 individual minute bars. Fewer than ~20 minutes of logged window available → too little to be meaningful, gate passes by default — never block on a gap, never pretend the check ran.

**Minimum ER required to enter, scaled to how forgiving the moment should be** (early moves are naturally noisier as they establish; entries later in the window are into an already-maturing move and should be held to a higher bar). **Ranges are continuous — every clock time from 9:40 to 11:15 falls in exactly one row, no gaps.** This matters beyond the regular grid: a C12 mini-cycle check can land at any minute (fill-time-anchored, not just on the quarter hour), and needs an unambiguous minimum wherever it lands:

| Checkpoint time | Minimum ER |
|---|---|
| 9:40 – 10:29 | 0.15 |
| 10:30 – 10:59 | 0.25 |
| 11:00 – 11:15 | 0.30 |

(v3.60 — restored to three rows: the close moving from 11:00 back out to 11:30 brings back a genuine "late, mature move" bracket, so the 0.30 bar retired in v3.57 comes back too, keyed to the new window. v3.64 — the top row's endpoint moved from 11:20 to 11:15 to match the tightened 5-min management cadence's own last checkpoint; the three-bracket shape and thresholds themselves are unchanged.)

Below the window's minimum → declined as too choppy, regardless of C1–C10 all passing. This is a real, separate failure mode from C10: C10 asks "is it currently falling," C11 asks "is the recent path actually going anywhere, net."

**C11 now depends on B6's rolling log (v3.47)** — a reversal from before, when it self-supplied a fresh full-window pull independent of B6. A candidate with a real gap in its own B6 history (nothing logged since 9:40, say) simply has no window to compute ER from; same default-pass-and-flag rule above, not a special case.

## C12. Re-entry cycle — an exit restarts the entry clock, not the whole day

**Applies whenever a position closes before 11:30, regardless of why** — stop, reversal, any other B3 exit. (The 11:30 close itself is a direct market sell, v3.58/v3.60, not a stop trigger — nothing re-enters after it, since 11:15 is the end of the entry window, C9, v3.64.) The moment of exit becomes an ad hoc **"9:30-equivalent,"** rather than waiting for the next regular grid slot (the uniform 5-min cadence, v3.64).

0. **A profitable exit checks its own instrument first — a stop is a pause to reassess, not a verdict (v3.67).** If the exit's `pnl_pct_position` was positive, before anything else in this mini-cycle, run C10 (against v3.66's corrected floor) on the instrument that just closed, alone. Still clearing all three legs — still trending, not reversed — **re-enter it directly**, sized fresh off current settled cash (C8), without waiting to rank it against the rest of the shortlist; step 1's C7 re-rank does not gate this same-instrument check. Only fall through to the full gate stack in steps 1–4 below (every shortlist name, freshly ranked) if the same instrument no longer qualifies — a real reversal, not just a pullback that clipped the trail. First applied live 2026-09-14: RBLX stopped out at $48.02 (+0.46%), kept climbing to $49.34 over the next several checkpoints, and was re-entered directly on that basis rather than competing in a fresh ranking against RIG/DVN/whatever else was on the shortlist that moment.

**A losing exit's own instrument is excluded from re-entry for the rest of the trading day, full stop (v3.68 — direct governor instruction, 2026-09-15).** Not merely denied step 0's shortcut — removed outright from the shortlist candidate pool for every gate-stack run today, this mini-cycle's and any later one's, even if it would otherwise clear C10/C11/C7 cleanly. **Real, live 2026-09-15: RKLB stopped out at -2.01% (9:50 checkpoint).** The very next mini-cycle (9:55) let it compete in a normal C7 ranking against six alternatives anyway — nothing in C12 or C7 excluded it — and it won that ranking on its static 43-session `mfe_per_stop` (0.854), a number computed from daily bars that said nothing about the reversal-prone live action it had just shown, minutes earlier, at its own exit. Re-entered, reversed again the same way, closed a second time at -1.59%. Two losses on the same name in under twenty minutes, both preventable: the governor's original instruction ("the next check should be on the stock that just exited... if that's true it should be re-entered") was about a stock that just *won* — a loser doesn't get the benefit of the doubt a winner does, and letting it compete fairly in C7 was never the same thing as excluding it. Applies symmetrically to inverse exits.
1. **The exit's fill timestamp is the mini-cycle's actual "9:30-equivalent" moment — not whenever it's later discovered or read.** At the moment the exit is discovered (T+0), same turn, no new trigger needed: run the 9:30-style check (C1, if any commodity is on today's shortlist) against today's existing shortlist — the 25-name individual-stock list and any commodities already built at 9:00, not a fresh market-wide scan. Record any commodity's current day change and note which shortlist names are still holding their move. C7 re-ranks fresh here too — the capital base just changed (the position closed), which by C7's own rule voids the earlier ranking. **(Skipped entirely if step 0 already re-entered the same instrument — nothing left to rank this cycle.)**
2. **T+10 is measured from the exit's actual fill timestamp (from the order response), never from when it happened to be noticed.** Detection lags the real fill whenever the exit fires between scheduled checkpoints — get the real fill time first, then compute `elapsed = now − fill_time`:
   - **`elapsed ≥ 10 minutes`** — the window has already passed. Run the full 9:40-style entry gate stack, C1–C11, immediately, same turn as T+0. No trigger to arm, no further wait.
   - **`elapsed < 10 minutes`** — arm one ad hoc trigger for `10 − elapsed` minutes out (the nearest possible time to exactly `fill_time + 10min`, not a flat 10 minutes from T+0) to run the gate stack then.
   Enter if a candidate clears every gate, exactly as any other entry checkpoint would. This is in addition to, not a replacement for, the regular grid triggers already armed for the rest of the day.
3. **The comparison baseline for this gate stack's first run is each candidate's price *at the fill timestamp itself*, not at whenever the check happens to execute, and not the last regular grid slot** — **but never below that candidate's own actual 9:30 open (v3.66, C10 leg 1's hard floor).** Pull minute-bar historicals for that exact minute, for every shortlist name — the same one fixed moment for all of them, the same way 9:30 is one fixed moment for the whole watchlist, not something recomputed per candidate. This is what C10 leg 1 ("not currently falling") and C1's baseline reading compare against for this mini-cycle's first pass — whether that pass runs immediately (the `elapsed ≥ 10` branch) or at the armed T+10 trigger (the `elapsed < 10` branch). Being "free to trade" (timing, step 2) and "what you compare against" (this step) are two separate questions — 15 minutes already elapsed since the fill clears you to act *now*, but the price you're judging "still rising since I sold" against is still the price *at the fill*, not the price at whatever minute you happened to look, **and never a price below where that candidate actually opened the day — a candidate that's been falling since 9:30 doesn't get a fresh, lower floor just because a different position's exit happened to reset the clock.**
4. **After the gate stack runs, whether or not a new position was opened, resume the standard grid at its own next slot — not exit-relative.** Exit at 10:40, discovered and gated promptly → the next check is the regular 10:50 slot, then 11:00, unchanged. This mini-cycle's first read (step 3) is itself a formal checkpoint in the single chronological chain C10 tracks and B6 logs (v3.26) — the regular slot that follows it compares against *that* read's own `bar_close`, not back past it to the fill-timestamp baseline again. The fill-timestamp anchor is a one-time reference for this mini-cycle's opening comparison only, never a standing reference point afterward.

**Worked example, steps 2–4 together (this is the authority C10 leg 1 points back to; v3.64 — cadence is uniform 5-min throughout, running through 11:15, logic unchanged):** a position exits (fill) at 10:32. The 10:35 grid check discovers it; only 3 minutes have passed (`elapsed < 10`), so an ad hoc trigger arms for 10:42 (`fill_time + 10min`) — landing between two regular slots, which is now the normal case under the tighter cadence rather than the exception. At 10:42 the full gate stack runs — C10 leg 1 there compares 10:42's `bar_close` against the candidate's price *at 10:32* (step 3), not against 10:35's close. Declined → the next check is the regular 10:45 slot, and *that* leg 1 compares against the 10:42 read's own `bar_close` (step 4) — not back against 10:32 again, and not against 10:35. From there it's fully normal: 10:50 vs 10:45, 10:55 vs 10:50, and so on every 5 minutes — and since 11:30 is the close, the 11:15 read is the last comparison of the day.

Fires once per exit, not a new recurring cadence. If T+10 finds nothing that clears every gate, the book just stays flat until the next regular grid slot — same as any other declined entry.

**A chance to re-check, never a mandate to re-enter — everything else already in force still binds at full strength.** C5's "no read = no trade" and C9's "never force a trade" apply to the T+10 check exactly as hard as at 9:40; C9's 9:40–11:15 entry window (v3.60/v3.64) still governs — a mini-cycle triggered late enough that `fill_time + 10min` would land past 11:15 simply finds no entry available, same as any other post-11:15 moment; A1's one-position gate is untouched. This rule only shortens *when* the next attempt happens, never *whether* one is allowed.

---

# PART D — SCHEDULE & ADMIN

## D1. The grid (ET)

`9:00 · 9:30 · 9:40 · 9:45 · 9:50 · 9:55 · 10:00 · 10:05 · 10:10 · 10:15 · 10:20 · 10:25 · 10:30 · 10:35 · 10:40 · 10:45 · 10:50 · 10:55 · 11:00 · 11:05 · 11:10 · 11:15 · 11:30 · 8:00`

**No extended-hours slots.** As of v3.60 the trading day ends at 11:30 structurally — the 11:30 checkpoint closes whatever's open with a direct market sell (B2, v3.58), so there is nothing left to manage into the rest of the morning, the afternoon, or the evening. 8:00pm exists purely to verify tomorrow got armed (below), not to trade.

**Close moved from 11:00 to 11:30 (v3.60); management cadence between 9:45 and 11:15 tightened from 10 minutes to 5 (v3.64).** v3.60 was a direct governor instruction following the D4 review of Wednesday 9/9's trades; v3.64 a direct governor instruction given 9/14 as part of the circuit-breaker reassessment (alongside v3.62/v3.63). Entry stays at 9:40. **Every slot from 9:45 through 11:15 is a plain management checkpoint, 5 minutes apart, ratcheting the same way** — no special first-slot casing, no special last-slot casing, no market sell, no special handling; **11:30 takes over sole responsibility for the close**: direct market sell if still open (v3.58), report, arm tomorrow. The entire 15-minute-cadence afternoon stretch (formerly 11:15 through 11:45, retired v3.57) stays retired — this is not a revival of it, a materially tighter cadence than that stretch ever ran. ET → UTC: EDT = UTC−4; after Sun Nov 1 2026, EST = UTC−5. Skip market holidays — **verify the calendar, never assume.** On an early close, end the grid at whichever of 11:30 or the early-close time comes first. **Friday arms Monday**, not the weekend.

Runs indefinitely until the governor pauses it. Never stop on your own initiative.

### Arming — primary at 11:30, backup at 8:00

**Tomorrow's full checkpoint chain gets created at the 11:30 close, right after that day's exit/report work (D3) — not held until 8:00.** Skip the weekend the same way as always — Friday's 11:30 arms Monday.

**8:00pm is a verification pass, not a second independent arming.** Check that tomorrow's chain already exists (`list_triggers`, looking for tomorrow's date). If it does, this is a non-event — stay silent per D3, nothing to report. **If it's missing or incomplete — the 11:30 arming failed or was skipped somehow — create it now, and say so explicitly**, the same way A2 already treats any past-due, still-enabled trigger as a missed checkpoint that gets done late and flagged, not silently absorbed.

Never delete either checkpoint (A2's rule, not restated here).

### Early shutdown

Flat · no resting orders · **and** no entry possible (buying power short) → delete remaining intraday checkpoints. **Keep exactly two: 11:30 close (report + primary arming, v3.60) and 8:00 backup (verify tomorrow is armed; re-arm only if it isn't).** Being flat because an earlier trade already closed today is **not** by itself a reason to shut down — a later opportunity is still tradeable within the window unless one of the two conditions above is actually true.

## D2. 9:00am research — standard work

**v3.53 — sectors dropped. Individual-stock-first, market-wide; commodities are the one exception, tracked separately, never blended into the 25.**

1. **Headlines** — macro, geopolitical, overnight.
2. **Pre-market prices** across the universe and yesterday's watchlist.
3. **Earnings reactions** from last night's after-close reporters.
4. **Market-wide magnitude scan — individual stocks, no sector scoping.** Run the scanner's `% Change` gainers filter (C3's threshold, `≥0.75%`) across the whole market, with a liquidity floor (average volume — `FILTER_TYPE_AVERAGE_VOLUME`, same mechanism as any other scan) to keep the results real and tradeable rather than illiquid noise. No `Sector` filter this time — the point is to find whichever individual names are actually moving today, wherever they sit.
5. **Separately, check the fixed commodity list (E3) for a real move, either direction (v3.61)** — the one category still allowed a group vehicle. Energy, gold, silver, copper, uranium, and broader materials each get a quick day-change read on their plain proxy; a commodity makes today's list provisionally on that premarket read whether it's clearly positive (long track, C1/C4/C6) or clearly negative (inverse track, C1's inverse leg, C4's 1i/2i, C6's inverse leg 2) — real qualification either way still needs the formal 9:30→9:40 test to clear live, same discipline as any other candidate, never assumed from the headline alone.
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
- **Friday 11:30am always reports** (v3.60 — moved from 11:00; v3.57 had moved it up from 12:00pm before that), trades or not — balance, every trade, loss-streak count, what was declined and why, any rulebook change. The guaranteed heartbeat. (Moved here from 8:00pm under D1's arming restructure — 8:00 is now a silent-unless-broken backup check, even on Fridays; the real weekly data already lives at the close, not eight hours later.)

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

**Commodity groups — plain and leveraged vehicles together, C1/C6 apply. Inverse vehicles (v3.61) are the ones on each row prefixed with a direction below — bought long, never short-sold (E2), same as everything else:**

| Instrument(s) | Commodity | Inverse (v3.61) |
|---|---|---|
| XLE · GUSH · ERX · NRGU | Energy / E&P complex | ERY · DRIP · OILD |
| USO · UCO | Crude oil (direct) | SCO |
| UNG · BOIL | Natural gas | KOLD |
| GDX · NUGT · GDXU · JNUG | Gold miners | DUST · JDST |
| GLD · UGL | Gold (direct) | GLL |
| SLV · AGQ · SIL · SILJ | Silver | ZSL |
| COPX · CPER | Copper | **none listed — verify live** |
| URA · URNM | Uranium | **none listed — verify live** |
| XLB · UYM | Broader materials/mining ("or such," per the governor's own framing) | SMN |

**Copper and uranium have no inverse vehicle listed above** — checked at v3.61's adoption, nothing obviously real turned up on a first pass, but per the standing wrapper-search discipline (below), a live `search` is still required before concluding no inverse path exists for either — this table is a convenience index, not the boundary. If a real, liquid one is found, add it here rather than re-discovering it next time.

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
| USGG · USAX | USAR |
| KLAG | KLAC |
| IONX · IONL | IONQ |
| QBTX | QBTS |
| METU | META |
| MVLL · MRVU · MRVX | MRVL |

**This table is not exhaustive by construction — verify with `search` before ruling out a wrapper, don't just check this list.** Found missing 2026-09-04: USAR's entry (9/4 9:35) went into the plain stock because this table didn't have it, when USGG (Themes 2X Long USAR Daily ETF) and USAX (Tradr 2X Long USAR Daily ETF) both exist and are tradeable — a real C4 miss, not a hypothetical one. New single-stock leveraged products launch continuously; this table only grows when someone happens to add an entry. **Before declaring "no wrapper exists" at C4/E3, run a quick `search` for the underlying's name/ticker plus "leveraged" or "2X"/"3X" as a live check, not just a table lookup.**

**A single failed `search` call is not proof either — found 2026-09-08.** IONQ's 9:40 entry ran `search` ("IonQ 2x daily long leveraged single stock ETF") and got zero results, so it traded plain — but three real, live wrappers exist (IONX/Defiance, IONL/GraniteShares, both liquid and tradeable; IONC/Corgi exists too but is stale/illiquid, correctly excludable on Friday's AXTC precedent). The governor caught it from the live Robinhood app search within minutes. **When a candidate is posting a large, obviously wrapper-worthy move (double-digit day change, mega-cap-adjacent liquidity, a "hot" theme like quantum/AI), one empty `search` result is a weak signal, not confirmation** — a differently-phrased retry (drop qualifiers, try just the ticker + "ETF", or try "2x" and "leveraged" as separate calls) costs one extra tool call against a real risk of trading the wrong vehicle. Cheap to switch immediately if the position is fresh and near-flat (as it was here — cancel the stop, exit, re-enter the wrapper, no real cost); expensive if caught late (as USAR was on 9/4) — the earlier this is caught, the cheaper the fix, which argues for the extra verification pass *before* placing the plain-stock order, not after.

**Standing governor instruction, 2026-09-08 9:50 checkpoint: search harder for leveraged plays, every time, before any commodity or individual-stock entry.** At the 9:50 URA entry, `search` *did* find URAA (Direxion Daily Uranium Industry Bull 2X ETF) on a second, differently-phrased retry — not a miss like IONQ — but it was then declined on liquidity grounds (28K-165K daily volume vs URA's own millions). The governor's instruction is broader than any single incident: **exhaust search variants (ticker alone, ticker + "ETF", "2x"/"3x" + the theme name, the company/commodity's full name) before concluding a wrapper doesn't exist, and don't be quick to wave off a found wrapper on liquidity without a real look** (full daily volume history, live spread, whether the last-trade/bid gap is a momentary quirk or a persistent thin-market signal) — a fast pass isn't the same as a real check. Applies going forward to every C4 instrument-priority decision, not just when a name is already suspected to be wrapper-worthy. **Does not mean switch out of an already-held position on a later, better-verified find** — if a position is already open and performing, chasing a marginally-better vehicle open-ended is its own risk (execution cost, fresh entry risk on the new vehicle, as IONX itself just demonstrated); this rule governs the *search* discipline at entry, not a standing invitation to rotate vehicles mid-hold.

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
**Tuesday 2026-09-15, 9:00 research** (v3.67 live; three trades closed yesterday, breaker clean at 0/3):

- **A1 checks: loss streak 0 of 3** (unchanged — no trades closed since yesterday's clearance). **Position: flat, no resting orders** (`get_equity_positions` empty). Total value/cash/buying power **$471.96**, unchanged overnight, no pending deposits, no unsettled funds.
- **Headlines/macro: risk-off, Fed-day tension, oil-driven, semis licking wounds from Monday's AI-safety selloff.** 10-year Treasury yield hit ~5.0% intraday (highest since 2023), FOMC's two-day meeting begins today (decision Wednesday, ~92-95% odds of a 25bp hike per CME FedWatch). Oil still elevated on the Saudi-pipeline/Houthi Strait-of-Hormuz disruption (Brent ~$106-107.5, WTI ~$102-103). Gold/silver both down Monday (~1.5-2.6%). **Monday's real story**: Anthropic's Amodei (backed by OpenAI's Altman and Musk) publicly urged an AI-development slowdown over safety risk — triggered a sharp semis/AI-infra selloff (NVDA -3.4%, AMD -4.4%, MU -5.25%, MRVL -6-7%, INTC -6.2%, SNDK/ASML/SK hynix all hit hard too). **Tuesday premarket shows early stabilization/dip-buying in the same names** (MU +0.9%, NVDA +0.7% premarket per Benzinga) — today's scan below confirms this live.
- **Market-wide individual-stock scan (D2 step 4)**, run live on the saved scan `4ceac364-d887-4afc-b3e1-7cfe991001e1`. **41 names cleared.**
- **Today's watchlist, ranked by day-change magnitude — MU/AMD/MRVL/INTC/NBIS all land naturally in the top 25; no wrapper-carrying name outside the top 25 needs a priority bump (E3 checked):**
  1. ADBT +31.24% (micro-cap $47.2M — flagged suspect) · 2. PDSB +21.92% (micro-cap $22.3M — flagged suspect) · 3. TRUG +13.62% (micro-cap $1.2M, noncompliant — flagged suspect) · 4. TNON +12.59% (micro-cap $3.7M — flagged suspect) · 5. CELZ +8.74% (micro-cap $5.7M — flagged suspect, same illiquid name from yesterday) · 6. FNGR +4.07% (micro-cap $11.1M, noncompliant — flagged suspect) · 7. DAIC +3.07% (micro-cap $2.8M — flagged suspect) · 8. NOK +2.69% (Nokia, real) · 9. ADGM +2.02% (micro-cap $10.0M biotech — flagged suspect) · 10. AUR +2.01% (Aurora Innovation, real) · 11. RKLB +1.82% (Rocket Lab — real, fresh catalyst, see below) · 12. GOSS +1.78% (Gossamer Bio, $65.8M — thin, flagged suspect) · 13. INTC +1.67% · 14. MMA +1.58% (micro-cap $10.4M — flagged suspect) · 15. EOSE +1.57% (Eos Energy, real) · 16. AXTI +1.47% (AXT Inc, semiconductor materials) · 17. WFC +1.44% · 18. COMP +1.41% · 19. BE +1.30% (Bloom Energy) · 20. GRAB +1.30% · 21. AMD +1.27% · 22. MRVL +1.25% · 23. MU +1.23% · 24. FAMI +1.19% (micro-cap $4.8M — flagged suspect) · 25. NBIS +1.18% (Nebius Group, AI-infra cloud).
  **Real, coherent theme underneath: semis/AI-infra relief bounce, not a fresh breakout.** MU/AMD/MRVL/INTC/NBIS/AXTI all cratered Monday on Amodei's AI-slowdown-safety call and are bouncing modestly today. Checked live via `get_equity_news`: **INTC's own catalyst signal is weak/indirect** (Musk/Terafab semiconductor-manufacturing sentiment spillover, not INTC-specific news) — falls under C5's tech/semis exception (a clean catalyst often doesn't exist for this category; absence doesn't exclude the name, but expect extra C10/C11 scrutiny given this is a dip-buy, not a breakout). **RKLB has a genuine, fresh, dated, company-specific catalyst**: completed a $1.94B at-the-market equity offering (published 06:45 and 08:53 ET today) to fund its pending Iridium Communications acquisition — real news, not sentiment.
  **11 of 25 flagged as suspect** — thin/micro-cap names (ADBT, PDSB, TRUG, TNON, CELZ, FNGR, DAIC, ADGM, GOSS, MMA, FAMI, all under ~$70M market cap, several noncompliant per `financial_status_indicator`) — kept per D2 (real filtering happens at C5/C10/C11), expect heavy scrutiny/likely liquidity declines at entry, same pattern as yesterday's thin cluster.
- **Commodity check (D2 step 5, v3.61 — both directions): all six essentially flat/marginal pre-market (~9:05 ET) — no clear divergence yet, unlike yesterday's energy-vs-everything split.** XLE +0.15% ($64.63 vs $64.53), **SLV +1.41%** ($57.64 vs $56.84) — the only one with a real move, GLD +0.19% ($393.57 vs $392.84), COPX -0.21% ($85.44 vs $85.62), XLB +0.35% ($50.67 vs $50.49), URA +0.38% ($42.35 vs $42.19). Provisional only — real qualification needs the live 9:30→9:40 test; SLV worth watching into 9:30 if the move holds.
- **Deposited capital recomputed**: `total_value ($471.96) − all-time realized P&L ($21.15) − unrealized P&L ($0)` = **$450.81** — a $0.02 rounding drift from yesterday's $450.83 (cumulative per-trade % rounding, immaterial). **Floor: $225.41** (50% of deposited).
- Profiling (`tools/profile.py`) and affordability marking deferred to the 9:30/9:40 live checks per D2 step 7, per usual. Full 41-name scan result is live via `run_scan` on the same saved scan id — not re-pasted here.

**9:30 observation (A1 · C1 Gate-1 baseline)**: git verified in sync. A1 re-checked fresh: loss streak still **0 of 3**, flat, no resting orders, total value/cash/buying power **$471.96**, unchanged. **Four commodities positive at 9:30 — a real split, not yesterday's single-name read**: XLE +0.85% ($65.08 vs $64.53), SLV +1.12% ($57.48 vs $56.84), GLD +0.09% ($393.21 vs $392.84, barely), URA +0.50% ($42.40 vs $42.19) — all provisional long-track candidates. **COPX -0.27% ($85.39 vs $85.62) and XLB -0.12% ($50.43 vs $50.49) negative** — both provisional inverse-track candidates. Next: 9:40 entry checkpoint — re-confirm all six commodities' C1 legs live, run C3/C10/C11/C4 on the 25-name individual-stock watchlist, with extra scrutiny on the semis/AI-infra bounce names (dip-buy character, not fresh breakout) and the 11 flagged thin micro-caps.

**9:40 entry — RKLB entered.** **C1 9:40 recheck**: XLE +1.33% (up from +0.85%) and GLD +0.097% (barely up from +0.094%) both cleared all three long legs. **SLV +1.07% (down from +1.12%) and URA +0.28% (down from +0.50%) failed leg 3** — eased since 9:30, no entry this checkpoint (late-entry test available later if either re-exceeds its 9:30 reading). **COPX -0.81% and XLB -0.26%, both deepened further from 9:30** — cleared C1's inverse leg cleanly, but no affordable/liquid path pursued this checkpoint given a stronger individual-stock candidate (below); not chased further this cycle.
**Individual-stock side**: re-confirmed all 25 names live via fresh quotes. **DAIC, GOSS, COMP reversed to negative since 9:00 — declined outright** (fail C3 re-confirmation). **AUR (+0.70%) and MU (+0.60%) fell below the 0.75% magnitude floor — declined** (fail C3 leg 1 re-confirmation). Of the rest, **ADBT, PDSB, TNON, FNGR all now trading below their own 9:30 open — fail C10 leg 1, declined.** **CELZ, ADGM, MMA technically hold above their 9:30 opens but are trading on near-zero real volume** (mostly interpolated/gap-fill minute bars) — **declined on liquidity**, same discipline as yesterday's MDXH/CELZ. **GRAB flat/barely below its 9:30 open ($3.075 vs $3.08) — declined, C10 leg 1 not strictly cleared.**
**Real, liquid candidates clearing C3 + C10 leg 1**: TRUG (thin, noncompliant — no catalyst found, declined on quality), FAMI (thin $4.8M — no catalyst found, declined on quality), NOK, RKLB, INTC, EOSE (choppy, dipped below its own open mid-window — declined on trend quality), AXTI, WFC, BE, AMD, MRVL, NBIS. **C11 default-passes all of them** (first checkpoint of the day, no logged intraday history yet, same as every prior first-entry checkpoint this week).
**Catalyst check (C5) on the two strongest, real, liquid names — both had a genuine fresh same-day story, unlike the broader semis-bounce group**: **RKLB** completed a $1.94B ATM equity offering (06:45 ET) to fund its pending Iridium acquisition, plus 1.7% intraday move flagged in the same MT Newswires sector wrap. **NOK** has a fresh product/demand catalyst (Nokia + Telxius deploying 800G optical tech for AI/data-center connectivity, 07:16-09:10 ET) plus a same-day analyst Buy initiation (Rosenblatt, $15 PT). **Profiled both for C7** (`tools/profile.py`, 43 sessions of daily OHLC each): **RKLB mfe_per_stop 0.854** (stop 3.19%, target 4.78%, reachable at 1.76×) vs **NOK mfe_per_stop 0.406** (stop 3.14%, target 4.71%, flagged unreachable at 3.69× mfe_to_target). **RKLB ranked clearly higher on both ranking and target reachability.** INTC/AMD/MRVL/NBIS/AXTI/BE/WFC not individually profiled once RKLB's ranking was this decisive; their own catalyst signal remains the weak/indirect semis-bounce story noted at 9:00 (covered by C5's tech/semis exception, but second-tier to RKLB's genuine news either way).
**Vehicle check (C4)**: searched for a leveraged RKLB wrapper — none found, plain stock per C4 rule 3 (no affordable leveraged vehicle → take it plain). **Entry executed**: reviewed (bid $65.05 × ask $65.13, 9:42 AM ET, clean, no alerts), live ask still well above the $63.68 9:30-open baseline (C10 leg 1 live re-check, C8/v3.50). **Filled 7 sh @ $65.1299 avg** (13:42:30 UTC / 9:42:30 ET), cost **$455.91**. **Stop placed and confirmed resting**: stop_market sell 7 sh @ **$63.06** (3.18% below fill). Next regular slot (9:45) is <3min out — no entry+5 catch-up needed (C8/v3.64). Intended exit: stop $63.06 (-3.18%) or target ~$68.22 (+4.78%), ratcheting up only through 11:30 close.

**9:45 management — no ratchet, live price dipped below entry fill.** `run_high` $65.1299 → **$65.370** (13:42-13:44 window). Live $64.125 < entry fill $65.1299 — per v3.63, the profit gate blocks any ratchet unconditionally. Stop stays at $63.06, untouched. Unrealized: -$7.03 (-1.54%). No B3 exit — no level named at entry has broken, just a normal early pullback well inside the 3.18% stop distance. Pre-commit: exit at the $63.06 stop if hit, or on a live reversal below $63.68 (today's 9:30 open) at the next checkpoint if the pullback deepens further without stabilizing.

**9:50 management — pre-commit honored, RKLB closed.** `run_high` stayed at $65.370 (this window's bar_high $64.51 didn't exceed it). Live price $63.625 < entry fill — profit gate would have blocked any ratchet anyway, but the pullback deepened for a second straight checkpoint without stabilizing (65.13 → 64.125 → 63.625) and dropped below the $63.68 level named in the 9:45 pre-commit (today's 9:30 open / C10's entry-gate baseline). Per B3's own instruction ("then honour it"), exited rather than waiting for the mechanical stop 0.89% further away: **cancelled the resting $63.06 stop (confirmed cancelled, no fill raced it)**, sold **7 sh @ $63.8207** (marketable limit at $63.40, filled well above it on a brief bounce, 13:52:24 UTC / 9:52:24 ET). True MAE/MFE from minute bars over the ~10-minute hold: true high $65.370 (9:43, one minute after the fill, MFE +0.37%), true low $63.52 (9:50 bar, MAE +2.47%). **Net: -$9.16, -2.01%, r=-0.632** — a real loss under E1's -1.0% threshold. Logged to `archive/trades.csv`. **Loss streak now 1 of 3** — not a breaker trip, but the first real loss since the 9/14 clearance; two more consecutive sub-(-1.0%) closes would trip it. Flat, no resting orders, confirmed. Position size at entry (7sh, ~$456 of $471.96) means the next entry (if any this checkpoint cycle) sizes fresh off current settled cash (~$465.83), per C8. **C12 mini-cycle**: a losing exit skips v3.67's step 0 (profit-only shortcut) and goes straight to the full mini-cycle. Elapsed since fill is 0 minutes; the next regular grid checkpoint (9:55) is only ~3 minutes out, well before a literal T+10 (10:02:24) — letting it do double duty rather than arming a separate ad hoc trigger, same precedent as 9/14's RBLX/RIG mini-cycle. Baseline for C10 leg 1 at 9:55 resets to each shortlist candidate's price at this exit's own fill timestamp (13:52:24 UTC), floored per v3.66 at each candidate's true 9:30 open — never below it.

**9:55 — C12 T+10 gate stack + regular grid, RKLB re-entered.** Baseline for each shortlist candidate reset to its price at RKLB's own fill timestamp (13:52 UTC), floored at its true 9:30 open per v3.66. **8 real names cleared leg 1 against the reset baseline**: RKLB ($64.15 live vs $63.689 reset floor), NOK, INTC, EOSE, BE, AMD, MRVL, NBIS. **AXTI and WFC failed narrowly** — both sitting just below their own T+0 reset price. TRUG/FAMI remain thin/suspect, not re-considered. **Profiled the six not already profiled at 9:40** (`tools/profile.py`, 43 sessions each): INTC 0.827, BE 0.718, MRVL 0.680, NBIS 0.594 (target unreachable, 2.52×), AMD 0.584 (target unreachable, 2.57×), EOSE 0.478 (target unreachable, 3.14×). **RKLB still ranks highest at 0.854**, narrowly ahead of INTC's 0.827 — both real, liquid, with the same catalysts already established (RKLB's ATM/Iridium raise, INTC still on C5's tech/semis exception). **C11 checked properly this time** (real B6 history exists since 9:00 for the shortlist, and RKLB itself has a full round-trip logged): ER over the trailing window ≈ 0.20 (net progress $0.78 ÷ path length ~$3.90 across the 9:30→9:55 checkpoint closes) — above the 9:40-10:29 bracket's 0.15 minimum, a real if choppy net move, not pure back-and-forth. **Re-entered RKLB** rather than treating the just-closed loss as a reason to avoid it — the fresh gate stack, run structurally rather than on feel, ranked it highest again and it cleared every gate on its own current numbers; letting the ranking decide is the entire point of C7 existing. Re-verified live before placing (C8/v3.50): ask $64.15, still above the $63.689 reset floor. **Entry executed**: reviewed (bid $64.07 × ask $64.15, 9:58 AM ET, clean, no alerts), **filled 7 sh @ $64.15 avg** (13:58:36 UTC / 9:58:36 ET), cost **$449.05**. **Stop placed and confirmed resting**: stop_market sell 7 sh @ **$62.11** (3.18% below fill). Intended exit: stop $62.11 (-3.18%) or target ~$67.21 (+4.78%), ratcheting up only through 11:30 close. **This is a fresh position with its own fresh pre-commit — the 9:45 pre-commit that led to the prior exit is fully discharged and does not carry over.**

**10:00 management — no ratchet, small pullback.** `run_high` $64.15 → **$64.240** (13:58-13:59 window). Live $63.875 < entry fill $64.15 — profit gate blocks any ratchet. Stop stays at $62.11, untouched. Unrealized: -$1.93 (-0.43%). No B3 exit — a small, normal pullback well inside the 3.18% stop distance, no named level broken. Pre-commit this time: mechanical stop only ($62.11) or a genuine reversal below the day's own low so far — no intermediate named level, given the last round-trip's early exit turned out to front-run a bounce that would have been profitable held through.

**10:04 ET — governor instruction "Stop for today," RKLB closed, session ends.** Unlike the 9:45→9:50 round-trip, this decline never bounced — a clean, continuous slide from the $64.240 run_high through every bar of the hold, live price never once back above the entry fill, so the profit-gated ratchet never engaged; stop sat untouched at $62.11 the whole way. Rather than leave a real position open and unmanaged overnight against B4's own no-overnight-hold rule, closed it immediately on the governor's instruction: cancelled the resting $62.11 stop (confirmed cancelled, no fill raced it), sold **7 sh @ $63.1321** (marketable limit at $63.00, filled above it, 14:04:10 UTC / 10:04:10 ET). True MAE/MFE from minute bars over the ~6-minute hold: true high $64.240 (9:59, MFE +0.14%), true low $63.10 (10:04 bar, at the exit itself, MAE +1.64%). **Net: -$7.13, -1.59%, r=-0.499** — a second consecutive real loss under E1's -1.0% threshold. Logged to `archive/trades.csv`. **Loss streak now 2 of 3** — one more sub-(-1.0%) close would trip the circuit breaker; flagging this loudly rather than burying it. Position confirmed flat, no resting orders.

**Session note on today's two RKLB trades**: both losses, -$9.16 and -$7.13, -$16.29 net on the day, both on the same instrument. RKLB's historical `mfe_per_stop` (0.854, from 43 daily sessions, real and correctly computed) ranked it highest both times it was compared against real alternatives — the C7 ranking mechanism worked exactly as designed on its own numbers. What that static daily-bar ranking couldn't see: RKLB was reversal-prone and choppy in its actual live intraday action today, on both entries, in a way its 43-session daily profile didn't predict. Worth the governor's attention before RKLB is next taken as a top-ranked candidate on a similar setup — not a rule change proposed here, just a flag for review (E6/D4), since one day's live pattern isn't yet enough evidence to change C7 or C10 structurally.

**Trading halted for the day on governor instruction ("Stop for today"), 10:04 ET.** Today's remaining scheduled checkpoints (10:05 through 11:30, and the 8:00pm backup) were deleted rather than left to fire into a session that's intentionally stopped. **Today's final tally: two trades, both RKLB — RKLB#1 -$9.16 (-2.01%), RKLB#2 -$7.13 (-1.59%). Net today: -$16.29.** Loss streak: **2 of 3** — a genuine, real signal-quality concern, not a scratch or two.

**Governor explicitly asked whether to also skip tomorrow's grid or still arm it — chose to arm tomorrow, stop only today.** Since the 11:30/8:00pm triggers that would normally do the arming were deleted along with the rest of today's grid, armed Wednesday 2026-09-16's full 24-slot chain manually this same turn: 9:00 · 9:30 · 9:40 · 9:45-11:15 every 5min (19 slots) · 11:30 close+arming · 8:00pm backup — verified via `list_triggers`, all 24 present, no gaps or duplicates. Normal D1 arming resumes tomorrow at its own 11:30 checkpoint (arming Thursday), same as any other day.

**Governor correction, same session: RKLB's 9:55 re-entry was a real rule-application error, fixed as v3.68.** The 9:52 close-out narrative above states plainly that a losing exit "skips v3.67's step 0" — true, but incomplete: skipping the shortcut still let RKLB compete fairly in the full C7 ranking at 9:55, and it won that ranking on a static 43-session `mfe_per_stop` that had nothing to say about the reversal-prone live action it had just shown, minutes earlier, at its own exit. The governor's original v3.67 instruction was specifically about re-entering a stock after a *winning* exit ("the next check should be on the stock that just exited... if that's true it should be re-entered") — a losing exit was never meant to get that same benefit of the doubt, fast-tracked or fairly ranked. **Fixed via v3.68**: a losing exit's own instrument is now excluded outright from the shortlist for every gate-stack run for the rest of the day, not merely denied the step-0 shortcut. The second RKLB loss (9:58 entry, -1.59% exit) would not have happened under this corrected rule — RKLB would have been struck from the candidate pool at 9:55 and never reached the C7 ranking at all.

## E6. Known issues — backlog, not yet fixed

**Resolved 2026-09-14, v3.65.** C10 given the mirrored inverse leg exactly as scoped when this was first found (9/10) — checks the commodity's plain proxy, never the inverse vehicle's own price, mirroring C1/C6's existing pattern. Direct governor instruction, given live mid-session with SLV/GLD/COPX/URA all sitting on qualifying inverse setups. Reopen only if a gap in the mirror itself turns up.



**Local git working copy can silently desync from the actual remote branch — found and fixed 2026-09-09.** Local `trades.csv` was missing 7 rows already safely committed on `origin`; no data was actually lost, root cause not fully diagnosed (likely a container/checkout artifact from resuming after a date change). Fixed via checkout-from-origin plus a merge. **Standing practice: if `git push` is ever rejected non-fast-forward, or trades.csv/RULEBOOK.md ever look thinner than expected, verify against `origin` (`git log origin/...`, `git diff origin/...`) before trusting local state or force-pushing.** Full incident: `git show dd716ce:RULEBOOK.md` (E6).

**Stop-order placement can fail silently, two distinct failure modes — resolved for the close checkpoint, still open elsewhere.** *Mode 1:* comes back `cancelled` with zero fill, no error (first seen 8/24; escalated 8/25, SMCX ×3, forced a manual exit). *Mode 2:* outright `rejected` when the stop price is already at/above live market at placement time — the broker apparently won't convert an already-triggered stop into a market order (first seen 8/25 UUUU; recurred 9/9 MUU at the then-11:00 close, where B2's own close-checkpoint rule *requires* pinning the stop to live price, guaranteeing the trigger condition every day). **v3.58 closed mode 2 at the root for the close checkpoint specifically**, by direct governor instruction: the close is now a direct market sell, no stop-pin attempted at all. Modes 1/2 still apply to every other checkpoint's regular ratchet, where a resting stop remains the right mechanism. **Standing mitigation (governor-accepted 8/25, still current): after every stop placement, verify it landed via `get_equity_orders` before considering the position protected; retry immediately if not, re-checking live price first if the retry itself might already be stale.** Zero losses attributable to the glitch itself to date; an automatic retry-and-verify wrapper remains a nice-to-have, not urgent — revisit only on a real loss or a rising failure rate. Full incident detail: `git show dd716ce:RULEBOOK.md` (E6).

**Resolved 2026-09-14, v3.62 + v3.63 — the stale-`run_high` pattern.** Eight documented instances over three weeks (AFRM 8/28, GUSH 8/31, NUGT 9/2, USAR 9/4 real loss -2.13%, IONX 9/8 real loss -2.13%, METU 9/9, AAPU 9/10 real loss -1.28%, MVLL 9/11 real loss -1.01%) of the same mechanical defect: `run_high` stalls shortly after entry, then a later checkpoint's `candidate_stop` computes above live price because the trail had already gone stale between checkpoints. v3.59's checkpoint-count grace (adopted 9/9) addressed *when* tightening starts but not the underlying staleness gap — AAPU and MVLL (2 of the last 3 trades, both real losses) proved it insufficient and tripped the circuit breaker. **Fix:** v3.62 adds a live staleness guard (fresh quote pulled immediately before finalizing `candidate_stop`, skip the ratchet if already breached); v3.63 replaces the checkpoint-count grace entirely with an unconditional profit gate (stop only ratchets while live price is above the entry fill price). Both retrospectively verified against AAPU and MVLL — both losses would have been directly prevented, not just softened. Reopen only if the *same* mechanism reappears despite both fixes being live. Full instance-by-instance detail: `git show dd716ce:RULEBOOK.md` (E6).

---

## Current state

**Pull on demand only — like Part E, never read this section front to back (added 2026-09-14, token-cost cleanup).** Every entry below is a historical rule-change record; the full reasoning behind each one already lives permanently in the git commit that made it. Only entries actively cited by an inline pointer elsewhere in this file are kept in full — currently **v3.43, v3.44, v3.46**. Everything else is one line: what changed, one-sentence why, and a pointer. If a rule's fuller rationale is genuinely needed and it isn't one of those three, `git show <hash>` (or `git log --all --grep=vX.XX -- RULEBOOK.md` for versions predating this file's per-version commit convention) has the original text, unedited, in full.

**v3.68** — C12: a losing exit's own instrument is now excluded outright from re-entry for the rest of the day, not just denied v3.67's shortcut. Direct governor correction, 9/15, after RKLB stopped out at -2.01% (9:50) and was still allowed to compete in — and win — a normal C7 ranking ten minutes later on its static historical `mfe_per_stop`, ignoring the reversal-prone live action it had just shown at its own exit; re-entered, reversed again, closed a second time at -1.59%. Governor's original instruction was specifically about re-entering a stock after a *winning* exit — a loser was never meant to get the same benefit of the doubt, and "goes straight to the full gate stack" (v3.67) wrongly let it still compete instead of being excluded.
**v3.67** — C12 given a new step 0: a profitable exit checks its own instrument first for continuation (re-run C10 on it alone) before falling through to the full shortlist gate stack — a stop is a pause to reassess, not an automatic move-on. Direct governor instruction, 9/14 10:35 checkpoint, prompted by RBLX's own session: stopped out +0.46%, kept climbing, re-entered a few checkpoints later only because it happened to still win a fresh full-shortlist ranking — the governor wants that continuation check to be the *first* thing checked after any winning exit, not a byproduct of re-ranking against unrelated candidates. Applies to inverse exits identically (C10's mirror). Losing-exit handling was tightened further in v3.68.
**v3.66** — C10 leg 1's baseline given a hard floor: `effective_baseline = max(true 9:30 open, C12 reset price)`, never below the real open. Governor correction, 9/14 10:30 checkpoint, after RIG was entered via a C12-reset baseline ($5.570) that sat below RIG's own 9:30 open ($5.700) — RIG had been falling all morning and never once cleared its actual open; the reset (from RBLX's unrelated exit) made a bounce off RIG's own low look like "not falling." A live, real-money entry that shouldn't have cleared the gate, not a hypothetical. Inverse leg mirrored (ceiling, `min(...)`). C12 step 3 updated to match.
**v3.65** — C10 given an inverse leg mirroring C1/C6's (checks the commodity proxy, not the inverse vehicle), closing the gap that silently blocked every inverse commodity trade since v3.61. Direct governor instruction, 9/14 9:40 checkpoint, live mid-session with SLV/GLD/COPX/URA all sitting on qualifying inverse setups at the time.
**v3.64** — management cadence tightened 10min→5min, 9:45–11:15, 19 checkpoints. `a4f9669`
**v3.63** — ratchet now gated on being in profit (live price > entry fill); replaces v3.59's checkpoint-count grace outright. `9871740`
**v3.62** — live staleness guard: fresh quote pulled before finalizing `candidate_stop`, skips the ratchet if already breached. `d0bdfd5`
**v3.61** — commodity inverse trades enabled, C1/C4/C6 all get a mirrored bearish leg. `c21d8f2`
**v3.60** — close moved 11:00→11:30, three more full-protection management checkpoints added ahead of it. `fdfe3be`
**v3.59** — B2 two-checkpoint entry grace (no ratchet at #1, half-rate at #2) — retired outright by v3.63. `c937357`
**v3.58** — 11:00 close changed from a stop-pin (found structurally broken) to a direct market sell. `656240a`
**v3.57** — trading day close moved up from 12:00 to 11:00. `5c11b2d`
**v3.56** — entry moved back to 9:40, reverting v3.54's shift to 9:35. `70205a3`
**v3.55** — entry+5 catch-up check added for the AFRM/GUSH/NUGT gap pattern (now permanently dormant under v3.64's cadence). `25c7af5`
**v3.54** — grid compressed, entry→9:35, close→12:00 (both later reverted, v3.56/v3.57). `git log --all --grep=v3.54 -- RULEBOOK.md`
**v3.53** — sectors dropped entirely; individual stocks (25-name market-wide scan) plus commodities as the sole group exception. `git log --all --grep=v3.53 -- RULEBOOK.md`
**v3.52** — two-speed management cadence, 10min through 10:50 then 15min to 12:30 (both since superseded by later cadence changes). `git log --all --grep=v3.52 -- RULEBOOK.md`
**v3.50** — C10 leg 1 tightened to strictly-above baseline, re-verified against a live quote immediately before order placement. `git log --all --grep=v3.50 -- RULEBOOK.md`
**v3.49** — E1's loss definition changed to `pnl_pct_position` worse than −1.0% (was any negative P&L). `git log --all --grep=v3.49 -- RULEBOOK.md`
**v3.48** — pre-open fix to v3.47's B6 log-seeding scope (never ran live unfixed). `git log --all --grep=v3.48 -- RULEBOOK.md`
**v3.47** — B6's `session_high`/`session_low`/ER moved from re-derived-every-checkpoint to incrementally maintained. `git log --all --grep=v3.47 -- RULEBOOK.md`

**v3.46 (10:36 ET, governor session, live mid-day): C10 leg 1's baseline fixed to 9:30, reset only by an exit's fill timestamp (C12) — never by an intervening checkpoint.** Prompted by today's own 10:00 entry, where the five newly-added candidates (ESTC/GAP/SOLS/AFRM/UMC, added ~9:50) had no 9:30 read of their own, so their first C10 check was treated as an ad hoc free pass. Governor's proposed fix, confirmed: a candidate's first-ever entry check of the day always compares against 9:30's real price (pulled fresh via historicals if it joined the watchlist later), no matter which checkpoint that first entry attempt lands on — 9:40, 10:00, or later all compare back to 9:30 alike, since merely re-checking a candidate without entering it doesn't advance the baseline. The one thing that does advance it: an exit (C12), which resets the baseline to that exit's fill-timestamp price for every shortlist candidate being reconsidered, not just the one that closed — already how today's post-AFRM T+0/T+10 mini-cycle worked, now made the general rule rather than a special case. No effect on any decision already made today (AFRM's entry, the 10:00/10:30 checkpoints) — those stand as executed under the rule in force at the time; this governs from here forward.

**v3.45** — lean cleanup, dead fields (`breakeven_trigger`/`trail_pct`) retired, B2/B3/B4 rationale trimmed to pointers, `archive/EXPERIMENTS.md` swept. `git log --all --grep=v3.45 -- RULEBOOK.md`

**v3.44 (evening of 8/27, same governor session, continued): the average-based ratchet replaced by a single continuous chandelier trail anchored to `run_high`, and the separate velocity trigger retired.** Governor's own read of the old (pre-v3.40) system: the entry-time stop was its best feature, but the staged ratchet triggered too rarely and moved too linearly. Backtested against all 13 trades on record (real minute-bar paths, each instrument's own noise band from its real ~40-day history) sweeping a discount multiplier 1×–5× off `run_high`: **`candidate_stop = run_high × (1 − 2 × stall_threshold_pct)`, `new_stop = max(current_stop, candidate_stop)`, checked every 15-min checkpoint** — 2× beat the real historical results on both average captured gain (+1.56% vs. the real system's +1.53%) and win rate (9/12 vs. 7/12), fixing two real reversal losses (UEC 8/26 -2.54%→+0.26% simulated; MSTX 8/20 -1.24%→+1.02% simulated) without giving other reversals extra room, unlike wider multipliers (4×–5×) which scored higher only because of one outlier trend day (MSTX 8/27 continuing to run for hours past its real exit) while making two genuine reversals worse. Anchoring to `run_high` instead of the trailing average is what gives a real trend room to breathe — the average sits close to the entry price right after a fill, so a normal early pullback could trip the old design before a trend had even formed (found via a separate before/after check on UUUU 8/25: the average-based design would have cut a real +$6.86 winner down to roughly breakeven). The velocity trigger is retired — anchoring continuously to `run_high` already gives the fast-reaction behavior it existed for, without a second mechanism running in parallel.

**v3.43 (evening of 8/27, governor session): a full restructure driven by the data — every profitable entry across the system's history has landed between 9:42 and 10:34 ET, and the one entry after 10:34 (MSTX 8/21, 12:32pm) lost money.** Trading day shortened to 9:00–12:30 (was 9:00–4:00pm); management checkpoints now run every 15 minutes from 10:00–12:30 (was 30 minutes to 4:00pm), net *fewer* total daily checkpoints (15 vs 17) despite the tighter cadence. Entries valid anywhere 9:40–12:30, no preferred-window distinction. **B2's stepped 8-stage ratchet is retired, replaced by a continuous rule**: every 15-min checkpoint ratchets the stop to `avg_price(since last checkpoint) × (1 − stall_threshold_pct)`, per-instrument noise-scaled, up only — validated against MSTX's actual 8/27 bars before adoption (would have exited +5.79% vs. the real trade's velocity-driven +5.37%). The velocity trigger is unchanged, still the faster-reacting override for a single sharp spike. The 12:30 checkpoint additionally pins the stop to live price, which is what now enforces same-day close — no separate 4:00pm deadline. **B3's stall-count ladder is retired entirely** — the continuous ratchet already squeezes a stalling position without a second, potentially-conflicting counting mechanism. C11's chop-filter table compressed to 3 bands fitting 9:40–12:30. No more extended-hours slots (4:30–7:30pm gone) or cadence-reduction rule (both moot with the day already this short).

**v3.38–v3.42** — 8-stage ratchet + fixed-target removal (v3.38–v3.40), sector-first/leveraged-priority research (v3.41), 24-name/6-sector watchlist (v3.42) — all fully superseded by v3.43 (day restructure), v3.44 (chandelier trail), and v3.53 (sectors dropped entirely). `git log --all --grep="v3\.3[89]\|v3\.4[012]" -- RULEBOOK.md`

**Daily close-summary entries prior to 2026-09-14 (dated recaps of specific trading days, e.g. "Wednesday 2026-09-02 closed flat...") were removed in the same cleanup** — `archive/trades.csv` is the authoritative per-trade record and each day's own dated E5 log (git-tracked, never deleted from history) already carries the full checkpoint-by-checkpoint narrative; the recap here was a third copy of the same facts. Nothing is lost — `git log -p -- RULEBOOK.md` around any date recovers the exact wording if ever needed.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
