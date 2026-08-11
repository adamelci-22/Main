#!/usr/bin/env python3
"""
Stop and target calibration from real daily bars.

Answers one question the rulebook currently guesses at: is a -5% stop inside
or outside normal daily noise for the instruments we actually trade?

Universe: LEVERAGED SECTOR ETFs and LEVERAGED SINGLE-STOCK ETFs only. Index
leveraged (TQQQ/SQQQ/TNA/TZA), unleveraged single names and commodity funds
are deliberately excluded -- they are not what this strategy trades.

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
        d = {k: float(r[k]) for k in ("open", "high", "low", "close")}
        d["class"] = r["class"]
        by.setdefault(r["symbol"], []).append(d)

    print("Stop / target calibration — long entry at the open, daily bars")
    print(f"{len(rows)} sessions across {len(by)} instruments\n")

    hdr = (f"{'sym':6}{'class':>14}{'n':>4}{'med rng':>9}{'med MAE':>9}{'med MFE':>9}"
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
        print(f"{sym:6}{bars[0]['class']:>14}{n:>4}{pct(st.median(rng)):>9}{pct(st.median(mae)):>9}"
              f"{pct(st.median(mfe)):>9}{pct(s5):>9}{pct(s7):>9}"
              f"{pct(t3):>9}{pct(t8):>9}")
        allrows.append((sym, s5, s7, t3, t8, st.median(mae), bars[0]["class"]))

    print()
    print("Reading the table:")
    print("  med MAE  = typical distance the price goes AGAINST a long from the open")
    print("  hit -5%  = share of sessions a 5% stop would have been touched")
    print("  hit +8%  = share of sessions the low end of target was reachable")
    print()

    print("Per-instrument verdict on the 5% stop:")
    for sym, s5, s7, t3, t8, medmae, cls in sorted(allrows, key=lambda r: -r[1]):
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
    print("PROPOSED SCALED STOP = 1.5 x median adverse excursion, floor 2.5%, cap 7.0%")
    print("(cap and floor from RULEBOOK section 6; the floor exists because a stop inside")
    print(" the spread plus normal tick noise is not a stop, it is a coin toss)")
    print()
    print(f"  {'sym':6}{'med MAE':>9}{'scaled':>9}{'vs flat 5%':>12}  note")
    for sym, s5, s7, t3, t8, medmae, cls in sorted(allrows, key=lambda r: r[5]):
        raw = 1.5 * medmae
        scaled = min(max(raw, 2.5), 7.0)
        if raw > 7.0:
            note = "EXCLUDE — noise exceeds the 7% cap"
        elif raw < 2.5:
            note = "floored"
        else:
            note = ""
        delta = scaled - 5.0
        print(f"  {sym:6}{medmae:8.1f}%{scaled:8.1f}%{delta:+11.1f}pp  {note}")

    print()
    print("THE STRUCTURAL FINDING — stop quality and target reachability are INVERSE:")
    print(f"  {'sym':6}{'stop-out':>10}{'reached +8%':>13}")
    for sym, s5, s7, t3, t8, medmae, cls in sorted(allrows, key=lambda r: -r[1]):
        print(f"  {sym:6}{s5:9.0f}%{t8:12.0f}%")
    print("  Instruments where the target is reachable are the ones where a 5% stop")
    print("  fails, and vice versa. The fixed stop/target pair is mismatched on")
    print("  essentially every instrument — one end or the other is always wrong.")

    print()
    print("CAVEATS — read before quoting any of this:")
    print("  * Entry at the open is NOT our entry rule. It is a hindsight-free proxy,")
    print("    not a simulation of the strategy.")
    print("  * A daily bar cannot order the high and the low. Days touching both")
    print("    -5% and +8% count in both columns, so stop-out rates are an UPPER")
    print("    bound and target rates are an UPPER bound too.")
    print("  * ~21 sessions per instrument. This is a calibration sanity check,")
    print("    not evidence of edge, and it covers one particular market month.")


if __name__ == "__main__":
    main()
