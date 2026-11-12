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

## P50 deep dive (2026-11-12): can +50% trades be identified with confidence?

The governor asked for a system that identifies, with a stated confidence, trades that return at least 50% with acceptable risk/reward. Files: `p50.py`, `results/p50_study.txt`, `results/p50_fear_dip.txt`.

Setup:
- 166,420 candidates: every symbol and day, call and put.
- Trade: a 21-session 0.60-delta option with a +50% take-profit, otherwise exit at session 10.
- 38 features known at the close: price, trend, volatility, volume, earnings timing, sector, SPY, VIX, credit, rates.
- Gradient boosting, retrained every 6 months on past data only with a 15-session purge. 133,154 out-of-sample predictions.

Results, out of sample:
- Base rate: 22.5% of candidates hit +50%, mean -15.2%.
- The model ranks (AUC 0.59): its lowest bucket hits 6.8% and its highest 31.5%.
- It is overconfident: predicted 50%+ meant 31.5% in practice.
- No bucket made money. Break-even needs about 45% hits, because a miss averages -41% and a hit is capped at +50%.
- The model's top 1 to 5 picks per day hit 31-35% and lost 10% to 15% per trade, in both halves and in every half-year.
- Inside the FEAR-DIP regime (calls, SPY 200-day rising, VIX >= 20, stock RSI(2) < 10, model P >= 0.40): 455 trades on 75 days, 41.1% hit, +3.9% mean. That is the best short-dated result, still below FEAR-DIP's 60-day 0.75-delta structure (+13.4% per trade).
- What drives the probability: call vs put, days to earnings, short vs long volatility ratio, volatility level, VIX, sector. Mostly volatility, not direction.

Conclusion: a confident "+50% in 10 sessions" call does not exist in this data. The best measured odds are about 4 in 10, inside fear dips. Capping winners at +50% removes the tail that pays for the losers. Use FEAR-DIP's structure, which holds 10 sessions without a cap, and treat any P(+50%) shown by the scanner as a ranking, not a guarantee.

## BIG-WIN system (2026-11-12): few trades, let winners run

Governor: "I don't want to sell at 50%. I would rather have a couple of consistent big winners." Study: `bigwin.py`, `results/bigwin.txt`.

**Exit structures** (all FEAR-DIP signals, fixed before running):

| Structure | Mean per trade | Win | Doublers | Episodes positive | IV +30% & spread 3% |
|---|---|---|---|---|---|
| 42-session 0.75-delta, sell at session 10 | **+13.4%** | 60% | 3% | **15/19** | **+8.5%** |
| 63-session 0.70-delta, sell at session 20 | +10.1% | 51% | 3% | 13/19 | +5.0% |
| 63s, trail: stock closes under its 10-day low, max 30 | +5.0% | 32% | 5% | 11/19 | +0.4% |
| 63s, trail: option up 50% then gives back 35%, max 30 | +7.5% | 50% | 6% | 10/19 | +2.2% |

Longer holds make the best trade bigger (+407% against +237%) but lower the average and the consistency. The fear-dip rebound plays out in about two weeks.

**Concentration**, 10-session structure, 92 signal days from 2023-07 (P50 scores are out of sample):

| Pick per signal day | Mean | Episodes positive |
|---|---|---|
| all signals | +13.7% | 14/17 |
| **top 2 by P50** | **+16.4%** | **17/17** |
| top 2 random (200 draws) | +11.9% (95th percentile +14.6%) | |
| top 2 highest beta | +12.6% | 14/17 |
| top 2 deepest 5-day drop | +13.8% | 14/17 |

**The system:**
1. SPY 200-day rising and VIX >= 20.
2. FEAR-DIP signals, ranked by P50.
3. Take the top 2 that pass the earnings and news checks.
4. Buy a 42-session (about 60-day) 0.75-delta call. Sell at the close of the 10th session.
5. Spend 10% of the account in premium per trade, at most 3 open.

Backtest, 2023-07 to 2026-11:
- 61 trades, about 17 a year: x3.48, max drawdown 18%.
- In fractions of the starting account: 2023 +0.19, 2024 +0.47, 2025 +0.08, 2026 +1.74.
- About 1 trade in 6 ends at +50% or more, and about 1 in 25 doubles. The average win is about +35%.

Setup after cloning:
- Run `python3 tools/scanner/p50.py --study`. It builds `data/p50_rows.pkl` in about 20 minutes, then runs the walk-forward.
- Then run `p50.py --score`, which trains `data/p50_model.pkl`.
- Both files are gitignored. `features_at` matches the training features on 300 of 300 sampled rows.
