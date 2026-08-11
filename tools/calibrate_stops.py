#!/usr/bin/env python3
"""
Stop and target calibration from real daily bars.

Answers one question the rulebook currently guesses at: is a -5% stop inside
or outside normal daily noise for the instruments we actually trade?

Method. For each session, assume a long entry at the open — a crude but
UNBIASED proxy, since it makes no use of hindsight about which entries were
good. Then measure:

  adverse excursion   (open - low)  / open   how far it went against you
  favourable excursion (high - open) / open   how far it went your way
  range               (high - low)  / open

and count how often a stop at 5% / 7% would have been touched, and how often
+3% (the breakeven-ratchet trigger) and +8% (the low end of target) were reached.

CAVEAT, stated in the output: entering at the open is not our entry rule, and
the daily bar cannot tell us whether the low came before or after the high.
A day that touched both -5% and +8% is counted in both columns. So the
stop-out figures are an UPPER bound on being stopped and the target figures
are an UPPER bound on reaching target. Directionally this is still decisive.
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pct(x):
    return f"{x:5.1f}%"


def main():
    path = os.path.join(ROOT, "data", "calibration_daily.csv")
    rows = list(csv.DictReader(open(path)))
    by = {}
    for r in rows:
        by.setdefault(r["symbol"], []).append(
            {k: float(r[k]) for k in ("open", "high", "low", "close")}
        )

    print("Stop / target calibration — long entry at the open, daily bars")
    print(f"{len(rows)} sessions across {len(by)} instruments\n")

    hdr = (f"{'sym':6}{'n':>4}{'med rng':>9}{'med MAE':>9}{'med MFE':>9}"
           f"{'hit -5%':>9}{'hit -7%':>9}{'hit +3%':>9}{'hit +8%':>9}")
    print(hdr)
    print("-" * len(hdr))

    allrows = []
    for sym, bars in by.items():
        rng = [(b["high"] - b["low"]) / b["open"] * 100 for b in bars]
        mae = [(b["open"] - b["low"]) / b["open"] * 100 for b in bars]
        mfe = [(b["high"] - b["open"]) / b["open"] * 100 for b in bars]
        n = len(bars)
        s5 = sum(1 for x in mae if x >= 5.0) / n * 100
        s7 = sum(1 for x in mae if x >= 7.0) / n * 100
        t3 = sum(1 for x in mfe if x >= 3.0) / n * 100
        t8 = sum(1 for x in mfe if x >= 8.0) / n * 100
        print(f"{sym:6}{n:>4}{pct(st.median(rng)):>9}{pct(st.median(mae)):>9}"
              f"{pct(st.median(mfe)):>9}{pct(s5):>9}{pct(s7):>9}"
              f"{pct(t3):>9}{pct(t8):>9}")
        allrows.append((sym, s5, s7, t3, t8, st.median(mae)))

    print()
    print("Reading the table:")
    print("  med MAE  = typical distance the price goes AGAINST a long from the open")
    print("  hit -5%  = share of sessions a 5% stop would have been touched")
    print("  hit +8%  = share of sessions the low end of target was reachable")
    print()

    print("Per-instrument verdict on the 5% stop:")
    for sym, s5, s7, t3, t8, medmae in sorted(allrows, key=lambda r: -r[1]):
        if s5 >= 50:
            v = "UNUSABLE — stopped on a coin flip or worse"
        elif s5 >= 30:
            v = "MARGINAL — stopped on roughly a third of days"
        elif s5 >= 15:
            v = "workable"
        else:
            v = "comfortable"
        print(f"  {sym:6} stop-out {s5:4.0f}% of sessions · median adverse {medmae:4.1f}%  → {v}")

    print()
    print("CAVEATS — read before quoting any of this:")
    print("  * Entry at the open is NOT our entry rule. It is a hindsight-free proxy,")
    print("    not a simulation of the strategy.")
    print("  * A daily bar cannot order the high and the low. Days touching both")
    print("    -5% and +8% count in both columns, so stop-out rates are an UPPER")
    print("    bound and target rates are an UPPER bound too.")
    print("  * 21 sessions per instrument. This is a calibration sanity check,")
    print("    not evidence of edge, and it covers one particular market month.")


if __name__ == "__main__":
    main()
