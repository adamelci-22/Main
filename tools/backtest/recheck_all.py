"""Second-look checks on the proposals: (1) are the late-entry results robust to WHICH setups happen to be late (20 random assignments)?
(2) the A3 widening, tested directly: a blocked/skipped FADE entry leaves a 'ghost' model position that hides later signals (current rule) vs the account being free (proposed).
(3) does the liquidity-cap conclusion survive different market-impact assumptions?"""
import io, contextlib, hashlib, math, random, statistics as st, collections
with contextlib.redirect_stdout(io.StringIO()):
    import late_rule_test as R
    import scale_500k as S
L = R.L; MXD = R.MXD; FS = R.FS; D = S.D; days = S.days; f0, p0 = S.f0, S.p0
import twobar as TB

def draw(p, d, shares, salt):
    u = int(hashlib.md5(f'{salt}{p}{d}'.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for k, sh in enumerate(shares):
        acc += sh
        if u < acc: return k
    return len(shares)
def pct(a): return st.mean(a['daily'].values())

# ---------------------------------------------------------------- 1. robustness to which setups are late
print("1. ROBUSTNESS: 20 different random assignments of which setups are late (same mix each time)\n")
print(f"{'mix (on time / 1 bar / 2+ bars)':<34}{'rule':<24}{'mean %/day':>11}{'std':>8}{'min':>8}{'max':>8}")
for shares in ((0.93, 0.07, 0.0), (0.80, 0.17, 0.03), (0.55, 0.35, 0.10)):
    res = {}
    for band, name in ((0.5, 'current 0.5% band'), (1.0, 'proposed 1.0% band'), (None, 'no band')):
        v = []
        for salt in range(20):
            def delays(p, d, salt=salt):
                k = draw(p, d, shares, salt)
                return None if k >= 2 else k
            fc = L.fade_cands(D, days, 0, None, band=band, delays=delays)
            v.append(pct(MXD.account(D, days, fc + p0)))
        res[name] = v
        print(f"{str(shares):<34}{name:<24}{st.mean(v):>+11.3f}{st.pstdev(v):>8.3f}{min(v):>+8.3f}{max(v):>+8.3f}")
    wins = sum(a >= b for a, b in zip(res['proposed 1.0% band'], res['current 0.5% band']))
    print(f"   proposed >= current in {wins} of 20 draws\n")

# ---------------------------------------------------------------- 2. A3 widening: ghost position vs free account
print("2. A3 WIDENING, tested directly: when a FADE entry is blocked, does the model's ghost position hide later signals?\n")
ontime = {(c['day'], c['proxy']): c for c in f0 if c['sys'] == 'FADE'}
late1 = {(c['day'], c['proxy']): c for c in L.fade_cands(D, days, 1, None, band=1.0)}
def account(items, start=2000.0, risk=0.03):
    """items: dict(day, mk, mx, real=None|(k,xbar,pct,risk), proxy, sys). Model timeline (mk,mx) decides what is 'busy'; real P&L only if real is not None."""
    by = collections.defaultdict(list)
    for it in items: by[it['day']].append(it)
    eq = start; dl = []; n = 0
    for d in days:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: (c['mk'], -TB.rvol(D, c['proxy'], d, c['mk']))); free = 0; k = 0
        for it in day:
            if k >= 3: break
            if it['mk'] < free: continue
            free = it['mx'] + 1; k += 1
            if it['real'] is not None:
                _, _, p, r = it['real']; eq += min(eq, eq * risk / (r / 100)) * p / 100; n += 1
        dl.append((eq / e0 - 1) * 100)
    return n, st.mean(dl), (eq / start - 1) * 100
def build(shares, salt, ghost):
    items = []
    for c in p0: items.append(dict(day=c['day'], mk=c['k'], mx=c['xbar'], proxy=c['proxy'], real=(c['k'], c['xbar'], c['pct'], c['risk'])))
    for key, c in ontime.items():
        k = draw(key[1], key[0], shares, salt)
        real = None
        if k == 0: real = (c['k'], c['xbar'], c['pct'], c['risk'])
        elif k == 1 and key in late1: x = late1[key]; real = (x['k'], x['xbar'], x['pct'], x['risk'])
        if ghost: items.append(dict(day=key[0], mk=c['k'], mx=c['xbar'], proxy=key[1], real=real))
        elif real is not None: items.append(dict(day=key[0], mk=real[0], mx=real[1], proxy=key[1], real=real))
    return items
print(f"{'mix (on time / 1 bar / 2+ bars)':<34}{'handling':<44}{'mean %/day':>11}{'min':>8}{'max':>8}")
for shares in ((1.0, 0.0, 0.0), (0.93, 0.07, 0.0), (0.80, 0.17, 0.03), (0.55, 0.35, 0.10)):
    for ghost, name in ((True, 'CURRENT A3: blocked trade leaves a ghost position'), (False, 'PROPOSED: account free after a blocked trade')):
        v = [account(build(shares, s, ghost))[1] for s in range(20)]
        print(f"{str(shares):<34}{name:<44}{st.mean(v):>+11.3f}{min(v):>+8.3f}{max(v):>+8.3f}")
print()

# ---------------------------------------------------------------- 3. liquidity cap vs impact assumption
print("3. LIQUIDITY CAP: best cap by account size under different market-impact assumptions (impact = k x 0.5% x sqrt(participation) per side; k=1 is the base case)\n")
def acct_scaled(cs, start, cap, k):
    by = collections.defaultdict(list)
    for c in cs: by[c['day']].append(c)
    eq = start; dl = []
    for d in days:
        e0 = eq; day = sorted(by.get(d, []), key=lambda c: c['k']); free = 0; n = 0
        while day and n < 3:
            av = [c for c in day if c['k'] >= free]
            if not av: break
            k0 = min(c['k'] for c in av); same = [c for c in av if c['k'] == k0]
            same.sort(key=lambda c: -TB.rvol(D, c['proxy'], d, c['k'])); c = same[0]
            notional = min(eq, eq * 0.03 / (c['risk'] / 100)); part = 0.0
            if c['vol']:
                if cap: notional = min(notional, cap * c['vol'])
                part = notional / c['vol']
            imp = 2 * k * 0.5 * math.sqrt(part)
            eq += notional * (c['pct'] - imp) / 100; free = c['xbar'] + 1; day.remove(c); n += 1
        dl.append((eq / e0 - 1) * 100)
    return st.mean(dl)
caps = (None, 0.50, 0.30, 0.20, 0.10, 0.05)
print(f"{'impact k':>9}{'account':>11}" + ''.join(f"{('none' if c is None else str(int(c*100))+'%'):>9}" for c in caps) + "   best")
for k in (0.5, 1.0, 2.0):
    for a in (50000, 100000, 250000, 500000):
        r = {c: acct_scaled(S.base, a, c, k) for c in caps}; b = max(r, key=r.get)
        print(f"{k:>9}{a:>11,}" + ''.join(f"{r[c]:>+9.3f}" for c in caps) + f"   {'none' if b is None else str(int(b*100))+'%'}")
