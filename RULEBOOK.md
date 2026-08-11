# Agentic Trading Rulebook

**Canonical source of truth for policy.** Nothing is copied forward between checkpoints — the rules live in files, not in memory, so they cannot degrade through recopying. Edit here to change behaviour everywhere, immediately.

**Two files, partitioned by how often they are needed. No rule appears in both.**

| File | Read by | Size |
|---|---|---|
| **`OPERATIONS.md`** | every management checkpoint — the hot path | ~16KB |
| **`RULEBOOK.md`** (this file) | 9:00 research · 9:45 entry · 4:00 report · 8:00 arming · Saturday research | ~57KB |

**Account:** Robinhood `462514035` ("Agentic"), cash account, `agentic_allowed=true`, `option_level_2` — *the option level is descriptive only; options are not permitted here (§4).*

---

## 0. Objective

Grow the account as fast as possible, "nothing to lose," using **leverage** plus **day and swing trading**, while **locking in profits**.

- **There is NO dollar target.** Never plan around one — it creates path-dependent incentives, under-risking near it and chasing when behind.
- **AGGRESSION belongs to the ENTRY**: leveraged 2x/3x, full position, concentrated, long or inverse.
- **DISCIPLINE belongs to the EXIT**: stops that only ratchet up, a defined target, a short horizon.
- **"Nothing to lose" NEVER licenses aggression in the exit.** Holding through a stop hoping for more is the single behaviour that destroys accounts.
- **"Constant profit" is impossible.** Losing trades are structural, not failures. The goal is positive expectancy, which includes red days.

### DESIGN FOR SCALE — the current balance is not the frame

**Judge every rule as though the account were 10x its size or more.**

- **A +2% win is significant.** At scale, a high win rate banking +2% with the downside capped at breakeven is an excellent system, and it is the thing being built.
- **Never reason from the dollar balance to a change in strategy.** "This won't compound at $62, so reach for the fat tail" optimises for an account size meant to be temporary, and trains variance-seeking that is harmful at scale.
- **Every threshold is a PERCENTAGE.** Dollars appear only where a mechanical constraint forces it — affordability, and the recorded deposit total.
- **Rules dormant today that activate with size, and must not be dropped for being unused:** partial sells in the override case (§7, needs 2+ shares); most of the leveraged universe (§4, unaffordable as whole shares); multiple concurrent positions (approved in principle, not now).
- **Where the small-account answer and the at-scale answer differ, say so explicitly** rather than silently optimising for today.

### ⚠ SANDBOX-ONLY RISK MODEL — NOT SCALABLE

**Design-for-scale applies to rules and metrics. It does NOT apply to sizing.** The whole balance sits in one leveraged instrument, so the stop distance *is* the account risk:

| Event | Account impact |
|---|---|
| Three consecutive −5% losses | **−14.3%** |
| Three consecutive −7% losses | **−19.6%** |
| −25% drawdown | a **flag**, not a halt (§14) |
| Hard stop | **50% of deposited cash gone** (§10) |

**At $62 this is acceptable because it is tuition** — a process tested where being wrong is cheap. **It is not a risk framework and must never be described as one.**

**Before this manages meaningful money:** position size becomes an independent risk control (risk per trade well under 2%) · **§6's "stop distance is the only risk lever" becomes FALSE and must be DELETED, not reinterpreted** · concentration limits appear · the −25% flag becomes a brake · the 50% floor gets far tighter.

**Do not raise sizing incrementally as the balance grows.** "All-in" to "sized" is a redesign the governor decides deliberately, not a threshold to drift across.

---

> ## ⚠ THE INTRADAY RULES NOW LIVE IN `OPERATIONS.md`
>
> **§1** trigger hygiene · **§3** early shutdown · **§5** order execution · **§6** stops · **§8** exit criteria · **§11** headline check
>
> They were moved, not copied — each rule exists in exactly one file, so they cannot drift apart. Section numbers are unchanged, so every `(§n)` reference still resolves.
> **A management checkpoint reads only `OPERATIONS.md` (~16KB) instead of this file (~57KB).** Entering, reporting, arming and research read both.
>
> **Both files are INSTRUCTION ONLY. The reasoning for every rule is in the commit that introduced it**, rendered in `RULE_HISTORY.md`. Do not re-add justification to either file — every KB in `OPERATIONS.md` is re-read up to 24 times a day, and bulk hides contradictions as reliably as it costs tokens.

---

## 1. Step Zero — trigger hygiene (do this FIRST, every checkpoint)

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 2. The daily grid (ET)

A three-stage morning funnel, then management, then close. **17 checkpoints, plus 7 extended-hours slots only when holding.**

| Time | Role | Orders | Reads |
|---|---|---|---|
| **9:00am** | **Pre-market research** | ❌ read-only | both files |
| **9:30am** | Opening observation | ❌ read-only | `OPERATIONS.md` |
| **9:45am** | **TRADING OPENS** — first entry | ✅ | **both files** |
| 10:00 → 3:30 | Management, every 30 min | ✅ | `OPERATIONS.md` |
| 4:00pm | Close, session report | ✅ until the bell | both files |
| 4:30 → 7:00 | Extended hours — **only if holding** | ⚠️ limit only, **no new positions** | `OPERATIONS.md` |
| **7:30pm** | **LAST ACTIONABLE CLOSE** — only if holding | ⚠️ day trades must close | `OPERATIONS.md` |
| **8:00pm** | Report + arm the next day | ❌ admin only | both files |

Convert each ET time to UTC using the offset in effect.

### THE CADENCE IS 30 MINUTES. Flat or holding, it does not change.

`9:00 · 9:30 · 9:45 · 10:00 · 10:30 · 11:00 · 11:30 · 12:00 · 12:30 · 1:00 · 1:30 · 2:00 · 2:30 · 3:00 · 3:30 · 4:00 · 8:00`

**Only if holding at 4:00pm**, add `4:30 · 5:00 · 5:30 · 6:00 · 6:30 · 7:00 · 7:30`. A flat book never arms these (§3).

- **No densification on entry.** Entering a trade does not change the clock.
- **Carrying overnight:** 8:00pm arms the standard schedule; extended slots get armed the following afternoon if still held.
- **§12 volatility escalation** is the one authorised off-grid exception.
- **State the cadence in force** in the report (observation records are suspended, §16).

> ### ⚠ THE CADENCE IS NOW LOAD-BEARING ON THE EXIT RULE. Do not change it casually.
> The stall counts **checkpoints** (§8.1), so **the cadence IS the stall timescale.** At a 10-minute cadence three stalls would fire after 30 minutes instead of 90 — a different exit rule wearing the same words. **If the cadence is ever changed, re-derive `stall.checks_to_sell` in the same breath**, or the exit rule changes without anyone deciding to change it.
>
> This was not true before 2026-08-11, when the stall ran on market time and was deliberately cadence-independent. That property is gone; the pinned cadence is what replaces it.

**Why 30 minutes:** replay took the *same exit for the same reason* at 10, 15 and 30 minutes — −0.60R / −0.58R / −0.61R, so a 3× cadence range moved the outcome 0.03R (EXP-006/011, now stale — re-run before citing). And **every checkpoint is a chance to make an unforced error**: each is a cold session that re-derives and re-decides. **More looking is not more discipline.**

**What it costs:** about 15 minutes of average delay acting on a newly crossed ratchet threshold. Accepted.

### Keep the hot path small

A management checkpoint reads `OPERATIONS.md` alone — **~16KB against ~90KB for both files.** That partition is what makes 17–24 checkpoints a day affordable. **Before adding to `OPERATIONS.md`, ask whether the rule is needed to *manage or exit an open position*. If it is only needed to *enter*, it belongs here.** The reasoning for any rule belongs in the commit message, not in either file.

### 9:00am pre-market research — read-only, no orders

- **(a) Headlines**, broad — macro, geopolitical, anything that moved overnight.
- **(b) Pre-market prices** via `quote.last_non_reg_trade_price` across the universe plus yesterday's watchlist.
- **(c) Earnings reactions** of last night's after-close reporters; their prints often set the day's leadership.
- **(d) Rank sector leadership** as indicated pre-market.
- **(e) Confirm settled buying power** (`get_accounts` for `unsettled_funds`, plus `get_portfolio`) so 9:45 knows its size instead of discovering a shortfall mid-setup.
  - **A balance larger than yesterday's close, beyond what trading explains, means the governor funded the account.** No announcement is coming — this check is where you find out. Size to it and say so in the report. **Do not ask for or campaign for funds.**
  - **Recompute deposited capital and report it if it changed.** The floor is a percentage of it (§10) and the figure is **derived, never cached** (§16).
- **(f) WRITE A WATCHLIST OF AT LEAST 5 NAMES** — a minimum, not a target.
  - **Rank the full profiled universe first, then mark affordability** (§4). Each name: `mfe_per_stop`, price, affordable as a whole share or not, sector proxy, one line of thesis or reason for watching.
  - **Include unaffordable names.** They are the record of what capital is costing.
  - **Write it as a `watchlist` record** (§16), so 9:45 reads a list built calmly rather than assembled under pressure, and Saturday can score what was watched and skipped.
  - **Fewer than five means the scan was too narrow**, not that the market was empty.
- **(g) REFRESH `data/vol_profile.csv`.** Pull ~20 sessions of daily bars for the watchlist, recompute median adverse and favourable excursion, rewrite the file (`tools/vol_profile.py`). **Every risk number derives from it** (§6). Commit and push.
  - **Recompute, never freeze.** SOXL ranged $196 → $91 inside the window that produced the first profile.
  - **An instrument absent from the profile may not be traded.** No fallback default.

### 9:30am opening observation — read-only, no orders

Test whether the 9:00 thesis survived the open: did pre-market strength hold into real volume, or fade? Check breadth within the leader. **Chop argues against every leveraged ETF.** Record the sector proxy's day change — Gate 1 (§4) compares it against the 9:45 reading.

---

## 3. Early shutdown — saves usage

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 4. Entry — what to look for

> **Instruction only. The reasoning for each rule is in the git commit that added it** (`RULE_HISTORY.md`). Do not re-add justification here — this section is read under time pressure at 9:45.

### CIRCUIT BREAKER — check before every entry

**After 3 consecutive losing closed trades, STOP ENTERING until the governor clears it.**

- A **loss** is any closed position with negative realised P&L, however small. Do not reclassify one as "flat" to keep a streak alive.
- Consecutive **closed trades**, not days. A winner anywhere resets it to zero. Rows marked `counts_toward_streak=no` are excluded — a mechanical abort is not a trade.
- **"Pause" means no new entries.** Manage any open position to its exit, keep running every checkpoint, keep reporting, and **keep arming.** Pausing entries must never become pausing the system.
- **Tell the governor plainly at the third loss:** the three theses, and your honest read on whether they were three bad reads or one bad read repeated.
- **Only the governor restarts entries.** Not on your own judgment, and not because a setup looks good — that instinct is what the brake exists to interrupt.
- `preflight.py` computes the streak from `data/trades.csv`. Never from memory.

**A −25% drawdown from peak is a FLAG, not a brake** — report it loudly with a written review, keep trading (§14). The hard floor is **50% of deposited capital** (§10), recomputed daily.

### Signals

- **Sector leadership, ranked from data.** Never default to one you have been watching.
- **Breadth.** Is the group moving together, or is one name dragging the ETF? **Broad beats narrow every time.**
- **A catalyst you can name.** "It's going up" is not a catalyst. *(Commodities and materials use the trend-structure gate instead — see below.)*
- **Trend, not chop.** Leveraged ETFs decay in chop.
- **Continuation, not prediction.** Go with an established move; do not call tops or bottoms.
- **No read = no trade.** A flat day is a correct outcome.

### ⛔ GATE 1 — the sector must HOLD a positive trend from 9:30 to 9:45

Record the sector proxy's day change at the **9:30** observation and again at **9:45**. All three must hold:

1. positive at 9:30, **and**
2. positive at 9:45, **and**
3. the 9:45 reading **not below** the 9:30 reading.

Any failure → **no entry in that sector**, whatever pre-market indicated.

**Two fixed observations decide it. Do not add intermediate readings** — nothing at 5- or 13-minute resolution is a trend, and narrating each swing as a regime change is how an entry gets taken with no stable thesis.

### ⛔ GATE 2 — a single-stock leveraged ETF whose UNDERLYING lags its sector

> **Never buy a single-stock leveraged ETF when its underlying is underperforming its sector proxy on the day.**

- Both as day change; sector proxy from the map in §16. If `underlying_pct < sector_pct` → **decline**, and log `declined` with gate `underlying_lags_sector`.
- **You are otherwise buying the laggard with leverage**, which turns a correct sector call into a losing trade.
- **Does not apply to sector or index leveraged ETFs** — those *are* the group.
- **`preflight.py` enforces it.** `--underlying-pct` and `--sector-pct` are mandatory for these names; **omitting them DENYs.**

### ⛔ GATE 3 — CLASS PRIORITY. Sector and index beat single-stock.

**Decided BEFORE `mfe_per_stop` ranking.** The ratio ranks *within* a class; it never promotes a single-stock name above a sector one.

| | Class | Examples |
|---|---|---|
| **1** | Sector / industry leveraged | SOXL · TECL · GUSH · ERX · NUGT · LABU · SOXS · DUST · AGQ |
| **2** | Index leveraged (broad-market read) | TQQQ · UPRO · TNA · SQQQ · SPXS |
| **3** | Single-stock leveraged | NVDX · NVDL · SMCX · MSTX · TSLL · CONL · MUU · AMDL |

**The read is almost always sectoral, and a single-stock leveraged ETF multiplies twice** — leverage on idiosyncratic concentration. An earnings miss or downgrade the sector shrugs off is not in your thesis.

**A single-stock name needs ALL FOUR:**

1. no sector or index vehicle for the same read is affordable as a whole share, **and**
2. its underlying is **leading** its sector (Gate 2), **and**
3. every other gate clears, **and**
4. **you name at entry which sector vehicles were ruled out, by name and price.** "None affordable" is valid; not having looked is not.

**Accepted cost:** sector leveraged ETFs cost more per share ($135–282) than single-stock 2x names ($4–20), so at current capital this produces **more no-trade days.** That is the correct outcome — it reports that the account cannot buy what the thesis calls for.

### RANKING — rank the full universe FIRST, then intersect with affordability

**"Find the good then the affordable."** Never filter by price first.

1. Rank the **whole profiled universe** by `mfe_per_stop`, ignoring price.
2. **Then** mark what buying power reaches as a whole share.
3. **Then** apply the gates and pick from what survives.

- **`mfe_per_stop` and `mfe_to_target` are precomputed** in `data/vol_profile.csv` at the 9:00 refresh. This is a lookup, not a judgement.
- **A stop is a risk normaliser, not a quality signal.** Comparing raw stop widths across instruments compares nothing.
- **State the ratio for the top two candidates at entry**, and **name the top-ranked candidate if it was unaffordable, with the gap.** That number is what tells the governor whether capital is the binding constraint.
- **Deployment percentage is the LAST tiebreaker, never a filter.**
- **`mfe_to_target` above ~2.5× means the target is effectively unreachable** and the trade is a trail-or-stall exit by construction. Say so at entry rather than implying a target that cannot be hit.
- **When the capital base or the thesis changes, the 9:00 shortlist is VOID.** Re-rank from the current tape. Asking "what fits?" instead of "what is best?" ratifies a decision already made.

### ⛔ FRACTIONAL IS PROHIBITED. Whole shares only.

**A fractional position cannot carry a resting stop.** Verified by live orders 2026-08-11:

| Attempt | Result |
|---|---|
| `limit` buy, 0.52 | ❌ `Limit order quantity cannot include fractional shares.` |
| `stop_market` sell, 0.52, `gtc` | ❌ `Invalid time in force for fractional order.` |
| `stop_market` sell, 0.52, `gfd` | ❌ `Invalid trigger for fractional order.` |
| `market` buy/sell, 0.52 | ✅ filled |

**Market orders only, both directions — no limit, no stop, no trigger.** The entire exit model assumes the stop rests continuously at the broker, so a fractional position is a **different risk model**, not a worse version of the same one.

**If the best setup is unaffordable as a whole share, it is not available.** Take the next candidate or no trade.

> **`review_equity_order` accepted both refused orders.** Review does not validate fractional constraints. **A clean review proves nothing about placement** — only an order response is evidence (§15).

### Commodities and materials — TREND-STRUCTURE GATE replaces the catalyst gate

Commodities trend without nameable news, so for **this asset class only** the catalyst requirement is *replaced* — not waived. **All three legs must hold:**

1. **Established multi-session trend** — higher highs *and* higher lows across several sessions. One big day is not a trend.
2. **Confirmation from the related complex** — metal vs miners, crude vs E&P, gas vs producers. Divergence *in the trade's direction* is the strongest form (miners green while the metal is red = the dip is being bought).
3. **Pullback, not breakdown** — inside the prior session's range and **above its low.** Below the prior low it is a breakdown; the trade is off.

- **No named catalyst required.** Do not invent one, and do not decline a qualifying setup for lacking one.
- **Applies only to commodities and materials.** Everything else keeps the catalyst requirement.
- **A replacement, not a relaxation** — the scaled stop, the scaled target, the stall ladder, the circuit breaker, the floor and whole-shares-only all still bind.

### Timing — prefer the morning, never force

- **Preferred window 9:45–11:00am.** Highest volume and conviction, and it leaves the session to manage rather than defend.
- **After 11:00am a new entry must be clearly BETTER than the morning offered**, not merely available because the morning was empty. Boredom is not a signal.
- **NEVER force a trade because the window is closing.** No qualifying setup ends the day with no trade.
- **One round trip per day exists** (T+1, §10). Spend it well, not merely spend it.
- **Late entries commit to an unprotected overnight hold on day one.** Say so at entry.

### Instrument selection

1. **Whole share only** — the most leverage per dollar that fits. Preserves the extended-hours exit and limit orders.
2. **Verify `all_day_tradability` before entering.**
3. **Spread: no rejection gate — PRICE IT IN.** Read the actual bid/ask, **double it for the round trip**, subtract from the expected move, and take the trade only if it still clears the target with room. **Log the actual spread cost on every fill.**
4. **Check the price before building a thesis.** A candidate you cannot buy is not a candidate.

### Universe

- **Index:** TQQQ · SPXL · UPRO · TNA · UDOW
- **Sector:** SOXL · TECL · GUSH · ERX · FNGU · BULZ · LABU · NUGT · GDXU · NRGU · YINN · KORU · USD
- **Single-stock:** NVDL · NVDX · TSLL · CONL · MSTX · SMCX · MUU · AMDL · TSMX
- **Inverse:** SQQQ · SOXS · SPXS · SDOW · TZA · DUST · ERY · YANG · ZSL · JDST · SCO · DRIP · KOLD
- **Commodities / materials:** AGQ · UGL · GLL · JNUG · SIL · SILJ · UCO · BOIL · OILU · OILD · UYM · SMN · COPX · CPER · URA · URNM · LIT · REMX · SLX
- **Crypto proxies:** BITX · BITU · ETHU · ETHT · RIOT · MARA · CLSK
- **Volatility:** UVIX · VXX — **event/intraday ONLY, never a hold.**
- Any liquid high-beta single name with a catalyst.

**An instrument absent from `data/vol_profile.csv` may not be traded** (§2g). Compute it or pick another.

### Asset classes — equities and ETFs ONLY, indefinitely

- **Tradeable: common stock and ETFs**, including leveraged and inverse. That is the whole permitted set.
- **Options are excluded.** Settled, not an open question and not a milestone. Do not propose one, price one, or build a plan needing one. Reading option data as a sentiment signal is fine; placing an order is not.
- **NO SHORT SELLING** — this cash account cannot (§10). Express bearish views via inverse ETFs bought long.
- Only the governor reopens either.

## 5. Order execution

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 6. Stops — UP ONLY, NEVER DOWN

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 7. Profit-taking

- **Target is PER-INSTRUMENT**, from `target_pct` in `data/vol_profile.csv`: `clamp(2.0 × median favourable excursion, 1.5 × stop, 12.0%)`. **At any checkpoint showing a gain at or above it, SELL.**
- **The target is a CEILING, and most trades will not reach it.** The three-check stall (§8.1) closes the majority first, at whatever gain stands. Target is the exit that requires no judgment; it is **not** a reason to keep holding a position the other criteria have already condemned.
- **On reaching it: BANK IT — close the ENTIRE position**, unless there is **named new information** supporting more upside. Momentum does not qualify. Neither does reluctance to sell a winner.
- **Never let the stop become the only exit.** That is drift.
- Profit-taking is **manual at checkpoints**, because the stop occupies the one resting-order slot. The downside must work unattended; the upside can wait 30 minutes.

### Target hit = FULL exit. No scaling out, no runner.

- **Hitting the target closes the WHOLE position, at any share count.** Multiple shares change the dollar amount, never the decision. A runner converts a decided exit into an open-ended hold, and on a decaying leveraged instrument it is the part most likely to give the gain back.
- **The ONLY thing that keeps you in past target is the override: named new information.**
- **If the override fires and you hold 2+ shares, bank half and hold the rest.**

### The override lifecycle — approval starts a clock, not a holiday

1. **Sell half THE MOMENT the override is approved** — not at the next checkpoint. The gain is locked when the decision to stay is made, or the point is lost.
2. **RAISE THE STOP ON THE REMAINDER TO AT LEAST THE TARGET PRICE.** Mandatory, immediate. You chose not to sell at target; the remainder must not be allowed back *below* it, or the override can end up worse than obeying the target.
3. **Re-justify at EVERY checkpoint, out loud.** Name the information again and say whether it is still true, still unpriced, still pointing up. **Silence is expiry** — an override you did not restate is one that has ended, and the remainder gets sold.
4. **Sell the remainder the moment ANY of these is true:** the information is exhausted, contradicted or priced in · **any** §8 criterion fires · the ratcheted stop is hit · a pre-commitment fires · the horizon ceiling is reached.
5. **You may NOT override the override.** One extension per trade. Serial extension is an infinite hold with extra steps.
6. **Log both fills as separate rows** in `data/trades.csv` with the override reason. Report the blended P&L honestly — **if the override earned less than a clean exit at target, say so plainly.** That is the only way to learn whether overrides are worth taking, and the one legitimate exception to §9, because it measures a decision you made rather than tape you did not act on.

> **UNVERIFIED MECHANIC — override case only.** §10's one-resting-order limit was proven on a single share. Whether a stop on *part* of a multi-share position leaves the remainder sellable is **not known**. Before any partial sell, confirm with `review_equity_order` — and remember a clean review is not proof (§15). **If it is refused:** cancel the stop, sell half, immediately replace the stop on the remainder, knowing the position is unprotected in between. Do not discover this mid-trade.

### Holding period

- **DEFAULT FOR A LEVERAGED OR INVERSE INSTRUMENT: CLOSE THE SAME DAY.** Overnight is not the default and is not what happens when a day trade fails to exit.
  - These track a **daily** multiple and reset daily; held across days the return diverges from the simple multiple, worst precisely when volatility is high — which is when we are most likely holding one.
  - **Overnight is completely unprotected** — no stop can rest (§6).
- **Carrying overnight is a SEPARATE DECISION needing a named reason, stated at the 3:30pm checkpoint** while a stop still functions. Acceptable: a multi-day catalyst that has not played out, position still making new highs into the close. **Not acceptable: "the exit criteria did not fire."** That is drift.
- **The one-week ceiling does not apply to leveraged instruments** without evidence a multi-day hold works here. Ordinary equities and ETFs only.
- **Absolute ceiling: 1 trading week**, for an *exceptional* opportunity only, declared at entry. "It's still going up" is not exceptional.
- **State the intended maximum hold at entry**, so it is a commitment rather than a running negotiation.
- **This is predominantly a day-trading system**, with swings as a deliberate exception rather than the plan.

---

## 8. Exit criteria — any one fires

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 9. Post-exit prices — forbidden to the EXECUTOR

**Once a position is closed, do not report, track, or comment on what the price did afterward. Do not compute "would I have been better off holding."**

That is **outcome bias** — an exit's quality is fixed by the information available *at* the decision. It is also actively harmful: logging "it went up after I sold" trains hesitation into future exits.

**Green is green. If the system says sell, sell and move on.**

**The same applies to a candidate you DECLINED.** Checking whether it ran is the same failure in different clothes, and the likeliest route to a forced late entry.

**ONE carve-out, only if an override was actually invoked and acted on (§7):** then compare the realised result against a clean exit at target, and report it honestly including when the override lost money. That is not outcome bias — the target was reached and observed *at the moment of the decision*, so it is a real alternative you consciously declined. **Considering an override and correctly rejecting it does not qualify.**

**If no override was invoked, the comparison is FORBIDDEN** — that covers almost every trade.

*The RESEARCHER does collect post-exit data, retroactively, on Saturday (§17). Statelessness enforces the firewall: tomorrow's EXECUTOR remembers none of it and may not read `EXPERIMENTS.md`. Currently **SUSPENDED** (§16).*

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

> **⚠ MOVED — this section now lives in `OPERATIONS.md`. Read it there.**

## 12. Volatility escalation — authorized

If a position becomes **exceptionally volatile**, you may watch it as long as necessary, **including overnight**.

- Arm extra `send_later` checkpoints at **off-grid minutes** (`:10, :20, :40, :50`) at 10–15 minute intervals, so they can never collide with the standing `:00`/`:30` grid.
- Manage via `all_day_hours` limit orders if the instrument is eligible.
- Stand down to the normal cadence once it settles.

This is the one permitted exception to "do not arm anything."

---

## 13. Runs indefinitely

The loop continues **every trading day until the user explicitly pauses or cancels it.** They set that date, not you. Never stop on your own initiative; no week-end or month-end is terminal.

- **Each 8:00pm checkpoint MUST arm the next trading day** — highest priority, ahead of reporting. Arm the **17-slot standard schedule** (§2). Extended-hours slots are armed only when a position is actually open at 4:00pm, so a normal evening arms 17 and nothing more.
- **SKIP US market holidays**; arm the next real trading day. Upcoming: **Labor Day Mon Sep 7 2026**; **Thanksgiving Thu Nov 26 2026** (**Fri Nov 27 early 1:00pm close**); **Christmas Fri Dec 25 2026**. On early closes, end the regular grid at the early close and skip extended-hours checkpoints. **Verify the calendar** rather than assuming.
- **Friday's final checkpoint arms Monday's grid AND the Saturday 10:00am RESEARCHER pass** (§17).
- **Daylight saving:** the ET times in §2 are authoritative. EDT = UTC−4; after **Sun Nov 1 2026** EST = UTC−5, shifting every UTC slot +1 hour. **Recompute UTC from ET** rather than copying.
- **Month-end is a reporting milestone, not a stop:** report the month, then continue arming.
- If you detect the chain was broken (a gap where checkpoints should have fired), **tell the user plainly and re-arm immediately.**

---

## 14. How success is measured

> **⏸ Measurement is DEFERRED while minimal logging is in force (§16).** The trade log still accumulates, so this becomes computable the moment the governor resumes analysis. Nothing here is abandoned; it is simply not run daily.

- **EXPECTANCY PER TRADE, IN R, is the primary figure — ahead of everything else.**
  - `R = (exit% − entry%) ÷ initial stop distance%`, using the stop set **at entry**.
  - `Expectancy = (win rate × avg winner in R) − (loss rate × avg loser in R)`
  - **Positive expectancy is the only thing that decides whether this works.** Negative expectancy over 30+ trades is a process failure — report it as one and hand the decision to the governor.
- **R is why every risk number is volatility-scaled.** A fixed stop made R mean something different on every instrument, so expectancy could not be summed across them. Scaling is what makes this metric exist at all.
- **Win rate and average winner ÷ average loser are DESCRIPTIVE ONLY.** Never a pass or a fail: 60% at 0.9R is profitable, 40% at 1.2R is not.
- **Exclude rows marked `counts_toward_expectancy=no`, and report which were excluded and why.** Silently dropping trades flatters a record.
- **State the EFFECTIVE sample size, not the row count.** As of 2026-08-11 it is **1 trade**, which supports no conclusion about anything.
- Also track: profit factor · maximum drawdown from peak · slippage both sides · rule adherence.
- **A −25% drawdown from peak is a FLAG, not a brake** (§4) — report it loudly with a written review, keep trading. The brake is 3 consecutive losses; the halt is the 50%-of-deposits floor (§10).

---

## 15. Reporting standards

### ⛔ A CAPABILITY IS VERIFIED BY AN ORDER RESPONSE OR A SUCCESSFUL CALL. NOTHING ELSE.

- **Never** record a capability as verified on the strength of a **review**, **documentation**, or **inference from a similar case**.
- **Never** commit capital or write policy that depends on a mechanism you have not seen succeed.
- **A refusal is evidence too.** Record the exact error string verbatim.
- **Make the smallest call that proves the primitive, before the one that depends on it.**

*Three instances in one session, 2026-08-11: bought AGQ then found its stop refused · recorded "fractional can carry a stop" because a review passed, putting **a false claim into this rulebook** that every cold session would have trusted · wrote a 15-minute bar interval into four files before the first call proved it does not exist.*

### Reporting

- **Report losses as plainly as gains.** No spin.
- **Verified fills only.** P&L in dollars and percent; slippage against intended price.
- **Never claim edge from a small sample.**
- **Correct your own errors promptly**, including ones that look bad.
- **Most checkpoints are non-events — stay silent.** No "checked, nothing to do."

### Cadence

- **Material events report immediately:** entry · exit · stop fired · circuit breaker · error · a break in the checkpoint chain · a balance change indicating funding · a setup notable enough to name though declined.
- **A no-trade day gets NO evening message.** Silence is the correct output.
- **Friday's 8:00pm checkpoint ALWAYS reports**, trades or not: balance, every trade, win/loss and loss-streak count, what was declined and why, any rulebook change. **This is the guaranteed heartbeat** — the only way the governor can tell "correctly sat out" from "silently stopped running."
- **Month-end adds the §14 statistics** — deferred while logging is minimal (§16).

### Known limitations — state honestly when relevant

**No learning from practice** (only the rulebook improves) · **30-minute blindness** between checkpoints · **overnight cannot be automatically protected** · **stops do not protect gaps** · **headlines arrive late and are sometimes undateable** · **one round trip per day** caps trade count regardless of capital · **no demonstrated ability to generate a trade on a no-leadership day.**

---

## 16. The data layer

> ### ⚠ MINIMAL LOGGING MODE — IN FORCE 2026-08-11. Log trades. Nothing else.
>
> **Governor decision: "still store the trade data but don't do anything with it — we'll analyse later."** The operator operates from the rulebook; the observation and feature-collection layer is **SUSPENDED**, not deleted.
>
> | Write | Status |
> |---|---|
> | `data/trades.csv` — one row per closed trade | ✅ **REQUIRED** |
> | `watchlist` record at 9:00 | ✅ **REQUIRED** — it is an operating aid read at 9:45, not analysis |
> | `entry_snapshot` (33 fields) | ⏸ **SUSPENDED** |
> | `checkpoint` record, every check while holding | ⏸ **SUSPENDED** |
> | `catalyst` records | ⏸ **SUSPENDED** |
> | `declined` records | ⏸ **SUSPENDED** |
> | `kill_trigger_fired` records | ⏸ **SUSPENDED** |
> | Saturday RESEARCHER pass | ⏸ **SUSPENDED** |
>
> **What suspension does NOT change.** The trade log is still the circuit breaker's only input, so a missing row breaks the brake. `r_multiple` is still computed at exit while the entry stop is known — it cannot be reconstructed later. And **the derived count still gets STATED in every report while holding** (§8.1); it is simply not written to a file.
>
> **The cost, stated so it is a decision and not a drift:** every suspended record was a defence against a specific bias. `declined` is the only guard against selection bias; `catalyst` is the only way to learn which news is worth trading; `entry_snapshot` is the only way to separate winners from losers by anything other than luck. **Suspending them means the eventual analysis starts from the resumption date, not from today.** That is the accepted trade for a cheaper, faster day.
>
> **Only the governor resumes it.** Do not restart logging because a pattern looks interesting — that instinct is why the layer exists.

| File | Holds | Written by | Mutability |
|---|---|---|---|
| `RULEBOOK.md` · `OPERATIONS.md` | Policy only | Governor | Edited rarely |
| `data/trades.csv` | One row per closed trade | Executor, at exit | **Append-only** |
| `data/vol_profile.csv` | Per-instrument risk numbers | 9:00 checkpoint | Regenerated daily |
| `data/observations.jsonl` | Watchlists now; the rest when resumed | Executor | **Append-only** |
| `EXPERIMENTS.md` | Proposals and evidence | Researcher | Edited |
| `RULE_HISTORY.md` | Every change with its reasoning | **Generated** from git | **Never hand-edited** |

- **`RULE_HISTORY.md` is a rendering of the git log.** Regenerate it; never write to it. **This is where the reasoning for every rule lives** — the policy files carry instruction only.
- **No cached state.** Loss streak, deposited capital and month-to-date are **derived** — the streak from `trades.csv`, the deposit total from the broker (§10). A cached copy goes stale.

### `data/trades.csv` — the one required write

**At exit, append one row. 30 columns.** The essentials, which must never be left blank:

| Field | Note |
|---|---|
| `date_closed`, `instrument`, `shares` | |
| `entry_time_et`, `entry_price`, `exit_time_et`, `exit_price` | From the order responses. Confirmed, never assumed |
| `pnl_usd`, `pnl_pct_position`, `pnl_pct_account` | |
| `initial_stop_pct` | The stop distance set **at entry** |
| **`r_multiple`** | `(exit% − entry%) ÷ initial_stop_pct`. **Compute at exit** — it cannot be reconstructed once the entry stop is forgotten |
| `mae_pct`, `mfe_pct` | Maximum adverse and favourable excursion *during the hold* |
| `hold_minutes`, `stop_initial`, `stop_final`, `target_pct` | |
| `exit_reason`, `stall_count_at_exit` | |
| `slippage_entry`, `slippage_exit` | Against the intended price |
| `rulebook_commit` | `git rev-parse --short HEAD` |
| **`counts_toward_streak`** | `no` **only** for a mechanical abort — an order-plumbing failure, not a chosen exit. A mechanical abort must not reset the circuit breaker |
| **`counts_toward_expectancy`** | `no` for a mechanical abort **or** a funded execution test. A test entry must not enter expectancy |
| `notes` | Say why, whenever either `counts_toward_*` is `no` |

### The watchlist — 9:00, at least 5 names

One `watchlist` record: `ts`, `session_date`, `universe_ranked`, `affordable_count`, and a `names` array of ≥5, each with `symbol`, `rank_overall`, `mfe_per_stop`, `mfe_to_target`, `price`, `affordable_whole_share`, `instrument_class`, `sector_proxy`, `thesis_or_reason`.

`universe_ranked` and `affordable_count` make **the capital constraint measurable rather than asserted.** Read at 9:45 so the entry consults a list built calmly.

### Sector proxy map — for Gate 2 and the sector read

| Instrument | Proxy |
|---|---|
| SOXL · SOXS · USD | SMH |
| NVDL · NVDX · NVDU | NVDA → SMH · **AMDL** AMD · **MUU** MU · **TSMX/TSMU** TSM · **SMCX** SMCI · **AVGX** AVGO — all → SMH |
| TQQQ · SQQQ · FNGU · BULZ · TECL | QQQ |
| SPXL · UPRO · SPXS · SDOW · UDOW | SPY · **TNA · TZA** IWM |
| GUSH · ERX · ERY · NRGU · DRIP · OILU · OILD | XLE · **UCO · SCO** USO · **BOIL · KOLD** UNG |
| NUGT · DUST · GDXU · JNUG · JDST | GDX · **AGQ · ZSL · SIL · SILJ** SLV · **UGL · GLL** GLD |
| LABU | XBI · **UYM · SMN** XLB · **COPX · CPER** copper · **URA · URNM** uranium |
| YINN · YANG | FXI · **KORU** EWY |
| TSLL | TSLA → QQQ · **CONL** COIN → IBIT · **MSTX** MSTR → IBIT |
| RIOT · MARA · CLSK · BITX · BITU · ETHU · ETHT | IBIT, noted as crypto |
| UVIX · VXX | VIX |

**Not on this map?** Name the closest unleveraged proxy and say it was chosen ad hoc. For Gate 2, `limits.json → single_stock_leveraged.map` is authoritative.

### Append-only

- **Never edit or delete a past row.** A mistake gets a correcting row and a note.
- **Adding a column is a MIGRATION, not an edit, and is permitted** — backfilling revises no recorded outcome, which is what append-only protects. Say so in the commit; never change an existing value while doing it.
- **Never evaluate how a DECLINED candidate performed since you declined it**, or a price after an exit (§9). It trains chasing.
- **Never promote an experiment.** Only the governor approves a rule change.

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

### POLICY VERSION: v1.2 — increment on every policy change

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

### ⚠ REGENERATE EVERY CHECKPOINT PROMPT FROM THE CURRENT FILES. Never copy forward last night's text.

**Governor-relevant defect, observed 2026-08-11.** Checkpoint prompts are written at arming time and **cannot update themselves**. Policy changed twelve times during that session, and by mid-morning the armed prompts were issuing retired instructions:

| Trigger | Stale instruction it carried |
|---|---|
| 9:45 entry | *"fractional only if the setup is clearly better"* — **fractional had been prohibited at 9:46** |
| 10:00 management | *"walk the §5 exit precedence"* — exit precedence is **§8**; §5 is order execution |

**Neither caused a wrong action, only because the session reads the rulebook fresh at every checkpoint and the files outrank the prompt.** A session that trusted the prompt over the file would have opened an unprotected fractional position.

- **At the 8:00pm arming, rebuild each prompt's rule content by reading `RULEBOOK.md` and `OPERATIONS.md` as they stand that evening.** Do not paste yesterday's message with the date changed.
- **Prompts are advisory. The files are authoritative.** If a prompt and a file disagree, the file wins, and **say so in the report** rather than resolving it silently — a prompt that contradicts policy is a defect worth surfacing.
- **Keep prompts short and point at the files.** The longer a prompt restates policy, the more of it goes stale. A prompt should say *which* sections to read and *what decision* is due, not re-explain the rules.

---

## Current position

Flat. See `data/trades.csv` for all closed trades and `EXPERIMENTS.md` for open questions.

**Hard floor: 50% of deposited cash** (§10) — deposits recomputed at each 9:00am check.
