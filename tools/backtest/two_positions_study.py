import sys, inspect, re; sys.path[:0] = ['/home/user/Main/tools/live']
import improve as im, paper
src = inspect.getsource(paper.simulate)
a = src.index("    taken, skipped, free, eq = [], [], 0, equity"); b = src.index("    # a signal is only actionable")
block = '''    taken, skipped, eq0 = [], [], equity
    for c in cands:
        if streak >= LOCKOUT_LOSSES:
            c['why_skipped'] = 'LOCKOUT'; skipped.append(c); continue
        opn = [x for x in taken if x['xbar'] >= c['k']]
        if ALLOC in ('one', 'base'):
            if opn: c['why_skipped'] = 'account busy'; skipped.append(c); continue
        elif any(x['system'] == c['system'] for x in opn) or len(opn) >= 2:
            c['why_skipped'] = 'account busy'; skipped.append(c); continue
        eq = eq0 + sum(x['usd'] for x in taken if x['xbar'] < c['k'])
        if c['system'] == 'FADE':
            leg_risk = c['lev'] * c['risk_pct']; pct = c['lev'] * c['gross'] / c['entry'] * 100 - FADE_COST
        else:
            leg_risk = c['risk_pct']; pct = c['gross'] / c['entry'] * 100
        notional = min(eq * SIZE_CAP, eq * RISK / (leg_risk / 100))
        if c['system'] == 'FADE' and ALLOC in ('one', 'two'): notional = min(notional, eq * FADE_CAP)
        if ALLOC in ('two', 'free'): notional = min(notional, eq - sum(x['notional'] for x in opn))
        if notional < eq * 0.02:
            c['why_skipped'] = 'no capital left'; skipped.append(c); continue
        c.update(leg_risk=leg_risk, notional=notional, pct=pct, usd=notional * pct / 100, ov=bool(opn))
        streak = streak + 1 if c['usd'] < 0 else 0
        c['streak'] = streak; taken.append(c)
    eq = eq0 + sum(x['usd'] for x in taken)
'''
src = src[:a] + block + src[b:]
src = src.replace("def simulate(", "def simulate2(", 1)
paper.ALLOC, paper.FADE_CAP = 'base', 0.75
exec(src, paper.__dict__)
D = im.load_data(); values = im.champion_values(im.tun())

def run(mode, cap=0.75):
    paper.ALLOC, paper.FADE_CAP = mode, cap
    saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = values, '0000-00-00', '0000-00-00', True
    eq, daily, trades, skips, ov = 2000.0, [], [], 0, 0
    try:
        for i in range(1, len(D.days)):
            d, pd = D.days[i], D.days[i - 1]
            tod = {s: D.bars[s][d][:48] for s in im.WANT() if d in D.bars.get(s, {})}
            prv = {s: D.bars[s][pd] for s in im.WANT() if pd in D.bars.get(s, {})}
            taken, sk, _, e2 = paper.simulate2(tod, prv, 48, eq, None, 0, d)
            for c in taken:
                trades.append((d, c['usd'], c['usd'] / eq * 100, c['system'], False, c.get('ov', False), c['notional'] / eq * 100))
            skips += sum(1 for s in sk if s.get('why_skipped') in ('account busy', 'no capital left'))
            daily.append((d, (e2 / eq - 1) * 100)); eq = e2
    finally:
        paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved
    return daily, trades, skips

ref, rt = im.run_cf(D, values)
for name, mode, cap in (('Current (one at a time)', 'base', 1.0), ('Two at once, no cap, second trade gets only the cash left', 'free', 1.0), ('Two at once, no cap, each sized as if alone (needs 2x buying power)', 'lev', 1.0)):
    daily, tr, sk = run(mode, cap)
    s = im.stats(daily, tr)
    f = [t for t in tr if t[3] == 'FADE']; p = [t for t in tr if t[3] != 'FADE']
    ov = [t for t in tr if t[5]]
    print(f"{name}\n  {s['ret']:+.1f}% total, {s['mean_day']:+.3f}%/day, drawdown {s['dd']:.2f}%, Sharpe {s['sharpe']}, PF {s['pf']}; trades FADE {len(f)} PB {len(p)} (overlapping {len(ov)}), skipped busy {sk}")
    print(f"  avg size FADE {sum(t[6] for t in f)/max(1,len(f)):.0f}% PB {sum(t[6] for t in p)/max(1,len(p)):.0f}%; PB trades that ran alongside FADE avg size {sum(t[6] for t in ov)/max(1,len(ov)):.0f}% of account")
    if mode == 'base': print(f"  check vs run_cf: {im.stats(ref, rt)['ret']:+.1f}% {im.stats(ref, rt)['mean_day']:+.3f}%/day trades {len(rt)}")
