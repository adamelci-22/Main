#!/usr/bin/env python3
"""Self-improvement loop for the FADE and PULLBACK model (RULEBOOK D4, draft: see PROPOSED_SELF_IMPROVEMENT.md).

Champion / challenger. The REAL account and the paper model keep running the version in force (the champion). A proposed change becomes a
CHALLENGER that is only simulated, every close, on the same saved bars as the champion. It reaches the live account only if the governor
promotes it after a passing trial. Only the eleven tunables in tools/live/tunables.json can change. Entry safety (A1), the one-position rule, the
ticker lists, the session hours and the structure of the exits are not tunable. Nothing here places an order.

Commands (stdlib only; run from anywhere):
    improve.py tick [DUMP ...]        13:30 close, AFTER `paper.py --close`: shadow-run the challenger, verdict, else a proposal if due
    improve.py status                 version in force, challenger, pending proposal, last ledger events
    improve.py menu [--risk-off]      counterfactual table: every one-step change, walk-forward, with the gate result (under a minute).
                                      --risk-off adds position-size cuts (risk.pct and size.cap_pct, both % of the account, downward only); use it when the C5 drawdown measure is at ACT
    improve.py prompt                 print the proposer prompt (the checkpoint session answers it, then runs `submit`)
    improve.py submit CHOICE "why"    CHOICE = a menu id (e.g. fade.cut_r+1) or hold; writes the pending proposal
    improve.py approve --note "..."   governor: start the shadow trial (--start D, default today). The live account is NOT changed
    improve.py promote --effective D --note "..."   governor: after a PROMOTE verdict, put the challenger live from future trading day D
    improve.py discard --note "..."   governor: drop the challenger. improve.py reject: drop a pending proposal
    improve.py rollback --effective D governor: restore the values the version in force replaced (after a promotion)
Proposers for `tick --proposer`: session (default; the session reads `prompt`, answers with `submit`), api (ANTHROPIC_API_KEY), fallback (best row of the menu, no LLM).
"""
import argparse, csv, glob, json, math, os, statistics as st, sys, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import paper

TUN = os.path.join(HERE, 'tunables.json')
IDIR = os.path.join(ROOT, 'archive', 'improve')
LEDGER, PENDING, SHADOW = (os.path.join(IDIR, n) for n in ('ledger.jsonl', 'pending.json', 'shadow.csv'))
PAPER_LOG = os.path.join(ROOT, 'archive', 'paper_trades.csv')
HWM = os.path.join(ROOT, 'archive', 'hwm.json')
ET = ZoneInfo('America/New_York')
GATE_DD_SLACK, GATE_MIN_GAIN, GATE_TRADE_KEEP, SPLIT = 1.0, 0.01, 0.75, 0.6     # pts of drawdown, %/day, share of trades kept, in-sample share


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


# ------------------------------------------------------------------ counterfactual engine (paper.simulate on the shared 5-minute dataset)
def load_data():
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'backtest'))
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        from lab import get_data
        return get_data()


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


# ------------------------------------------------------------------ proposers
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


def context(t, base, rows):
    tr = model_trades()[-25:]
    return dict(objective=t.get('goals'), progress=goal_progress(), note='Paper model that mirrors a LIVE account.',
                current_version=current(t), recent_model_trades=tr, baseline_walk_forward=base,
                menu=[{k: r[k] for k in ('id', 'variable', 'old', 'new', 'delta', 'passes', 'fails')} | {'oos': r['stats']['oos'], 'ins': r['stats']['ins']} for r in rows])


def prompt_text(ctx):
    return ("You propose at most ONE change to a live-money trading model. The governor approves or rejects it. Choose ONLY an id from the menu rows "
            "where passes is true, or 'hold'. Prefer hold unless a row is clearly better in both in-sample and out-of-sample AND fits the recent trades. "
            "Do not invent parameters. All sizing is a percentage of the account, never a dollar amount, and size is never raised. Reply with one JSON object: {\"choice\": \"<id or hold>\", \"rationale\": \"<two sentences max>\"}.\n\n" + json.dumps(ctx, indent=1))


def ask_api(text):
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key: sys.exit('ANTHROPIC_API_KEY is not set')
    body = json.dumps(dict(model=os.environ.get('IMPROVE_MODEL', 'claude-sonnet-5-5'), max_tokens=600, messages=[dict(role='user', content=text)])).encode()
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', body, {'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    out = json.load(urllib.request.urlopen(req, timeout=120))['content'][0]['text']
    a, b = out.find('{'), out.rfind('}')
    return json.loads(out[a:b + 1])


def fallback_choice(rows):
    ok = [r for r in rows if r['passes']]
    if not ok: return dict(choice='hold', rationale='No one-step change passes the walk-forward gate.')
    best = max(ok, key=lambda r: (min(r['delta']['ins'], r['delta']['oos']), r['stats']['full'].get('sharpe_gain', 0)))
    return dict(choice=best['id'], rationale=f"Best worst-half gain among passing rows ({best['delta']['ins']:+.3f} in-sample, {best['delta']['oos']:+.3f} out-of-sample %/day).")


def write_pending(t, base, rows, choice, why, source):
    row = next((r for r in rows if r['id'] == choice), None)
    if choice == 'hold' or row is None or not row['passes']:
        ledger('hold', rationale=why, source=source); print(f"HOLD: {why}"); return
    p = dict(id=f"p{len(ledger()) + 1}", created=datetime.now(ET).isoformat(timespec='seconds'), source=source, rationale=why, base_version=current(t)['version'],
             variable=row['variable'], old=row['old'], new=row['new'], baseline=base, evidence=row)
    json.dump(p, open(PENDING, 'w'), indent=1); ledger('proposal', **{k: p[k] for k in ('id', 'variable', 'old', 'new', 'source', 'rationale')})
    print(f"PROPOSAL {p['id']}: {p['variable']} {p['old']} -> {p['new']} ({source}). Walk-forward %/day vs baseline: in-sample {row['delta']['ins']:+.3f}, "
          f"out-of-sample {row['delta']['oos']:+.3f}, full {row['delta']['full']:+.3f}. Waiting for the governor: improve.py approve --effective <date> --note \"...\"")


# ------------------------------------------------------------------ shadow run + verdict
def shadow_day(dumps, values):
    """What the version being judged against would have done on today's saved bars (same code path as paper.main). Returns (day, return %)."""
    raw = paper.load([f for g in dumps for f in glob.glob(g)])
    days = sorted({d for s in raw.values() for d in s})
    day = days[-1]; prevday = max(d for d in days if d < day)
    today_ = {s: g for s in raw if day in raw[s] for g in [paper.grid(raw[s][day], 48)] if g}
    prev = {s: g for s in raw if prevday in raw[s] for g in [paper.grid(raw[s][prevday], 78)] if g}
    paper.FLOOR_TARGET = day >= paper.FLOOR_FROM; saved = paper.OVERRIDE; paper.OVERRIDE = values
    try:
        taken, _, _, e2 = paper.simulate(today_, prev, 48, 1000.0, None, 0, day)
    finally:
        paper.OVERRIDE = saved
    return day, (e2 / 1000.0 - 1) * 100


def shadow_rows():
    return list(csv.DictReader(open(SHADOW))) if os.path.exists(SHADOW) else []


def record_shadow(ch, champion_values, dumps):
    """Run BOTH versions on the same saved bars, so the comparison does not depend on account state or on what the live model did."""
    day, old = shadow_day(dumps, champion_values)
    _, new = shadow_day(dumps, ch['values'])
    if day < ch['start'] or any(r['day'] == day and r['challenger'] == ch['id'] for r in shadow_rows()): return day
    new_file = not os.path.exists(SHADOW); os.makedirs(IDIR, exist_ok=True)
    with open(SHADOW, 'a', newline='') as f:
        w = csv.writer(f)
        if new_file: w.writerow(['day', 'challenger', 'champion_ret_pct', 'challenger_ret_pct'])
        w.writerow([day, ch['id'], round(old, 4), round(new, 4)])
    return day


def verdict(ch, pol):
    rows = [r for r in shadow_rows() if r['challenger'] == ch['id']]
    n = len(rows); diff = sum(float(r['challenger_ret_pct']) - float(r['champion_ret_pct']) for r in rows)
    differing = sum(1 for r in rows if abs(float(r['challenger_ret_pct']) - float(r['champion_ret_pct'])) > 1e-9)
    if n >= 5 and diff <= pol['early_discard_pct']: res = 'discard'
    elif n >= pol['min_trial_days'] and diff <= pol['discard_pct']: res = 'discard'
    elif n >= pol['min_trial_days'] and diff >= pol['promote_pct']: res = 'promote'
    elif n >= pol['max_trial_days']: res = 'discard'
    else: res = 'continue'
    return res, dict(challenger=ch['id'], days=n, days_that_differed=differing, challenger_minus_champion_pct_of_account=round(diff, 3))


def future_trading_day(eff):
    if eff <= today().isoformat() or datetime.strptime(eff, '%Y-%m-%d').weekday() >= 5 or eff in paper.NO_TRADE:
        sys.exit('--effective must be a future trading day: a live day is never changed mid-session')


def append_version(t, kind, eff, vals, **kw):
    n = max(v['version'] for v in t['versions']) + 1
    t['versions'].append(dict(version=n, kind=kind, effective_from=eff, values=vals, **kw)); return n


# ------------------------------------------------------------------ commands
def cmd_tick(a):
    t = tun(); pol = t['policy']; ch = challenger(t)
    if ch:
        if ch['status'] == 'ready':
            print(f"  challenger {ch['id']} passed its trial and waits for the governor: improve.py promote --effective <date> --note \"...\" (or discard)"); return
        if a.dumps:
            d = record_shadow(ch, version_values(t, ch['base_version']), a.dumps); print(f"  shadow run for {d} recorded (champion v{ch['base_version']} vs challenger {ch['id']}; neither places an order)")
        else: print("  no dumps passed: shadow run skipped today (the verdict needs one per trading day)")
        res, info = verdict(ch, pol); print(f"VERDICT {ch['id']}: {res.upper()} {info}")
        if res == 'promote':
            ch['status'] = 'ready'; ch['verdict'] = info; save_tun(t); ledger('verdict', result='promote', **info)
            print(f"  PROMOTION RECOMMENDED. Tell the governor. The real account stays on v{ch['base_version']} until the governor runs promote.")
        elif res == 'discard':
            t['challenger'] = None; save_tun(t); ledger('discarded', reason='trial', **info); print("  Challenger discarded. The live account was never changed.")
        return
    if pending(): print("  proposal pending, waiting for the governor:", json.dumps({k: pending()[k] for k in ('id', 'variable', 'old', 'new')})); return
    ev = [e for e in ledger() if e['event'] in ('approved', 'rejected', 'hold', 'promoted', 'discarded')]
    since = ev[-1]['ts'][:10] if ev else '0000-00-00'
    n = sum(1 for x in model_trades() if x['day'] > since)
    if n < pol['cadence_trades'] and not a.force: print(f"  no proposal due: {n} of {pol['cadence_trades']} model trades since the last decision ({since})"); return
    propose(t, a.proposer, a.risk_off)


def propose(t, proposer, risk_off=False):
    D = load_data(); base, rows = menu(D, current(t)['values'], t['space'], risk_off, t.get('goals'))
    json.dump(dict(base=base, rows=rows), open(os.path.join(IDIR, 'menu.json'), 'w'), indent=1)
    ctx = context(t, base, rows)
    if proposer == 'session':
        print("PROPOSAL DUE. Read archive/improve/menu.json, answer this prompt, then run: improve.py submit <id|hold> \"rationale\"\n"); print(prompt_text(ctx)); return
    c = ask_api(prompt_text(ctx)) if proposer == 'api' else fallback_choice(rows)
    write_pending(t, base, rows, c['choice'], c['rationale'], proposer)


def cmd_menu(a):
    t = tun(); D = load_data(); base, rows = menu(D, current(t)['values'], t['space'], a.risk_off, t.get('goals'))
    os.makedirs(IDIR, exist_ok=True); json.dump(dict(base=base, rows=rows), open(os.path.join(IDIR, 'menu.json'), 'w'), indent=1)
    b = base
    print(f"baseline v{current(t)['version']}: full {b['full']}\n  in-sample {b['ins']}\n  out-of-sample {b['oos']}")
    for r in rows: print(f"  {r['id']:<24}{r['old']:>7} -> {r['new']:<7} d%/day ins {r['delta']['ins']:+.3f} oos {r['delta']['oos']:+.3f} full {r['delta']['full']:+.3f}  dd {r['stats']['full']['dd']:.1f}  trades {r['stats']['full']['trades']}  {'PASS' if r['passes'] else 'fail: ' + ', '.join(r['fails'])}")


def cmd_prompt(a):
    t = tun(); m = json.load(open(os.path.join(IDIR, 'menu.json')))
    print(prompt_text(context(t, m['base'], m['rows'])))


def cmd_submit(a):
    t = tun(); m = json.load(open(os.path.join(IDIR, 'menu.json')))
    if pending(): sys.exit('a proposal is already pending')
    if a.choice != 'hold' and a.choice not in {r['id'] for r in m['rows']}: sys.exit(f"{a.choice} is not a menu id")
    write_pending(t, m['base'], m['rows'], a.choice, a.why, 'session')


def cmd_approve(a):
    p = pending(); t = tun()
    if not p: sys.exit('nothing pending')
    if challenger(t): sys.exit('a challenger is already in trial: one at a time')
    if p['base_version'] != current(t)['version']: sys.exit('the proposal is stale (the version in force changed): reject it and propose again')
    if a.start < today().isoformat(): sys.exit('--start cannot be in the past')
    vals = dict(current(t)['values']); vals[p['variable']] = p['new']
    t['challenger'] = dict(id=p['id'], variable=p['variable'], old=p['old'], new=p['new'], values=vals, base_version=p['base_version'], start=a.start, status='running', note=a.note)
    save_tun(t); os.remove(PENDING); ledger('approved', id=p['id'], start=a.start, note=a.note)
    print(f"TRIAL STARTED: {p['variable']} {p['old']} -> {p['new']} as a paper-only challenger from {a.start}. The live account and the paper model stay on v{p['base_version']}.")


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


def cmd_status(a):
    t = tun(); c = current(t); ch = challenger(t)
    print(f"version in force (real account and paper model): v{c['version']} ({c['kind']}, from {c['effective_from']}) {c['values']}")
    if ch: print(f"challenger {ch['id']} ({ch['status']}, paper only, from {ch['start']}): {ch['variable']} {ch['old']} -> {ch['new']}; so far", verdict(ch, t['policy']))
    else: print('challenger: none')
    print('goals vs paper model:', json.dumps(goal_progress()))
    print('pending:', json.dumps(pending()) if pending() else 'none')
    try: print('drawdown stop:', 'ACTIVE' if json.load(open(HWM)).get('halted') else 'clear')
    except Exception: pass
    for e in ledger()[-5:]: print(' ', json.dumps(e))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('tick'); s.add_argument('dumps', nargs='*'); s.add_argument('--proposer', choices=['session', 'api', 'fallback'], default='session'); s.add_argument('--force', action='store_true'); s.add_argument('--risk-off', action='store_true'); s.set_defaults(f=cmd_tick)
    s = sub.add_parser('menu'); s.add_argument('--risk-off', action='store_true'); s.set_defaults(f=cmd_menu)
    for n, f in (('prompt', cmd_prompt), ('status', cmd_status)): sub.add_parser(n).set_defaults(f=f)
    s = sub.add_parser('submit'); s.add_argument('choice'); s.add_argument('why'); s.set_defaults(f=cmd_submit)
    s = sub.add_parser('approve'); s.add_argument('--start', default=today().isoformat()); s.add_argument('--note', required=True); s.set_defaults(f=cmd_approve)
    s = sub.add_parser('promote'); s.add_argument('--effective', required=True); s.add_argument('--note', required=True); s.set_defaults(f=cmd_promote)
    s = sub.add_parser('discard'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_discard)
    s = sub.add_parser('reject'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_reject)
    s = sub.add_parser('rollback'); s.add_argument('--effective', required=True); s.set_defaults(f=cmd_rollback)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
