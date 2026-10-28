#!/usr/bin/env python3
"""FADE and PULLBACK health tracker (RULEBOOK C5, governor instructions 2026-10-28). Run at the 13:30 close after the day's trades are logged:
    python3 tools/live/health.py <total value> [YYYY-MM-DD]     # prints both tables and records the day's row in archive/health_log.csv
Real trades from archive/live_trades.csv; drawdown from archive/hwm.json. Rolling window = the last 30 trades of each system.
    FADE      profit factor                  healthy > 1.5      warning 1.0-1.5        ACT < 1.0
              % of trades reaching +2R       healthy > 40%      warning 30-40%         ACT < 30%
    PULLBACK  profit factor                  healthy > 1.5      warning 1.0-1.5        ACT < 1.0
              win rate                       healthy > 60%      warning 50-60%         ACT < 50%
              average trade (% of position)  healthy > +0.20%   warning 0 to +0.20%    ACT < 0
    both      execution gap, real - model    healthy > -0.10%   warning -0.10 to -0.25 ACT < -0.25%   (per trade, % of position; v5.2.23)
              trade frequency vs backtest    healthy >= 60%     warning 30-60%         CHECK < 30%    (last 30 trading days; v5.2.23)
    account   drawdown from the all-time high healthy < 7%      warning 7-10%          ACT >= 10%     (A1.13 hard stop at 15%)
Two or more ACT in a system -> the governor decides (FADE: S1 stretch-filter version or pause; PULLBACK: back to SOXS LABD TECS UVXY or drop it).
Trade measures are provisional below 30 trades and never count as ACT below 10. Frequency is graded from 10 live trading days and never counts as
ACT: a low count means check the tooling (fetch groups, waiters, data) first, then the market. Reports only: it changes no order, rule or state."""
import csv, json, os, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TRADES = os.path.join(ROOT, 'archive', 'live_trades.csv')
HWM = os.path.join(ROOT, 'archive', 'hwm.json')
LOG = os.path.join(ROOT, 'archive', 'health_log.csv')
WINDOW, MIN_ACT, FREQ_DAYS, FREQ_MIN_DAYS = 30, 10, 30, 10
LIVE_START = '2026-10-16'
# expected trades per trading day: Robinhood backtest 2026-03-03..10-14 of the live rules (v5.2.22, 8-fund PULLBACK), one account, 157 days
RATE = {'FADE': 63 / 157, 'PULLBACK': 50 / 157}


def grade(v, healthy, warn, higher_is_better=True):
    """healthy/warn are the band edges: higher-is-better -> healthy if v > healthy, warning if v >= warn, else ACT."""
    if v is None: return 'n/a'
    if higher_is_better: return 'HEALTHY' if v > healthy else 'WARNING' if v >= warn else 'ACT'
    return 'HEALTHY' if v < healthy else 'WARNING' if v < warn else 'ACT'


def trading_days(start, end):
    try:
        import paper; closed = set(paper.NO_TRADE)
    except Exception: closed = set()
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5 and d.isoformat() not in closed: out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def pf(rs):
    g = sum(float(r['pnl_usd']) for r in rs if float(r['pnl_usd']) > 0); l = -sum(float(r['pnl_usd']) for r in rs if float(r['pnl_usd']) <= 0)
    return (g / l if l else float('inf')) if rs else None


fmt_pf = lambda v: 'n/a' if v is None else ('inf (no losses)' if v == float('inf') else f'{v:.2f}')
line = lambda name, now, h, w, a, st: print(f"  {name:<40}{now:>22}   {h:<10}{w:<16}{a:<10} {st}")


def system(name, rows, day, tdays, specific):
    """specific(rs) -> list of (label, value_text, healthy, warning, act, grade) for the system's own measures."""
    allr = [r for r in rows if r['system'] == name and r['date'] <= day]; rs = allr[-WINDOW:]; n = len(rs)
    gaps = [float(r['pnl_pct_position']) - float(r['model_pct']) for r in rs if r.get('model_pct', '').strip() and r.get('pnl_pct_position', '').strip()
            and not r.get('exclude_from_gap', '').strip().lower().startswith('yes')]      # governor hand closes are not system execution
    gap = sum(gaps) / len(gaps) if gaps else None
    win = tdays[-FREQ_DAYS:]; got = sum(1 for r in allr if r['date'] in set(win)); exp = RATE[name] * len(win)
    freq = 100 * got / exp if exp else None
    meas = specific(rs) + [('Execution gap, real - model, per trade', ('n/a' if gap is None else f'{gap:+.2f}%') + f' (n={len(gaps)})', '> -0.10%', '-0.10 to -0.25', '< -0.25%', grade(gap, -0.10, -0.25))]
    if n < MIN_ACT: meas = [(a, b, c, d, e, g + ' (too few trades)' if g not in ('n/a',) else g) for a, b, c, d, e, g in meas]
    fg = grade(freq, 59.999, 30)
    fg = 'n/a' if freq is None else ('too early' if len(win) < FREQ_MIN_DAYS else fg.replace('ACT', 'CHECK TOOLING'))
    print(f"\n{name} HEALTH {day}" + ('' if n >= WINDOW else f'  [provisional: {n} of {WINDOW} trades]'))
    line('measure', 'now', 'healthy', 'warning', 'ACT', 'status')
    for m in meas: line(*m)
    line(f'Trades, last {len(win)} trading days', f'{got} vs {exp:.1f} expected', '>= 60%', '30-60%', '< 30%', f"{fg}" + ('' if freq is None else f' ({freq:.0f}% of pace)'))
    live_results(name, allr)
    return meas, fg, n, gap, freq, got, exp


def live_results(name, allr):
    """The real trades of one system since LIVE_START: totals, then every trade (v5.2.23, governor: 'the results of the tracked trades')."""
    usd = [float(r['pnl_usd']) for r in allr]; pos = [float(r['pnl_pct_position']) for r in allr]; acct = [float(r['acct_pct']) for r in allr]
    w = [u for u in usd if u > 0]; l = [u for u in usd if u <= 0]
    print(f"  LIVE RESULTS since {LIVE_START}: {len(allr)} trades | {len(w)} wins, {len(l)} losses"
          + (f" ({100 * len(w) / len(allr):.0f}% win rate)" if allr else '') + f" | PF {fmt_pf(pf(allr))} | total ${sum(usd):+.2f} ({sum(acct):+.2f}% of account)")
    if not allr: return
    aw = f"${sum(w) / len(w):+.2f}" if w else 'n/a'; al = f"${sum(l) / len(l):+.2f}" if l else 'n/a'
    best = max(allr, key=lambda r: float(r['pnl_usd'])); worst = min(allr, key=lambda r: float(r['pnl_usd']))
    print(f"    average trade ${sum(usd) / len(usd):+.2f} ({sum(pos) / len(pos):+.2f}% of position) | average win {aw} | average loss {al}"
          f" | best {best['date']} {best['ticker']} ${float(best['pnl_usd']):+.2f} | worst {worst['date']} {worst['ticker']} ${float(worst['pnl_usd']):+.2f}")
    for r in allr:
        print(f"    {r['date']} {r['ticker']:<5} {r['entry_time']}->{r['exit_time']}  ${float(r['pnl_usd']):+7.2f}  {float(r['pnl_pct_position']):+.2f}% of position"
              f"  (model {float(r['model_pct']):+.2f}%)" + ('  reached 2R' if r.get('reached_2R', '').strip().lower() == 'yes' else ''))


def verdict(meas, fg, extra, act_text):
    gs = [m[5] for m in meas] + extra
    acts = sum(g == 'ACT' for g in gs)
    if acts >= 2: v = f"ACT: two or more triggers. Governor decision: {act_text}. Nothing changes until the governor decides."
    elif acts == 1 or any(g.startswith('WARNING') for g in gs): v = "WATCH: a measure is outside the healthy range. No action; keep the system as is."
    else: v = "HEALTHY: keep the system as is."
    if fg.startswith('CHECK'): v += " TRADE COUNT LOW: check the fetch groups, waiters and data before blaming the market."
    return acts, v


def main():
    if len(sys.argv) < 2: sys.exit("usage: health.py <total value> [YYYY-MM-DD]")
    total = float(sys.argv[1])
    day = sys.argv[2] if len(sys.argv) > 2 else datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    rows = list(csv.DictReader(open(TRADES))); tdays = trading_days(LIVE_START, day)
    hwm = json.load(open(HWM))['hwm']; dd = max(0.0, (1 - total / hwm) * 100); g_dd = grade(dd, 7, 10, higher_is_better=False)

    def fade_specific(rs):
        r2 = [r for r in rs if r.get('reached_2R', '').strip().lower() in ('yes', 'no')]
        p2r = 100 * sum(r['reached_2R'].strip().lower() == 'yes' for r in r2) / len(r2) if r2 else None
        v = pf(rs)
        return [(f'Profit factor, last {WINDOW} trades', fmt_pf(v) + f' (n={len(rs)})', '> 1.5', '1.0-1.5', '< 1.0', grade(v, 1.5, 1.0)),
                (f'% reaching +2R, last {WINDOW}', ('n/a' if p2r is None else f'{p2r:.0f}%') + f' (n={len(r2)})', '> 40%', '30-40%', '< 30%', grade(p2r, 40, 30))]

    def pb_specific(rs):
        n = len(rs); v = pf(rs)
        win = 100 * sum(float(r['pnl_usd']) > 0 for r in rs) / n if n else None
        avg = sum(float(r['pnl_pct_position']) for r in rs) / n if n else None
        return [(f'Profit factor, last {WINDOW} trades', fmt_pf(v) + f' (n={n})', '> 1.5', '1.0-1.5', '< 1.0', grade(v, 1.5, 1.0)),
                (f'Win rate, last {WINDOW} trades', 'n/a' if win is None else f'{win:.0f}%', '> 60%', '50-60%', '< 50%', grade(win, 60, 50)),
                ('Average trade (% of position)', 'n/a' if avg is None else f'{avg:+.2f}%', '> +0.20%', '0 to +0.20%', '< 0', grade(avg, 0.20, 0.0))]

    fm, ffg, fn, fgap, ffreq, fgot, fexp = system('FADE', rows, day, tdays, fade_specific)
    line('Drawdown from the all-time high (account)', f'{dd:.1f}% (high ${hwm:,.2f})', '< 7%', '7-10%', '>= 10%', f'{g_dd}   (A1.13 hard stop at 15%)')
    facts, fv = verdict(fm, ffg, [g_dd], 'switch FADE to the S1 stretch-filter version, or pause and review')
    print(f"  VERDICT: {fv}")
    pm, pfg, pn, pgap, pfreq, pgot, pexp = system('PULLBACK', rows, day, tdays, pb_specific)
    pacts, pv = verdict(pm, pfg, [], 'go back to the four funds (SOXS LABD TECS UVXY) or drop PULLBACK')
    print(f"  VERDICT: {pv}  (probation review at 30 live PULLBACK trades)")
    both = [r for r in rows if r['date'] <= day and r['system'] in ('FADE', 'PULLBACK')]
    bw = sum(float(r['pnl_usd']) > 0 for r in both)
    print(f"\nBOTH SYSTEMS since {LIVE_START}: {len(both)} trades, {bw} wins / {len(both) - bw} losses, PF {fmt_pf(pf(both))}, "
          f"total ${sum(float(r['pnl_usd']) for r in both):+.2f}; account ${total:,.2f}, drawdown {dd:.1f}% from the high")

    hdr = ['date', 'fade_trades', 'fade_pf', 'pct_reach_2R', 'drawdown_pct', 'total_value', 'hwm', 'pf_status', 'reach_2R_status', 'dd_status', 'act_count', 'verdict',
           'pb_trades', 'pb_pf', 'pb_win_pct', 'pb_avg_pct', 'pb_pf_status', 'pb_win_status', 'pb_avg_status', 'pb_act_count', 'pb_verdict',
           'fade_exec_gap_pct', 'fade_exec_status', 'fade_trades_30d', 'fade_expected_30d', 'fade_freq_status',
           'pb_exec_gap_pct', 'pb_exec_status', 'pb_trades_30d', 'pb_expected_30d', 'pb_freq_status']
    old = [r for r in csv.DictReader(open(LOG))] if os.path.exists(LOG) else []
    old = [r for r in old if r['date'] != day]
    num = lambda s: s.split(' ')[0]
    old.append(dict(date=day, fade_trades=fn, fade_pf=fm[0][1].split(' (n=')[0], pct_reach_2R=num(fm[1][1]).rstrip('%').replace('n/a', ''), drawdown_pct=f'{dd:.2f}',
                    total_value=f'{total:.2f}', hwm=f'{hwm:.2f}', pf_status=fm[0][5], reach_2R_status=fm[1][5], dd_status=g_dd, act_count=facts, verdict=fv.split(':')[0],
                    pb_trades=pn, pb_pf=pm[0][1].split(' (n=')[0], pb_win_pct=pm[1][1].rstrip('%').replace('n/a', ''), pb_avg_pct=pm[2][1].rstrip('%').replace('n/a', ''),
                    pb_pf_status=pm[0][5], pb_win_status=pm[1][5], pb_avg_status=pm[2][5], pb_act_count=pacts, pb_verdict=pv.split(':')[0],
                    fade_exec_gap_pct='' if fgap is None else f'{fgap:+.2f}', fade_exec_status=fm[2][5], fade_trades_30d=fgot, fade_expected_30d=f'{fexp:.1f}', fade_freq_status=ffg,
                    pb_exec_gap_pct='' if pgap is None else f'{pgap:+.2f}', pb_exec_status=pm[3][5], pb_trades_30d=pgot, pb_expected_30d=f'{pexp:.1f}', pb_freq_status=pfg))
    with open(LOG, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=hdr, lineterminator='\n', restval=''); w.writeheader(); w.writerows(sorted(old, key=lambda r: r['date']))
    print(f"\n  recorded in archive/health_log.csv")


if __name__ == '__main__':
    main()
