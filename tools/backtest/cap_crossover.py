"""At what account size does a liquidity cap start to beat no cap? (same model and impact assumption as scale_500k.py)"""
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import scale_500k as S
print("%/day and profit by starting equity (impact charged, 1x cash max)\n")
print(f"{'account':>10}{'no cap':>10}{'cap 20%':>10}{'cap 10%':>10}{'cap 5%':>10}   avg participation uncapped   best")
for a in (2000, 5000, 10000, 25000, 50000, 75000, 100000, 150000, 250000, 500000, 1000000):
    r = {c: S.account(S.base, a, c) for c in (None, 0.20, 0.10, 0.05)}
    best = max(r, key=lambda c: r[c]['day'])
    print(f"{a:>10,}" + ''.join(f"{r[c]['day']:>+9.3f}%" for c in (None, 0.20, 0.10, 0.05)) + f"{r[None]['avgpart']:>16.1f}%{'':>10}{'none' if best is None else f'{int(best*100)}%'}")
