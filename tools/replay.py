#!/usr/bin/env python3
"""
Replay the ACTUAL exit rules on 5-minute bars, honouring the checkpoint structure.

Why this exists: the earlier daily-bar study implicitly assumed the profit
target was hit continuously. It is not. Only the STOP rests at the broker. The
target, the stall ladder and the stop ratchet are all evaluated by the agent,
which exists only at discrete checkpoints. Modelling those as continuous
invents exits that cannot happen and omits the exit that fires most often.

What is modelled, per RULEBOOK section 6 / section 8 and OPERATIONS.md:

  CONTINUOUS   the resting stop — a real order at the broker, so any bar whose
               low pierces it fills. Checked on every 5-minute bar.
  CHECKPOINTS  everything else. Target, stall count, ratchet, exit decisions
               happen only at cadence boundaries, at the price then showing.
  STALL CLOCK  30-minute windows of MARKET time, clock-anchored at :00/:30,
               independent of the checkpoint cadence. A window is stalled when
               its high fails to beat the running high by >0.3% AND its volume
               is below the prior window's. NO midday exclusion -- every window
               counts normally.
  LADDER       2 stalled windows -> stop to max(current, breakeven), never
               lowered. 3 -> sell at the next checkpoint, any gain.
  RATCHET      gain >= breakeven_trigger -> breakeven. Past that -> trail
               `--trail-pct` below the running high. Up only, min move 0.5%.
  TARGET       any checkpoint showing gain AT OR ABOVE +8% -> sell.

Usage:
    python3 tools/replay.py data/bars_5min_GUSH_2026-08-05.csv \\
        --entry 13:45 --cadence 15 --stop-pct 5 --target-pct 8 [--verbose]
"""
import argparse
import csv
import os
import sys

ET_OFFSET = -4  # EDT


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def et(hhmm):
    """UTC HH:MM -> ET minutes since midnight."""
    return to_min(hhmm) + ET_OFFSET * 60


def load(path):
    out = []
    for r in csv.DictReader(open(path)):
        out.append({
            "ts": r["ts_utc"],
            "m": to_min(r["ts_utc"]),
            "et": et(r["ts_utc"]),
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "vol": float(r["volume"]), "interp": r["interpolated"] == "1",
        })
    return out


def stall_windows(bars, entry_m):
    """Aggregate post-entry bars into clock-anchored 30-minute windows."""
    wins = {}
    for b in bars:
        if b["m"] < entry_m or b["interp"]:
            continue
        key = (b["m"] // 30) * 30
        w = wins.setdefault(key, {"high": -1e9, "vol": 0.0, "end": key + 30})
        w["high"] = max(w["high"], b["high"])
        w["vol"] += b["vol"]
    return [dict(start=k, **v) for k, v in sorted(wins.items())]


def ratchet(gain_pct, run_high_pct, trail_pct, stalls, be_trigger):
    """Target stop as a percent offset from entry. None = leave as is.

    gain >= be_trigger -> breakeven
    past breakeven     -> trail `trail_pct` below the running high
    2 stalled windows  -> max(current, breakeven); the up-only rule does the rest
    """
    levels = []
    if gain_pct >= be_trigger:
        levels.append(0.0)
    if run_high_pct is not None and run_high_pct >= be_trigger:
        levels.append(run_high_pct - trail_pct)
    if stalls >= 2:
        levels.append(0.0)
    return max(levels) if levels else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("bars")
    p.add_argument("--entry", default="13:45", help="UTC HH:MM of the entry checkpoint")
    p.add_argument("--cadence", type=int, default=15, help="checkpoint spacing, minutes")
    p.add_argument("--stop-pct", type=float, default=5.0)
    p.add_argument("--target-pct", type=float, default=8.0)
    p.add_argument("--breakeven-pct", type=float, default=2.1,
                   help="gain at which the stop first goes to breakeven")
    p.add_argument("--trail-pct", type=float, default=2.0,
                   help="trail distance below the running high, = 1 x median MAE")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    bars = load(a.bars)
    entry_m = to_min(a.entry)
    ebars = [b for b in bars if b["m"] >= entry_m]
    if not ebars:
        print("no bars at or after entry"); return 2

    entry = ebars[0]["open"]
    stop = entry * (1 - a.stop_pct / 100)
    stop_label = f"-{a.stop_pct:.2f}%"
    wins = stall_windows(bars, entry_m)

    exit_price = exit_ts = reason = None
    log = []

    for b in ebars:
        # --- CONTINUOUS: the resting stop is a real order
        if b["low"] <= stop:
            exit_price, exit_ts, reason = stop, b["ts"], f"STOP hit ({stop_label})"
            log.append(f"  {b['ts']}  STOP FILLED at {stop:.4f}")
            break

        # --- CHECKPOINT boundary?
        if (b["m"] - entry_m) % a.cadence != 0 or b["m"] == entry_m:
            continue

        px = b["close"]
        gain = (px - entry) / entry * 100

        # Stall count over completed windows. NO midday exclusion -- every
        # window counts normally (governor decision 2026-08-11).
        run_high, stalls, prev_vol = entry, 0, None
        for w in wins:
            if w["end"] > b["m"]:
                break
            progressed = w["high"] > run_high * 1.003
            if progressed:
                stalls = 0
                run_high = max(run_high, w["high"])
            else:
                vol_dry = prev_vol is not None and w["vol"] < prev_vol
                if vol_dry:
                    stalls += 1
            prev_vol = w["vol"]

        # ratchet, up only. min move 0.5% of entry to bound cancel/replace churn.
        run_high_pct = (run_high - entry) / entry * 100
        sched = ratchet(gain, run_high_pct, a.trail_pct, stalls, a.breakeven_pct)
        if sched is not None:
            new = entry * (1 + sched / 100)
            if new > stop and (new - stop) / entry * 100 >= 0.5:
                stop, stop_label = new, f"{sched:+.2f}%"
                log.append(f"  {b['ts']}  ratchet -> stop {stop:.4f} ({stop_label}) "
                           f"at {gain:+.2f}%, high {run_high_pct:+.2f}%, stalls {stalls}")

        if a.verbose:
            log.append(f"  {b['ts']}  px {px:.4f} {gain:+6.2f}%  stalls {stalls}  stop {stop:.4f}")

        # exits, in precedence order
        if gain >= a.target_pct:
            exit_price, exit_ts, reason = px, b["ts"], f"TARGET (+{a.target_pct:.0f}%)"
            break
        if stalls >= 3:
            exit_price, exit_ts, reason = px, b["ts"], f"STALL x3 at {gain:+.2f}%"
            break

    if exit_price is None:
        last = ebars[-1]
        exit_price, exit_ts, reason = last["close"], last["ts"], "session close (4:00pm)"

    ret = (exit_price - entry) / entry * 100
    r_mult = ret / a.stop_pct

    print(f"{os.path.basename(a.bars)}  cadence {a.cadence}min  stop {a.stop_pct}%  target {a.target_pct}%")
    print(f"  entry  {a.entry} UTC at {entry:.4f}")
    print(f"  exit   {exit_ts} UTC at {exit_price:.4f}  —  {reason}")
    print(f"  result {ret:+.2f}%   {r_mult:+.2f}R")
    if log:
        print("  events:")
        for l in log:
            print(l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
