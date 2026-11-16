#!/usr/bin/env python3
"""Hougaard TFM direct directional re-check (governor 2026-11-16: "Are you sure"). Research only. No legs, no stops, no book: just direction.
Pattern: Thursday, Friday (Friday's high did not exceed Thursday's), then Monday trades below Friday's low. Claim: Monday falls.
For each proxy (QQQ SOXX IWM XLK XBI XLF) and each qualifying Monday we measure the proxy return from three points to the Monday close:
  open (9:30), first break of Friday's low (price = Friday's low), and 9:35 open.
Controls: (1) all other Mondays, (2) the same test for every other weekday pair (Tue after Mon etc.: pattern = prior day high below the day before's high, then break of prior low),
(3) 5,000 random draws of the same number of Mondays. Two-sided p = share of random draws with an average as low as the pattern's.
    python3 -I tools/backtest/hougaard6.py > tools/backtest/results/hougaard6_2026-11-16.txt"""
import datetime as dt, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hougaard as H
ds, days, ix, dly, wd, prev, cons = H.ds, H.days, H.ix, H.dly, H.wd, H.prev, H.cons; PX = H.PX
rng = np.random.default_rng(7)


def events(dow):
    """Per weekday `dow` (0 Mon..4 Fri): list of dicts for every proxy-day with the TFM-like structure and the outcomes."""
    out = []
    for p in PX:
        for d in days:
            if wd(d) != dow or d not in ds.bars[p]: continue
            f = prev(d); th = prev(d, 2) if f else None
            if not th or not (cons(th, f) and cons(f, d)) or f not in ds.bars[p] or th not in ds.bars[p]: continue
            fh, fl, _, _ = dly(p, f); thh = dly(p, th)[0]; b = ds.bars[p][d]
            o = b[0][0]; c = b[-1][3]; ex = next((j for j in range(0, 77) if b[j][2] < fl), None)
            out.append(dict(p=p, d=d, pat=fh <= thh, brk=ex is not None, r_open=(c / o - 1) * 100, r_b935=(c / b[1][0] - 1) * 100,
                            r_break=((c / min(fl, b[ex][0]) - 1) * 100) if ex is not None else None, gap=(o / fl - 1) * 100))
    return out


def summarize(tag, x, key):
    v = np.array([e[key] for e in x if e[key] is not None])
    if len(v) < 5: print(f"      {tag:<46} n {len(v)}"); return
    print(f"      {tag:<46} n {len(v):4d} mean {v.mean():+.3f}% median {np.median(v):+.3f}% up {100 * (v > 0).mean():3.0f}% t {v.mean() / (v.std(ddof=1) / np.sqrt(len(v))):+5.2f}")


def main():
    print(__doc__.split('\n')[0]); print("   returns in % on the PROXY to the 15:55 bar close. Negative = the Monday fall the claim predicts.\n")
    E = events(0); pat = [e for e in E if e['pat'] and e['brk']]; nonpat = [e for e in E if not (e['pat'] and e['brk'])]
    print(f"MONDAYS: {len(E)} proxy-Mondays. TFM pattern (Friday high <= Thursday high) AND Monday breaks Friday's low: {len(pat)} ({100 * len(pat) / len(E):.0f}%)")
    for key, lab in (('r_open', 'open to close'), ('r_b935', '9:35 open to close'), ('r_break', 'break of Friday low to close')):
        print(f"   {lab}"); summarize('TFM pattern + break', pat, key); summarize('all other Mondays', nonpat, key)
        if key != 'r_break':
            v = np.array([e[key] for e in pat]); pool = np.array([e[key] for e in E]); m = np.array([rng.choice(pool, len(v), replace=False).mean() for _ in range(5000)])
            print(f"      random draws of {len(v)} Mondays: pattern mean {v.mean():+.3f}% is lower than {100 * (m > v.mean()).mean():.1f}% of draws (p low-side {(m <= v.mean()).mean():.3f})")
    print("\nBY PROXY (open to close, pattern + break)")
    for p in PX: summarize(p, [e for e in pat if e['p'] == p], 'r_open')
    print("\nBY YEAR (open to close, pattern + break)")
    for y in range(2022, 2027): summarize(str(y), [e for e in pat if e['d'].startswith(str(y))], 'r_open')
    print("\nPLACEBO: the same structure on every other weekday (day d, d-1 high <= d-2 high, d breaks d-1 low), open to close")
    for dow, nm in ((1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday')):
        Ew = events(dow); pw = [e for e in Ew if e['pat'] and e['brk']]; summarize(f"{nm} ({100 * len(pw) / len(Ew):.0f}% qualify)", pw, 'r_open')
    print("\nTRADE-LIKE: short the proxy at the 9:35 open on pattern Mondays whose open is already below Friday's low (gap) vs not")
    summarize('gap below Friday low', [e for e in pat if e['gap'] < 0], 'r_b935'); summarize('open above Friday low, then breaks it', [e for e in pat if e['gap'] >= 0], 'r_b935')


if __name__ == '__main__':
    main()
