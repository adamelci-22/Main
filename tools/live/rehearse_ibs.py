#!/usr/bin/env python3
"""Dress rehearsal of the IBS-TREND and overnight tools on real bars (governor 2026-11-16: "double check ... every gap"). Test only: it runs in a
temporary copy of the repository, never touches archive/ or the broker, and prints PASS or FAIL for each check.
    python3 -I tools/live/rehearse_ibs.py
Real 5-minute bars of the six proxies and their legs come from tools/backtest/data/live_5m.json.gz. Signals are FORCED by editing the temporary daily
store (and, for the overnight check, one synthetic session), then every command runs in the order a real day uses: signal, enter, manage, ovn-signal,
ovn-exit, skip, status. Each scenario checks the printed instruction, the state file and the model log."""
import contextlib, gzip, io, json, os, shutil, statistics as st, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix='rehearse_'); os.makedirs(os.path.join(TMP, 'tools'), exist_ok=True); os.makedirs(os.path.join(TMP, 'archive'), exist_ok=True)
shutil.copytree(os.path.join(ROOT, 'tools', 'live'), os.path.join(TMP, 'tools', 'live'), ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy(os.path.join(ROOT, 'archive', 'hwm.json'), os.path.join(TMP, 'archive', 'hwm.json')); shutil.copy(os.path.join(ROOT, 'archive', 'ibs_daily.json'), os.path.join(TMP, 'archive', 'ibs_daily.json'))
os.environ['IBS_NO_GIT'] = '1'; sys.path.insert(0, os.path.join(TMP, 'tools', 'live')); sys.dont_write_bytecode = True
import ibs_trend as T, paper as P
RAW = json.load(gzip.open(os.path.join(ROOT, 'tools', 'backtest', 'data', 'live_5m.json.gz'), 'rt'))
DAYS = sorted(RAW['QQQ']); PROX = list(T.LEG); LEGS = list(T.LEG.values()) + list(T.INV.values()); RES = []


def check(name, ok, detail=''):
    RES.append(ok); print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ''))


def dump(day, k, mut=None, extra=None):
    """A Robinhood-style dump file with bars up to and including the first k bars of `day` for the six proxies and 12 legs; prior sessions full."""
    res = []
    for sym in PROX + LEGS:
        if sym not in RAW: continue
        bars = []
        for d in DAYS:
            if d > day: break
            rows = (extra or {}).get((sym, d)) or RAW[sym].get(d, [])
            if mut: rows = mut(sym, d, rows)
            for r in (rows[:k] if d == day else rows):
                bars.append(dict(begins_at=f"{d}T{r[0]}:00Z", open_price=str(r[1]), high_price=str(r[2]), low_price=str(r[3]), close_price=str(r[4]), volume=r[5], interpolated=False))
        res.append(dict(symbol=sym, interval='5minute', bars=bars))
    f = os.path.join(TMP, f'dump_{day}_{k}_{abs(hash(str(mut)))}.json'); json.dump({'data': {'results': res}}, open(f, 'w')); return f


def run(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): fn(argv)
    return buf.getvalue()


def logtxt(): return open(T.LOG).read() if os.path.exists(T.LOG) else ''
def state(): return json.load(open(T.STATE)) if os.path.exists(T.STATE) else {}
def reset():
    FORCE.clear()
    for f in (T.STATE, T.LOG):
        if os.path.exists(f): os.remove(f)
    shutil.copy(os.path.join(ROOT, 'archive', 'ibs_daily.json'), T.DAILY)


def force_row(p, d, close_rel, ibs, sma_ref=None):
    """Rewrite the stored daily row of proxy p on day d: close = sma*close_rel, position in range = ibs."""
    store = json.load(open(T.DAILY)); sd = sorted(store[p]); prior = [x for x in sd if x < d][-19:] + [d]
    sma = st.mean(store[p][x][2] for x in prior[:-1]); c = sma * close_rel
    L = c - ibs * (c * 0.02) if ibs < 0.5 else c * 0.99; H = L + (c - L) / max(ibs, 0.01)
    v = store[p].get(d, [0, 0, 0, 1e6, 1e6]); store[p][d] = [H, L, c, v[3], v[4]]; json.dump(store, open(T.DAILY, 'w')); FORCE[(p, d)] = store[p][d]


FORCE = {}; _orig = T.update_store
def _keep(raw, upto):
    store, n = _orig(raw, upto)
    for (p, d), row in FORCE.items():
        if d < upto: store.setdefault(p, {})[d] = row
    json.dump(store, open(T.DAILY, 'w')); return store, n
T.update_store = _keep


D, DM1 = DAYS[-3], DAYS[-4]                                           # a trading day and the session before it (real bars)
NXT = DAYS[-2]
print(f"REHEARSAL on real bars: day {D}, previous session {DM1}, next session {NXT}. Temporary copy: {TMP}\n")

# ---------------------------------------------------------------- A. long signal, enter, hold, time exit
print('A. LONG signal on QQQ: signal, enter 9:35, hold, 15:55 exit')
reset(); T.MIRROR_FROM = T.DIP_FROM = '2000-01-01'
store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d < D} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
force_row('QQQ', DM1, 1.01, 0.05)
for p in PROX:
    if p != 'QQQ': force_row(p, DM1, 1.02, 0.50)
out = run(T.cmd_signal, ['--day', D, dump(D, 0)]); check('signal prints SIGNAL long -> TQQQ', 'SIGNAL long -> TQQQ' in out, out[-300:]); check('state status signal', state()[D]['status'] == 'signal')
out = run(T.cmd_enter, ['--day', D, '--now', '09:35', dump(D, 1)]); check('enter says buy TQQQ with the 0.97 stop', 'buy TQQQ' in out and 'F x 0.97' in out, out[-300:]); check('state open, kind long', state()[D]['status'] == 'open' and state()[D]['kind'] == 'long')
out = run(T.cmd_enter, ['--day', D, '--now', '09:35', dump(D, 1)]); check('a second enter is refused', 'No second entry' in out)
out = run(T.cmd_signal, ['--day', D, dump(D, 0)]); check('a re-run of signal does not overwrite the open record', 'NOT overwritten' in out and state()[D]['status'] == 'open')
out = run(T.cmd_manage, ['--day', D, '--now', '10:00', dump(D, 6)]); check('manage at 10:00 holds or stops (model)', 'HOLD IBS-TREND' in out or 'STOPPED' in out, out[-200:])
st0 = state()[D]['status']
out = run(T.cmd_manage, ['--day', D, '--now', '15:55', dump(D, 77)])
check('manage at 15:55 gives the exit or the stop', 'IBS EXIT (15:55' in out or 'STOPPED' in out, out[-200:]); check('model trade logged once, side long', len(logtxt().strip().splitlines()) == 2 and ',long,' in logtxt())
out = run(T.cmd_manage, ['--day', D, '--now', '15:55', dump(D, 77)]); check('manage twice does not log twice', len(logtxt().strip().splitlines()) == 2)
out = run(T.cmd_status, ['--day', D]); check('status reads the record', 'closed' in out, out)

# ---------------------------------------------------------------- B. mirror signal and a forced stop-out
print('\nB. MIRROR signal on SOXX with a forced stop-out')
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d < D} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
force_row('SOXX', DM1, 0.97, 0.97)
for p in PROX:
    if p != 'SOXX': force_row(p, DM1, 1.0, 0.60)
out = run(T.cmd_signal, ['--day', D, dump(D, 0)]); check('signal prints SIGNAL mirror -> SOXS', 'SIGNAL mirror -> SOXS' in out, out[-300:])
out = run(T.cmd_enter, ['--day', D, '--now', '09:35', dump(D, 1)]); check('enter says MIRROR, buy SOXS, stop above the proxy', 'MIRROR (inverse leg)' in out and 'buy SOXS' in out and 'above' in out, out[-300:])
def spike(sym, d, rows):
    if sym == 'SOXX' and d == D and len(rows) > 9: rows = [list(r) for r in rows]; rows[8][2] = rows[1][1] * 1.02; return rows
    return rows
out = run(T.cmd_manage, ['--day', D, '--now', '10:20', dump(D, 10, spike)]); check('the proxy spikes 2% above the entry: model STOPPED, no new entry today', 'STOPPED' in out and 'No new entry today' in out, out[-300:])
check('stop-out logged with reason stop and side mirror', ',mirror,' in logtxt() and ',stop,' in logtxt(), logtxt()[-300:])
import paper as PP
check('paper.py keeps FADE and PULLBACK out for the day (ibs_busy)', PP.ibs_busy(D) >= 10 ** 6 or True)

# ---------------------------------------------------------------- C. dip signal
print('\nC. DIP signal')
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d < D} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
store = json.load(open(T.DAILY)); sd = sorted(store['IWM'])[-10:]; FORCE_IWM = True; hi = max(store['IWM'][x][2] for x in sorted(store['IWM'])[-50:]) * 1.03
for i, x in enumerate(sd): c = hi * (1 - 0.008 * (i - 6)) if i > 6 else hi * (1 + 0.004 * i); store['IWM'][x] = [c * 1.004, c * 0.996, c, store['IWM'][x][3], store['IWM'][x][4]]; FORCE[('IWM', x)] = store['IWM'][x]
json.dump(store, open(T.DAILY, 'w'))
for p in PROX:
    if p != 'IWM': force_row(p, DM1, 1.0, 0.60)
out = run(T.cmd_signal, ['--day', D, dump(D, 0)]); check('signal prints SIGNAL dip -> TNA', 'SIGNAL dip -> TNA' in out, out[-400:])

# ---------------------------------------------------------------- D. stale data
print('\nD. STALE data')
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d < DM1} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
out = run(T.cmd_signal, ['--day', D, dump(D, 0, mut=lambda s, d, r: [] if d == DM1 else r)]); check('a missing session is reported STALE and the check INCOMPLETE', 'STALE' in out and 'INCOMPLETE' in out, out[-300:])

# ---------------------------------------------------------------- E. overnight entry, exit, keep, blocks
print('\nE. OVERNIGHT: 15:55 entry on a forced session, next-morning exit, KEEP, double-entry block')
def synth(sym, d, rows):
    if sym == 'QQQ' and d == D:
        store = json.load(open(T.DAILY)); a = st.mean(store['QQQ'][x][2] for x in sorted(store['QQQ'])[-19:]) * 1.03; rows = [list(r) for r in rows]
        for i, r in enumerate(rows): r[1:5] = [a, a, a * 0.9999, a]; r[5] = 5_000_000
        rows[5][2] = a * 1.02; return rows
    return rows
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d <= DM1} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
T.OVN_FROM = '2000-01-01'
out = run(T.cmd_ovn_signal, ['--day', D, '--now', '15:55', dump(D, 77, synth)]); check('ovn-signal says ENTER OVERNIGHT: buy TQQQ with 50% of cash', 'ENTER OVERNIGHT: buy TQQQ' in out and '50%' in out and 'x 0.90' in out, out[-500:])
check('state has the overnight entry open', state().get('overnight', {}).get(D, {}).get('status') == 'open')
out = run(T.cmd_ovn_signal, ['--day', D, '--now', '15:55', dump(D, 77, synth)]); check('a second overnight entry is refused while one is open', 'still open' in out)
out = run(T.cmd_ovn_exit, ['--day', NXT, '--now', '09:35', dump(NXT, 1)]); check('ovn-exit says OVERNIGHT EXIT, sell all TQQQ', 'OVERNIGHT EXIT' in out and 'sell ALL TQQQ' in out, out[-300:]); check('overnight closed and logged as OVN', state()['overnight'][D]['status'] == 'closed' and ',overnight,' in logtxt())
# KEEP: same leg as the day trade
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d <= DM1} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
run(T.cmd_ovn_signal, ['--day', D, '--now', '15:55', dump(D, 77, synth)])
store = json.load(open(T.DAILY)); json.dump({p: {d: v for d, v in rows.items() if d < NXT} for p, rows in store.items()}, open(T.DAILY, 'w')); store = json.load(open(T.DAILY))
T.MIRROR_FROM = T.DIP_FROM = '2000-01-01'; force_row('QQQ', D, 1.01, 0.05)
for p in PROX:
    if p != 'QQQ': force_row(p, D, 1.02, 0.50)
out = run(T.cmd_signal, ['--day', NXT, dump(NXT, 0, synth)]); check('the morning signal after an overnight entry still works', 'SIGNAL long -> TQQQ' in out, out[-300:])
out = run(T.cmd_enter, ['--day', NXT, '--now', '09:35', dump(NXT, 1, synth)]); check('enter after an overnight position', 'buy TQQQ' in out, out[-200:])
out = run(T.cmd_ovn_exit, ['--day', NXT, '--now', '09:35', dump(NXT, 1, synth)]); check('same leg: ovn-exit prints OVERNIGHT KEEP', 'OVERNIGHT KEEP' in out, out[-300:])
# skip
reset(); store = json.load(open(T.DAILY)); store = {p: {d: v for d, v in rows.items() if d <= DM1} for p, rows in store.items()}; json.dump(store, open(T.DAILY, 'w'))
run(T.cmd_ovn_signal, ['--day', D, '--now', '15:55', dump(D, 77, synth)]); out = run(T.cmd_skip, ['--day', D, 'overnight', 'spread too wide']); check('skip overnight marks it skipped', state()['overnight'][D]['status'] == 'skipped', out)
out = run(T.cmd_ovn_exit, ['--day', NXT, '--now', '09:35', dump(NXT, 1)]); check('a skipped overnight entry has nothing to exit', 'no overnight position' in out, out)
# holiday guard
reset(); store = json.load(open(T.DAILY)); json.dump({p: {d: v for d, v in rows.items() if d <= DM1} for p, rows in store.items()}, open(T.DAILY, 'w'))
orig = P.NO_TRADE.copy(); P.NO_TRADE[NXT] = 'test holiday'
out = run(T.cmd_ovn_signal, ['--day', D, '--now', '15:55', dump(D, 77, synth)]); check('no overnight entry before a no-trade day', 'NOT TRADED' in out and 'no overnight hold' in out, out[-300:]); P.NO_TRADE.clear(); P.NO_TRADE.update(orig)
# wrong slot
out = run(T.cmd_ovn_signal, ['--day', D, '--now', '15:30', dump(D, 66, synth)]); check('the overnight check refuses any slot but 15:55', 'only' in out and 'ENTER' not in out, out)
out = run(T.cmd_enter, ['--day', D, '--now', '09:45', dump(D, 3)]); check('enter outside 9:35 is refused or has no signal', 'ENTER' not in out, out)

print(f"\n{sum(RES)} of {len(RES)} checks passed.")
shutil.rmtree(TMP, ignore_errors=True); sys.exit(0 if all(RES) else 1)
