#!/usr/bin/env python3
"""
Pre-order checker. Run BEFORE placing any entry.

    python3 tools/preflight.py --symbol SOXL --qty 1 --limit 24.50 --stop 23.28 \
        --balance 42.07 --deposits 40.84 --open-positions 0 --resting-orders 0

Exit code 0 = ALLOW, 1 = DENY, 2 = bad invocation.

WHAT THIS IS
------------
A deterministic check of the arithmetic that must hold before an order.
Limits come from limits.json; the consecutive-loss streak is COMPUTED from
data/trades.csv rather than remembered, which removes a whole class of
counting error from the circuit breaker.

WHAT THIS IS NOT
----------------
It is not a gate. The agent calls the broker directly through tools this
script cannot intercept, so nothing forces the script to be run and nothing
prevents a DENY from being ignored. It is a TRIPWIRE: it makes the check
deterministic, and it makes skipping the check or overriding a refusal
visible in the transcript instead of a judgement call nobody can audit.
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_limits():
    with open(os.path.join(ROOT, "limits.json")) as fh:
        return json.load(fh)


def vol_profile(symbol):
    """Per-instrument stop/target/breakeven from data/vol_profile.csv, or None."""
    path = os.path.join(ROOT, "data", "vol_profile.csv")
    if not os.path.exists(path):
        return None
    for r in csv.DictReader(open(path)):
        if r["symbol"].upper() == symbol.upper():
            return r
    return None


def loss_streak():
    """Consecutive losing closed trades ending at the most recent one.

    A loss is any negative realised P&L, however small (RULEBOOK section 4).
    Returns (streak, n_trades).
    """
    path = os.path.join(ROOT, "data", "trades.csv")
    if not os.path.exists(path):
        return 0, 0
    with open(path) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("pnl_usd", "").strip()]
    streak = 0
    for row in reversed(rows):
        try:
            pnl = float(row["pnl_usd"])
        except ValueError:
            break
        if pnl < 0:
            streak += 1
        else:
            break
    return streak, len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--qty", type=float, required=True)
    p.add_argument("--limit", type=float, required=True, help="entry limit price")
    p.add_argument("--stop", type=float, required=True, help="protective stop price; 0 = none")
    p.add_argument("--balance", type=float, required=True,
                   help="TOTAL ACCOUNT VALUE (get_portfolio total_value). The floor is measured "
                        "against this, never against buying power — unsettled proceeds are still "
                        "the account's money.")
    p.add_argument("--buying-power", type=float, default=None,
                   help="SETTLED, SPENDABLE cash (get_portfolio buying_power.buying_power). "
                        "Affordability is measured against this. Defaults to --balance, which is "
                        "correct only when nothing is unsettled.")
    p.add_argument("--deposits", type=float, required=True, help="deposited capital")
    p.add_argument("--open-positions", type=int, default=0)
    p.add_argument("--resting-orders", type=int, default=0)
    p.add_argument("--order-type", default="limit")
    p.add_argument("--underlying-pct", type=float, default=None,
                   help="Day change of the UNDERLYING for a single-stock leveraged ETF "
                        "(e.g. NVDA for NVDX). Required for those; ignored otherwise.")
    p.add_argument("--sector-pct", type=float, default=None,
                   help="Day change of the SECTOR PROXY (e.g. SMH for NVDX). Paired with "
                        "--underlying-pct to enforce the single-stock gate.")
    a = p.parse_args()

    lim = load_limits()
    fails, warns = [], []

    # --- circuit breaker, computed not remembered
    streak, n = loss_streak()
    cap = lim["circuit_breaker"]["consecutive_losses"]
    if streak >= cap:
        fails.append(f"CIRCUIT BREAKER: {streak} consecutive losses (limit {cap}). "
                     "Only the governor clears it.")

    # Buying power defaults to the account value; they differ whenever proceeds are
    # unsettled. The floor is an ACCOUNT VALUE test (section 10) — measuring it against
    # buying power would falsely halt trading every time a sale had not yet settled.
    bp = a.buying_power if a.buying_power is not None else a.balance

    # --- floor
    floor = lim["floor"]["pct_of_deposits"] / 100.0 * a.deposits
    if a.balance < floor:
        fails.append(f"FLOOR: balance {a.balance:.2f} below {floor:.2f} "
                     f"({lim['floor']['pct_of_deposits']:.0f}% of {a.deposits:.2f} deposited).")

    # --- concentration
    if a.open_positions >= lim["position"]["max_open"]:
        fails.append(f"POSITION: {a.open_positions} already open (max {lim['position']['max_open']}).")
    if a.resting_orders >= lim["position"]["max_resting_orders"]:
        fails.append(f"RESTING ORDERS: {a.resting_orders} already resting "
                     f"(max {lim['position']['max_resting_orders']}). A pending sell locks the shares.")

    # --- stop present and sized against THIS instrument's profile
    s = lim["stop"]
    prof = vol_profile(a.symbol)
    if prof is None:
        fails.append(f"NO VOLATILITY PROFILE for {a.symbol.upper()}. The stop, target and "
                     "breakeven trigger all derive from data/vol_profile.csv. Compute it "
                     "(tools/vol_profile.py) or pick another instrument — there is no "
                     "fallback default.")
    elif prof.get("stop_at_cap") == "yes":
        warns.append(f"{a.symbol.upper()} median adverse excursion "
                     f"{float(prof['median_mae_pct']):.1f}% is WIDER than its capped "
                     f"{float(prof['stop_pct']):.1f}% stop — expect frequent noise stop-outs.")

    if s["required"] and a.stop <= 0:
        fails.append("STOP: none supplied. A stop is placed immediately after the entry fills.")
    else:
        dist = (a.limit - a.stop) / a.limit * 100.0
        if dist <= 0:
            fails.append(f"STOP: {a.stop:.4f} is not below the entry {a.limit:.4f}.")
        elif dist > s["max_pct"]:
            fails.append(f"STOP TOO WIDE: {dist:.2f}% exceeds the {s['max_pct']:.1f}% hard cap. "
                         "A setup needing more room is declined, not entered wider.")
        elif dist < s["floor_pct"]:
            fails.append(f"STOP TOO TIGHT: {dist:.2f}% is inside the {s['floor_pct']:.1f}% floor. "
                         "A stop inside the spread plus tick noise is a coin toss.")
        elif prof is not None:
            want = float(prof["stop_pct"])
            if abs(dist - want) > 0.75:
                fails.append(f"STOP MISMATCH: {dist:.2f}% but the profile for "
                             f"{a.symbol.upper()} says {want:.2f}% "
                             f"(1.5 x median adverse {float(prof['median_mae_pct']):.2f}%). "
                             "Use the scaled stop or state explicitly why not.")
            else:
                warns.append(f"stop {dist:.2f}% matches profile {want:.2f}% · "
                             f"target {float(prof['target_pct']):.2f}% · "
                             f"breakeven trigger +{float(prof['breakeven_trigger_pct']):.2f}% · "
                             f"trail {float(prof['trail_pct']):.2f}%")

    # --- affordability
    notional = a.qty * a.limit
    if notional > bp:
        fails.append(f"NOTIONAL: {notional:.2f} exceeds settled buying power {bp:.2f}"
                     + (f" (account value is {a.balance:.2f}, but {a.balance - bp:.2f} is "
                        "unsettled and cannot be spent)." if bp < a.balance else "."))

    # --- fractional: PROHIBITED 2026-08-11
    # The broker refuses a resting stop on a fractional quantity ("Invalid trigger
    # for fractional order"), and every exit rule is calibrated against a stop that
    # rests continuously at the broker. Whole shares only.
    if a.qty != int(a.qty) and not lim.get("fractional", {}).get("permitted", False):
        fails.append(f"FRACTIONAL: qty {a.qty:g} is not a whole share. A fractional position "
                     "cannot carry a resting stop, so it cannot be protected between "
                     "checkpoints. If the setup is unaffordable whole, it is unavailable.")

    # --- order type
    if a.order_type not in lim["order"]["allowed_types"]:
        if a.order_type == "market" and a.qty != int(a.qty) and \
                lim["order"].get("market_allowed_only_for_fractional", False):
            warns.append("market order permitted only because the quantity is fractional.")
        else:
            fails.append(f"ORDER TYPE: '{a.order_type}' not allowed "
                         f"(allowed: {lim['order']['allowed_types']}).")

    # --- single-stock leveraged: the underlying must not lag its sector (RULEBOOK section 4)
    ss = lim.get("single_stock_leveraged", {})
    pair = ss.get("map", {}).get(a.symbol.upper())
    if pair:
        und, sec = pair
        if a.underlying_pct is None or a.sector_pct is None:
            fails.append(f"UNDERLYING GATE UNCHECKED: {a.symbol.upper()} is a single-stock "
                         f"leveraged ETF, so --underlying-pct ({und}) and --sector-pct ({sec}) "
                         "are required. The gate cannot be waived by omitting its inputs.")
        elif a.underlying_pct < a.sector_pct:
            fails.append(f"UNDERLYING LAGS SECTOR: {und} {a.underlying_pct:+.2f}% is behind "
                         f"{sec} {a.sector_pct:+.2f}%. Buying the laggard with leverage turns a "
                         "correct sector call into a losing trade (NVDX 2026-08-11).")
        else:
            warns.append(f"underlying gate OK: {und} {a.underlying_pct:+.2f}% "
                         f"vs {sec} {a.sector_pct:+.2f}%")

    # --- universe
    if a.symbol.upper() not in lim["universe"]:
        warns.append(f"{a.symbol.upper()} is not on the listed universe — permitted only as a "
                     "liquid high-beta name with a catalyst. Say why in the entry note.")

    # --- risk context, always printed
    risk_pct = (a.limit - a.stop) * a.qty / a.balance * 100.0 if a.stop > 0 else float("nan")

    print(f"preflight · policy v{lim['policy_version']}")
    if prof is not None:
        print(f"  profile: {prof['sessions']} sessions, computed {prof['computed']}")
    print(f"  {a.symbol.upper()} qty {a.qty:g} @ {a.limit:.4f} = {notional:.2f} "
          f"of {bp:.2f} ({notional / bp * 100:.1f}% of buying power)")
    print(f"  stop {a.stop:.4f} · risk {risk_pct:.2f}% of account "
          f"(SANDBOX sizing — see RULEBOOK section 0)")
    print(f"  loss streak {streak}/{cap} over {n} closed trade(s) · floor {floor:.2f}"
          f" vs account value {a.balance:.2f}"
          + (f" · {a.balance - bp:.2f} unsettled" if bp < a.balance else ""))
    for w in warns:
        print(f"  note: {w}")

    if fails:
        print("\nDENY")
        for f in fails:
            print(f"  - {f}")
        print("\nOverriding a DENY is a policy violation. If you proceed anyway, say so explicitly.")
        return 1

    print("\nALLOW")
    return 0


if __name__ == "__main__":
    sys.exit(main())
