import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'exit_lab.py')).read())
import statistics as st, random
V=[("BASELINE: current trail (2x stall)",dict(K=2))]
V+=[(f"trail {k}x stall",dict(K=k)) for k in (1,1.5,3,4,6)]
V+=[("no trail: initial stop, hold to 12:30",dict(K=None))]
V+=[(f"breakeven stop after +{b}%, trail 2x",dict(K=2,be=b)) for b in (0.5,1.0)]
for f in (0.3,0.5,0.7):
    for thr in (0.5,1.0,2.0):
        V.append((f"lock {int(f*100)}% of open gain once +{thr}%, + trail 2x",dict(K=2,lock=(f,thr))))
V+=[(f"lock 50% of open gain once +{thr}% (no trail)",dict(K=None,lock=(0.5,thr))) for thr in (0.5,1.0)]
V+=[(f"take ALL off at +{x}%, trail 2x until then",dict(K=2,tp=x)) for x in (1.0,1.5,2.0,3.0)]
for x in (1.0,1.5,2.0):
    V.append((f"half off at +{x}%, rest trail 2x",dict(K=2,half=x)))
    V.append((f"half off at +{x}%, rest trail 3x",dict(K=2,half=x,half_K=3)))
    V.append((f"half off at +{x}%, rest lock 50%",dict(K=2,half=x,half_K=None,lock=(0.5,x))))
V+=[(f"close at {lbl} instead of 12:30, trail 2x",dict(K=2,end=e)) for lbl,e in (("11:00",89),("11:30",119),("12:00",149))]
res={}
for n,kw in V: res[n]=run(**kw)
base=res[V[0][0]]
dates=sorted(set(t['date'] for t in T)); cut=dates[len(dates)//2]
H1=[i for i,t in enumerate(T) if t['date']<cut]; H2=[i for i,t in enumerate(T) if t['date']>=cut]
def acct(rs): return [r[0]*T[i]['expo'] for i,r in enumerate(rs)]
ba=acct(base)
print(f"{len(T)} real trades, {len(dates)} days; split at {cut} ({len(H1)}/{len(H2)} trades)\n")
print(f"{'exit rule':52} {'avg%pos':>8} {'acct sum':>8} {'win':>4} {'1st':>6} {'2nd':>6} {'worst':>6} {'vs base':>8} {'P(better)':>9}")
rows=[]
for n,rs in res.items():
    a=acct(rs); diffs=[x-y for x,y in zip(a,ba)]
    rng=random.Random(1); p=sum(sum(rng.choice(diffs) for _ in diffs)>0 for _ in range(4000))/4000
    rows.append((sum(a),n,st.mean(r[0] for r in rs),sum(r[0]>0 for r in rs)/len(rs),sum(a[i] for i in H1),sum(a[i] for i in H2),min(r[0] for r in rs),sum(diffs),p))
for tot,n,m,w,h1,h2,wr,d,p in rows:
    print(f"{n:52} {m:+8.3f} {tot:+8.1f} {w:4.0%} {h1:+6.1f} {h2:+6.1f} {wr:+6.1f} {d:+8.1f} {('—' if n.startswith('BASE') else f'{p:.0%}'):>9}")
pk=sum(r[1] for r in base)
print(f"\nCapture: baseline kept {sum(r[0] for r in base):.0f}pp of {pk:.0f}pp total peak reached by 12:30 ({sum(r[0] for r in base)/pk:.0%})")
