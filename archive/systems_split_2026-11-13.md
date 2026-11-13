# Four-system build, second pass: train 2022 / 2024 / 2026, test 2023 / 2025 (research only)

Governor instruction (2026-11-12 evening, run on "Run the 3 am" 2026-11-13): train on 2022, 2024, 2026 and test on 2023 and 2025.
System 1 = robust over time. System 2 = most consistent months, each year judged alone. System 3 = do the new systems run in
parallel with the other two or must they replace them. Script `tools/backtest/split_build.py`, output
`tools/backtest/results/split_build_2026-11-13.txt`. Massive 5-minute tape, 6 proxies, 4 PULLBACK legs. Account: 3% risk capped
at cash, one position at a time, 3 entries a day. Champion stays v5.2.47. Nothing adopted.

## Result in one table (year returns, %)

| book | 2022 | 2023 | 2024 | 2025 | 2026 | TRAIN compounded | TEST compounded | max DD | winning months, average (worst year) |
|---|---|---|---|---|---|---|---|---|---|
| LIVE (FADE + PULLBACK) | +11.8 | -29.8 | +15.4 | +18.3 | +151.1 | +223.9 | -16.9 | 31.8 | 60% (25%) |
| SYSTEM 1 train pick | +50.4 | -30.2 | +27.3 | +15.9 | +146.5 | +371.8 | -19.1 | 31.8 | 56% (25%) |
| SYSTEM 2 train pick | +2.2 | -6.0 | +10.4 | +10.3 | +16.7 | +31.7 | +3.7 | 15.8 | 52% (33%) |
| RELVAL alone | +7.5 | -3.1 | +4.5 | +3.3 | +7.6 | +20.8 | +0.2 | 6.0 | 57% (33%) |
| DIP alone | +4.9 | -12.2 | +4.0 | +6.3 | +6.7 | +16.4 | -6.7 | 12.2 | 30% (0%) |
| IBS-TREND alone | +24.1 | +17.9 | +7.3 | +37.2 | +8.0 | +43.8 | +61.7 | 11.8 | 51% (40%) |
| LIVE + RELVAL | +20.2 | -31.9 | +20.6 | +22.2 | +170.1 | +291.3 | -16.8 | 35.1 | 61% (25%) |
| LIVE + IBS-TREND (one position) | +43.0 | -13.5 | +13.6 | +73.7 | +126.8 | +268.6 | +50.3 | 23.9 | 64% (50%) |
| LIVE + IBS-TREND (cash split 50/50) | +29.6 | -19.3 | +13.5 | +46.4 | +135.4 | +246.3 | +18.2 | 24.0 | 64% (50%) |
| LIVE + DIP-or-IBS + RELVAL | +57.2 | -24.0 | +22.8 | +86.2 | +157.7 | +397.4 | +41.5 | 30.5 | 68% (42%) |
| NEW ONLY: DIP-or-IBS + RELVAL | +40.0 | -0.6 | +16.9 | +50.9 | +28.6 | +110.3 | +50.0 | 17.3 | 62% (50%) |

## System 1: robust over time. The tune fails the test.
- Score: worst train year, averaged with the one-step neighbours on the grid, all three train years positive. 1,948 of 14,244 qualify.
- Train pick: FADE target 3R, chandelier 3, runaway skip off. PULLBACK volume 1.0x, runner on a 3-ATR chandelier. Train years +50.4, +27.3, +146.5.
- Test: 2023 -30.2%, 2025 +15.9%. Live: -29.8%, +18.3%. The pick is worse than live in both test years.
- Top 1% of the score: beat live in 2023 82% of the time, in 2025 25%, in both 20%. Rank correlation of the train score with the test result: +0.15.
- All 14,244 tunes on test: median -13.5%. Live -16.9% (40th percentile). No knob setting of FADE + PULLBACK makes 2023 a winning year for a train-chosen pick.
- Conclusion: robustness over time does not come from re-tuning these knobs. It has to come from a different source of return.

## System 2: most consistent months, each year alone. The tune fails the test.
- Score: the worst train year's winning-month share and median month. One strong year adds nothing.
- Train pick: FADE off. PULLBACK volume 1.0x, range 10:00, all out at the morning high. The score drops FADE because FADE's months are uneven outside 2026.
- Train months: 50%, 75%, 60% winning. Test months: 33% winning in 2023 (median -1.04%), 42% in 2025 (median -0.08%).
- Live on test: 25% winning months in 2023 (median -3.43%), 58% in 2025 (median +0.74%).
- Top 1% of the score: worst test-year winning share 25%, same as live. Beat live on both monthly figures 39% of the time.
- Conclusion: the consistent-month tune is calmer and earns little. It does not produce consistent winning months in the test years.
- Month consistency does improve with IBS-TREND added: winning months average 64%, worst year 50%, against 60% and 25% for live.

## System 3: new systems re-chosen on the train years
- **IBS-TREND passes.** Train pick: proxy above its 20-day average, prior close in the bottom 10% of the prior day's range, buy the 3x long leg at 9:35, stop 1% of the proxy, out 15:55. Years +24.1, +17.9, +7.3, +37.2, +8.0. Test +61.7% compounded, drawdown 11.8%. 13 of 18 settings are positive in both test years. 4 of the 6 settings at 0.1 are positive in all five years. 305 trades, 170 signal days of 1,198 (14%).
- **RELVAL is flat on test.** Train pick 1.0% and 2.5 sd (the same setting as before). Test 2023 -3.1%, 2025 +3.3%. 0 of 9 settings are positive in both test years. Drawdown 6%.
- **DIP fails.** Train pick RSI(2) under 5: test 2023 -12.2%, 2025 +6.3%. The looser settings win the test years and lose 2022 and 2024. The family is unstable from year to year.

## Parallel or replacement
Clock (entry median and range, exit):
- FADE 10:15 (10:10-10:20), out by 13:30. PULLBACK 11:35 (10:40-12:35), out by 13:30.
- RELVAL 13:40 (13:35-15:10), out 15:55. DIP and IBS-TREND 9:35, out 15:55.

- **RELVAL: parallel.** It starts after the book is flat. On its signal days the combined account equals the sum of the two (+0.59% vs +0.58% a day on train, +0.29% vs +0.29% on test). Zero interference. Its own edge on test is zero (+0.01% a signal day).
- **IBS-TREND: replacement on its signal days, silent on the rest.** It buys at 9:35 and holds to 15:55, so FADE, PULLBACK and RELVAL do not trade that day unless it stops out early. That is 14% of days. Live had a trade on about half of them. Per signal day on test: live alone -0.26%, IBS-TREND alone +0.68%, both in one account +0.57%.
- **True parallel (cash split 50/50 on signal days) is worse** than giving the day to IBS-TREND: test +18.2% vs +50.3%, train +246.3% vs +268.6%.
- **DIP: same clock as IBS-TREND, same answer, and no edge on test.** 5% of days.

## What this means
1. The live book lost 16.9% over 2023 + 2025 on this tape and no train-chosen tune fixes it.
2. One addition passes the split the governor set: IBS-TREND. With it the book earns +50.3% over the test years and the worst year improves from -29.8% to -13.5%.
3. RELVAL costs nothing in overlap and adds nothing on the test years. It stays a paper candidate.
4. Caution: IBS-TREND was found last night in a search of 135 settings, then re-chosen here from 18. Its test pass is real, and the sample is 305 trades. It sizes at full cash on a 3x leg with a 3% leg stop. Paper first.

Instructions that would start each piece: "shadow IBS-TREND" (paper log, 30 signals, about 10 weeks), "push IBS-TREND", "shadow RELVAL".
