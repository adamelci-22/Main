#!/usr/bin/env python3
"""
Just-in-time risk profile for ONE candidate.

Reads daily OHLC bars on stdin, one per line: open,high,low
Prints every risk number RULEBOOK Part B1 needs.

    printf '33.4,34.1,32.9\n33.0,33.8,32.7\n' | python3 tools/profile.py SOXL

Exists to make the arithmetic deterministic. Doing it by hand at 9:40 is
where a transposed digit becomes a mispriced stop.
"""
import sys


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "?"
    mae, mfe = [], []
    for line in sys.stdin:
        line = line.strip()
        if not line or line[0].isalpha():        # skip blanks and a header row
            continue
        o, h, l = (float(v) for v in line.split(",")[:3])
        if o <= 0:
            continue
        mae.append((o - l) / o * 100)            # adverse: how far below the open
        mfe.append((h - o) / o * 100)            # favourable: how far above it

    n = len(mae)
    if n == 0:
        sys.exit("no usable bars on stdin (expected: open,high,low per line)")

    med_mae, med_mfe = median(mae), median(mfe)

    stop      = clamp(1.5 * med_mae, 2.5, 7.0)
    target    = clamp(1.25 * med_mfe, 1.5 * stop, 12.0)
    stall     = clamp(0.15 * med_mfe, 0.10, 1.00)
    min_move  = clamp(0.25 * med_mae, 0.20, 1.00)
    at_cap    = 1.5 * med_mae > 7.0

    print(f"{symbol}  ({n} sessions)")
    if n < 15:
        print(f"  !! ONLY {n} SESSIONS — thin sample, treat the numbers as provisional")
    print(f"  median adverse   {med_mae:6.2f}%")
    print(f"  median favourable{med_mfe:6.2f}%")
    print(f"  ---")
    print(f"  stop             {stop:6.2f}%   " + ("<-- AT THE 7% CAP, noise is wider than the stop" if at_cap else ""))
    print(f"  target           {target:6.2f}%")
    print(f"  stall threshold  {stall:6.2f}%")
    print(f"  min stop move    {min_move:6.2f}%")
    print(f"  ---")
    print(f"  mfe_per_stop     {med_mfe/stop:6.3f}   (ranking metric — higher is better)")
    print(f"  mfe_to_target    {target/med_mfe:6.2f}   " + ("<-- ABOVE 2.5, target effectively unreachable" if target/med_mfe > 2.5 else ""))


if __name__ == "__main__":
    main()
