"""Best liquidity cap by account size (same model as scale_500k.py; impact is an ASSUMPTION)."""
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import scale_500k as S
caps = (None, 0.50, 0.30, 0.20, 0.15, 0.10, 0.07, 0.05)
print(f"{'account':>10}" + ''.join(f"{('none' if c is None else str(int(c*100))+'%'):>9}" for c in caps) + "   best")
for a in (50000, 100000, 150000, 250000, 500000, 1000000):
    r = {c: S.account(S.base, a, c)['day'] for c in caps}
    b = max(r, key=r.get)
    print(f"{a:>10,}" + ''.join(f"{r[c]:>+9.3f}" for c in caps) + f"   {'none' if b is None else str(int(b*100))+'%'}")
