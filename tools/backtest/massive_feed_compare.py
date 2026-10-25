#!/usr/bin/env python3
"""Bar-by-bar Robinhood vs Massive (full consolidated tape) comparison on the shared 2026 dates.
    /usr/bin/python3 -I tools/backtest/massive_feed_compare.py MASSIVE_5M.json.gz > tools/backtest/results/massive_feed_compare.txt
Bars are matched by UTC start time (a missing bar is not shifted onto its neighbour). Massive is the reference.
Columns: days; median day volume Massive/RH; share of matched bars with zero volume on each feed (Massive omits no-trade bars, so its zeros are bars RH shows and Massive lacks: see 'only RH');
'only RH' / 'only MS' = bars present on one feed only, % of the session grid; 'RH hi lower' = RH bar high below Massive's; 'RH lo higher' = RH bar low above Massive's;
|hi diff| / |close diff| = mean absolute difference in bp; 'box' = median ratio (Massive / RH) of the 9:30-10:00 high-low range; 'AM-high diff' = (RH - Massive) of the 9:30-10:00 high, bp.
"""
import gzip, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ms = json.load(gzip.open(sys.argv[1], 'rt')); rh = json.load(gzip.open(os.path.join(HERE, 'data', 'bt_5m.json.gz'), 'rt'))
SYMS = ['QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SOXS', 'LABD', 'TECS', 'UVXY', 'TQQQ', 'SQQQ', 'SOXL', 'TNA', 'TZA', 'TECL', 'LABU', 'FAS', 'FAZ',
        'SPY', 'TLT', 'GLD', 'KRE', 'VIXY', 'SPXU', 'SDS', 'QID', 'SRTY', 'SDOW', 'ERY', 'DRIP', 'DUST', 'TMV', 'UVIX', 'SVIX', 'NUGT', 'TMF']
print(f"{'sym':<5}{'days':>5}{'vol MS/RH':>10}{'0vol MS':>8}{'0vol RH':>8}{'only RH':>8}{'only MS':>8}{'RH hi lower':>12}{'RH lo higher':>13}{'|hi diff| bp':>13}{'|close diff| bp':>16}{'box MS/RH':>10}{'AM-high bp':>11}")
for s in SYMS:
    if s not in ms or s not in rh: continue
    vr = []; n = z1 = z2 = oR = oM = hl = lh = grid = 0; hd = []; cd = []; bx = []; amh = []; nd = 0
    for d in sorted(set(ms[s]) & set(rh[s])):
        A = {r[0]: r for r in ms[s][d]}; B = {r[0]: r for r in rh[s][d]}
        if len(B) < 60 or len(A) < 5: continue
        nd += 1; keys = sorted(set(A) & set(B)); grid += 78
        oR += len(set(B) - set(A)); oM += len(set(A) - set(B))
        if not keys: continue
        vr.append(sum(A[k][5] for k in keys) / max(1, sum(B[k][5] for k in keys)))
        for k in keys:
            n += 1; z1 += A[k][5] == 0; z2 += B[k][5] == 0
            hl += B[k][2] < A[k][2] - 1e-9; lh += B[k][3] > A[k][3] + 1e-9
            hd.append(abs(A[k][2] - B[k][2]) / A[k][2] * 1e4); cd.append(abs(A[k][4] - B[k][4]) / A[k][4] * 1e4)
        k6 = sorted(A)[:6]
        if len(k6) == 6 and all(k in B for k in k6):
            w1 = max(A[k][2] for k in k6) - min(A[k][3] for k in k6); w2 = max(B[k][2] for k in k6) - min(B[k][3] for k in k6)
            if w2 > 0: bx.append(w1 / w2)
            amh.append((max(B[k][2] for k in k6) - max(A[k][2] for k in k6)) / max(A[k][2] for k in k6) * 1e4)
    if not n: continue
    print(f"{s:<5}{nd:>5}{st.median(vr)*100:>9.0f}%{100*z1/n:>7.1f}%{100*z2/n:>7.1f}%{100*oR/grid:>7.1f}%{100*oM/grid:>7.1f}%{100*hl/n:>11.0f}%{100*lh/n:>12.0f}%{st.mean(hd):>13.1f}{st.mean(cd):>16.1f}"
          f"{(st.median(bx)*100 if bx else float('nan')):>9.0f}%{(st.mean(amh) if amh else float('nan')):>11.1f}")
