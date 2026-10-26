#!/usr/bin/env python3
"""RULEBOOK A1.13 drawdown stop: halt all real trading when total value falls 15% below its all-time high (deposit-adjusted).
State: archive/hwm.json  {"hwm": all-time-high total value, "halted": bool, "halted_at": ..., "events": [...]}
    python3 tools/live/hwm.py check VALUE        # every state check: raises the high if VALUE is a new high; HALTS if VALUE <= 85% of the high
    python3 tools/live/hwm.py deposit AMOUNT     # a deposit (+) or withdrawal (-): moves the high by the same dollars so it is never a drawdown or a fake high
    python3 tools/live/hwm.py clear VALUE        # GOVERNOR ONLY: lift a halt; the high restarts at VALUE
    python3 tools/live/hwm.py status
Exit code 0 = trading allowed, 2 = HALTED (no entries; cancel open orders and sell any position, A1.13).
VALUE is get_portfolio total value at the checkpoint, including the mark of any open position."""
import json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo
F = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'archive', 'hwm.json')
LIMIT = 0.15


def load(): return json.load(open(F))


def save(s): json.dump(s, open(F, 'w'), indent=1); open(F, 'a').write('\n')


def now(): return datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M ET')


def report(s, v=None):
    lvl = s['hwm'] * (1 - LIMIT)
    msg = f"high ${s['hwm']:,.2f}, stop level ${lvl:,.2f} (-{LIMIT:.0%})"
    if v is not None: msg += f", value ${v:,.2f} = {100*(v/s['hwm']-1):+.2f}% from the high"
    print(('DRAWDOWN STOP ACTIVE - NO ENTRIES, FLATTEN (A1.13): ' if s['halted'] else 'drawdown stop clear: ') + msg)
    return 2 if s['halted'] else 0


if __name__ == '__main__':
    s = load(); c = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if c == 'check':
        v = float(sys.argv[2])
        if v > s['hwm']: s['hwm'] = round(v, 2); s['events'].append(f"{now()} new high ${v:,.2f}")
        if not s['halted'] and v <= s['hwm'] * (1 - LIMIT):
            s['halted'] = True; s['halted_at'] = now(); s['events'].append(f"{now()} HALT: value ${v:,.2f} <= {1-LIMIT:.0%} of high ${s['hwm']:,.2f}")
        save(s); sys.exit(report(s, v))
    elif c == 'deposit':
        a = float(sys.argv[2]); s['hwm'] = round(s['hwm'] + a, 2); s['events'].append(f"{now()} deposit/withdrawal {a:+,.2f}: high now ${s['hwm']:,.2f}"); save(s); sys.exit(report(s))
    elif c == 'clear':
        v = float(sys.argv[2]); s.update(hwm=round(v, 2), halted=False); s.pop('halted_at', None); s['events'].append(f"{now()} governor cleared the halt; high restarts at ${v:,.2f}"); save(s); sys.exit(report(s, v))
    else: sys.exit(report(s))
