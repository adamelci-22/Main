# PROPOSED: self-improvement loop, RULEBOOK D4 (draft, not in force)

Status: draft for the governor. Nothing here changes a trade until the governor approves it and the version is bumped to 5.2.29. The only edit to an existing file is `tools/live/paper.py`, and it is behaviour-neutral (section 2). `RULEBOOK.md` is unchanged.

## 1. What it does

The model learns from outcomes, but it cannot change the live system by itself.

1. **Tunables.** Five numbers may change, nothing else: `fade.retest_tol_pct` (B2.3), `fade.lock_trigger_r`, `fade.lock_level_r`, `fade.cut_r` (B2.5), `pb.vol_mult` (B3.2). Bounds and a one-step size are in `tools/live/tunables.json`. A1 controls, sizing, ticker lists, hours and exits at 2R are not tunable.
2. **Menu.** `improve.py menu` re-runs the current rules on the 158-session dataset with every one-step change. A row passes only if it beats the baseline in-sample (first 60%) and out-of-sample (last 40%), gains at least 0.01%/day, adds under 1 point of drawdown and keeps 75% of the trades.
3. **Proposal.** At most one change. Proposers: the checkpoint session (`session`, default), the Claude API (`api`) or the best passing row (`fallback`). A proposer picks only a passing menu id or `hold`. It cannot invent a value.
4. **Governor.** `improve.py approve --effective <future trading day> --note "..."`. Never applied mid-session. One change in flight at a time.
5. **Verdict.** Each close, `tick` runs the old and the new version on the same saved bars. After 15 trading days: keep if new minus old is 0 or better, revert if worse than -0.5% of the account. Early revert at -2.0% after 5 days. At 30 days it decides on the sign.
6. **Rollback.** `improve.py rollback` appends a new version with the old values. History is append-only. `policy.auto_rollback` is `false`. With it off, a REVERT is reported to the governor and waits for the governor.
7. **Trigger.** `tick` proposes when 5 model trades have closed since the last decision, and only when no trial or proposal is open.

Not built on purpose: automatic approval of a new change. This account trades real money and the rulebook says the governor decides.

## 2. Files

| File | Change |
|---|---|
| `tools/live/improve.py` | new, stdlib only |
| `tools/live/tunables.json` | new, version 1 = today's constants |
| `tools/live/paper.py` | `RETEST_TOL` and `PB_VOL` replace two literals; `apply_tunables(day)` is called at the top of `simulate()` |
| `archive/improve/` | created on first use: `ledger.jsonl`, `pending.json`, `shadow.csv`, `menu.json` |

Neutrality test: the patched `paper.simulate` was compared with v5.2.28 over 157 backtest sessions, with and without the lock and cut (314 day-runs). Trades, exits and equity were identical in all 314.

## 3. Rule text to add (new Part D4)

**D4. Self-improvement loop (v5.2.29).** `tools/live/improve.py` may propose a change to the five tunables in `tools/live/tunables.json`. A proposal takes effect only after the governor runs `approve --effective <date>` for a future trading day, and the approval is recorded in the commit with the governor's words. One change is in flight at a time. The trial is judged against the previous version on the same days (C4 step 5). A REVERT verdict is reported at once and rolled back on the governor's word. Nothing in A1 is tunable. `tunables.json`, `archive/improve/` and the version bump are committed together.

**C4 step 5 (new):** after `paper.py --close`, run `python3 tools/live/improve.py tick <the day's dump files>` and paste its output into the report. Friday summary includes `improve.py status`.

## 4. Evidence today (2026-10-28)

`improve.py menu` on `bt_5m.json.gz` (2026-03-03 to 10-15, 114 trades): baseline +0.521%/day, profit factor 3.68, maximum drawdown 2.8%. First half +0.667%/day, second half +0.303%/day.

No one-step change passes the gate. The best raw rows are worth +0.001 to +0.003%/day, which is noise. The loop starts in `hold`. That is the correct result for parameters that already sit at a local optimum.

## 5. Limits

- The dataset ends 2026-10-15. Refresh it with `build_data.py` before trusting a menu run.
- The menu optimises past data. The in-sample and out-of-sample split reduces the risk. It does not remove it.
- A 15-day trial has little power because most days produce identical results under both versions. Treat the verdict as a guard against harm, not proof of gain.
- Live paper results since 2026-10-23 are far below the backtest average. Look at execution and data gaps (C5 health tracker) before tuning rules.

## 6. Install (for the live session)

1. Review the diff: `git diff main..claude/self-improvement-loop`.
2. Run `python3 tools/live/improve.py menu` and `python3 tools/live/improve.py status`. Both must run clean.
3. Bump the RULEBOOK to 5.2.29 with the section 3 text, then commit and push. This needs the governor's approval.
4. From the next close, add the `tick` line to C4.
