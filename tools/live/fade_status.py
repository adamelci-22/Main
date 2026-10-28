import sys
sys.path.insert(0,'tools/live')
import paper as P
raw=P.load(sys.argv[1:]); day=max(d for s in raw.values() for d in s)
P.apply_tunables(day)      # RULEBOOK D4: the version in force for this day (retest tolerance)
K=(max(m for s in raw.values() if day in s for m in s[day])-570)//5+1
print('last bar starts', P.k2t(K-1))
for p in ['QQQ','SOXX','IWM','XLK','XBI','XLF']:
    b=P.grid(raw[p][day],K); hi=max(x[1] for x in b[:6]); lo=min(x[2] for x in b[:6])
    brk=None
    for i in range(6,min(K,9)):      # 10:00,10:05,10:10 bars
        if b[i][3]>hi: brk=(i,'UP',hi); break
        if b[i][3]<lo: brk=(i,'DOWN',lo); break
    last=b[K-1][3]
    if not brk: print(f"{p:5} box {lo:.2f}-{hi:.2f} last {last:.2f}  NO BREAK by 10:10 bar -> no FADE today"); continue
    i,side,edge=brk; ret=None
    for j in range(i+1,min(K,i+13)):
        tol=P.RETEST_TOL/100; touch=(b[j][2]<=edge*(1+tol)) if side=='UP' else (b[j][1]>=edge*(1-tol))
        inside=(b[j][3]<edge) if side=='UP' else (b[j][3]>edge)
        if touch and inside: ret=(P.k2t(j),'FAILED-RETEST (signal)'); break
        if touch and not inside: ret=(P.k2t(j),'retest HELD (no trade)'); break
    gap=(last/edge-1)*100
    print(f"{p:5} box {lo:.2f}-{hi:.2f} last {last:.2f}  {side}-break at {P.k2t(i)} (edge {edge:.2f}); last is {gap:+.2f}% from edge; window ends {P.k2t(min(i+12,77))}; retest: {ret or 'none yet'}")
