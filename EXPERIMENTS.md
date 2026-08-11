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

---

## Closed

*None yet.*
