

<!-- E5 as of the 2026-10-29 9:00 refresh (replaced wholesale) -->
## E5. Live context — dated, refreshed at 9:00, replaced wholesale

**Wednesday 2026-10-28 (before the open), v5.2.22 (governor: "lets remove the frozen trail").** FADE exits from today: +0.15R lock at the first +0.5R close, early cut at 15 min at −0.5R, ⅓ at 2R with the stop to breakeven, 2-ATR chandelier on the rest, out 13:30. The frozen trail never traded live.

**Wednesday 2026-10-28 (before the open), v5.2.21 (governor: "push it").** PULLBACK adds NVDQ NVD MSFU SSG (B1); C1.2 fetches a third group (NVDQ NVD MSFU SSG); the A1.9 earnings skip is back: **MSFT reports today (10-28) after the close, so no MSFU entry on Thu 10-29**; NVDA reports 11-17 pm, so no NVD/NVDQ on 11-18. PULLBACK health tracker added (C5).

**Wednesday 2026-10-28 (early, before the open), v5.2.20 (governor):** FADE health tracker added to the 13:30 report (C5, `tools/live/health.py`, `archive/health_log.csv`, new `reached_2R` column in `archive/live_trades.csv`, backfilled: 10-27 TNA = yes). No trading rule changed. Seed row 2026-10-27: 1 FADE trade, drawdown 0.1%, HEALTHY (provisional).

**Tuesday 2026-10-27 (8:50 PM ET), v5.2.19 adopted (governor: "lets push B + C").** FADE +0.15R lock at the first +0.5R close and early cut at 15 minutes if the close is −0.5R or worse (B2.5, B5.3), from Wed 2026-10-28. Same commit fixes `paper.py`, which never switched the v5.2.18 frozen trail on (`FROZEN_ON` stayed False); both now switch on by date in `simulate()`. The Wednesday chain prompts say v5.2.17; RULEBOOK governs.

**Tuesday 2026-10-27, v5.2.18 adopted (governor).** FADE frozen 1R trail before 2R, capped at +0.75R (B2.5, B5.3), from Wed 2026-10-28. The Wednesday chain prompts say v5.2.17; RULEBOOK governs.

**Tuesday 2026-10-27, 13:30 close (v5.2.17).** Flat, no open orders, **$2,568.92** (+$33.36, +1.32% on the day). One real trade: FADE TNA (fade of IWM), 44 sh @ 56.8299 at 10:10; 14 sh take-profit @ 57.61 (10:53); 30 sh closed by the governor by hand @ 57.58 (11:07). Model: +1.89% (runner out on the chandelier 12:40). Losing streak 0/5; A1.13 clear (high $2,571.81). Entries stopped at 11:40 on the governor's word. Running total since 2026-10-16: 3 real trades, all green, +$75.49. **Wednesday 2026-10-28 chain armed (v5.2.17 wording): all 46 confirmed with list_triggers; ids in `archive/chain_ids.json`.** The 12:00-13:25 waiters of today were killed by the app at about 11:55 (account flat, day ended; no slot lost that mattered).

**Tuesday 2026-10-27, v5.2.17 adopted (governor: "let's skip fridays").** No FADE entries on Fridays from Fri 2026-10-30 (A1.10); PULLBACK unchanged. `paper.py` enforces it.

**Tuesday 2026-10-27, 11:40 (governor: "Let's end the day").** No new entries for the rest of the day (treated as a stop for today only, not a kill-switch for tomorrow). The real account is flat at $2,568.92 with no open orders; the model's TNA runner is a ghost (run slots with `--real-free`). Result so far: one real trade, FADE TNA, +$33.36 (see `live_trades.csv`). The remaining waiters, the 13:30 close and Wednesday's arming are left as they are until the governor says otherwise.

**Wednesday 2026-10-28, 9:00 research (v5.2.25).**
- **Real account:** flat, no positions, no open equity or OCO orders, **total value $2,568.92** (cash $2,568.92, no pending deposit, unchanged from Tuesday's 13:30 value, so no deposit or withdrawal). Daily loss limit (-3%) = $77.07, stop at $2,491.85.
- **Controls:** losing streak 0/5. **A1.13 drawdown stop: clear**, high $2,571.81, stop level $2,186.04, value -0.11% from the high (`hwm.py check 2568.92`). No A1.10 restriction; normal full session. Friday FADE skip starts Fri 10-30.
- **Corporate actions (C3.2):** clean. All 13 funds, NVDQ NVD MSFU SSG and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.4% vs TQQQ +1.1% / SQQQ -1.1%; SOXX +0.8% vs SOXL +2.3% / SOXS -2.3%; IWM +0.1% vs TNA +0.3%; XLK +0.5% vs TECL +1.4% / TECS -1.1%; XBI -0.3% vs LABU -1.4% / LABD +1.1%; XLF -0.3% vs FAS -1.1% / FAZ +0.8%); none near 20%. Wide premarket spread on SSG (10.71 / 12.83) and TECL, LABU (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-30..2026-10-27) -> `archive/paper_rvol_2026-10-28.json`.
- **Context:** large reports before the open include BIIB, BSX, GE Vernova, ADP, GRMN, PSX, VRT; after the close MSFT, GOOGL, GOOG, KLAC, NOW, EBAY, FTNT, F, FDX, TMUS (none are traded proxies; MSFT is MSFU's underlying, so no MSFU entry Thu 10-29, A1.9). The Fed meets today (Wed 10-28). No scheduled macro release found before 13:30 in the data available.

**Tuesday 2026-10-27, 9:00 research (v5.2.16).**
- **Real account:** flat, no positions, no open equity or OCO orders, **total value $2,535.56** (cash $2,535.56, no pending deposit, unchanged from Monday's close; the $2,500 deposit has not landed). Daily loss limit (-3%) = $76.07, stop at $2,459.49.
- **Controls:** losing streak 0/5. **A1.13 drawdown stop: clear**, value = the high $2,535.56, stop level $2,155.23 (`hwm.py check 2535.56`). No A1.10 restriction; normal full session.
- **Corporate actions (C3.2):** clean. All 13 funds and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.4% vs TQQQ +1.3% / SQQQ -1.3%; SOXX +1.7% vs SOXL +5.1% / SOXS -4.9%; IWM +0.4% vs TNA +1.5%; XLK +0.7% vs TECL +2.3% / TECS -1.7%; XBI -0.2% vs LABU +0.8% / LABD +0.1%; XLF +0.5% vs FAS +1.2%; UVXY -1.2%); none near 20%. Wide premarket spreads on TECL, TECS, LABU, LABD (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-29..2026-10-26) -> `archive/paper_rvol_2026-10-27.json`.
- **Context:** large reports before the open include UPS, KO, PYPL, BA, SPGI, FCX, RCL, HCA; after the close V, STX, NXPI, TER, HOOD, ENPH (none are proxies). The Fed meets Wed 10-28. No scheduled macro release found before 13:30.

**Monday 2026-10-26, 13:30 close (v5.2.16).**
- **Real account:** flat all day, no positions, no open equity or OCO orders at 13:30, total value **$2,535.56** (unchanged; no trade, no deposit yet). Losing streak 0/5. No safety control fired. A1.13 drawdown stop clear (high $2,535.56, stop level $2,155.23).
- **Signals:** none. FADE: XLF and IWM broke up but their retests held (no close back inside), the other four never broke in the window; PULLBACK: TECS volume breakout (10:05) failed the trend test, UVXY broke out at 12:45 but never dipped. Early shutdown at 12:55 (account flat). Model: 0 trades, equity $2,520.60.
- **Waiters:** 72 of 72 entry slots (2 days) covered by the waiter first, lag 7 s every time (`slot_report.py`). **Fault found:** the 13:30 waiter started at 11:25 hit the 2-hour cap and was killed at 13:25 before it could fire. Fix in D1: batch 2 is 11:30-13:25 only, and the 13:20 checkpoint starts a fresh 13:30 waiter (timeout 900000); the scheduled 13:30 close trigger stays the primary.
- **Tuesday 2026-10-27 chain armed:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids in `archive/chain_ids.json`. ET is UTC-4 until Sun 11-01; the DST check runs Fri 10-30 8:15 PM ET.
- **Research this session (no live rule changed):** FADE diagnosis on Databento 2023-03..2026-10 (`results/fade_*.txt`) and PULLBACK-only run (`results/db_pb.txt`): the edge is absent 2023-03..2026-02 on the Mini feed and present Mar-Oct 2026; Mini bars are not a fair test of the thin funds (`results/db_feed_compare.txt`). Candidate (not adopted, waits for the governor): stop floor 0.3% + touch within 3 bars. Governor instruction 2026-10-26: A1.13 hard stop at -15% from the all-time high (added, v5.2.16). A Massive (Polygon) consolidated-tape download was run in another session; not yet in this repo.

**Monday 2026-10-26, 9:00 research (v5.2.16).**
- **Real account:** flat, no positions, no open equity or OCO orders at 9:00, **total value $2,535.56** (cash $2,535.56, no pending deposit, unchanged from Friday's close; the $2,500 deposit has not landed). Daily loss limit (-3%) = $76.07, stop at $2,459.49. Floor 50% of deposited cash.
- **Controls:** losing streak 0/5 (2 real trades, both wins). **A1.13 drawdown stop (new, v5.2.16): clear**, high $2,535.56, stop level $2,155.23 (`archive/hwm.json`, `hwm.py check 2535.56`). No A1.10 restriction; normal full session. No single stock is traded, so no earnings skip applies.
- **Corporate actions (C3.2):** clean. All 13 funds and 6 proxies active; premarket moves match their underlyings at the stated leverage (QQQ +0.5% vs TQQQ +1.4% / SQQQ -1.4%; SOXX +1.3% vs SOXL +3.7% / SOXS -3.4%; XLK +0.6% vs TECL +1.7% / TECS -1.8%; IWM +0.1% vs TNA +0.3%; XBI +0.3% vs LABU +0.8% / LABD -1.1%; XLF flat vs FAS +0.3%; UVXY -2.6%); none near 20%. Wide premarket spreads on TECL, TECS, LABU (A1.7 will matter at the open).
- **RVOL baseline:** 20 sessions (2026-09-28..2026-10-23) -> `archive/paper_rvol_2026-10-26.json`.
- **Context:** first session on the v5.2.13/14 lists (XLF in, AMD and NVD out). Futures higher premarket (QQQ +0.5%, semis +1.3%). Before 13:30: VZ reported before the open; large reports after the close include CDNS, NUE, WELL, HIG (not proxies). The Fed meets Wed 10-28. No scheduled macro release found before 13:30.

**Friday 2026-10-23, 9:00 research (v5.2.12).**
- **Real account:** flat, no positions, no open or recent orders, **total value $2,508.09** (all cash, buying power $2,508.09). The daily loss limit (A1.2) is measured from it: a close at or below **$2,432.85** blocks entries.
- **Controls:** losing streak 0/5. No AMD or NVIDIA earnings today (AMD reports Tue 2026-11-03 after the close: skip the AMD fade row Wed 11-04). Regular full session, no holiday.
- **Corporate actions (C3.2):** clean. All 14 funds and 7 proxies active. Premarket moves match their underlyings at the stated leverage (TQQQ -0.8% vs QQQ -0.2%, SOXL +0.7% vs SOXX +0.2%, TNA -1.9% vs IWM -0.6%, LABU -2.6% vs XBI -0.8%); nothing near 20%.
- **RVOL baseline:** 20 sessions (2026-09-25..2026-10-22) -> `archive/paper_rvol_2026-10-23.json`.
- **Context:** futures slightly lower after Thursday's tech sell-off (S&P about -0.2%, Nasdaq 100 about -0.1%). AI-infrastructure financing worries, high oil, French bond turmoil; the Fed meets next week (Oct 28), hike bets have faded. No scheduled data release found before 13:30.
- **Model:** equity $2,087.46. Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46.
- **Today is the first day of the slot waiters (v5.2.10-12):** 9:30 starts batch 1 (10:00-11:25), the 11:25 waiter starts batch 2 (11:30-13:25); waiter fire times log to `archive/waiter_log.csv`; scheduled twins deleted after flat completions via `archive/chain_ids.json`.
- **Still unverified live:** the 1/3 OCO + 2/3 stop together on one FADE position (E2 item 1); no test order was run (governor, 2026-10-22).

**Thursday 2026-10-22, 9:00 research (v5.2.7).**
- **Real account:** flat, no positions, no open equity or OCO orders at 9:00, **total value $2,508.09** (cash $2,508.09; deposited cash $2,493.43, floor $1,246.72). Daily loss limit (-3%) = $75.24, stop at $2,432.85.
- **Controls:** losing streak 0 (1 real trade, a win). AMD reports Tue 2026-11-03 after the close (skip AMD fade row Wed 11-04); no AMD or NVIDIA report today; normal full session (`paper.py` calendar ends 2026-12-31).
- **Corporate actions (C3.2):** clean. All 14 funds and 7 proxies active; premarket moves match their underlyings at the stated leverage (SOXX -4.2% vs SOXL -12.5% and SOXS +12.7%; QQQ -1.6% vs TQQQ -4.9% and SQQQ +5.0%; XLK -2.2% vs TECL -5.9% and TECS +6.4%; AMD -4.7% vs AMDL -9.5% and AMDD +4.4%); none more than 20% off yesterday's close.
- **RVOL baseline:** 20 sessions (2026-09-24..2026-10-21) -> `archive/paper_rvol_2026-10-22.json`.
- **Context:** sharp risk-off premarket, semis hardest hit (SOXX -4.2%, AMD -4.7%, NVDA -2.4%, QQQ -1.6%, IWM -0.6%, XBI -0.5%). A web search did not confirm a cause for today; none is assumed. Earnings before 13:30 are large non-proxy names only (HON, UNP, PG, LMT, NSC, SPOT, CMCSA and similar); WDC reports after the close. Wide premarket spreads on thin legs (TECL, LABU, TECS), so expect the spread check (A1.6) to matter at the open.
- **Model:** equity $2,087.46 (excludes the $500 deposit). Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46. Yesterday (Wed 10-21): no signals either system, early shutdown at 12:55.
- **Routine for today:** fetch all three C1.2 groups every slot (incl. NVDA); `--real-free` only if the governor closes a position by hand; reports lead with FADE status and a one-line PULLBACK status (governor, 2026-10-20). If a slot fires before its bar closes, the newest bar is one short (E6); refetch if a signal is near trigger.
- **Still unverified live:** the 1/3 OCO + 2/3 stop together on one FADE position (E2 item 1).
- **Chain:** Thursday's 46 slots verified complete at the Wednesday 8:00 PM backup. Slot backups (D1, v5.2.8) armed by hand for the rest of today: 16 one-shots at 10:17, 10:22, ... 11:32 ET (2 minutes after the 10:15-11:30 primaries). The 10:05 primary arrived 7:27 late (14:12:27 UTC), after a manual 10:10 run had covered it; the 10:10 primary was likewise a duplicate. This day's 13:30 close arms Friday 2026-10-23. Bimonthly reminder `trig_01Dwv81fMNH5Rw141Uy3wLKP`, next 2026-11-01.

**Thursday 2026-10-22, 13:30 close (v5.2.12).**
- **Real account:** flat, no positions, no open orders at 13:30, total value **$2,508.09**, unchanged on the day. No real trade today. Losing streak 0/5.
- **Day:** no real or model trades. FADE: no entries (AMD and XLK retests expired or held). PULLBACK: TECS (11:30) and NVD (11:25, 12:25) formed setups that failed the room-to-target and stop-distance filters (B3.8); nothing qualified. Early shutdown done at 12:55 (13:00-13:25 triggers deleted).
- **Model:** equity $2,087.46 (no trades today). Running totals since 2026-10-16: 1 real trade, 1 win, +$14.66; model 2 trades, both wins, +$87.46.
- **Changes today:** v5.2.9 FADE late band 1.5%; v5.2.10 no slot backups, one-shot slot waiters (`slot_clock.sh`); v5.2.11 delete the scheduled twin after a flat waiter checkpoint (`archive/chain_ids.json`); v5.2.12 success-rate tracking (`archive/waiter_log.csv`, `slot_report.py`), review set for Fri 2026-11-06 (`trig_018N3oepVLFhbBuPwtwcTWJ1`).
- **Friday 2026-10-23 chain armed and verified:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids of the 10:00-12:55 primaries in `archive/chain_ids.json`. Monday arms Fri 13:30 with UTC-4 (UTC-5 from Mon 2026-11-02).
- **Scheduler lag (E6):** median 62 s, :05/:10/:15 slots worst; clock waiter wake measured 4-10 s.

**Friday 2026-10-23, 13:30 close (v5.2.12).**
- **Real account:** flat, no positions, no open orders at 13:30, total value **$2,535.56**. 9:00 value was $2,508.09. Losing streak 0/5. No safety control fired.
- **Real trade:** UVXY PULLBACK, 131 sh, 19.0599 -> 19.2701, **+$27.47** (1.100% of position); model +$17.21 (0.824%). Entered at the last entry slot, closed by the 13:30 time exit.
- **Model reset (governor instruction, 2026-10-23):** the model/real comparison restarts at v5.2.12, from 2026-10-23. Model history before today is archived in `archive/paper_trades_pre_v5.2.12.csv` and `archive/paper_state_pre_v5.2.12.json` (3 trades, +$104.67, equity $2,104.67). The model is re-based to the $2,500 account base at the start of 2026-10-23 (`paper.py` default); today's UVXY trade is re-sized to that base: +$20.60 (0.824%), equity **$2,520.60**, streak 0. Real trades stay in `archive/live_trades.csv` (2 trades, +$42.13 since 2026-10-16); the comparison counts real trades from 2026-10-23 only (1 trade, +$27.47 vs model +$20.60). No trading rule changed.
- **Waiters, first day:** all slots fired 4-10 s after the clock; a container restart at 11:46 ET killed 20 waiters, re-created at once (see E6). Log in `archive/waiter_log.csv`.
- **Monday 2026-10-26 chain armed:** 46 triggers (9:00, 9:30 with the waiter start, 10:00-13:25, 13:30, 8:00pm), ids of the 10:00-13:25 primaries in `archive/chain_ids.json`. Verified by the Friday 8:00pm check.

<!-- E5 as of the 2026-11-02 9:00 refresh (replaced wholesale) -->
**Thursday 2026-10-29, 9:00 research (run at 8:44 ET by the 8:41 morning trigger, v5.2.37).**
- **9:00 value (A1.2 base): $2,573.22**, flat, no open orders. Drawdown stop clear: high $2,596.99, stop $2,207.44, −0.92% from the high. Daily loss limit fires at $2,496.02 (−3%).
- **Controls:** losing streak 0 (4 live trades, all wins). Trading day, not in `NO_TRADE`. **MSFU: no entry today** (MSFT reported 10-28 pm; `EARNINGS_SKIP` matches). NVDA next reports 11-17 pm, so NVD/NVDQ skip 11-18 (matches). **Friday 10-30: no FADE entries** (A1.10).
- **Corporate actions:** clean. All 17 traded funds and 6 proxies active; each premarket move matches its underlying (SOXX −2.4%, SOXL −7.1%, SOXS +7.4%; QQQ −1.3%).
- **RVOL baseline:** 20 sessions 2026-10-01..10-28 → `archive/paper_rvol_2026-10-29.json`.
- **Context:** semis and Nasdaq gap lower premarket (SOXX −2.4%, QQQ −1.3%); MSFT +1.7% after earnings. A gap day: watch the 9:30-10:00 box for a FADE break and retest.
- **Triggers (governor 2026-10-29):** DST check deleted (the chain it checked is retired; waiters and the two standing triggers follow New York time by themselves); the 11-06 review is now a waiter coverage report only (`trig_018N3oepVLFhbBuPwtwcTWJ1`).
- **Improvement cycle (D4):** FADE 2 of 5 trades, PULLBACK 1 of 5; no trial running; no proposal pending (p2 withdrawn 10-28).

<!-- E5 as of the 2026-11-03 9:00 refresh (replaced wholesale) -->
**Friday 2026-10-30, 9:00 research (8:42 ET, morning trigger, v5.2.39).**
- **9:00 value (A1.2 base): $2,545.80**, flat, no open orders. Drawdown stop clear (high $2,596.99, −1.97%). Daily loss limit fires at $2,469.43 (−3%).
- **Controls:** losing streak 1 (10-29 TZA). Trading day. **Friday: no FADE entries (A1.10); PULLBACK trades.** Earnings: none affecting today (NVD/NVDQ skip 11-18).
- **Corporate actions:** clean; all funds active, premarket moves match their underlyings.
- **RVOL baseline:** 20 sessions 2026-10-02..10-29 → `archive/paper_rvol_2026-10-30.json`.
- **Context:** heavy semiconductor sell-off premarket (SOXX −6.7%, QQQ −2.6%, NVDA −2.7%; SOXL −20%, SOXS +20%). Inverse funds (SOXS, TECS, SSG, NVDQ, NVD, UVXY) are PULLBACK candidates on a trend day; spreads on SSG are wide premarket (12.70/14.50), the 0.30% spread check (A1.7) applies.
- **Cycle (D4):** FADE 0 of 5 under v2, PULLBACK 1 of 5; no trial, no pending proposal.

**Monday 2026-11-02, 9:00 research (morning trigger fired 9:13:10 ET, 32 minutes after its 8:41 slot, v5.2.39).**
- **9:00 value (A1.2 base): $2,571.18** (pre-open, read 9:15 ET), flat, no open orders. Drawdown stop clear (high $2,596.99, -0.99%). Daily loss limit fires at $2,494.04 (-3%).
- **Deposit check (D1):** +$0.99 against the 10-30 13:30 value ($2,570.19). Governor (2026-11-02): it is the monthly interest on the account's cash. Not a deposit: `hwm.py deposit` not run, high unchanged ($2,596.99), model equity unchanged. Month-end interest credits will recur and are treated the same way.
- **Controls:** losing streak 0 (10-29 TZA loss, then SSG and LABD wins). Monday: FADE and PULLBACK both trade. Earnings: MSFT reported 10-28 pm (next 2027-01-27 pm, matches `EARNINGS_SKIP` 2027-01-28). NVDA next reports 2026-11-17 pm, verified (NVD/NVDQ skip 11-18, matches). No earnings skip today.
- **Corporate actions:** clean. All 19 funds and proxies active; each premarket move matches its underlying (QQQ +0.8%, TQQQ +2.4%; SOXX +1.4%, SOXL +4.1%, SOXS -4.2%). Wide premarket spreads on TECL, LABU, TECS and FAS: A1.7 applies at order time.
- **RVOL baseline:** 20 sessions 2026-10-05..10-30 -> `archive/paper_rvol_2026-11-02.json`.
- **Context:** premarket proxies up 0.4% to 1.4% (SOXX +1.4%, QQQ +0.8%, IWM +0.8%, XLK +0.9%, XLF +0.6%, XBI +0.4%). No event calendar checked beyond earnings.
- **Triggers (A2):** the 8:41 and 13:30 standing triggers and the two dated ones are enabled on this session. The morning trigger fired 32 minutes late. About 12 disabled, fired one-shot checkpoints from 10-27 and 10-28 remain on the old session: reported, not deleted. The two `v5 paper` triggers belong to another session.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null in `tunables.json`. No proposal pending, no approved challenger.

**Tuesday 2026-11-03, 9:00 research (morning trigger fired 8:41:46 ET on time, v5.2.39).**
- **9:00 value (A1.2 base): $2,571.18** (pre-open, read 8:43 ET), flat, no open orders, same as the 11-02 close. Drawdown stop clear (high $2,596.99, -0.99%). Daily loss limit fires at $2,494.04 (-3%).
- **Controls:** losing streak 0. Tuesday: FADE and PULLBACK both trade. Earnings: MSFT next reports 2027-01-27 pm (tentative, matches `EARNINGS_SKIP` 2027-01-28). NVDA next reports 2026-11-17 pm, verified (NVD/NVDQ skip 11-18, matches). No earnings skip today.
- **Corporate actions:** clean. All 19 funds and proxies active; each premarket move matches its underlying (SOXX +3.8%, SOXL +11.5%, SOXS -11.7%; QQQ +0.8%, TQQQ +2.2%; XLK +0.9%, TECL +3.0%). Wide premarket spreads on TECS, LABU, XBI and TECL: A1.7 applies at order time.
- **RVOL baseline:** 20 sessions 2026-10-06..11-02 -> `archive/paper_rvol_2026-11-03.json`.
- **Context:** large semiconductor gap up premarket (SOXX +3.8%) after a down day, broad proxies up 0.5% to 0.9%, XLF -0.3%. No event calendar checked beyond earnings. Month-end cash interest (+$0.99 on 10-31) is not a deposit (governor, 11-02).
- **Triggers (A2):** the 8:41 and 13:30 standing triggers and the two dated ones are enabled on this session. About 100 disabled, fired one-shot checkpoints from the old session remain (94 deleted 11-02 at the governor's instruction, rest inert). The two `v5 paper` triggers belong to another session.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null. No proposal pending, no approved challenger.

**Wednesday 2026-11-04, 9:00 research (morning trigger fired 8:42:14 ET, v5.2.39).**
- **9:00 value (A1.2 base): $2,571.18** (pre-open, read 8:43 ET), flat, no open orders, same as the 11-03 close. Drawdown stop clear (high $2,596.99, -0.99%). Daily loss limit fires at $2,494.04 (-3%).
- **Controls:** losing streak 0. Wednesday: FADE and PULLBACK both trade. Earnings: MSFT next reports 2027-01-27 pm (tentative, matches `EARNINGS_SKIP` 2027-01-28). NVDA next reports 2026-11-17 pm, verified (NVD/NVDQ skip 11-18, matches). No earnings skip today.
- **Corporate actions:** clean. All 23 funds and proxies active; each premarket move matches its underlying (IWM +1.7%, TNA +5.1%; XLF +1.8%, FAS +5.5%; XBI +2.3%, LABU +7.0%; SOXX -1.1%, SOXL -3.2%, SOXS +3.4%). No fund more than 20% off its close. Wide premarket spreads on SSG, TECL, TECS, NVDQ and LABU: A1.7 applies at order time.
- **RVOL baseline:** 20 sessions 2026-10-07..11-03 -> `archive/paper_rvol_2026-11-04.json`.
- **Context:** day after the US midterm election. Small caps, financials and biotech up premarket, semiconductors down. No event calendar checked beyond earnings.
- **Triggers (A2):** the 8:41 and 13:30 standing triggers and the two dated ones are enabled on this session. One disabled 10-05 checkpoint remains on the old session, inert. The two `v5 paper` triggers belong to another session.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null. No proposal pending, no approved challenger. FADE waiting 0 of 5, PULLBACK waiting 1 of 5.

**Thursday 2026-11-05, 9:00 research (morning trigger fired 8:42:00 ET, v5.2.42).**
- **9:00 value (A1.2 base): $2,503.12** (pre-open, read 8:42 ET), flat, no open orders or advanced orders. It is 2,502 USDG plus $1.12 cash (B4.8, bought 00:55 ET). Equal to the 11-04 close value. Drawdown stop clear (high $2,596.99, -3.61%). Daily loss limit fires at $2,428.03 (-3%).
- **Controls:** losing streak 2 of 5 (11-04 PULLBACK SOXS -1.94%, MSFU -0.72%). Thursday: FADE and PULLBACK both trade. Earnings: MSFT next reports 2027-01-27 pm (tentative). NVDA next reports 2026-11-17 pm, verified (NVD/NVDQ skip 11-18). No earnings skip today.
- **Rules in force:** tunables v4. Runaway skip 0.85% (from 10-29), PULLBACK breakout volume 1.3x and the same-system loss block B4.7 (both from today). v5.2.42 USDG rule ON (governor "Start usdg buy all capital into it now", cap 100%): peg quote bid = ask = $1.00. No interest has been credited yet: the balance is still 2,502 after 7.8 hours, so the crediting schedule is unknown. Check at the close.
- **Corporate actions:** SOXX 3-for-1 split effective today (previous close $450.41 raw = $150.14 split-adjusted; premarket $144.5). Robinhood bars come split-adjusted, history rescaled, so the SOXX box, ranges and the RVOL baseline use one scale. The SOXX RVOL baseline (12.5M shares to 13:30) should be compared with the first slot's SOXX volume: if SOXX RVOL reads near 0.33 or 3, the volume history is not adjusted and it only affects same-bar ties. Other premarket moves match their underlyings: SOXX -3.8%, SOXL -11.7%, SOXS +12.0%; QQQ -0.8%, TQQQ -2.4%; XLK -1.6%, TECL -5.3%; XLF +1.3%, FAS +4.3%; XBI -0.4%, LABU -1.0%; IWM +0.3%, TNA +0.8%. No fund more than 20% off its close except SOXL and SOXS, which follow SOXX by 3x. Wide premarket spreads on SSG, TECL, TECS, FAS and NVDQ: A1.7 applies at order time.
- **RVOL baseline:** 20 sessions 2026-10-08..11-04 -> `archive/paper_rvol_2026-11-05.json`.
- **Context:** second day after the US midterm election. Semiconductors down about 4% premarket, tech down 1.6%, financials up 1.3%. No FOMC (the last was 10-28). Weekly jobless claims 8:30. The October jobs report is due Friday 11-06. No event calendar checked beyond earnings.
- **Triggers (A2):** the 8:41 and 13:30 standing triggers, the 11-06 waiter coverage report and the bimonthly reset reminder are enabled on this session. The two `v5 paper` triggers belong to another session. One disabled 10-05 checkpoint remains on the old session, inert.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null. No proposal pending, no approved challenger. Both cycles restarted at 0 of 5 from 2026-11-05 (v4).

**Friday 2026-11-06, 9:00 research (morning trigger fired 8:42:53 ET, v5.2.43).**
- **9:00 value (A1.2 base): $2,553.16** (pre-open, read 8:43 ET), flat, no open orders. It is 2,552 USDG plus $1.16 cash. Equal to the 11-05 close. Drawdown stop clear (high $2,596.99, -1.69%). Daily loss limit fires at $2,476.56 (-3%).
- **Controls:** losing streak 0 (11-05 LABD was a win). Friday: **FADE does not trade** (A1.10), PULLBACK only. Earnings: MSFT next reports 2027-01-27 pm (tentative). NVDA next reports 2026-11-17 pm, verified (NVD/NVDQ skip 11-18). No earnings skip today.
- **Rules in force:** tunables v4: runaway skip 0.85%, PULLBACK volume 1.3x, same-system loss block (B4.7). USDG rule ON (B4.8, v5.2.42); every-5-minute check (C2, v5.2.43).
- **USDG:** peg bid = ask = $1.00. Balance 2,552.00 exactly. **No interest has been credited in 32 hours** (bought 00:55 on 11-05, 7% APY would be about $0.20 an hour). The governor's 7% rate is unverified: the credit schedule or the rate needs the governor's check in the app.
- **Corporate actions:** clean. Premarket moves match their underlyings: SOXX +4.8%, SOXL +16.8%, SOXS -16.7%; QQQ +1.5%, TQQQ +3.7%; XLK +2.3%, TECL +7.4%; XLF -1.0%, FAS -2.5%; IWM +0.2%, TNA +0.3%. NVD and NVDQ -8% with the inverse Nvidia legs. Wide premarket spreads on SSG, TECS, TECL, LABU, FAS: A1.7 at order time.
- **RVOL baseline:** 20 sessions 2026-10-09..11-05 -> `archive/paper_rvol_2026-11-06.json`.
- **Context:** the October jobs report came out at 8:30. Semiconductors are up about 5% premarket, tech up 2%, financials down 1%. No FOMC. No event calendar checked beyond earnings.
- **Triggers (A2):** the 8:41 and 13:30 standing triggers, the 11-06 waiter coverage report (13:45) and the bimonthly reset reminder are enabled on this session. The two `v5 paper` triggers belong to another session. One disabled 10-05 checkpoint remains, inert.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null. No proposal pending, no approved challenger. FADE 0 of 5, PULLBACK 1 of 5 (model TECS 11-05).

**Monday 2026-11-09, 9:00 research (morning trigger fired 8:41 ET, v5.2.43).**
- **9:00 value (A1.2 base): $2,580.10** (pre-open, read 8:42 ET), flat, no open orders. It is 2,579 USDG plus $1.10 cash. Equal to the 11-06 close. Drawdown stop clear (high $2,596.99, -0.65%). Daily loss limit fires at $2,502.70 (-3%).
- **Controls:** losing streak 0. Monday: FADE and PULLBACK both trade. Earnings: MSFT next reports 2027-01-27 (tentative). NVDA next reports 2026-11-17, verified (NVD/NVDQ skip 11-18). No earnings skip today.
- **Rules in force:** tunables v4: runaway skip 0.85%, PULLBACK volume 1.3x, same-system loss block (B4.7). USDG rule ON (B4.8, v5.2.42). Every-5-minute check (C2, v5.2.43).
- **USDG:** peg bid = ask = $1.00. Balance 2,579.00 exactly, unchanged from Friday. No interest credited over the weekend. The governor must check the posted rate and credit schedule in the Robinhood app. Turn the rule off if it pays nothing.
- **Corporate actions:** clean. Premarket moves match their underlyings: SOXX +1.2%, SOXL +3.8%, SOXS -3.7%; QQQ +0.9%, TQQQ +2.6%; XLK +0.4%, TECL +1.1%; IWM +1.4%, TNA +4.3%; XLF +1.2%, FAS +2.8%; XBI +0.8%. NVD and NVDQ about +11% against NVDA -5.2% (inverse legs, under the 20% threshold). MSFU +4.0% with MSFT +2.0%. Wide premarket spreads on SSG, LABU, TECS, TECL, FAS (A1.7 applies at order time).
- **RVOL baseline:** 20 sessions 2026-10-12..11-06 -> `archive/paper_rvol_2026-11-09.json`.
- **Triggers (A2):** the 8:41, 13:30 and watchdog (9:36 to 12:36) standing triggers and the bimonthly reset reminder are enabled on this session. The two `v5 paper` triggers belong to another session. One disabled 10-05 checkpoint remains, inert.
- **Cycle (D4):** no `archive/improve/pending.json`, `challenger` null. No proposal pending, no approved challenger. FADE 0 of 5, PULLBACK 2 of 5 (NVDQ 11-06).
