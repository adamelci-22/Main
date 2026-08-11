# OPERATIONS — the intraday hot path

**Read at every management checkpoint. Authoritative for everything in it.** Section numbers are global, so `(§6)` means the same in both files.

| Here | In `RULEBOOK.md` |
|---|---|
| §1 triggers · §3 shutdown · §5 execution · §6 stops · §8 exits · §11 headlines | §0 objective · §2 schedule · §4 entry · §7 targets · §9 post-exit · §10 mechanics · §12–17 |

> **YOU MAY NOT OPEN A POSITION FROM THIS FILE ALONE.** Entry needs the §4 gates, class priority and instrument selection — all in `RULEBOOK.md`. Managing and exiting is fully covered here.

**Also read `RULEBOOK.md` when:** entering · 4:00pm report · 8:00pm arming · an override fires · anything ambiguous.

> **This file is INSTRUCTION ONLY. The reasoning for every rule is in the git commit that introduced it**, rendered in `RULE_HISTORY.md`. If you want to know *why*, look there — do not expect it here, and do not re-add it. Every KB here is re-read up to 24 times a day.

---
## 1. Step Zero — trigger hygiene, before anything else

Call `list_triggers`.

1. **DELETE every trigger with `ended_reason='run_once_fired'`.** An unreadable list is where a real duplicate hides, and two checkpoints on one setup can place two orders.
2. **DELETE any trigger occupying a slot you are about to arm.** Exactly one per slot.
3. **NEVER delete the trigger you are running from** until the next day is armed.
4. After arming, list again, confirm one per slot, report the count.

**A past-due trigger still `enabled` with `ended_reason=None` is a MISSED checkpoint, not a pending one.** A trigger cannot deliver into a session already generating a turn — a long turn silently eats the slot. When you find one: do that checkpoint's work now, say in the report that it was missed and why, then delete it so it cannot fire mid-turn later.

- **Do not start work that will outlast the current slot.** Near a boundary, finish and reply; continue at the next checkpoint.
- **Never silently absorb a missed checkpoint.** A vanished checkpoint looks exactly like a quiet day.
- **A BACKUP ARMING TRIGGER is armed 20 minutes after every 8:00pm slot.** It no-ops if the day is already armed. Each arming re-arms the next one. **Never delete it without confirming the primary fired.**

---
## 3. Early shutdown

> ### OUT OF BUYING POWER = THE DAY IS DONE. A stop-work rule, not a suggestion.

**Delete the remaining intraday checkpoints when all of:** flat · no resting orders · settled buying power cannot fund an entry.

They can only report "nothing to do," and no headline changes that — T+1 means today's proceeds are not spendable until tomorrow. Continuing to wake invites the worst failure available: talking yourself into an entry funded by unsettled proceeds, which is how a good-faith violation happens (§10).

**Keep exactly three slots: the 4:00pm report, the 8:00pm arming, its 8:20pm backup.**

- **If flat at 4:00pm, delete 4:30–7:30** even after a no-trade day. No new positions after hours.
- **If flat but buying power is sufficient, KEEP the checkpoints.** Settled-cash bought and sold same day is not a violation.

> ### NEVER delete the 8:00pm arming checkpoint. It is the single point of failure.

---
## 5. Order execution

### Preflight first — before every entry

```
python3 tools/preflight.py --symbol X --qty N --limit P --stop S \
    --balance <TOTAL ACCOUNT VALUE> --buying-power <SETTLED CASH> --deposits D \
    --open-positions 0 --resting-orders 0 \
    [--underlying-pct U --sector-pct S]     # MANDATORY for single-stock leveraged
```

Checks against `limits.json`: loss streak from `data/trades.csv` excluding `counts_toward_streak=no` · the 50%-of-deposits floor · one position, one resting order · stop present, inside the 7% cap, matching the instrument's profile · **whole shares only** · affordability against settled cash · the single-stock underlying-vs-sector gate · order type · universe. **Exit 0 = ALLOW, 1 = DENY.**

**Two argument traps, both of which have already bitten:**

- **`--balance` is ACCOUNT VALUE, `--buying-power` is SETTLED CASH.** They diverge whenever a sale is unsettled. Floor tests account value; affordability tests buying power. Conflating them produced a false floor DENY at double the floor.
- **`--underlying-pct` / `--sector-pct` are REQUIRED for single-stock leveraged, and omitting them DENYs.** The gate cannot be waived by leaving arguments out.

**A DENY means do not place the order.** Overriding is a policy violation — if you proceed you must say so explicitly. **Never edit `limits.json` to make an order pass**; that is a policy change (§17).

> **TRIPWIRE, NOT A GATE.** Broker orders go through tools this script cannot intercept. What it buys is that the arithmetic is deterministic and that skipping or overriding it is *visible*.

### Then

- `review_equity_order` before placing. **A clean review proves nothing about placement** — it accepted a fractional stop the broker then refused.
- **Marketable limit, never plain market.**
- **Verify the fill from the order response.** Never report an unconfirmed fill.
- **Place the protective stop immediately after the fill.**
- Report slippage against the intended price.

---
## 6. Stops — UP ONLY, NEVER DOWN

- **Never widen for comfort or "room for variance."** If the tape needs more room, the trade is wrong for this account — be out. Sizing is not adjustable.
- The only permitted downward change is **correcting a factual placement error**, and you must say so.
- **Not every check.** Each raise is cancel-then-replace, briefly unprotected. **Never tighten on a flat print** — the stop migrates up as the position *gains*.
- **Tighten to structure only if the level is NEARER.** Structure beats the scaled number when closer, never when further.
- **State the stop price, the percentage and the target at entry**, in the same breath as the entry.

### Every number comes from `data/vol_profile.csv`, refreshed at 9:00am

```
stop        = clamp(1.5 x median adverse excursion, 2.5%, 7.0%)
target      = clamp(2.0 x median favourable excursion, 1.5 x stop, 12.0%)
breakeven   = max(median favourable excursion, 0.5 x stop)
trail       = 1.0 x median adverse excursion, below the running high
stall thr   = clamp(0.15 x median favourable excursion, 0.10%, 1.00%)
min stop mv = clamp(0.25 x median adverse excursion, 0.20%, 1.00%)
```

**No flat constants remain. Read the row; do not compute from memory.**

- **An instrument absent from `vol_profile.csv` may not be traded.** Compute it or pick another. No fallback default.
- **HARD CEILING 7%.** A setup needing more room is not a setup.
- **Nothing is excluded on volatility.** Where `1.5 × median MAE` exceeds the cap the stop is capped and flagged `stop_at_cap=yes` — a warning of frequent noise stop-outs, not a disqualification.
- Sizing is all-in, so **stop distance is the only risk lever** — **true only of the sandbox** (§0 requires this line deleted, not reinterpreted, once real money is involved).

### The ratchet — a stepped ramp, then a trail

| Stage | Stop goes to |
|---|---|
| At entry | `−stop_pct` |
| Gain reaches `breakeven_trigger ÷ 2` | **`−stop_pct ÷ 2`** — halve the risk |
| Gain reaches `breakeven_trigger` | **breakeven** (the fill) |
| Past that | **trail `trail_pct` below the running high** |
| 2 stalled checks, **in profit** | `max(current stop, breakeven)` — never lowered |
| 2 stalled checks, **below the fill** | **SELL** (§8.1) |
| 3 stalled checks | **SELL** (§8.1) |
| Any check **at or above `target_pct`** | **SELL** |

- **Up only.** At 2 stalls the stop goes to breakeven *only if that is higher* than where it sits.
- **Minimum move: `min_stop_move_pct` from the profile.** Do not re-place for less.
- **Structural override, UPWARD ONLY.** A swing low holding above the trailed level may be used instead.
- **Expect scratches.** A trail one median-adverse-excursion wide is by construction hit by an ordinary adverse move. That is the price of bounded downside.

### Hard limits of a stop

- **Stop orders are REGULAR-HOURS ONLY.** Extended and overnight cannot be automatically protected; a sell limit below market fills instantly and cannot fake a stop.
- **A stop does NOT protect against a gap.** It bounds slippage in an orderly decline only.
- **The only real defence for an overnight event is not holding into it.**
- **The governor has been told and accepts this.** Do not re-litigate it at checkpoints. Raise it only when a specific identifiable event is approaching — that is a trade decision (§8.5), not a structural complaint.

---
## 8. Exit criteria — any one fires

### 8.1 Momentum stalled

> **MEASURED AT THE CHECKPOINT PRICE ONLY. What happens between checks is ignored.**

**A stalled check** = a 30-minute checkpoint whose price *at that moment* failed to exceed `run_high` by more than `stall_threshold_pct` from the profile.

- **`run_high` is the highest CHECKPOINT price**, seeded at the fill — not the highest price traded. It advances only when a check clears the threshold.
- **A spike between checks is not progress.** +2% at 10:12 that is flat again at the 10:30 check is a **stall**. A high you never saw and could not have sold into is not a gain you could have captured.
- **No volume condition. No bars.** One quote per checkpoint is sufficient.

| Stalled checks | Price vs fill | Action |
|---|---|---|
| **2** | at or above | **stop → `max(current, breakeven)`, keep holding** |
| **2** | **below** | **SELL NOW — the market, at whatever the loss is** |
| **3** | either | **SELL — whatever the gain.** No floor, no exception |

**The ladder is deliberately ASYMMETRIC: two checks for a loser, three for a winner.** A position underwater and failing to make a new high twice has no gain to protect, so the breakeven step has nothing to act on and a third check buys information the first two already gave. It also resolves an unexecutable order: **breakeven sits above the market when losing, and a sell stop above the market is rejected.** **Never place, or attempt to place, a stop above the market.**

**SELL means now, not next checkpoint.** Cancel the resting stop first — a pending sell locks the share (§10) — then exit with a marketable limit.

> **⚠ COUPLED TO THE 30-MINUTE CADENCE.** Counting *checks* means the cadence IS the stall timescale: at 10 minutes, three stalls would fire after 30 minutes instead of 90 — a different rule wearing the same words. Safe only because §2 pins the cadence. **If the cadence ever changes, re-derive the stall count in the same breath.**

**HOW A COLD CHECKPOINT COUNTS STALLS — nothing remembers it; DERIVE it every time:**

1. Read **one quote**: the price now.
2. If `price > run_high × (1 + stall_threshold_pct/100)` → **progressed**: stall count to 0, `run_high` to this price.
3. Otherwise → **stalled**: count increments.
4. The total is the consecutive stalled checks ending at the most recent one.

**State the count, every checkpoint price since entry, its threshold and its verdict, in every report while holding.** A silently derived count makes the most consequential number in the system unauditable — a wrong count either sells a good position or holds a dead one.

- **No midday exclusion. Every check counts, all session.** Volume genuinely dies over lunch, so a position held through midday is likelier to stall out there. That is intended: a position going nowhere is a position going nowhere.
- **A stalled leveraged position is negative expectancy, not neutral.** Decay plus spread means time in a non-moving 2x/3x costs money. Waiting is not free.
- **LOG EVERY STALL-2 EVENT** (§16): the gain at the time, and whether a qualifying new high followed before the third check. This is in-trade data and creates no exception to §9.

### 8.2 Reversal

Broke the level or VWAP that justified entry, or the sector rolled over. Exits at any profit level, ahead of everything except the stop and a headline trigger.

- **The level must have been NAMED AT ENTRY.** Otherwise the claim is unfalsifiable. No named level, no reversal claim.
- The ratcheting stop covers most of this during regular hours. Reversal as a manual criterion matters chiefly for **extended hours and overnight**, where no stop can rest, and for **headline reversals that gap through any stop.**

### 8.3–8.5

3. **Risk/reward flipped** — small remaining upside against a large distance to the stop.
4. **Day trade nearing the 7:30pm deadline** with the move finished.
5. **Unwanted event approaching** — earnings or macro data you did not intend to hold through.

**Not** on one red candle, midday noise, or impatience.

### Pre-commit — every checkpoint while holding

End every report with the **specific, falsifiable condition** that would make you exit at the next checkpoint. Name the instruments and the direction. **Then honour it.** To override you must say you are overriding a pre-commitment and name the specific **new** information. *"It looks like it's turning back up" is not new information.*

> A stop is for when you are **wrong**. A voluntary exit is for when the **thesis stops working**. Waiting for the stop after the thesis has died gives back profit for no reason.

> **Target the DRIVER, not a relative-strength proxy.** Aug 10: the pre-commit named XOP weak *while XLE and OIH advance*; XLE fell too, so the trigger could not fire. "If crude rolls further off its high" was the right condition.

---
## 11. Headline check — every checkpoint

- **FLAT → the PREVIOUS DAY's headlines.** Yesterday and overnight is what forms today's setups.
- **HOLDING → the SAME DAY's headlines.** Only live news matters once capital is committed; yesterday's is in the price.

On a geopolitical trade the thesis dies by headline, not by chart — a ceasefire can move oil 5–10% in minutes, faster than any price criterion.

**Every catalyst gets a structured `catalyst` record (§16), traded or not.** A fired kill trigger gets a `kill_trigger_fired` record.

### Live context — DATED. Refresh it; never carry it forward stale.

**The 9:00am checkpoint re-verifies this block and edits this file if it has changed, then commits.** The 8:00pm checkpoint is the backstop: if the stamp is more than a few days old, refresh or delete it. **Stale context asserted confidently is worse than none** — an exit trigger that already happened will never fire.

This is a **slot, not a fixture.** When the driver stops mattering, replace it wholesale; its triggers are specific to it.

*As of Aug 10 2026:* the **Strait of Hormuz closure** — US-Israel-Iran war, Iran blocked the strait Feb 28 2026, demands sanctions relief and reparations, has ruled out direct US talks. The Iran–**Oman** route deal (~Aug 5–7, "final drafting") is with Oman, not the US, and crossings **fell** after it (15 → 11 → 6). WTI ~$80, Brent >$84. Reopening-optimism headlines are stale and undated — weigh price action.

**Immediate exit triggers regardless of price:** ceasefire · joint statement signed · reopening implemented · sanctions relief · direct US-Iran talks · **crossing counts turning up.**

---
## Logging — MINIMAL MODE. Trades only.

> **Governor decision 2026-08-11: log the trades, do nothing else with the data yet.** Per-checkpoint observation records, entry snapshots, catalyst records and declined records are **SUSPENDED** (§16). Only the governor resumes them.

**Nothing to write at a management checkpoint.** State the derived stall count, the checkpoint prices behind it and the pre-commit **in the report** (§8.1) — that keeps the count auditable without a file write.

**At exit — append one row to `data/trades.csv`.** 30 columns, schema in `RULEBOOK.md` §16.

- **Compute `r_multiple` NOW**, while the entry stop is known. It cannot be reconstructed later.
- **Set `counts_toward_streak` and `counts_toward_expectancy`.** `no` only for a mechanical abort or a funded execution test — and **say why in `notes`**.
- **Append-only: never edit or delete a past row.** A mistake gets a correcting row.
- **Commit and push.**

**At 9:00 — one `watchlist` record** (§16). That one stays: it is an operating aid read at 9:45, not analysis.

> **Do NOT look at what a price did after an exit, or after a candidate you declined.**
