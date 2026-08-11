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
    EXCLUDED  if 1.5 x median_mae > 7.0%   (noise wider than the hard cap)
    target    = 2.0 x stop                 (2:1 by construction)
    breakeven = max(median_mfe, 0.5 x stop)
    trail     = 1.0 x median_mae           (below the running high, once past breakeven)

WHY breakeven has a floor of half the stop: moving the stop to breakeven when
the gain is G leaves the stop G below price. If G is smaller than normal
retracement the position scratches on noise. Half the stop distance is the
smallest gain for which a breakeven stop is not itself inside the noise.

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
TARGET_RR = 2.0
BREAKEVEN_FLOOR_FRAC = 0.5
TRAIL_MULT = 1.0


def profile(bars):
    mae = [(b["open"] - b["low"]) / b["open"] * 100 for b in bars]
    mfe = [(b["high"] - b["open"]) / b["open"] * 100 for b in bars]
    med_mae, med_mfe = st.median(mae), st.median(mfe)
    raw = STOP_MULT * med_mae
    excluded = raw > STOP_CAP
    stop = min(max(raw, STOP_FLOOR), STOP_CAP)
    return {
        "sessions": len(bars),
        "median_mae_pct": round(med_mae, 3),
        "median_mfe_pct": round(med_mfe, 3),
        "stop_pct": round(stop, 2),
        "target_pct": round(stop * TARGET_RR, 2),
        "breakeven_trigger_pct": round(max(med_mfe, BREAKEVEN_FLOOR_FRAC * stop), 2),
        "trail_pct": round(TRAIL_MULT * med_mae, 2),
        "excluded": "yes" if excluded else "no",
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
            "target_pct", "breakeven_trigger_pct", "trail_pct", "excluded", "computed"]

    print(f"{'sym':6}{'n':>4}{'medMAE':>8}{'medMFE':>8}{'stop':>7}{'target':>8}"
          f"{'BE trig':>9}{'trail':>7}  status")
    print("-" * 68)
    for d in sorted(out, key=lambda x: x["stop_pct"]):
        status = "EXCLUDED — noise > 7% cap" if d["excluded"] == "yes" else ""
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
