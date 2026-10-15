# Pullback buy — candidate specification

Status: **adopted — live from 2026-10-16 as RULEBOOK B3 (v5.0).** The rulebook governs where this file differs. The rules below are the governor's choices from 2026-10-15.
Code: `tools/backtest/pb_final.py`. Results: `tools/backtest/results_pb_final.txt`.

## List (inverse/fear tickers; long only, on each ticker's own chart)

- **Current list (RULEBOOK B1):** SOXS, LABD, TECS, UVXY, NVD. BTCZ, SQQQ and TZA were cut; NVD was added under a fixed rule (`pb_replace.py`).
- **Earlier List A:** SOXS, SQQQ, TZA, TECS, BTCZ.
- **Earlier List B:** List A plus LABD and UVXY.

## Entry

1. The 9:30–9:45 high is the opening range.
2. **Breakout on volume:** a later 5-minute bar closes above that high, on volume above 1.5× the average of the prior 6 bars.
3. **Uptrend:** at the trigger, the 9-EMA is above the 20-EMA and price closes above the 9-EMA. The EMAs carry over from the prior day.
4. **The dip:** 2–5 bars, each either red or making a lower high. The dip's lowest low lies between 0.5% below the 20-EMA and 0.1% above the 9-EMA.
5. **Trigger:** a bar closes above the prior bar's high. Trigger bars run from 10:10 to 12:50.
6. **Limit buy** at the trigger close. It fills only if the next bar trades down to it; otherwise, keep watching that ticker.
7. **Stop** = dip low × (1 − 0.05%). Skip the trade if the stop is less than 0.75% below the entry.
8. **Minimum target:** skip unless the morning high (the high before the dip) is at least 0.75× the stop distance above the entry, and at least 0.25% above it.
9. **Optional OCO rule:** skip if the stop and target are less than $0.10 apart. This is Robinhood's OCO minimum, and it only affects BTCZ.

## Exit

- **One OCO order:** sell 100% at the morning high, or stop out.
- **Time exit:** sell anything still open at 13:30.

## Account rules

- $2,000 account; risk 3% per trade, capped at available cash.
- One position at a time; at most 3 entries a day; at most one setup per ticker per day.
- The earliest trigger is taken first. Ties go to the higher RVOL (the proxy's volume against its 20-day average at the same time of day).

## Results, 2026-04-07 – 10-14

| List | Trades | Win % | %/day | Return | Max DD | H1 / H2 %/day |
|---|---|---|---|---|---|---|
| A | 25 | 64% | +0.082 | +11.4% | 2.5% | +0.121 / +0.043 |
| A + $0.10 OCO rule | 22 | 59% | +0.067 | +9.1% | 2.2% | +0.078 / +0.055 |
| B | 40 | 70% | +0.157 | +23.0% | 2.6% | +0.161 / +0.153 |
| B + $0.10 OCO rule | 37 | 68% | +0.142 | +20.5% | 2.2% | +0.118 / +0.166 |
