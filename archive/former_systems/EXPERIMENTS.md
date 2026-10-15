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

**Nothing currently open.** EXP-001 through EXP-016 below were all written between 2026-08-11 and 2026-08-13, against an earlier architecture (`OPERATIONS.md` with numbered §-sections, `tools/replay.py`, `tools/calibrate_stops.py`, `tools/preflight.py`, `data/vol_profile.csv`, `limits.json`). None of that tooling or document structure exists in this repo anymore — it was superseded by `RULEBOOK.md`'s Part A–E structure and the single `tools/profile.py` script, which have since gone through their own many versions (currently v3.45). Swept to Closed below, 2026-08-28, per this file's own "prefer killing to letting it linger" rule — most were already well past a month old and untestable against tooling that no longer exists.

## Closed

### EXP-007 · A single global stop cannot serve this universe — **LIVE, still true**

- **State:** ✅ `LIVE` — approved by the governor 2026-08-11, policy **v1.1**. The concept survives every rewrite since: `RULEBOOK.md`'s current B1 computes `stop_pct = clamp(1.5 × median adverse, 2.5%, 7.0%)` per instrument via `tools/profile.py` — same formula, same floor/cap, just reimplemented after the original `vol_profile.csv`/`calibrate_stops.py`/`limits.json`/`preflight.py` pipeline this entry names was retired. Original evidence and reasoning below, unedited.
- **Locked evaluation period:** may not change again for **20 closed trades** (§17 — an old section number; no longer a live cross-reference).
- **Previously:** `TESTED` — real data
- **Opened:** 2026-08-11 · **Rerun on the correct universe** 2026-08-11
- **Data:** `data/calibration_daily.csv` — **293 sessions, 14 instruments, leveraged sector ETFs and leveraged single-stock ETFs only.** An earlier run wrongly included index-leveraged (SQQQ, TZA) and an unleveraged single name (RIOT); those are not what this strategy trades and the run was discarded.
- **Method:** `tools/calibrate_stops.py`. Long entry at the open — crude, but uses no hindsight about which entries were good.
- **Rule at the time:** −5% default stop applied identically to every instrument.

**Share of sessions a 5% stop would have been touched:**

| Verdict | Instruments |
|---|---|
| **Unusable** ≥50% | SOXL 57% |
| **Marginal** 30–49% | SOXS 45% · LABU 43% · CONL 38% · MSTX 38% |
| Workable 15–29% | TSLL 29% · NRGU 24% · NVDL 24% · NUGT 19% · DUST 19% |
| Comfortable <15% | GUSH 14% · FNGU 10% · ERX 5% · YINN 0% |

- **Median adverse excursion spans 0.9% (YINN) to 6.6% (SOXL) — a sevenfold range.** No single number serves that. **Five of fourteen instruments would be stopped on 38% or more of sessions** by noise rather than by being wrong.
- **SOXL's median adverse move (6.6%) is wider than the 5% stop itself**, and 1.5× it exceeds the 7% ceiling — so under the current cap, which declines any setup needing more room, **SOXL is structurally untradeable by this system.** Independent of it also costing $140.

**Proposed rule:** `stop = 1.5 × median adverse excursion`, floored at **2.5%** and capped at **7%**; exclude any instrument whose scaled stop exceeds the cap.

| | YINN | ERX | NUGT | FNGU | GUSH | NRGU | DUST | LABU | NVDL | TSLL | MSTX | CONL | SOXS | SOXL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scaled stop | 2.5 | 2.5 | 2.6 | 3.0 | 3.0 | 4.1 | 4.3 | 4.8 | 5.0 | 5.1 | 5.2 | 6.4 | 6.5 | **excl** |

- Only SOXL is excluded. The floor exists because a stop inside the spread plus normal tick noise is a coin toss, not a stop.
- **Sample:** 293 sessions, one month. **Hypotheses examined against this data: 1.**

### EXP-008 · Stop quality and target reachability are INVERSE — the pair is mismatched everywhere — **LIVE, still true**

> **Closed 2026-08-11.** The second half of this finding — that the flat +8% target was unreachable wherever the stop was comfortable — is now fixed too, and the fix survives every rewrite since: `RULEBOOK.md`'s current B1 computes `target_pct = clamp(1.25 × median favourable, 1.5 × stop_pct, 12.0%)` per instrument. Note `target_pct` is informational-only as of v3.40 — no exit is target-triggered anymore (B4) — so this finding's original consequence (a fixed target being unreachable) matters less than it did, but the scaled-target concept itself is still exactly how B1 computes the number. Do not re-argue this experiment; the replacement has been live and stable for many rulebook versions.

- **State:** ✅ `LIVE` — approved 2026-08-11, policy **v1.1**. Target now scaled per instrument (see above); the flat +8–12% is retired.
- **Locked evaluation period:** 20 closed trades.
- **Previously:** `TESTED` — real data · **the more important of the two findings**
- **Same data and method as EXP-007.**
- **Rule at the time:** −5% stop and a +8–12% target, both fixed, both applied to every instrument.

**Sessions reaching +8% from the open, against the 5% stop-out rate. Both are upper bounds** — a daily bar cannot say whether the high came before the low.

| | SOXL | SOXS | LABU | CONL | MSTX | TSLL | NVDL | NRGU | NUGT | DUST | GUSH | FNGU | ERX | YINN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stop-out at 5% | 57% | 45% | 43% | 38% | 38% | 29% | 24% | 24% | 19% | 19% | 14% | 10% | 5% | 0% |
| reached +8% | 29% | 35% | 10% | 24% | 24% | 5% | 14% | **0%** | **0%** | **0%** | **0%** | 5% | **0%** | **0%** |

- **The relationship is monotone and it is the finding.** Every instrument where +8% is achievable is an instrument where a 5% stop gets hit constantly. Every instrument where the stop is comfortable never reaches +8%. **The fixed stop/target pair is wrong on essentially all fourteen — one end or the other always is.**
- Six of fourteen did not reach +8% once in 21 sessions: NRGU, NUGT, DUST, GUSH, ERX, YINN.
- **Corroborates the only real trade at the time.** GUSH exited at **+3.25%** on a stall (the stall ladder itself is retired as of v3.43 — see below). GUSH reached +8% on zero of 21 sessions, so that target was never available.
- **Consequence.** Scaling only the stop leaves the target unreachable on the calm names and scaling only the target leaves the stop broken on the volatile ones. **Both must scale together to the same volatility measure.**
- **Sample:** 293 sessions, one month. **Hypotheses examined: 1.**

> **Do not read the favourable/adverse ratios as instrument quality.** NUGT looks asymmetric because gold miners rallied from 115 to 160 during this window; that is a fact about July–August 2026, not about NUGT. Entry-at-open has no edge, so direction over the sample contaminates any up-versus-down comparison.

### EXP-015 · Gate 1 is INVERTED for inverse vehicles — **RESOLVED, independently**

- **State:** ⚪ `KILLED` (as an open item) 2026-08-28 — **the underlying concern is resolved, just not by a change traceable to this entry.** Found at the 2026-08-13 09:30 observation: Gate 1 required the sector proxy positive at 9:30/9:45, which an inverse ETF's proxy can never satisfy by construction, silently removing SOXS/DUST/YANG/ZSL/SCO from the tradeable universe. **Current C1 does not have this hole**: real trades since (DUST/JDST/ZSL as "precious metals reversal," YANG as "China reversal," FAZ as "financials reversal" — see `RULEBOOK.md` E5's live logs) evaluate the *vehicle's own* self-referencing day change, not the raw underlying sector proxy's move — exactly the polarity-aware fix this entry proposed. Whether that was a deliberate fix or fell out of the sector-first/leveraged-priority research rewrite (v3.41) isn't recorded; either way, the gap this entry found does not exist in the live rule today.
- Original finding, unedited: Gate 1 (§4, old numbering) required the sector proxy to be **positive at 9:30, positive at 9:45**, and not lower at 9:45. An inverse ETF's entire thesis is that its proxy **falls**. Read literally, an inverse vehicle could never pass Gate 1. On Aug 13 the single most decisive move on the board was GDX **−2.47%** at 9:31, holding **−2.50%** at 9:46 — a clean, sustained, high-conviction directional move. Its vehicle, DUST, was class priority 1 and affordable at ~$42, and was unreachable on a technicality rather than a market judgement.
- **If this specific self-referencing evaluation is ever removed from C1 in a future rewrite, re-open this concern** — the failure mode (inverse vehicles structurally unbuyable) is real and was hit on real tape once already.

### EXP-014 · Gate 1 has no minimum margin, and a foreign-market gap is not a trend — **KILLED, partially superseded**

- **State:** ⚪ `KILLED` 2026-08-28 — dead references (§4, old numbering; no replacement tooling to test the margin question quantitatively). **Partially addressed by the current rule, not fully.** Two sub-findings from the Wed 2026-08-12 session (ended flat, no P&L):
- **(1) No minimum margin.** Both surviving proxies passed Gate 1 on Aug 12 by noise-sized margins (EWY +2.4bp, SMH +0.6bp) — a gate meant to confirm a *holding* trend passed on a tape that had gone dead flat. **Current C1's late-entry clause requires the reading to be *strictly higher* than the 9:30 baseline (real margin), but the original 9:40 pass/fail test itself still only requires "not below"** — so the initial-entry version of this concern is not fully resolved. Worth re-raising quantitatively if a near-zero-margin 9:40 pass produces a bad trade.
- **(2) A foreign-market gap can be a fully spent move.** KORU's entire +13.5% on Aug 12 was an opening reprice of a KOSPI session that closed ~7 hours earlier — no further Korean price discovery was available. C10's `session_high`/`session_low`/giveback-ceiling logic (added since) catches a *faded* gap-and-go, but not this specific argument (a gap can be "spent" even while still holding, if its catalyst already finished). Not the same mechanism, so not fully superseded either.
- **Not proposing a foreign-ETF ban** — KORU/YINN/YANG have genuine US-session price discovery too; the narrow point is that a gap repricing an already-closed session isn't by itself evidence of a live trend.

### EXP-016 · The already-extended check — a pre-entry test for an unreachable target — **KILLED, premise weakened**

- **State:** ⚪ `KILLED` 2026-08-28 — the underlying worry (buying a spent gap with no reachable target left) is now much less consequential than when this was written, because **no exit is target-triggered as of v3.40** — the chandelier trail (B2) locks in gains continuously regardless of any fixed target, so "is the target still reachable from here" no longer gates whether a late entry can produce a good outcome the way it did under the old fixed +8% target. C7's `mfe_to_target` (instrument-level reachability) and C10 (momentum/reversal, added since) together cover most of what this entry was reaching for, from a different angle.
- Original finding, unedited: FNGU opened at $32.750 and topped at $34.000; Gate 1's mandatory wait meant the earliest legal fill was 09:45, filled 09:48:39 at $33.5999 having watched +2.60% of a +3.82% move go past. At entry the instrument was already +4.38% on the day against a median daily MFE of 2.405% — 1.82× its typical whole-day excursion before entry was permitted. The scaled target (+4.81%) was arithmetically out of reach from that fill. True MFE that trade was +1.19%, exit −0.059% — no rule banked the sub-1% move.
- **If fixed-target exits are ever reintroduced, re-open this** — the mechanism (`day_change_at_entry / median_mfe_pct >= ~1.5` flags an unreachable target from *today's* fill, distinct from `mfe_to_target`'s instrument-general reachability) is still a reasonable, cheap pre-entry check.

### EXP-013 · preflight's class-priority tripwire is blind to 1x single-stock names — **KILLED**

- **State:** ⚪ `KILLED` 2026-08-28 — `preflight.py` and `limits.json`, the tools this entry's fix targets, no longer exist. **The specific blind spot (a lookup map that only lists leveraged single-stock ETFs, so plain 1x names like RIOT/MARA/CLSK got no class-priority warning) has no equivalent in the current C4** (Instrument priority), which ranks by whether an affordable leveraged wrapper exists for the mover, not by class-priority map membership — a different design that doesn't have this failure mode.

### EXP-012 · Should the trail be 0.4× stop instead of 1.0× median MAE? — **KILLED, mechanism replaced**

- **State:** ⚪ `KILLED` 2026-08-28 — moot. B2's trail has been fully redesigned twice since this was written (v3.43: stepped ratchet → continuous average-based; v3.44: average-based → chandelier off `run_high`, discount `2 × stall_threshold_pct`). Neither "0.4× stop" nor "1.0× median MAE" describes anything in the current rule, and `tools/replay.py` no longer exists to test a trail multiplier against history the way this entry proposed. See `RULEBOOK.md` B2 and Current State (v3.44) for how the discount multiplier question was actually settled — backtested 1×–5× against real trade data, landed on 2× off `run_high`.

### EXP-010 · The stall ladder is a LOSS LIMITER below entry, not only a gain-banker — **KILLED, mechanism retired**

- **State:** ⚪ `KILLED` 2026-08-28 — the stall-count ladder this entry is about was retired entirely in v3.43 (B3). The finding (a stalled position below entry gets cut before the stop, at a smaller loss than −1.0R) doesn't have an equivalent question under the current continuous chandelier trail, which tightens every checkpoint regardless of stall count.

### EXP-011 · Cadence — FIRST REAL EVIDENCE, and it is nearly irrelevant — **KILLED, superseded by later cadence changes**

- **State:** ⚪ `KILLED` 2026-08-28 — `tools/replay.py` no longer exists. The cadence question itself was later resolved by a *different* kind of evidence than this entry used (counterfactual replay of one session): v3.43 shortened the trading day to 9:00–12:30 and tightened the grid to 15 minutes based on real multi-week trade P&L showing profit concentrated in the first 1–2 hours of the day — live outcome data, not a replay study. This entry's finding (cadence barely moves the exit because the stall clock ran on market time) is also moot since the stall clock it describes no longer exists.

### EXP-009 · The exit rules are approximately VALUE-NEUTRAL on random entries — **KILLED, superseded architecture**

- **State:** ⚪ `KILLED` 2026-08-28 — `tools/calibrate_stops.py` and the exit rules this measured (flat stall windows, old ratchet) no longer exist. The core conclusion — that the exit machinery's job is to bound losses, not generate edge, and that all hypothesised edge lives in the entry gates — is still a reasonable prior but hasn't been re-measured against the current chandelier trail; would need fresh evidence, not a revival of this entry.

### EXP-006 · Does wake cadence change outcomes? — **KILLED, superseded**

- **State:** ⚪ `KILLED` 2026-08-28 — see EXP-011's closing note; cadence has since been changed twice (30min→15min in v3.43) based on real trade timing data, answering the practical question this entry asked by a different route than the counterfactual-replay method it proposed. `tools/replay.py` no longer exists to run that method anyway.

### EXP-005 · Is 30 minutes the right stall window? — **RETIRED 2026-08-11, question dissolved; now KILLED outright**

- **State:** ⚪ `KILLED` 2026-08-28 (previously `RETIRED`, its question already dissolved before the stall ladder itself was retired in v3.43). Kept as a two-line pointer rather than the original entry: the stall window / wake cadence distinction this asked about no longer applies to anything live.

### EXP-004 · Is stated confidence calibrated? — **KILLED, data no longer collected**

- **State:** ⚪ `KILLED` 2026-08-28 — the `confidence` 1–5 field this asks about isn't part of the current `archive/trades.csv` schema; nothing has been collecting it. Would need a new field added deliberately before this could be re-opened.

### EXP-003 · Does catalyst age predict anything? — **KILLED, revivable if volume grows**

- **State:** ⚪ `KILLED` 2026-08-28 — the specific `age_min`/`source_time_confidence` fields this names don't exist, but `archive/trades.csv` does carry a `catalyst_age_min` field today (mostly unfilled in practice). **Worth re-opening once trade volume is large enough** — at 15 trades total, nowhere close.

### EXP-002 · Do catalyst categories differ in hit rate? — **KILLED, revivable if volume grows**

- **State:** ⚪ `KILLED` 2026-08-28 — same as EXP-003. `archive/trades.csv` does carry `catalyst_type` today, so the data this needs is closer to hand than when written, but 15 total trades across many catalyst types is nowhere near the ~15-observations-per-bucket this entry itself said was the minimum. **Revisit once real volume exists.**

### EXP-001 · Stall exit at 3 checks or 4? — **KILLED, mechanism retired**

- **State:** ⚪ `KILLED` 2026-08-28 — the three-stall-forces-a-sale rule this asks about was retired in v3.43 along with the rest of the stall-count ladder. No equivalent question under the current continuous trail.
