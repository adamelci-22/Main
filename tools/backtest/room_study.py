#!/usr/bin/env python3
"""Room-to-target study: loosen the PULLBACK filter  (morning high - entry) >= MIN_RR x (entry - stop)  and  >= MIN_ROOM_PCT % of entry.
    python3 tools/backtest/room_study.py > tools/backtest/results/room_study.txt
Same harness as final_system.py. D3: judge on H2 and the untouched March window, not only the whole period.
"""
import io, contextlib, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import manual as m, pb_final as PBF, mixed as MXD, final_system as FS
    from lab import get_data
D = get_data(); m.rvol = PBF.rvol(D); ALL = D.days[1:]
MAR = [d for d in ALL if d < '2026-04-07']; TUNE = [d for d in ALL if d >= '2026-04-07']; h = len(TUNE) // 2; H1, H2 = TUNE[:h], TUNE[h:]
f0 = [c for p in FS.FADE for c in MXD.norm_px(FS.EX.fade_trades(D, ALL, p, FS.FA.ROWS[p]), 'FADE')]
print(f"ROOM STUDY  {ALL[0]}..{ALL[-1]} ({len(ALL)} d) | H1 {H1[0]}..{H1[-1]} | H2 {H2[0]}..{H2[-1]} | MARCH {MAR[0]}..{MAR[-1]}\n")
def go(rr, pct):
    PBF.MIN_RR, PBF.MIN_ROOM_PCT = rr, pct
    S = PBF.run(D, ALL, FS.PB, oco_gap=True)
    p = [dict(day=x['day'], sys='PB', name=x['inst'], proxy=FS.PI.PROXY[x['inst']], k=x['k'], xbar=x['xbar'], pct=x['pct'], risk=x['risk'] / x['entry'] * 100) for x in S]
    a = MXD.account(D, ALL, f0 + p); dl = a['daily']; v = lambda ds: st.mean(dl[d] for d in ds)
    tk = a['taken']; pb = [x for x in tk if x.get('sys') == 'PB']
    return dict(all=v(ALL), h1=v(H1), h2=v(H2), mar=v(MAR), ret=a['ret'], dd=a['mdd'], n=len(tk), npb=len(pb), setups=len(p),
                wr=100 * sum(x['usd'] > 0 for x in pb) / max(1, len(pb)), pbusd=sum(x['usd'] for x in pb))
base = go(0.75, 0.25)
print(f"{'MIN_RR':>6} {'MIN%':>5} | {'%/day':>7} {'H1':>7} {'H2':>7} {'Mar':>7} | {'ret%':>7} {'DD%':>5} | trades PBtaken PBsetups PBwin% PB$")
for rr in (0.75, 0.5, 0.25, 0.0):
    for pct in (0.25, 0.15, 0.10, 0.0):
        r = go(rr, pct); ok = r['h2'] > base['h2'] and r['mar'] > base['mar'] and r['all'] > base['all']
        print(f"{rr:6.2f} {pct:5.2f} | {r['all']:+7.3f} {r['h1']:+7.3f} {r['h2']:+7.3f} {r['mar']:+7.3f} | {r['ret']:+7.1f} {r['dd']:5.1f} | {r['n']:5d} {r['npb']:7d} {r['setups']:8d} {r['wr']:7.0f} {r['pbusd']:+8.0f}" + ('  BEATS BASE ALL 3' if ok and (rr, pct) != (0.75, 0.25) else '') + ('  <- live' if (rr, pct) == (0.75, 0.25) else ''))
PBF.MIN_RR, PBF.MIN_ROOM_PCT = 0.75, 0.25
