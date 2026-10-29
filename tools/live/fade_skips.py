#!/usr/bin/env python3
"""Track the trades the FADE runaway skip passes on (governor request 2026-10-29: "track the skipped trades on the scorecard too").
    python3 tools/live/fade_skips.py DUMP [DUMP ...]        # at the 13:30 close, with the day's saved bars (C4 step 5)
Runs the day twice on its own bars (fresh $1,000 account, one position at a time, same code as paper.simulate): the rules in force,
and the same rules with the runaway skip off. Every FADE trade the second run takes and the first does not is a skipped trade;
one row each goes to archive/fade_skips.csv with what it would have made, and the day's result of the rules in force beside it.
Idempotent per day. Reporting only: it changes no order, rule or state."""
import csv, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import paper, improve as I
OUT = os.path.join(ROOT, 'archive', 'fade_skips.csv')
HDR = ['day', 'proxy', 'ticker', 'entry_time', 'trend_pct', 'skipped_acct_pct', 'skipped_reached_2R', 'exit_reason', 'day_acct_pct_in_force', 'note']


def run(day, today_, prev, values):
    paper.FLOOR_TARGET = day >= paper.FLOOR_FROM; saved = paper.OVERRIDE; paper.OVERRIDE = values
    try:
        taken, _, _, e2 = paper.simulate(today_, prev, 48, 1000.0, None, 0, day)
    finally:
        paper.OVERRIDE = saved
    return taken, (e2 / 1000.0 - 1) * 100


def main():
    files = [f for g in sys.argv[1:] for f in glob.glob(g)]
    if not files: sys.exit(__doc__)
    day, today_, prev = I.day_inputs(files); t = I.tun(); cur = I.champion_values(t)
    if cur.get('x.fade_max_trend') is None: print(f"{day}: the runaway skip is not in force; nothing to track"); return
    have = list(csv.DictReader(open(OUT))) if os.path.exists(OUT) else []
    if any(r['day'] == day for r in have): print(f"{day}: already recorded"); return
    a, apct = run(day, today_, prev, cur); b, _ = run(day, today_, prev, {**cur, 'x.fade_max_trend': None})
    keep = {(c['proxy'], c['k']) for c in a if c['system'] == 'FADE'}; rows = []
    for c in b:
        if c['system'] != 'FADE' or (c['proxy'], c['k']) in keep or c['status'] != 'closed': continue
        p = c['proxy']; tr = (today_[p][c['k'] - 1][3] / prev[p][-1][3] - 1) * 100 * -c['side']
        rows.append(dict(day=day, proxy=p, ticker=c['ticker'], entry_time=paper.k2t(c['k']), trend_pct=f"{tr:.2f}", skipped_acct_pct=f"{c['usd'] / 10:.3f}",
                         skipped_reached_2R='yes' if any('take profit' in e[1] for e in c['events']) else 'no', exit_reason=c.get('why') or '',
                         day_acct_pct_in_force=f"{apct:.3f}", note=''))
    if not rows: print(f"{day}: no FADE trade skipped"); return
    fresh = not os.path.exists(OUT)
    with open(OUT, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=HDR, lineterminator='\n')
        if fresh: w.writeheader()
        w.writerows(rows)
    for r in rows: print(f"SKIPPED {r['day']} FADE {r['proxy']} -> {r['ticker']} at {r['entry_time']} (proxy {r['trend_pct']}% in the break direction): would have made {float(r['skipped_acct_pct']):+.2f}% of the account ({r['exit_reason']})")


if __name__ == '__main__':
    main()
