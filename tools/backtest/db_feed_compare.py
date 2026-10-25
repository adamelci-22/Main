#!/usr/bin/env python3
"""Bar-by-bar Robinhood vs Databento EQUS.MINI comparison on the shared 2026 dates.  /usr/bin/python3 -I tools/backtest/db_feed_compare.py DB_5M.json.gz"""
import gzip, json, statistics as st, sys
db = json.load(gzip.open(sys.argv[1], 'rt')); rh = json.load(gzip.open('/home/user/Main/tools/backtest/data/bt_5m.json.gz', 'rt'))
def et(t):  # DB bars are UTC start -> convert to ET using the RH session open
    return t
print(f"{'sym':<5}{'days':>5}{'vol DB/RH':>10}{'empty DB':>9}{'empty RH':>9}{'hi lower':>9}{'lo higher':>10}{'|hi diff| bp':>13}{'box DB/RH':>10}{'AM-high diff bp':>16}{'close diff bp':>14}")
for s in ('QQQ', 'SOXX', 'IWM', 'XLK', 'XBI', 'XLF', 'SOXS', 'LABD', 'TECS', 'TQQQ', 'SQQQ', 'SOXL', 'FAZ'):
    if s not in db or s not in rh: continue
    vr = []; e1 = e2 = n = 0; hl = lh = 0; hd = []; bx = []; amh = []; cd = []; nd = 0
    for d in sorted(set(db[s]) & set(rh[s])):
        a = db[s][d]; b = rh[s][d]
        if len(a) < 60 or len(b) < 60: continue
        # align by position from the session open (both are 9:30-start 5-min RTH bars)
        A = {i: r for i, r in enumerate(a)}; B = {i: r for i, r in enumerate(b)}
        if a[0][0] != b[0][0]:
            # align by clock offset
            off = (int(a[0][0][:2]) - int(b[0][0][:2])) * 60 + int(a[0][0][3:5]) - int(b[0][0][3:5])
            A = {r[0]: r for r in a}; B = {r[0]: r for r in b}
            def sh(t, m): h, mi = map(int, t.split(':')[:2]); x = h * 60 + mi + m; return f"{x//60:02d}:{x%60:02d}"
            A = {sh(k, -off): v for k, v in A.items()}
        keys = sorted(set(A) & set(B)); nd += 1
        vr.append(sum(A[k][5] for k in keys) / max(1, sum(B[k][5] for k in keys)))
        for k in keys:
            n += 1; e1 += A[k][5] == 0; e2 += B[k][5] == 0
            hl += A[k][2] < B[k][2] - 1e-9; lh += A[k][3] > B[k][3] + 1e-9; hd.append(abs(A[k][2] - B[k][2]) / B[k][2] * 1e4); cd.append(abs(A[k][4] - B[k][4]) / B[k][4] * 1e4)
        k6 = keys[:6]
        if len(k6) == 6:
            w1 = max(A[k][2] for k in k6) - min(A[k][3] for k in k6); w2 = max(B[k][2] for k in k6) - min(B[k][3] for k in k6)
            if w2 > 0: bx.append(w1 / w2)
            amh.append((max(B[k][2] for k in k6) - max(A[k][2] for k in k6)) / max(B[k][2] for k in k6) * 1e4)
    print(f"{s:<5}{nd:>5}{st.median(vr)*100:>9.0f}%{100*e1/n:>8.1f}%{100*e2/n:>8.1f}%{100*hl/n:>8.0f}%{100*lh/n:>9.0f}%{st.mean(hd):>13.1f}{st.median(bx)*100:>9.0f}%{st.mean(amh):>16.1f}{st.mean(cd):>14.1f}")
