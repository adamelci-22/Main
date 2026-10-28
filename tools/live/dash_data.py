#!/usr/bin/env python3
"""Build the scorecard dashboard's live data from archive/live_trades.csv (governor request 2026-10-28).
    python3 tools/live/dash_data.py OUT_DIR [YYYY-MM-DD]      # writes live_trades.json, live_days.json, health.json and periods_live.json into OUT_DIR
Every real trade since 2026-10-16 as a row (n, day, system, ticker, acct_pct, pos_pct, model_pct, reached_2R) plus the number of trading days elapsed.
Reporting only: it changes no order, rule or state."""
import csv, json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import health

out = sys.argv[1]; os.makedirs(out, exist_ok=True)
day = sys.argv[2] if len(sys.argv) > 2 else datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
rows = [r for r in csv.DictReader(open(health.TRADES)) if r['date'] <= day]
rows.sort(key=lambda r: (r['date'], r['exit_time']))
trades = []
for i, r in enumerate(rows, 1):
    r2 = r.get('reached_2R', '').strip().lower()
    trades.append(dict(n=i, day=r['date'], system=r['system'], ticker=r['ticker'], acct_pct=float(r['acct_pct']), pos_pct=float(r['pnl_pct_position']),
                       model_pct=float(r['model_pct']) if r.get('model_pct', '').strip() else None, pnl_usd=float(r['pnl_usd']),
                       reached_2R=(True if r2 == 'yes' else False if r2 == 'no' else None)))
days = health.trading_days(health.LIVE_START, day)
# one row per live trading day: the account % made that day by each system (0 on days without a trade)
daily = []
for i, d in enumerate(days, 1):
    row = dict(d=i, day=d, combined=0.0, fade=0.0, pullback=0.0)
    for t in trades:
        if t['day'] == d:
            row['combined'] = round(row['combined'] + t['acct_pct'], 4)
            k = 'fade' if t['system'] == 'FADE' else 'pullback'; row[k] = round(row[k] + t['acct_pct'], 4)
    daily.append(row)
# health.json: the latest tracker row (archive/health_log.csv, written by health.py) as one line per measure, for the dashboard's health cards
def tone(st):
    st = (st or '').strip()
    if 'too few' in st or st == 'too early': return 'early'
    if st.startswith('HEALTHY'): return 'ok'
    if st.startswith('WARNING') or st.startswith('WATCH') or st.startswith('CHECK'): return 'warn'
    if st.startswith('ACT'): return 'bad'
    return 'na'
log = [r for r in csv.DictReader(open(health.LOG)) if r['date'] <= day]
hrows = []
if log:
    L = log[-1]
    def pct(v, d=2, sign=False):
        try: return format(float(v), ('+' if sign else '') + f'.{d}f') + '%'
        except ValueError: return 'n/a'
    def freq(got, exp):
        try: return f"{got} of {float(exp):.1f} expected ({100 * float(got) / float(exp):.0f}%)"
        except (ValueError, ZeroDivisionError): return 'n/a'
    def add(system, i, measure, value, rule, st): hrows.append(dict(id=f'{system}_{i}', system=system, order=i, measure=measure, value=value, rule=rule, tone=tone(st), status=st))
    W = health.WINDOW
    add('FADE', 0, 'Verdict', L['verdict'], '', L['verdict'])
    add('FADE', 1, f'Profit factor, last {W}', L['fade_pf'], 'healthy above 1.5, act below 1.0', L['pf_status'])
    add('FADE', 2, f'Reached +2R, last {W}', (L['pct_reach_2R'] + '%') if L['pct_reach_2R'] else 'n/a', 'healthy above 40%, act below 30%', L['reach_2R_status'])
    add('FADE', 3, 'Execution gap', pct(L['fade_exec_gap_pct'], 2, True) if L['fade_exec_gap_pct'] else 'n/a', 'healthy above -0.10%, act below -0.25%', L['fade_exec_status'])
    add('FADE', 4, 'Trade pace, last 30 days', freq(L['fade_trades_30d'], L['fade_expected_30d']), 'healthy at 60% or more of backtest pace', L['fade_freq_status'])
    add('FADE', 5, 'Drawdown from high', pct(L['drawdown_pct'], 1), 'healthy below 7%, act at 10%', L['dd_status'])
    add('PULLBACK', 0, 'Verdict', L['pb_verdict'], '', L['pb_verdict'])
    add('PULLBACK', 1, f'Profit factor, last {W}', L['pb_pf'], 'healthy above 1.5, act below 1.0', L['pb_pf_status'])
    add('PULLBACK', 2, f'Win rate, last {W}', (L['pb_win_pct'] + '%') if L['pb_win_pct'] else 'n/a', 'healthy above 60%, act below 50%', L['pb_win_status'])
    add('PULLBACK', 3, 'Average trade (of position)', (L['pb_avg_pct'] + '%') if L['pb_avg_pct'] else 'n/a', 'healthy above +0.20%, act below 0', L['pb_avg_status'])
    add('PULLBACK', 4, 'Execution gap', pct(L['pb_exec_gap_pct'].rstrip('%'), 2, True) if L['pb_exec_gap_pct'] else 'n/a', 'healthy above -0.10%, act below -0.25%', L['pb_exec_status'])
    add('PULLBACK', 5, 'Trade pace, last 30 days', freq(L['pb_trades_30d'], L['pb_expected_30d']), 'healthy at 60% or more of backtest pace', L['pb_freq_status'])
    for sname, k in (('FADE', 'fade_trades'), ('PULLBACK', 'pb_trades')):
        for r in hrows:
            if r['system'] == sname: r['trades'] = int(L[k]); r['window'] = W; r['day'] = L['date']
json.dump(hrows, open(os.path.join(out, 'health.json'), 'w'))
json.dump(daily, open(os.path.join(out, 'live_days.json'), 'w'))
json.dump(trades, open(os.path.join(out, 'live_trades.json'), 'w'))
json.dump([dict(source='live', days=len(days), start=health.LIVE_START, end=day)], open(os.path.join(out, 'periods_live.json'), 'w'))
print(f"{len(trades)} live trades, {len(days)} trading days {health.LIVE_START}..{day} -> {out}")
