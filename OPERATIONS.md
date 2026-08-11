# OPERATIONS — the intraday hot path

**Read this at every management checkpoint. It is the authoritative text for everything in it.**

Sections keep their global numbers, so a cross-reference like "(§6)" means the same thing in both files.

| Lives here | Lives in `RULEBOOK.md` |
|---|---|
| **§1** trigger hygiene · **§3** early shutdown · **§5** order execution · **§6** stops · **§8** exits · **§11** headlines | §0 objective · §2 schedule and cadence · §4 entry gates · §7 profit-taking · §9 post-exit · §10 mechanics · §12–§17 |

> ### ⚠ YOU MAY NOT OPEN A NEW POSITION FROM THIS FILE ALONE.
> Entering requires the §4 gates, instrument selection, the entry-snapshot spec and the catalyst schema — all in `RULEBOOK.md`. **Read it before any entry.** Managing and exiting an existing position is fully covered here.

**Also read `RULEBOOK.md` in full when:** entering · reporting at 4:00pm · arming at 8:00pm · a profit-target override fires (§7) · anything unusual, ambiguous, or not covered below. When in doubt, read it.

---
## 1. Step Zero — trigger hygiene (do this FIRST, every checkpoint)

Call `list_triggers`.

1. **DELETE every trigger with `ended_reason='run_once_fired'`.** Spent triggers show a stale `next_run_at` pointing at tomorrow's same clock time, which makes the list unreadable at a glance. **Observed Aug 10:** 14 spent triggers sat inert with `enabled: false` and did **not** re-fire — so the risk is lower than first assumed, but deletion stays mandatory, because a list you cannot read is a list where a real duplicate hides. **Two checkpoints on one setup can place two orders — a real-money failure, not untidiness.**
2. **DELETE any trigger occupying a slot you are about to arm** — exactly one trigger per time slot.
3. **NEVER delete the trigger you are currently running from** until the next day is successfully armed.
4. After arming, `list_triggers` again, confirm one per slot with no extras, report the count.

---

## 3. Early shutdown — saves usage

**DELETE the remaining checkpoints for today when ALL of these hold:**

- position is **FLAT**, and
- **no resting orders** to manage, and
- **buying power insufficient** for a viable entry (usually because proceeds are unsettled until the next business day).

Those checkpoints can only report "flat, nothing to do." They cannot trade and no headline can change that.

**ALSO:** if flat at 4:00pm with no position — even after a no-trade day — delete 4:30 through 7:30. Nothing to manage, and new positions are forbidden after hours.

> ### NEVER delete the 8:00pm arming checkpoint.
> It is the single point of failure. Deleting it stops the entire system silently and permanently.

**If flat but settled buying power is still sufficient, KEEP the checkpoints** — a fresh entry is legitimate, since a settled-cash purchase sold the same day is not a good-faith violation.

---

## 5. Order execution

### RUN THE PREFLIGHT CHECK FIRST — before every entry

```
python3 tools/preflight.py --symbol X --qty N --limit P --stop S \
    --balance B --deposits D --open-positions 0 --resting-orders 0
```

Checks, deterministically, against `limits.json`: the loss streak **computed from `data/trades.csv`** rather than remembered · the 50%-of-deposits floor · one position and one resting order · a stop present and inside the 7% ceiling · affordability · order type · universe membership. Exit 0 = ALLOW, 1 = DENY.

- **Its most valuable job is the circuit breaker.** The streak is derived from the trade log, not recalled — a cold session cannot miscount it, and cannot talk itself into a different number.
- **A DENY means do not place the order.** Overriding one is a policy violation; if you proceed regardless you must say so in as many words, so the transcript records it.
- **Changing a value in `limits.json` is a POLICY CHANGE** and follows the §17 promotion path. Do not edit it to make an order pass.

> **Honest limit: this is a TRIPWIRE, NOT A GATE.** Broker orders go through tools the script cannot intercept, so nothing forces it to run and nothing stops a refusal being ignored. What it buys is that the arithmetic becomes deterministic instead of a judgement, and that **skipping the check or overriding it is visible** rather than invisible. Real enforcement would need the order path to run through code that can refuse — which is not available here. Do not describe this as a hard gate.

### Then

- `review_equity_order` before placing.
- **Marketable limit, never plain market** — price protection.
- **Verify the fill from the order response.** Never report a fill you did not confirm.
- **Place the protective stop immediately after the entry fills.**
- Report slippage against the intended price.

---

## 6. Stops — UP ONLY, NEVER DOWN

- **Never widen for comfort or "room for variance."** If the tape needs more room than the stop allows, **the trade is wrong for this account** — exit rather than move the goalposts. Sizing is fixed at all-in, so "reduce the position" is not an available answer; the answer is to be out.
- The only permitted downward change is **correcting a factual placement error**, and you must say that is what it is.
- Raise on **rules** or on **structure** (below a support that has held across several checks).
- **Not every check.** Each raise is cancel-then-replace, which briefly leaves the position unprotected, and over-tightening invites noise stop-outs on a leveraged instrument. **Do not tighten on a flat print** — the stop migrates up as the position *gains*.
- **Migrate from loss-avoidance to profit-locking as gains accrue.** A stop left far below price on a winner lets it round-trip through breakeven.

### Initial placement — decided BEFORE the entry, not after

- **Default: 5% below the fill.** This is the working number for every trade.
- **Tighten to structure if a level is closer** — just below a support that has actually held. Structure beats the percentage when it is *nearer*, never when it is further.
- **HARD CEILING: 7%. Never wider, for any reason, on any instrument.** If the setup appears to need more than 7% of room, **it is not a setup** — decline it. Do not enter and widen.
- **State the stop price and the percentage at entry**, in the same breath as the entry itself. Placement is not a follow-up decision to be negotiated once the position is open. That was the Aug 10 failure: no number existed to check my judgment against, so it got argued out in chat across three messages while the position was live.
- **Why these numbers:** paired with the +8–12% target, a 5% stop is what produces a winner worth more than a loser. A 3–4% stop sits inside ordinary leveraged-ETF noise and stops out trades that were right; past 7% a single loss cancels a good win.
- Sizing is all-in on one position, so **stop distance is the only risk lever there is.** Treat it accordingly. **This is true only of the sandbox** — see the sandbox-only risk block in §0, which requires this line to be deleted rather than reinterpreted once the account holds meaningful money.

### The ratchet ladder — schedule is the floor, structure may be tighter

| Gain reached | Stop moves to | Trail from price |
|---|---|---|
| Entry | **−5%** (ceiling −7%) | 5% |
| **+2% and stalled 2 checks** | **breakeven** | ~2% |
| +3% | **breakeven** | 3% |
| +5% | +2% | ~3% |
| +8% | +4% | ~4% |
| +10% | +6% | ~4% |
| +12% or more | half the gain | ~5% |

- **Structural override, UPWARD ONLY.** If a 10-minute swing low that has held sits *above* the scheduled level, use that instead. Structure may tighten the stop; it may never loosen it.
- **When to move it:** only when a schedule threshold is newly crossed, or a new higher swing low has formed and held across two checkpoints. **Not on every check** — each raise is cancel-then-replace and briefly leaves the position unprotected.
- **Never on a flat print.** The stop migrates up as the position *gains*.
- **Once past +3%, the stop never sits below breakeven again.** A trade that has been meaningfully green does not become a loss.
- **Consequence worth stating:** a ~2–4% trail on a leveraged ETF is under an hour of typical range, so **expect noise stop-outs and expect scratches at breakeven.** That is the accepted cost of a bounded downside. The ladder is a starting hypothesis on one trade of data — month-end win rate and the winner/loser ratio are what will show whether the trail is too tight.

### Hard limits of a stop

- **Stop orders are REGULAR-HOURS ONLY.** Extended hours and overnight **cannot** be automatically protected — a sell limit below market fills instantly at the bid, so it cannot fake a stop.
- **A stop does NOT protect against a gap.** It bounds slippage in an orderly decline only.
- **The only real defence for an overnight event is not holding into it.**
- **The user has been told this and accepts it** — *"the overnight stuff I'm not too worried about."* A 1–2 day default horizon means routinely holding unprotected overnight, and that is a known, accepted cost, not an oversight. **Do not re-litigate it at checkpoints or re-warn about it as though it were news.** State it only when a specific, identifiable overnight event is approaching — that is a trade decision (§8.5), not a structural complaint.

---

## 8. Exit criteria — any one fires

1. **Momentum stalled — a two-step escalation, NOT a single judgment call.**

   **THE STALL CLOCK RUNS ON MARKET TIME, NOT ON CHECKPOINTS.** A stall is measured in **30-minute windows of market time**, built from 5-minute bars. Waking more often does not advance it; waking less often does not slow it. This matters because the wake cadence is variable (§2) — if a stall counted *checks*, then checking every 10 minutes would fire the exit after 30 minutes instead of 90, silently turning it into a different rule.

   **A stalled window** = a 30-minute window of market time in which the high failed to exceed the running high by more than **0.3%**, *and* volume was below the prior window's. Marginal ticks of +0.05% are not progress; they are a stall pretending otherwise.

   | Stalled windows | Elapsed | Action |
   |---|---|---|
   | **2** | 60 min | **Raise the stop to breakeven. Keep holding.** Downside eliminated; upside still open. |
   | **3** | 90 min | **SELL — whatever the gain.** No floor, no minimum, no exception. |

   **Windows are anchored to the clock** (`:00` and `:30`), not to the entry time, so two sessions looking at the same position count identically. A partial window in progress does not count until it completes.

   - **There is NO profit floor on the stall exit.** The earlier +5% floor is retired; this ladder replaces it. A three-check stall sells at +1% or +9% alike.
   - **CORRECTED 2026-08-11 — the earlier justification here was false.** It read: "by the time the sell fires the stop is already at breakeven, so the rule can only ever cost upside, never a loss." **That is only true of a position that first reached +2% or +3%** and so triggered the ratchet. A position that goes down from entry and stalls has **no breakeven stop**, and the three-window sell closes it at a loss. Replay of GUSH 2026-08-05 exits at **−2.91%**.
   - **The rule is still right, for a different reason.** In that same session the −5% stop would have been hit — GUSH closed −5.5% from the entry. The stall exit took **−0.58R instead of −1.0R.** So on a position that never goes green, the ladder is a **loss limiter**, cutting before the stop rather than protecting a gain.
   - **Two distinct jobs, then:** above +2–3% the ladder banks a gain the ratchet has already protected. Below entry it cuts a dead trade early. Do not justify it with the protected-gain argument when the position is red — that argument does not apply there.
   - **A stall of 2 converts the signal from "sell" into "protect."** The information is not discarded; it is redirected.
   - **MIDDAY EXCLUSION: checks between 12:00 and 1:30pm ET do not count toward the stall total.** Volume structurally dies over lunch every day, so counting that window would sell nearly every position held through it for reasons that carry no information. Positions may still be *protected* (stop raised) during it — they are not *sold* on it.
   - **Why unconditional:** a stalled leveraged position is **negative expectancy, not neutral.** Daily rebalancing decay plus spread means time in a non-moving 2x/3x costs money. Waiting is not free.
   - **HOW A COLD CHECKPOINT COUNTS STALLS.** The count is per-position state and **nothing remembers it** — each checkpoint is a fresh session with no recollection of the last one. It must therefore be **DERIVED, every time, from price history**, not recalled:
     - Pull **5-minute bars** from entry to now (`get_equity_historicals`) and aggregate them into clock-anchored 30-minute windows. Collect at the finer resolution and aggregate up; do not request 30-minute bars directly, so the window length stays a free parameter rather than a property of the data (§2).
     - Walk the windows forward tracking the running high. A window is **stalled** if its high failed to exceed the running high by more than 0.3% **and** its volume was below the prior window's.
     - **Skip windows in the 12:00–1:30pm exclusion window** — not counted either way.
     - The stall total is the number of **consecutive** stalled windows ending at the last *completed* one. Any window making a qualifying new high resets it to zero.
     - **State the derived count, the windows it came from, and their highs, in every report while holding.** Deriving it silently makes the most consequential number in the system unauditable, and a wrong count either sells a good position or holds a dead one.
   - **LOG EVERY STALL-2 EVENT**, in `data/observations.jsonl` (§16): the gain at the time, and whether the position subsequently made a qualifying new high before the third stalled **window** closed. Over enough trades this yields the **resumption rate**, which is the only thing that can settle whether the sell belongs at 3 windows or 4 (EXP-001) — break-even is roughly a 33% resumption rate, and the answer is currently a prior, not a measurement.
   - This log is **in-trade data**, recorded while the position is still open. It does **not** require tracking price after an exit and creates no exception to §9.
2. **Reversal** — broke the level/VWAP that justified entry, or the sector rolled over. An exit at any profit level, taking precedence over everything except the stop and a headline trigger.
   - **The ratcheting stop now covers most of this automatically** during regular hours: a stop sitting under the structure removes the need to judge a reversal at all, and it fires *between* checkpoints where I am blind. Reversal as a manual criterion matters chiefly for **extended hours and overnight**, where no stop can rest, and for **headline reversals that gap through any stop.**
   - **The level must have been NAMED AT ENTRY.** "It broke the level that justified entry" is unfalsifiable unless the level and its price were stated before the trade. No named level, no reversal claim.
3. **Risk/reward flipped** — small remaining upside against a large distance to the stop.
4. **Day trade nearing the 7:30pm deadline** with the move finished.
5. **Unwanted event approaching** — earnings or macro data you did not intend to hold through.

**Not** on one red candle, midday noise, or impatience.

### Pre-commit rule — every checkpoint while holding

At the **end** of every report with an open position, state the **specific, falsifiable condition** that would make you exit at the next checkpoint. Name the instruments and the direction.

**Then honour it.** If the condition is met, exit — even if green, even if it feels early. To override you **must** say you are overriding a pre-commitment and name the specific **new** information. *"It looks like it's turning back up" is not new information.*

> A stop is for when you are **wrong**. A voluntary exit is for when the **thesis stops working**. Do not conflate them — waiting for the stop after the thesis has died gives back profit for no reason.

> **Lesson, Aug 10:** the pre-committed condition (XOP flat/negative *while XLE and OIH advance*) did not fire — XLE fell too, so there was no relative weakness. The exit was right on other criteria, but the stated trigger was the wrong one. **Target the driver** (e.g. "if crude rolls further off its high"), not relative sub-sector strength.

---

## 11. Headline check — every checkpoint

- **Flat:** scan major market headlines broadly.
- **Holding:** scan **only** position-relevant headlines.

On a geopolitical trade the thesis dies by headline, not by chart. A ceasefire or reopening can move oil 5–10% in minutes, faster than any price-based criterion will show it.

**Every catalyst identified gets a structured `catalyst` record (§16), traded or not.** "Nameable catalyst" is the guardrail; the record is what eventually makes it measurable. A fired kill trigger gets a `kill_trigger_fired` record.

### Live context — DATED, refresh it, do not carry stale facts forward

**Whose job that is:** the **9:00am research checkpoint** re-verifies this block against current headlines and **edits this file** if any of it has changed or gone stale — then commits and pushes. The **8:00pm checkpoint** is the backstop: if the date stamp below is more than a few days old, refresh it or delete it. **Stale context asserted confidently is worse than no context** — an exit trigger below that has already happened is a trigger that will never fire.

This block holds **whatever the dominant macro driver currently is** — it is a slot, not a permanent fixture. When the driver below stops mattering, **replace it wholesale** rather than appending to it. Its exit triggers are specific to the driver named and must be rewritten with it.

*As of Aug 10 2026 the driver is:* the **2026 Strait of Hormuz crisis** — an active closure amid a US-Israel-Iran war (Iran blocked the strait Feb 28 2026). Iran demands sanctions relief **and** war reparations, and has ruled out direct US talks. The Iran–**Oman** proposed-route deal (~Aug 5–7, joint statement "in final drafting") is with **Oman, not the US**; crossings **fell** afterward (15 Fri → 11 Sat → 6 Sun), so it produced no flow. WTI ~$80, Brent >$84. Reopening-optimism headlines exist ("deal as early as Wednesday") but are stale/undated — weigh price action.

**Immediate exit triggers, regardless of price:** ceasefire · joint statement signed · reopening implemented · sanctions relief · direct US-Iran talks resuming · **crossing counts turning up**.

---

---

## Logging — every checkpoint, before you finish

Append to `data/observations.jsonl`. **Append-only: never edit or delete a past row.** A mistake gets a correcting row and a note.

**While holding — one `checkpoint` record:**

| Field | |
|---|---|
| `type` | `"checkpoint"` |
| `ts` | UTC |
| `instrument`, `price`, `unrealised_pct` | |
| `stall_count` | the derived count (§8.1) |
| `stall_windows` | the windows it came from, **with their highs** — so the count is auditable, not asserted |
| `stop_price` | current |
| `stop_moved`, `stop_move_reason` | `false` is a normal and common answer |
| `headlines_checked` | position-relevant only while holding (§11) |
| `precommit` | the falsifiable exit condition for the next checkpoint (§8) |
| `cadence_min` | the interval in force (§2) |

**While flat — one `declined` record** for any candidate considered and passed on: instrument, the gate that failed, price at the time. Nothing to log if nothing was considered.

**At exit — also append a row to `data/trades.csv`.** 28 columns; the schema and the R-multiple formula are in `RULEBOOK.md` §16 and §14. **Compute `r_multiple` now, while the entry stop is still known.**

**When a §11 kill trigger fires** — a `kill_trigger_fired` record: which trigger, price, action taken.

**Commit and push** anything written.

> **Do NOT log what a price did after an exit, and do not look.** That is Saturday's job (§9). The same applies to a candidate you declined — do not check how it performed after you passed.
