# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), **limited margin** (converted from cash 2026-08-20), `agentic_allowed=true`.
**Policy version: 3.11.** Bump on every rule/threshold change; record it in the commit.

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
| Weekly day-trade cap reached | ≥10 day trades already in the trailing 7 calendar days (E2) — self-imposed pacing limit |
| Position already open | One position, one resting order (E2) |

**⚠ CURRENT STATE — streak 1 of 3.** Governor cleared the breaker **2026-08-15**; count only trades closed after that date. One loss since: GUSH, closed 2026-08-17 (-$0.0199). The streak is computed from `archive/trades.csv`, the **live append-only log** — new rows go there. **A missing or unreadable file must never be read as a streak of zero**; that silently disables the breaker at the moment it matters most.

**⚠ CURRENT STATE — weekly day-trade count as of 2026-08-20: 4** (MSTX + BSX today, GUSH 8/19, GUSH 8/17 — all within the trailing 7 calendar days). Well under the 10-cap; not blocking. Recompute fresh each checkpoint per E2, don't reuse this number cold.

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

> **Override (dormant while a position is sized at 1 share — needs 2+ to have a "half" to sell).** Staying past target requires *named new information*; momentum does not qualify. If invoked: sell half immediately, raise the remainder's stop to ≥ target, re-justify aloud every checkpoint (silence = expiry), sell the remainder when the information dies or any exit fires. One extension per trade. Log both fills; report blended P&L honestly including when the override lost money.

## B5. Headlines while holding

Check **every hour**, position-relevant only, same-day news only — yesterday's is already in the price. Name the catalyst in the report.

*(While flat and no candidate is live, hourly is enough (D1's cadence reduction already drops the check frequency). Don't stop checking just because an earlier trade already closed today — a later opportunity is still tradeable.)*

---

# PART C — ENTRY (9:00 · 9:30 · 9:40 primarily; any 10:00–3:30 checkpoint while flat)

> **No position may be opened outside 9:40–4:00.** Multiple round trips per day, across different candidates, are now possible (limited margin, since 2026-08-20) — a fresh entry may be taken at **any** checkpoint while flat, not only 9:40, subject to C1's late-entry clause and the weekly day-trade cap (E2). Check the cap fresh before every entry, not just the first.

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

## C2. Gate 2 — a leveraged single-stock ETF's underlying must lead its sector

Both as day change; proxy map in **E3**. If `underlying_pct < sector_pct` → **decline.** Buying the laggard with leverage turns a correct sector call into a losing trade. Does not apply to sector or index vehicles — those *are* the group.

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

**Track, per candidate, from the day's own checkpoint reads already logged in E5** (9:30 is the first formal read; the 9:00 scan is informal/stale per C3 and does not count here):

- `session_high` — the best checkpoint reading so far today. Advances any time a fresh high prints.
- `session_low` — the lowest checkpoint reading recorded *since* `session_high` was last set. Only exists while price is currently below `session_high`; clears the instant a new `session_high` prints — a fresh high ends the pullback episode outright.

**All three must hold, checked fresh at every entry-eligible checkpoint (never cached):**

1. **Not currently falling.** This checkpoint's reading ≥ the immediately prior formal checkpoint's reading, for this candidate specifically. (The per-candidate, universal version of C1 leg 3 — C1 itself stays scoped to sector proxies only.)
2. **If below `session_high`, the bounce off `session_low` must be real, not noise.** Price must clear `session_low × (1 + stall_threshold_pct)`, using *this candidate's own* `stall_threshold_pct` from today's fresh JIT profile (B1) — a choppier name needs a bigger bounce to count, a calmer one needs less. Automatically satisfied when price is at or above `session_high` (no pullback active, nothing to confirm).
3. **Giveback ceiling.** Decline regardless of a qualifying bounce if `(session_high − price) / (session_high − prior_close) > 65%` — more than roughly two-thirds of the day's move already erased reads as a broken trend, not a dip. (`prior_close` = the official prior-session close, same reference C3 uses.) In practice this rarely binds on its own — a candidate that's given back that much has usually also failed C3's magnitude gate outright — but it exists as a backstop against buying a confirmed-but-small bounce inside an otherwise-collapsed move.

Fails leg 1 → blocked outright, full stop, regardless of how the candidate otherwise ranks. Fails leg 2 or 3 while leg 1 passes → the "bounce" isn't real yet or the move is too far gone; wait for the next checkpoint rather than forcing it (C9's "never force a trade because the window is closing" applies here too).

Reset `session_high`/`session_low` at 9:00 daily — nothing carries between sessions (per this file's own opening line).

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
- **PDT (Pattern Day Trader) restriction is gone.** Verified directly from Robinhood's own support page (fetched 2026-08-20, re-read with today's real date in view so "will" vs "already has" isn't misread): *"On June 4, 2026, FINRA's new intraday margin standards will replace Pattern Day Trading (PDT)... No more day trade restrictions or day trade calls with your Robinhood margin account... If you had a pattern day trading (PDT) flag or restrictions on your account, they'll be removed... You will no longer need to maintain a $25,000 minimum portfolio value to day trade."* June 4, 2026 is in the past relative to today (2026-08-20) — the change is live, not pending. The old 4-day-trades-in-5-business-days trigger and the $25,000 minimum no longer apply. **Residual, smaller uncertainty, not fully closed out:** the page discusses "margin account" generally without singling out `limited_margin` by name; inferred it's covered because the *old* PDT rule explicitly applied to "both full and limited margin accounts" per the same research pass, and the new rule replaces that identical framework wholesale. Also unconfirmed: whether Robinhood's separate **$2,000 margin minimum equity** requirement (still standing per the same page) applies to `limited_margin` itself or only to actual margin investing/borrowing — `get_limited_margin_upgrade_info`'s own description states limited margin adds "no borrowing or leverage," which argues against it applying here, but that's inference, not a citation naming the two together. Watch for any broker-side restriction message as a signal this inference was wrong; nothing in current account state suggests it was.
- **Weekly day-trade cap — self-imposed pacing, not a compliance requirement.** With PDT gone, this exists purely to bound churn/slippage on a small account, per governor instruction to set an explicit weekly limit. Cap: **no more than 10 day trades in the trailing 7 calendar days** (today inclusive). Count the same way as before: every `archive/trades.csv` row is a day trade (B4/Part C force same-day entry and same-day close), plus any governor-placed manual round trip visible in `get_equity_orders` that wouldn't appear in the trade log. Recompute fresh at every entry-eligible checkpoint, never cached. Revisit the number if it turns out to bind often (too tight) or never binds at all (too loose, in which case it's just there for the record).
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

*As of Aug 21 2026, ~9:03am ET (premarket):* **Crypto is still the story, third session running.** MSTR and COIN are both up hard again premarket, and their leveraged wrappers are up harder still — same shape as Wed/Thu (Trump's crypto-legislation push, Bitcoin rallying). No new headline confirmed yet this morning specifically; treat this as continuation of the existing catalyst until B5's hourly check finds something fresher, not as a new, independently-sourced story. Gold/miners are also strong (GDX +2.74% premarket) — second axis worth watching alongside crypto.

**A1 verified fresh:** `get_equity_positions` empty, `get_equity_orders` since 2026-08-21T00:00:00Z empty — flat, no resting orders, nothing pending. **Account fully settled:** `get_accounts` shows `unsettled_funds: $0.00`; `get_portfolio` confirms **buying power $202.32 = full account value** — this is the real, uncomplicated full-deployment number the governor described, no T+1 asterisk this time. Streak unchanged at 1 of 3 (last loss: MSTX, 2026-08-20). **Weekly day-trade count (E2, trailing 7 calendar days, Aug 15–21): 4** (MSTX + BSX 8/20, GUSH 8/19, GUSH 8/17) — well under the cap of 10, not blocking.

**Premarket individual moves** (underlying vs. adjusted previous close, broker quotes): **MSTR +7.39%**, **COIN +4.60%** (crypto, third day running), TSM +1.80%, AVGO +1.53%, SMCI +1.59%, AMD +1.35%, MU +1.40%, TSLA +1.30%, NVDA +0.42% (weakest of the semis complex). Plain stocks all essentially flat: GOOGL +0.74%, AMZN +0.72% (both just under the +0.75% bar), AAPL +0.29%, MSFT +0.28%, META +0.32%, PLTR +0.17%.

**Wrapper premarket moves** (leverage effect confirmed again — wrapper move is larger than the underlying's): **MSTX +14.48%**, **CONL +9.14%**, TSMU +3.34%, SMCX +3.30%, AVGX +2.82%, AMDL +2.71%, MUU +2.71%, TSLL +2.36%, NVDL +0.57%.

**Sector proxies (premarket, informational only — not the C1 baseline):** GDX +2.74% (gold miners strong, opposite of Wednesday) · SMH +1.31% · QQQ +0.75% · SPY +0.52% · XLE −0.05% (energy essentially flat, GUSH's 3-session grind may be pausing).

**20-name watchlist, re-profiled just-in-time (B1) fresh this morning on 43 sessions through Aug 20 close** (`tools/profile.py`, never reused from yesterday) — ✓ = affordable against the real, uncomplicated **$202.32**:

*15 individuals:*
| Rank | Symbol | Underlying | Premarket chg | mfe_per_stop | Ask | Afford |
|---|---|---|---|---|---|---|
| 1 | PLTR | — | +0.17% | 0.906 | $174.56 | ✓ (barely, but not a candidate — underlying flat) |
| 2 | MSTX | MSTR | **+14.48%*** | 0.844 | $12.73 | ✓ |
| 3 | CONL | COIN | **+9.14%*** | 0.773 | $5.88 | ✓ |
| 4 | TSLL | TSLA | +2.36%* | 0.765 | $9.09 | ✓ |
| 5 | SMCX | SMCI | +3.30%* | 0.749 | $12.12 | ✓ |
| 6 | MUU | MU | +2.71%* | 0.644 | $32.98 | ✓ |
| 7 | TSMU | TSM | +3.34%* | 0.595 | $68.81 | ✓ |
| 8 | MSFT | — | +0.28% | 0.520 | $482.90 | ✗ |
| 9 | META | — | +0.32% | 0.508 | $548.29 | ✗ |
| 10 | AMDL | AMD | +2.71%* | 0.506 | $50.01 | ✓ |
| 11 | AMZN | — | +0.72% | 0.464 | $261.97 | ✗ |
| 12 | NVDL | NVDA | +0.57%* | 0.450 | $34.26 | ✓ (but NVDA underlying weak — not a candidate) |
| 13 | GOOGL | — | +0.74% | 0.443 | $343.20 | ✗ |
| 14 | AVGX | AVGO | +2.82%* | 0.377 | $42.72 | ✓ |
| 15 | AAPL | — | +0.29% | 0.373 | $312.25 | ✗ |

*Wrapper premarket % shown where it differs materially from the underlying (leverage effect); underlying's own move used for the plain names.

*5 sector/index vehicles* (feed C1; leveraged form noted for C4 rank-2/3):
| Symbol | Proxy | Premarket chg | mfe_per_stop | Ask | Afford |
|---|---|---|---|---|---|
| GUSH | Energy (XLE) | −0.05% | 0.933 | $44.80 | ✓ (but proxy flat/negative — not a candidate) |
| NUGT | Gold miners (GDX) | **+2.74%** | 0.907 | $207.30 | ✗ (unaffordable, $5 short) |
| SOXL | Semis (SMH) | +1.31% | 0.520 | $127.62 | ✓ |
| TQQQ | Tech/index (QQQ) | +0.75% | 0.454 | $71.95 | ✓ |
| SPXL | Broad market (SPY) | +0.52% | 0.450 | $287.50 | ✗ |

**The real story, third session running: MSTX (#2, 0.844) and CONL (#3, 0.779) are both up huge premarket on the same crypto catalyst as Wed/Thu** — both easily affordable, both with real intraday history now (MSTX traded yesterday; today would be the first live test of the new C10 momentum-direction gate on this exact name, which is worth watching given yesterday's gap-and-fade). TSLL, SMCX, MUU, TSMU, AMDL, AVGX are all real, all clear C3's premarket bar, all affordable — genuine depth in the shortlist today, not a one-name morning. NUGT is the highest-ranked sector vehicle after GUSH but **unaffordable by about $5** — worth noting as a real cost of the current capital base. **Nothing decided yet — re-confirm everything live at 9:30/9:40 per C1/C2/C3/C7/C10, and re-verify A1 fresh before touching any of this.**

**Stale for any later session; refresh before trusting.**

### C1 Gate-1 baseline — formal 9:30 reading

**A1 re-verified fresh at 9:31 ET: flat, no orders, no positions.** Nothing has changed since 9:00.

**Recorded 9:30 checkpoint, read ~2026-08-21T13:31:26Z (~9:31am ET).** Compare against the 9:40 reading; two fixed observations decide C1, no intermediate reads.

| Proxy | 9:30 day change | vs. premarket |
|---|---|---|
| GDX | **+3.095%** | strengthened sharply (premarket +2.74% → +3.10%) |
| SMH | +1.018% | strengthened (premarket +1.31%, but base shifted — still clearly positive) |
| QQQ | +0.414% | roughly steady |
| SPY | +0.355% | roughly steady |
| XLE | +0.329% | flipped positive (premarket was −0.05%) |

**All five proxies are alive for C1 at 9:30** — a stronger, broader tape than either of the last two mornings, where 2-3 proxies failed leg 1 outright. GDX is the clear standout.

**Individual candidates — wrapper day-change at 9:30:**

*Clearing C3's +0.75% bar:* **CONL +11.15%**, **MSTX +9.80%** (both still enormous, crypto catalyst intact), AVGX +3.36%, AMDL +3.15%, SMCX +3.84%, MUU +3.02%, TSLL +2.44%.

*Not candidates:* NVDL +0.56% (short of the bar), GOOGL +0.12%, PLTR 0.00%, AMZN −0.56%, AAPL −0.25%, META −0.21%, MSFT −0.34%. **TSMU shows a stale 0.00% print** (last trade timestamped to yesterday's close, no fresh trade yet at read time) — same pattern as prior mornings, re-check at 9:40 before trusting either way.

**Seven real candidates clearing C3's magnitude bar at 9:30 (informational; formal check is 9:40 live):** MSTX, CONL, SMCX, MUU, AMDL, AVGX, TSLL. Same lineup as the 9:00 premarket read, now confirmed live and, in most cases, stronger. **C10 note: this is the first formal checkpoint of the day for every candidate — `session_high` is seeded at today's 9:30 reading for each one; nothing to compare it against yet, so C10's leg 1 is trivially open at this checkpoint.** Re-confirm everything live at 9:40.

### 9:40 entry — CONL, individual leveraged stock (first live use of C10, and its first block)

**A1 re-confirmed fresh: no positions, no orders, buying power $202.32, fully settled.** Weekly day-trade count 4/10, not blocking.

**C1 re-checked at 9:40:** all 5 proxies **declined from their 9:30 readings** — XLE +0.28% (was +0.33%), GDX +2.86% (was +3.10%), SMH +0.29% (was +1.02%), QQQ +0.19% (was +0.41%), SPY +0.33% (was +0.36%). All still positive (legs 1–2 hold) but **every proxy fails leg 3** — a genuinely broader pullback than either individual candidate saw. Sector-leveraged path not needed regardless; noted for the record since it's the first time all five have failed leg 3 together this week.

**C3 magnitude re-confirmed live for all 15 individuals:** MSTX +11.51%, CONL +15.15%, AVGX +4.50%, SMCX +3.84%, TSMU +2.56% (real print now, 9:30's 0.00% was confirmed stale), TSLL +2.23%, AMDL +1.30%, **META +0.86%** (newly clearing, wasn't a candidate at 9:00/9:30). **MUU dropped out** — +0.39% at 9:40, down hard from +3.02% at 9:30, now below the bar.

**C10 — first live application, and its first real block.** Comparing each candidate's 9:40 reading against its own 9:30 baseline (`session_high`):
- MSTX +11.51% (up from +9.80%) — new high, **passes**.
- CONL +15.15% (up from +11.15%) — new high, **passes**.
- SMCX +3.84% (flat vs. +3.84%) — not below, **passes**.
- TSMU: 9:30 reading was a confirmed stale print, not a real observation — treated as this candidate's first real formal read; **passes** by default.
- AVGX +4.50% (up from +3.36%) — new high, **passes**.
- META +0.86% (up from −0.21% at 9:30, when it wasn't yet a candidate) — **passes**.
- **TSLL +2.23% (down from +2.44% at 9:30) — FAILS leg 1, blocked.** Still clears C3's magnitude bar on its own, but is currently falling — exactly the shape C10 exists to catch.
- **AMDL +1.30% (down hard from +3.15% at 9:30) — FAILS leg 1, blocked.** Same story, larger decline.

**C7 ranking (mfe_per_stop) among C10 survivors:** MSTX 0.844 > CONL 0.773 > SMCX 0.749 > TSMU 0.595 > META 0.508 > AVGX 0.377. **Affordability against $202.32:** MSTX ✓ ($12.41) · CONL ✓ ($6.28 at review) · SMCX ✓ ($12.18) · TSMU ✓ ($67.98) · **META ✗** ($550.69) · AVGX ✓ ($43.43).

**C4:** MSTX ranks rank-1 (individual leveraged stock, C3 cleared, affordable) — checked first.

**C2 on the top pick, MSTX: FAILS.** Underlying MSTR +5.80% vs. its sector proxy IBIT (crypto, per E3) +5.95% — **IBIT is leading, not MSTR** (by 0.14pp; verified with a direct calculation, not eyeballed). Buying the laggard with leverage turns a correct call into a losing trade — declined per C2's own text, despite ranking #1 by `mfe_per_stop` and passing C10 cleanly. **This is the actual reason CONL was bought instead of MSTX today**, not a ranking artifact.

**C2 on the next pick, CONL: passes decisively.** Underlying COIN +7.67% vs. IBIT +5.95% — COIN leads by 1.72pp, real separation. CONL becomes the pick.

**C5 catalyst:** same crypto/Bitcoin-legislation story running its third session — continuation, not a fresh independent source today (flagged as such this morning). Real and named, not "it's going up."

**C9 checked:** within the preferred window. Spread priced at review: bid $6.27/ask $6.28 (1¢ wide) — trivial against a target move of roughly $0.53/share (8.61% of ~$6.30). `all_day_tradability`: untradable (regular hours only, not a concern for a 9:40 entry). Tape moving fast — confirmed by what happened next.

**Sizing per C8:** floor($202.32 ÷ $6.29 review ask) = 32 shares, reviewed clean (no `order_checks` alerts). **First attempt (32 shares, marketable limit $6.29) went unfilled and was cancelled after ~30 seconds — CONL's ask had already run to $6.33, past the limit, on a genuinely fast tape.** Verified `cancelled` with zero `cumulative_quantity` before re-pricing, no partial fill to reconcile. **Re-sized fresh against the live ask:** floor($202.32 ÷ $6.38 new limit) = 31 shares.

**Entry executed:** BUY 31 CONL, marketable limit $6.38, **filled avg $6.3299** (order `6a8855f6`, verified via order response, 09:43:19 ET), total cost **$196.23**. Filled **below** the limit — favorable, despite the fast tape.

**Protective stop placed immediately, confirmed resting** (order `6a885613`, state `confirmed`): stop_market, **$5.98** (stage 1 = fill × (1 − 5.57%)), quantity 31.

**Full ratchet schedule for this fill ($6.3299), from this morning's fresh profile (stop_pct 5.57%, target_pct 8.61%, breakeven_trigger 4.31%, trail_pct 3.71%, stall_threshold 0.65%, min_stop_move 0.93%):**

| Stage | `run_high` reaches | Stop becomes |
|---|---|---|
| 1 — entry | $6.33 (fill) | **$5.98** ← resting now |
| 2 — half-risk | $6.47 | $6.15 |
| 3 — breakeven | $6.60 | $6.33 (fill) |
| 4 — trail | past stage 3 | `run_high × (1 − 3.71%)`, recomputed every checkpoint |
| target | $6.87 | **SELL ALL** |

**Pre-commit for 10:00:** derive the stall count cold from checkpoint prices per B3; before noon, 3 stalls needed to sell and stalls 1–2 don't move the stop. Also worth checking cold at 10:00: whether MSTX (declined here on C2 alone, not on quality) has continued outrunning CONL — if the gap between MSTR and IBIT closes or reverses, that's informational for tomorrow's read on C2's bite, not a reason to revisit today's already-placed trade.

### 10:00 management checkpoint — progressed, run_high advances, stop unchanged

**A1 confirmed fresh: position 31 CONL @ $6.3299 avg cost, stop resting confirmed** (`6a885613`, state `confirmed`, $5.98).

**Stall derivation, cold, per B3:** `run_high` seeded at fill $6.3299. Progression threshold: $6.3299 × 1.0065 = $6.3711. Checkpoint price at 10:00 (read ~2026-08-21T14:01:35Z): **$6.435** — clears the threshold with room. **Progressed, not stalled. Count: 0.** `run_high` advances to $6.435. Stage 2 half-risk needs $6.47 — not reached yet. **Stop stays at $5.98, unchanged.**

**Pre-commit for 10:30:** re-derive the stall count cold against the new `run_high` $6.435 and a new progression threshold of $6.435 × 1.0065 = **$6.4768**. If price clears $6.47 first (stage 2, half-risk), the stop moves to $6.15 regardless of the stall count.

### 10:30 management checkpoint — first stall, stop unchanged

**A1 confirmed fresh: position 31 CONL, stop resting confirmed** (`6a885613`, state `confirmed`, $5.98).

**Stall derivation, cold, per B3:** `run_high` still $6.435 (10:00's high). Progression threshold $6.4768. Checkpoint price at 10:30 (read ~2026-08-21T14:31:05Z): **$6.27** — below both `run_high` and the threshold. **Stalled. Count: 1.** Before-noon ladder: stalls 1–2 don't move the stop, only the ratchet stages can. Stage 2 half-risk ($6.47) was never reached. **Stop stays at $5.98, unchanged. `run_high` unchanged at $6.435** (the high-water mark never decreases).

**Pre-commit for 11:00:** re-check against the same `run_high` $6.435 and threshold $6.4768. A 2nd stall still doesn't move the stop; a 3rd stall before noon forces SELL ALL regardless of price.

---

## Current state

**Holding 31 CONL @ $6.3299 avg (entered 09:43:19 ET), stop resting at $5.98.** Weekly day-trade count now 5/10 (today's CONL round trip will make it 6 once closed) — still well under the cap of 10, not blocking.

**C10 lived up to its design on its first real use.** TSLL and AMDL both still cleared C3's magnitude bar at 9:40 but were falling checkpoint-to-checkpoint (down from their own 9:30 readings) — C10 blocked both. MSTX ranked #1 and passed C10 cleanly but was declined separately on **C2** (its underlying MSTR no longer led sector proxy IBIT, by a thin 0.14pp) — a reminder that C10 and C2 catch genuinely different failure modes, and a candidate can clear one while failing the other. CONL, ranked #2, passed both and became the actual entry.

**Order execution note:** the first attempt (32 shares, limit $6.29) went unfilled on a fast-moving tape and was cancelled cleanly (verified zero fill before re-pricing) — re-priced to a $6.38 limit and filled 31 shares at $6.3299, still favorable. Worth watching whether this kind of slippage-from-speed recurs on crypto-catalyst mornings specifically.

Prior trades: 2026-08-19 GUSH (+$0.22, r=+0.194); 2026-08-18 no trade; 2026-08-17 GUSH (-$0.02, r=-0.02); 2026-08-20 MSTX (-$0.54, r=-0.201, closed early by the governor's own off-cycle decision, not a rule-triggered exit).

**Loss streak 1 of 3** (the 2026-08-19 GUSH win reset it to zero; the 2026-08-20 MSTX loss is the only one since). Buying power: reconfirm live at each checkpoint, don't assume this morning's figure carries forward.

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
