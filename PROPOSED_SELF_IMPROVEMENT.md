# PROPOSED: self-improvement loop, RULEBOOK D4 (draft, not in force)

Status: draft for the governor. Nothing here changes a trade until the governor approves it and the version is bumped to 5.2.29. The only edit to an existing file is `tools/live/paper.py`, and it is behaviour-neutral (section 2). `RULEBOOK.md` is unchanged.

## 1. What it does

Champion and challenger. **The real account and the paper model keep trading the version in force. A proposed change only runs as a simulated paper challenger until it earns a promotion.**

1. **Tunables.** Five numbers may change, nothing else: `fade.retest_tol_pct` (B2.3), `fade.lock_trigger_r`, `fade.lock_level_r`, `fade.cut_r` (B2.5), `pb.vol_mult` (B3.2). Bounds and a one-step size are in `tools/live/tunables.json`. A1 controls, sizing, ticker lists, hours and the 2R exit are not tunable.
2. **Menu.** `improve.py menu` re-runs the current rules on the 158-session dataset with every one-step change. A row passes only if it beats the baseline in-sample (first 60%) and out-of-sample (last 40%), gains at least 0.01%/day, adds under 1 point of drawdown and keeps 75% of the trades.
3. **Proposal.** At most one. Proposers: the checkpoint session (`session`, default), the Claude API (`api`) or the best passing row (`fallback`). A proposer picks only a passing menu id or `hold`. It cannot invent a value.
4. **Trial.** `improve.py approve --note "..."` starts the challenger. Nothing live changes. Each close, `tick` runs the champion and the challenger on the same saved bars. Neither places an order.
5. **Verdict.** After 15 trading days: promote-ready if the challenger beat the champion by 0.5% of the account or more. Discard if it is down 0.5% or worse. Early discard at -2.0% after 5 days. At 30 days anything short of the promote bar is discarded. A discard never touches the live account.
6. **Promotion.** `improve.py promote --effective <future trading day> --note "..."`. Governor only, never mid-session. The version in force changes only then.
7. **Rollback.** `improve.py rollback --effective <date>` restores the values the promoted version replaced. History is append-only.
8. **Trigger.** `tick` proposes when 5 model trades have closed since the last decision, and only when no challenger or proposal is open.

Not built on purpose: any automatic approval or promotion. This account trades real money and the rulebook says the governor decides.

## 2. Files

| File | Change |
|---|---|
| `tools/live/improve.py` | new, stdlib only |
| `tools/live/tunables.json` | new, version 1 = today's constants |
| `tools/live/paper.py` | `RETEST_TOL` and `PB_VOL` replace two literals; `apply_tunables(day)` is called at the top of `simulate()` |
| `archive/improve/` | created on first use: `ledger.jsonl`, `pending.json`, `shadow.csv`, `menu.json` |

Neutrality test: the patched `paper.simulate` was compared with v5.2.28 over 157 backtest sessions, with and without the lock and cut (314 day-runs). Trades, exits and equity were identical in all 314.

## 3. Rule text to add (new Part D4)

**D4. Self-improvement loop (v5.2.29).** `tools/live/improve.py` may propose a change to the five tunables in `tools/live/tunables.json`. An approved proposal runs only as a paper challenger beside the version in force; the real account and the paper model do not change. The challenger is judged against the version in force on the same saved bars (C4 step 5). It goes live only when the governor runs `promote --effective <future trading day>` after a PROMOTE verdict, and the promotion is recorded in the commit with the governor's words. One challenger at a time. Nothing in A1 is tunable. `tunables.json`, `archive/improve/` and the version bump are committed together.

**C4 step 5 (new):** after `paper.py --close`, run `python3 tools/live/improve.py tick <the day's dump files>` and paste its output into the report. Friday summary includes `improve.py status`.

## 4. Evidence today (2026-10-28)

`improve.py menu` on `bt_5m.json.gz` (2026-03-03 to 10-15, 114 trades): baseline +0.521%/day, profit factor 3.68, maximum drawdown 2.8%. First half +0.667%/day, second half +0.303%/day.

No one-step change passes the gate. The best raw rows are worth +0.001 to +0.003%/day, which is noise. The loop starts in `hold`. That is the correct result for parameters that already sit at a local optimum.

## 5. Limits

- The dataset ends 2026-10-15. Refresh it with `build_data.py` before trusting a menu run.
- The menu optimises past data. The in-sample and out-of-sample split reduces the risk. It does not remove it.
- A 15-day trial has little power because most days produce identical results under both versions. Expect most challengers to be discarded or to take the full 30 days.
- The shadow run ignores slippage, fills and the A1 checks. It compares the two rule sets, not real execution.
- Live paper results since 2026-10-23 are far below the backtest average. Look at execution and data gaps (C5 health tracker) before tuning rules.

## 6. Install (for the live session)

1. Review the diff: `git diff main..claude/self-improvement-loop`.
2. Run `python3 tools/live/improve.py menu` and `python3 tools/live/improve.py status`. Both must run clean.
3. Bump the RULEBOOK to 5.2.29 with the section 3 text, then commit and push. This needs the governor's approval.
4. From the next close, add the `tick` line to C4.
