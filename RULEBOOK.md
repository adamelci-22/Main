# Agentic Trading Rulebook

**Account:** Robinhood `462514035` ("Agentic"), cash, `agentic_allowed=true`.
**Policy version: 3.5.** Bump on every rule/threshold change; record it in the commit.

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

Any failure → no entry in that sector's leveraged vehicle. **Two fixed observations decide it — never add intermediate readings.**

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
- After 11:00 a new entry must be **clearly better** than the morning offered, not merely available. Boredom is not a signal.
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

*As of Aug 18 2026, ~9:03am ET (premarket):* **Broad risk-off — semis/tech hit hard, energy the lone bright spot, continuing yesterday's driver.** Overnight escalation: Trump threatened further economic pressure on Iran and to "bomb" Oman if it interferes with Strait of Hormuz plans. Nasdaq-100 futures -1.1%, S&P futures -0.4%. Oil at a 2+ week high; gold +0.36%. This is the same geopolitical driver as yesterday's GUSH trade, now amplified.

**Premarket individual moves** (vs. adjusted previous close): MU -4.65%, AMD -3.36%, SMCI -3.34%, TSM -2.55%, NVDA -2.05%, AVGO -1.96%, MSTR -1.66%, COIN -1.56%, TSLA -1.51%, META -1.22%, GOOGL -0.51%, PLTR -0.16% — **all red, none clear C3's up-only magnitude leg.** MSFT +0.63% and AAPL +0.56% show relative strength inside the selloff but neither clears +0.75%. **HD +2.39%** on Q2 earnings (reported 6am ET) is the one real individual mover with a named catalyst — unaffordable regardless (**$345.95**, no leveraged wrapper exists for it, plain-stock price alone is 5.6x the account).

**Sector proxies (premarket, informational only — not the C1 baseline):** SMH -3.21% · QQQ -1.22% · SPY -0.40% · XLE **+1.09%** · GDX -1.03%. Energy is the only sector green; GUSH itself **+1.93%** premarket, continuing to extend yesterday's move.

### C1 Gate-1 baseline — formal 9:30 reading

**Recorded 9:30 checkpoint, read time 2026-08-18T13:31:04Z (~9:31am ET).** Compare against the 9:40 reading; two fixed observations decide C1, no intermediate reads.

| Proxy | 9:30 day change | vs. premarket |
|---|---|---|
| XLE | **+1.49%** | strengthened (+1.09%→+1.49%) |
| SPY | −0.50% | weakened slightly |
| QQQ | −1.24% | ~flat |
| GDX | −1.54% | weakened |
| SMH | −2.99% | modest recovery, still deeply red |

**Verdict at this reading: only XLE is alive for C1.** SPY, QQQ, GDX, SMH are all negative at 9:30 — leg 1 ("positive at 9:30") already fails for all four; nothing left to track there. XLE is positive and has strengthened since the open — needs to hold positive and not fade below +1.49% at 9:40 to complete the pass.

**Breadth and premarket-to-real-volume check: this is genuine, broad risk-off, not one name.** Every individual mover checked (NVDA, AMD, MU, TSM, SMCI, AVGO, TSLA, COIN, MSTR) is still solidly red at the open — MU worst at -4.37%, AMD -2.97%, TSM -2.96%. Premarket weakness **held into real volume**, it did not fade — the opposite pattern from yesterday's single-name MU dislocation. No individual stock is a candidate today; this is entirely a sector-level (energy) story if it's tradeable at all.

**⚠ Rule gap surfaced today, not resolved — flagging rather than guessing:** C1's literal text ("positive at 9:30 and positive at 9:40") is written for a bullish sector-leveraged trade only. It never defines the entry gate for an inverse sector ETF (e.g. SOXS, SQQQ), which today's broad semis/tech weakness could otherwise make relevant. **Declining any inverse-sector trade today on this gap rather than inventing an interpretation for real money** — C3 already declines to touch inverses for individual stocks and points to "C1 + an inverse sector ETF" as the outlet, but C1 itself was never actually written to cover that case. Worth a rule clarification when there's time to discuss it, not something to resolve unilaterally mid-session.

### 9:40 entry window — no trade, both gates failed cleanly

**Live re-check, read time ~2026-08-18T13:41:25Z (~9:41am ET).** C3 magnitude leg re-confirmed for all 9 individual leveraged-wrapper-mapped stocks: NVDA -1.671%, AMD -3.109%, MU -3.630%, TSM -2.954%, SMCI -0.849%, AVGO -2.175%, TSLA +0.153%, COIN -1.143%, MSTR -1.305%. **All fail** — none clears +0.75%; TSLA flipped positive but is nowhere close to the bar. No individual candidate exists.

**C1 leg 3 re-checked for XLE, the only sector still alive at 9:30:** 9:30 reading was +1.486% ($63.51); 9:40 reading is **+1.206%** ($63.335). Still positive, but the 9:40 reading is **below** the 9:30 reading — leg 3 ("the 9:40 reading not below the 9:30 reading") fails. GUSH itself was still up on the day at 9:40 ($42.85, +0.563%), but that's irrelevant: GUSH only qualifies today through C4's rank-2 track gated by XLE passing C1, and XLE just failed.

**Conclusion: no trade at 9:40.** Both the individual-stock path and the sector-leveraged path close out at this checkpoint for the same underlying reason — this morning's move weakened into the open instead of confirming, the mirror image of yesterday's MU/GUSH pattern where the sector strengthened. Still flat, still inside the preferred 9:40–11:00 window per the schedule — 9:40 failing does not close the day; a fresh candidate at 10:00 or 10:30 is still eligible for the day's one round trip if either gate flips clean. Nothing carries forward as a bias either way — re-derive cold at the next checkpoint.

### 10:00 management checkpoint — flat, still no candidate

**A1 confirmed fresh from the broker: no positions, no resting orders.** Blocking conditions clear, not that it matters while flat.

**Live re-check at ~10:01am ET.** Individual stocks all still deeply red: NVDA -2.211%, AMD -5.121%, MU -5.377%, TSM -3.766%, SMCI -2.481%, AVGO -3.302%, TSLA -0.492%, COIN -2.418%, MSTR -2.114% — every one further from C3's +0.75% bar than at 9:40, not closer. No individual candidate.

**XLE:** $63.34, +1.214% — a slight recovery off the 9:40 low (+1.206%) but still **below the 9:30 baseline of +1.486%**. C1 leg 3 still fails; the sector hasn't reclaimed the level it needs to hold. GUSH itself is +0.915% ($43.00) but remains gated by XLE's failure.

**B5 headlines (last flat-check per the schedule — none required after 10:00 while flat):** Same driver, escalating — a vessel was reportedly struck by an "unknown projectile" in the Strait of Hormuz overnight, Trump posted an image labeling the waterway "New US Territory," and Iran's Parliament Speaker reiterated the strait stays closed until sanctions lift and assets are unfrozen. Brent just under $91, WTI toward $85 — both at their highest since July. This is real, intensifying, and consistent with XLE/GUSH's relative strength — the reason energy hasn't cracked like the rest of the tape, just not enough yet to clear C1's specific bar.

**No trade at 10:00.** Pre-commit for 10:30: enter GUSH (rank-2, C4) only if XLE's next reading clears **+1.486%** (back above the 9:30 baseline, satisfying leg 3) while still positive — no other condition substitutes. No individual stock is watched further; the gap to +0.75% is now 1.2–4.6pp across all nine, not closing on a single intraday check.

### 10:30 management checkpoint — pre-commit checked, condition not met

**A1 confirmed fresh: no positions, no resting orders.**

**Pre-commit test: XLE at $63.425, +1.350%.** Required **+1.486%** to clear leg 3 — still short by 0.14pp, though it's the closest read yet (up from +1.206% at 9:40, +1.214% at 10:00). Condition not met; honoring the pre-commit means declining, not re-deciding on a softer read. GUSH itself +1.126% ($43.09), still gated.

**Individual stocks, all still red:** NVDA -2.062%, AMD -4.647%, MU -5.391%, TSM -3.578%, SMCI -2.927%, AVGO -3.326%, TSLA -0.401%, COIN -0.326%, MSTR -0.891%. TSLA/COIN/MSTR narrowed their losses but none is within reach of +0.75%; no candidate.

**No trade at 10:30.** This is the second-to-last slot of the preferred window — D1's early-shutdown clause doesn't apply (buying power is intact and the day's round trip is unspent; entry is still structurally possible, the gate just hasn't cleared), so the day continues on schedule rather than shutting down early. Pre-commit for 11:00, the window's last slot: same XLE trigger, **+1.486% while positive**. If still short at 11:00, drop to hourly per D1's cadence-reduction rule and stop watching the half-hour slots — the bar for a late entry rises from there.

### 11:00 management checkpoint — preferred window closes, no trade, cadence dropped to hourly

**A1 confirmed fresh: no positions, no resting orders.**

**Pre-commit test: XLE at $63.21, +1.006%.** Required +1.486% — the gap widened again versus 10:30's +1.350%, moving away from the trigger, not toward it. Condition not met. GUSH itself is now barely positive (+0.692%, $42.90), its smallest reading yet.

**Individual stocks, all still red and several re-widening:** NVDA -2.747%, AMD -5.883%, MU -7.524% (worst of the day), TSM -4.348%, SMCI -5.068%, AVGO -3.576%, TSLA -1.224%, COIN -1.960%, MSTR -2.298%. TSLA/COIN/MSTR's brief 10:30 narrowing reversed. No candidate — the morning offered nothing across either path, all four checks (9:40, 10:00, 10:30, 11:00) agree.

**Preferred window closed with no entry.** Per D1's cadence-reduction rule, dropped to hourly and deleted the half-hour slots: 11:30, 12:30, 2:30 and 3:30 removed. **The 1:30pm slot's deletion was denied** (a tool-call permission decline, not a rulebook exception) — it stays armed and will need handling at the 1:00pm checkpoint rather than firing as a stray half-hour slot. Any entry from here forward must be **clearly better** than what the morning offered, not merely available — the bar is deliberately higher past this point, per E4/D1.

### 12:00 management checkpoint — flat, declining a nominal pre-commit hit on a rule-design ground

**A1 confirmed fresh: no positions, no resting orders.**

**XLE at $63.525, +1.510% — the pre-commit's literal +1.486% trigger is technically cleared, still positive.** GUSH itself is at its best reading of the day, +1.807% ($43.38). On the number alone, the 10:00 pre-commit says enter.

**Declining anyway, and flagging why rather than trading on it.** C1 is written as a **one-shot gate anchored to two fixed timestamps** — "positive at 9:30, positive at 9:40, 9:40 not below 9:30" — not a continuously-re-tested condition. That test already ran and **failed at 9:40** (9:40's +1.206% came in below 9:30's +1.486%); nothing in C1 provides for re-running it later in the session when price happens to revisit the same level. The XLE-clears-+1.486% tripwire in the 10:00/10:30/11:00 pre-commits was **my own shorthand for "the sector recovers," not an actual rule in the book** — treating it as a live entry trigger now would mean inventing a late-session re-entry gate for real money that C1's text does not contain. Per standing policy, a genuine rule gap gets flagged and the trade declined, not resolved by guessing. **Individual stocks are moot regardless:** NVDA -2.140%, AMD -5.099%, MU -6.525%, TSM -3.722%, SMCI -3.762%, AVGO -2.752%, TSLA +0.165% (barely positive, still far under +0.75%), COIN -1.119%, MSTR -2.032% — no candidate there either.

**No trade at noon.** Worth a rule discussion later: should a sector-leveraged path get a defined late-session re-entry test distinct from C1's 9:30/9:40 anchor, or should recovered sector strength after the preferred window simply never be tradeable under the current gate design? Not resolved unilaterally today. Noon boundary also now in effect for the stall ladder (moot while flat).

### 1:00pm management checkpoint — flat, no candidate, XLE tripwire retired

**A1 confirmed fresh: no positions, no resting orders.**

**Individual stocks, all still failing C3, best barely positive:** NVDA -2.222%, AMD -5.251%, MU -7.153%, TSM -4.125%, SMCI -2.417%, AVGO -2.959%, TSLA +0.050%, COIN -1.306%, MSTR -2.386%. No candidate.

**XLE $63.465 (+1.414%), GUSH $43.33 (+1.690%)** — not tracked against the old +1.486% number anymore. That tripwire was retired at noon: C1 already resolved (fail) at 9:40 and isn't re-testable intraday, so continuing to watch for XLE to cross a specific level would just be re-litigating the same invented gate. Nothing left to watch on the sector side today absent an actual rule change.

**No trade at 1:00pm.** Nothing new to pre-commit to — both paths are closed for the rest of the session on their own terms (individual stocks on distance from +0.75%, sector on C1 already having run its one shot), not on a moving price target. B5 is not required past 10:00 while flat per its own note — skipped, not missed.

### 1:30pm — stray half-hour slot, fired despite the 11:00 cadence drop, no action needed

**This is the slot whose deletion was declined at 11:00.** It's a one-shot (`run_once_at`) trigger, so firing here consumes it — no further cleanup call needed; it won't recur. **A1 confirmed fresh anyway: no positions, no resting orders.** Individual stocks unchanged in kind: NVDA -2.058%, AMD -5.183%, MU -7.062%, TSM -4.199%, SMCI -1.508%, AVGO -2.812%, TSLA -0.654%, COIN -1.250%, MSTR -2.501% — no candidate. XLE +1.454%, GUSH +1.361% — not a live signal per the noon/1:00 finding (C1 already resolved, not re-testable). No trade; nothing to pre-commit differently than 1:00's entry.

**20-name watchlist**, profiled just-in-time (B1) on 31 sessions through Aug 17, ranked by `mfe_per_stop` — ✓ = affordable as 1 whole share against $61.99 settled. Individual list swapped AMZN (yesterday's flattest name) for HD (today's real mover):

*15 individuals:*
| Rank | Symbol | Underlying | Day chg | mfe_per_stop | Price | Afford |
|---|---|---|---|---|---|---|
| 1 | MSTX | MSTR | -1.66% | 0.903 | $8.32 | ✓ |
| 2 | SMCX | SMCI | -3.34% | 0.770 | $12.01 | ✓ |
| 3 | PLTR | — | -0.16% | 0.739 | $172.28 | ✗ |
| 4 | MUU | MU | -4.65% | 0.688 | $31.54 | ✓ |
| 5 | CONL | COIN | -1.56% | 0.685 | $4.03 | ✓ |
| 6 | AMDL | AMD | -3.36% | 0.669 | $52.73 | ✓ |
| 7 | TSMU | TSM | -2.55% | 0.580 | $68.24 | ✗ ($6.25 short) |
| 8 | META | — | -1.22% | 0.570 | $562.05 | ✗ |
| 9 | TSLL | TSLA | -1.51% | 0.503 | $8.33 | ✓ |
| 10 | NVDL | NVDA | -2.05% | 0.493 | $35.06 | ✓ |
| 11 | MSFT | — | +0.63% | 0.478 | $483.37 | ✗ |
| 12 | AVGX | AVGO | -1.96% | 0.420 | $46.37 | ✓ |
| 13 | GOOGL | — | -0.51% | 0.372 | $342.26 | ✗ |
| 14 | HD | — | +2.39% | 0.352 | $345.95 | ✗ |
| 15 | AAPL | — | +0.56% | 0.310 | $307.30 | ✗ |

TSMX (pricier TSM wrapper, $77.79) excluded in favor of TSMU — both unaffordable regardless.

*5 sector/index vehicles* (feed C1; leveraged form noted for C4 rank-2/3):
| Symbol | Proxy | Day chg | Leveraged form | mfe_per_stop | Price | Afford |
|---|---|---|---|---|---|---|
| XLE | Energy | +1.09% | GUSH | 1.025 | $43.43 | ✓ |
| SPY | Broad market | -0.40% | SPXL | 0.449 | $291.13 | ✗ |
| QQQ | Tech/index | -1.22% | TQQQ | 0.454 | $73.45 | ✗ |
| GDX | Gold miners | -1.03% | NUGT | 0.875 | $164.11 | ✗ |
| SMH | Semis | -3.21% | SOXL | 0.574 | $134.22 | ✗ |

**GUSH ranks #1 of all 21 profiled instruments (1.025) and is the only sector-leveraged vehicle both affordable and (if C1 holds) gate-eligible today** — same instrument as yesterday, same driver, still moving in the same direction. Top-ranked affordable individual: MSTX (0.903, also #1 among individuals) — but MSTR is red premarket, no thesis. Second-ranked affordable individual: SMCX (0.770) — also red, no thesis. **Nothing on the individual side has both a bullish move and clears the bar; re-confirm everything live at 9:40 per C7** — this is the 9:00 shortlist, void if capital or thesis moves.

**Stale for any later session; refresh before trusting.**

---

## Current state

**Flat.** Last close 2026-08-17: one trade (GUSH, -$0.02, r=-0.02) — full detail lives in `archive/trades.csv` and the commit history, not repeated here.

**Loss streak 1 of 3** (cleared 2026-08-15). Floor: **$30.42** (50% of deposited cash, recomputed each 9:00 — reconfirm live, don't trust this number past the next research checkpoint).

**Live files:** `archive/trades.csv` is the append-only trade log and the circuit-breaker's only input; a row gets appended at exit, not at entry. `tools/profile.py` computes risk numbers on demand (B1). Nothing else is required to trade.
