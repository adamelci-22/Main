"""Full backtest of the live system INCLUDING the v5.2.3 FADE late-entry rule (up to one bar / ~6 min late, entry only if the leg is within 1.0% of the model price, skip beyond).
Lateness mixes are assigned per FADE setup by a fixed hash (same draw for every run). PULLBACK entries are limit orders and are unchanged. $2,000 start, 2026-03-03..10-14."""
import io, contextlib, statistics as st, collections
with contextlib.redirect_stdout(io.StringIO()):
    import late_rule_test as R
L = R.L; MXD = R.MXD; FS = R.FS
from lab import get_data
import manual as m, pb_final as PBF
D = get_data(); m.rvol = PBF.rvol(D)
days = [x for x in D.days[1:] if '2026-03-03' <= x <= '2026-10-14']
march = [d for d in days if d < '2026-04-07']; tune = [d for d in days if d >= '2026-04-07']
f0, p0 = FS.cands(D, days)
def fade(shares):
    if shares is None: return [c for c in f0 if c['sys'] == 'FADE']
    def delays(p, d):
        k = R.draw(p, d, shares)
        return None if k >= 2 else k
    return L.fade_cands(D, days, 0, None, band=1.0, delays=delays)
def report(name, fc):
    cs = fc + [c for c in p0 if c['sys'] == 'PB']
    a = MXD.account(D, days, cs); tk = a['taken']; dl = list(a['daily'].values()); h = len(days) // 2
    wins = [t for t in tk if t['usd'] > 0]; losses = [t for t in tk if t['usd'] <= 0]
    streak = best = 0
    for t in sorted(tk, key=lambda t: (t['day'], t['k'])):
        streak = streak + 1 if t['usd'] <= 0 else 0; best = max(best, streak)
    am = MXD.account(D, march, [c for c in cs if c['day'] in set(march)]); at = MXD.account(D, tune, [c for c in cs if c['day'] in set(tune)])
    fdt = [t for t in tk if t['sys'] == 'FADE']; pbt = [t for t in tk if t['sys'] == 'PB']
    print(f"=== {name} ===")
    print(f"  all: {len(tk)} trades ({len(fdt)} FADE, {len(pbt)} PULLBACK), win {100*len(wins)/len(tk):.0f}%, {st.mean(dl):+.3f}%/day, return {a['ret']:+.1f}% ($2,000 -> ${2000*(1+a['ret']/100):,.0f}), max DD {a['mdd']:.1f}%, halves {st.mean(dl[:h]):+.3f} / {st.mean(dl[h:]):+.3f}, longest losing streak {best}")
    print(f"  FADE trades: win {100*sum(t['usd']>0 for t in fdt)/max(len(fdt),1):.0f}%, total ${sum(t['usd'] for t in fdt):+,.0f}   PULLBACK trades: win {100*sum(t['usd']>0 for t in pbt)/max(len(pbt),1):.0f}%, total ${sum(t['usd'] for t in pbt):+,.0f}")
    print(f"  untouched March window: {st.mean(am['daily'].values()):+.3f}%/day ({am['ret']:+.1f}%, DD {am['mdd']:.1f}%)   tuning window: {st.mean(at['daily'].values()):+.3f}%/day ({at['ret']:+.1f}%, DD {at['mdd']:.1f}%)")
    mo = collections.OrderedDict(); eq = 2000.0
    for d in days:
        e0 = eq; eq *= 1 + a['daily'][d] / 100; mo.setdefault(d[:7], [e0, eq])[1] = eq
    print('  months: ' + ', '.join(f"{k[5:]} {100*(v[1]/v[0]-1):+.1f}%" for k, v in mo.items()))
    print()
print("FULL BACKTEST, live system v5.2.3 (FADE + PULLBACK, one position at a time, 3% risk, late-entry rule on)\n")
report('A. every signal on time (the original backtest)', fade(None))
report("B. today's real lateness mix: 93% on time / 7% one bar late / 0% beyond 6 min", fade((0.93, 0.07, 0.0)))
report('C. in-between mix: 80% / 17% / 3% beyond 6 min (skipped)', fade((0.80, 0.17, 0.03)))
report('D. stress mix: 55% / 35% / 10% beyond 6 min (skipped)', fade((0.55, 0.35, 0.10)))
