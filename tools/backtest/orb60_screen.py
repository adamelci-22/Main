#!/usr/bin/env python3
"""1-hour ORB continuation (governor 2026-11-12: "add 1 hr orb continuation and keep fade to enter by what it does now so they don't
affect each other"). Box = 9:30-10:30 (12 bars) of each FADE proxy; first 5-minute close beyond it from the 10:30 bar to END enters the
3x leg in the break direction at the next open. FADE (v5.2.45) and PULLBACK (v5.2.46) unchanged.
Three ways to run it with the live book: ALONE; SHARED (one account, one position at a time, earliest entry wins);
IDLE (ORB only on days the live book took no trade). Design on Massive H1, judge on H2 and Robinhood 2026.
    python3 -I tools/backtest/orb60_screen.py > tools/backtest/results/orb60_screen_2026-11-12.txt"""
import itertools, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fade_diag as F, other_systems as OS, entry_fade as EF, fade_setup_exits as FS, pb_exit_screen as PS
PX = F.LIVE


def orb60(ds, ctx, p, d, b, end=36, stop='mid', ex='2r', trend=0.0):
    H = max(x[1] for x in b[:12]); L = min(x[2] for x in b[:12]); mid = (H + L) / 2
    i = ds.idx[d]; pc = ds.bars[p][ds.days[i - 1]][-1][3] if i and ds.days[i - 1] in ds.bars[p] else None
    for j in range(11, end):
        c = b[j][3]; s = 1 if c > H else -1 if c < L else 0
        if not s: continue
        if trend and (pc is None or (c / pc - 1) * 100 * s < trend): return None
        k = j + 1; e = b[k][0]; st_ = mid if stop == 'mid' else (L if s > 0 else H)
        if (e - st_) * s <= 0: return None
        if ex == '2r': x, g, r = OS.run_exit(b, k, s, e, st_, ctx['atr'][p][d])
        elif ex == '100@2r': x, g, r = OS.run_exit(b, k, s, e, st_, ctx['atr'][p][d], tpR=2.0, frac=1.0, chand=0)
        else: x, g, r = OS.run_exit(b, k, s, e, st_, ctx['atr'][p][d], tpR=None, chand=0)
        return OS.fin(d, p, k, x, e, g, r)
    return None


def main():
    FB = EF.blocks(F.P(floor_pct=0.5)); PB = PS.load(); RUN = dict(frac=1 / 3, run=('ema', 20))
    book = [[FS.manage(t, {}) for t in FB[b].E] + [PS.manage(t, RUN) for t in PB[b].E] for b in range(3)]
    base = [F.account(PB[b].ds, PB[b].days, book[b]) for b in range(3)]
    busy = [{x['day'] for x in base[b]['taken']} for b in range(3)]
    print(__doc__.split('\n')[0])
    print('LIVE BOOK v5.2.46: ' + ' | '.join(f"{PB[b].name[:10]} {base[b]['ret']:+7.1f}% DD{base[b]['mdd']:5.1f} n{len(base[b]['taken'])}" for b in range(3)))
    print('columns per block: ALONE total / PF / n | SHARED total (change vs book) DD | IDLE total (change) DD')
    rows = []
    for end, stop, ex, trend in itertools.product((24, 36), ('mid', 'edge'), ('2r', '100@2r', 'hold'), (0.0, 0.5, 1.0)):
        cells = []; ok = True
        for b in range(3):
            B = PB[b]; T = [x for p in PX if p in B.ds.bars for d in B.days if d in B.ds.bars[p] for x in [orb60(B.ds, FB[b].ctx, p, d, B.ds.bars[p][d], end, stop, ex, trend)] if x]
            a = F.account(B.ds, B.days, T); tk = a['taken']
            g = sum(x['acct'] for x in tk if x['acct'] > 0); l = -sum(x['acct'] for x in tk if x['acct'] <= 0)
            sh = F.account(B.ds, B.days, book[b] + T); idl = F.account(B.ds, B.days, book[b] + [x for x in T if x['day'] not in busy[b]])
            if b in (0, 2): ok &= idl['ret'] > base[b]['ret'] and sh['ret'] > base[b]['ret']
            cells.append(f"{B.name[:6]} {a['ret']:+6.1f}% PF{(g / l if l else 9):4.2f} n{len(tk):3d} | SH {sh['ret']:+6.1f}% ({sh['ret'] - base[b]['ret']:+5.1f}) DD{sh['mdd']:4.1f} | ID {idl['ret']:+6.1f}% ({idl['ret'] - base[b]['ret']:+5.1f}) DD{idl['mdd']:4.1f}")
        rows.append((ok, f"to {(570 + 5 * end) // 60}:{(570 + 5 * end) % 60:02d} stop {stop:<4} exit {ex:<6} trend>={trend:.1f}%", cells))
    rows.sort(key=lambda z: -z[0])
    for ok, name, cells in rows: print(f"  {'PASS ' if ok else '     '}{name:<44} " + ' || '.join(cells))
    print(f"  passing (SHARED and IDLE both better on RH and M H2): {sum(r[0] for r in rows)} of {len(rows)}")


if __name__ == '__main__':
    main()
