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

---

## 1. Step Zero — trigger hygiene (do this FIRST, every checkpoint)

Call `list_triggers`.

1. **DELETE every trigger with `ended_reason='run_once_fired'`.** Spent triggers show a stale `next_run_at` pointing at tomorrow's same clock time. It is UNCONFIRMED whether they can re-fire — assume they might. Deleting is harmless if they are dead and prevents duplicate checkpoints if they are not. **Two checkpoints on one setup can place two orders — a real-money failure, not untidiness.**
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

### Instrument selection, in priority order

1. **Whole share is the DEFAULT** — the most leverage per dollar that fits as a whole share. Whole shares preserve the after-hours and 24-hour-market exit and allow limit orders.
2. **Verify `all_day_tradability` before entering.**
3. **Check the spread.** Do not assume it.
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

- **Never widen for comfort or "room for variance."** If the tape needs more room than the stop allows, **the position is too big** — exit rather than move the goalposts.
- The only permitted downward change is **correcting a factual placement error**, and you must say that is what it is.
- Raise on **rules** or on **structure** (below a support that has held across several checks).
- **Not every check.** Each raise is cancel-then-replace, which briefly leaves the position unprotected, and over-tightening invites noise stop-outs on a leveraged instrument. **Do not tighten on a flat print** — the stop migrates up as the position *gains*.
- **Migrate from loss-avoidance to profit-locking as gains accrue.** A stop left far below price on a winner lets it round-trip through breakeven.

### Hard limits of a stop

- **Stop orders are REGULAR-HOURS ONLY.** Extended hours and overnight **cannot** be automatically protected — a sell limit below market fills instantly at the bid, so it cannot fake a stop.
- **A stop does NOT protect against a gap.** It bounds slippage in an orderly decline only.
- **The only real defence for an overnight event is not holding into it.**
- **The user has been told this and accepts it** — *"the overnight stuff I'm not too worried about."* A 1–2 day default horizon means routinely holding unprotected overnight, and that is a known, accepted cost, not an oversight. **Do not re-litigate it at checkpoints or re-warn about it as though it were news.** State it only when a specific, identifiable overnight event is approaching — that is a trade decision (§8.5), not a structural complaint.

---

## 7. Profit-taking

- Set a **realistic target at entry** — roughly **+8% to +12%** on a 2x sector ETF — separate from any far tail target.
- **On reaching it: BANK IT**, unless there is **new information** supporting more upside, named explicitly. Momentum alone does not qualify. Neither does reluctance to sell a winner.
- **Never let the stop become the only exit** — that is drift.
- Profit-taking is **manual** at checkpoints, because the stop occupies the one resting-order slot. That is the correct allocation: the downside must work unattended; the upside can wait for a 30-minute check.

### Holding period

- **Default: 1–2 days.** This is the working assumption for every trade.
- **Absolute ceiling: 1 trading week.** Only for an *exceptional* opportunity, and you must say at entry that you are invoking it and why. "It's still going up" is not exceptional.
- **State the intended maximum hold at entry**, so it is a commitment rather than a running negotiation.
- If the target is not reached and event risk approaches, **exit rather than drift** — the horizon is a ceiling, not a target to fill.

### Scaling out — once more than one share is affordable

- With a single share, the only choices are all-in or all-out. **Once the balance supports 2+ shares, take partial profits:** bank roughly half at target, let the remainder run with the stop ratcheted up behind it.
- This is the one thing a single share structurally cannot do, and it serves "lock in profits" directly — a realised gain on half the position, with continued exposure on the rest.
- The remainder is still governed by every other rule: same stop discipline, same exit criteria, same horizon ceiling.
- **UNVERIFIED MECHANIC — test before relying on it.** §10's one-resting-order limit was proven with a single share, where a resting stop drove `sharesCanSell` to 0. Whether a stop on *part* of a multi-share position leaves the remainder sellable is **not yet known**. Before the first scale-out, confirm with `review_equity_order` that a partial sell is accepted while a stop rests on the rest. **If it is not**, scaling out means cancelling the stop, selling half, and immediately replacing the stop on the remainder — sequenced deliberately, since the position is unprotected in between. Do not discover this mid-trade.

---

## 8. Exit criteria — any one fires

1. **Momentum stalled** — no new high across 2+ checkpoints *and* volume drying up.
2. **Reversal** — broke the level/VWAP that justified entry, or the sector rolled over.
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

## 9. No post-exit price tracking

Once a position is **closed**, do **not** report, track, or comment on what the price did afterward. Do not compute "would I have been better off holding."

That is **outcome bias** — the quality of an exit is fixed by the information available *at* the decision, not by the next few minutes of tape. It is also actively harmful: logging "it went up after I sold" trains hesitation into future exits and destroys the discipline these rules exist to enforce.

**Green is green. If the system says sell, sell and move on — we are not married to these leveraged plays.**

The legitimate version of this check is **aggregate**, and it is already captured by the month-end metric *average winner ≥ 2× average loser*. If exits are systematically premature, that ratio degrades and it will show up there. Single-trade post-exit price action is noise pretending to be feedback.

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
- **Floor: stop trading and report below ~$15.**

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

*As of Aug 10 2026:* the **2026 Strait of Hormuz crisis** — an active closure amid a US-Israel-Iran war (Iran blocked the strait Feb 28 2026). Iran demands sanctions relief **and** war reparations, and has ruled out direct US talks. The Iran–**Oman** proposed-route deal (~Aug 5–7, joint statement "in final drafting") is with **Oman, not the US**; crossings **fell** afterward (15 Fri → 11 Sat → 6 Sun), so it produced no flow. WTI ~$80, Brent >$84. Reopening-optimism headlines exist ("deal as early as Wednesday") but are stale/undated — weigh price action.

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
- **Friday's final checkpoint arms Monday.**
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

- **Average winner ≥ 2× average loser** (the metric that actually predicts long-run results)
- **Win rate** reported alongside it — 40% at 3:1 is excellent; 70% at 0.8:1 is a time bomb
- **Trade count** reported, not targeted
- **Max drawdown from peak** — worse than **−25%** is a **process failure regardless of P&L**. It is a **flag, not a brake**: report it loudly with a written review of what broke, then keep trading. The brake is the 3-consecutive-loss circuit breaker (§4), because a loss streak diagnoses a broken process where a percentage only reflects instrument volatility.

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

## Trade log

| Date | Instrument | In | Out | P&L | % | Note |
|---|---|---|---|---|---|---|
| Aug 10 2026 | GUSH ×1 | $37.9299 (9:52am) | $39.1613 (3:02pm) | **+$1.2314** | **+3.25%** | Hormuz supply shock; exited on stalled momentum, not target. Zero fees. Account $40.84 → $42.07 |

**Month to date (Aug 2026):** 1 trade · 1 win · 0 losses · **+3.01%** · max drawdown from peak −0.5% · **consecutive-loss streak: 0** (circuit breaker at 3, §4)
