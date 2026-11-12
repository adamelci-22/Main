# Swing-option scanner (1-2 week holds)

Built 2026-11-12 on the governor's instruction: "build the best scanner for finding 1-2 week option holds. Look at everything: news, charts, earnings, macro. Find options with a risk to reward that justifies the chance of success."
Status: **research complete, paper only.** No orders. The account has options level 2, so long calls and puts only.

## Run it

    python3 tools/scanner/scanner.py                                    # after the close: regime, signals, watchlist, next steps
    python3 tools/scanner/scanner.py --contract SYM STRIKE ASK IV SESS  # score a live quote (SESS = sessions to expiry)
    python3 tools/scanner/lab.py [--pass2|--pass3|--pass4]              # the research (results/study*.txt)

Data refresh:
- Robinhood `get_equity_historicals` (interval day, 10 symbols per call), then `build_data.py DUMPS`.
- VIX: `get_index_historicals` (VIX id `3b912aa2-...`), passed with `--vix`.
- Earnings dates: `get_earnings_calendar` windows, then `build_earnings.py DUMPS`.

## The rule that survived: FEAR-DIP

| Part | Rule |
|---|---|
| Regime | SPY 200-day average higher than 20 sessions ago (bull market) **and** VIX close >= 20 (fear) |
| Signal (any one) | C1: above the 200-day and near the 50-day, RSI(2) < 10. C7: closes below the prior 20-day low on volume > 1.5x average. C8: above the 200-day, RSI(2) < 5, 3 down closes in a row |
| Option | CALL, about 60 calendar days (42 sessions) to expiry, 0.75 delta (about 5-8% in the money) |
| Entry / exit | Buy at the next open. Sell at the close of the 10th session. No stop and no target: both tested worse |
| Skip | An earnings date inside the hold. Company-specific bad news (news veto) |
| Size | Premium at most 5% of the account per trade, at most 6 open |

**Evidence** (`results/study_pass4.txt`). 80 symbols, 2022-08 to 2026-11. Robinhood daily bars, VIX, and real report dates. Option prices are modelled.
- 654 trades in 19 fear episodes, 15 of them positive. Win rate 60%. Average win +35%, average loss -19%. **+13.4% per trade** (t 8.9, PF 2.75).
- Development period 2023 to Jun 2024: +29.6% (68 trades). Test period Jul 2024 to Nov 2026: +11.5% (586 trades). The rule and its parameters were fixed before the test period was examined.
- Stress tests:
  - IV 30% richer: +11.8%.
  - IV 50% richer: +10.2%.
  - Spreads doubled to 3% of premium: +10.0%.
  - Both IV 30% richer and spreads doubled: **+8.5%**.
- Portfolio, 5% of equity in premium per trade, at most 6 open: x2.68 from 2023 to 2026, max drawdown 15%. In fractions of the starting account: 2023 +0.27, 2024 +0.28, 2025 +0.26, 2026 +0.86.
- No trades in 2022. The bull-market filter was off all year. The same dip-buying in 2022 lost money (C6/C7 development rows in `study_pass2.txt`).

**Why it works.** Market-wide fear pushes good stocks down with everything else. When the long trend is still up, those dips recover within two weeks. The average stock move was +3.6% in 10 sessions, against +0.7% for random dates. That is enough to beat the option's time decay and spread. Deep in-the-money 60-day calls lose little to time decay over a 10-session hold.

## What failed (all as long options, `results/study.txt`, `study_pass2.txt`)

| Idea | Development | Test |
|---|---|---|
| Random calls (baseline) | -6.3% | -6.8% |
| Random puts (baseline) | -16.0% | -15.1% |
| 55-day high breakout | +2.2% | -2.6% |
| Bollinger squeeze breakout | -3.7% | -10.9% |
| Relative-strength leaders | +1.1% | -6.1% |
| Post-earnings drift up / down | -4.5% / -22.2% | -9.7% / -8.4% |
| Every put signal (rally fail, breakdown) | -7% to -15% | -12% to -28% |
| Uptrend pullback without the fear filter | -9.2% | -1.7% |

Buying options on chart signals alone loses to the option's time decay and spread. The edge exists only when the signal's expected stock move is several percent in two weeks.

## Inputs the scanner uses

- **Charts:** 200, 50 and 20-day averages, RSI(2), RSI(14), ATR, 20 and 55-day highs and lows, Bollinger width, volume vs the 50-day average, 3-month relative strength.
- **Macro:** SPY trend, VIX level and trend, credit (HYG vs its 50-day), rates (TLT vs its 50-day), and 1-month sector leadership. Only SPY trend and VIX passed testing. Credit and VIX-falling filters did not help (`study_pass2.txt`, section 4). They print for context only.
- **Earnings:** 1,072 real report dates from Robinhood, 2021-10 to 2026-11. Off-cycle reporters get 190 quarterly estimates between real dates, used with a ±5-session safety band.
- **News:** Massive `/v2/reference/news` carries per-ticker sentiment. Historical news cannot be backtested here, so news works as a veto only, judged by the session. Example from 2026-11-12: NVDA fell 7-8% after hours on reports the board may remove its CEO. A dip with a company-specific cause is not a fear dip.

## Limits

- Option prices are modelled. Robinhood keeps no history for expired contracts. The IV model is the larger of 20-day and 60-day realised vol, times 1.15. Real IV is higher in fear regimes, so the stress rows matter more than the base row.
- The 19 episodes are the real sample, not the 654 trades. Trades inside one episode move together.
- The test period was mostly a bull market (2024 to 2026). The SPY trend filter is the protection against a 2022-style year. It switched off in 2022 and must keep doing that.
- The daily bars come from one broker feed. Survivorship: the universe is today's large names, so stocks that collapsed and were delisted are missing.

## Next steps

1. Paper trade every FEAR-DIP signal on real quotes: news veto, `--contract` score, entry at the next open, exit at session 10. Log each trade in `tools/scanner/paper_trades.csv`.
2. After 2 fear episodes or 15 paper trades, compare real fills with the model, then decide on live money.
3. Live use needs the agent account's options level 2 (it has it) and a bucket rule like the 0DTE plan.
