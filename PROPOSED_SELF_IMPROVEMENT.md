# PROPOSED: self-improvement loop, RULEBOOK D4 (draft, not in force)

Status: ADOPTED in RULEBOOK v5.2.29 (governor instruction, 2026-10-28). The text below is the design record; RULEBOOK D4 and C4 step 5 are in force.

## 1. What it does

Champion and challenger. **The real account and the paper model keep trading the version in force. A proposed change only runs as a simulated paper challenger until it earns a promotion.**

1. **Tunables.** Twelve numbers may change, nothing else. Bounds and a one-step size are in `tools/live/tunables.json`.

| Tunable | Rule | Now | Range |
|---|---|---|---|
| `fade.retest_tol_pct` | B2.3 | 0.10% | 0.05 to 0.20 |
| `fade.lock_trigger_r` | B2.5 | +0.5R | 0.3 to 0.8 |
| `fade.lock_level_r` | B2.5 | +0.15R | 0.0 to 0.3 |
| `fade.cut_r` | B2.5 | -0.5R | -0.8 to -0.3 |
| `fade.target_r` | B2.5 take-profit | 2R | 1.5 to 3.0 |
| `fade.take_frac` | B2.5/B5.2 share sold at the target | 1/3 | 0.25 to 0.5 |
| `fade.chandelier_atr` | B5.4 runner trail | 2 ATR | 1.5 to 3.0 |
| `pb.vol_mult` | B3.2 | 1.5 | 1.2 to 2.0 |
| `pb.stop_buffer_pct` | B3.7 stop below the dip low | 0.05% | 0.02 to 0.15 |
| `pb.min_stop_pct` | B3.7 minimum stop distance | 0.75% | 0.5 to 1.0 |
| `risk.pct` | B4.1 risk per trade | 3% | 1 to 3, downward only |
| `size.cap_pct` | B4.1 largest position as a % of total account value | 100% | 50 to 100, downward only |

The two sizing rows are offered only with `improve.py menu --risk-off`, which the session uses when the C5 drawdown measure is at ACT. They can only cut size. Raising size above today's level needs the governor to edit `hi` in `tunables.json`. A cut passes only if it lowers drawdown by 15% or more and keeps return per drawdown point within 10%. Both are percentages of the account. No tunable is ever a dollar amount, and `improve.py` refuses to load a tunable named for dollars. `size.cap_pct` adds a third term to B4.1: `floor(cap% x total value / ask)`. It binds only below 100%. It is the lever that moves size, because the 3% risk term rarely binds on 0.5 to 1.5% stops, so `risk.pct` alone moves size very little.

**Still not tunable, and why:**
- **One-position rule.** The model, A1.5, B4.4 and every B5 order step assume one position. Two positions needs a concurrent-position engine, a new buying-power split and new broker checks. That is a redesign, not a number.
- **Ticker lists and the proxy mapping.** The fetch groups (C1.2), earnings skips (A1.9), thin-ticker spread care and the waiters all key on the lists. Picking the best symbols from the dataset is also the easiest way to overfit. First candidate: a drop-one row, which can only shrink the list.
- **Entry hours and flat-by-13:30.** The dataset ends at 13:55, so a later exit cannot be tested. An earlier exit changes the D1 waiters and the C4 close. First candidate: an earlier flat time after the schedule is parametrised.
- **Stop location.** The stop stays beyond the failed breakout's extreme (FADE) and below the dip low (PULLBACK). Only the PULLBACK buffer and minimum distance are tunable.
- **A1 safety controls, the order procedure (B5) and paper-only mode.**
2. **Menu.** `improve.py menu` re-runs the current rules on the 158-session dataset with every one-step change. A row passes only if it beats the baseline in-sample (first 60%) and out-of-sample (last 40%), gains at least 0.01%/day, adds under 1 point of drawdown and keeps 75% of the trades.
3. **Proposal.** At most one. Proposers: the checkpoint session (`session`, default), the Claude API (`api`) or the best passing row (`fallback`). A proposer picks only a passing menu id or `hold`. It cannot invent a value.
4. **Trial.** `improve.py approve --note "..."` starts the challenger. Nothing live changes. Each close, `tick` runs the champion and the challenger on the same saved bars. Neither places an order.
5. **Verdict.** After 15 trading days: promote-ready if the challenger beat the champion by 0.5% of the account or more. Discard if it is down 0.5% or worse. Early discard at -2.0% after 5 days. At 30 days anything short of the promote bar is discarded. A discard never touches the live account.
6. **Promotion.** `improve.py promote --effective <future trading day> --note "..."`. Governor only, never mid-session. The version in force changes only then.
7. **Rollback.** `improve.py rollback --effective <date>` restores the values the promoted version replaced. History is append-only.
8. **Trigger.** `tick` proposes when 5 model trades have closed since the last decision, and only when no challenger or proposal is open.

Not built on purpose: any automatic approval or promotion. This account trades real money and the rulebook says the governor decides.

**Goals.** They live in `tools/live/tunables.json` under `goals`: 0.4% per trading day, 15% drawdown limit (matches A1.13), Sharpe floor 1.2, Sharpe goal 2.0. They are used in three places:
- The menu gate rejects a candidate whose drawdown exceeds 15%, or whose Sharpe falls below 1.2 when the baseline is above it.
- The proposer prompt carries the goals and the paper model's progress against them. The fallback proposer breaks ties by Sharpe gain.
- `improve.py status` prints the progress line. Sharpe is not shown before 2 trading days and is not meaningful before about 30.

The verdict still compares challenger and champion on the same days. It does not test the goals.

## 2. Files

| File | Change |
|---|---|
| `tools/live/improve.py` | new, stdlib only |
| `tools/live/tunables.json` | new, version 1 = today's constants |
| `tools/live/paper.py` | eleven hard-coded numbers become globals set by `apply_tunables(day)`, called at the top of `simulate()`. The `--live` text reads the live values (take-profit R, share sold, early-cut R) and gains one sizing line on FADE entries |
| `archive/improve/` | created on first use: `ledger.jsonl`, `pending.json`, `shadow.csv`, `menu.json` |

Neutrality test: the patched `paper.simulate` was compared with v5.2.28 over 157 backtest sessions, with and without the lock and cut (314 day-runs, 237 trades). Trades, exits and equity were identical in all of them. The `--live` text matched except for the new sizing line.

## 3. Rule text to add (new Part D4)

**D4. Self-improvement loop (v5.2.29).** `tools/live/improve.py` may propose a change to the twelve tunables in `tools/live/tunables.json` (B2.3, B2.5, B3.2, B3.7, B4.1, B5.4). B2.5, B3.7, B4.1 and B5.2 read their numbers from the version in force; the values in those rules are the v1 defaults. An approved proposal runs only as a paper challenger beside the version in force; the real account and the paper model do not change. The challenger is judged against the version in force on the same saved bars (C4 step 5). It goes live only when the governor runs `promote --effective <future trading day>` after a PROMOTE verdict, and the promotion is recorded in the commit with the governor's words. One challenger at a time. Nothing in A1 is tunable. `tunables.json`, `archive/improve/` and the version bump are committed together.

**C4 step 5 (new):** after `paper.py --close`, run `python3 tools/live/improve.py tick <the day's dump files>` and paste its output into the report. Friday summary includes `improve.py status`.

## 4. Evidence today (2026-10-28)

`improve.py menu` on `bt_5m.json.gz` (2026-03-03 to 10-15, 114 trades): baseline +0.521%/day, profit factor 3.68, maximum drawdown 2.8%. First half +0.667%/day, second half +0.303%/day. Annualised Sharpe of the daily returns is 5.7, above the 2.0 goal. The backtest already clears every goal, so the live gap is the open question.

No one-step change passes the gate on any of the twelve tunables, including the size cuts under `--risk-off` (drawdown falls 2.76% to 2.5% at best). The best raw rows are worth +0.001 to +0.008%/day, which is noise. The loop starts in `hold`. That is the correct result for parameters that sit at a local optimum.

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
