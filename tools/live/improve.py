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

TUN = os.path.join(HERE, 'tunables.json'); IDEAS = os.path.join(HERE, 'ideas.json'); RLEDGER = os.environ.get('IMPROVE_RLEDGER') or os.path.join(HERE, 'research_ledger.json')
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
            tod = {s: D.bars[s][d][:48] for s in paper.EXPECTED if d in D.bars.get(s, {})}
            prv = {s: D.bars[s][pd] for s in paper.EXPECTED if pd in D.bars.get(s, {})}
            taken, _, _, e2 = paper.simulate(tod, prv, 48, eq, None, 0, d)
            for c in taken:
                if c['status'] == 'closed': trades.append((d, c['usd'], c['usd'] / eq * 100))
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
    return {'shadow_from': '0000-00-00', 'min_diff_days': 20, 'alpha': 0.10, 'harm_diff_days': 10, 'retire_days': 60, 'resamples': 5000, 'promote_pct': 0.5, **t['policy']}


def ideas():
    return json.load(open(IDEAS)) if os.path.exists(IDEAS) else []


def champion_values(t):
    return {**paper.TUNABLE_DEFAULTS, **current(t)['values']}


def rledger():
    return json.load(open(RLEDGER)) if os.path.exists(RLEDGER) else []


def radd(**kw):
    L = rledger(); L.append({'date': today().isoformat(), **kw}); json.dump(L, open(RLEDGER, 'w'), indent=1); open(RLEDGER, 'a').write('\n')


def retired_ids(t):
    cv = current(t)['version']
    return {e['id'] for e in rledger() if e.get('kind') == 'shadow' and e.get('champion_version') == cv and e.get('verdict') in ('rejected', 'inconclusive')}


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
    retired = retired_ids(t); m_ever = len(set(by) | retired); m = max(1, m_ever); meta = {c['id']: c for c in candidates(t)}; out = []
    for cid, rows in by.items():
        if cid in retired: continue
        rows.sort(key=lambda r: r['day']); d = [float(r['candidate_pct']) - float(r['champion_pct']) for r in rows]; n = len(d)
        rng = random.Random(f"{cid}:{n}:{cv}"); B = pol['resamples']
        sums = sorted(sum(rng.choices(d, k=n)) for _ in range(B)) if n >= 5 else None
        lo = sums[min(B - 1, int(pol['alpha'] / m * B))] if sums else None            # Bonferroni: the lower bound at alpha / (candidates ever tracked)
        hi = sums[min(B - 1, int((1 - pol['alpha']) * B))] if sums else None
        e = dict(id=cid, kind=meta[cid]['kind'] if cid in meta else '?', promotable=meta[cid]['promotable'] if cid in meta else False, desc=meta[cid]['desc'] if cid in meta else '',
                 n_days=n, n_diff=sum(int(r['differs']) for r in rows), total=round(sum(d), 3), lo=None if lo is None else round(lo, 3), hi=None if hi is None else round(hi, 3), m=m)
        if e['n_diff'] >= pol['min_diff_days'] and lo is not None and lo > 0 and e['total'] >= pol['promote_pct']: e['status'] = 'ready'
        elif e['n_diff'] >= pol['harm_diff_days'] and hi is not None and hi < 0: e['status'] = 'harm'
        elif n >= pol['retire_days']: e['status'] = 'stale'
        else: e['status'] = 'collecting'
        out.append(e)
    return sorted(out, key=lambda e: (e['status'] != 'ready', -e['total'])), m_ever


def evidence_line(e):
    lo = 'n/a' if e['lo'] is None else f"{e['lo']:+.2f}"
    return f"  {e['id']:<26}{e['status']:<11}{e['n_days']:>4}d {e['n_diff']:>3} differed  total {e['total']:+7.2f}% of account  lower bound {lo:>6}  {'' if e['promotable'] else '[idea: needs a rulebook change]'}"


def retire(t, evs):
    cv = current(t)['version']; done = []
    for e in evs:
        if e['status'] not in ('harm', 'stale'): continue
        verdict = 'rejected' if e['status'] == 'harm' else 'inconclusive'
        radd(kind='shadow', id=e['id'], champion_version=cv, idea=e['desc'], method='forward paper shadow on the saved bars of every close, paired against the champion',
             result=f"{e['n_days']} days, {e['n_diff']} differed, total {e['total']:+.2f}% of the account, bootstrap 90% interval upper bound {e['hi']:+.2f}, tracked candidates {e['m']}", verdict=verdict)
        ledger('retired', id=e['id'], verdict=verdict, total=e['total']); done.append(e)
    return done


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
    n = append_version(t, 'change', a.effective, ch['values'], base_version=ch['base_version'], proposal=ch['id'], note=a.note)
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


def cmd_tick(a):
    t = tun(); pol = policy(t); ch = challenger(t)
    if a.dumps:
        day, today_, prev = day_inputs(a.dumps); n = record_all(t, day, today_, prev, a.force)
        print(f"  shadow: {day}, champion v{current(t)['version']} and {n} candidates recorded (no orders)" if n else f"  shadow: {day} already recorded or before {pol['shadow_from']}")
    else: print("  no dumps passed: shadow run skipped today (every day missed is a day of evidence lost)")
    evs, m = evidence(t); done = retire(t, evs)
    cv = current(t)['version']; days = max([e['n_days'] for e in evs] or [0])
    print(f"  evidence vs v{cv}: {len(evs)} candidates tracked ({m} ever), {days} forward shadow days, {sum(e['status'] == 'collecting' for e in evs)} collecting")
    for e in evs[:5]: print(evidence_line(e))
    for e in done: print(f"RETIRED {e['id']}: {e['status']} ({e['total']:+.2f}% of account over {e['n_days']} days); written to the research ledger")
    ready = [e for e in evs if e['status'] == 'ready']
    if ch: print(f"  challenger {ch['id']} approved and waiting for the governor: improve.py promote --effective <date> --note \"...\" (or discard)"); return
    if pending(): print("  proposal pending, waiting for the governor:", json.dumps({k: pending()[k] for k in ('id', 'variable', 'old', 'new')})); return
    for e in ready:
        if e['promotable']: print(f"EVIDENCE READY: {e['id']} ({e['desc']}). Read the table above, answer `improve.py prompt`, then `improve.py submit <id|hold> \"why\"`, report to the governor and wait.")
        else: print(f"IDEA READY (needs a rulebook change, D3): {e['id']} ({e['desc']}). Report it to the governor at once; the loop will not change a structural rule.")
    if not ready: print("  no candidate is ready")


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
    evs, _ = evidence(t); row = next((e for e in evs if e['id'] == p['evidence']['id']), None)
    if not row or row['status'] != 'ready': sys.exit('the evidence no longer meets the gate: reject the proposal')
    t['challenger'] = dict(id=p['evidence']['id'], variable=p['variable'], old=p['old'], new=p['new'], values=p['values'], base_version=p['base_version'], start=today().isoformat(), status='ready', note=a.note, evidence=row)
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
            tod = {s: D.bars[s][d][:48] for s in paper.EXPECTED if d in D.bars.get(s, {})}; prv = {s: D.bars[s][pd] for s in paper.EXPECTED if pd in D.bars.get(s, {})}
            n += record_all(t, d, tod, prv, a.force)
    finally:
        paper.LOCKCUT_FROM, paper.FADE_NO_FRIDAY_FROM = saved
    print(f"replayed {a.frm}..{a.to}: {n} rows -> {SHADOW}")


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
    s = sub.add_parser('tick'); s.add_argument('dumps', nargs='*'); s.add_argument('--force', action='store_true'); s.set_defaults(f=cmd_tick)
    s = sub.add_parser('menu'); s.add_argument('--risk-off', action='store_true'); s.set_defaults(f=cmd_menu)
    for n, f in (('prompt', cmd_prompt), ('status', cmd_status), ('evidence', cmd_evidence)): sub.add_parser(n).set_defaults(f=f)
    s = sub.add_parser('research'); s.add_argument('--verdict'); s.set_defaults(f=cmd_research)
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
