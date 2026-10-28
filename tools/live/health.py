#!/usr/bin/env python3
"""FADE and PULLBACK health tracker (RULEBOOK C5, governor instructions 2026-10-28). Run at the 13:30 close after the day's trades are logged:
    python3 tools/live/health.py <total value>          # prints the table and records today's row in archive/health_log.csv
Measures (rolling, real trades from archive/live_trades.csv; drawdown from archive/hwm.json):
    profit factor, last 30 FADE trades      healthy > 1.5   warning 1.0-1.5   ACT < 1.0
    % of FADE trades reaching +2R, last 30  healthy > 40%   warning 30-40%    ACT < 30%
    drawdown from the all-time high         healthy < 7%    warning 7-10%     ACT >= 10%   (A1.13 hard stop at 15%)
Two or more ACT -> the governor decides: switch FADE to the S1 stretch-filter version or pause and review.
Below 30 trades the two trade measures are provisional; below 10 they are shown but never count as ACT.
PULLBACK (v5.2.21): PF > 1.5 / 1.0-1.5 / < 1.0, win rate > 60% / 50-60% / < 50%, average trade > +0.20% / 0-0.20% / < 0 (% of position), last 30 real trades.
Reports only: it changes no order, rule or state."""
import csv, json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TRADES = os.path.join(ROOT, 'archive', 'live_trades.csv')
HWM = os.path.join(ROOT, 'archive', 'hwm.json')
LOG = os.path.join(ROOT, 'archive', 'health_log.csv')
WINDOW, MIN_ACT = 30, 10


def grade(v, healthy, warn, higher_is_better=True):
    """healthy/warn are the band edges: higher-is-better -> healthy if v > healthy, warning if v >= warn, else ACT."""
    if v is None: return 'n/a'
    if higher_is_better: return 'HEALTHY' if v > healthy else 'WARNING' if v >= warn else 'ACT'
    return 'HEALTHY' if v < healthy else 'WARNING' if v < warn else 'ACT'


def main():
    if len(sys.argv) < 2: sys.exit("usage: health.py <total value> [YYYY-MM-DD]")
    total = float(sys.argv[1])
    day = sys.argv[2] if len(sys.argv) > 2 else datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    rows = list(csv.DictReader(open(TRADES)))
    fade = [r for r in rows if r['system'] == 'FADE' and r['date'] <= day][-WINDOW:]
    pb = [r for r in rows if r['system'] == 'PULLBACK' and r['date'] <= day][-WINDOW:]
    def pf(rs):
        g = sum(float(r['pnl_usd']) for r in rs if float(r['pnl_usd']) > 0); l = -sum(float(r['pnl_usd']) for r in rs if float(r['pnl_usd']) <= 0)
        return (g / l if l else float('inf')) if rs else None
    n = len(fade); fpf = pf(fade)
    r2 = [r for r in fade if r.get('reached_2R', '').strip().lower() in ('yes', 'no')]
    p2r = 100 * sum(r['reached_2R'].strip().lower() == 'yes' for r in r2) / len(r2) if r2 else None
    hwm = json.load(open(HWM))['hwm']; dd = max(0.0, (1 - total / hwm) * 100)
    g_pf = grade(fpf, 1.5, 1.0); g_2r = grade(p2r, 40, 30); g_dd = grade(dd, 7, 10, higher_is_better=False)
    small = n < MIN_ACT
    if small:      # too few trades: show the grade but never let it count as ACT
        g_pf = g_pf + ' (too few trades)' if g_pf != 'n/a' else g_pf; g_2r = g_2r + ' (too few trades)' if g_2r != 'n/a' else g_2r
    acts = sum(g == 'ACT' for g in (g_pf, g_2r, g_dd))
    prov = '' if n >= WINDOW else f'  [provisional: {n} of {WINDOW} trades]'
    fmt_pf = lambda v: 'n/a' if v is None else ('inf (no losses)' if v == float('inf') else f'{v:.2f}')
    print(f"FADE HEALTH {day}{prov}")
    print(f"  {'measure':<40}{'now':>18}   {'healthy':<9}{'warning':<10}{'ACT':<9} status")
    print(f"  {'Profit factor, last ' + str(WINDOW) + ' FADE trades':<40}{fmt_pf(fpf) + f' (n={n})':>18}   {'> 1.5':<9}{'1.0-1.5':<10}{'< 1.0':<9} {g_pf}")
    print(f"  {'% of FADE trades reaching +2R, last ' + str(WINDOW):<40}{('n/a' if p2r is None else f'{p2r:.0f}%') + f' (n={len(r2)})':>18}   {'> 40%':<9}{'30-40%':<10}{'< 30%':<9} {g_2r}")
    print(f"  {'Drawdown from the all-time high':<40}{f'{dd:.1f}% (high ${hwm:,.2f})':>18}   {'< 7%':<9}{'7-10%':<10}{'>= 10%':<9} {g_dd}   (A1.13 hard stop at 15%)")
    if acts >= 2: verdict = "ACT: two or more triggers. Governor decision: switch FADE to the S1 stretch-filter version, or pause and review. Nothing changes until the governor decides."
    elif acts == 1 or any(g.startswith('WARNING') for g in (g_pf, g_2r, g_dd)): verdict = "WATCH: a measure is outside the healthy range. No action; keep the system as is."
    else: verdict = "HEALTHY: keep the system as is."
    print(f"  VERDICT: {verdict}")
    # PULLBACK (v5.2.21): profit factor, win rate and average result of the last 30 real PULLBACK trades; drawdown is the shared line above
    pn = len(pb); ppf = pf(pb)
    pwin = 100 * sum(float(r['pnl_usd']) > 0 for r in pb) / pn if pn else None
    pavg = sum(float(r['pnl_pct_position']) for r in pb) / pn if pn else None
    p_pf = grade(ppf, 1.5, 1.0); p_win = grade(pwin, 60, 50); p_avg = grade(pavg, 0.20, 0.0)
    if pn < MIN_ACT:
        p_pf, p_win, p_avg = (g + ' (too few trades)' if g != 'n/a' else g for g in (p_pf, p_win, p_avg))
    pacts = sum(g == 'ACT' for g in (p_pf, p_win, p_avg))
    print(f"\nPULLBACK HEALTH {day}" + ('' if pn >= WINDOW else f'  [provisional: {pn} of {WINDOW} trades]'))
    print(f"  {'measure':<40}{'now':>18}   {'healthy':<9}{'warning':<10}{'ACT':<9} status")
    print(f"  {'Profit factor, last ' + str(WINDOW) + ' PULLBACK trades':<40}{fmt_pf(ppf) + f' (n={pn})':>18}   {'> 1.5':<9}{'1.0-1.5':<10}{'< 1.0':<9} {p_pf}")
    print(f"  {'Win rate, last ' + str(WINDOW) + ' PULLBACK trades':<40}{('n/a' if pwin is None else f'{pwin:.0f}%'):>18}   {'> 60%':<9}{'50-60%':<10}{'< 50%':<9} {p_win}")
    print(f"  {'Average trade (% of position)':<40}{('n/a' if pavg is None else f'{pavg:+.2f}%'):>18}   {'> +0.20%':<9}{'0-0.20%':<10}{'< 0':<9} {p_avg}")
    if pacts >= 2: pverdict = "ACT: two or more triggers. Governor decision: go back to the four funds (SOXS LABD TECS UVXY) or drop PULLBACK. Nothing changes until the governor decides."
    elif pacts == 1 or any(g.startswith('WARNING') for g in (p_pf, p_win, p_avg)): pverdict = "WATCH: a measure is outside the healthy range. No action; keep the system as is."
    else: pverdict = "HEALTHY: keep the system as is."
    print(f"  VERDICT: {pverdict}  (probation review at 30 live PULLBACK trades)")
    # one row per day in archive/health_log.csv (re-running on the same day replaces the row)
    hdr = ['date', 'fade_trades', 'fade_pf', 'pct_reach_2R', 'drawdown_pct', 'total_value', 'hwm', 'pf_status', 'reach_2R_status', 'dd_status', 'act_count', 'verdict',
           'pb_trades', 'pb_pf', 'pb_win_pct', 'pb_avg_pct', 'pb_pf_status', 'pb_win_status', 'pb_avg_status', 'pb_act_count', 'pb_verdict']
    old = [r for r in csv.DictReader(open(LOG))] if os.path.exists(LOG) else []
    old = [r for r in old if r['date'] != day]
    old.append(dict(date=day, fade_trades=n, fade_pf=fmt_pf(fpf), pct_reach_2R='' if p2r is None else f'{p2r:.0f}', drawdown_pct=f'{dd:.2f}', total_value=f'{total:.2f}',
                    hwm=f'{hwm:.2f}', pf_status=g_pf, reach_2R_status=g_2r, dd_status=g_dd, act_count=acts, verdict=verdict.split(':')[0],
                    pb_trades=pn, pb_pf=fmt_pf(ppf), pb_win_pct='' if pwin is None else f'{pwin:.0f}', pb_avg_pct='' if pavg is None else f'{pavg:+.2f}',
                    pb_pf_status=p_pf, pb_win_status=p_win, pb_avg_status=p_avg, pb_act_count=pacts, pb_verdict=pverdict.split(':')[0]))
    with open(LOG, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=hdr, lineterminator='\n', restval=''); w.writeheader(); w.writerows(sorted(old, key=lambda r: r['date']))
    print(f"  recorded in archive/health_log.csv")


if __name__ == '__main__':
    main()
