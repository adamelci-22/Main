# 2-Bar Compressed ORB (15-minute) — system specification

Status: **rejected (no edge).** Kept as research history. Its finding — the 10:00 range break fades on these proxies — led to the FADE system now in RULEBOOK B2.
Code: `tools/backtest/twobar.py`. Results: `twobar.txt` section of `tools/backtest/results/research_results_former.txt`.

## Universe

| Proxy (chart only) | Bull leg | Bear leg | Leverage |
|---|---|---|---|
| QQQ | TQQQ | SQQQ | 3x |
| SOXX | SOXL | SOXS | 3x |
| IWM | TNA | TZA | 3x |
| XLK | TECL | TECS | 3x |
| IBIT | BTCL | BTCZ | 2x |

## Rules as written (the outside write-up)

1. **Chart:** the proxy on 15-minute bars. Bar 1 is 9:30–9:45 and Bar 2 is 9:45–10:00.
2. **Box:** the highest high and lowest low of Bars 1 and 2 (9:30–10:00).
3. **Trigger:** during Bar 3 (10:00–10:15) only.
   - The proxy trades above the box high: buy the bull leg.
   - The proxy trades below the box low: buy the bear leg.
   - No candle close is needed.
   - If both edges are hit in the same 5-minute bar, there is no trade.
   - If there is no break by 10:15, that proxy has no trade for the day.
4. **Stop:** the low of Bar 2 for a long, the high of Bar 2 for a short, measured on the proxy.
5. **Target:** sell half at 1:1 risk-to-reward and move the stop to breakeven on the rest. The rest runs to the 15:55 close or the breakeven stop.
6. **Account rules (house rules, same as the pullback buy):**
   - $2,000 account, 3% risk per trade, capped at available cash.
   - One position at a time, at most 3 trades a day.
   - Simultaneous triggers are ranked by proxy RVOL.

## Live-execution version

The checkpoints run every 5 minutes, and Robinhood cannot place an order on a leg conditional on the proxy's price. So the live version changes two things:
- **Entry:** a completed 5-minute bar trades through the box, and the leg is bought at the next checkpoint at market.
- **Half sale:** the 1:1 half is sold at the next checkpoint after the target trades. This means cancel the stop, sell half, and place a new stop at breakeven.

## Results (2026-04-07 – 2026-10-14, 133 days, leg cost 0.06% round trip)

| Version | Trades | Win % | %/day | Return | Max DD | H1 / H2 %/day |
|---|---|---|---|---|---|---|
| As written | 130 | 46% | −0.339 | −37.4% | 41.9% | −0.498 / −0.183 |
| Live-execution | 133 | 50% | −0.149 | −19.3% | 26.7% | −0.230 / −0.069 |
| *Pullback buy (reference, live-execution)* | 94 | 53% | *+0.108* | *+14.6%* | 5.8% | +0.145 / +0.073 |

**Grid:** 192 variants were tested. They cover the entry type (checkpoint, or wait for a 15-minute close), the trigger window (Bar 3 only, up to 10:30, up to 11:15), four stops (Bar 2, trigger bar, box edge, midpoint), four exits (half at 1:1 + breakeven, 1R, 2R, time only) and two time exits (12:30, 15:55).
- 7 of 192 variants were positive in H1. **0 of 192 were positive in H2.**
- The walk-forward pick (best H1) made +0.182%/day in H1 and **−0.504%/day in H2**.

**Why it fails here:** after the trigger, the proxy moves against the breakout on average.

| Trigger type | Move at 60 minutes | Move by the close | Share in profit |
|---|---|---|---|
| Instant break | −0.110% (≈3 SE) | −0.109% | 44% |
| 15-minute close outside the box | −0.152% | −0.224% | 40% |

Waiting for confirmation makes the fade worse. On these five proxies over these seven months, the 10:00 range break is a fade signal, not a continuation signal.

## What would change this verdict

- **A longer intraday history** (2–3 years from another data source) showing that the continuation exists in other regimes.
- **Forward results**, if the governor chooses to paper-track it alongside the pullback buy.
