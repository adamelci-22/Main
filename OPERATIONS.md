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

### ⚠ A LONG TURN CAN SWALLOW A CHECKPOINT — verified 2026-08-11

**A trigger cannot deliver into a session that is already generating a turn.** The 9:30am checkpoint on 2026-08-11 did not fire: at 13:30:00Z the session was mid-turn running a universe-wide instrument scan, and the trigger was still sitting `enabled=True` with `ended_reason=None` and `next_run_at` six minutes in the past. The user had to prompt it manually. The 9:00am trigger in the same chain shows `ended_reason='run_once_fired'`, so the chain itself was intact — the slot was simply occupied.

**Why this is the most dangerous defect in the system:** the same mechanism applied to the 8:00pm arming checkpoint stops everything, silently and permanently. A long turn spanning that slot has the identical effect to deleting it, which §3 names as the single point of failure.

**Mitigations, in force:**

- **A BACKUP ARMING TRIGGER is armed 20 minutes after every 8:00pm slot.** It runs Step Zero, does nothing if the day is already armed, and runs the full arming pass if it is not. Each arming checkpoint re-arms the next evening's backup. **Never delete the backup without confirming the primary fired.**
- **Do not start work that will outlast the current slot.** Near a checkpoint boundary, finish and reply — then continue at the next checkpoint. A scan that spans two slots costs a checkpoint, and the missed checkpoint is invisible unless someone notices.
- **A past-due trigger still `enabled` with `ended_reason=None` means a MISSED checkpoint, not a pending one.** Check for this at every Step Zero. If found: do that checkpoint's work now, note in the report that it was missed and why, then delete the stale trigger so it cannot fire mid-turn later.
- **Never silently absorb a missed checkpoint.** Say which one was missed and what the cause was. A checkpoint that vanishes without a trace is how a broken schedule looks exactly like a quiet day.

---

## 3. Early shutdown — saves usage

> ### ⚠ OUT OF PURCHASING POWER = THE DAY IS DONE. Shut it down.
> **Governor decision 2026-08-11.** When settled buying power can no longer fund an entry, there is no decision left to make. Every remaining checkpoint can only report "flat, nothing to do" — it cannot trade, and **no headline, no setup and no amount of watching can change that**, because T+1 means today's proceeds are not spendable until tomorrow.
>
> **This is a stop-work rule, not a suggestion.** Delete the remaining intraday checkpoints the moment it is true. Continuing to wake and look is pure cost with a guaranteed null result, and it invites the worst failure available — talking yourself into an entry you cannot fund, or one funded by unsettled proceeds, which is how a good-faith violation happens (§10).
>
> **Keep exactly three things:** the **4:00pm session report**, the **8:00pm arming checkpoint**, and its **8:20pm backup**. Never the intraday slots.
>
> **Applied 2026-08-11:** flat after the NVDX exit with ~$0.24 settled against $61.60 unsettled. Seventeen checkpoints deleted, 11:00am–3:30pm and 4:30–7:30pm.

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

### Initial placement — VOLATILITY-SCALED, decided BEFORE the entry

**The stop is scaled to the instrument, not fixed.** Read `data/vol_profile.csv`, refreshed at the 9:00am checkpoint (§2e).

```
stop        = clamp(1.5 x median adverse excursion, 2.5%, 7.0%)
target      = clamp(2.0 x median FAVOURABLE excursion, 1.5 x stop, 12.0%)
breakeven   = max(median favourable excursion, 0.5 x stop)
trail       = 1.0 x median adverse excursion, below the running high
stall thr   = clamp(0.15 x median favourable excursion, 0.10%, 1.00%)
min stop mv = clamp(0.25 x median adverse excursion, 0.20%, 1.00%)
```

**EVERY ONE OF THESE IS NOW SCALED. The flat +8% target, the flat 0.3% stall threshold and the flat 0.5% minimum stop move were retired 2026-08-11** — they were the last constants in a volatility-scaled system, and each was wrong at both ends of the universe.

**Why this replaced a flat 5%.** Median adverse excursion across the leveraged universe spans **0.9% (YINN) to 6.6% (SOXL)** — sevenfold. A single number is four times too tight on one end and twice too loose on the other. Worse, stop quality and target reachability are **inverse**: every instrument where +8% was reachable is one where a 5% stop was hit constantly, and every instrument with a comfortable stop never reached +8%. The fixed pair was wrong on all fourteen (EXP-007, EXP-008).

**Current values** — *illustrative only; `vol_profile.csv` is authoritative and is recomputed every morning.*

| | stop | target | R at target | breakeven | trail | stall thr | min move |
|---|---|---|---|---|---|---|---|
| AGQ | 2.50% | 3.75% | 1.50 | 1.76% | 1.45% | 0.26% | 0.36% |
| YANG | 2.54% | 3.80% | 1.50 | 1.27% | 1.69% | 0.14% | 0.42% |
| GUSH | 2.59% | 4.39% | 1.69 | 2.20% | 1.73% | 0.33% | 0.43% |
| NVDX | 4.99% | 7.49% | 1.50 | 2.70% | 3.33% | 0.40% | 0.83% |
| MSTX | 5.81% | 10.93% | 1.88 | 5.47% | 3.88% | 0.82% | 0.97% |
| SOXS | 6.15% | 12.00% | 1.95 | 6.29% | 4.10% | 0.94% | 1.00% |
| SOXL | 7.00% | 10.50% | 1.50 | 4.16% | 6.98% | 0.62% | 1.00% |

- **NOTHING IS EXCLUDED on volatility.** Any leveraged instrument may be traded if it meets the §4 entry gates. Where `1.5 × median MAE` exceeds the cap the stop is simply **capped at 7%** and flagged `stop_at_cap=yes` — SOXL is the current case, its 6.6% median adverse being wider than its own 7% stop. That is a **warning to weigh at entry, not a disqualification**: expect frequent noise stop-outs there.
- **If an instrument is not in `vol_profile.csv`, you may not trade it.** Compute its profile first or pick something else. No falling back to a flat default.
- **HARD CEILING 7%, unchanged.** A setup needing more room is not a setup — decline it.
- **Tighten to structure if a level is nearer.** Structure beats the scaled number when it is *closer*, never when it is further.
- **State the stop price, the percentage, and the target at entry**, in the same breath as the entry. That was the Aug 10 failure: no number existed to check judgment against, so it got argued out in chat while the position was live.
- Sizing is all-in, so **stop distance is the only risk lever there is** — **true only of the sandbox** (§0, which requires this line deleted rather than reinterpreted once the account holds real money).

> **Honest note on what this buys.** Replaying it changed expectancy by about **+0.01R — noise** (EXP-009). This is a **risk-consistency fix, not a return fix.** Its value is that R finally means the same thing across instruments, which is what makes the expectancy metric in §14 meaningful at all. Do not expect it to make money.

### The ratchet — one trigger, then a trail

**Governor decision 2026-08-11 — a STEPPED RAMP to breakeven, then a trail. The ramp is new.**

| Stage | Stop goes to |
|---|---|
| At entry | `−stop_pct` from the profile |
| **Gain reaches `breakeven_trigger ÷ 2`** | **`−stop_pct ÷ 2`** — halve the risk. **This step is new** |
| **Gain reaches `breakeven_trigger`** | **breakeven** (the fill price) |
| Past that | **trail at `trail_pct` below the running high** |
| **2 stalled checks, in profit** | **`max(current stop, breakeven)`** — never lowered |
| **2 stalled checks, below the fill** | **SELL** (§8.1) — the ladder is asymmetric |
| **3 stalled checks** | **SELL** (§8.1) |
| **Any check AT OR ABOVE `target_pct`** | **SELL** — the target, now per-instrument |

**Why the half-risk step matters.** Before it, the stop sat at its *full* initial distance until breakeven was reached — so a position could show a real gain, give all of it back, and then keep going to a full stop-out having never once had its risk reduced. The governor's ladder (`−5% → +1% gain → −3% → +2% gain → 0 → then gain − 2`) fixes exactly that, and it is right: **risk should come off the table in proportion to gain, not in one jump at the end.**

**Worked example, NVDX profile** (stop 4.99%, breakeven trigger +2.70%, trail 3.33%):

| Gain | Stop |
|---|---|
| entry | −4.99% |
| **+1.35%** | **−2.50%** ← half the risk gone |
| +2.70% | 0.00% |
| +4.37% | +1.04% |
| +6.03% | +2.70% |

> **One deliberate departure from the governor's spec, flagged rather than silently applied.** The spec implied a trail of 2pp against a 5% stop — a **0.4 × stop** trail. This keeps **1.0 × median adverse excursion (≈0.67 × stop)**, because trailing *inside* one normal pullback converts winners into scratches: the stop would sit closer than the instrument's ordinary wiggle and get hit on noise rather than on reversal. **Say the word and it tightens to 0.4 × stop** — it locks in more per winner and cuts more winners short, and that trade-off is the governor's to price, not mine.

- **The trigger is per-instrument**, from `vol_profile.csv`: GUSH +2.1%, ERX +1.2%, NUGT +2.7%, MSTX +6.2%. It is `max(median favourable excursion, 0.5 × stop)`.
- **Why the trigger is not a flat number.** It floors at half the stop because moving the stop to breakeven at a gain *smaller* than normal retracement just scratches the position on noise — the newly tightened stop would sit inside the instrument's own wiggle. Half the stop distance is the smallest gain at which a breakeven stop is not itself inside the noise.
- **At 2 stalls the stop goes to breakeven ONLY IF that is higher than where it already sits.** If the trail has carried it above breakeven, it stays. The stop never moves down (§6).
- **The trail replaces the old rung schedule.** Rungs at +5/+8/+10/+12 were dead code — +8% occurred in zero of 21 sessions for GUSH, ERX, NUGT, NRGU, DUST and YINN.
- **Minimum move 0.5%.** Do not re-place the stop for less — every move is a cancel-then-replace that briefly leaves the position unprotected.
- **Structural override, UPWARD ONLY.** A swing low that has held above the trailed level may be used instead.
- **Never on a flat print.** The stop migrates up as the position *gains*.
- **Expect scratches.** A trail one median-adverse-excursion wide is by construction hit by an ordinary adverse move. That is the accepted price of a bounded downside — and the ladder also cuts losers near **−0.6R rather than −1.0R** (EXP-010).

### Hard limits of a stop

- **Stop orders are REGULAR-HOURS ONLY.** Extended hours and overnight **cannot** be automatically protected — a sell limit below market fills instantly at the bid, so it cannot fake a stop.
- **A stop does NOT protect against a gap.** It bounds slippage in an orderly decline only.
- **The only real defence for an overnight event is not holding into it.**
- **The user has been told this and accepts it** — *"the overnight stuff I'm not too worried about."* A 1–2 day default horizon means routinely holding unprotected overnight, and that is a known, accepted cost, not an oversight. **Do not re-litigate it at checkpoints or re-warn about it as though it were news.** State it only when a specific, identifiable overnight event is approaching — that is a trade decision (§8.5), not a structural complaint.

---

## 8. Exit criteria — any one fires

1. **Momentum stalled — a two-step escalation, NOT a single judgment call.**

   **THE STALL IS MEASURED AT THE CHECKPOINT PRICE ONLY. What happens between checks is ignored.** Governor decision 2026-08-11, replacing intra-window highs from bars.

   **A stalled check** = a 30-minute checkpoint whose **price at that moment** failed to exceed the running high by more than **0.3%**. Marginal ticks of +0.05% are not progress; they are a stall pretending otherwise.

   - **`run_high` is the highest CHECKPOINT price seen, not the highest price traded.** It starts at the fill price and advances only when a check prints above the threshold.
   - **A spike between checks is not progress.** If price ran +2% at 10:12 and was back to flat by the 10:30 check, that is a **stall**. The agent exists only at checkpoints — a high it never saw and could never have sold into is not a gain it could have captured. Counting it as progress credited the position with something unreachable.
   - **This makes the stall consistent with the rest of the exit model.** `tools/replay.py` already treats the target, the ratchet and the ladder as checkpoint-evaluated, and only the resting stop as continuous. Using intra-window highs for the stall was the one place that assumed the agent could see between its own checks.
   - **THE VOLUME CONDITION IS REMOVED.** A stall used to require *both* no new high *and* declining volume. Volume has no instantaneous value — it only exists over an interval — so "checkpoint price only" cannot accommodate it. **Effect: stalls now fire strictly more often**, because a non-progressing check with rising volume used to be exempt and no longer is. Three flat-or-down checks in a row now sell, full stop.
   - **No bars are needed for the stall.** One quote per checkpoint is sufficient, which is why this also removes the bar pull from the hot path.

   > **⚠ THIS RULE IS NOW COUPLED TO THE 30-MINUTE CADENCE.** The previous market-time definition was deliberately cadence-independent, precisely so that changing the wake schedule could not silently change the exit rule. Counting *checks* re-introduces that coupling: **at a 10-minute cadence, three stalls would fire after 30 minutes instead of 90 — a completely different rule wearing the same words.** This is safe only because §2 pins the cadence at 30 minutes flat or holding. **If the cadence is ever changed, the stall threshold must be re-derived in the same breath, or the exit rule changes without anyone deciding to change it.**

   | Stalled windows | Elapsed | Action |
   |---|---|---|
   | **2** | 60 min | **Raise the stop to breakeven. Keep holding.** Downside eliminated; upside still open. |

   > ### ⚠ AT 2 STALLS, IF PRICE IS BELOW BREAKEVEN — **SELL.** Do not wait for the third.
   >
   > **Governor decision 2026-08-11. The ladder is deliberately ASYMMETRIC: two stalled checks for a loser, three for a winner.**
   >
   > | At stall 2 | Price vs the fill | Action |
   > |---|---|---|
   > | | **at or above** breakeven | raise the stop to `max(current stop, breakeven)` and keep holding — three checks still apply |
   > | | **below** breakeven | **SELL immediately, at the market, at whatever the loss is** |
   >
   > **Why the asymmetry is right and not just harsher.** The stall-2 breakeven step was written to protect a gain. A position that is *underwater* and has failed to make a new high twice running has no gain to protect — the rule had nothing to act on, so the position was drifting on the initial stop alone with no thesis left supporting it. Giving a losing, stalling position a third check spends 30 more minutes of exposure to buy information the first two checks already delivered.
   >
   > **It also resolves an unexecutable instruction.** Breakeven sits *above* the market when the position is losing, and **a sell stop above the market is rejected by the broker** — it is not a stop, it is a market order wearing a stop's name. Selling removes the need to place an order that cannot exist. **Never place, or attempt to place, a stop above the market price.**
   >
   > **Sell means sell now**, not at the next checkpoint. The condition is met the moment the second stalled check is counted. Cancel the resting stop first — a pending sell locks the share (§10) — then exit with a marketable limit.
   >
   > **First application:** NVDX, 2026-08-11. Stalled at the 10:00 and 10:30 checks against a 19.8677 threshold, price 19.76 against a 19.8083 fill. Sold at 19.6901 for −0.60%, −0.12R. Under the previous rule it would have held to the 11:00 check.
   | **3** | 90 min | **SELL — whatever the gain.** No floor, no minimum, no exception. |

   **Windows are anchored to the clock** (`:00` and `:30`), not to the entry time, so two sessions looking at the same position count identically. A partial window in progress does not count until it completes.

   - **There is NO profit floor on the stall exit.** The earlier +5% floor is retired; this ladder replaces it. A three-check stall sells at +1% or +9% alike.
   - **CORRECTED 2026-08-11 — the earlier justification here was false.** It read: "by the time the sell fires the stop is already at breakeven, so the rule can only ever cost upside, never a loss." **That is only true of a position that first reached +2% or +3%** and so triggered the ratchet. A position that goes down from entry and stalls has **no breakeven stop**, and the three-window sell closes it at a loss. Replay of GUSH 2026-08-05 exits at **−2.91%**.
   - **The rule is still right, for a different reason.** In that same session the −5% stop would have been hit — GUSH closed −5.5% from the entry. The stall exit took **−0.58R instead of −1.0R.** So on a position that never goes green, the ladder is a **loss limiter**, cutting before the stop rather than protecting a gain.
   - **Two distinct jobs, then:** above +2–3% the ladder banks a gain the ratchet has already protected. Below entry it cuts a dead trade early. Do not justify it with the protected-gain argument when the position is red — that argument does not apply there.
   - **A stall of 2 converts the signal from "sell" into "protect."** The information is not discarded; it is redirected.
   - **NO MIDDAY EXCLUSION. Every window counts normally, all session.** Governor decision 2026-08-11 — earlier versions skipped or half-counted 12:00–1:30pm ET and that is removed. Lunch windows increment the stall count, reset it on a qualifying new high, and enter the volume comparison chain exactly like any other window.
     - **Consequence, accepted:** volume genuinely does die over lunch, so a position held through midday is now more likely to accumulate stalls and be sold there. That is the intended behaviour — a position going nowhere on low volume is still a position going nowhere.
   - **Why unconditional:** a stalled leveraged position is **negative expectancy, not neutral.** Daily rebalancing decay plus spread means time in a non-moving 2x/3x costs money. Waiting is not free.
   - **HOW A COLD CHECKPOINT COUNTS STALLS.** The count is per-position state and **nothing remembers it** — each checkpoint is a fresh session with no recollection of the last one. It must therefore be **DERIVED, every time, from price history**, not recalled:
     - Read **one quote** — the price at this checkpoint. No bars. The stall is a comparison between checkpoint prices, so intra-checkpoint data cannot enter it (governor decision 2026-08-11).
     - Compare that price against `run_high`, the highest **checkpoint** price so far, seeded at the fill. If `price > run_high x 1.003`, the check **progressed**: reset the stall count to zero and advance `run_high` to this price. Otherwise it is a **stalled check** and the count increments.
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

- **FLAT — read the PREVIOUS DAY's headlines.** What happened yesterday and overnight is what forms today's setups. That is the material a shortlist is built from.
- **HOLDING — read the SAME DAY's headlines.** Once capital is committed, only live news matters: what could invalidate the thesis right now. Yesterday's news is already in the price.
- The split is deliberate. Looking for a setup and defending a position are different jobs needing different information.

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
| `stall_checks` | every checkpoint price since entry with its threshold and verdict — so the count is auditable, not asserted |
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
