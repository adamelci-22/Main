import importlib.util, sys, os, io, contextlib, time
S = os.path.dirname(os.path.abspath(__file__))
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
PM, PB = load('paper_main', S + '/main/paper.py'), load('paper_branch', S + '/branch/paper.py')
sys.path.insert(0, '/home/user/Main/tools/backtest')
with contextlib.redirect_stdout(io.StringIO()):
    from lab import get_data
    D = get_data(live=True)
print('sessions', len(D.days), D.days[0], D.days[-1])
def sig(taken):
    return [(c['system'], c['ticker'], c['k'], round(c.get('usd') or 0, 6), c['status'], c.get('why'), round(c.get('pct') or 0, 8), [(e[0], e[1], round(e[2], 6)) for e in c['events']]) for c in taken]
tot = same = 0; trades = 0; t0 = time.time()
for label, lc in (('lock+cut ON', '0000-00-00'), ('lock+cut OFF', '9999-12-31')):
    for P in (PM, PB): P.LOCKCUT_FROM = lc
    eq_m = eq_b = 2000.0; diffs = 0
    for i in range(1, len(D.days)):
        d, pd = D.days[i], D.days[i - 1]
        tod = {s: D.bars[s][d][:48] for s in PM.EXPECTED if d in D.bars.get(s, {})}; prv = {s: D.bars[s][pd] for s in PM.EXPECTED if pd in D.bars.get(s, {})}
        for day_arg in (d, None):
            rm = PM.simulate(tod, prv, 48, eq_m, None, 0, day_arg); rb = PB.simulate(tod, prv, 48, eq_b, None, 0, day_arg)
            tot += 1; ok = sig(rm[0]) == sig(rb[0]) and rm[3] == rb[3] and [s['ticker'] if isinstance(s, dict) and 'ticker' in s else str(s) for s in rm[2]] == [s['ticker'] if isinstance(s, dict) and 'ticker' in s else str(s) for s in rb[2]]
            same += ok; diffs += (not ok); trades += len(rm[0])
            if day_arg == d: eq_m, eq_b = rm[3], rb[3]
    print(f"{label}: sessions x2 compared, differing {diffs}, final equity main {eq_m:.4f} branch {eq_b:.4f}")
print(f"day-runs {tot}, identical {same}, trades compared {trades}, {time.time()-t0:.0f}s")
