"""Backtest of the proposed A1.6 amendment: act on a FADE signal up to ~6 minutes late (one 5-minute bar) with a marketable order, and accept the entry only if
the leg's price is within BAND% of the model price (two-sided). Beyond 6 minutes (2+ bars) the signal is skipped. Stop/target reset from the fill with the same R (B5.2).
Compared: current rule (band 0.5%, effectively 'on time only' for fast moves), proposed band 1.0%, and no band. PULLBACK entries unchanged."""
import hashlib, statistics as st
import late_entry_tests as L
import final_system as FS, mixed as MXD, manual as m, pb_final as PBF
from lab import get_data

def draw(p, d, shares):
    u = int(hashlib.md5(f'{p}{d}'.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for k, sh in enumerate(shares):
        acc += sh
        if u < acc: return k
    return len(shares)

def main():
    D = get_data(); m.rvol = PBF.rvol(D)
    days = [x for x in D.days[1:] if '2026-03-03' <= x <= '2026-10-14']
    f0, p0 = FS.cands(D, days)
    def run(tag, fc, ref=None):
        a = MXD.account(D, days, fc + p0); tk = a['taken']; dl = list(a['daily'].values()); w = 100 * sum(t['usd'] > 0 for t in tk) / len(tk)
        fd = sum(1 for t in tk if t['sys'] == 'FADE')
        print(f"{tag:<58}{len(tk):>5}{fd:>6}{w:>6.0f}%{st.mean(dl):>+9.3f}%{a['ret']:>+9.1f}%{a['mdd']:>6.1f}%{(st.mean(dl)-ref) if ref is not None else 0:>+9.3f}")
        return st.mean(dl)
    print(f"{'':<58}{'trd':>5}{'fade':>6}{'win':>7}{'%/day':>10}{'return':>10}{'DD':>7}{'vs on-time':>11}")
    print("-- every FADE signal arrives exactly one bar (5-6 min) late --")
    base = run('on time (live backtest)', L.fade_cands(D, days, 0, None))
    for band, tag in ((0.5, 'current band 0.5% on the leg'), (1.0, 'PROPOSED band 1.0% on the leg'), (1.5, 'band 1.5%'), (None, 'no band (always enter)')):
        run('  ' + tag, L.fade_cands(D, days, 1, None, band=band), base)
    for dl_, nm in ((2, 'two bars (10-11 min) late'),):
        print(f"-- every FADE signal {nm}: the proposal skips these (beyond 6 min) --")
        run('  proposal: skip (no FADE trades at all)', [], base)
        run('  for reference: enter anyway, no band', L.fade_cands(D, days, dl_, None), base)
    print("-- realistic mix: 55% on time, 35% one bar late, 10% two or more bars late (assigned per setup by hash, same mix for every rule) --")
    shares = (0.55, 0.35, 0.10)
    def mix(band, skip_late):
        def delays(p, d):
            k = draw(p, d, shares)
            if k >= 2: return None if skip_late else 2
            return k
        return L.fade_cands(D, days, 0, None, band=band, delays=delays)
    for band, tag in ((0.5, 'current rule: band 0.5%, skip beyond 6 min'), (1.0, 'PROPOSED: band 1.0%, skip beyond 6 min'), (None, 'no band, skip beyond 6 min'), (None, 'no band, enter even 10 min late')):
        skip = 'beyond' in tag or 'PROPOSED' in tag or 'current' in tag
        run('  ' + tag, mix(band, skip), base)
    print("-- how many setups does each band let through when one bar late? --")
    n = {}
    for band in (0.5, 1.0, 1.5, None):
        c = L.fade_cands(D, days, 1, None, band=band); n[band] = len(c)
    print('  ' + ', '.join(f"band {b if b else 'none'}: {v} of {n[None]} setups" for b, v in n.items()))
main()
