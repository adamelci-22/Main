#!/usr/bin/env python3
"""Build the scorecard dashboard's live data from archive/live_trades.csv (governor request 2026-10-28).
    python3 tools/live/dash_data.py OUT_DIR [YYYY-MM-DD]      # writes live_trades.json and periods_live.json into OUT_DIR
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
json.dump(trades, open(os.path.join(out, 'live_trades.json'), 'w'))
json.dump([dict(source='live', days=len(days), start=health.LIVE_START, end=day)], open(os.path.join(out, 'periods_live.json'), 'w'))
print(f"{len(trades)} live trades, {len(days)} trading days {health.LIVE_START}..{day} -> {out}")
