# Replay tools (month-end re-test)

- `minute_sim.py` — minute-resolution replay of the C1 gate + B2 management on 12 proxies (cadence, confirmation, range-length tests).
- `suggestions.py` — current rules including v3.117 (volume test before 11:00) and v3.119 (second-entry momentum check), with switches for every idea in the "Suggested Edits — Month-End Review" doc. Run: `python3 suggestions.py`.
- `data/` — 1-minute bars 2026-09-01..10-06 and 5-minute bars from 2026-08-18 (Robinhood historicals, gzipped).

To extend: fetch 1-minute bars (Robinhood caps ~5,000 bars per symbol per call — about 12 days), merge into the same JSON shape (sym -> day -> 390 bars of [o,h,l,c,v,interpolated]), append 5-minute bars likewise, and rerun. Judge each idea on the NEW days only (Oct 7 onward), not the 25 days it was chosen on.
