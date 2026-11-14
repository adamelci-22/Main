#!/usr/bin/env python3
"""Live review alert for the new systems (RULEBOOK A4.6, B6.11, B7.10; governor 2026-11-14: "set an alert of what we need after 60 trades").
    python3 -I tools/live/review_alert.py [--csv live_trades.csv] [--exec execution_log.csv] [--state review_state.json] [--no-save]
Run by the 13:30 loop trigger every trading day. Counts real trades in archive/live_trades.csv. Prints ALERT lines (each is sent once, kept in
archive/review_state.json) and, when a review is due, the full review packet: per-system numbers and the decisions the governor is asked for.
  per system: 20 trades = first review (warning if profit factor under 1.0), 30 trades = decision (under 1.0 goes to the governor)
  new systems together (IBS-LONG, MIRROR, DIP, OVERNIGHT): 60 trades = the full review
Reporting only. It changes no order, rule or state except its own alert record."""
import csv, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
opts = {}; a = sys.argv[1:]
while a:
    if a[0] == '--no-save': opts['no-save'] = '1'; a = a[1:]
    else: opts[a[0][2:]] = a[1]; a = a[2:]
CSV = opts.get('csv', os.path.join(ROOT, 'archive', 'live_trades.csv')); EXE = opts.get('exec', os.path.join(ROOT, 'archive', 'execution_log.csv'))
STATE = opts.get('state', os.path.join(ROOT, 'archive', 'review_state.json'))
NEW = ['IBS-LONG', 'MIRROR', 'DIP', 'OVERNIGHT']; ALL = ['FADE', 'PULLBACK'] + NEW
rows = [r for r in csv.DictReader(open(CSV))] if os.path.exists(CSV) else []
def num(v):
    try: return float(v)
    except Exception: return None
def stats(rs):
    acct = [num(r['acct_pct']) for r in rs if num(r.get('acct_pct')) is not None]; n = len(acct)
    if not n: return dict(n=0)
    gw = sum(x for x in acct if x > 0); gl = -sum(x for x in acct if x <= 0)
    gaps = [num(r['acct_pct']) - num(r['model_pct']) for r in rs if num(r.get('acct_pct')) is not None and num(r.get('model_pct')) is not None]
    return dict(n=n, win=100 * sum(x > 0 for x in acct) / n, pf=(gw / gl) if gl else None, avg=st.mean(acct), worst=min(acct), best=max(acct), gap=(st.mean(gaps) if gaps else None), total=sum(acct))
by = {s: [r for r in rows if r['system'].strip().upper() == s] for s in ALL}; S = {s: stats(by[s]) for s in ALL}
newn = sum(S[s]['n'] for s in NEW)
try: state = json.load(open(STATE))
except Exception: state = {'alerted': []}
due = []
for s in NEW + ['FADE', 'PULLBACK']:
    for k in (20, 30):
        key = f'{s}_{k}'
        if S[s]['n'] >= k and key not in state['alerted']: due.append((key, f"{s} reached {k} live trades: " + ('first review' if k == 20 else 'decision review')))
if newn >= 60 and 'new_60' not in state['alerted']: due.append(('new_60', f'the new systems reached {newn} live trades: FULL REVIEW'))
slip = []
if os.path.exists(EXE):
    for r in csv.DictReader(open(EXE)):
        if r.get('system', '').strip().upper() in NEW and r.get('purpose', '').lower() not in ('usdg', 'usdg_sell', 'usdg_rebuy', 'skipped') and num(r.get('slippage_pct')) is not None: slip.append(num(r['slippage_pct']))
def fmt(v, d=2, sign=False): return 'n/a' if v is None else format(v, ('+' if sign else '') + f'.{d}f')
print(f"LIVE TRADE COUNT: new systems {newn} of 60 | " + ', '.join(f"{s} {S[s]['n']}" for s in ALL))
if not due: print("No review due."); sys.exit(0)
for key, msg in due: print(f"REVIEW DUE: {msg}")
print("\nREVIEW PACKET (live trades, account % per trade)")
for s in ALL:
    x = S[s]
    print(f"  {s:<9} n {x['n']:3d}" + ('' if not x['n'] else f" | win {x['win']:.0f}% | PF {fmt(x['pf'])} | avg {fmt(x['avg'], 2, True)}% | worst {fmt(x['worst'], 2, True)}% | real minus model {fmt(x['gap'], 2, True)}% | total {fmt(x['total'], 1, True)}%"))
if slip: print(f"  real slippage on new-system orders: mean {st.mean(slip):+.3f}%, worst {min(slip):+.3f}% over {len(slip)} orders (the backtest assumed 0.03% a side)")
print("""
WHAT THE GOVERNOR IS ASKED TO DECIDE
  1. Keep, halve or turn off each system. Profit factor under 1.0 at 30 trades: off. 1.0 to 1.3: keep and keep watching. Above 1.3: keep.
  2. Size: if the new systems started at half size, go to full only with profit factor above 1.3 and real cost under 0.10% a round trip.
  3. Cost: compare real slippage with the backtest. Above 0.15% a round trip, the answer is limit orders and dropping the thin funds, not more trading.
  4. OVERNIGHT: keep 50%, change the size, or stop. Worst real night against the backtest's -4.1% of the account.
  5. MIRROR: it needs falling markets. If fewer than 10 trades have happened, say so and wait.
  6. The 15% drawdown stop: how many times it fired, and whether to keep it at 15%.
  7. USDG: still on or off, with the interest actually received.
  8. FADE: its kill rule (profit factor under 1.0 over its last 30 trades).
CLAUDE WILL BRING: the numbers above, the same table from the backtest for comparison, and a recommendation for each point.""")
msg = '; '.join(m for _, m in due)
print(f"\nPUSH MESSAGE: Agentic review due: {msg}. Decisions needed: keep/size/off per system, cost, USDG.")
if 'no-save' not in opts:
    state['alerted'] += [k for k, _ in due]; json.dump(state, open(STATE, 'w'), indent=1)
