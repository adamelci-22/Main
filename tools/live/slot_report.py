#!/usr/bin/env python3
"""Slot success-rate report for the waiter system (RULEBOOK D1, v5.2.12).
    python3 tools/live/slot_report.py [--from 2026-10-23] [--session /root/.claude/projects/.../<session>.jsonl]
Sources: archive/waiter_log.csv (the waiter's own fire time) and the session transcript (when I saw each waiter wake, and every
scheduled primary that fired). Per trading day and slot 10:00-12:55 (the entry window; 13:00-13:25 are deleted by the early shutdown) it computes the first wake = the earlier of the waiter and the
scheduled primary, and compares it with the scheduler-only baseline (median 62 s, p90 164 s, 2026-10-09..22, slot_lag.py).
"""
import argparse, csv, collections, datetime as dt, glob, json, os, re, statistics as st
ap = argparse.ArgumentParser(); ap.add_argument('--from', dest='start', default='2026-10-23'); ap.add_argument('--session'); a = ap.parse_args()
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sess = a.session or max(glob.glob('/root/.claude/projects/-home-user-Main/*.jsonl'), key=os.path.getmtime)
def utc(s): return dt.datetime.fromisoformat(s.replace('Z', '')).replace(tzinfo=dt.timezone.utc).timestamp()
def off(day): return 4 if day <= '2026-11-01' else 5
slots = [f'{h}:{m:02d}' for h in range(10, 14) for m in range(0, 60, 5) if '10:00' <= f'{h:02d}:{m:02d}' <= '12:55']
due = lambda day, slot: (dt.datetime.fromisoformat(day + 'T00:00:00').replace(tzinfo=dt.timezone.utc) + dt.timedelta(hours=int(slot.split(':')[0]) + off(day), minutes=int(slot.split(':')[1]))).timestamp()
W = collections.defaultdict(dict)                      # waiter fire
for r in csv.DictReader(open(os.path.join(root, 'archive', 'waiter_log.csv'))):
    if r['date'] >= a.start: W[r['date']][r['slot']] = float(r['fired_epoch']) - float(r['due_epoch'])
S = collections.defaultdict(dict); SEEN = collections.defaultdict(dict)   # scheduled primary lag, waiter wake-seen lag
txt = open(sess).read()
for line in txt.split('\n'):
    if '"timestamp"' not in line: continue
    try: d = json.loads(line)
    except Exception: continue
    t = d.get('timestamp'); s = json.dumps(d.get('message', ''))
    m = re.search(r'Background command \\?"Slot waiter (\d+:\d\d)\\?" completed', s)
    if m and t:
        day = (dt.datetime.fromtimestamp(utc(t), dt.timezone.utc) - dt.timedelta(hours=4)).strftime('%F')
        if day >= a.start: SEEN[day][m.group(1)] = utc(t) - due(day, m.group(1))
    m = re.search(r'This task fired at \w+ (\d{4}-\d\d-\d\d) ([\d:]+) UTC.*?Fired by routine \\?"Checkpoint (\d+:\d\d) ET', s)
    if m and m.group(1) >= a.start and m.group(3).zfill(5) >= '10:00' and m.group(3).zfill(5) <= '12:55':
        day, slot = m.group(1), m.group(3)
        S[day][slot] = utc(day + 'T' + m.group(2)) - due(day, slot) if True else 0
days = sorted(set(W) | set(S) | set(SEEN))
if not days: print(f'no data from {a.start} yet'); raise SystemExit
rows = []
for d in days:
    for sl in slots:
        w, sc, sn = W[d].get(sl), S[d].get(sl), SEEN[d].get(sl)
        cands = [x for x in (sn if sn is not None else w, sc) if x is not None]
        first = min(cands) if cands else None
        who = 'missed' if first is None else ('waiter' if (sn if sn is not None else w) is not None and (sc is None or (sn if sn is not None else w) <= sc) else 'scheduled (fallback)')
        rows.append((d, sl, w, sn, sc, first, who))
def pct(v, p): v = sorted(v); return v[int(p * (len(v) - 1))]
print(f'SLOT REPORT {days[0]}..{days[-1]} ({len(days)} trading day(s), {len(rows)} slots 10:00-12:55)  [baseline scheduler only: median 62 s, p90 164 s, 6% over 300 s]\n')
fw = [r[5] for r in rows if r[5] is not None]
print(f'covered by a waiter or a scheduled primary: {len(fw)} of {len(rows)} ({100*len(fw)/len(rows):.1f}%)   missed outright: {sum(r[6]=="missed" for r in rows)}')
print(f'waiter fired (own clock): {sum(r[2] is not None for r in rows)} of {len(rows)} slots   saw the wake: {sum(r[3] is not None for r in rows)}')
if fw: print(f'first-wake lag after the slot: median {st.median(fw):.0f}s  p90 {pct(fw, .9):.0f}s  max {max(fw):.0f}s   over 15 s: {100*sum(x>15 for x in fw)/len(fw):.1f}%   over 60 s: {100*sum(x>60 for x in fw)/len(fw):.1f}%   over 300 s: {100*sum(x>300 for x in fw)/len(fw):.1f}%')
sn = [r[3] for r in rows if r[3] is not None]
if sn: print(f'waiter wake seen by me: median {st.median(sn):.0f}s  p90 {pct(sn, .9):.0f}s  max {max(sn):.0f}s   (waiter is due +6 s)')
sc = [r[4] for r in rows if r[4] is not None]
if sc: print(f'scheduled primaries that still fired (not deleted): {len(sc)}  median lag {st.median(sc):.0f}s  max {max(sc):.0f}s')
print(f'who woke first: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter(r[6] for r in rows).items()))
print('\nper day:   covered  waiter-first  fallback  missed  worst first-wake s')
for d in days:
    rs = [r for r in rows if r[0] == d]; f = [r[5] for r in rs if r[5] is not None]
    print(f' {d}  {len(f):3d}/{len(rs)}   {sum(r[6]=="waiter" for r in rs):6d}   {sum(r[6].startswith("sched") for r in rs):6d}   {sum(r[6]=="missed" for r in rs):5d}   {max(f) if f else 0:8.0f}')
ok = len(days) >= 10 and not any(r[6] == 'missed' for r in rows) and fw and pct(fw, .9) <= 20 and sum(r[6].startswith('sched') for r in rows) <= 0.02 * len(rows)
print(f"\nDELETE-THE-SCHEDULED-PRIMARIES CRITERIA (>=10 trading days, 0 missed slots, p90 first wake <= 20 s, fallback used <= 2% of slots): {'MET' if ok else 'NOT YET MET'}")
