# Rule history

**Generated file — do not edit.** Regenerate with `tools/gen-rule-history.sh`.

Every change to `RULEBOOK.md`, newest first, with the reasoning recorded at the time.
The git log is authoritative; this is a rendering of it.

Generated 2026-08-11 06:07 UTC · 24 changes to the rulebook.

---

## 2026-08-11 · `fd7b05c`

**Implement volatility-scaled stops and targets — policy v1.1**

Approved by the governor. EXP-007 and EXP-008 promoted from TESTED to LIVE,
with a 20-closed-trade locked evaluation period per section 17.

The flat 5% stop and +8-12% target are retired. Both now scale to the same
per-instrument volatility measure, because the pair was mismatched on all
fourteen instruments -- every one where +8% was reachable was one where a 5%
stop got shredded, and vice versa.

  stop      = clamp(1.5 x median adverse excursion, 2.5%, 7.0%)
  target    = 2.0 x stop
  breakeven = max(median favourable excursion, 0.5 x stop)
  trail     = 1.0 x median adverse excursion
  EXCLUDE   if 1.5 x median MAE > 7.0%

The breakeven floor of half the stop exists because moving the stop to
breakeven at a gain smaller than normal retracement just scratches the
position on noise.

The old ratchet is replaced by one trigger and a trail. Rungs at +5%, +8%,
+10% and +12% were dead code -- +8% occurred in zero of 21 sessions for GUSH,
ERX, NUGT, NRGU, DUST and YINN -- so the ladder was already a single rung in
practice and is now written as one. Minimum stop move of 0.5% bounds
cancel-and-replace churn.

SOXL is excluded outright: its median adverse excursion of 6.6% is wider than
the 7% hard cap, so no permissible stop survives an ordinary session. That is
a conclusion, not an omission.

RECOMPUTED, NOT FROZEN -- the point the governor insisted on. tools/vol_profile.py
derives the numbers, data/vol_profile.csv holds them, and a new 9:00am subtask
(g) refreshes it from ~20 sessions of daily bars each morning. SOXL ranged from
$196 to $91 inside the window that produced the first profile; a hardcoded
table would be a fixed guess wearing a formula. An instrument with no profile
row may not be traded, and there is no fallback default.

preflight.py now checks the instrument's own profile rather than a flat
ceiling. Verified: GUSH at the scaled 3.0% stop ALLOWs; GUSH at the old flat
5% now DENYs on stop mismatch; SOXL DENYs on exclusion.

Honest scope, restated in the rules: replay showed this moves expectancy by
about +0.01R, which is noise. It is a risk-consistency fix, not a return fix.
Its value is that R finally means the same thing across instruments, which is
what makes the expectancy metric meaningful at all.

---

## 2026-08-11 · `611cdeb`

**Fix cadence at 30 minutes, flat or holding**

Governor decision: the cadence is 30 minutes after 10:00 and does not change
when a trade is entered. Removes both the 15-minute densification while
holding and the conditional 10-minute densification near a stop or ratchet
threshold.

Standard schedule is now 17 checkpoints armed every evening, plus 7
extended-hours slots armed only when a position is actually open at 4:00pm.

The replay evidence supports this rather than merely permitting it: GUSH
2026-08-05 took the same exit for the same reason at 10, 15 and 30 minutes,
for -0.60R, -0.58R and -0.61R. A threefold range of cadence moved the outcome
0.03R. Because the stall clock runs on market time, waking more often cannot
change when the ladder fires -- it only changes when the same decision gets
executed.

Cost stated honestly: average delay to act on a newly crossed ratchet
threshold is about 15 minutes, so a threshold crossed at 10:07 leaves the stop
unmoved until 10:30. Accepted, and the replay says the price is small.

24 checkpoints on a holding day is the same count as the original fixed grid,
but the rulebook partition cut the per-checkpoint read from ~78KB to ~23KB, so
it costs roughly 57% less than the same count did before the split.

Section 12 volatility escalation is untouched -- it is a separate prior
authorisation for exceptional cases, not a cadence default.

Also fixed stale text the change exposed: a section heading that still said
"arm sparse, densify on entry", the arming instruction still specifying a
13-slot baseline, and partition sizes quoted from before the file grew.

---

## 2026-08-11 · `0bc1cc8`

**Fix the section 2 schedule table**

Three rows were missing the Reads column added when the rulebook was
partitioned, leaving the table malformed. The extended-hours row also still
described a fixed six checkpoints, which the state-dependent cadence
replaced -- those slots are now armed only when a position is held.

---

## 2026-08-11 · `6d0ef4b`

**Partition the rulebook into a hot path and a policy file**

The rulebook grew from 19KB to 75KB today acting on the review. Every
checkpoint re-reads it from scratch, so per-checkpoint cost had roughly
quadrupled -- and cadence is a linear multiplier on that cost. Fixing the
per-session read buys more than tuning the multiplier.

Sections 1, 3, 5, 6, 8 and 11 -- trigger hygiene, early shutdown, order
execution, stops, exits, headlines -- MOVED to OPERATIONS.md. Moved, not
copied: each rule now exists in exactly one file, so the two cannot drift
apart. Section numbers are unchanged, so every existing (section n)
cross-reference still resolves, and no renumbering churn touches the role
files or the armed triggers.

Done with a script rather than by hand, because transcribing 40KB of rules
manually is how a rule silently changes.

Measured effect on policy reading per day:
  holding day, 15-min cadence:  608K -> 248K tokens  (60% less)
  flat day:                     282K -> 134K tokens  (53% less)

Two gaps the split exposed and closed:
- A management checkpoint reading only OPERATIONS.md would not have known it
  must log anything, since the logging obligation lived in section 16. The
  checkpoint-record fields moved across; the full schemas stayed in the
  rulebook, with section 16 pointing at OPERATIONS.md rather than repeating
  the fields.
- OPERATIONS.md now states in a banner that a new position may NOT be opened
  from it alone -- entry needs the section 4 gates, instrument selection, the
  33-field snapshot spec and the catalyst schema. The cheap path covers
  managing and exiting; the expensive path covers committing capital.

Also added CONDITIONAL 10-MINUTE DENSIFICATION, which the partition pays
for: drop to 10 minutes only within 1% of a ratchet threshold, within 1.5%
of the stop, in the final hour holding with an overnight decision pending, or
under section 12 volatility. Recorded why uniform 10 minutes is refused --
it changes the exit rule not at all now that the stall clock runs on market
time, the average latency gain from 15 to 10 is 2.5 minutes for 50% more
sessions, and every extra checkpoint is another cold session that can talk
itself out of a sound position. More looking is not more discipline.

Fixed stale text the split surfaced: the header claiming every checkpoint
reads this file, the "24 checkpoints" section title, a "12 standard
checkpoints, every 30 min" row, and duplicate section numbering in
RESEARCHER.md.

---

## 2026-08-11 · `700d2fa`

**Complete the review: sandbox risk label, day-trade default, rule layers, version locking, and a preflight checker**

Items 8 through 13 of the review feedback.

SANDBOX-ONLY RISK MODEL (section 0). Resolves a contradiction introduced
earlier: "judge every rule as if the account were 10x" and "all-in, so stop
distance is the only risk lever" cannot both be right. Design-for-scale now
explicitly applies to rules and metrics but NOT to sizing. Records the
arithmetic -- three consecutive 5% losses is -14.3%, three 7% losses is
-19.6% -- and lists what must change before real money: position size as an
independent lever, concentration limits, the -25% flag becoming a brake, a
far tighter floor, and deletion rather than reinterpretation of the
"stop distance is the only lever" line. Sizing is not to be raised
incrementally as the balance grows; it is a deliberate redesign.

LEVERAGED POSITIONS CLOSE SAME DAY BY DEFAULT (section 7). Leveraged funds
target a daily multiple and reset daily, so multi-day returns diverge from
the simple multiple, worst when volatility is high -- which is when we are
most likely to be holding. Overnight is now a separate decision requiring a
named reason stated at 3:30pm while a stop still functions. "The exit
criteria did not fire" is explicitly not a reason. The one-week ceiling no
longer applies to leveraged instruments without evidence.

Note for the governor: this narrows the swing-trading half of the original
mandate. Implemented in the softer form -- overnight permitted with stated
justification rather than banned -- since the stall ladder already produced
this outcome in practice and this states it as intent.

RULE LAYERS (section 10): universal, asset class, category, instrument, with
guidance to place a rule at the narrowest level where it is true. The
category layer is deliberately near-empty; per-sector models arrive through
EXPERIMENTS.md with evidence, not improvised at a checkpoint.

MARGIN WARNING (section 10): all settlement facts are verified for this cash
account only. A reviewer's claim that FINRA margin day-trading rules changed
in June 2026 is recorded as UNVERIFIED, since it cannot be confirmed from
here. Any move to margin requires re-verifying from primary sources first.

POLICY VERSIONING AND A LOCKED EVALUATION PERIOD (section 17). Policy is now
v1.0. After a rule changes it may not change again for 20 closed trades
unless the governor overrides. Without this the loop becomes trade, lose,
adjust, repeat -- a machine for fitting yesterday. Records honestly that the
stall rule changed three times in one session, that this was acceptable only
as pre-deployment design on an untested rule, and that the same pace becomes
forbidden once live trades exist.

PREFLIGHT CHECKER (limits.json, tools/preflight.py, section 5). Deterministic
pre-order checks: loss streak COMPUTED from trades.csv rather than
remembered, the floor, one position and one resting order, stop present and
inside the 7% ceiling, affordability, order type, universe membership.
Tested against a valid entry, an over-wide stop, and an unaffordable
off-universe market order with no stop.

Documented plainly as a TRIPWIRE, NOT A GATE: broker orders go through tools
the script cannot intercept, so nothing forces it to run and nothing stops a
DENY being ignored. What it buys is deterministic arithmetic and a visible
trace when it is skipped or overridden. Real enforcement would require the
order path to run through code that can refuse, which is not available here.

---

## 2026-08-11 · `824270a`

**Decouple data resolution from wake cadence; stall clock on market time**

The review identified a circularity: checkpoints were 30 minutes apart, the
stall was defined from 30-minute bars, and three stalls forced an exit -- so
the exit rule's timescale was an artifact of the schedule rather than a claim
about the market.

The correctness fix has to come first, because decoupling the cadence breaks
the stall rule otherwise. A stall is now measured in 30-minute windows of
MARKET TIME, anchored to the clock at :00 and :30, built by aggregating
5-minute bars. Waking more often no longer advances it. Without this,
switching to a 15-minute cadence would have fired the exit after 45 minutes
instead of 90 -- silently a different rule with no edit to the rule.

Bars are now always collected at 5-minute resolution and aggregated up,
deliberately so the window length stays a free parameter rather than a
property of the data.

Cadence becomes state-dependent:

- Baseline armed each evening assumes flat: 13 checkpoints, dense through
  the 9:45-11:00 preferred entry window, then hourly, since after 11:00 an
  entry must clear a higher bar anyway and a flat checkpoint can only report
  that nothing qualified.
- On entry, the entering checkpoint arms 15-minute fill-ins for the rest of
  regular hours. Stated reason: a ratchet threshold crossed at 10:07 sits
  unacted-on for 23 minutes at 30-minute spacing.
- Carrying overnight arms the holding schedule for the next day.

This is cheaper, not more expensive. A flat day costs 13 checkpoints instead
of 24; a day that enters at 9:45 and exits at 1:00 runs dense for three hours
and then early shutdown deletes the rest. Only one round trip per day is
possible, so the dense period is always short and bounded.

The baseline is deliberately sufficient to manage a position on its own, so a
failure to densify degrades coverage rather than removing it.

cadence_min is recorded on every observation so the question can be settled
later. Seeded EXP-005 (is 30 minutes the right window -- noting the value is
inherited from the old checkpoint spacing and has no empirical basis) and
EXP-006 (does cadence change outcomes, noting more frequent is not
automatically better since each extra check is a chance to talk oneself out
of a sound position). Both are answerable by replay because 5-minute bars are
stored, and both carry a warning that testing several parameter values
against a small history is several chances to find a winner by luck.

Takes effect from the next arming checkpoint; days already armed on the fixed
grid run as armed.

---

## 2026-08-11 · `a73050d`

**Structure catalysts as data, and log them whether traded or not**

"A nameable catalyst" is a sound guardrail and an unmeasurable one -- almost
anything can be narrated as a catalyst after the fact. This converts it into
structured records that can be scored by category.

- A `catalyst` record for every catalyst identified, INCLUDING ones not
  traded. Logging only traded catalysts would leave the same selection bias
  as logging only taken trades: the sample would contain only news already
  believed in, so no category could ever be shown worthless.
- 18 fields: type, direction, scheduled-or-surprise, source and discovery
  times with an explicit confidence flag on the source time, age, affected
  instrument and underlying, direct-versus-indirect relevance, an
  expected_move_pct prediction, expected duration, and a 1-5 confidence
  recorded on the stated assumption that it is probably uncalibrated.
- Classification rules so categories stay consistent: record the proximate
  cause rather than the mechanism, sector_sympathy only for another
  company's news, and `other` above roughly 15% of records is treated as
  evidence the taxonomy itself is wrong.
- Outcomes are SEPARATE append-only records referencing the catalyst id,
  never edits to the original, measured Saturday by the Researcher at
  +15/+30/+60/+120 minutes and to the close.
- A fired section 11 kill trigger now logs a `kill_trigger_fired` record.
  These are the system's highest-conviction exits and nothing so far records
  whether any of them has ever been right.

One new prohibition, found while writing this: the Executor may not evaluate
how a declined candidate has performed since declining it. That is post-exit
tracking wearing different clothes -- it trains chasing rather than
hesitation, and it is the likeliest route to a forced late entry. The
Researcher scores declined candidates on Saturday instead.

Seeded EXP-002 (do catalyst categories differ in hit rate), EXP-003 (does
catalyst age predict anything), EXP-004 (is stated confidence calibrated at
all -- where a negative result is the more valuable one). Each carries a
sample count of zero and an explicit trap to avoid, since eleven categories
against a few dozen observations guarantees one looks terrible by chance.

---

## 2026-08-11 · `588ddb8`

**Specify the entry snapshot, and log declined candidates too**

The data layer previously named the entry-snapshot fields but not how to
compute any of them, which left a cold session to invent a method and would
have produced fields that were not comparable across trades.

Now a full spec: 33 fields with the exact derivation for each, a worked JSON
example verified to match the spec field-for-field, and an unleveraged proxy
map so sector context is measured against SMH, XLE, QQQ, GDX and so on
rather than against whichever index the session happened to pick.

Notable fields: trend over 5/15/30/60 minutes plus a trend_alignment count
of how many horizons share the trade's direction, which is the specific
hypothesis the review suggested; position_in_range, so entering at the high
of the session is distinguishable from entering at the low; spread at entry;
and catalyst type, direction, scheduled-or-surprise, source time and age.

Two disciplines recorded alongside:

- FEATURES, NOT RULES. Nothing in the snapshot gates a trade. It is an
  explicit violation to decline or size a trade because a snapshot field
  looks bad unless that field is already a section 4 gate -- letting a
  logged feature influence judgment converts it into an unapproved rule
  while leaving no trace that a rule was added. Patterns become rules only
  through EXPERIMENTS.md and governor approval.
- DECLINED CANDIDATES are now logged: one record per checkpoint that
  considered a candidate and passed, with the failing gate. Without them the
  dataset contains only trades that were taken, so every conclusion drawn
  from it is selection-biased -- we could measure how entries performed but
  never whether the filters were discarding winners. Costs one short record
  and no extra tool calls.

Also recorded a known weakness rather than hiding it: volume_vs_session is
not time-of-day adjusted, so early-session values run high.

RESEARCHER.md gains the task of analysing features and declined records, and
is named as the only role permitted to look for patterns in them.

---

## 2026-08-11 · `6b1131e`

**Make expectancy the primary metric; demote win rate to descriptive**

The previous section made win rate the headline metric and required an
average winner of at least 1.2x the average loser. That was wrong, and the
arithmetic in the review demonstrates it:

  60% win rate at 0.9R:  0.60*0.9 - 0.40*1.0 = +0.14R  profitable, but
                                                        fails the old rule
  40% win rate at 1.2R:  0.40*1.2 - 0.60*1.0 = -0.12R  loses money, but
                                                        passes the old rule

The old metric could be failed by a winning system and satisfied by a
losing one. Neither number means anything alone.

Expectancy per trade in R is now the primary figure, with R defined as the
stop distance accepted at entry and never recalculated afterwards, so that
ratcheting a stop to breakeven shows up as a smaller loss rather than as
smaller risk. Reported alongside it: profit factor, max drawdown, rule
adherence, slippage and sample size. Win rate and the win/loss ratio remain
reported but are explicitly descriptive and target nothing.

Two further reasons recorded in the file. A headline win rate rewards being
right, and trading pays the distribution of money rather than correctness,
so optimising win rate pushes toward cutting winners early -- the exact
drift the exit rules exist to prevent. And expectancy is the metric that
credits this system's own design, since the breakeven ratchet converts
would-be losses into ~0R scratches, which a win/loss ratio barely registers.

A negative expectancy over 30+ trades is defined as a process failure,
reported to the governor rather than triggering an automatic halt.

trades.csv gains initial_stop_pct and r_multiple, computed at exit while the
entry stop is known. The Aug 10 trade backfills to +0.6918R (+3.2465%
against a 4.6926% initial stop).

---

## 2026-08-11 · `c96cfb9`

**Split Executor and Researcher roles; scope the post-exit ban by role**

Adds the authority firewall from the review: one model, two roles at
different times, with the human as the only party that can promote a rule.

- EXECUTOR.md: the trading role. May trade and log; may not look at
  post-exit prices, read EXPERIMENTS.md, optimise, or change policy.
- RESEARCHER.md: the analysis role, Saturday only. May measure anything
  including post-exit prices; may not place an order or edit RULEBOOK.md.
- RULEBOOK section 17: the firewall, the promotion path, and a table
  separating what is actually enforced from what is only documented.

Section 9 previously banned post-exit price tracking outright. That is a
good execution rule and a bad research rule, so it is now scoped by role:
forbidden to the Executor, required of the Researcher.

Three deliberate departures from the proposal as written:

- The research pass runs Saturday rather than weekday evenings. Extended
  hours orders are still live on a weekday evening; on Saturday the market
  is shut, so "the Researcher cannot trade" becomes a fact about the
  calendar instead of a promise.
- Post-exit prices are collected retroactively from historical bars, not
  captured live. Capturing them live would require the Executor to see the
  very numbers it is forbidden to consider. Statelessness then does the
  rest: tomorrow's Executor cannot remember what Saturday's Researcher saw.
- Both role files and section 17 state plainly that most of the separation
  is documented rather than enforced, because send_later cannot restrict
  tools and every session comes up with the identical tool set. Violations
  would be detected, not prevented. The firewall is not described as a
  technical guarantee anywhere.

Friday's arming checkpoint now arms Monday's grid plus the Saturday pass,
and armed trading messages must point at EXECUTOR.md alongside the
rulebook. The first research pass is armed directly for Sat 15 Aug so it
does not depend on the new rule propagating through the chain.

---

## 2026-08-11 · `15fc044`

**Separate history from policy: add the data layer**

Acts on review feedback identifying the central architectural confusion in
this design: it conflated "the LLM must have no memory" with "the system
must have no memory." The first is a fact about the operator. The second
was an accident, and it meant history lived inside the policy file mixed in
with the rules.

Five stores, separated by lifecycle and reader:

- RULEBOOK.md now holds rules and verified mechanics only.
- data/trades.csv, append-only, one row per closed trade with 26 fields --
  MAE and MFE during the hold, time held, both slippage figures, catalyst
  type and direction, exit reason, stall count at exit, and the rulebook
  commit in force at the time. Seeded with the Aug 10 GUSH trade; its
  MAE/MFE are recorded as unknown rather than backfilled, since they
  predate the observation layer.
- data/observations.jsonl, append-only, one record per checkpoint while
  holding plus an entry snapshot. Explicitly features, not rules -- to be
  collected now and reasoned about only once there is evidence.
- EXPERIMENTS.md, with a state lifecycle where only the human governor can
  move an entry to APPROVED, a requirement to state sample size and how
  many hypotheses were tested against the same data, and an exemption so
  safety defects are fixed immediately rather than queued as experiments.
  Seeded with EXP-001, the open question of whether the stall exit belongs
  at three checks or four.
- RULE_HISTORY.md, GENERATED from git log by tools/gen-rule-history.sh and
  never hand-edited. The review proposed maintaining it by hand; generating
  it instead avoids a second source of truth that would eventually
  contradict the commits it describes.

Also removed all cached state from the rulebook. Loss streak and trade
history are read from trades.csv, deposited capital is recomputed from the
broker each morning. A cached copy is a copy that goes stale, and the
derivation is a single file read.

Four stale references to the old in-file trade log were repointed.

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

