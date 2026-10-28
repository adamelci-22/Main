#!/usr/bin/env python3
"""Self-improvement loop for the FADE and PULLBACK model (RULEBOOK D4, draft: see PROPOSED_SELF_IMPROVEMENT.md).

The loop never changes a live setting by itself. It proposes, the governor approves, and every approved change is judged against the
version it replaced on the SAME days. Only the five tunables in tools/live/tunables.json can change. Entry safety (A1), sizing (B4.1),
the ticker lists and the session hours are not tunable.

Commands (stdlib only; run from anywhere):
    improve.py tick [DUMP ...]        13:30 close, AFTER `paper.py --close`: shadow-run + verdict on an active trial, else a proposal if due
    improve.py status                 versions, active trial, pending proposal, last ledger events
    improve.py menu                   counterfactual table: every one-step change, walk-forward, with the gate result (about a minute)
    improve.py prompt                 print the proposer prompt (the checkpoint session answers it, then runs `submit`)
    improve.py submit CHOICE "why"    CHOICE = a menu id (e.g. fade.cut_r+1) or hold; writes the pending proposal
    improve.py approve --effective D --note "governor words"      governor only: appends a version that takes effect on date D
    improve.py reject --note "..."    governor only: discards the pending proposal
    improve.py rollback --effective D governor (or tick if policy.auto_rollback): re-instates the values the active trial replaced
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
    return json.load(open(TUN))


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


def active_trial(t=None):
    """The newest 'change' version that has no keep/revert verdict yet."""
    t = t or tun(); closed = {e['version'] for e in ledger() if e['event'] in ('keep', 'revert')}
    ch = [v for v in t['versions'] if v['kind'] == 'change' and v['version'] not in closed]
    return max(ch, key=lambda x: x['version']) if ch else None


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
    return dict(mean_day=round(st.mean(r), 4) if r else 0.0, dd=round(dd, 2), trades=len(tr), pf=round(w / l, 2) if l else None, ret=round((eq - 1) * 100, 2))


def evaluate(D, values):
    daily, trades = run_cf(D, values); cut = int(len(daily) * SPLIT)
    return dict(full=stats(daily, trades), ins=stats(daily, trades, 0, cut), oos=stats(daily, trades, cut))


def menu(D, base_values, space):
    base = evaluate(D, base_values); rows = []
    for var, sp in space.items():
        for sgn in (-1, 1):
            new = round(min(sp['hi'], max(sp['lo'], base_values[var] + sgn * sp['step'])), 4)
            if new == base_values[var]: continue
            v = dict(base_values); v[var] = new; e = evaluate(D, v)
            d = {k: round(e[k]['mean_day'] - base[k]['mean_day'], 4) for k in e}
            why = []
            if d['ins'] < 0: why.append('worse in-sample')
            if d['oos'] < 0: why.append('worse out-of-sample')
            if d['full'] < GATE_MIN_GAIN: why.append(f"gain < {GATE_MIN_GAIN}%/day")
            if e['full']['dd'] > base['full']['dd'] + GATE_DD_SLACK: why.append('drawdown +%.1f pts' % (e['full']['dd'] - base['full']['dd']))
            if e['full']['trades'] < GATE_TRADE_KEEP * base['full']['trades']: why.append('trades cut by more than 25%')
            rows.append(dict(id=f"{var}{'+1' if sgn > 0 else '-1'}", variable=var, old=base_values[var], new=new, delta=d, stats=e, passes=not why, fails=why))
    return base, rows


# ------------------------------------------------------------------ proposers
def context(t, base, rows):
    tr = model_trades()[-25:]
    return dict(objective='0.4% per trading day average over a year; 15% drawdown hard stop; Sharpe 1.2 floor, 2.0 goal. Paper model that mirrors a LIVE account.',
                current_version=current(t), recent_model_trades=tr, baseline_walk_forward=base,
                menu=[{k: r[k] for k in ('id', 'variable', 'old', 'new', 'delta', 'passes', 'fails')} | {'oos': r['stats']['oos'], 'ins': r['stats']['ins']} for r in rows])


def prompt_text(ctx):
    return ("You propose at most ONE change to a live-money trading model. The governor approves or rejects it. Choose ONLY an id from the menu rows "
            "where passes is true, or 'hold'. Prefer hold unless a row is clearly better in both in-sample and out-of-sample AND fits the recent trades. "
            "Do not invent parameters. Reply with one JSON object: {\"choice\": \"<id or hold>\", \"rationale\": \"<two sentences max>\"}.\n\n" + json.dumps(ctx, indent=1))


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
    best = max(ok, key=lambda r: min(r['delta']['ins'], r['delta']['oos']))
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


def record_shadow(trial, base_values, dumps):
    """Run BOTH versions on the same saved bars, so the comparison does not depend on account state or on which version the live model used."""
    day, ret = shadow_day(dumps, base_values)
    _, mret = shadow_day(dumps, trial['values'])
    if any(r['day'] == day and r['trial'] == str(trial['version']) for r in shadow_rows()): return day
    if day < trial['effective_from']: return day
    new_file = not os.path.exists(SHADOW); os.makedirs(IDIR, exist_ok=True)
    with open(SHADOW, 'a', newline='') as f:
        w = csv.writer(f)
        if new_file: w.writerow(['day', 'trial', 'old_ret_pct', 'new_ret_pct'])
        w.writerow([day, trial['version'], round(ret, 4), round(mret, 4)])
    return day


def verdict(trial, pol):
    rows = [r for r in shadow_rows() if r['trial'] == str(trial['version'])]
    n = len(rows); diff = sum(float(r['new_ret_pct']) - float(r['old_ret_pct']) for r in rows)
    differing = sum(1 for r in rows if abs(float(r['new_ret_pct']) - float(r['old_ret_pct'])) > 1e-9)
    if n >= 5 and diff <= pol['early_revert_pct']: res = 'revert'
    elif n >= pol['min_trial_days'] and diff < pol['revert_pct']: res = 'revert'
    elif n >= pol['min_trial_days'] and diff >= 0: res = 'keep'
    elif n >= 2 * pol['min_trial_days']: res = 'keep' if diff >= 0 else 'revert'
    else: res = 'continue'
    return res, dict(version=trial['version'], days=n, days_that_differed=differing, new_minus_old_pct_of_account=round(diff, 3))


def do_rollback(t, trial, eff, who):
    vals = version_values(t, trial['base_version'])
    n = max(v['version'] for v in t['versions']) + 1
    t['versions'].append(dict(version=n, kind='rollback', effective_from=eff, values=vals, note=f"rollback of v{trial['version']} ({who})", base_version=trial['version']))
    save_tun(t); ledger('revert', version=trial['version'], new_version=n, effective_from=eff, by=who)
    print(f"ROLLBACK: v{n} restores v{trial['base_version']} values from {eff}. Commit tools/live/tunables.json and archive/improve/.")


# ------------------------------------------------------------------ commands
def cmd_tick(a):
    t = tun(); pol = t['policy']; trial = active_trial(t)
    if trial:
        if a.dumps:
            d = record_shadow(trial, version_values(t, trial['base_version']), a.dumps); print(f"  shadow run for {d} recorded (old version v{trial['base_version']} vs trial v{trial['version']})")
        else: print("  no dumps passed: shadow run skipped today (the verdict needs one per trading day)")
        res, info = verdict(trial, pol); print(f"VERDICT v{trial['version']}: {res.upper()} {info}")
        if res == 'keep': ledger('keep', **info); print("  Trial closed: keep. Report it to the governor.")
        elif res == 'revert':
            if pol['auto_rollback']: do_rollback(t, trial, next_trading_day(today()).isoformat(), 'auto_rollback policy')
            else: print("  REVERT RECOMMENDED. Tell the governor now. Run: improve.py rollback --effective <date> after the governor agrees (policy.auto_rollback is off).")
        return
    if pending(): print("  proposal pending, waiting for the governor:", json.dumps({k: pending()[k] for k in ('id', 'variable', 'old', 'new')})); return
    ev = [e for e in ledger() if e['event'] in ('approved', 'rejected', 'hold', 'keep', 'revert')]
    since = ev[-1]['ts'][:10] if ev else '0000-00-00'
    n = sum(1 for x in model_trades() if x['day'] > since)
    if n < pol['cadence_trades'] and not a.force: print(f"  no proposal due: {n} of {pol['cadence_trades']} model trades since the last decision ({since})"); return
    propose(t, a.proposer)


def propose(t, proposer):
    D = load_data(); base, rows = menu(D, current(t)['values'], t['space'])
    json.dump(dict(base=base, rows=rows), open(os.path.join(IDIR, 'menu.json'), 'w'), indent=1)
    ctx = context(t, base, rows)
    if proposer == 'session':
        print("PROPOSAL DUE. Read archive/improve/menu.json, answer this prompt, then run: improve.py submit <id|hold> \"rationale\"\n"); print(prompt_text(ctx)); return
    c = ask_api(prompt_text(ctx)) if proposer == 'api' else fallback_choice(rows)
    write_pending(t, base, rows, c['choice'], c['rationale'], proposer)


def cmd_menu(a):
    t = tun(); D = load_data(); base, rows = menu(D, current(t)['values'], t['space'])
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
    if active_trial(t): sys.exit('a trial is still running: one change at a time')
    if a.effective <= today().isoformat() or datetime.strptime(a.effective, '%Y-%m-%d').weekday() >= 5 or a.effective in paper.NO_TRADE:
        sys.exit('--effective must be a future trading day: a live day is never changed mid-session')
    if p['base_version'] != current(t)['version']: sys.exit('the proposal is stale (the current version changed): reject it and propose again')
    vals = dict(current(t)['values']); vals[p['variable']] = p['new']; n = current(t)['version'] + 1
    t['versions'].append(dict(version=n, kind='change', effective_from=a.effective, values=vals, base_version=p['base_version'], proposal=p['id'], note=a.note))
    save_tun(t); os.remove(PENDING); ledger('approved', id=p['id'], version=n, effective_from=a.effective, note=a.note)
    print(f"APPROVED: v{n} ({p['variable']} {p['old']} -> {p['new']}) from {a.effective}. Bump the RULEBOOK version, record it in the commit, commit tunables.json + archive/improve/.")


def cmd_reject(a):
    p = pending()
    if not p: sys.exit('nothing pending')
    os.remove(PENDING); ledger('rejected', id=p['id'], note=a.note); print('rejected')


def cmd_rollback(a):
    t = tun(); trial = active_trial(t)
    if not trial: sys.exit('no active trial to roll back')
    if a.effective <= today().isoformat() or datetime.strptime(a.effective, '%Y-%m-%d').weekday() >= 5 or a.effective in paper.NO_TRADE:
        sys.exit('--effective must be a future trading day')
    do_rollback(t, trial, a.effective, 'governor')


def cmd_status(a):
    t = tun(); c = current(t); tr = active_trial(t)
    print(f"version in force: v{c['version']} ({c['kind']}, from {c['effective_from']}) {c['values']}")
    print(f"active trial: {('v%d since %s' % (tr['version'], tr['effective_from'])) if tr else 'none'}")
    if tr: print('  verdict so far:', verdict(tr, t['policy']))
    print('pending:', json.dumps(pending()) if pending() else 'none')
    try: print('drawdown stop:', 'ACTIVE' if json.load(open(HWM)).get('halted') else 'clear')
    except Exception: pass
    for e in ledger()[-5:]: print(' ', json.dumps(e))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('tick'); s.add_argument('dumps', nargs='*'); s.add_argument('--proposer', choices=['session', 'api', 'fallback'], default='session'); s.add_argument('--force', action='store_true'); s.set_defaults(f=cmd_tick)
    for n, f in (('menu', cmd_menu), ('prompt', cmd_prompt), ('status', cmd_status)): sub.add_parser(n).set_defaults(f=f)
    s = sub.add_parser('submit'); s.add_argument('choice'); s.add_argument('why'); s.set_defaults(f=cmd_submit)
    s = sub.add_parser('approve'); s.add_argument('--effective', required=True); s.add_argument('--note', required=True); s.set_defaults(f=cmd_approve)
    s = sub.add_parser('reject'); s.add_argument('--note', required=True); s.set_defaults(f=cmd_reject)
    s = sub.add_parser('rollback'); s.add_argument('--effective', required=True); s.set_defaults(f=cmd_rollback)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
