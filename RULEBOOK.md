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

### ⚠ SANDBOX-ONLY RISK MODEL — NOT SCALABLE

**The risk model is the one part of this system that must NOT be carried to a larger account.** Design-for-scale above applies to rules and metrics. It does **not** apply to sizing, and pretending otherwise would be the most expensive mistake in this document.

**The arithmetic, stated plainly.** The whole balance sits in one leveraged instrument, so a 5% stop is roughly **5% of the account** and a 7% stop is roughly **7%**, before slippage or a gap:

| Event | Account impact |
|---|---|
| Three consecutive −5% losses | **−14.3%** |
| Three consecutive −7% losses | **−19.6%** |
| −25% drawdown | a **flag**, not a halt (§14) |
| Actual hard stop | **50% of deposited cash gone** (§10) |

**At $40.84 this is acceptable because it is tuition.** The purpose is to test a process where being wrong is cheap. It is not a risk framework and must never be described as one.

**What must change before this manages meaningful money:**

- **Position size becomes an independent risk control.** Risk per trade drops to a small fraction of the account — conventionally well under 2% — and stop distance stops being the only lever.
- **§6's line "stop distance is the only risk lever there is" becomes false and must be deleted**, not reinterpreted. It is a true statement about a $40 sandbox and a dangerous one about anything else.
- **Concentration limits appear.** One instrument holding 100% is a sandbox artifact.
- **The −25% drawdown flag becomes a brake**, not a diagnostic.
- **The 50%-of-deposits floor becomes far tighter.** Losing half of real capital is not a backstop, it is a catastrophe.

**Do not raise sizing incrementally as the balance grows.** The change from "all-in" to "sized" is a redesign that the governor decides deliberately, not a threshold to drift across.

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

### CADENCE IS STATE-DEPENDENT — arm sparse, densify on entry

**Data resolution and decision cadence are separate things and must not be confused.** An earlier version coupled them: checkpoints were 30 minutes apart, the stall was defined from 30-minute bars, and three stalls triggered an exit — so the exit rule's timescale was an artifact of the schedule rather than a claim about the market. **Always collect 5-minute bars** (§8.1) regardless of how often the agent wakes.

**Baseline armed each evening — assume FLAT. 13 checkpoints:**

`9:00 · 9:30 · 9:45 · 10:00 · 10:30 · 11:00 · 11:30 · 12:30 · 1:30 · 2:30 · 3:30 · 4:00 · 8:00`

Dense through the preferred entry window (9:45–11:00), then hourly, because after 11:00 a new entry must clear a higher bar anyway (§4 Timing) and a flat checkpoint can only report that nothing qualified.

**ON ENTRY, the entering checkpoint immediately arms the fill-ins** — this is part of executing the trade, not an afterthought:

| State | Cadence | Reason |
|---|---|---|
| Holding, regular hours | **every 15 min** to 4:00 | Halves ratchet latency. A threshold crossed at 10:07 with a 30-minute cadence leaves the stop unmoved for 23 minutes while the position runs |
| Holding, extended hours | 30 min, 4:30 → 7:00, plus **7:30** | No stop can rest; manual management only (§6) |
| Carrying overnight | 8:00pm arms the **holding** schedule for the next day | The position exists before the day starts |
| Exceptional volatility | §12 — off-grid minutes, 10–15 min | Already authorised |

**Why this is not more expensive.** A flat day costs 13 checkpoints instead of 24. A day that enters at 9:45 and exits at 1:00 runs dense for three hours and then §3 early-shutdown deletes the rest — roughly 18. Since only one round trip per day is possible and an exit ends the session's trading, **the dense period is always short and bounded.**

**Densification is not optional, and a failure to densify must not leave a position under-covered.** The baseline above is deliberately sufficient to manage a position on its own — 30-minute gaps at worst until 11:30, then hourly — so if the fill-in arming fails, the position is still managed, just less tightly. Report the failure.

**Record the cadence actually in use** in every observation (§16), so it becomes possible to ask later whether it mattered.

**This takes effect from the next arming checkpoint.** Any day already armed on the old fixed 24-slot grid runs as armed; the extra checkpoints are harmless.

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

## 7. Profit-taking

- Set a **realistic target at entry** — roughly **+8% to +12%** on a 2x sector ETF — separate from any far tail target.
- **The target is a CEILING, and most trades will not reach it.** The three-check stall exit (§8.1) will close the majority of positions first, at whatever gain stands. Target is the exit that requires no judgment; it is **not** a reason to keep holding a position the other criteria have already condemned.
- **On reaching it: BANK IT — close the ENTIRE position**, unless there is **new information** supporting more upside, named explicitly. Momentum alone does not qualify. Neither does reluctance to sell a winner.
- **Never let the stop become the only exit** — that is drift.
- Profit-taking is **manual** at checkpoints, because the stop occupies the one resting-order slot. That is the correct allocation: the downside must work unattended; the upside can wait for a 30-minute check.

### Holding period

- **DEFAULT FOR A LEVERAGED OR INVERSE INSTRUMENT: CLOSE THE SAME DAY.** Overnight is not the default and is not what happens when a day trade fails to exit.
  - **Leveraged ETFs target a *daily* multiple and reset daily.** Held across multiple days, the return can diverge substantially from the simple multiple, and the divergence is worst precisely when volatility is high — which is when we are most likely to be holding one.
  - **Overnight is also completely unprotected** — no stop can rest (§6).
- **Carrying overnight is a SEPARATE DECISION requiring a named reason, stated at the 3:30pm checkpoint** while a stop still functions. Acceptable: the thesis is a multi-day catalyst that has not played out and the position is still making new highs into the close. **Not acceptable: "the exit criteria did not fire."** That is drift, and it is how an unintended overnight hold happens.
- **The one-week ceiling does not apply to leveraged instruments** without evidence that a multi-day hold works here. Treat it as available for ordinary equities and ETFs only.
- **Practical effect:** this is **predominantly a day-trading system**, with swing holds as a deliberate exception rather than the plan. The §8.1 stall ladder already produces that outcome; this states it as intent rather than leaving it as a side effect.
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

   **THE STALL CLOCK RUNS ON MARKET TIME, NOT ON CHECKPOINTS.** A stall is measured in **30-minute windows of market time**, built from 5-minute bars. Waking more often does not advance it; waking less often does not slow it. This matters because the wake cadence is variable (§2) — if a stall counted *checks*, then checking every 10 minutes would fire the exit after 30 minutes instead of 90, silently turning it into a different rule.

   **A stalled window** = a 30-minute window of market time in which the high failed to exceed the running high by more than **0.3%**, *and* volume was below the prior window's. Marginal ticks of +0.05% are not progress; they are a stall pretending otherwise.

   | Stalled windows | Elapsed | Action |
   |---|---|---|
   | **2** | 60 min | **Raise the stop to breakeven. Keep holding.** Downside eliminated; upside still open. |
   | **3** | 90 min | **SELL — whatever the gain.** No floor, no minimum, no exception. |

   **Windows are anchored to the clock** (`:00` and `:30`), not to the entry time, so two sessions looking at the same position count identically. A partial window in progress does not count until it completes.

   - **There is NO profit floor on the stall exit.** The earlier +5% floor is retired; this ladder replaces it. A three-check stall sells at +1% or +9% alike.
   - **By the time the sell fires, the stop is already at breakeven**, so the rule can only ever cost upside — never a loss. That is what makes an unconditional sell safe.
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

### Rule layers — where a new rule belongs

Rules live at four levels. **A rule stated at the wrong level is either too broad to be true or too narrow to be found.**

| Layer | Scope | Examples |
|---|---|---|
| **Universal** | Everything, always | Capital protection · order verification · stops ratchet up only · one resting order · loss floor · logging obligations |
| **Asset class** | Equity · ETF · **leveraged/inverse ETF** | Daily reset and decay · same-day close default (§7) · overnight unprotectable |
| **Category** | Energy · semis · gold miners · crypto · index | Which catalysts matter · which proxy to compare against (§16) |
| **Instrument** | A single ticker | Overnight tradability · spread behaviour · `position_closing_only` restrictions |

- **Place a new rule at the narrowest level where it is actually true.** "Leveraged ETFs decay in chop" is asset-class. "JDST fractional is closing-only" is instrument. Stating the second as a universal rule would be false; stating the first as an instrument rule would mean rediscovering it for every ticker.
- **The category layer is mostly empty and that is correct for now.** Energy responds to inventories, OPEC and geopolitics; gold miners to rates, the dollar and real yields; agriculture would respond to planting calendars, USDA reports and weather. **Those models are not built and must not be improvised at a checkpoint.** They arrive through `EXPERIMENTS.md` and governor approval, with evidence, one category at a time.
- **Do not collapse domain knowledge into the generic gate.** "Leading sector + breadth + catalyst + trend" is what the system has today, and it deliberately throws away domain information. That is a known limitation, not a design goal.

### Verified facts

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
- **Cash accounts are exempt from PDT** — no $25k minimum, so daily trading is permitted. **This is verified for THIS cash account and nothing else.**

### ⚠ Do not carry these settlement facts into a margin account

- Everything above is verified against a **cash** account. **Pattern-day-trader rules apply to margin accounts, not this one**, so none of the PDT reasoning here has been tested against margin mechanics.
- **A reviewer has flagged that FINRA's margin day-trading rules changed in June 2026 with a firm transition period running into 2027.** *This claim is unverified* — it postdates what can be confirmed from here, and it has not been checked against a primary source.
- **Therefore: if this account is ever converted to margin, or a margin account is added, re-verify the day-trading and settlement rules from primary sources BEFORE the first trade.** Do not port a single assumption from this section.
- The general principle: **settlement and account-type rules are external facts with expiry dates.** They are not derivable and they change. Verify, cite, date.

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

## 12. Volatility escalation — authorized

If a position becomes **exceptionally volatile**, you may watch it as long as necessary, **including overnight**.

- Arm extra `send_later` checkpoints at **off-grid minutes** (`:10, :20, :40, :50`) at 10–15 minute intervals, so they can never collide with the standing `:00`/`:30` grid.
- Manage via `all_day_hours` limit orders if the instrument is eligible.
- Stand down to the normal cadence once it settles.

This is the one permitted exception to "do not arm anything."

---

## 13. Runs indefinitely

The loop continues **every trading day until the user explicitly pauses or cancels it.** They set that date, not you. Never stop on your own initiative; no week-end or month-end is terminal.

- **Each 8:00pm checkpoint MUST arm the next trading day** — highest priority, ahead of reporting. Arm the **13-slot flat baseline** (§2) unless a position is being carried overnight, in which case arm the holding schedule.
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

- **At entry** — one `entry_snapshot` observation. See the spec below; the fields must be computed the same way every time or they cannot be compared across trades.
- **At every checkpoint while holding** — one `checkpoint` observation: price, unrealised percent, the derived stall count *and the windows it came from*, stop location, whether the stop moved and why, headlines checked, the pre-committed exit condition for the next check, and **`cadence_min`** — the interval in force (§2), so it becomes possible to ask later whether cadence changed outcomes.
- **At every stall-2 event** — flag it in the observation, and record afterwards whether the position made a qualifying new high before the next check. This feeds EXP-001.
- **At exit** — one row in `data/trades.csv`, including **`initial_stop_pct` and `r_multiple`** (§14), maximum adverse and maximum favourable excursion *during the hold*, time held, both slippage figures, exit reason, and the rulebook commit hash in force at the time. **Compute the R multiple at exit while the entry stop is known**, rather than leaving it to be reconstructed later.

### The entry snapshot — exact spec

**Written once per entry, immediately after the fill is confirmed.** Roughly three extra tool calls, once a day.

| Field | How to compute it |
|---|---|
| `ts` | Record timestamp, **UTC**. Every record type carries it, so records can be ordered across files |
| `instrument`, `fill_price`, `fill_time_et` | From the order response (§5). Confirmed, never assumed |
| `trend_5m` `trend_15m` `trend_30m` `trend_60m` | Percent change over each lookback, from **5-minute bars** (`get_equity_historicals`). `(last close − close N min ago) ÷ close N min ago × 100` |
| `trend_since_open` | `(fill − session open) ÷ session open × 100` |
| `gap_from_prev_close` | `(session open − previous close) ÷ previous close × 100` |
| `trend_alignment` | **How many of the four horizons share the sign of the trade** (0–4). Long counts positive; inverse ETF bought long counts the *fund's* own positive move |
| `position_in_range` | `(fill − session low) ÷ (session high − session low)`. 0 = entering at the low, 1 = at the high |
| `session_high`, `session_low` | From the bars |
| `volume_vs_session` | Latest 5-min bar volume ÷ median 5-min bar volume so far today. **Known weakness:** not time-of-day adjusted, so early-session values run high. Record it anyway and correct later if it matters |
| `sector_pct` | Day change of the **unleveraged** proxy from the map below |
| `market_pct` | SPY day change |
| `vix_level`, `vix_change` | `get_index_quotes` on VIX. Blank if unavailable — do not substitute a guess |
| `spread_pct_at_entry` | `(ask − bid) ÷ mid × 100` at the moment of entry |
| `catalyst_type` | One of: `earnings` · `guidance` · `macro` · `geopolitical` · `regulation` · `commodity_supply` · `weather` · `analyst` · `corporate_action` · `sector_sympathy` · `other` |
| `catalyst_direction` | `bullish` · `bearish` · `ambiguous` |
| `catalyst_scheduled` | `true` if a known calendar event, `false` if a surprise |
| `catalyst_source_time`, `catalyst_age_min` | When the news was published, and its age at entry. Blank if undateable — **say blank, never estimate** |
| `entry_thesis` | One sentence. What is expected to happen and why |
| `falsification_condition` | The §8 pre-commitment, stated as a checkable condition |
| `stop_price`, `stop_pct`, `target_pct`, `intended_max_hold` | As stated at entry (§6, §7) |
| `rulebook_commit` | `git rev-parse --short HEAD` |

### Unleveraged proxy map — for `sector_pct`

| Instrument | Proxy | | Instrument | Proxy |
|---|---|---|---|---|
| SOXL · SOXS | SMH | | GUSH · ERX · ERY · NRGU | XLE |
| TQQQ · SQQQ · FNGU · BULZ | QQQ | | LABU | XBI |
| SPXL · SPXS · SDOW | SPY | | NUGT · DUST · GDXU | GDX |
| TNA · TZA | IWM | | YINN | FXI |
| NVDL | NVDA | | TSLL | TSLA |
| CONL | COIN | | MSTX | MSTR |
| RIOT · MARA · BITX | own sector, note as crypto | | UVIX · VXX | VIX |

`market_pct` is always SPY. If an instrument is not on this map, name the closest unleveraged proxy in the snapshot and say it was chosen ad hoc.

**Shape** — one line in `data/observations.jsonl`, no line breaks:

```json
{"type":"entry_snapshot","ts":"2026-08-11T13:52:55Z","fill_time_et":"09:52:55","instrument":"SOXL","fill_price":24.31,
 "trend_5m":0.41,"trend_15m":0.88,"trend_30m":1.12,"trend_60m":1.60,"trend_alignment":4,
 "trend_since_open":1.44,"gap_from_prev_close":0.62,"position_in_range":0.91,
 "session_high":24.35,"session_low":23.88,"volume_vs_session":1.8,
 "sector_pct":0.54,"market_pct":0.21,"vix_level":17.4,"vix_change":-0.6,
 "spread_pct_at_entry":0.08,"catalyst_type":"earnings","catalyst_direction":"bullish",
 "catalyst_scheduled":true,"catalyst_source_time":"2026-08-10T20:05:00Z","catalyst_age_min":1067,
 "entry_thesis":"Memory guidance beat lifts the whole group; breadth confirms.",
 "falsification_condition":"SMH loses its opening range low while SOXL fails to make a new high.",
 "stop_price":23.09,"stop_pct":-5.0,"target_pct":10.0,"intended_max_hold":"1 day",
 "rulebook_commit":"6b1131e"}
```

### FEATURES, NOT RULES — the discipline that makes this safe

- **Record these because we will want them later. They are not criteria.** Nothing in the snapshot gates a trade.
- **It is a VIOLATION to decline or size a trade because a snapshot field "looks bad"**, unless that field is already a §4 gate. Letting a logged feature quietly influence judgment converts it into an unapproved rule while leaving no trace that a rule was added.
- **The §4 gates are the complete entry criteria.** The snapshot is observation running alongside them.
- A pattern becomes a rule only via `EXPERIMENTS.md` → evidence with a stated sample size → **governor approval** (§17). Never by noticing it at a checkpoint.
- **Why this order matters:** inventing the rule first and finding support for it afterwards is how a system fits yesterday. Collect first, decide later, and the evidence gets a chance to say no.

### Catalysts — structured, and logged whether traded or not

**"A nameable catalyst" is a good guardrail and a bad measurement.** As prose it is unfalsifiable — almost anything can be narrated as a catalyst. Structuring it makes categories scoreable, and makes it possible to discover that some kinds of news are worth trading and others are not.

**Write one `catalyst` record for every catalyst identified at the 9:00am research pass or noticed at any checkpoint — including ones not traded.** Logging only traded catalysts would leave the same selection bias as logging only taken trades: the sample would contain only news already believed in, so no category could ever be shown worthless.

| Field | Notes |
|---|---|
| `id` | `CAT-YYYY-MM-DD-NN` |
| `ts`, `discovery_time` | When logged / when first seen |
| `source_time`, `source_time_confidence` | Publication time, and `exact` · `approximate` · `unknown`. **Never estimate a time and present it as known** |
| `age_min` | Age at discovery. Blank if `source_time_confidence` is `unknown` |
| `type` | The 11 categories above |
| `direction` | `bullish` · `bearish` · `ambiguous` |
| `scheduled` | Calendar event, or surprise |
| `affected_instrument` | The tradeable name |
| `affected_underlying` | Sector or underlying, from the proxy map |
| `relevance` | `direct` — the instrument's own news · `indirect` — someone else's news reaching it |
| `expected_move_pct` | **A prediction.** Record it so it can be scored |
| `expected_duration` | `minutes` · `hours` · `days` |
| `confidence` | 1–5. **Known to be uncalibrated** — logged precisely so the RESEARCHER can find out whether it predicts anything at all. Do not treat it as meaningful yet |
| `headline`, `source` | Short |
| `traded` | `true` / `false`, plus a one-line reason when false |
| `entry_snapshot_ts` | Links to the entry, if traded |

**Classification rules — so the categories mean the same thing each time:**

- **When two types apply, record the proximate cause**, not the mechanism. An OPEC production decision moving oil is `commodity_supply`; the same move caused by a shooting war is `geopolitical`.
- **`sector_sympathy` is only for another company's news reaching this instrument.** If it is the instrument's own news it is never sympathy.
- **`other` requires a written reason.** If `other` exceeds roughly 15% of records, the taxonomy is wrong and the RESEARCHER should propose fixing it. That threshold is the taxonomy checking itself.
- One catalyst per record. Two pieces of news are two records, even if they point the same way.

**Outcomes are a SEPARATE record, written Saturday by the RESEARCHER.** Observations are append-only — never edit a catalyst record to add its result. Write `catalyst_outcome` referencing the `id`, with the affected instrument's move at **+15, +30, +60, +120 minutes and to the close**, whether the direction was right, actual against `expected_move_pct`, and the favourable and adverse extremes in the window.

**When a §11 kill trigger fires, log a `kill_trigger_fired` record** — which trigger, the price at the time, and what was done. These are the highest-conviction exits in the system and there is currently no record of whether they have ever been right.

### Declined candidates — log the trades NOT taken

**One `declined` record per checkpoint that considered a candidate and passed**, naming the instrument, the gate that failed, and the price at the time.

Without this the dataset contains only trades that were taken, which makes every conclusion drawn from it selection-biased — we could measure how our entries performed but never whether our filters were throwing away winners. This is the cheapest possible correction: one short record, no extra tool calls beyond what the gate check already required.

### What the EXECUTOR must NOT do

- **Never edit or delete a past row.** History is append-only. A mistake gets a correcting row and a note, never an overwrite.
- **Never evaluate how a DECLINED candidate has performed since you declined it.** Log the rejection and move on. Checking whether the one you passed on has run is the same failure as post-exit tracking (§9) wearing different clothes — it trains chasing instead of hesitation, and it is the likeliest route to a forced late entry. The RESEARCHER scores declined candidates on Saturday; you do not.
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

### POLICY VERSION: v1.0 — increment on every policy change

**Bump the minor version on any change to a rule, threshold or limit.** Record it in the commit. `rulebook_commit` is already stamped on every trade row (§16), so any trade can be traced to the exact policy it ran under — the version number is the human-readable handle for the same thing.

### The locked evaluation period — the anti-overfitting rule

**After a rule changes, it may not change again until at least 20 closed trades have run under the new version** — or the governor explicitly overrides.

- **Why:** without this, the loop becomes *trade → lose → adjust rule → trade → lose → adjust rule*, which is a sophisticated machine for fitting yesterday. Repeatedly selecting the variant that performed best on a small history produces a strategy that looks excellent in review and has no predictive content whatsoever. This is a well-documented failure in quantitative finance, not a hypothetical.
- **A rule changed three times in a week has never been tested.** It has only been fitted. And there is no way afterwards to attribute any outcome to any version.
- **Exempt:** safety defects, factual corrections, and anything the governor directs in conversation.
- **Honest note on precedent.** The stall rule went through three versions in a single session on 2026-08-11, before any trade ran under any of them. That was acceptable *only* because it was pre-deployment design work on an untested rule, driven by reasoning about arithmetic rather than by results. **Once live trades exist, that pace becomes forbidden** — it would be indistinguishable from chasing noise.
- **20 trades is roughly a month** at one round trip per day. That is deliberately slow. Slow is the point.

### Scheduling the RESEARCHER

- **Friday's 8:00pm arming checkpoint arms two things:** Monday's 24-checkpoint grid, and **Saturday 10:00am ET for the RESEARCHER** (14:00 UTC while EDT is in effect).
- The Saturday pass is one session per week. At roughly one trade per day there is not yet enough data to justify running it daily.
- **Every armed trading checkpoint must instruct the session to read `RULEBOOK.md` AND `EXECUTOR.md`.** The Saturday message points at `RULEBOOK.md` and `RESEARCHER.md` instead, and must state that no order may be placed.

---

## Current position

Flat. See `data/trades.csv` for all closed trades and `EXPERIMENTS.md` for open questions.

**Hard floor: 50% of deposited cash** (§10) — deposits recomputed at each 9:00am check.
