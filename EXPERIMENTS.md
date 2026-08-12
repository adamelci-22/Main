# Experiments — proposed rule changes and their evidence

**This file proposes. It never decides.** Nothing here affects behaviour until it reaches `APPROVED` and is written into `RULEBOOK.md` by an explicit edit. The EXECUTOR role may not read this file during trading hours; it exists for the RESEARCHER role and for the human governor.

## Lifecycle

Every entry moves through these states in order. It may be killed at any stage.

| State | Meaning | Who moves it |
|---|---|---|
| `PROPOSED` | A pattern was noticed. No test yet. | Researcher |
| `TESTED` | Checked against the history we actually have. Sample size stated. | Researcher |
| `SHADOW` | Being tracked in parallel — what *would* the alternative rule have done — without changing live behaviour. | Researcher |
| `APPROVED` | The human governor has agreed to promote it. | **Human only** |
| `LIVE` | Written into RULEBOOK.md. Records the commit and the date. | Human, then Researcher records |
| `RETIRED` | Was live, then reverted. Records why. | Human |
| `KILLED` | Rejected before going live. Records why. | Either |

## Rules for this file

- **Evidence may propose. Evidence may never promote.** No entry advances to `APPROVED` without the human governor saying so in as many words.
- **State the sample size on every claim.** A pattern in 6 trades is an anecdote. Say so.
- **Assume overfitting until shown otherwise.** With one trade a day, a year is ~250 observations. Testing many hypotheses against one small history will produce apparently significant results by chance. Every entry must state how many other hypotheses were examined against the same data.
- **Safety defects are exempt from this whole process.** A bug that could place a duplicate order, exceed the loss floor, or misreport a fill gets fixed immediately and is not an experiment.
- **Prefer killing an entry to letting it linger.** An untested `PROPOSED` older than a month should be killed or tested.

---

## Open

### EXP-012 · Should the trail be 0.4 x stop instead of 1.0 x median MAE?

- **State:** 🟡 `PROPOSED` — awaiting governor decision. Raised 2026-08-11 and deliberately NOT applied.
- **Origin:** the governor's stop ladder spec (`-5% → +1% gain → -3% → +2% gain → 0 → then gain - 2`) implies a trail of **2pp against a 5% stop = 0.4 x stop**. The live trail is **1.0 x median adverse excursion ≈ 0.67 x stop**.
- **The trade-off, stated as a testable claim:** a trail at 0.4 x stop sits **inside one normal adverse excursion**, so it is hit by ordinary noise rather than by reversal. It should therefore raise the share of winners that end as small scratches, while raising the average locked-in gain on the winners that do run.
- **Falsifiable test:** re-run `tools/replay.py` at both trail values over the available sessions and compare (a) expectancy in R, (b) share of trades exiting between 0 and +0.5R, (c) average R of trades exiting above +1R. If expectancy is materially higher at 0.4, adopt it; if the only effect is more scratches, reject it.
- **Blocked on:** sample size. The effective expectancy sample is **1 trade**. This cannot be settled by evidence yet, so it stays a governor preference call rather than a measurement.
- **Why it was not silently applied:** the governor gave explicit numbers, and departing from them without saying so would hide a real change in behaviour. The departure is recorded in `OPERATIONS.md`'s git history and here.

### EXP-001 · Stall exit at 3 checks or 4?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** three stalled checks force a sale at any gain (§8.1).
- **Question:** does four work better than three?
- **Reasoning:** at two stalls the stop is already at breakeven, so extending costs nothing on the downside — the position scratches instead of losing. What is being bought is one more 30-minute window for the move to resume; what is being spent is the gain that would have been banked at three. Payoff is roughly +4 points against −2, so **break-even is about a 33% resumption rate.**
- **Evidence needed:** the resumption rate. Every stall-2 event is logged with whether the position later made a qualifying new high (§8.1). This is in-trade data, so collecting it requires no exception to §9.
- **Sample so far:** 0. The rule postdates the only closed trade.
- **Hypotheses examined against this data:** 1.
- **Do not promote on fewer than ~20 stall-2 events.**

### EXP-002 · Do catalyst categories differ in hit rate?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** §4 requires "a catalyst you can name." All eleven categories are treated as equally valid.
- **Question:** are they? A plausible outcome is that `geopolitical` and `earnings` carry real edge while `analyst` and `sector_sympathy` carry none — in which case the entry gate should exclude the weak ones.
- **Evidence needed:** `catalyst` records paired with `catalyst_outcome` records, grouped by `type`. Both traded and untraded catalysts count, which is why untraded ones are logged.
- **Sample so far:** 0.
- **Hypotheses examined against this data:** 1.
- **Trap to avoid:** eleven categories against a few dozen catalysts is a few observations per bucket. **Do not propose dropping a category on fewer than ~15 observations of that category.** With eleven buckets, one will look terrible by chance.

### EXP-003 · Does catalyst age predict anything?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** none. Age is recorded but never used.
- **Question:** does a catalyst stop being tradeable after some interval — is stale news already priced?
- **Evidence needed:** `age_min` against outcome, across catalyst records. Only records with `source_time_confidence` of `exact` or `approximate` may be used; `unknown` must be excluded rather than guessed at.
- **Sample so far:** 0.
- **Hypotheses examined against this data:** 1.
- **Note:** if this produces a threshold it becomes an entry gate, which makes it a higher-consequence change than most. Require a larger sample than usual.

### EXP-004 · Is stated confidence calibrated?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** none. `confidence` 1–5 is recorded on every catalyst and used for nothing.
- **Question:** do high-confidence catalysts outperform low-confidence ones?
- **Why it matters either way:** if yes, confidence becomes a usable input. **If no, that is the more valuable result** — it would be direct evidence that this agent's self-reported certainty is noise, which is worth knowing well beyond this one field.
- **Evidence needed:** outcome grouped by `confidence`, checking for monotonicity rather than just a difference between the extremes.
- **Sample so far:** 0.
- **Hypotheses examined against this data:** 1.

### EXP-005 · Is 30 minutes the right stall window? — **RETIRED 2026-08-11, question dissolved**

> **This experiment no longer has a variable to test.** The stall is now measured at the checkpoint price (§8.1), so there is no window separate from the cadence — the window IS the wake schedule. 'Window length' and 'cadence' collapsed into one parameter, which is EXP-011's subject. Retired rather than deleted, so the reasoning survives.

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** a stalled window is 30 minutes of market time; three of them force a sale (§8.1).
- **Question:** why 30? **There is no empirical justification — it is inherited from the old checkpoint spacing**, which is exactly the circularity the cadence decoupling was meant to remove. The window is now a free parameter and has simply kept its historical value.
- **Evidence needed:** 5-minute bars are collected, so windows of 15, 20, 30, 45 and 60 minutes can all be reconstructed after the fact from the same data. Replay each against closed trades and compare what the exit would have been.
- **Sample so far:** 0 trades under the current rule.
- **Hypotheses examined against this data:** 1 — but note that testing five window lengths against a small history is **five chances to find a winner by luck.** Whichever looks best will look better than it is. Require a large margin, not a small edge.
- **Trap:** this is replay, not live evidence. It shows what would have happened to entries that were actually taken, which is not the same as what would happen if the rule changed and different trades resulted.

### EXP-006 · Does wake cadence change outcomes?

> ### ⚠ STALE AS OF 2026-08-11 — computed under exit rules that no longer exist.
> The stall is now measured at the **checkpoint price** with **no volume condition**, the target is
> **per-instrument** rather than a flat +8%, and the ratchet has a **new half-risk step**. Every number
> below was produced by `replay.py` before those changes. **The conclusions may still hold; the figures
> do not.** Re-run before citing, and do not treat these as evidence for or against the current rules.


- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** **30 minutes, flat or holding** (§2), set by governor decision 2026-08-11 and supported by the replay evidence below.
- **Question:** does checking more often actually improve results, or just cost more? The stated reason for 15 minutes is reduced ratchet latency — a threshold crossed at 10:07 sits unacted-on for 23 minutes at 30-minute spacing. That is a plausible mechanism, **not a measured one.**
- **Evidence needed:** `cadence_min` is recorded on every observation. Compare stop-move latency and outcomes across cadences. Because 5-minute bars are stored, the counterfactual — where the stop *would* have moved at a different cadence — can be reconstructed exactly.
- **Sample so far:** 0.
- **Hypotheses examined against this data:** 1.
- **Note:** more frequent is not automatically better. A shorter cadence gives more opportunities to react to meaningless noise, and every extra checkpoint is a chance to talk oneself out of a sound position.

### EXP-007 · A single global stop cannot serve this universe — **IMPLEMENTED, closed**

- **State:** ✅ `LIVE` — approved by the governor 2026-08-11, policy **v1.1**. Implemented in `OPERATIONS.md` §6, `tools/vol_profile.py`, `data/vol_profile.csv`, `limits.json`, `tools/preflight.py`.
- **Locked evaluation period:** may not change again for **20 closed trades** (§17).
- **Previously:** `TESTED` — real data
- **Opened:** 2026-08-11 · **Rerun on the correct universe** 2026-08-11
- **Data:** `data/calibration_daily.csv` — **293 sessions, 14 instruments, leveraged sector ETFs and leveraged single-stock ETFs only.** An earlier run wrongly included index-leveraged (SQQQ, TZA) and an unleveraged single name (RIOT); those are not what this strategy trades and the run was discarded.
- **Method:** `tools/calibrate_stops.py`. Long entry at the open — crude, but uses no hindsight about which entries were good.
- **Rule today:** −5% default stop applied identically to every instrument (§6).

**Share of sessions a 5% stop would have been touched:**

| Verdict | Instruments |
|---|---|
| **Unusable** ≥50% | SOXL 57% |
| **Marginal** 30–49% | SOXS 45% · LABU 43% · CONL 38% · MSTX 38% |
| Workable 15–29% | TSLL 29% · NRGU 24% · NVDL 24% · NUGT 19% · DUST 19% |
| Comfortable <15% | GUSH 14% · FNGU 10% · ERX 5% · YINN 0% |

- **Median adverse excursion spans 0.9% (YINN) to 6.6% (SOXL) — a sevenfold range.** No single number serves that. **Five of fourteen instruments would be stopped on 38% or more of sessions** by noise rather than by being wrong.
- **SOXL's median adverse move (6.6%) is wider than the 5% stop itself**, and 1.5× it exceeds the 7% ceiling — so under §6, which declines any setup needing more room, **SOXL is structurally untradeable by this system.** Independent of it also costing $140.

**Proposed rule:** `stop = 1.5 × median adverse excursion`, floored at **2.5%** and capped at **7%**; exclude any instrument whose scaled stop exceeds the cap.

| | YINN | ERX | NUGT | FNGU | GUSH | NRGU | DUST | LABU | NVDL | TSLL | MSTX | CONL | SOXS | SOXL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scaled stop | 2.5 | 2.5 | 2.6 | 3.0 | 3.0 | 4.1 | 4.3 | 4.8 | 5.0 | 5.1 | 5.2 | 6.4 | 6.5 | **excl** |

- Only SOXL is excluded. The floor exists because a stop inside the spread plus normal tick noise is a coin toss, not a stop.
- **Sample:** 293 sessions, one month. **Hypotheses examined against this data: 1.**

### EXP-008 · Stop quality and target reachability are INVERSE — the pair is mismatched everywhere — **IMPLEMENTED, closed**

> **Closed 2026-08-11.** The second half of this finding — that the flat +8% target was unreachable wherever the stop was comfortable — is now fixed too: the target is `clamp(2.0 x median MFE, 1.5 x stop, 12.0%)` per instrument, which cut effectively-unreachable instruments from **18 of 31 to 8 of 31**. Do not re-argue this experiment; measure the replacement.

- **State:** ✅ `LIVE` — approved 2026-08-11, policy **v1.1**. Target now `2.0 x stop` per instrument; the flat +8–12% is retired (`RULEBOOK.md` §7).
- **Locked evaluation period:** 20 closed trades.
- **Previously:** `TESTED` — real data · **the more important of the two findings**
- **Same data and method as EXP-007.**
- **Rule today:** −5% stop and a +8–12% target, both fixed, both applied to every instrument (§6, §7).

**Sessions reaching +8% from the open, against the 5% stop-out rate. Both are upper bounds** — a daily bar cannot say whether the high came before the low.

| | SOXL | SOXS | LABU | CONL | MSTX | TSLL | NVDL | NRGU | NUGT | DUST | GUSH | FNGU | ERX | YINN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stop-out at 5% | 57% | 45% | 43% | 38% | 38% | 29% | 24% | 24% | 19% | 19% | 14% | 10% | 5% | 0% |
| reached +8% | 29% | 35% | 10% | 24% | 24% | 5% | 14% | **0%** | **0%** | **0%** | **0%** | 5% | **0%** | **0%** |

- **The relationship is monotone and it is the finding.** Every instrument where +8% is achievable is an instrument where a 5% stop gets hit constantly. Every instrument where the stop is comfortable never reaches +8%. **The fixed stop/target pair is wrong on essentially all fourteen — one end or the other always is.**
- Six of fourteen did not reach +8% once in 21 sessions: NRGU, NUGT, DUST, GUSH, ERX, YINN.
- **Corroborates the only real trade.** GUSH exited at **+3.25%** on a stall. GUSH reached +8% on zero of 21 sessions, so that target was never available and the stall ladder was always going to be the exit.
- **Consequence.** Scaling only the stop leaves the target unreachable on the calm names and scaling only the target leaves the stop broken on the volatile ones. **Both must scale together to the same volatility measure**, or the system keeps taking trades whose stated target is unreachable and whose stop is decorative.
- **Sample:** 293 sessions, one month. **Hypotheses examined: 1.**

> **Do not read the favourable/adverse ratios as instrument quality.** NUGT looks asymmetric because gold miners rallied from 115 to 160 during this window; that is a fact about July–August 2026, not about NUGT. Entry-at-open has no edge, so direction over the sample contaminates any up-versus-down comparison.

### EXP-009 · The exit rules are approximately VALUE-NEUTRAL on random entries

> ### ⚠ STALE AS OF 2026-08-11 — computed under exit rules that no longer exist.
> The stall is now measured at the **checkpoint price** with **no volume condition**, the target is
> **per-instrument** rather than a flat +8%, and the ratchet has a **new half-risk step**. Every number
> below was produced by `replay.py` before those changes. **The conclusions may still hold; the figures
> do not.** Re-run before citing, and do not treat these as evidence for or against the current rules.


- **State:** `TESTED` — real data · **the most consequential result so far**
- **Opened:** 2026-08-11 · **Method:** `tools/calibrate_stops.py`, 293 sessions, 14 leveraged instruments.
- **Question:** applied to entries with no selection edge, do the exit rules make money?

| Scenario | n | % profitable | Expectancy | Profit factor |
|---|---|---|---|---|
| Current rules — 5% stop, 8% target | 293 | 48.5–48.8% | +0.01 to +0.02R | 1.04–1.07 |
| Proposed — scaled stop, target 2× stop | 272 | 48.5–48.9% | +0.02 to +0.03R | 1.06–1.09 |

Bounds are pessimistic (assume the stop was touched first whenever both were) and optimistic (target first). The truth is between and **cannot be narrowed with daily bars.**

- **At n=293 the standard error on a 48.5% rate is ±2.9%. This is indistinguishable from a coin flip, and expectancy is indistinguishable from zero.**
- **This is the correct and expected result, not a failure.** Entry at the open has no edge by construction. A value-neutral outcome means **the exit machinery neither creates nor destroys value** — it bounds losses without generating profit.
- **The conclusion that matters:** every bit of hypothesised edge in this system rests on the **entry gates** — sector leadership, breadth, a nameable catalyst, trend over chop. Those are the components that **cannot be backtested** (§ no structured historical news, and the gates need judgment), and they have a sample size of **one closed trade.**
- **Do not read this as "the strategy is break-even."** It says nothing about the strategy. It says the exits are sound plumbing and the entries are entirely unvalidated.

**Second-order finding, and it corrects how EXP-007 should be sold.** The proposed scaled stop improves expectancy by roughly **+0.01R** — noise. So volatility-scaling the stop is a **risk-consistency fix, not a return fix**: it makes R mean the same thing across instruments and stops SOXL-class names being stopped by noise. It should be argued on those grounds and not as a profit improvement, which the data does not support.

### EXP-011 · Cadence — FIRST REAL EVIDENCE, and it is nearly irrelevant

> ### ⚠ STALE AS OF 2026-08-11 — computed under exit rules that no longer exist.
> The stall is now measured at the **checkpoint price** with **no volume condition**, the target is
> **per-instrument** rather than a flat +8%, and the ratchet has a **new half-risk step**. Every number
> below was produced by `replay.py` before those changes. **The conclusions may still hold; the figures
> do not.** Re-run before citing, and do not treat these as evidence for or against the current rules.


> **Renumbered 2026-08-11.** This was filed as a second EXP-006, colliding with the open experiment above. Two entries sharing an ID makes both unciteable.

- **State:** `TESTED` — first replay evidence · **n = 1 session, so directional only**
- **Method:** `tools/replay.py` on `data/bars_5min_GUSH_2026-08-05.csv`. Models the real structure: the resting stop is checked **continuously** because it is an actual broker order; target, stall count and ratchet only at **checkpoint boundaries**; stall windows are 30-minute market-time windows independent of the cadence.

| Cadence | Exit | Result |
|---|---|---|
| 10 min | 18:35, stall ×3 | −3.02% / −0.60R |
| **15 min (current)** | 18:30, stall ×3 | **−2.91% / −0.58R** |
| 30 min (old) | 18:45, stall ×3 | −3.07% / −0.61R |

- **Total spread across a 3× range of cadence: 0.16 percentage points, or 0.03R.** All three took the same exit for the same reason, minutes apart.
- **This is what the decoupling was for.** Because the stall clock runs on market time, tripling the wake rate does not change the exit — it only shifts *when* the same decision gets executed. Direct support for refusing uniform 10-minute cadence (§2).
- **Sample: one session.** Not evidence of a general result. But the *mechanism* is now demonstrated rather than argued.

### EXP-010 · The stall ladder is a LOSS LIMITER below entry, not only a gain-banker

> ### ⚠ STALE AS OF 2026-08-11 — computed under exit rules that no longer exist.
> The stall is now measured at the **checkpoint price** with **no volume condition**, the target is
> **per-instrument** rather than a flat +8%, and the ratchet has a **new half-risk step**. Every number
> below was produced by `replay.py` before those changes. **The conclusions may still hold; the figures
> do not.** Re-run before citing, and do not treat these as evidence for or against the current rules.


- **State:** `TESTED` · **arose from a rulebook error this replay exposed**
- The rules claimed the three-window sell "can only ever cost upside — never a loss," because the stop would already be at breakeven. **False.** The ratchet only engages at +2–3%; a position that goes down from entry and stalls has no breakeven stop, and the sell closes it at a loss. **Corrected in `OPERATIONS.md` §8.1** as a factual fix, not a policy change.
- **The rule survives on better grounds.** In the same session the −5% stop *would* have been hit — GUSH closed −5.5% below entry. The stall exit took **−0.58R instead of −1.0R.**
- **So the ladder does two different jobs**, and conflating them hid the error: above +2–3% it banks a gain the ratchet already protected; below entry it cuts a dead trade before the stop does. The second job is arguably the more valuable and was undocumented.
- **Open question this raises:** if the ladder reliably exits red positions near −0.6R rather than −1.0R, then the *effective* average loss is smaller than the stop implies, which changes the expectancy arithmetic in §14 in our favour. **Needs many more sessions before believing it** — one trade proves nothing, and the ladder could equally fire at −4.5% on a different tape.

### EXP-013 · preflight's class-priority tripwire is blind to 1x single-stock names

- **State:** `PROPOSED` · found at the 2026-08-12 09:00 checkpoint while ranking the profiled universe.
- `preflight.py` fires the single-stock underlying gate AND the class-priority warning off one lookup:
  `limits.json -> single_stock_leveraged.map`. That map only lists **leveraged** single-stock ETFs.
- **RIOT, MARA, CLSK** are plain 1x equities. They are still class-priority 3 (single-stock), and they
  are on the watchlist and affordable — but preflight prints **no** class-priority warning for them,
  so an entry could take the lowest-priority class with the tripwire silent. The underlying gate
  correctly does not apply (the underlying *is* the instrument), but the priority warning should.
- **Fix:** derive the priority class from `data/vol_profile.csv`'s instrument class (`single_1x`,
  `single_2x`) rather than from map membership, and keep the map for the underlying-vs-sector gate only.
- **Deliberately NOT changed at the 09:00 checkpoint.** Editing the tripwire 45 minutes before an
  entry decision is the same mistake as the fractional-stop episode: verify capability on a calm slot,
  not against a clock. Scheduled for the 20:00 rule-change slot.
- **Bounded risk today:** the three affected names rank 27, 29 and 30 of 31 on `mfe_per_stop`, so the
  ranking rule already puts them last. The tripwire gap is real but is not load-bearing this session.

---

## Closed

*None yet.*
