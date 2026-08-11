# Rule history

**Generated file — do not edit.** Regenerate with `tools/gen-rule-history.sh`.

Every change to `RULEBOOK.md`, newest first, with the reasoning recorded at the time.
The git log is authoritative; this is a rendering of it.

Generated 2026-08-11 02:49 UTC · 13 changes to the rulebook.

---

## 2026-08-11 · `87a1e2a`

**Specify how a cold checkpoint derives the stall count**

The stall count is per-position state and nothing carries it between
checkpoints -- each one is a fresh session with no recollection of the
last. The rule said what to do at two and three stalls but never said how
a session that cannot remember either one arrives at the number, which
left the most consequential value in the system undefined at the moment it
is needed.

It is now derived from 30-minute bars on every check: walk forward from
entry tracking the running high, mark a bar stalled when its high fails to
exceed the running high by more than 0.3% and its volume is below the
prior bar, skip bars inside the midday exclusion window, and take the
consecutive run ending at the present. Any qualifying new high resets it.

The derived count and the bars behind it must be stated in every report
while holding, since deriving it silently would make it unauditable and a
wrong count either sells a good position or holds a dead one.

---

## 2026-08-10 · `5e7fee2`

**Set the hard floor to 50% of deposited cash**

Raises the floor from 35% to 50%, currently $20.42. This is a real change
in risk level rather than a change of form: the system halts after losing
half of contributed capital rather than roughly two thirds.

Also makes the denominator unambiguous, since the previous wording could be
misread. The base is the cash deposited, never the current account value --
account value is used only to derive the deposit figure. Stated explicitly
that the floor does not rise with gains: at $80 of account value the floor
is still $20.42, because it limits how much of the user's own money can be
lost rather than acting as a trailing stop, and a floor that ratcheted up
with profits would liquidate on an ordinary drawdown from a high.

---

## 2026-08-10 · `03eaf61`

**Express the hard floor as a percentage of deposited capital**

Replaces the fixed ~$15 floor, which was a small-account artifact and the
only dollar-denominated threshold left in the document. The floor is now
35% of deposited capital, calibrated to match the previous figure at the
current deposit total.

Deposited capital is not exposed as an API field -- there is no cumulative
deposits value, and pending_deposits covers in-flight money only. It
derives as total value less all-time realized P&L less unrealized P&L.
Validated against the account: $42.07 total less $1.23 all-time realized,
flat, gives $40.84, confirmed as the exact amount deposited. The formula
also stays correct as funding is added, since a deposit raises total value
without touching realized P&L.

The figure is recomputed at the 9:00am check and recorded in the trade log,
with any disagreement between recorded and derived values reported rather
than silently resolved. Funding detection now also updates it, since a
stale denominator means a floor set against the wrong number.

---

## 2026-08-10 · `6b46305`

**Log stall-2 resumptions and add a design-for-scale principle**

Keeps the three-check stall sell and instruments the open question behind
it. Every stall-2 event is now logged with the gain at the time and
whether the position made a new high before the third stalled check. That
yields a resumption rate, which is the only thing that can settle 3 checks
versus 4 -- break-even is roughly 33% and the current answer is a prior,
not a measurement. The log is in-trade data, so it needs no exception to
the no-post-exit-tracking rule.

Adds an explicit design principle: the system is being trained for much
larger sums, so rules are judged as though the account were 10x its
current size. A +2% win is significant on its own terms, and reasoning
from the current dollar balance to a change in strategy is invalid -- it
optimises for an account size meant to be temporary and trains
variance-seeking that would be harmful at scale. Recorded that thresholds
belong in percentages rather than dollars, and listed the rules currently
dormant for lack of size so they are not dropped for being unused.

---

## 2026-08-10 · `5de0f6e`

**Replace the stall floor with a two-step escalation ladder**

The +5% profit floor on the stall exit is retired. It required holding a
stalling green position at full stop width, which meant risking 5% to gain
another 3% on a position that had already stopped moving.

New rule:
- Two stalled checks raise the stop to breakeven and keep holding, which
  converts the stall signal from "sell" into "protect" and eliminates the
  downside without giving up the upside.
- Three stalled checks sell unconditionally, at any gain. Safe precisely
  because the stop is already at breakeven by then, so the rule can only
  cost upside, never a loss.

Supporting definitions, added because each would otherwise be exploitable:
- A new high must exceed the prior high by more than 0.3% to count as
  progress and reset the stall counter.
- Checks between 12:00 and 1:30pm ET do not count toward the stall total.
  Volume structurally dies over lunch, so counting it would sell nearly
  every position held through midday for no informational reason.
- The volume component of the stall test is retained.

Also added the full ratchet ladder to section 6, which the breakeven rule
depends on: scheduled stop levels by gain reached, structural overrides
permitted upward only, and a cadence rule so the stop is not moved on
every check.

Two consequences recorded rather than left to be discovered:
- Win rate becomes the headline metric and the winner/loser target drops
  from 2:1 to 1.2:1, with 1:1 still a hard failure. Most winners will land
  at +2-5% rather than at target, so 2:1 is no longer producible.
- This is now predominantly a day-trading system. An overnight hold only
  happens when a position is still making new highs into the close.

Reversal is narrowed to what the ratcheting stop cannot cover -- extended
hours, overnight, and headline gaps -- and now requires that the level was
named at entry, since otherwise the claim is unfalsifiable.

---

## 2026-08-10 · `4593715`

**Restore the stall-exit floor and the 2:1 winner/loser requirement**

Corrects a misread of the stall-rule decision. The intent was to affirm
that a multi-period stall and a reversal are both genuine exits, within
the recommended framework -- not to remove the profit floor beneath the
stall exit.

- The stall exit again requires roughly half the target (~+5%) on a green
  position that has not reversed. Below that a stall alone is insufficient.
- The floor is waived, and the stall fires at any level, when price is at
  or below entry or when a reversal is present. Reversal always outranks
  the floor.
- Restored the average winner >= 2x average loser requirement, with 1:1 as
  hard failure, and recorded that it is reachable only because the floor
  exists. Noted that removing the floor requires lowering the metric in
  the same edit, since the two are load-bearing for each other.
- Target reframed as a ceiling rather than a guarantee, now that the floor
  means fewer trades close early on a stall.

---

## 2026-08-10 · `70a9262`

**Define initial stop placement, entry timing, and spread handling**

Closes the gaps identified in the logic audit. Four decisions applied:

- Initial stop: 5% below fill by default, tightened to structure only when
  a level is nearer, hard ceiling of 7% never to be exceeded. A setup
  needing more room is declined rather than entered and widened. The stop
  price and percentage are stated at entry, since previously the document
  covered only how to move a stop and never where to place one.
- Stall and reversal exits fire at any profit level, with no minimum gain
  and no waiting for target. Target is reframed as a ceiling rather than a
  destination, since most trades will close before it.
- Spread has no rejection gate: double the quoted spread for the round
  trip, subtract from the expected move, and take the trade only if it
  still clears target with room. Actual spread cost logged per fill.
- Entry timing prefers 9:45-11:00; later entries must beat what the
  morning offered, and no trade is ever forced to fill the window.

Also corrected the winner/loser ratio target from 2:1 to a 1:1 failure
threshold, with the reasoning recorded. 2:1 is unreachable now that stall
exits bank winners small while the stop permits a 5% loss. The exit
discipline is worth more than the metric, and a metric the process cannot
produce invites holding winners longer to flatter it.

Cleanups: the macro-driver block is now marked as a replaceable slot
rather than a permanent fixture, the fixed-sizing note replaces advice to
reduce position size, and the spent-trigger uncertainty is replaced with
what was actually observed.

---

## 2026-08-10 · `e98e0af`

**Restrict the post-exit comparison to invoked overrides only**

Tightens the carve-out added in the previous commit so it cannot be read
as general permission. The comparison against a clean target exit is
forbidden unless an override was actually invoked and acted on. Normal
target exits, stops, stalled-momentum exits, pre-committed exits and
deadline exits all fall under the default rule: the price afterward is
irrelevant and is not to be looked at.

Considering an override and correctly rejecting it does not qualify --
the test is whether a choice was made against a price already observed.

---

## 2026-08-10 · `c41c6f0`

**Define the profit-target override lifecycle**

Keeps the override-case partial sell and specifies what governs the
remainder afterward, so approving an override cannot become an
open-ended hold:

- Sell half at the moment the override is approved, not later.
- Raise the stop on the remainder to at least the target price, so the
  override can never end up worse than simply obeying the target.
- Re-justify the override out loud at every checkpoint; an override that
  was not restated has expired and the remainder is sold.
- Sell the remainder when the new information is exhausted, contradicted
  or priced in, or when any existing exit criterion, the stop, a
  pre-committed condition, or the horizon ceiling fires.
- No overriding the override: one extension per trade, since serial
  extension is an indefinite hold with extra steps.
- Log both fills with the override reason and report the blended result
  honestly, including when the override underperformed a clean exit.

Added a narrow carve-out to the no-post-exit-tracking rule for that last
point. Comparing an override against the target is not outcome bias --
the target price was observed at decision time, so it is a real declined
alternative rather than subsequent tape.

---

## 2026-08-10 · `036d59b`

**Target hit closes the whole position; remove scaling out at target**

Reaching the +8-12% target now exits the entire position regardless of
share count. The previous rule banked half at target and let a remainder
run behind a ratcheted stop, which reintroduced the drift the exit rules
exist to prevent -- it converted a decided exit into an open-ended hold,
and on a decaying leveraged instrument the remainder is the part most
likely to give the gain back.

Partial sells now exist in exactly one circumstance: when the existing
named-new-information override fires and the position is 2+ shares, bank
half rather than holding all of it. That is strictly more conservative
than the override already permits.

All other exit criteria are unchanged and still fire first -- stalled
momentum, reversal, flipped risk/reward, the 7:30pm deadline, an
approaching event, the ratcheting stop, and the pre-commit rule.

Rescoped the unverified partial-sell-with-resting-stop mechanic to the
override case, which is now the only place it applies.

---

## 2026-08-10 · `12debb1`

**Add loss-streak circuit breaker, fractional exception, reporting cadence**

Resolves open questions and inconsistencies found in a full audit:

- Fractional shares: whole share stays the default, but fractional is now
  explicitly permitted when the setup is materially stronger than anything
  affordable whole, with the cost stated at entry (market order only,
  regular hours only, no overnight exit) and a tighter leash to match.
  Reconciles section 4 with the earlier instruction not to let whole-share
  sizing block the best available trade. Also added a rule to check price
  before shortlisting, since much of the listed universe is unaffordable
  whole at a small balance.
- Circuit breaker: three consecutive losing closed trades halts new
  entries until cleared. Defines what counts as a loss, that the count is
  trades rather than days, and that pausing entries never pauses the
  system -- checkpoints keep running and the arming checkpoint stays alive.
  A -25% drawdown is now explicitly a flag, not a brake; the two were
  previously ambiguous about which one stopped trading.
- Reporting cadence: material events reported as they occur, no evening
  message on a no-trade day, and a guaranteed Friday recap so a silent
  failure cannot be mistaken for a quiet market.
- Assigned ownership of the dated live-context block, which said to
  refresh itself but named nobody to do it.
- Flagged the partial-sell-with-resting-stop mechanic as unverified, with
  a fallback sequence, so it is not discovered mid-trade.
- Recorded that overnight gap risk is known and accepted, to stop it being
  re-raised at checkpoints as though it were new.

---

## 2026-08-10 · `56ea002`

**Encode hold horizon, scaling out, asset-class scope, and funding detection**

Applies four settled decisions to the rulebook:

- Hold horizon: default 1-2 days, absolute ceiling of one trading week
  reserved for exceptional setups, with the intended maximum stated at
  entry so it is a commitment rather than a running negotiation.
- Scaling out: once the balance supports 2+ shares, bank roughly half at
  target and let the remainder run behind a ratcheted stop. A single share
  can only go all-in or all-out.
- Asset classes: equities and ETFs only, indefinitely. Options are
  excluded as a settled decision, not a milestone to graduate past.
  Reading option data for sentiment is allowed; placing an option order
  is not. Annotated the account's option_level_2 as descriptive only so a
  future checkpoint does not read it as permission.
- Funding detection: a balance increase at the 9:00am check that trading
  does not explain means the account was funded. Size to it and note it
  in the report; never ask for or campaign for funds.

---

## 2026-08-10 · `6789cbf`

**Add canonical trading rulebook as single source of truth**

Replaces the self-copying checkpoint prompt with one authoritative
document that every scheduled checkpoint reads. The previous design
carried the full ruleset forward in each 8pm arming message, which
could degrade over many iterations if any run summarized rather than
copied verbatim.

Covers objective, the 24-checkpoint daily grid with the 9:00/9:30/9:45
morning funnel, early-shutdown and trigger-hygiene rules, entry
criteria and instrument universe, stop discipline (up only), profit
taking, exit criteria with the pre-commit rule, verified account
mechanics (no shorting, one resting order, T+1 settlement, 24-hour
tradability), monthly evaluation metrics, and reporting standards.

---

