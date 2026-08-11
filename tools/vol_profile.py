#!/usr/bin/env python3
"""
Volatility profile — derives the per-instrument stop, target and breakeven
trigger from recent daily bars.

WHY THIS EXISTS. A fixed 5% stop and 8% target are mismatched on essentially
every instrument we trade (EXP-007, EXP-008): median adverse excursion spans
0.9% to 6.6% across the leveraged universe, and the instruments where +8% is
reachable are exactly the ones where a 5% stop is hit by noise. Both ends must
scale to the same volatility measure.

FORMULAS
    median_mae   median of (open - low)  / open over the window
    median_mfe   median of (high - open) / open over the window

    stop      = clamp(1.5 x median_mae, 2.5%, 7.0%)
    target    = clamp(2.0 x median_mfe, 1.5 x stop, 12.0%)   governor 2026-08-11
    breakeven = max(median_mfe, 0.5 x stop)  (where the stop first goes to breakeven)
    trail     = 1.0 x median_mae           (below the running high, once past breakeven)

WHY the breakeven trigger floors at half the stop: moving the stop to breakeven
when the gain is G leaves the stop G below price. If G is smaller than normal
retracement the position just scratches on noise. Half the stop distance is the
smallest gain at which a breakeven stop is not itself inside the noise.

    NOTHING IS EXCLUDED on volatility. Where 1.5 x median_mae exceeds the cap the
    stop is simply capped at 7% and stop_at_cap is flagged, so the tightness
    relative to that instrument's noise is visible rather than disqualifying.

THIS MUST BE RECOMPUTED, NOT FROZEN. Volatility moves -- SOXL ranged from $196
to $91 inside the sample window that produced the first profile. The 9:00am
checkpoint refreshes it (RULEBOOK section 2e). A hardcoded table is just a
different fixed guess wearing a formula.

Usage:
    python3 tools/vol_profile.py                     # from data/calibration_daily.csv
    python3 tools/vol_profile.py --write             # also write data/vol_profile.csv
"""
import argparse
import csv
import datetime as dt
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STOP_MULT = 1.5
STOP_FLOOR = 2.5
STOP_CAP = 7.0
TARGET_MULT_MFE = 2.0     # an exceptional day, not a median one
TARGET_FLOOR_R = 1.5      # a target hit must pay at least this many R
TARGET_CAP = 12.0         # above this it stops being a "bank it" level
STALL_THR_FRAC = 0.15     # stall new-high threshold, as a fraction of median_mfe
STALL_THR_MIN, STALL_THR_MAX = 0.10, 1.00
MIN_MOVE_FRAC = 0.25      # minimum stop move, as a fraction of median_mae
MIN_MOVE_MIN, MIN_MOVE_MAX = 0.20, 1.00
BREAKEVEN_FLOOR_FRAC = 0.5    # trigger floors at half the stop
TRAIL_MULT = 1.0


def profile(bars):
    mae = [(b["open"] - b["low"]) / b["open"] * 100 for b in bars]
    mfe = [(b["high"] - b["open"]) / b["open"] * 100 for b in bars]
    med_mae, med_mfe = st.median(mae), st.median(mfe)
    raw = STOP_MULT * med_mae
    capped = raw > STOP_CAP          # informational only -- nothing is excluded
    stop = min(max(raw, STOP_FLOOR), STOP_CAP)
    target = min(max(TARGET_MULT_MFE * med_mfe, TARGET_FLOOR_R * stop), TARGET_CAP)
    return {
        "sessions": len(bars),
        "median_mae_pct": round(med_mae, 3),
        "median_mfe_pct": round(med_mfe, 3),
        "stop_pct": round(stop, 2),
        "target_pct": round(target, 2),
        "breakeven_trigger_pct": round(max(med_mfe, BREAKEVEN_FLOOR_FRAC * stop), 2),
        "trail_pct": round(TRAIL_MULT * med_mae, 2),
        # Favourable excursion per unit of risk — the RANKING metric for a small
        # affordable set (RULEBOOK section 4). Comparing raw stop widths across
        # instruments compares nothing; a stop is a risk normaliser, not a signal.
        "mfe_per_stop": round(med_mfe / stop, 3),
        # How far +8% is in units of this instrument's normal day. Above ~2.5 the
        # target is effectively unreachable and the trade is a trail-or-stall exit.
        "mfe_to_target": round(target / med_mfe, 2) if med_mfe > 0 else None,
        # Scaled 2026-08-11: a flat 0.3% threshold was 33% of a calm instrument's daily
        # range and 5% of a volatile one's — the one parameter that was never scaled.
        "stall_threshold_pct": round(min(max(STALL_THR_FRAC * med_mfe, STALL_THR_MIN), STALL_THR_MAX), 2),
        "min_stop_move_pct": round(min(max(MIN_MOVE_FRAC * med_mae, MIN_MOVE_MIN), MIN_MOVE_MAX), 2),
        "stop_at_cap": "yes" if capped else "no",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bars", default="data/calibration_daily.csv")
    p.add_argument("--write", action="store_true")
    a = p.parse_args()

    rows = list(csv.DictReader(open(os.path.join(ROOT, a.bars))))
    by = {}
    for r in rows:
        by.setdefault(r["symbol"], []).append(
            {k: float(r[k]) for k in ("open", "high", "low", "close")})

    out = []
    for sym in sorted(by):
        d = profile(by[sym])
        d["symbol"] = sym
        d["computed"] = dt.date.today().isoformat()
        out.append(d)

    cols = ["symbol", "sessions", "median_mae_pct", "median_mfe_pct", "stop_pct",
            "target_pct", "breakeven_trigger_pct", "trail_pct", "mfe_per_stop",
            "mfe_to_target", "stall_threshold_pct", "min_stop_move_pct", "stop_at_cap", "computed"]

    print(f"{'sym':6}{'n':>4}{'medMAE':>8}{'medMFE':>8}{'stop':>7}{'target':>8}"
          f"{'BE trig':>9}{'trail':>7}  status")
    print("-" * 68)
    for d in sorted(out, key=lambda x: x["stop_pct"]):
        status = "stop AT THE 7% CAP — noise is wider than the stop" if d["stop_at_cap"] == "yes" else ""
        print(f"{d['symbol']:6}{d['sessions']:>4}{d['median_mae_pct']:>7.1f}%"
              f"{d['median_mfe_pct']:>7.1f}%{d['stop_pct']:>6.1f}%{d['target_pct']:>7.1f}%"
              f"{d['breakeven_trigger_pct']:>8.1f}%{d['trail_pct']:>6.1f}%  {status}")

    if a.write:
        path = os.path.join(ROOT, "data", "vol_profile.csv")
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for d in out:
                w.writerow({k: d[k] for k in cols})
        print(f"\nwrote data/vol_profile.csv ({len(out)} instruments)")

    print("\nCAVEAT: derived from an entry-at-the-open proxy on DAILY bars, which is")
    print("hindsight-free but is not our entry rule. Treat the numbers as volatility")
    print("scaling, not as a forecast. Refresh at the 9:00am checkpoint.")


if __name__ == "__main__":
    main()
