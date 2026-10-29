#!/usr/bin/env python3
"""Self-improvement loop for the FADE and PULLBACK model (RULEBOOK D4, v5.2.31: forward-shadow evidence).

Champion / challenger. The REAL account and the paper model keep running the version in force (the champion). EVERY candidate is simulated beside it on each
day's saved bars, forever and for free (no orders): the 12 numbers in tunables.json one step either way, plus the structural ideas in ideas.json
(universe drops, entry cut-offs, minimum retest wait, choppy-trade exit, one-loss-ends-the-day). Evidence is only what happens AFTER the baseline date
(policy.shadow_from), so it is out-of-sample by construction. A candidate is READY when, over its shadow days, it differed on enough days, its paired
bootstrap lower bound (Bonferroni-adjusted for the number of candidates ever tracked) is above zero and it gained the promote margin. A candidate that is
clearly harming (or still undecided after retire_days) is retired and written to the research ledger (tools/live/research_ledger.json).
Only a numeric tunable can be promoted by this loop, and only by the governor; an idea that becomes READY is reported and needs a rulebook change (D3).
Nothing here places an order.

Commands (stdlib only; run from anywhere):
    improve.py tick [DUMP ...]        13:30 close, AFTER `paper.py --close`: shadow-run every candidate on the day's bars, update the evidence, retire, report
    improve.py evidence               the full evidence table (champion version in force)
    improve.py status                 version in force, challenger, pending proposal, evidence summary, last ledger events
    improve.py research [--verdict V] the research ledger: every study and every retired candidate with its numbers
    improve.py research-add --id I --idea "..." --method "..." --result "..." --verdict V      append a study to the research ledger
    improve.py screen [SYM ...]       liquidity and data coverage of dataset symbols (candidates for the watchlist)
    improve.py watch-add --type fade|pb ...   put a ticker or FADE proxy on trial (shadow only); add-checklist ID prints the D3 steps to trade it
    improve.py prompt                 the proposer prompt (the checkpoint session answers it, then runs `submit`)
    improve.py submit CHOICE "why"    CHOICE = a READY numeric candidate id (e.g. fade.cut_r-1) or hold; writes the pending proposal
    improve.py approve --note "..."   governor: the pending proposal becomes the challenger (its evidence is already forward). The live account is NOT changed
    improve.py promote --effective D --note "..."   governor: put the challenger live from future trading day D
    improve.py discard --note "..."   governor: drop the challenger. improve.py reject: drop a pending proposal
    improve.py rollback --effective D governor: restore the values the version in force replaced (after a promotion)
    improve.py menu [--risk-off]      informational: one-step table on the dataset (base file plus the appended live sessions), walk-forward gate. --risk-off adds size cuts
    improve.py shadow-replay --from D --to D [--force]   test/backfill: shadow-run dataset sessions (use IMPROVE_DIR=<tmp> so the real ledger is untouched)
"""
import argparse, csv, glob, json, math, os, random, statistics as st, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import paper

TUN = os.path.join(HERE, 'tunables.json'); IDEAS = os.path.join(HERE, 'ideas.json'); WATCH = os.path.join(HERE, 'watchlist.json'); RLEDGER = os.environ.get('IMPROVE_RLEDGER') or os.path.join(HERE, 'research_ledger.json')
IDIR = os.environ.get('IMPROVE_DIR') or os.path.join(ROOT, 'archive', 'improve')
LEDGER, PENDING, SHADOW = (os.path.join(IDIR, n) for n in ('ledger.jsonl', 'pending.json', 'shadow_all.csv'))
PAPER_LOG = os.path.join(ROOT, 'archive', 'paper_trades.csv')
HWM = os.path.join(ROOT, 'archive', 'hwm.json')
ET = ZoneInfo('America/New_York')
GATE_DD_SLACK, GATE_MIN_GAIN, GATE_TRADE_KEEP, SPLIT = 1.0, 0.01, 0.75, 0.6     # menu only: pts of drawdown, %/day, share of trades kept, in-sample share
SHADOW_HDR = ['day', 'cver', 'id', 'champion_pct', 'candidate_pct', 'differs', 'champion_trades', 'candidate_trades']


# ------------------------------------------------------------------ files
def tun():
    t = json.load(open(TUN))
    bad = [k for k in t['space'] if any(w in k.lower() for w in ('usd', 'dollar', '$'))]
    if bad: sys.exit(f"tunables must be percentages or ratios of the account, never dollar amounts: {bad}")
    return t


def save_tun(t):
    json.dump(t, open(TUN, 'w'), indent=2); open(TUN, 'a').write('\n')


def ledger(event=None, **kw):
    os.makedirs(IDIR, exist_ok=True)
    if event:
        with open(LEDGER, 'a') as f: f.write(json.dumps(dict(ts=datetime.now(ET).isoformat(timespec='seconds'), event=event, **kw)) + '\n')
    return [json.loads(x) for x in open(LEDGER) if x.strip()] if os.path.exists(LEDGER) else []


def pending():
    return json.load(open(PENDING)) if os.path.exists(PENDING) else None


def today():
    return datetime.now(ET).date()


def next_trading_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in paper.NO_TRADE: d += timedelta(days=1)
    return d


def current(t=None):
    v = (t or tun())['versions']
    return max(v, key=lambda x: x['effective_from'])


def challenger(t=None):
    return (t or tun()).get('challenger')


def version_values(t, n):
    return next(v['values'] for v in t['versions'] if v['version'] == n)


def model_trades():
    if not os.path.exists(PAPER_LOG): return []
    out = []
    for r in csv.DictReader(open(PAPER_LOG)):
        usd = float(r['pnl_usd']); eq_before = float(r['equity_after']) - usd
        out.append(dict(day=r['day'], system=r['system'], ticker=r['ticker'], reason=r['exit_reason'], usd=usd, acct_pct=usd / eq_before * 100, pct_leg=float(r['pct_leg'])))
    return out


# ------------------------------------------------------------------ counterfactual engine (menu only; paper.simulate on the dataset)
def WANT():
    return set(paper.EXPECTED) | watch_symbols()


def load_data():
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'backtest'))
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        from lab import get_data
        return get_data(live=True)      # base dataset plus the live sessions appended by tools/backtest/extend_live.py


def run_cf(D, values):
    """Current rules (lock, early cut, no FADE on Fridays, floored target) over every session in the dataset with the given tunables.
    One account from $2,000, 3% risk, losing streak cleared each morning (the backtest convention). Returns daily returns and trades."""
    saved = (paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET)
    paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = values, '0000-00-00', '0000-00-00', True
    try:
        eq, daily, trades = 2000.0, [], []
        for i in range(1, len(D.days)):
            d, pd = D.days[i], D.days[i - 1]
            tod = {s: D.bars[s][d][:48] for s in WANT() if d in D.bars.get(s, {})}
            prv = {s: D.bars[s][pd] for s in WANT() if pd in D.bars.get(s, {})}
            taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
            for c in taken:
                if c['status'] == 'closed': trades.append((d, c['usd'], c['usd'] / eq * 100, c['system'], c['system'] == 'FADE' and any('take profit' in e[1] for e in c['events'])))
            daily.append((d, (e2 / eq - 1) * 100)); eq = e2
        return daily, trades
    finally:
        paper.OVERRIDE, paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM, paper.FLOOR_TARGET = saved


def stats(daily, trades, lo=0, hi=None):
    days = daily[lo:hi]; dset = {d for d, _ in days}; tr = [t for t in trades if t[0] in dset]
    r = [x for _, x in days]; eq = peak = 1.0; dd = 0.0
    for x in r:
        eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    w = sum(t[1] for t in tr if t[1] > 0); l = -sum(t[1] for t in tr if t[1] < 0)
    sd = st.pstdev(r) if len(r) > 1 else 0.0
    sharpe = round(st.mean(r) / sd * math.sqrt(252), 2) if sd else 0.0
    return dict(mean_day=round(st.mean(r), 4) if r else 0.0, dd=round(dd, 2), trades=len(tr), pf=round(w / l, 2) if l else None, ret=round((eq - 1) * 100, 2), sharpe=sharpe)


def evaluate(D, values):
    daily, trades = run_cf(D, values); cut = int(len(daily) * SPLIT)
    return dict(full=stats(daily, trades), ins=stats(daily, trades, 0, cut), oos=stats(daily, trades, cut))


def menu(D, base_values, space, risk_off=False, goals=None):
    goals = goals or {}
    base_values = {**paper.TUNABLE_DEFAULTS, **base_values}; base = evaluate(D, base_values); rows = []
    for var, sp in space.items():
        if sp.get('needs') == 'risk_off' and not risk_off: continue
        for sgn in (-1, 1):
            if sp.get('down_only') and sgn > 0: continue
            new = round(min(sp['hi'], max(sp['lo'], base_values[var] + sgn * sp['step'])), 4)
            if new == base_values[var]: continue
            v = dict(base_values); v[var] = new; e = evaluate(D, v)
            d = {k: round(e[k]['mean_day'] - base[k]['mean_day'], 4) for k in e}
            why = []
            if sp.get('needs') == 'risk_off':      # a risk cut always lowers %/day, so it is judged on risk instead: drawdown down 15%+, return per drawdown point kept within 10%
                b, c = base['full'], e['full']
                if c['dd'] > 0.85 * b['dd']: why.append('drawdown not cut by 15%')
                if c['dd'] and b['dd'] and c['ret'] / c['dd'] < 0.9 * b['ret'] / b['dd']: why.append('return per drawdown point down more than 10%')
                rows.append(dict(id=f"{var}-1", variable=var, old=base_values[var], new=new, delta=d, stats=e, passes=not why, fails=why)); continue
            if d['ins'] < 0: why.append('worse in-sample')
            if d['oos'] < 0: why.append('worse out-of-sample')
            if d['full'] < GATE_MIN_GAIN: why.append(f"gain < {GATE_MIN_GAIN}%/day")
            if e['full']['dd'] > base['full']['dd'] + GATE_DD_SLACK: why.append('drawdown +%.1f pts' % (e['full']['dd'] - base['full']['dd']))
            if e['full']['trades'] < GATE_TRADE_KEEP * base['full']['trades']: why.append('trades cut by more than 25%')
            if goals:
                if e['full']['dd'] > goals['max_drawdown_pct']: why.append(f"drawdown above the {goals['max_drawdown_pct']}% goal limit")
                if base['full']['sharpe'] >= goals['min_sharpe'] and e['full']['sharpe'] < goals['min_sharpe']: why.append(f"Sharpe falls below the {goals['min_sharpe']} floor")
                e['full']['sharpe_gain'] = round(e['full']['sharpe'] - base['full']['sharpe'], 2)
            rows.append(dict(id=f"{var}{'+1' if sgn > 0 else '-1'}", variable=var, old=base_values[var], new=new, delta=d, stats=e, passes=not why, fails=why))
    return base, rows


def goal_progress():
    """The paper model's own record against the goals: 30-day-equivalent return, drawdown, Sharpe (needs 2+ trading days)."""
    g = tun().get('goals') or {}; d = {}
    for x in model_trades(): d[x['day']] = d.get(x['day'], 0.0) + x['acct_pct']
    r = [v for _, v in sorted(d.items())]
    if len(r) < 2: return dict(days=len(r), note='fewer than 2 trading days')
    eq = peak = 1.0; dd = 0.0
    for x in r: eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    sd = st.pstdev(r); sh = st.mean(r) / sd * math.sqrt(252) if sd else 0.0
    return dict(days=len(r), mean_pct_per_day=round(st.mean(r), 3), target_pct_per_day=g.get('target_daily_pct'), max_drawdown_pct=round(dd, 2), drawdown_limit_pct=g.get('max_drawdown_pct'),
                sharpe=round(sh, 2), sharpe_floor=g.get('min_sharpe'), sharpe_goal=g.get('target_sharpe'))




def future_trading_day(eff):
    if eff <= today().isoformat() or datetime.strptime(eff, '%Y-%m-%d').weekday() >= 5 or eff in paper.NO_TRADE:
        sys.exit('--effective must be a future trading day: a live day is never changed mid-session')


def append_version(t, kind, eff, vals, **kw):
    n = max(v['version'] for v in t['versions']) + 1
    t['versions'].append(dict(version=n, kind=kind, effective_from=eff, values=vals, **kw)); return n


# ------------------------------------------------------------------ candidates, shadow runs, evidence
def policy(t):
    return {'shadow_from': '0000-00-00', 'min_diff_days': 20, 'alpha': 0.10, 'harm_diff_days': 10, 'retire_days': 60, 'resamples': 5000, 'promote_pct': 0.5, 'risk_pstop_slack': 1.0, 'risk_dd_slack': 1.0, 'risk_target_pstop': 2.0, 'risk_cost_max': 0.10, **t['policy']}


def ideas():
    return json.load(open(IDEAS)) if os.path.exists(IDEAS) else []


def watchlist():
    return json.load(open(WATCH)) if os.path.exists(WATCH) else []


def watch_symbols():
    out = set()
    for w in watchlist(): out |= {w['proxy'], w['bull'], w['bear']} if w['type'] == 'fade' else {w['leg']}
    return out


def champion_values(t):
    return {**paper.TUNABLE_DEFAULTS, **current(t)['values']}


def rledger():
    return json.load(open(RLEDGER)) if os.path.exists(RLEDGER) else []


def radd(**kw):
    L = rledger(); L.append({'date': today().isoformat(), **kw}); json.dump(L, open(RLEDGER, 'w'), indent=1); open(RLEDGER, 'a').write('\n')


def retired_ids(t):
    cv = current(t)['version']
    return {e['id'] for e in rledger() if e.get('kind') in ('shadow', 'prior') and e.get('champion_version') == cv and e.get('verdict') in ('rejected', 'inconclusive', 'parked')}


def candidates(t, retired=()):
    """Every one-step numeric change (not the size cuts, which stay manual: menu --risk-off) plus every idea, each as a full value set vs the champion."""
    base = champion_values(t); out = []
    for var, sp in t['space'].items():
        if sp.get('needs') == 'risk_off': continue
        for sgn in (-1, 1):
            new = round(min(sp['hi'], max(sp['lo'], base[var] + sgn * sp['step'])), 4)
            if new == base[var]: continue
            v = dict(base); v[var] = new
            out.append(dict(id=f"{var}{'+1' if sgn > 0 else '-1'}", kind='tunable', desc=f"{var} {base[var]:g} -> {new:g} ({sp['rule']})", values=v, promotable=True, variable=var, old=base[var], new=new))
    for i in ideas():
        v = dict(base); v.update(i['values'])
        out.append(dict(id=i['id'], kind='idea', desc=i['desc'], values=v, promotable=False))
    for w in watchlist():                       # tickers and proxies on trial (shadow only; adding to the traded lists is a rulebook change, D3)
        v = dict(base)
        if w['type'] == 'fade': v['x.add_fade'] = [[w['proxy'], w['bull'], w['bear'], w['lev_bull'], w['lev_bear']]]; cid, desc = f"add.fade.{w['proxy']}", f"add the {w['proxy']} FADE proxy ({w['bull']}/{w['bear']}, {w['lev_bull']:g}x/{w['lev_bear']:g}x)"
        else: v['x.add_pb'] = [w['leg']]; cid, desc = f"add.pb.{w['leg']}", f"add {w['leg']} to the PULLBACK list"
        out.append(dict(id=cid, kind='idea', desc=desc, values=v, promotable=False))
    cur = current(t)
    if cur['kind'] == 'change' and not cur.get('defensive'):     # a defensive change is undone by RESTORE POSSIBLE (edge INTACT), not by return; rollback guard (v5.2.34): the version a promotion replaced is shadowed against it at once
        v = {**paper.TUNABLE_DEFAULTS, **version_values(t, cur['base_version'])}
        out.append(dict(id=f"rollback.v{cur['base_version']}", kind='rollback', desc=f"go back to v{cur['base_version']} (undo the promotion of v{cur['version']})", values=v, promotable=False))
    return [c for c in out if c['id'] not in retired]


def day_inputs(dumps):
    raw = paper.load([f for g in dumps for f in glob.glob(g)])
    days = sorted({d for s in raw.values() for d in s}); day = days[-1]; prevday = max(d for d in days if d < day)
    today_ = {s: g for s in raw if day in raw[s] for g in [paper.grid(raw[s][day], 48)] if g}
    prev = {s: g for s in raw if prevday in raw[s] for g in [paper.grid(raw[s][prevday], 78)] if g}
    return day, today_, prev


def run_day(day, today_, prev, values):
    """One day on a fresh $1,000 with a clean streak (same code path as paper.main). Returns (account return %, trade signature)."""
    paper.FLOOR_TARGET = day >= paper.FLOOR_FROM; saved = paper.OVERRIDE; paper.OVERRIDE = values
    try:
        taken, _, _, e2 = paper.simulate(today_, prev, 48, 1000.0, None, 0, day)
    finally:
        paper.OVERRIDE = saved
    return (e2 / 1000.0 - 1) * 100, [(c['system'], c['ticker'], c['k'], round(c.get('usd') or 0, 6), c.get('why')) for c in taken]


def shadow_rows():
    return list(csv.DictReader(open(SHADOW))) if os.path.exists(SHADOW) else []


def record_all(t, day, today_, prev, force=False):
    """Run the champion and every active candidate on this day's bars and append one row each (idempotent per day, version and id)."""
    pol = policy(t)
    if day < pol['shadow_from'] and not force: return 0
    cv = current(t)['version']; have = {(r['day'], r['cver'], r['id']) for r in shadow_rows()}
    cpct, csig = run_day(day, today_, prev, champion_values(t)); new = []
    for c in candidates(t, retired_ids(t)):
        if (day, str(cv), c['id']) in have: continue
        p, s = run_day(day, today_, prev, c['values'])
        new.append([day, cv, c['id'], round(cpct, 6), round(p, 6), int(s != csig), len(csig), len(s)])
    if new:
        fresh = not os.path.exists(SHADOW); os.makedirs(IDIR, exist_ok=True)
        with open(SHADOW, 'a', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            if fresh: w.writerow(SHADOW_HDR)
            w.writerows(new)
    return len(new)


def evidence(t):
    """Paired evidence per active candidate against the champion in force, from forward shadow days only."""
    pol = policy(t); cv = str(current(t)['version']); by = {}
    for r in shadow_rows():
        if r['cver'] == cv: by.setdefault(r['id'], []).append(r)
    retired = retired_ids(t); cvi = int(cv); m_ever = len(set(by) | {e['id'] for e in rledger() if e.get('kind') == 'shadow' and e.get('champion_version') == cvi}); m = max(1, m_ever); meta = {c['id']: c for c in candidates(t)}; out = []      # parked (prior) candidates never ran forward, so they do not count
    for cid, rows in by.items():
        if cid in retired: continue
        rows.sort(key=lambda r: r['day']); d = [float(r['candidate_pct']) - float(r['champion_pct']) for r in rows]; n = len(d)
        rng = random.Random(f"{cid}:{n}:{cv}"); B = pol['resamples']
        sums = sorted(sum(rng.choices(d, k=n)) for _ in range(B)) if n >= 5 else None
        lo = sums[min(B - 1, int(pol['alpha'] / m * B))] if sums else None            # Bonferroni: the lower bound at alpha / (candidates ever tracked)
        hi = sums[min(B - 1, int((1 - pol['alpha']) * B))] if sums else None
        e = dict(id=cid, kind=meta[cid]['kind'] if cid in meta else '?', promotable=meta[cid]['promotable'] if cid in meta else False, desc=meta[cid]['desc'] if cid in meta else '',
                 n_days=n, n_diff=sum(int(r['differs']) for r in rows), total=round(sum(d), 3), lo=None if lo is None else round(lo, 3), hi=None if hi is None else round(hi, 3), m=m)
        if cid.startswith('rollback.'):        # a promotion is undone on less evidence than it took to make it: 10 differing days, lower bound above zero
            e['status'] = 'ready' if e['n_diff'] >= pol['harm_diff_days'] and lo is not None and lo > 0 else 'collecting'
        elif e['n_diff'] >= pol['min_diff_days'] and lo is not None and lo > 0 and e['total'] >= pol['promote_pct']: e['status'] = 'ready'
        elif e['n_diff'] >= pol['harm_diff_days'] and hi is not None and hi < 0: e['status'] = 'harm'
        elif n >= pol['retire_days']: e['status'] = 'stale'
        else: e['status'] = 'collecting'
        out.append(e)
    if any(e['status'] == 'ready' for e in out):           # risk check (v5.2.33): a READY candidate must not raise the stressed hard-stop risk
        D = load_data(); cd = run_cf(D, champion_values(t))[0]
        for e in out:
            if e['status'] != 'ready' or e['id'] not in meta or e['id'].startswith('rollback.'): continue
            why, _, b = risk_check(t, D, cd, meta[e['id']]['values'])
            e['risk'] = b
            if why: e['status'] = 'risk-blocked'; e['risk_why'] = why
    return sorted(out, key=lambda e: (e['status'] != 'ready', -e['total'])), m_ever


def evidence_line(e):
    lo = 'n/a' if e['lo'] is None else f"{e['lo']:+.2f}"
    return f"  {e['id']:<26}{e['status']:<13}{e['n_days']:>4}d {e['n_diff']:>3} differed  total {e['total']:+7.2f}% of account  lower bound {lo:>6}  {'[rollback: governor only]' if e['id'].startswith('rollback.') else '' if e['promotable'] else '[idea: needs a rulebook change]'}"


def retire(t, evs):
    cv = current(t)['version']; done = []
    for e in evs:
        if e['status'] not in ('harm', 'stale'): continue
        verdict = 'rejected' if e['status'] == 'harm' else 'inconclusive'
        radd(kind='shadow', id=e['id'], champion_version=cv, idea=e['desc'], method='forward paper shadow on the saved bars of every close, paired against the champion',
             result=f"{e['n_days']} days, {e['n_diff']} differed, total {e['total']:+.2f}% of the account, bootstrap 90% interval upper bound {e['hi']:+.2f}, tracked candidates {e['m']}", verdict=verdict)
        ledger('retired', id=e['id'], verdict=verdict, total=e['total']); done.append(e)
    return done


# ------------------------------------------------------------------ risk as the account lives it (D4, v5.2.33)
SCENARIOS = [('as replayed', 1.0, 1.0), ('wins -40%', 0.6, 1.0), ('wins -40%, losses +25%', 0.6, 1.25)]     # the last one stands in for the live-vs-backtest gap


def risk_profile(daily, win=1.0, loss=1.0, days=250, B=4000, stop=15.0, seed='risk'):
    """Bootstrap one trading year from the daily account returns (each day as replayed, wins and losses scaled for the stress).
    Returns the chance of reaching the A1.13 hard stop (-15% from the high; the path stops there), the median and 5th-percentile
    year, and the median and 95th-percentile worst drawdown. Days, not trades, are resampled, so idle days count as they happen."""
    r = [x * win if x > 0 else x * loss for _, x in daily]
    if len(r) < 20: return None
    rng = random.Random(f"{seed}:{len(r)}:{win}:{loss}"); hits = 0; rets = []; dds = []
    for _ in range(B):
        eq = peak = 1.0; dd = 0.0
        for x in rng.choices(r, k=days):
            eq *= 1 + x / 100
            if eq > peak: peak = eq
            dn = (1 - eq / peak) * 100
            if dn > dd: dd = dn
            if dn >= stop: hits += 1; break
        rets.append((eq - 1) * 100); dds.append(dd)
    rets.sort(); dds.sort()
    return dict(p_stop=round(100 * hits / B, 2), median=round(rets[B // 2], 1), p5=round(rets[B // 20], 1), dd_med=round(dds[B // 2], 1), dd_p95=round(dds[int(B * 0.95)], 1), n=len(r))


def risk_line(name, rp):
    if not rp: return f"  {name:<26}too few days"
    return f"  {name:<26}P(-15% stop) {rp['p_stop']:5.1f}%   median year {rp['median']:+7.1f}%   bad year (5th pct) {rp['p5']:+7.1f}%   drawdown median {rp['dd_med']:4.1f}% (95th {rp['dd_p95']:4.1f}%)"


def risk_check(t, D, champ_daily, values):
    """READY also needs the candidate not to raise the stressed risk (third scenario) over the full dataset: P(stop) at most
    risk_pstop_slack points above the champion's, median worst drawdown at most risk_dd_slack points above. In-sample by nature,
    so it is a do-no-harm check on risk; the edge itself must come from the forward shadow evidence."""
    pol = policy(t); _, w, l = SCENARIOS[-1]
    a = risk_profile(champ_daily, w, l); b = risk_profile(run_cf(D, values)[0], w, l); why = []
    if a and b:
        if b['p_stop'] > a['p_stop'] + pol['risk_pstop_slack']: why.append(f"stressed P(stop) {b['p_stop']}% vs {a['p_stop']}%")
        if b['dd_med'] > a['dd_med'] + pol['risk_dd_slack']: why.append(f"stressed median drawdown {b['dd_med']}% vs {a['dd_med']}%")
    return why, a, b


def live_daily():
    """The real account's daily returns (acct_pct summed per day) on every trading day since launch, idle days as 0."""
    import health
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'archive', 'live_trades.csv')))); by = {}
    for r in rows: by[r['date']] = by.get(r['date'], 0.0) + float(r['acct_pct'] or 0)
    days = health.trading_days(health.LIVE_START, today().isoformat())
    return [(d, by.get(d, 0.0)) for d in days if d < today().isoformat() or d in by]


# ------------------------------------------------------------------ regime, attribution, defensive review (D4, v5.2.33)
def regime(D, values, window=20):
    """The champion's own trades on the most recent sessions of the dataset (it grows by one live session each close): FADE +2R reach
    rate and profit factor over the last `window` FADE trades, PULLBACK profit factor over the last `window`, against the whole dataset.
    Bands as the health tracker (C5): +2R reach > 40% / 30-40% / < 30%, PF > 1.5 / 1.0-1.5 / < 1.0. HOSTILE if any band is in the bottom."""
    daily, tr = run_cf(D, values)
    def pf_(x):
        g = sum(u for u in x if u > 0); l = -sum(u for u in x if u < 0); return round(g / l, 2) if l else None
    f = [x for x in tr if x[3] == 'FADE']; p = [x for x in tr if x[3] != 'FADE']; fw, pw = f[-window:], p[-window:]
    reach = lambda x: round(100 * sum(1 for y in x if y[4]) / len(x)) if x else None
    out = dict(window=window, fade_from=fw[0][0] if fw else None, fade_reach=reach(fw), fade_reach_all=reach(f), fade_pf=pf_([x[1] for x in fw]), fade_pf_all=pf_([x[1] for x in f]),
               pb_from=pw[0][0] if pw else None, pb_pf=pf_([x[1] for x in pw]), pb_pf_all=pf_([x[1] for x in p]))
    bad = []; warn = []
    for k, v, hi, lo in (('FADE +2R reach', out['fade_reach'], 40, 30), ('FADE PF', out['fade_pf'], 1.5, 1.0), ('PULLBACK PF', out['pb_pf'], 1.5, 1.0)):
        if v is None: continue
        if v < lo: bad.append(k)
        elif v <= hi: warn.append(k)
    # edge monitor (v5.2.34): the version in force's mean day over the last 40 sessions against the whole dataset, and the bootstrap
    # chance that the recent mean is above zero. INTACT: chance >= 90% and mean at least half the dataset's; FADING: chance below 70%; else THINNING.
    r = [x for _, x in daily[-40:]]; allm = sum(x for _, x in daily) / len(daily); rng = random.Random(f"edge:{len(daily)}")
    p = sum(sum(rng.choices(r, k=len(r))) > 0 for _ in range(2000)) / 2000; m = sum(r) / len(r)
    out.update(edge_from=daily[-40][0], edge_mean=round(m, 3), edge_all=round(allm, 3), edge_p=round(100 * p),
               edge='FADING' if p < 0.70 else 'INTACT' if p >= 0.90 and m >= allm / 2 else 'THINNING')
    if out['edge'] == 'FADING': bad.append('edge FADING')
    elif out['edge'] == 'THINNING': warn.append('edge THINNING')
    out['state'] = 'HOSTILE' if bad else 'THIN' if warn else 'NORMAL'; out['flags'] = bad + warn
    return out


def regime_line(g):
    return (f"  regime {g['state']}: edge {g['edge']} (last 40 sessions from {g['edge_from']}: {g['edge_mean']:+.3f}%/day vs dataset {g['edge_all']:+.3f}%, chance above zero {g['edge_p']}%); last {g['window']} model FADE trades (from {g['fade_from']}) reach +2R {g['fade_reach']}% (dataset {g['fade_reach_all']}%), PF {g['fade_pf']} (dataset {g['fade_pf_all']}); "
            f"last {g['window']} PULLBACK (from {g['pb_from']}) PF {g['pb_pf']} (dataset {g['pb_pf_all']})" + (f"  [{', '.join(g['flags'])}]" if g['flags'] else ''))


def attribution(since=None):
    """Live vs model per real trade, % of position: entry price (model entry vs real fill, whole position), hand close (a governor close,
    exclude_from_gap = yes: the whole gap), exit and path (the rest: exit fills, partial take-profits, stop timing). Plus model trades the
    account did not take (missed) and real trades the model did not have (extra)."""
    live = [r for r in csv.DictReader(open(os.path.join(ROOT, 'archive', 'live_trades.csv'))) if not since or r['date'] >= since]
    model = [r for r in csv.DictReader(open(PAPER_LOG))] if os.path.exists(PAPER_LOG) else []
    mk = {(r['day'], r['ticker']): r for r in model}; out = []
    for r in live:
        if not r.get('model_pct', '').strip(): out.append(dict(date=r['date'], ticker=r['ticker'], system=r['system'], kind='extra', real=float(r['pnl_pct_position']))); continue
        real, mod = float(r['pnl_pct_position']), float(r['model_pct']); gap = real - mod; m = mk.get((r['date'], r['ticker']))
        entry = (float(m['entry_px_leg']) - float(r['entry_px'])) / float(m['entry_px_leg']) * 100 if m and m.get('entry_px_leg') else None
        hand = r.get('exclude_from_gap', '').strip().lower().startswith('yes')
        out.append(dict(date=r['date'], ticker=r['ticker'], system=r['system'], kind='taken', real=real, model=mod, gap=gap, entry=entry,
                        hand=gap - (entry or 0.0) if hand else 0.0, path=0.0 if hand else gap - (entry or 0.0)))
    took = {(r['date'], r['ticker']) for r in live}; first = min([r['date'] for r in live] or ['9999'])
    for r in model:
        if (r['day'], r['ticker']) not in took and r['day'] >= max(first, since or ''): out.append(dict(date=r['day'], ticker=r['ticker'], system=r['system'], kind='missed', model=float(r['pct_leg'])))
    return sorted(out, key=lambda x: x['date'])


def attribution_text(rows):
    if not rows: return "  attribution: no live trades in the window"
    tk = [x for x in rows if x['kind'] == 'taken']; f = lambda v: 'n/a' if v is None else f"{v:+.2f}%"
    L = [f"  {x['date']} {x['system']:<9}{x['ticker']:<6}" + (f"real {x['real']:+.2f}% model {x['model']:+.2f}% gap {x['gap']:+.2f}% = entry {f(x['entry'])} + hand close {x['hand']:+.2f}% + exit/path {x['path']:+.2f}%" if x['kind'] == 'taken'
         else f"MISSED: model {x['model']:+.2f}% on the leg, no real trade" if x['kind'] == 'missed' else f"EXTRA: real {x['real']:+.2f}%, no model trade") for x in rows]
    if tk:
        s = lambda k: sum(x[k] or 0.0 for x in tk) / len(tk)
        L.append(f"  average per taken trade ({len(tk)}): gap {s('gap'):+.2f}% = entry {s('entry'):+.2f}% + hand close {s('hand'):+.2f}% + exit/path {s('path'):+.2f}%; "
                 f"missed {sum(x['kind'] == 'missed' for x in rows)}, extra {sum(x['kind'] == 'extra' for x in rows)}")
    return "\n".join(L)


def health_acts():
    """Today's (or the latest) row of archive/health_log.csv: the ACT measures the tracker found."""
    f = os.path.join(ROOT, 'archive', 'health_log.csv')
    if not os.path.exists(f): return None, []
    r = list(csv.DictReader(open(f)))[-1]; acts = [k for k, v in r.items() if k.endswith('_status') and v.strip() == 'ACT']
    return r['date'], acts


def defensive(t, D, window=60):
    """Defensive options judged by risk, not %/day: each lower risk.pct and size.cap_pct step and the defensive ideas (one loss ends the
    day, dropping each FADE proxy). Stop risk = the stressed scenario on the last `window` sessions; cost = the change in mean %/day over
    the whole dataset. Returns the version in force's profile, the rows and the recommendation (v5.2.35): when the version in force's
    stressed chance of the hard stop is above policy risk_target_pstop, the numeric option with the best whole-dataset %/day among those
    that bring it to the target or below while keeping at least (1 - risk_cost_max) of the %/day. Ideas are shown, never recommended."""
    pol = policy(t); base = champion_values(t); _, w, l = SCENARIOS[-1]; rows = []
    def prof(v):
        d = run_cf(D, v)[0]; return risk_profile(d[-window:], w, l, seed='def'), stats(d, [])['mean_day']
    b, bm = prof(base); opts = []
    for var in ('risk.pct', 'size.cap_pct'):
        sp = t['space'][var]; x = base[var]
        while x - sp['step'] >= sp['lo'] - 1e-9:
            x = round(x - sp['step'], 4); v = dict(base); v[var] = x; opts.append((f"{var} {base[var]:g} -> {x:g}", v, dict(variable=var, old=base[var], new=x)))
    for i in ideas():
        if i['id'] == 'risk.one_loss_ends_day' or i['id'].startswith('drop.fade.'): v = dict(base); v.update(i['values']); opts.append((i['id'], v, None))
    for name, v, num in opts:
        rp, m = prof(v)
        if rp: rows.append(dict(name=name, rp=rp, mean=m, num=num, ok=bool(num) and rp['p_stop'] <= pol['risk_target_pstop'] and m >= (1 - pol['risk_cost_max']) * bm))
    rec = None
    if b and b['p_stop'] > pol['risk_target_pstop']:
        ok = [r for r in rows if r['ok']]; rec = max(ok, key=lambda r: (r['mean'], -r['rp']['p_stop'])) if ok else None
    return dict(b=b, mean=bm, window=window, target=pol['risk_target_pstop']), rows, rec


def defensive_text(head, rows, rec):
    L = [risk_line('version in force', head['b']) + f"   whole dataset {head['mean']:+.3f}%/day"]
    for r in rows: L.append(risk_line(r['name'], r['rp']) + f"   whole dataset {r['mean']:+.3f}%/day" + ('   <- recommended' if rec is r else '   <- meets the target' if r['ok'] else ''))
    return "\n".join(L)


# ------------------------------------------------------------------ proposer prompt
def context(t, evs):
    return dict(objective=t.get('goals'), progress=goal_progress(), note='Paper model that mirrors a LIVE account. Evidence is forward shadow only.', current_version=current(t),
                recent_model_trades=model_trades()[-25:], ready=[e for e in evs if e['status'] == 'ready'], leaderboard=evs[:10])


def prompt_text(ctx):
    return ("You propose at most ONE change to a live-money trading model. The governor approves or rejects it. Choose ONLY the id of a READY candidate whose promotable is true "
            "(a numeric tunable), or 'hold'. Prefer hold unless the evidence is clear and the change fits the recent trades. Ideas (promotable false) are reported to the governor, "
            "never proposed here. Do not invent parameters. All sizing is a percentage of the account, never a dollar amount, and size is never raised. "
            "Reply with one JSON object: {\"choice\": \"<id or hold>\", \"rationale\": \"<two sentences max>\"}.\n\n" + json.dumps(ctx, indent=1))


# ------------------------------------------------------------------ commands
def cmd_menu(a):
    t = tun(); D = load_data(); base, rows = menu(D, current(t)['values'], t['space'], a.risk_off, t.get('goals'))
    os.makedirs(IDIR, exist_ok=True); json.dump(dict(base=base, rows=rows), open(os.path.join(IDIR, 'menu.json'), 'w'), indent=1)
    b = base
    print(f"baseline v{current(t)['version']}: full {b['full']}\n  in-sample {b['ins']}\n  out-of-sample {b['oos']}")
    for r in rows: print(f"  {r['id']:<24}{r['old']:>7} -> {r['new']:<7} d%/day ins {r['delta']['ins']:+.3f} oos {r['delta']['oos']:+.3f} full {r['delta']['full']:+.3f}  dd {r['stats']['full']['dd']:.1f}  trades {r['stats']['full']['trades']}  {'PASS' if r['passes'] else 'fail: ' + ', '.join(r['fails'])}")


def cmd_reject(a):
    p = pending()
    if not p: sys.exit('nothing pending')
    os.remove(PENDING); ledger('rejected', id=p['id'], note=a.note); print('rejected')


def cmd_promote(a):
    t = tun(); ch = challenger(t)
    if not ch or ch['status'] != 'ready': sys.exit('no challenger has passed its trial')
    future_trading_day(a.effective)
    if ch['base_version'] != current(t)['version']: sys.exit('stale: the version in force changed since the trial started')
    n = append_version(t, 'change', a.effective, ch['values'], base_version=ch['base_version'], proposal=ch['id'], note=a.note, **({'defensive': True} if ch.get('defensive') else {}))
    t['challenger'] = None; save_tun(t); ledger('promoted', id=ch['id'], version=n, effective_from=a.effective, note=a.note)
    print(f"PROMOTED: v{n} ({ch['variable']} {ch['old']} -> {ch['new']}) live from {a.effective}. Bump the RULEBOOK version, record it in the commit, commit tunables.json + archive/improve/.")


def cmd_discard(a):
    t = tun(); ch = challenger(t)
    if not ch: sys.exit('no challenger')
    t['challenger'] = None; save_tun(t); ledger('discarded', reason='governor', id=ch['id'], note=a.note); print('challenger discarded; the live account was never changed')


def cmd_rollback(a):
    t = tun(); c = current(t)
    if c['kind'] != 'change': sys.exit('the version in force is not a promoted change')
    future_trading_day(a.effective)
    n = append_version(t, 'rollback', a.effective, version_values(t, c['base_version']), base_version=c['version'], note=f"rollback of v{c['version']}")
    save_tun(t); ledger('rollback', from_version=c['version'], version=n, effective_from=a.effective)
    print(f"ROLLBACK: v{n} restores v{c['base_version']} values from {a.effective}. Commit tools/live/tunables.json and archive/improve/.")


# ------------------------------------------------------------------ governor cycle (v5.2.36, governor instruction 2026-10-28)
# Per system (FADE and PULLBACK are treated as completely separate systems):
#   1. wait for 5 trades of the system, then look at the goals of the whole system (the real account since launch);
#   2. goal met -> no change, wait for the next 5; goal not met -> the session picks ONE change for that system from its last 5 trades;
#   3. paper trade the changed system in parallel with the live one for 10 trades of the system (no orders);
#   4. better -> PUSH REQUEST to the governor; not different -> 5 more trades, still not different -> scrap and pick the next change;
#      worse -> scrap and pick the next change. Continuous.
CYCLE = os.path.join(IDIR, 'cycle.json'); TRIAL_LOG = os.path.join(IDIR, 'trial_log.csv')
SYSN = {'fade': 'FADE', 'pb': 'PB'}; WAIT_TRADES, TRIAL_TRADES, EXTEND_TRADES = 5, 10, 5
DIFF_PCT = 0.20                 # a trial result counts as different when the paired total differs by at least 0.20% of the account
TRIAL_HDR = ['day', 'system', 'id', 'cver', 'live_pct', 'new_pct', 'live_trades', 'new_trades', 'differs']


def cycle():
    c = json.load(open(CYCLE)) if os.path.exists(CYCLE) else {}
    for k in SYSN: c.setdefault(k, dict(state='waiting', since='2026-10-16'))
    return c


def save_cycle(c):
    os.makedirs(IDIR, exist_ok=True); json.dump(c, open(CYCLE, 'w'), indent=1); open(CYCLE, 'a').write('\n')


def isolate(values, sysk):
    """The system on its own: the other system's tickers are switched off, so each system is judged as if it were the only one."""
    v = dict(values)
    if sysk == 'fade': v['x.drop_pb'] = list(paper.PB_LIST); v['x.add_pb'] = []
    else: v['x.drop_fade'] = list(paper.FADE_ROWS); v['x.add_fade'] = []
    return v


def sys_of(c):
    i = c['id']
    if i.startswith(('risk.', 'size.', 'rollback.')): return None
    if c['kind'] == 'tunable': return 'fade' if c['variable'].startswith('fade.') else 'pb' if c['variable'].startswith('pb.') else None
    return 'fade' if i.startswith(('drop.fade.', 'fade.', 'add.fade.')) else 'pb' if i.startswith(('drop.pb.', 'pb.', 'add.pb.')) else None


def scrapped(t, sysk):
    cv = current(t)['version']
    return {e['id'] for e in rledger() if e.get('kind') == 'trial' and e.get('system') == sysk and e.get('champion_version') == cv and e.get('verdict') in ('scrapped', 'declined')}


SHARED = ('risk.pct', 'size.cap_pct')       # shared by both systems: trialled in each cycle, pushed only when both cycles ask for it (governor 2026-10-28)


def sys_candidates(t, sysk):
    base = champion_values(t); out = []
    for var in SHARED:
        sp = t['space'][var]; new = round(max(sp['lo'], base[var] - sp['step']), 4)
        if new != base[var]:
            v = dict(base); v[var] = new
            out.append(dict(id=f"{var}-1", kind='tunable', desc=f"{var} {base[var]:g} -> {new:g} (shared by both systems: needs a push request from both cycles)", values=v, promotable=True, variable=var, old=base[var], new=new))
    out = [c for c in out if c['id'] not in scrapped(t, sysk)]
    for c in out: c['changes'] = {c['variable']: c['new']}
    for c in candidates(t, ()):
        if sys_of(c) != sysk or c['id'] in scrapped(t, sysk): continue
        c['changes'] = {k: v for k, v in c['values'].items() if base.get(k) != v}
        if c['changes']: out.append(c)            # a candidate already in force is not offered
    return out


def sys_trades(sysk, since):
    return [x for x in model_trades() if x['system'] == SYSN[sysk] and x['day'] >= since]


def goal_check(t):
    """The goals of the whole system, on the real account since launch (idle trading days count as 0)."""
    g = t.get('goals') or {}; lv = live_daily(); r = [x for _, x in lv]
    eq = peak = 1.0; dd = 0.0
    for x in r: eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, (1 - eq / peak) * 100)
    mean = sum(r) / len(r) if r else 0.0
    met = bool(r) and mean >= g.get('target_daily_pct', 0.4) and dd <= g.get('max_drawdown_pct', 15)
    return dict(days=len(r), mean=round(mean, 3), target=g.get('target_daily_pct'), dd=round(dd, 2), dd_limit=g.get('max_drawdown_pct'), total=round((eq - 1) * 100, 2), met=met)


def goal_text(gc):
    return (f"goals (whole system, real account since launch, {gc['days']} trading days): {gc['mean']:+.3f}%/day vs target {gc['target']}%, "
            f"drawdown {gc['dd']}% vs limit {gc['dd_limit']}%, total {gc['total']:+.2f}% -> {'MET' if gc['met'] else 'NOT MET'}")


def trial_rows(sysk=None, tid=None):
    if not os.path.exists(TRIAL_LOG): return []
    return [r for r in csv.DictReader(open(TRIAL_LOG)) if (sysk is None or r['system'] == sysk) and (tid is None or r['id'] == tid)]


def record_trials(t, c, day, today_, prev):
    """Each close: the live system and the changed system, each on its own, on the day's real bars (no orders). Idempotent per day."""
    have = {(r['day'], r['system'], r['id']) for r in trial_rows()}; new = []
    for sysk, st_ in c.items():
        if st_['state'] != 'trial' or day < st_['start'] or (day, sysk, st_['id']) in have: continue
        base = champion_values(t); lp, ls = run_day(day, today_, prev, isolate(base, sysk)); np_, ns = run_day(day, today_, prev, isolate({**base, **st_['changes']}, sysk))
        n_l = sum(1 for x in ls if x[3] or x[4]); n_n = sum(1 for x in ns if x[3] or x[4])
        new.append([day, sysk, st_['id'], current(t)['version'], round(lp, 6), round(np_, 6), n_l, n_n, int(ls != ns)])
    if new:
        fresh = not os.path.exists(TRIAL_LOG); os.makedirs(IDIR, exist_ok=True)
        with open(TRIAL_LOG, 'a', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            if fresh: w.writerow(TRIAL_HDR)
            w.writerows(new)
    return new


def trial_score(st_, sysk):
    rows = trial_rows(sysk, st_['id']); rows = [r for r in rows if r['day'] >= st_['start']]
    live = sum(float(r['live_pct']) for r in rows); new = sum(float(r['new_pct']) for r in rows)
    return dict(days=len(rows), trades=sum(int(r['live_trades']) for r in rows), new_trades=sum(int(r['new_trades']) for r in rows), diff_days=sum(int(r['differs']) for r in rows),
                live=round(live, 3), new=round(new, 3), delta=round(new - live, 3))


def scrap(c, sysk, t, verdict, sc):
    st_ = c[sysk]
    radd(kind='trial', system=sysk, id=st_['id'], champion_version=current(t)['version'], idea=st_['desc'], verdict=verdict, why=st_.get('why', ''),
         method=f"parallel paper trial from {st_['start']}, {SYSN[sysk]} on its own, live version vs changed version on the same real bars",
         result=f"{sc['trades']} live trades ({sc['new_trades']} changed), {sc['diff_days']} days differed, live {sc['live']:+.2f}% vs changed {sc['new']:+.2f}% of account (delta {sc['delta']:+.2f})")
    ledger('trial_' + verdict, system=sysk, id=st_['id'], **sc); c[sysk] = dict(state='choose', since=st_.get('since', today().isoformat()), reason=f"{st_['id']} {verdict}")


def advance(t, c):
    """Move each system's cycle forward and return the report lines (the top lines go to the governor)."""
    top, lines = [], []
    for sysk, st_ in c.items():
        name = 'FADE' if sysk == 'fade' else 'PULLBACK'
        if st_['state'] == 'waiting':
            n = len(sys_trades(sysk, st_['since']))
            if n < WAIT_TRADES: lines.append(f"  {name}: waiting, {n} of {WAIT_TRADES} trades since {st_['since']}"); continue
            gc = goal_check(t); lines.append(f"  {name}: {WAIT_TRADES} trades reached; {goal_text(gc)}")
            if gc['met']:
                c[sysk] = dict(state='waiting', since=next_trading_day(today()).isoformat()); ledger('goal_met', system=sysk, **gc)
                lines.append(f"  {name}: goal met, no change; waiting for the next {WAIT_TRADES} trades"); continue
            c[sysk] = dict(state='choose', since=st_['since'], reason='goal not met'); ledger('change_due', system=sysk, **gc)
        if c[sysk]['state'] == 'choose':
            top.append(f"CHANGE DUE ({name}): {c[sysk].get('reason', '')}. Pick one change from the last {WAIT_TRADES} {name} trades: "
                       f"`improve.py review {sysk}`, then `improve.py trial {sysk} <id> \"why\"` (paper only; starts the next trading day)")
        elif st_['state'] == 'trial':
            sc = trial_score(st_, sysk); need = TRIAL_TRADES + (EXTEND_TRADES if st_.get('extended') else 0)
            lines.append(f"  {name}: paper trial of {st_['id']} ({st_['desc']}) since {st_['start']}: {sc['trades']} of {need} trades, {sc['diff_days']} days differed, "
                         f"live {sc['live']:+.2f}% vs changed {sc['new']:+.2f}% of account (delta {sc['delta']:+.2f})")
            if sc['trades'] < need: continue
            if sc['delta'] >= DIFF_PCT:
                c[sysk] = dict(st_, state='push', result=sc); ledger('push_request', system=sysk, id=st_['id'], **sc)
            elif sc['delta'] <= -DIFF_PCT:
                scrap(c, sysk, t, 'scrapped', sc); top.append(f"SCRAPPED ({name}): {st_['id']} was worse ({sc['delta']:+.2f}% of account over {sc['trades']} trades); pick the next change")
            elif not st_.get('extended'):
                c[sysk] = dict(st_, extended=True); ledger('trial_extended', system=sysk, id=st_['id'], **sc)
                lines.append(f"  {name}: not different after {sc['trades']} trades (delta {sc['delta']:+.2f}, threshold {DIFF_PCT}): {EXTEND_TRADES} more trades")
            else:
                scrap(c, sysk, t, 'scrapped', sc); top.append(f"SCRAPPED ({name}): {st_['id']} still not different after {sc['trades']} trades; pick the next change")
        if c[sysk]['state'] == 'push':
            s2 = c[sysk]; r = s2['result']
            sh = set(s2['changes']) & set(SHARED); o = c['pb' if sysk == 'fade' else 'fade']
            if sh and not (o['state'] == 'push' and o.get('changes') == s2['changes']):
                lines.append(f"  {name}: {s2['id']} passed its trial; it is shared by both systems, so the push request waits until the other cycle passes the same change"); continue
            top.append(f"PUSH REQUEST ({name}): {s2['id']} ({s2['desc']}) beat the live version in the paper trial: {r['trades']} trades, changed {r['new']:+.2f}% vs live {r['live']:+.2f}% of account "
                       f"(delta {r['delta']:+.2f}). Ask the governor: push it live (`improve.py push {sysk} --effective <next trading day> --note \"...\"`) or decline (`improve.py decline {sysk}`)")
    return top, lines


def cmd_tick(a):
    t = tun(); c = cycle()
    if a.dumps:
        day, today_, prev = day_inputs(a.dumps); new = record_trials(t, c, day, today_, prev)
        print(f"  paper trials: {day}, {len(new)} system(s) recorded (no orders)" if new else f"  paper trials: none running or {day} already recorded")
    else: print("  no dumps passed: paper trials not recorded today")
    top, lines = advance(t, c); save_cycle(c)
    for x in top: print(x)
    for x in lines: print(x)
    try:                                                    # information only (v5.2.33-35): edge, regime and stop risk; they file nothing
        D = load_data(); g = regime(D, champion_values(t)); print(regime_line(g))
        head, rows, rec = defensive(t, D); bp = head['b']
        print(f"  stop risk: stressed chance of the -15% stop {bp['p_stop'] if bp else 'n/a'}% on the last {head['window']} sessions (information; risk.pct is shared by both systems)")
        if today().weekday() == 4: print("  live vs model attribution, this week:\n" + attribution_text(attribution((today() - timedelta(days=6)).isoformat())))
    except Exception as x: print(f"  regime step failed: {x!r} (information only)")
    if pending(): print("  legacy proposal pending (outside the cycle):", json.dumps({k: pending()[k] for k in ('id', 'variable', 'old', 'new')}))


def cmd_review(a):
    """What the session reads before picking a change: the system's last 5 trades, the goals, and every change available for that system
    with its effect, on its own, on the days of those trades and on the whole dataset (in-sample guide only; the paper trial decides)."""
    t = tun(); c = cycle(); sysk = a.system; name = 'FADE' if sysk == 'fade' else 'PULLBACK'
    last = [x for x in model_trades() if x['system'] == SYSN[sysk]][-WAIT_TRADES:]
    print(f"{name} cycle: {c[sysk]['state']}; {goal_text(goal_check(t))}\nlast {len(last)} {name} trades (model record):")
    for x in last: print(f"  {x['day']} {x['ticker']:<6}{x['reason']:<16}{x['pct_leg']:+.2f}% on the leg  {x['acct_pct']:+.2f}% of account")
    D = load_data(); base = isolate(champion_values(t), sysk); bd = dict(run_cf(D, base)[0]); days = {x['day'] for x in last}
    print(f"changes available for {name} (not yet scrapped under v{current(t)['version']}), effect on its own vs the live version:")
    rows = []
    for k in sys_candidates(t, sysk):
        d = dict(run_cf(D, isolate({**champion_values(t), **k['changes']}, sysk))[0])
        rows.append((sum(d[x] - bd[x] for x in d if x in days), sum(d[x] - bd[x] for x in d), sum(1 for x in d if abs(d[x] - bd[x]) > 1e-9), k))
    for l5, al, nd, k in sorted(rows, key=lambda r: (-r[0], -r[1])):
        print(f"  {k['id']:<26}last-5 days {l5:+6.2f}%  whole dataset {al:+7.2f}% ({nd} days differ)  {k['desc'][:80]}")


def cmd_trial(a):
    t = tun(); c = cycle(); sysk = a.system
    if c[sysk]['state'] != 'choose': sys.exit(f"{sysk} is {c[sysk]['state']}: a change is picked only when the cycle says CHANGE DUE")
    k = next((x for x in sys_candidates(t, sysk) if x['id'] == a.id), None)
    if not k: sys.exit(f"{a.id} is not an available {sysk} change (see improve.py review {sysk})")
    start = next_trading_day(today()).isoformat()
    c[sysk] = dict(state='trial', id=k['id'], desc=k['desc'], changes=k['changes'], why=a.why, start=start, since=c[sysk].get('since'), base_version=current(t)['version'])
    save_cycle(c); ledger('trial_start', system=sysk, id=k['id'], changes=k['changes'], why=a.why, start=start)
    print(f"PAPER TRIAL ({sysk}): {k['id']} ({k['desc']}) runs in parallel with the live system from {start} for {TRIAL_TRADES} {SYSN[sysk]} trades. No orders.")


def cmd_push(a):
    """Governor only: put a trial winner live from a future trading day, then the system waits for its next 5 trades."""
    t = tun(); c = cycle(); sysk = a.system; st_ = c[sysk]
    if st_['state'] != 'push': sys.exit(f"{sysk} has no push request")
    future_trading_day(a.effective)
    other = 'pb' if sysk == 'fade' else 'fade'
    if set(st_['changes']) & set(SHARED):
        o = c[other]
        if o['state'] != 'push' or o.get('changes') != st_['changes']: sys.exit(f"{st_['id']} is shared by both systems: it is pushed only when the {other} cycle also has a push request for the same change")
    vals = {**current(t)['values'], **st_['changes']}
    n = append_version(t, 'change', a.effective, vals, base_version=current(t)['version'], proposal=f"trial.{sysk}.{st_['id']}", note=a.note)
    save_tun(t); radd(kind='trial', system=sysk, id=st_['id'], champion_version=st_['base_version'], idea=st_['desc'], verdict='pushed', why=st_.get('why', ''),
                      method='parallel paper trial', result=json.dumps(st_['result']))
    ledger('pushed', system=sysk, id=st_['id'], version=n, effective_from=a.effective, note=a.note); c[sysk] = dict(state='waiting', since=a.effective)
    if set(st_['changes']) & set(SHARED): c[other] = dict(state='waiting', since=a.effective)      # one push covers both cycles
    save_cycle(c)
    print(f"PUSHED: v{n} ({st_['id']}) live from {a.effective}. Bump the RULEBOOK version, record it in the commit, commit tunables.json + archive/improve/.")


def cmd_decline(a):
    """Governor only: decline a push request; the change is scrapped and the next change is picked."""
    t = tun(); c = cycle(); sysk = a.system
    if c[sysk]['state'] != 'push': sys.exit(f"{sysk} has no push request")
    sc = c[sysk]['result']; scrap(c, sysk, t, 'declined', sc); save_cycle(c); print(f"declined; {sysk} needs its next change (CHANGE DUE)")


def cmd_evidence(a):
    t = tun(); evs, m = evidence(t); print(f"champion v{current(t)['version']}; {len(evs)} active candidates, {m} ever tracked; thresholds {json.dumps({k: policy(t)[k] for k in ('shadow_from', 'min_diff_days', 'alpha', 'harm_diff_days', 'retire_days', 'promote_pct')})}")
    for e in evs: print(evidence_line(e))
    if not evs: print("  no shadow rows yet (the first rows arrive at the first close on or after shadow_from)")


def cmd_prompt(a):
    t = tun(); evs, _ = evidence(t); print(prompt_text(context(t, evs)))


def cmd_submit(a):
    t = tun()
    if pending(): sys.exit('a proposal is already pending')
    evs, _ = evidence(t); row = next((e for e in evs if e['id'] == a.choice), None); meta = next((c for c in candidates(t) if c['id'] == a.choice), None)
    if a.choice == 'hold' or row is None:
        if a.choice != 'hold': sys.exit(f"{a.choice} is not an active candidate")
        ledger('hold', rationale=a.why, source='session'); print(f"HOLD: {a.why}"); return
    if row['status'] != 'ready': sys.exit(f"{a.choice} is not READY ({row['status']})")
    if not meta['promotable']: sys.exit(f"{a.choice} is an idea: it needs a rulebook change (D3), the loop cannot propose it")
    p = dict(id=f"p{len(ledger()) + 1}", created=datetime.now(ET).isoformat(timespec='seconds'), source='session', rationale=a.why, base_version=current(t)['version'],
             variable=meta['variable'], old=meta['old'], new=meta['new'], values=meta['values'], evidence=row)
    os.makedirs(IDIR, exist_ok=True); json.dump(p, open(PENDING, 'w'), indent=1); ledger('proposal', **{k: p[k] for k in ('id', 'variable', 'old', 'new', 'source', 'rationale')})
    print(f"PROPOSAL {p['id']}: {p['variable']} {p['old']} -> {p['new']}. Forward shadow: {row['n_days']} days, {row['n_diff']} differed, total {row['total']:+.2f}% of account, lower bound {row['lo']:+.2f}. "
          f"Waiting for the governor: improve.py approve --note \"...\"")


def cmd_approve(a):
    p = pending(); t = tun()
    if not p: sys.exit('nothing pending')
    if challenger(t): sys.exit('a challenger is already approved: one at a time')
    if p['base_version'] != current(t)['version']: sys.exit('the proposal is stale (the version in force changed): reject it and propose again')
    if p.get('kind') == 'defensive': row = p['evidence']      # judged on risk by the defensive review, not on forward shadow
    else:
        evs, _ = evidence(t); row = next((e for e in evs if e['id'] == p['evidence']['id']), None)
        if not row or row['status'] != 'ready': sys.exit('the evidence no longer meets the gate: reject the proposal')
    t['challenger'] = dict(defensive=p.get('kind') == 'defensive', id=p['evidence']['id'], variable=p['variable'], old=p['old'], new=p['new'], values=p['values'], base_version=p['base_version'], start=today().isoformat(), status='ready', note=a.note, evidence=row)
    save_tun(t); os.remove(PENDING); ledger('approved', id=p['id'], note=a.note)
    print(f"APPROVED: {p['variable']} {p['old']} -> {p['new']} is ready to promote (its evidence is forward shadow). The live account and the paper model stay on v{p['base_version']} until: improve.py promote --effective <future trading day> --note \"...\"")


def cmd_research(a):
    L = [e for e in rledger() if not a.verdict or e.get('verdict') == a.verdict]
    print(f"research ledger: {len(L)} entries" + (f" with verdict {a.verdict}" if a.verdict else ""))
    for e in L: print(f"  {e.get('date', '?')} {e['id']:<28}{e.get('verdict', '?'):<14}{e['idea'][:90]}\n      result: {e.get('result', '')[:200]}")


def cmd_research_add(a):
    if any(e['id'] == a.id for e in rledger()): sys.exit(f"{a.id} is already in the ledger")
    radd(kind='study', id=a.id, idea=a.idea, method=a.method, result=a.result, verdict=a.verdict); print('added', a.id)


def cmd_shadow_replay(a):
    """Dev/backfill: shadow-run dataset sessions with the current rules (lock and cut on, no FADE on Fridays), as the menu does."""
    t = tun(); D = load_data(); saved = (paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM)
    paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM = '0000-00-00', '0000-00-00'; n = 0
    try:
        for i in range(1, len(D.days)):
            d, pd = D.days[i], D.days[i - 1]
            if not (a.frm <= d <= a.to): continue
            tod = {s: D.bars[s][d][:48] for s in WANT() if d in D.bars.get(s, {})}; prv = {s: D.bars[s][pd] for s in WANT() if pd in D.bars.get(s, {})}
            n += record_all(t, d, tod, prv, a.force)
    finally:
        paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM = saved
    print(f"replayed {a.frm}..{a.to}: {n} rows -> {SHADOW}")


def sym_stats(D, sym):
    """Liquidity and data coverage of a symbol from the dataset: sessions, median 5-minute bar dollar volume, share of empty bars, median bar range %."""
    days = D.bars.get(sym, {})
    if not days: return None
    dv = [b[3] * b[4] for bars in days.values() for b in bars]; rg = [(b[1] - b[2]) / b[3] * 100 for bars in days.values() for b in bars if b[3] and b[4]]
    return dict(sessions=len(days), median_bar_usd=round(st.median(dv)), empty_bar_share=round(sum(1 for x in dv if x == 0) / len(dv), 3), median_range_pct=round(st.median(rg), 3) if rg else None)


def cmd_screen(a):
    D = load_data(); traded = set(paper.EXPECTED); names = a.symbols or sorted(D.bars)
    rows = [(s, sym_stats(D, s)) for s in names if s in D.bars and (a.symbols or s not in traded or a.traded)]
    rows = sorted([r for r in rows if r[1]], key=lambda r: -r[1]['median_bar_usd'])
    print(f"{'symbol':<7}{'sessions':>9}{'median $/bar':>14}{'empty bars':>12}{'bar range %':>13}   pass (>= {a.min_sessions} sessions and >= ${a.min_usd:,.0f} a bar)")
    for s, x in rows[:a.top or None]:
        ok = x['sessions'] >= a.min_sessions and x['median_bar_usd'] >= a.min_usd and x['empty_bar_share'] <= 0.10
        print(f"{s:<7}{x['sessions']:>9}{x['median_bar_usd']:>14,}{x['empty_bar_share']:>12.1%}{x['median_range_pct']:>13.3f}   {'yes' if ok else 'no'}")


def cmd_watch_add(a):
    """Put a ticker or proxy on trial (shadow only; it never trades). A session may do this; putting it on the traded lists is a governor rulebook change (D3)."""
    W = watchlist(); D = load_data(); syms = [a.proxy, a.bull, a.bear] if a.type == 'fade' else [a.leg]
    if a.type == 'fade' and not all([a.proxy, a.bull, a.bear, a.lev_bull, a.lev_bear]): sys.exit('fade needs --proxy --bull --bear --lev-bull --lev-bear')
    if a.type == 'pb' and not a.leg: sys.exit('pb needs --leg')
    cid = f"add.fade.{a.proxy}" if a.type == 'fade' else f"add.pb.{a.leg}"
    if any((f"add.fade.{w['proxy']}" if w['type'] == 'fade' else f"add.pb.{w['leg']}") == cid for w in W): sys.exit(f"{cid} is already on the watchlist")
    if a.type == 'fade' and a.proxy in paper.FADE_ROWS or a.type == 'pb' and a.leg in paper.PB_LIST: sys.exit('already traded')
    stt = {s: sym_stats(D, s) for s in syms}; bad = []
    for s, x in stt.items():
        if not x: bad.append(f"{s}: no bars in the dataset (fetch its history first)")
        else:
            if x['sessions'] < a.min_sessions: bad.append(f"{s}: only {x['sessions']} sessions")
            if s != a.proxy and x['median_bar_usd'] < a.min_usd: bad.append(f"{s}: median bar ${x['median_bar_usd']:,} is below ${a.min_usd:,.0f}")
            if x['empty_bar_share'] > 0.10: bad.append(f"{s}: {x['empty_bar_share']:.0%} of its bars are empty")
    if bad and not a.force: sys.exit('screen failed: ' + '; '.join(bad))
    e = dict(id=cid, type=a.type, added=today().isoformat(), why=a.why, screen=stt)
    e.update(dict(proxy=a.proxy, bull=a.bull, bear=a.bear, lev_bull=a.lev_bull, lev_bear=a.lev_bear) if a.type == 'fade' else dict(leg=a.leg))
    W.append(e); json.dump(W, open(WATCH, 'w'), indent=1); open(WATCH, 'a').write('\n')
    radd(kind='watch', id=cid, idea=a.why or f"{cid} on trial", method='liquidity and data screen, then forward paper shadow on every close', result=json.dumps(stt), verdict='shadowing')
    print(f"{cid} is on the watchlist (shadow only). Fetch its bars with the 13:30 research group; evidence starts at the next close.")


def cmd_add_checklist(a):
    w = next((w for w in watchlist() if (f"add.fade.{w['proxy']}" if w['type'] == 'fade' else f"add.pb.{w['leg']}") == a.id), None)
    if not w: sys.exit(f"{a.id} is not on the watchlist")
    sym = [w['proxy'], w['bull'], w['bear']] if w['type'] == 'fade' else [w['leg']]
    print(f"Adding {a.id} to the traded lists is a rulebook change (D3). Only on the governor's instruction. Checklist:\n"
          f"  1. get_equity_tradability and a live quote for {', '.join(sym)}: tradable, not restricted, spread well under 0.10% at 10:00.\n"
          f"  2. A1.7 spread care and the thin-ticker list (B1) if its median bar is under $150k; A1.9 earnings skip if it is a single-stock fund (get_earnings_calendar).\n"
          f"  3. paper.py: add {'the row to FADE_ROWS (proxy, bull, bear, leverages) and to EXPECTED' if w['type'] == 'fade' else 'the leg to PB_LIST and PB_PROXY (the RVOL proxy) and to EXPECTED'}; fetch_status scripts follow automatically.\n"
          f"  4. RULEBOOK: B{'2' if w['type'] == 'fade' else '3'} list and B1, C1.2 fetch groups (at most 10 symbols per call; add a group if needed), A1.9 if relevant, version bump, change-log line.\n"
          f"  5. Neutrality: paper.simulate with the new row switched on equals the shadow result; remove the id from watchlist.json and record the adoption in research_ledger.json.\n"
          f"  6. Republish the rulebook artifact (D3 item 5). Real orders for the new ticker start on the next trading day after the commit.")


def cmd_prune(a):
    """Park candidates that the whole dataset already rules out, so the forward gate is not diluted (Bonferroni counts every tracked
    candidate): the in-sample 80% bootstrap interval of the total difference is entirely below zero, or the candidate never differed in
    any session. Parked ones are written to the research ledger (kind prior, verdict parked) for the version in force; a new version
    re-admits them. Reads the dataset only; changes no rule, order or tunable."""
    t = tun(); D = load_data(); cv = current(t)['version']; cd = dict(run_cf(D, champion_values(t))[0]); parked = []
    have = {e['id'] for e in rledger() if e.get('kind') == 'prior' and e.get('champion_version') == cv}
    for c in candidates(t, retired_ids(t)):
        if c['id'].startswith('rollback.') or c['id'] in have: continue
        d = [x - cd[day] for day, x in run_cf(D, c['values'])[0]]; nd = sum(abs(v) > 1e-9 for v in d)
        rng = random.Random(c['id']); sums = sorted(sum(rng.choices(d, k=len(d))) for _ in range(2000)); hi = sums[1800]
        why = 'never differed' if nd == 0 else 'ruled out in-sample' if hi < 0 else None
        print(f"  {c['id']:<26}total {sum(d):+7.2f}%  80% upper {hi:+6.2f}  differing days {nd:3d}  {'PARK: ' + why if why else 'keep'}")
        if why and not a.dry: parked.append(c['id']); radd(kind='prior', id=c['id'], champion_version=cv, idea=c['desc'], verdict='parked',
                                                          method=f'in-sample screen on {len(d)} dataset sessions (base + live), paired bootstrap of daily differences',
                                                          result=f"total {sum(d):+.2f}% of the account, 80% interval upper bound {hi:+.2f}, {nd} differing sessions: {why}")
    print(f"parked {len(parked)}" + (' (dry run)' if a.dry else '') + "; the rest stay on the forward shadow")


def cmd_risk(a):
    t = tun(); D = load_data(); daily = run_cf(D, champion_values(t))[0]
    print(f"risk of the version in force v{current(t)['version']}: one trading year (250 days) bootstrapped from {len(daily)} replayed sessions, 4,000 paths, -15% hard stop ends a path")
    for name, w, l in SCENARIOS: print(risk_line(name, risk_profile(daily, w, l)))
    if a.id:
        c = next((c for c in candidates(t) if c['id'] == a.id), None)
        if not c: sys.exit(f"{a.id} is not a candidate")
        cd = run_cf(D, c['values'])[0]; print(f"candidate {a.id} ({c['desc']}):")
        for name, w, l in SCENARIOS: print(risk_line(name, risk_profile(cd, w, l)))
    lv = live_daily(); print(f"real account since launch ({len(lv)} trading days):"); print(risk_line('live record', risk_profile(lv)) + ('' if len(lv) >= 20 else '  (needs 20 trading days)'))


def cmd_regime(a):
    t = tun(); print(regime_line(regime(load_data(), champion_values(t), a.window)))


def cmd_attrib(a):
    print(f"live vs model attribution{' since ' + a.since if a.since else ' since launch'} (% of position):"); print(attribution_text(attribution(a.since)))


def cmd_defensive(a):
    t = tun(); head, rows, rec = defensive(t, load_data(), a.window)
    print(f"defensive options, stop risk on the last {a.window} sessions in scenario '{SCENARIOS[-1][0]}', target {head['target']}% (reports only; the governor decides):")
    print(defensive_text(head, rows, rec)); print(f"recommendation: {rec['name'] if rec else 'none (the version in force meets the target, or no option meets it within the cost limit)'}")


def cmd_defend(a):
    """Propose a defensive (risk-reducing) numeric change found by the defensive review. It needs no forward shadow evidence (it is judged
    on risk), but it must be a current recommendation-grade option. The governor approves and promotes as usual."""
    t = tun()
    if pending(): sys.exit('a proposal is already pending')
    head, rows, rec = defensive(t, load_data())
    row = next((r for r in rows if r['num'] and r['num']['variable'] == a.variable and abs(r['num']['new'] - a.new) < 1e-9), None)
    if not row or not row['ok']: sys.exit(f"{a.variable} {a.new:g} does not meet the defensive target ({head['target']}% stop risk within the cost limit)")
    v = dict(champion_values(t)); v[a.variable] = a.new
    p = dict(id=f"p{len(ledger()) + 1}", kind='defensive', created=datetime.now(ET).isoformat(timespec='seconds'), source='session', rationale=a.why, base_version=current(t)['version'],
             variable=a.variable, old=row['num']['old'], new=a.new, values=v, evidence=dict(id=f"defend.{a.variable}", stop_risk_before=head['b']['p_stop'], stop_risk_after=row['rp']['p_stop'],
             mean_before=head['mean'], mean_after=row['mean'], window=head['window']))
    os.makedirs(IDIR, exist_ok=True); json.dump(p, open(PENDING, 'w'), indent=1); ledger('proposal', **{k: p[k] for k in ('id', 'kind', 'variable', 'old', 'new', 'source', 'rationale')})
    print(f"DEFENSIVE PROPOSAL {p['id']}: {a.variable} {row['num']['old']:g} -> {a.new:g}. Stressed stop risk {head['b']['p_stop']}% -> {row['rp']['p_stop']}% (last {head['window']} sessions), "
          f"whole dataset {head['mean']:+.3f} -> {row['mean']:+.3f}%/day. Waiting for the governor: improve.py approve --note \"...\"")


def cmd_status(a):
    t = tun(); c = current(t); ch = challenger(t)
    print(f"version in force (real account and paper model): v{c['version']} ({c['kind']}, from {c['effective_from']}) {c['values']}")
    print(f"challenger {ch['id']} (approved, ready to promote, paper only): {ch['variable']} {ch['old']} -> {ch['new']}" if ch else 'challenger: none')
    evs, m = evidence(t)
    print(f"evidence: {len(evs)} candidates tracked ({m} ever), forward shadow days {max([e['n_days'] for e in evs] or [0])}, ready {sum(e['status'] == 'ready' for e in evs)}, retired this version {len(retired_ids(t))}; research ledger {len(rledger())} entries")
    print('goals vs paper model:', json.dumps(goal_progress()))
    print('pending:', json.dumps(pending()) if pending() else 'none')
    try: print('drawdown stop:', 'ACTIVE' if json.load(open(HWM)).get('halted') else 'clear')
    except Exception: pass
    for e in ledger()[-5:]: print(' ', json.dumps(e))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('review'); s.add_argument('system', choices=['fade', 'pb']); s.set_defaults(f=cmd_review)
    s = sub.add_parser('trial'); s.add_argument('system', choices=['fade', 'pb']); s.add_argument('id'); s.add_argument('why'); s.set_defaults(f=cmd_trial)
    s = sub.add_parser('push'); s.add_argument('system', choices=['fade', 'pb']); s.add_argument('--effective', required=True); s.add_argument('--note', required=True); s.set_defaults(f=cmd_push)
    s = sub.add_parser('decline'); s.add_argument('system', choices=['fade', 'pb']); s.set_defaults(f=cmd_decline)
    s = sub.add_parser('tick'); s.add_argument('dumps', nargs='*'); s.add_argument('--force', action='store_true'); s.set_defaults(f=cmd_tick)
    s = sub.add_parser('menu'); s.add_argument('--risk-off', action='store_true'); s.set_defaults(f=cmd_menu)
    for n, f in (('prompt', cmd_prompt), ('status', cmd_status), ('evidence', cmd_evidence)): sub.add_parser(n).set_defaults(f=f)
    s = sub.add_parser('research'); s.add_argument('--verdict'); s.set_defaults(f=cmd_research)
    s = sub.add_parser('screen'); s.add_argument('symbols', nargs='*'); s.add_argument('--top', type=int, default=40); s.add_argument('--min-usd', type=float, default=50000); s.add_argument('--min-sessions', type=int, default=120); s.add_argument('--traded', action='store_true'); s.set_defaults(f=cmd_screen)
    s = sub.add_parser('watch-add'); s.add_argument('--type', choices=['fade', 'pb'], required=True); s.add_argument('--proxy'); s.add_argument('--bull'); s.add_argument('--bear'); s.add_argument('--lev-bull', type=float); s.add_argument('--lev-bear', type=float); s.add_argument('--leg')
    s.add_argument('--why', default=''); s.add_argument('--force', action='store_true'); s.add_argument('--min-usd', type=float, default=50000); s.add_argument('--min-sessions', type=int, default=100); s.set_defaults(f=cmd_watch_add)
    s = sub.add_parser('prune'); s.add_argument('--dry', action='store_true'); s.set_defaults(f=cmd_prune)
    s = sub.add_parser('risk'); s.add_argument('--id'); s.set_defaults(f=cmd_risk)
    s = sub.add_parser('regime'); s.add_argument('--window', type=int, default=20); s.set_defaults(f=cmd_regime)
    s = sub.add_parser('attrib'); s.add_argument('--since'); s.set_defaults(f=cmd_attrib)
    s = sub.add_parser('defend'); s.add_argument('variable', choices=['risk.pct', 'size.cap_pct']); s.add_argument('new', type=float); s.add_argument('why'); s.set_defaults(f=cmd_defend)
    s = sub.add_parser('defensive'); s.add_argument('--window', type=int, default=60); s.set_defaults(f=cmd_defensive)
    s = sub.add_parser('add-checklist'); s.add_argument('id'); s.set_defaults(f=cmd_add_checklist)
    s = sub.add_parser('research-add'); [s.add_argument('--' + k, required=True) for k in ('id', 'idea', 'method', 'result', 'verdict')]; s.set_defaults(f=cmd_research_add)
    s = sub.add_parser('shadow-replay'); s.add_argument('--from', dest='frm', required=True); s.add_argument('--to', required=True); s.add_argument('--force', action='store_true'); s.set_defaults(f=cmd_shadow_replay)
    s = sub.add_parser('submit'); s.add_argument('choice'); s.add_argument('why'); s.set_defaults(f=cmd_submit)
    s = sub.add_parser('approve'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_approve)
    s = sub.add_parser('promote'); s.add_argument('--effective', required=True); s.add_argument('--note', required=True); s.set_defaults(f=cmd_promote)
    s = sub.add_parser('discard'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_discard)
    s = sub.add_parser('reject'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_reject)
    s = sub.add_parser('rollback'); s.add_argument('--effective', required=True); s.set_defaults(f=cmd_rollback)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
