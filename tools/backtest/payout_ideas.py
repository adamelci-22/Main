#!/usr/bin/env python3
"""Payout ideas for the live FADE + PULLBACK system (one account), each judged where it was not chosen.
    python3 tools/backtest/payout_ideas.py > tools/backtest/results/payout_ideas.txt
Windows: TUNE-H1 = 2026-04-07..07-10 (choose here), TUNE-H2 = 07-13..10-14 and MARCH = 03-03..04-06 (judge here). ALL = 157 days.
1  Account: signals skipped while busy; two positions (one per system, half the cash each); risk-per-trade dial; tie-break rules.
2  FADE filters at the signal (RVOL, box width, gap, stop size, break strength, retest-bar volume).
3  FADE stop buffer beyond the failed breakout's extreme.
4  PULLBACK filters (RVOL of the leg, room to target).
"""
import collections, io, contextlib, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import manual as m, pb_final as PBF, mixed as MXD, retest as RT, fade_combo as FC, final_system as FS, twobar as TB
    from lab import get_data

D = get_data(); m.rvol = PBF.rvol(D); ALL = D.days[1:]
MAR = [d for d in ALL if d < '2026-04-07']; TUNE = [d for d in ALL if d >= '2026-04-07']; h = len(TUNE) // 2; H1, H2 = TUNE[:h], TUNE[h:]
f0, p0 = FS.cands(D, ALL)


def acct(cands, **kw):
    a = MXD.account(D, ALL, cands, **kw); dl = a['daily']; v = lambda ds: st.mean(dl[d] for d in ds)
    return dict(all=v(ALL), h1=v(H1), h2=v(H2), mar=v(MAR), ret=a['ret'], dd=a['mdd'], n=len(a['taken']), a=a)


BASE = acct(f0 + p0)
def show(label, r, ref=BASE):
    flag = '  BEATS BASE IN H2 AND MARCH' if r['h2'] > ref['h2'] and r['mar'] > ref['mar'] and r['all'] > ref['all'] else ''
    print(f"   {label:<52} {r['all']:+.3f}%/day (H1 {r['h1']:+.3f} H2 {r['h2']:+.3f} Mar {r['mar']:+.3f}) ret {r['ret']:+7.1f}% DD {r['dd']:4.1f}% trades {r['n']:3d}{flag}")


print(f"PAYOUT IDEAS  ALL {ALL[0]}..{ALL[-1]} ({len(ALL)} d) | choose on TUNE-H1 {H1[0]}..{H1[-1]} | judge on TUNE-H2 {H2[0]}..{H2[-1]} and MARCH {MAR[0]}..{MAR[-1]}\n")
show('BASE (live rules)', BASE)

# ------------------------------------------------------------------ 1. account structure
print("\n== 1. ACCOUNT STRUCTURE ==")
taken = {(x['day'], x['sys'], x['name'], x['k']) for x in BASE['a']['taken']}
skipped = [c for c in f0 + p0 if (c['day'], c['sys'], c['name'], c['k']) not in taken]
print(f"   signals the live rules skip (account busy / tie lost): {len(skipped)}; their average result {st.mean(c['pct'] for c in skipped):+.3f}% on the leg "
      f"(taken trades average {st.mean(x['pct'] for x in BASE['a']['taken']):+.3f}%)")
show('two positions at once (one per system, each half the cash)', acct(f0 + p0, mode='two'))
for r in (0.02, 0.04, 0.05):
    show(f'risk per trade {r*100:.0f}% (live 3%; size still capped at cash)', acct(f0 + p0, risk=r))
show('tie-break: PULLBACK before FADE on the same bar', acct(f0 + p0, priority=['PB', 'FADE']))
show('tie-break: FADE before PULLBACK on the same bar', acct(f0 + p0, priority=['FADE', 'PB']))

# ------------------------------------------------------------------ 2. FADE filters
print("\n== 2. FADE FILTERS (chosen on TUNE-H1 only; PULLBACK unchanged) ==")
def feats(c):
    d, p = c['day'], c['proxy']; b = D.bars[p][d]; i = D.days.index(d); pc = D.bars[p][D.days[i - 1]][-1][3]
    H = max(x[1] for x in b[:6]); L = min(x[2] for x in b[:6]); side = 1 if c['name'].endswith('+') else -1
    j = next(q for q in range(6, 9) if b[q][3] > H or b[q][3] < L)
    edge = H if b[j][3] > H else L
    pri = D.prior(d, 20); wid = st.median((max(x[1] for x in D.bars[p][q][:6]) - min(x[2] for x in D.bars[p][q][:6])) / D.bars[p][q][0][0] for q in pri)
    return dict(rvol=TB.rvol(D, p, d, c['k']), wide=((H - L) / b[0][0]) > wid, gap_with=side * (b[0][0] - pc) > 0,
                brk=abs(b[j][3] - edge) / edge * 100, risk=c['risk'], rvol_brk=TB.rvol(D, p, d, j))
F = [(c, feats(c)) for c in f0]
med_risk = st.median(x['risk'] for _, x in F); med_brk = st.median(x['brk'] for _, x in F)
FILT = {
    'RVOL >= 1.0 at entry': lambda x: x['rvol'] >= 1.0, 'RVOL < 1.0 at entry': lambda x: x['rvol'] < 1.0,
    'RVOL >= 1.5 at entry': lambda x: x['rvol'] >= 1.5,
    'box wider than usual': lambda x: x['wide'], 'box narrower than usual': lambda x: not x['wide'],
    'gap in the trade direction': lambda x: x['gap_with'], 'gap against the trade': lambda x: not x['gap_with'],
    f'stop tighter than median ({med_risk:.2f}% leg)': lambda x: x['risk'] < med_risk, 'stop wider than median': lambda x: x['risk'] >= med_risk,
    f'weak break (< {med_brk:.2f}% past the edge)': lambda x: x['brk'] < med_brk, 'strong break': lambda x: x['brk'] >= med_brk,
}
res = []
for name, fn in FILT.items():
    r = acct([c for c, x in F if fn(x)] + p0); res.append((r['h1'], name, r))
res.sort(reverse=True)
for _, name, r in res: show(f'FADE only if {name}', r)
best = res[0]
print(f"   -> chosen on TUNE-H1: '{best[1]}'. Out of sample: H2 {best[2]['h2']:+.3f} vs base {BASE['h2']:+.3f}; March {best[2]['mar']:+.3f} vs {BASE['mar']:+.3f}")

# ------------------------------------------------------------------ 3. FADE stop buffer
print("\n== 3. FADE STOP BUFFER beyond the failed breakout's extreme ==")
orig = RT.setup
for buf in (0.05, 0.10, 0.20):
    def patched(raw, c, buf=buf):
        s = orig(raw, c)
        if s and c.fade:
            k, side, e, sp = s; return k, side, e, sp * (1 - side * buf / 100)
        return s
    RT.setup = patched
    f, _ = FS.cands(D, ALL); show(f'stop {buf:.2f}% further away', acct(f + p0))
RT.setup = orig

# ------------------------------------------------------------------ 4. PULLBACK filters
print("\n== 4. PULLBACK FILTERS (FADE unchanged) ==")
def pbf(c):
    return dict(rvol=TB.rvol(D, c['proxy'], c['day'], c['k']) if c['proxy'] in D.cum else None, risk=c['risk'])
P = [(c, pbf(c)) for c in p0]; mr = st.median(x['risk'] for _, x in P)
for name, fn in ((f'stop tighter than median ({mr:.2f}%)', lambda x: x['risk'] < mr), ('stop wider than median', lambda x: x['risk'] >= mr),
                 ('proxy RVOL >= 1.0 (SOXS/TECS/NVD only; others kept)', lambda x: x['rvol'] is None or x['rvol'] >= 1.0),
                 ('drop UVXY', None), ('drop LABD', None), ('drop NVD', None)):
    if fn is None:
        leg = name.split()[-1]; sel = [c for c in p0 if c['name'] != leg]
    else:
        sel = [c for c, x in P if fn(x)]
    show(f'PULLBACK only if {name}' if fn else f'PULLBACK {name}', acct(f0 + sel))

# ------------------------------------------------------------------ 5. PULLBACK entry: market at the next open instead of the limit
print("\n== 5. PULLBACK ENTRY: buy at the next bar's open (no limit) vs the live limit at the trigger close ==")
import pb_inverse as PI
orig_scan = PBF.scan
def scan_market(b, e9, e20, oco_gap):
    bh = max(x[1] for x in b[:3])
    for j in range(8, 41):
        if not (e9[j] > e20[j] and b[j][3] > e9[j]): continue
        for n in (2, 3, 4, 5):
            ps = range(j - n, j)
            if ps[0] < 4: continue
            if not all(b[i][3] < b[i][0] or b[i][1] < b[i - 1][1] for i in ps): continue
            if b[j][3] <= b[j - 1][1]: continue
            low = min(b[i][2] for i in ps)
            if not (e20[j - 1] * 0.995 <= low <= e9[j - 1] * 1.001): continue
            pre = j - n
            if not any(b[i][3] > bh and b[i][4] > 1.5 * st.mean(b[q][4] for q in range(max(0, i - 6), i)) for i in range(3, pre)): continue
            hod = PBF.target_level(b, pre, max(b[i][1] for i in range(0, pre))); stop = low * (1 - PBF.BUFFER_PCT / 100)
            entry = b[j + 1][0] * 1.001          # marketable buy: next open + 0.10%
            if hod <= entry or entry <= stop or (entry - stop) / entry * 100 < PBF.MIN_ROOM: continue
            if (hod - entry) < PBF.MIN_RR * (entry - stop) or (hod - entry) / entry * 100 < 0.25: continue
            if oco_gap and hod - stop < 0.10: continue
            return dict(k=j + 1, entry=entry, stop=stop, hod=hod, sig=j)
    return None
PBF.scan = scan_market
s = PBF.run(D, ALL, FS.PB, oco_gap=True)
pm = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in s]
PBF.scan = orig_scan
print(f"   PULLBACK setups: live limit {len(p0)}, market entry {len(pm)}")
show('PULLBACK market entry at next open + 0.10%', acct(f0 + pm))
