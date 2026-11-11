# ODTE-FADE: 0DTE options on the FADE signal

Status: **PAPER**, built 2026-11-11 on the governor's instruction ("we are going to build a system that can trade this").
Nothing here is in RULEBOOK.md yet. Nothing here places real orders until the governor says "ODTE live".

## Governor decisions (2026-11-11)

- Structure: long 0DTE calls and puts only. The agent account has options level 2, which allows no spreads.
- Capital: a separate $500 bucket. The governor deposits $500. The system trades only that $500 and its profit. It runs alongside FADE and PULLBACK.
- Data: Robinhood only.

## The rules (v1)

1. **Underlying:** QQQ only.
2. **Signal:** the live FADE rule (RULEBOOK B2) on QQQ, unchanged:
   - Box: the 9:30-10:00 high and low.
   - Break: the first 5-minute close outside the box, by the 10:10 bar.
   - Retest: within 12 bars, a bar trades back to the broken edge (within 0.10%) and closes back inside.
   - Runaway skip at 0.85%.
3. **Entry:** at the checkpoint after the retest bar closes. Buy the same-day expiry QQQ option at the strike nearest spot: a CALL after a failed downside break, a PUT after a failed upside break. Limit at the ask, or mid + 0.02 if the spread is wider than 0.03.
4. **Stop (on QQQ, not the premium):** the failed breakout's extreme, the same level FADE uses. R = the distance from entry to the stop.
5. **Exits (checked at every 5-minute slot), sell at market:**
   - Stop: QQQ trades through the stop.
   - Target: QQQ reaches 2R.
   - Early cut: the 3rd bar after entry closes at -0.5R or worse.
   - Time: 13:30.
6. **Size:** `contracts = floor(min(bucket x 35% / est_loss, bucket / premium))`, where est_loss is the premium lost at the stop. 0 contracts means skip. At $500 this is always 1 contract.
7. **Bucket stop:** at or below $250 (50% of the start), halt. Only the governor clears it.
8. **One position at a time.** No other 0DTE trade that day.

Tool: `tools/odte/odte_live.py --now HH:MM [--ask X] DUMPS` reads the same 5-minute dumps the FADE checkpoint already saves and prints SIGNAL / HOLD / EXIT. `--verify` checks the signal against `tools/live/paper.py` `fade()`. Result: 21 signal days, 0 mismatches.

## Evidence

Script: `tools/odte/odte_backtest.py`. Outputs: `results/odte_backtest.txt`, `results/odte_edge.txt`, `results/odte_trades_base.txt`.
Data: 177 sessions (2026-03-02 .. 2026-11-10) of Robinhood 5-minute bars, plus Robinhood VIX daily.

**Option prices are modelled, not real.** Robinhood keeps no intraday history for expired option contracts. On 2026-11-11, every bar of an expired XSP contract came back interpolated at one flat price. The model:
- Black-Scholes in trading time to the 16:00 expiry.
- IV = VIX open x 0.9 x (1 - 0.5 x time of day), x 1.2 for QQQ.
- Cost: 0.01 half-spread plus 0.04 per contract in fees, each side.
- The 1-cent spread matches the live SPY 0DTE quote. The 3:11 PM IV level also matches it (`data/quotes.csv`).

Per-trade option return, 1 contract on every signal:

| Underlying | Trades | Mean | t | Halves | Worst |
|---|---|---|---|---|---|
| **QQQ** | 13 | **+30.7%** | 3.23 | +10.7% / +47.9% | -34% |
| QQQ, IV x1.2 | 13 | +18.9% | 2.74 | +3.1% / +32.4% | -26% |
| QQQ, 0.03 half-spread | 13 | +29.1% | 3.09 | | |
| IWM | 16 | +8.6% | 1.04 | -11.2% / +28.4% | -38% |
| SPY | 17 | -0.6% | -0.12 | | -28% |
| 6 daily-expiry stocks (NVDA AAPL MSFT AMZN META TSLA) | 51 | -17.5% | -4.06 | -16.9% / -18.2% | -83% |

**Single stocks (governor's screenshot 2026-11-11: Robinhood's daily-expiry equity list is NVDA, GOOGL, AAPL, MSFT, AMZN, META, AVGO, TSLA).** That list covers single stocks only. ETFs (QQQ, SPY, IWM) and index options (XSP, SPX) also expire daily, as the option chains confirm. No bar data for GOOGL and AVGO. On the other six, the FADE signal fails on the stock itself, at -0.1R per trade across all six: MSFT 0 of 6, TSLA 1 of 6, NVDA 6 of 16. Stock 0DTE IV runs 1.3-4.2x SPY's (live 2026-11-11) and spreads run 0.02-0.16. Even where the stock moved the right way (AMZN +0.32R, META +0.55R), the option lost after premium and spread. Every stock is rejected. Stock IV = trailing 20-day realised-vol ratio to SPY. Spread = 2% of premium. Days with a gap over 3% are skipped as an earnings proxy.

QQQ $500 bucket, 1 contract each signal: 13 trades, 11 wins.
- At IV x0.9, $500 grew to $8,560 with a 22.5% max drawdown.
- At IV x1.2, $500 grew to $1,140 with a 31.2% drawdown, and 6 of 13 signals were too expensive to take.

**Why not to trust these numbers yet:**
- 13 trades is a small sample. One more loss changes the win rate by 8 points.
- Prices are modelled. Real 0DTE IV in the morning, skew, and fills are unknown until recorded.
- The FADE rules were tuned on these same months (RULEBOOK E3), so the signal is in-sample.
- Frequency is low: 13 QQQ signals in 177 sessions, about 1 every 2.7 weeks.
- Correlation: live FADE already trades the same QQQ signal through TQQQ/SQQQ. Both lose on the same day.

**Risk at $500:** one QQQ ATM 0DTE costs $250-360. Every trade puts 50-70% of the bucket in premium. A stop-out loses about $40-150, or 8-30% of the bucket. Two to three losses in a row reach the $250 halt.

## Steps to go live

1. **Paper record:** at every slot, run `odte_live.py` next to `paper.py`. Log each paper trade in `tools/odte/trades.csv` with the real bid/ask at entry and exit (`get_option_quotes`). Log a quote row in `data/quotes.csv` at 10:00, 11:00, 12:00 and 13:00 on every trading day, to calibrate IV.
2. **Gate:** at least 8 paper trades. Paper mean return per trade above +10% on real quotes. Real IV ratio within the backtest's 0.75-1.2 range.
3. **Governor says "ODTE live"** and deposits $500. Then set `state.json` mode to live.
4. **Before the deposit lands:** RULEBOOK B4.1 sizing (`total_value`, `buying_power`), the daily loss limit (A1.2), the drawdown stop (A1.13), and USDG parking (B4.8) must subtract the bucket. Without that carve-out, FADE and PULLBACK size up with the $500 and USDG parks it. This change needs D3: governor instruction, rulebook edit, version bump.

## Trend breakout test (2026-11-11, governor: "couple hour trades based on news and current market trends and VIX")

Signal `orb_signal` in `odte_backtest.py`:
- The first 5-minute close outside the 9:30-10:00 range, from 10:00 to 11:30.
- QQQ must agree: above its open for a call, below for a put.
- Buy the ATM 0DTE option. Stop at the range midpoint, 2R target, 2-hour hold.

| Set | Trades | Win | Mean per option | t | Underlying |
|---|---|---|---|---|---|
| 6 stocks | 452 | 27% | -19.3% | -8.4 | +0.03R |
| 6 stocks, no market filter | 652 | 26% | -19.0% | -9.7 | +0.04R |
| 6 stocks, VIX < 18 / >= 18 | 263 / 189 | 26% / 27% | -18.9% / -19.9% | | |
| QQQ | 153 | 30% | -10.9% | -2.2 | -0.01R |
| SPY | 163 | 27% | -13.0% | -3.3 | +0.08R |

Every stock lost, as did every target, VIX split and strike. The underlying moves near 0R after a trend breakout, so the option buyer loses theta plus spread, about 19% per trade.

News cannot be backtested from Robinhood data: there is no historical news feed. A news rule is tested forward only, on paper.

## Day-before entries (2026-11-11, governor: "put the order in the night before or day before, not buy same day")

Script `tools/odte/overnight.py`, output `results/overnight.txt`. Signals use only information known on day D:
- A: buy the 1DTE contract at D 15:45, hold overnight, sell on D+1 at 10:00, 12:00 or 15:30.
- B: order placed the evening of D, fills at the D+1 9:30 open as a 0DTE, sold at 10:00, 12:00 or 13:30.

Baselines: buying a call or put every day loses in both modes (stocks: -4% to -39% per option). Random entries pay the cost, as expected.

Best rows. With 11 rules x 4 groups x 6 exits = 264 rows, a few t near 2 are expected by chance.

| Rule | Mode, exit | Trades | Win | Mean per option | t | Underlying |
|---|---|---|---|---|---|---|
| VIX closes up >10% on D -> QQQ call | A, D+1 10:00 | 18 | 61% | +41.8% | 1.85 | +0.50% |
| same | A, D+1 12:00 | 18 | 56% | +40.5% | 1.67 | +0.70% (t 3.2) |
| same, IV x1.05 / overnight 0.6 | A, 10:00 | 18 | | +29.6% / +32.8% | 1.6 | |
| VIX up >10% -> IWM call | A, 12:00 | 18 | 67% | +20.4% | 1.09 | +0.52% |
| D down >1.5% -> QQQ call | A, 10:00 | 21 | 52% | +17.3% | 0.92 | +0.23% |
| QQQ up >0.5% with market up -> QQQ call | B, 10:00 | 66 | 56% | +14.9% | 2.19 | +0.13% (halves +3% / +27%) |
| 6 stocks, any rule | A or B | | | none above t 2 after the IV fix | | |

Candidate: the **VIX spike reversal**. After VIX closes up more than 10%, buy a QQQ call expiring the next day at 15:45 and sell it the next day at 10:00-12:00.
- 18 events in 8 months, about 2 a month.
- The underlying effect is real (+0.70% by noon, t 3.2). The option edge is not yet significant (t 1.7-1.9).
- Cost: an ATM 1DTE QQQ call on those evenings cost about $380-600. That is 75-120% of a $500 bucket. Use IWM (about $150-260) or an out-of-the-money strike until the bucket grows.

A first version of this test priced the 1DTE entry with afternoon IV and showed +50-85% on every row, puts included. That was a bug, fixed by using the next full day's IV from D's VIX close.
