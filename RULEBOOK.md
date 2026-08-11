# Agentic Trading Rulebook

**Canonical source of truth.** Every scheduled checkpoint reads this file and follows it. Nothing is copied forward between checkpoints — this document is the single authority, so it cannot degrade through recopying. Edit here to change behaviour everywhere, immediately.

**Account:** Robinhood `462514035` ("Agentic"), cash account, `agentic_allowed=true`, `option_level_2` — *the option level is descriptive only; options are not permitted here (§4).*

---

## 0. Objective

Grow the account as fast as possible in a "nothing to lose" mindset, using **leverage** plus **day trading and swing trading**, while **locking in profits**.

- **There is NO dollar target.** Never reference or plan around one. A fixed target creates path-dependent incentives — under-risking near it, chasing when behind — that corrupt decisions which should only be about whether the trade in front of you is good.
- **AGGRESSION belongs to the ENTRY**: leveraged 2x/3x instruments, full position, concentrated, no diversification requirement, long or inverse. Swing hard.
- **DISCIPLINE belongs to the EXIT**: stops that only ratchet up, a defined profit target, a short horizon. Cut fast.
- **"Nothing to lose" NEVER licenses aggression in the exit.** Holding through a stop hoping for more is the single behaviour that destroys accounts.
- **"Constant profit" is impossible.** Losing trades are structural, not failures. The goal is a consistent process with positive expectancy, which includes red days.

### DESIGN FOR SCALE — the current balance is not the frame

**This system is being trained to run at much larger sums. Judge every rule as though the account were 10x its current size or more.**

- **A +2% win is significant.** Do not dismiss small percentage gains as immaterial because the dollar figure is small today. At scale, a high win rate banking +2% with the downside capped at breakeven is an excellent system, and it is the thing being built.
- **Never reason from the dollar balance to a change in strategy.** "This won't compound meaningfully at $42, so reach for the fat tail" is invalid — it optimises for an account size that is meant to be temporary and trains variance-seeking that would be actively harmful at scale.
- **Every threshold is a PERCENTAGE, never a dollar amount.** Percentages transfer across account sizes; dollars do not. The hard floor is a percentage of **deposited capital** (§10) for exactly this reason. The only place dollar figures legitimately appear is where a mechanical constraint forces it — instrument affordability, and the recorded deposit total itself.
- **Rules currently dormant that activate with size**, and which must not be quietly dropped for being unused today: partial sells in the override case (§7, needs 2+ shares), and most of the leveraged universe (§4, unaffordable as whole shares at present).
- Prefer the choice that would still be correct at 10x. Where the small-account answer and the at-scale answer differ, **say so explicitly** rather than silently optimising for today.

---

## 1. Step Zero — trigger hygiene (do this FIRST, every checkpoint)

Call `list_triggers`.

1. **DELETE every trigger with `ended_reason='run_once_fired'`.** Spent triggers show a stale `next_run_at` pointing at tomorrow's same clock time, which makes the list unreadable at a glance. **Observed Aug 10:** 14 spent triggers sat inert with `enabled: false` and did **not** re-fire — so the risk is lower than first assumed, but deletion stays mandatory, because a list you cannot read is a list where a real duplicate hides. **Two checkpoints on one setup can place two orders — a real-money failure, not untidiness.**
2. **DELETE any trigger occupying a slot you are about to arm** — exactly one trigger per time slot.
3. **NEVER delete the trigger you are currently running from** until the next day is successfully armed.
4. After arming, `list_triggers` again, confirm one per slot with no extras, report the count.

---

## 2. The daily grid — 24 checkpoints (ET)

A three-stage morning funnel, then management, then close.

| Time | Role | Orders |
|---|---|---|
| **9:00am** | **Pre-market research** | ❌ read-only |
| **9:30am** | Opening observation | ❌ read-only |
| **9:45am** | **TRADING OPENS** — first entry | ✅ |
| 10:00 → 3:30 | 12 standard checkpoints, every 30 min | ✅ |
| 4:00pm | Close of regular hours, session report | ✅ until the bell |
| 4:30 → 7:00 | 6 extended-hours checkpoints | ⚠️ limit only, **no new positions** |
| **7:30pm** | **LAST ACTIONABLE CLOSE** | ⚠️ day trades must close; swings may hold |
| **8:00pm** | Report + arm the next trading day | ❌ admin only |

Convert each ET time to UTC using the offset in effect.

### 9:00am pre-market research — no orders, read-only tools only

Purpose: form a thesis before the bell.

- **(a)** Scan overnight and pre-market **headlines** broadly — macro, geopolitical, anything that moved.
- **(b)** Read **pre-market prices** via `quote.last_non_reg_trade_price` across the universe plus the prior day's watchlist.
- **(c)** Check **earnings reactions** of last night's after-close reporters — their pre-market prints often set the day's leadership.
- **(d)** Rank **sector leadership** as indicated pre-market.
- **(e)** Confirm **settled buying power** (`get_accounts` for `unsettled_funds`, plus `get_portfolio`) so the 9:45 entry knows its size instead of discovering a shortfall mid-setup.
  - **A balance larger than yesterday's close, beyond what trading explains, means the user funded the account.** No announcement is coming and none is needed — the 9:00am check is where you find out. Size to the new balance and say what you observed in the report. Do not ask for or campaign for funds; the user adds them when the system has earned it.
  - **On detecting funding, report the new deposited-capital figure** — the hard floor is a percentage of it (§10). The figure is **derived, never cached** (§16), so recomputing it each morning is what keeps the floor set against the right denominator.
- **(f)** Write a **ranked shortlist** with the reason each candidate beats the others.

### 9:30am opening observation — no orders, read-only only

Test whether the 9:00 thesis survived the open. Did pre-market strength hold into real volume, or fade? Check breadth within the leader. Trending or choppy — chop argues against all leveraged ETFs.

> Aug 10 precedent: SOXL indicated **+1.33%** overnight and opened **−1.29%**. A 9:00 thesis pointing at semis would have been correctly killed at 9:30. That is the funnel working.

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

## 4. Entry — what to look for

### CIRCUIT BREAKER — check before every entry

**After 3 consecutive losing closed trades, STOP ENTERING and wait for the user to clear it.**

- A **losing trade** is any closed position with negative realised P&L, however small. Scratches and near-breakeven exits count as losses if the number is negative. Do not reclassify a loss as "flat" to keep a streak alive.
- The count is **consecutive closed trades**, not days. A winner anywhere in the sequence resets it to zero.
- **What "pause" means:** manage any open position normally to its exit, then take **no new entries**. Keep running every checkpoint, keep reporting, and **keep arming the next day** — pausing entries must never become pausing the system. **The 8:00pm arming checkpoint stays alive no matter what** (§3).
- **Tell the user plainly at the third loss**: the three trades, what each thesis was, and your honest read on whether they were three bad reads or one bad read repeated. Three losses in a row is more diagnostic of a broken process than any single-day percentage, which is why this is the brake and drawdown is only a flag.
- **Only the user restarts entries.** Do not resume on your own judgment, and do not resume because a setup looks good — that instinct is exactly what the brake exists to interrupt.
- Track the streak in the month-to-date line so it is never reconstructed from memory.

**A −25% drawdown from peak is a FLAG, not a brake** — report it loudly with a written review of what broke, and keep trading (§14). The hard floor remains **~$15** (§10), below which sizing stops working.

### Signals

- **Sector leadership, ranked.** Which sector is *actually* leading. Never default to one you have been watching.
- **Breadth.** Is the whole group moving together, or is one name dragging the ETF? Broad beats narrow every time.
- **A catalyst you can name.** Geopolitical event, earnings, macro data. "It's going up" is not a catalyst.
- **Trend vs chop.** Leveraged ETFs decay in chop; multi-day holds need a real trend.
- **Continuation, not prediction.** Go with an established move. Do not call tops or bottoms.
- **Did overnight strength hold into real volume?**
- **No read = no trade.** A flat day is a valid and expected outcome.

### Timing — prefer the morning, never force

- **Preferred window: 9:45–11:00am.** Volume and directional conviction are highest, and it leaves the whole session to manage the position rather than defending it into the close.
- **After 11:00am, a new entry must be clearly better than anything the morning offered** — not merely available because the morning was empty. Boredom is not a signal.
- **NEVER force a trade because the window is closing.** User decision, explicit: *"prefer morning but if there's nothing don't force anything."* A day with no qualifying setup ends with no trade, and that is a correct outcome, not a missed one.
- **Only one round trip per day exists** (T+1, §10). That single shot is something to **spend well, not to spend.** An entry taken at 9:45 on a mediocre read forfeits the day's only opportunity.
- **Late-day entries carry an extra cost:** a position opened in the afternoon cannot reach target before the close, so it commits to an unprotected overnight hold on day one. Say so at entry if taking one.

### Instrument selection, in priority order

1. **Whole share is the DEFAULT** — the most leverage per dollar that fits as a whole share. Whole shares preserve the after-hours and 24-hour-market exit and allow limit orders.
2. **Verify `all_day_tradability` before entering.**
3. **Check the spread — no hard rejection gate; PRICE IT IN.** Read the actual bid/ask, double it for the round trip, subtract that from the expected move, and take the trade only if it **still clears the target with room to spare.** A spread does not disqualify an instrument by itself; a spread that eats the thesis does. Liquid leveraged ETFs typically run well under 0.15% and are a non-issue; thin sector and single-stock names are where this bites. **Log the actual spread cost on every fill** so the real drag accumulates in the record instead of being assumed.
4. **Check the actual price before shortlisting.** Much of the universe below is unaffordable as a whole share at a small balance. A candidate you cannot buy is not a candidate — do not build a thesis on one and discover the problem at the order stage.

### Fractional — permitted only when the setup is clearly better

- **Whole share is the default. Fractional is the exception**, allowed when the best available setup is materially stronger than anything affordable whole — not merely different, and not to avoid the work of finding an affordable equivalent.
- **You must say at entry that you are going fractional, and what you are giving up.** State it as a cost being accepted, not a detail.
- **What fractional costs, every time:** `type=market` only, `regular_hours` only. That means **no limit price** (no protection against the spread) and **no extended-hours or overnight exit at all** — a fractional position held overnight cannot be closed until the next regular session, whatever happens in between.
- Because the exit window is narrower, a fractional position gets a **tighter leash**: prefer closing it the same session, and never invoke the 1-week horizon ceiling on one.

### Asset classes — equities and ETFs ONLY, indefinitely

- **Tradeable: common stock and ETFs, including leveraged and inverse ETFs.** That is the whole permitted set.
- **Options are excluded.** This is a settled decision, not an open question and not a milestone to graduate past. Leverage comes from leveraged ETFs, not from contracts.
- **Do not propose options, price a contract, or build a plan that depends on one.** If a setup only works as an option, it is not a setup for this account.
- Reading option data for *information* (`get_option_chains`, unusual activity as a sentiment read) is fine. Placing an option order is not.
- Only the user reopens this.

### Universe — never sector-lock

- **Index leveraged:** TQQQ, SPXL, TNA
- **Sector leveraged:** SOXL (semis), GUSH (E&P), ERX (energy), FNGU / BULZ (mega tech), LABU (biotech), NUGT / GDXU (gold miners), NRGU (3x big oil), YINN (China)
- **Single-stock leveraged:** NVDL, TSLL, CONL, MSTX
- **Inverse (for bearish views):** SQQQ, SOXS, DUST, SPXS, SDOW, TZA, ERY
- **Crypto proxies:** BITX, ETHU, RIOT, MARA
- **Volatility:** UVIX, VXX — **event/intraday ONLY, never a hold** (severe structural decay)
- Any liquid high-beta single name with a catalyst

---

## 5. Order execution

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
- Sizing is all-in on one position, so **stop distance is the only risk lever there is.** Treat it accordingly.

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

## 7. Profit-taking

- Set a **realistic target at entry** — roughly **+8% to +12%** on a 2x sector ETF — separate from any far tail target.
- **The target is a CEILING, and most trades will not reach it.** The three-check stall exit (§8.1) will close the majority of positions first, at whatever gain stands. Target is the exit that requires no judgment; it is **not** a reason to keep holding a position the other criteria have already condemned.
- **On reaching it: BANK IT — close the ENTIRE position**, unless there is **new information** supporting more upside, named explicitly. Momentum alone does not qualify. Neither does reluctance to sell a winner.
- **Never let the stop become the only exit** — that is drift.
- Profit-taking is **manual** at checkpoints, because the stop occupies the one resting-order slot. That is the correct allocation: the downside must work unattended; the upside can wait for a 30-minute check.

### Holding period

- **Default: 1–2 days**, but understand what the stall ladder does to this in practice. **A three-check stall sells the position**, so an overnight hold now happens only when the position is still making new highs into the close. **This is predominantly a day-trading system**, with swing holds as the exception rather than the plan — a deliberate consequence of the §8.1 ladder, accepted because a stalled leveraged position decays and because overnight gaps cannot be protected at all.
- **Absolute ceiling: 1 trading week.** Only for an *exceptional* opportunity, and you must say at entry that you are invoking it and why. "It's still going up" is not exceptional.
- **State the intended maximum hold at entry**, so it is a commitment rather than a running negotiation.
- If the target is not reached and event risk approaches, **exit rather than drift** — the horizon is a ceiling, not a target to fill.

### Target hit = FULL exit. No scaling out at target.

- **Hitting the target closes the WHOLE position**, at any share count. Do not bank half and let a remainder run. Do not keep a "runner." **Multiple shares change the dollar amount, never the decision.**
- The only thing that keeps you in past target is the §7 override: **named new information** supporting more upside. Momentum is not new information. Reluctance to sell a winner is not new information. Neither is "there's still room."
- **If the override does fire and you hold 2+ shares, bank half and hold the rest** rather than holding all of it. Staying in on new information is already permitted; taking half off while doing so is strictly more conservative than the override allows, and it serves "lock in profits." This is the *only* circumstance for a partial sell — see the lifecycle below.
- **Every other exit rule is unchanged and still fires first** — stalled momentum, reversal, flipped risk/reward, the 7:30pm deadline, an approaching event (§8), the ratcheting stop (§6), and the pre-commit rule (§8). Reaching target is not the only way out; it is the way out that requires no further judgment.
- Rationale: a runner reintroduces exactly the drift these rules exist to prevent. It converts a decided exit into an open-ended hold, and on a decaying leveraged instrument the remainder is the part most likely to give the gain back.
### The override lifecycle — what happens after you bank half

Approving the override is not permission to stop deciding. It starts a clock that you re-justify at every single checkpoint.

1. **Sell half AT THE MOMENT the override is approved** — not at the next checkpoint, not once it runs further. The gain is locked when the decision to stay is made, or the whole point is lost.
2. **RAISE THE STOP ON THE REMAINDER TO AT LEAST THE TARGET PRICE.** This is mandatory and immediate. You chose not to sell at target; the remainder must therefore not be allowed to come back *below* target. Anything less means the override can end up worse than simply having obeyed the target, which is unacceptable.
3. **Re-justify the override at EVERY checkpoint, out loud.** Name the new information again and say whether it is still true, still unpriced, and still pointing up. **Silence is not continuation** — an override you did not restate is an override that has expired, and the remainder gets sold.
4. **Sell the remainder the moment ANY of these is true:**
   - the named new information is **exhausted, contradicted, or now priced in**;
   - **any** §8 exit criterion fires — stalled momentum, reversal, flipped risk/reward, the 7:30pm deadline, an approaching event;
   - the ratcheted stop is hit;
   - a **pre-committed condition** fires (§8);
   - the **horizon ceiling** (§7) is reached.
5. **You may NOT override the override.** One extension per trade, full stop. When the remainder's exit condition fires, it is sold — you do not name a second piece of new information and extend again. Serial extension is an infinite hold with extra steps, and it is the single most likely way this rule gets abused.
6. **Log both fills as separate rows** in `data/trades.csv` (§16), with the override reason recorded. The trade's result is the blended P&L of both, reported honestly — if the override earned less than a clean exit at target would have, **say so plainly.** That is the only way to find out whether overrides are worth taking at all, and it is the one legitimate exception to §9's no-post-exit-tracking rule, because it measures a *decision you made*, not tape you didn't act on.

- **UNVERIFIED MECHANIC — only relevant in the override case.** §10's one-resting-order limit was proven with a single share, where a resting stop drove `sharesCanSell` to 0. Whether a stop on *part* of a multi-share position leaves the remainder sellable is **not yet known**. Before any partial sell, confirm with `review_equity_order` that it is accepted while a stop rests on the rest. **If it is not**, the sequence is cancel the stop, sell half, immediately replace the stop on the remainder — done deliberately, since the position is unprotected in between. Do not discover this mid-trade.

---

## 8. Exit criteria — any one fires

1. **Momentum stalled — a two-step escalation, NOT a single judgment call.**

   **Definition of a stalled check:** no new high *and* volume drying up. **A "new high" must exceed the prior high by more than 0.3% to count as progress and reset the counter** — marginal ticks of +0.05% are not progress, they are a stall pretending otherwise.

   | Stalled checks | Action |
   |---|---|
   | **2** | **Raise the stop to breakeven. Keep holding.** Downside eliminated; upside still open. |
   | **3** | **SELL — whatever the gain.** No floor, no minimum, no exception. |

   - **There is NO profit floor on the stall exit.** The earlier +5% floor is retired; this ladder replaces it. A three-check stall sells at +1% or +9% alike.
   - **By the time the sell fires, the stop is already at breakeven**, so the rule can only ever cost upside — never a loss. That is what makes an unconditional sell safe.
   - **A stall of 2 converts the signal from "sell" into "protect."** The information is not discarded; it is redirected.
   - **MIDDAY EXCLUSION: checks between 12:00 and 1:30pm ET do not count toward the stall total.** Volume structurally dies over lunch every day, so counting that window would sell nearly every position held through it for reasons that carry no information. Positions may still be *protected* (stop raised) during it — they are not *sold* on it.
   - **Why unconditional:** a stalled leveraged position is **negative expectancy, not neutral.** Daily rebalancing decay plus spread means time in a non-moving 2x/3x costs money. Waiting is not free.
   - **HOW A COLD CHECKPOINT COUNTS STALLS.** The count is per-position state and **nothing remembers it** — each checkpoint is a fresh session with no recollection of the last one. It must therefore be **DERIVED, every time, from price history**, not recalled:
     - Pull 30-minute bars from entry to now (`get_equity_historicals`).
     - Walk them forward tracking the running high. A bar is a **stalled check** if its high failed to exceed the running high by more than 0.3% **and** its volume was below the prior bar's.
     - **Skip bars in the 12:00–1:30pm exclusion window** — they are not counted either way.
     - The stall total is the number of **consecutive** stalled bars ending at the present. Any bar that made a qualifying new high resets it to zero.
     - **State the derived count and the bars it came from in every report while holding.** Deriving it silently makes the most consequential number in the system unauditable, and a wrong count either sells a good position or holds a dead one.
   - **LOG EVERY STALL-2 EVENT**, in `data/observations.jsonl` (§16): the gain at the time, and whether the position subsequently made a new high before the third stalled check. Over enough trades this yields the **resumption rate**, which is the only thing that can settle whether the sell belongs at 3 checks or 4 — break-even is roughly a 33% resumption rate, and the answer is currently a prior, not a measurement.
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

## 9. Post-exit prices — forbidden to the EXECUTOR, required of the RESEARCHER

**This rule is split by role (§17), because it is an excellent execution rule and a terrible research rule.**

| Role | Post-exit prices |
|---|---|
| **EXECUTOR** (trading hours) | **Never.** Not to log, not in passing, not "just to check." |
| **RESEARCHER** (Saturday) | **Always.** Measuring them is the job. |

**Why the split is safe:** the RESEARCHER collects post-exit data retroactively from historical bars on Saturday, and writes it to `data/observations.jsonl` and `EXPERIMENTS.md` — never to this file. Tomorrow's EXECUTOR is a cold session that remembers nothing of it and is forbidden to read `EXPERIMENTS.md`. **The statelessness enforces the firewall.** The behavioural protection survives intact while the evidence still gets collected.

### The EXECUTOR's rule, in full

Once a position is **closed**, do **not** report, track, or comment on what the price did afterward. Do not compute "would I have been better off holding."

That is **outcome bias** — the quality of an exit is fixed by the information available *at* the decision, not by the next few minutes of tape. It is also actively harmful: logging "it went up after I sold" trains hesitation into future exits and destroys the discipline these rules exist to enforce.

**Green is green. If the system says sell, sell and move on — we are not married to these leveraged plays.**

**ONE carve-out, and it exists ONLY if an override was actually invoked and acted on (§7).**

- **If no override was invoked, the comparison is FORBIDDEN.** Do not perform it, do not mention it, do not think it. A normal exit at target, a stop firing, a stalled-momentum exit, a pre-committed exit, a deadline exit — for every one of these the price afterward is **irrelevant and must not be looked at**. This is the default case and it covers almost every trade.
- **Only when you held past target on named new information** do you then compare the realised result against what a clean exit at target would have returned. That is not outcome bias: the target price was actually reached and observed *at the moment of the decision*, so it is a real alternative you consciously declined — not subsequent tape you had no chance to act on.
- The distinction is **whether you made a choice against a price you had actually seen.** Considering an override and correctly rejecting it does not qualify — you took the target, so the tape afterward is none of your business.
- When it does apply, report it honestly, including when the override lost money relative to obeying the target.

The legitimate version of this check is **aggregate**, and it is already captured by the month-end winner/loser ratio (§14). If exits are systematically premature, that ratio degrades and it will show up there. Single-trade post-exit price action is noise pretending to be feedback.

---

## 10. Account mechanics — verified facts

- **NO SHORT SELLING.** This cash account cannot short. Verified Aug 10: a sell with `sharesOwned=0` is rejected with `EQUITY_MAX_SELL_SHARES_EXCEEDED` (`sharesCanSell: 0`). `short_selling_tradability: tradable` describes the **instrument**, not account eligibility. Do not waste a setup attempting it. **Express bearish views via inverse ETFs bought long.**
- **Inverse caution:** inverse leveraged ETFs decay in chop *and* carry a structural headwind since indices drift up. Day-trade or very short swing only — a faster exit than an equivalent long, never a multi-day hold.
- **Only ONE resting order per position.** A pending sell locks the share (`sharesCanSell: 0`), so a stop and a take-profit cannot coexist.
- **`all_day_tradability='tradable'`** (24 Hour Market, Sun 8pm–Fri 8pm ET, limit orders, `market_hours='all_day_hours'`): GUSH, FNGU, NVDL, BULZ, SQQQ, SOXS, SOXL, TQQQ, TSLL, BITX, RIOT, HAL, ERX, XLE, NRGU, DUST, USO.
- **`all_day` UNTRADABLE:** CONL, OIH. **JDST** fractional is `position_closing_only`.
- **Fractional orders place only in `regular_hours`**, and require `type=market`.
- **24-hour tradability is OPTIONALITY, NOT OBLIGATION.** Never hold just because you can.
- **The SWING label is a plan, not a promise.** Criteria override the label.
- **FLOOR: stop trading and report below 50% of DEPOSITED CASH.**
  - **The denominator is the cash the user put in — NOT the current account value.** Currently $40.84 deposited, so the floor is a **fixed $20.42** until more is deposited. Account value is used only to *derive* the deposit figure; it is never the base of the floor.
  - **The floor does NOT rise with gains.** If the account grows to $80, the floor stays $20.42 — it is a limit on how much of the user's own money may be lost, not a trailing stop on the account. A floor that ratcheted up with profits would liquidate the account on an ordinary drawdown from a high.
  - Expressed as a percentage so it transfers across account sizes (§0). Losing half of contributed capital is where the process stops being given the benefit of the doubt, whatever any single trade looks like.
  - **Deposited capital is not a field — it is DERIVED**, and the formula is confirmed correct: `deposited = total_value − all-time realized P&L − unrealized P&L`. There is no cumulative-deposits field; `pending_deposits` is in-flight money only.
  - **Validated Aug 10 2026:** $42.07 total − $1.23 all-time realized, flat, = **$40.84**, which the user confirmed is exactly the amount deposited. The formula holds and needs no fudge factor.
  - **It stays correct as funding is added**, because a new deposit raises `total_value` without touching realized P&L — the derived figure rises by the deposit, which is the desired behaviour.
  - **Recompute it at the 9:00am check.** It is derived, not cached (§16) — there is no stored figure to trust or to go stale. Report it whenever it changes (§2e).

### Settlement and round trips

Cash account, **T+1**.

- Sale proceeds are **unsettled until the next business day**, so after an exit only previously-settled cash is spendable. **Rotation is not possible same-day** — an exit means going flat and staying flat for the session.
- Buying with **settled** cash and selling the same day is fine and **not** a GFV. A **GFV** is selling something bought with **unsettled** proceeds. **3 GFVs = 90-day restriction.**
- **Cash accounts are exempt from PDT** — no $25k minimum, so daily trading is permitted.

---

## 11. Headline check — every checkpoint

- **Flat:** scan major market headlines broadly.
- **Holding:** scan **only** position-relevant headlines.

On a geopolitical trade the thesis dies by headline, not by chart. A ceasefire or reopening can move oil 5–10% in minutes, faster than any price-based criterion will show it.

### Live context — DATED, refresh it, do not carry stale facts forward

**Whose job that is:** the **9:00am research checkpoint** re-verifies this block against current headlines and **edits this file** if any of it has changed or gone stale — then commits and pushes. The **8:00pm checkpoint** is the backstop: if the date stamp below is more than a few days old, refresh it or delete it. **Stale context asserted confidently is worse than no context** — an exit trigger below that has already happened is a trigger that will never fire.

This block holds **whatever the dominant macro driver currently is** — it is a slot, not a permanent fixture. When the driver below stops mattering, **replace it wholesale** rather than appending to it. Its exit triggers are specific to the driver named and must be rewritten with it.

*As of Aug 10 2026 the driver is:* the **2026 Strait of Hormuz crisis** — an active closure amid a US-Israel-Iran war (Iran blocked the strait Feb 28 2026). Iran demands sanctions relief **and** war reparations, and has ruled out direct US talks. The Iran–**Oman** proposed-route deal (~Aug 5–7, joint statement "in final drafting") is with **Oman, not the US**; crossings **fell** afterward (15 Fri → 11 Sat → 6 Sun), so it produced no flow. WTI ~$80, Brent >$84. Reopening-optimism headlines exist ("deal as early as Wednesday") but are stale/undated — weigh price action.

**Immediate exit triggers, regardless of price:** ceasefire · joint statement signed · reopening implemented · sanctions relief · direct US-Iran talks resuming · **crossing counts turning up**.

---

## 12. Volatility escalation — authorized

If a position becomes **exceptionally volatile**, you may watch it as long as necessary, **including overnight**.

- Arm extra `send_later` checkpoints at **off-grid minutes** (`:10, :20, :40, :50`) at 10–15 minute intervals, so they can never collide with the standing `:00`/`:30` grid.
- Manage via `all_day_hours` limit orders if the instrument is eligible.
- Stand down to the normal cadence once it settles.

This is the one permitted exception to "do not arm anything."

---

## 13. Runs indefinitely

The loop continues **every trading day until the user explicitly pauses or cancels it.** They set that date, not you. Never stop on your own initiative; no week-end or month-end is terminal.

- **Each 8:00pm checkpoint MUST arm the next trading day** — highest priority, ahead of reporting.
- **SKIP US market holidays**; arm the next real trading day. Upcoming: **Labor Day Mon Sep 7 2026**; **Thanksgiving Thu Nov 26 2026** (**Fri Nov 27 early 1:00pm close**); **Christmas Fri Dec 25 2026**. On early closes, end the regular grid at the early close and skip extended-hours checkpoints. **Verify the calendar** rather than assuming.
- **Friday's final checkpoint arms Monday's grid AND the Saturday 10:00am RESEARCHER pass** (§17).
- **Daylight saving:** the ET times in §2 are authoritative. EDT = UTC−4; after **Sun Nov 1 2026** EST = UTC−5, shifting every UTC slot +1 hour. **Recompute UTC from ET** rather than copying.
- **Month-end is a reporting milestone, not a stop:** report the month, then continue arming.
- If you detect the chain was broken (a gap where checkpoints should have fired), **tell the user plainly and re-arm immediately.**

---

## 14. How success is measured — monthly, rolling

A week is ~3–4 trades and is noise. A month is ~12–15 and lets the win/loss ratio mean something. **Even a month is not statistical proof** (that needs 30–100+ trades). **Never claim edge from it.**

### Process tests — highest weight, reported continuously as they occur

1. A clean loss taken without excuse-making
2. A stop executed
3. A correct no-trade day, stated as such
4. A profit-take executed while the trade is still running — **✅ done Aug 10**
5. A whole choppy *stretch* sat out without forcing trades
6. A pre-committed event exit honoured **when it cost potential upside**

### Statistics — each month-end

### The primary metric is EXPECTANCY, in R

**R is the risk accepted at entry** — the initial stop distance in percent, fixed at the moment of entry and never recalculated afterwards. A trade's result in R is:

```
R multiple = (exit% − entry%) ÷ initial stop distance%
```

So a −5% initial stop and a +3.25% exit is **+0.65R**. Being stopped out at the initial stop is **−1.0R**. A scratch at breakeven is **0R**. Using *initial* risk as the denominator is deliberate: it measures return against the risk that was actually accepted, so ratcheting the stop to breakeven correctly shows up as a smaller loss rather than as smaller risk.

```
Expectancy per trade = (win rate × avg winner in R) − (loss rate × avg loser in R)
```

**Positive expectancy is the only thing that matters.** Report it every month. It is the primary figure, ahead of everything below.

### Why neither win rate nor the win/loss ratio can be the headline

An earlier version of this section made **win rate the headline metric** and required an average winner ≥ 1.2× the average loser. **That was wrong, and the arithmetic proves it:**

| Win rate | Avg winner | Expectancy | Verdict |
|---|---|---|---|
| 60% | 0.9R | `0.60×0.9 − 0.40×1.0` = **+0.14R** | **Profitable** — yet fails the old 1.2:1 rule |
| 40% | 1.2R | `0.40×1.2 − 0.60×1.0` = **−0.12R** | **Loses money** — yet passes the old 1.2:1 rule |

The old metric could be **failed by a winning system and satisfied by a losing one.** Either number alone is meaningless; only their product against the loss side decides anything.

**This also removes a bad incentive.** A headline win rate rewards *being right*. Trading does not pay for being right — it pays the distribution of money won against money lost. Optimising for win rate pushes toward cutting winners early to bank them, which is the exact drift §8 exists to prevent.

**Expectancy is also the metric that credits this system's actual design.** The breakeven ratchet (§6) converts would-be losses into ~0R scratches. A win/loss ratio barely notices that. Expectancy captures it directly, because a scratch removes a full −1R from the loss side.

### Reported every month, alongside expectancy

- **Profit factor** — gross winnings ÷ gross losses. Above 1.0 is profitable.
- **Max drawdown from peak** — worse than **−25%** is a **process failure regardless of P&L**. A **flag, not a brake**: report it loudly with a written review, then keep trading. The brake is the 3-consecutive-loss circuit breaker (§4), because a loss streak diagnoses a broken process where a percentage mostly reflects instrument volatility.
- **Rule adherence** — checkpoints where a rule was followed against where it was not. **A profitable month with poor adherence is worse news than a losing month with good adherence**, because the second is a process being tested and the first is luck being mistaken for one.
- **Slippage**, entry and exit.
- **Sample size**, stated next to every claim.
- **Win rate** and **average winner ÷ average loser** — still reported, now **descriptive only.** Neither is a target and neither passes or fails anything.
- **Trade count** reported, never targeted.

**A negative expectancy over 30+ trades is a process failure.** Report it that way and hand the decision to the governor — it is not an automatic halt, because 30 trades is still a small sample and the existing loss-streak brake already catches fast deterioration.

### P&L — lowest weight

Percentage growth net of costs, versus SPY over the same window.

**Do NOT let daily or weekly green-day targets drive behaviour.** They cause forced entries on no-setup days and premature exits on winners. Both are failures.

---

## 15. Reporting standards

- Report **losses as plainly as gains.** No spin.
- **Verified fills only** — never a fill you did not confirm from the order response.
- P&L in **dollars and percent**. Slippage against intended price.
- **Never claim edge from a small sample.**
- Correct your own errors promptly and plainly, including ones that make you look bad.
- Most checkpoints are non-events: **stay silent unless something material happened** — an entry, exit, stop, notable skipped setup, or an error. No "checked, nothing to do" messages.

### Cadence — events as they happen, plus a Friday recap

- **Material events: report immediately**, at the checkpoint where they occur. Entry, exit, stop fired, circuit breaker tripped, error, a detected break in the checkpoint chain, a balance change indicating funding, or a setup notable enough to name even though it was declined.
- **A no-trade day gets NO evening message.** Silence is the correct output.
- **Friday's 8:00pm checkpoint always reports**, regardless of whether the week had trades. Balance, every trade, the win/loss and loss-streak count, process tests satisfied, what was declined and why, and any rulebook change made during the week. **This is the guaranteed heartbeat** — it is the user's only way to distinguish "correctly sat out" from "the system silently stopped running," so it goes out even on a week where nothing at all happened.
- **Month-end still reports** the §14 statistics on top of the Friday recap.
- Silence between these is intentional and means "nothing material," never "nothing checked."

### Known limitations — state honestly when relevant

- **No learning from practice.** Only this rulebook improves, and only when errors are caught and written down.
- **30-minute blindness** between checkpoints.
- **Overnight cannot be automatically protected.** Structural.
- **Stops do not protect gaps.**
- **Headlines arrive late**, and dating them is sometimes impossible.
- **One round trip per day** caps trade count regardless of capital.
- **No demonstrated ability to generate a trade on a no-leadership day.**

---

## 16. The data layer — this file holds RULES, nothing else

**The LLM has no memory. The SYSTEM must remember everything.** Those are different propositions, and an earlier version of this design confused them — history was kept inside this file, mixed in with policy. It is now separated by lifecycle and by reader.

| File | Holds | Written by | Read by | Mutability |
|---|---|---|---|---|
| `RULEBOOK.md` | Rules and verified mechanics. **Policy only.** | Human governor | Every checkpoint | Edited rarely, reviewed |
| `data/trades.csv` | One row per closed trade | Executor, at exit | Researcher | **Append-only. Never edited.** |
| `data/observations.jsonl` | One record per checkpoint while holding, plus entry snapshots | Executor, at every check | Researcher | **Append-only. Never edited.** |
| `EXPERIMENTS.md` | Proposed rule changes and their evidence | Researcher | Human governor | Edited; states never skipped |
| `RULE_HISTORY.md` | Every rulebook change with its reasoning | **Generated** by `tools/gen-rule-history.sh` | Human governor | **Never hand-edited** |

- **`RULE_HISTORY.md` is a rendering of the git log, not a second source of truth.** Regenerate it; never write to it. If it disagrees with `git log`, the log is right and the file is stale. This is deliberate — a hand-maintained history would eventually contradict the commits it claims to describe.
- **No cached state in this file.** Loss streak, deposited capital and month-to-date figures are all **derived** — the streak and trade history from `data/trades.csv`, the deposit total from the broker (§10). A cached copy is a copy that goes stale, and there is no reason to keep one when the derivation is a single file read.

### What the EXECUTOR writes

- **At entry** — one `entry_snapshot` observation. These are **features, not rules.** Record them because we will want them later; do not invent a rule from them until there is evidence. Fields: instrument, timestamp, fill price, trend over 5/15/30/60 minutes and since the open, volume against normal, session high and low, sector performance, broad-market performance, volatility condition, catalyst type and age, the entry thesis, the falsification condition, stop, target.
- **At every checkpoint while holding** — one `checkpoint` observation: price, unrealised percent, the derived stall count *and the bars it came from*, stop location, whether the stop moved and why, headlines checked, and the pre-committed exit condition for the next check.
- **At every stall-2 event** — flag it in the observation, and record afterwards whether the position made a qualifying new high before the next check. This feeds EXP-001.
- **At exit** — one row in `data/trades.csv`, including **`initial_stop_pct` and `r_multiple`** (§14), maximum adverse and maximum favourable excursion *during the hold*, time held, both slippage figures, exit reason, and the rulebook commit hash in force at the time. **Compute the R multiple at exit while the entry stop is known**, rather than leaving it to be reconstructed later.

### What the EXECUTOR must NOT do

- **Never edit or delete a past row.** History is append-only. A mistake gets a correcting row and a note, never an overwrite.
- **Never write to `EXPERIMENTS.md`** during trading hours, and never read it while deciding a trade.
- **Never promote an experiment.** Only the human governor approves a rule change.

---

## 17. Two roles, one model — the authority firewall

The same model runs both roles at different times. **What is separated is authority, not identity.**

| Role | When | Reads | May write | Never |
|---|---|---|---|---|
| **EXECUTOR** | 9:00am–8:00pm ET, trading days | `RULEBOOK.md`, `EXECUTOR.md`, broker, live market, news | `trades.csv`, `observations.jsonl` | Post-exit prices · `EXPERIMENTS.md` · policy changes |
| **RESEARCHER** | **Saturday 10:00am ET** | history, `RULEBOOK.md`, `RESEARCHER.md`, `EXPERIMENTS.md`, historical bars | `EXPERIMENTS.md`, `observations.jsonl` | Any order · any edit to `RULEBOOK.md` |
| **GOVERNOR** | Whenever they choose | everything | `RULEBOOK.md` | — |

**The EXECUTOR never writes its own constitution.** This is the whole point. The same reasoning that says a model asked to justify widening a stop will succeed applies one level up: do not let the trading agent argue for changing the rules that constrain the trading agent.

### What is actually enforced, and what is not — read this honestly

| Control | Status |
|---|---|
| RESEARCHER cannot place an order | **ENFORCED** — Saturday, market shut. The 24-hour market runs Sun 8pm–Fri 8pm ET |
| EXECUTOR cannot see post-exit prices | **ENFORCED** — collected retroactively on Saturday; a cold session cannot remember what the last one saw |
| Every rule change is visible | **ENFORCED** — git diff on a reviewed branch. Not prevention; no change can be *invisible* |
| EXECUTOR must not read `EXPERIMENTS.md` | **DOCUMENTED ONLY** |
| RESEARCHER must not edit `RULEBOOK.md` | **DOCUMENTED ONLY** |
| Only the GOVERNOR promotes a rule | **DOCUMENTED ONLY** |

**`send_later` cannot restrict tools.** Every checkpoint session comes up with the identical tool set, so the "DOCUMENTED ONLY" rows are rules followed, not walls. Violations are **detected, not prevented** — same mechanism as the stop-never-widens rule, which has held. Do not describe this firewall to anyone as a technical guarantee.

### Promotion path — evidence may propose, never promote

`Observation → Hypothesis in EXPERIMENTS.md → tested against real history → shadow-tracked → GOVERNOR approves → written into RULEBOOK.md → locked evaluation period`

- **Safety defects skip all of it.** A duplicate-order risk, a floor breach, a misreported fill: fix immediately, then tell the governor. Never queue a safety bug as an experiment.
- **Keep the old rule version** so v(n) and v(n+1) can be compared instead of the goalposts moving continuously.

### Scheduling the RESEARCHER

- **Friday's 8:00pm arming checkpoint arms two things:** Monday's 24-checkpoint grid, and **Saturday 10:00am ET for the RESEARCHER** (14:00 UTC while EDT is in effect).
- The Saturday pass is one session per week. At roughly one trade per day there is not yet enough data to justify running it daily.
- **Every armed trading checkpoint must instruct the session to read `RULEBOOK.md` AND `EXECUTOR.md`.** The Saturday message points at `RULEBOOK.md` and `RESEARCHER.md` instead, and must state that no order may be placed.

---

## Current position

Flat. See `data/trades.csv` for all closed trades and `EXPERIMENTS.md` for open questions.

**Hard floor: 50% of deposited cash** (§10) — deposits recomputed at each 9:00am check.
