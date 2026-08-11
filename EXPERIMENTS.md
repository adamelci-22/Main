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

### EXP-005 · Is 30 minutes the right stall window?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** a stalled window is 30 minutes of market time; three of them force a sale (§8.1).
- **Question:** why 30? **There is no empirical justification — it is inherited from the old checkpoint spacing**, which is exactly the circularity the cadence decoupling was meant to remove. The window is now a free parameter and has simply kept its historical value.
- **Evidence needed:** 5-minute bars are collected, so windows of 15, 20, 30, 45 and 60 minutes can all be reconstructed after the fact from the same data. Replay each against closed trades and compare what the exit would have been.
- **Sample so far:** 0 trades under the current rule.
- **Hypotheses examined against this data:** 1 — but note that testing five window lengths against a small history is **five chances to find a winner by luck.** Whichever looks best will look better than it is. Require a large margin, not a small edge.
- **Trap:** this is replay, not live evidence. It shows what would have happened to entries that were actually taken, which is not the same as what would happen if the rule changed and different trades resulted.

### EXP-006 · Does wake cadence change outcomes?

- **State:** `PROPOSED`
- **Opened:** 2026-08-11
- **Rule today:** 15 minutes while holding, sparse while flat (§2).
- **Question:** does checking more often actually improve results, or just cost more? The stated reason for 15 minutes is reduced ratchet latency — a threshold crossed at 10:07 sits unacted-on for 23 minutes at 30-minute spacing. That is a plausible mechanism, **not a measured one.**
- **Evidence needed:** `cadence_min` is recorded on every observation. Compare stop-move latency and outcomes across cadences. Because 5-minute bars are stored, the counterfactual — where the stop *would* have moved at a different cadence — can be reconstructed exactly.
- **Sample so far:** 0.
- **Hypotheses examined against this data:** 1.
- **Note:** more frequent is not automatically better. A shorter cadence gives more opportunities to react to meaningless noise, and every extra checkpoint is a chance to talk oneself out of a sound position.

### EXP-007 · The 5% stop is wrong as a single global number

- **State:** `TESTED` — real data, first evidence
- **Opened:** 2026-08-11 · **Method:** `tools/calibrate_stops.py` on `data/calibration_daily.csv`
- **Rule today:** −5% default stop, −7% ceiling, applied identically to every instrument (§6).
- **Finding.** 21 sessions each, long entry at the open as a hindsight-free proxy. Share of sessions a 5% stop would have been **touched**:

  | | SOXL | RIOT | GUSH | SQQQ | TZA |
  |---|---|---|---|---|---|
  | stop-out rate | **57%** | **38%** | 14% | 10% | 0% |
  | median adverse excursion | 6.6% | 4.0% | 2.0% | 1.6% | 1.5% |
  | median daily range | 11.9% | 8.4% | 4.6% | 4.6% | 3.5% |

- **Interpretation.** A single global stop is **4× too tight for SOXL and arguably too loose for TZA.** SOXL's median adverse move *exceeds* the 5% stop, so on a typical day the stop is hit by noise rather than by being wrong. The instruments differ by a factor of four in volatility and the rule treats them identically.
- **A corollary worth noting:** since §6 caps the stop at 7% and declines any setup needing more room, **SOXL is structurally untradeable under the current risk model** — its noise is wider than the widest permitted stop. That is independent of it also being unaffordable at $140.
- **Proposed:** scale the stop to the instrument's recent volatility rather than fixing it — e.g. ~2× median adverse excursion, still hard-capped at 7%, with instruments whose scaled stop exceeds the cap excluded rather than entered on a too-tight stop.
- **Sample:** 105 sessions, 5 instruments, one month. **Hypotheses examined against this data: 1.**
- **Do not promote without governor approval.** But note this is arguably closer to a risk-model defect than an alpha hypothesis.

### EXP-008 · The +8–12% target is close to unreachable on the affordable universe

- **State:** `TESTED` — real data, first evidence
- **Opened:** 2026-08-11 · **Same method and data as EXP-007**
- **Rule today:** set a target of +8–12% at entry (§7).
- **Finding.** Share of sessions reaching **+8%** from the open — and these are **upper bounds**, since a daily bar cannot say whether the high came before the low:

  | | SOXL | RIOT | GUSH | SQQQ | TZA |
  |---|---|---|---|---|---|
  | reached +8% | 29% | 14% | **0%** | **0%** | **0%** |
  | reached +3% | 71% | 48% | 33% | 43% | 24% |

- **Interpretation.** On the three instruments actually affordable at this balance, **+8% did not occur once in 21 sessions.** The target is not merely rarely reached — intraday it is essentially unavailable. Meanwhile +3%, the breakeven-ratchet trigger, is reached 24–48% of the time, so **the ladder engages regularly while the target never fires.**
- This corroborates the only real trade: GUSH exited at **+3.25%** on a stall, nowhere near target.
- **Consequence for the metrics.** §14 already expects most trades to close before target. This says something stronger: for affordable instruments the target is **decorative**, and essentially all exits will come from the stall ladder or the stop. Expectancy will therefore be built from ~+2–4% winners, which makes the stop size (EXP-007) the dominant term in the whole system.
- **Proposed:** either scale the target to instrument volatility alongside the stop, or state plainly that a multi-day hold is required to reach +8% and price that against the same-day-close default (§7).
- **Sample:** 105 sessions, one month. **Hypotheses examined: 1.**

---

## Closed

*None yet.*
