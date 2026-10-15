import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pullback as P, manual as m, statistics as st, collections
from lab import get_data
D=get_data(); days=D.days[25:]
s=P.signals(D,days,0.75,41,77,'limit'); a=P.account(s,D,days); T=a['taken']
dl=list(a['daily'].values())
print(f"FULL PERIOD pick config: signals {len(s)}, taken {len(T)}, days {len(days)}, trade-days {sum(1 for v in dl if v!=0)}, avg/day {st.mean(dl):+.3f}%, ret {a['ret']:+.1f}%, maxDD {a['mdd']:.1f}%")
print(f"avg R {st.mean(x['R'] for x in T):+.2f}, avg acct% per trade {st.mean(x['acct_pct'] for x in T):+.3f}, trades/day {len(T)/len(days):.2f}, avg room {st.mean(x['room'] for x in T):.2f}%")
W=[x for x in T if x['usd']>0]; L=[x for x in T if x['usd']<=0]
print(f"winners {len(W)} avg acct {st.mean(x['acct_pct'] for x in W):+.2f}%  losers {len(L)} avg acct {st.mean(x['acct_pct'] for x in L):+.2f}%")
print('exit reasons:',collections.Counter(x['why'] for x in T), ' target(60%) hit:',sum(1 for x in T if x['why']!='stop' or True and False))
# path anatomy
def path(x):
    b=D.bars[x['inst']][x['day']]; e=x['entry']; seg=b[x['k']:x['xbar']+1]
    return (max(c[1] for c in seg)/e-1)*100,(min(c[2] for c in seg)/e-1)*100
cls=collections.defaultdict(list)
for x in T:
    mfe,mae=path(x); x['mfe']=mfe; x['mae']=mae; x['hit_hod']=max(c[1] for c in D.bars[x['inst']][x['day']][x['k']:x['xbar']+1])>=x['sp']['hod']
    if x['usd']>0: c='WIN'
    elif mfe<0.3: c='L1 red from start'
    elif mfe>=x['room']: c='L2 was up >= 1R then lost'
    else: c='L3 small green then lost'
    cls[c].append(x)
for c in sorted(cls):
    v=cls[c]; print(f"  {c:<28} n={len(v):3d} acct%={sum(x['acct_pct'] for x in v):+6.2f} avgMFE={st.mean(x['mfe'] for x in v):+.2f}% avgMAE={st.mean(x['mae'] for x in v):+.2f}% stops={sum(x['why']=='stop' for x in v)} hitHOD={sum(x['hit_hod'] for x in v)}")
print('by proxy:')
g=collections.defaultdict(list)
for x in T: g[m.LEGS[x['inst']][0]+(' bull' if m.LEGS[x['inst']][1]>0 else ' bear')].append(x)
for k in sorted(g): v=g[k]; print(f"  {k:<10} n={len(v):3d} win={100*sum(x['usd']>0 for x in v)/len(v):3.0f}% acct%={sum(x['acct_pct'] for x in v):+6.2f}")
print('by entry hour:')
g=collections.defaultdict(list)
for x in T: g[(x['k']*5+570)//60].append(x)
for k in sorted(g): v=g[k]; print(f"  {k}:00 n={len(v):3d} win={100*sum(x['usd']>0 for x in v)/len(v):3.0f}% acct%={sum(x['acct_pct'] for x in v):+6.2f}")
print('by month:')
g=collections.defaultdict(list)
for x in T: g[x['day'][:7]].append(x)
for k in sorted(g): v=g[k]; print(f"  {k} n={len(v):3d} acct%={sum(x['acct_pct'] for x in v):+6.2f}")
print('pullback length:',{n:(len(v),round(sum(x['acct_pct'] for x in v),2)) for n,v in sorted(collections.defaultdict(list,{}).items())})
g=collections.defaultdict(list)
for x in T: g[x['sp']['pb_len']].append(x)
print('  ',{n:(len(v),round(sum(x['acct_pct'] for x in v),2)) for n,v in sorted(g.items())})
# capture
print(f"winners avg MFE {st.mean(x['mfe'] for x in W):+.2f}% vs avg final {st.mean(x['pct'] for x in W):+.2f}%; losers avg final {st.mean(x['pct'] for x in L):+.2f}%")
# missed fills
sm=P.signals(D,days,0.75,41,77,'market'); print(f"market-entry signals {len(sm)} vs limit {len(s)}; market avg/sig {st.mean(x['pct'] for x in sm):+.3f}%")
# all signals no room filter, room buckets
s0=P.signals(D,days,0.0,41,77,'limit')
for lo,hi in ((0,0.5),(0.5,0.75),(0.75,1.0),(1.0,9)):
    v=[x for x in s0 if lo<=x['room']<hi]; print(f"  room {lo}-{hi}%: n={len(v)} avg/sig={st.mean(x['pct'] for x in v):+.3f}% avgR={st.mean(x['R'] for x in v):+.2f}")
