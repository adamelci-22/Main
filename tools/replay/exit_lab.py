"""Exit lab: replay exit rules on the REAL 1-minute paths of the 58 live trades (entry fixed).
Live rule (B2): every 5 min, run_high from completed 1-min bars since fill; cand = run_high*(1-2*stall);
move only if live>fill, live>cand, cand-stop >= min_move% of fill. Stop is a resting stop-market."""
import json, csv, glob, math, statistics as st, random
import os, gzip
HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,"data")
REPO=os.path.abspath(os.path.join(HERE,"..",".."))
BARS={tuple(k.split("|")):v for k,v in json.load(gzip.open(os.path.join(DATA,"exit_lab_bars_1m.json.gz"),"rt")).items()}
# ---- daily bars -> per-ticker profile as of trade date (31 prior sessions)
DAILY={k:[tuple(b) for b in v] for k,v in json.load(gzip.open(os.path.join(DATA,"exit_lab_daily.json.gz"),"rt")).items()}
def clamp(x,lo,hi): return max(lo,min(hi,x))
def profile(sym,date):
    rows=[b for b in DAILY[sym] if b[0]<date][-31:]
    mae=[(o-l)/o*100 for _,o,h,l in rows if o>0]; mfe=[(h-o)/o*100 for _,o,h,l in rows if o>0]
    return clamp(0.15*st.median(mfe),0.10,1.0), clamp(0.25*st.median(mae),0.20,1.0), len(rows)
# ---- trades
T=[]
for x in csv.DictReader(open(os.path.join(REPO,'archive','trades.csv'))):
    if x['date_closed']<'2026-09-01': continue
    sym,date=x['instrument'],x['date_closed']
    if (sym,date)==('QBTX','2026-09-08'): continue
    raw=BARS[(sym,date)]
    o=[0]*180;h=[0]*180;l=[0]*180;c=[0]*180;seen=[False]*180
    for ts,bo,bh,bl,bc,bv,ip in raw:
        i=(int(ts[11:13])-13)*60+int(ts[14:16])-30
        if 0<=i<180: o[i],h[i],l[i],c[i],seen[i]=bo,bh,bl,bc,True
    last=None
    for i in range(180):
        if seen[i]: last=c[i]
        elif last is not None: o[i]=h[i]=l[i]=c[i]=last
    hh,mm,_=map(int,x['entry_time_et'].split(':'))
    e0=(hh-9)*60+mm-30
    stall,mmv,n=profile(sym,date)
    pp=float(x['pnl_pct_position']); pa=float(x['pnl_pct_account'])
    expo=abs(pa/pp) if abs(pp)>0.05 else None
    T.append(dict(sym=sym,date=date,o=o,h=h,l=l,c=c,e0=e0,fill=float(x['entry_price']),stop0=float(x['stop_initial']),
                  stall=stall,mm=mmv,actual=pp,expo=expo,acct=pa,n=n))
med=st.median([t['expo'] for t in T if t['expo']])
for t in T: t['expo']=t['expo'] or med
print(f"{len(T)} trades; median exposure {med:.2f}x of account; profile sessions min {min(t['n'] for t in T)}")
# ---- simulator
def sim(t,K=2.0,tp=None,half=None,half_K=None,be=None,lock=None,end=179,mmf=1.0,latency=1,tight_after=None):
    o,h,l,c=t['o'],t['h'],t['l'],t['c']; fill=t['fill']; stop=t['stop0']; rh=fill
    banked=None; pend=[]; peak=fill; Kc=K
    def finish(px):
        r=(px/fill-1)*100
        return (0.5*banked+0.5*r) if banked is not None else r
    for i in range(t['e0']+1,end+1):
        for (ti,ns) in [p for p in pend if p[0]<=i]: stop=max(stop,ns)
        pend=[p for p in pend if p[0]>i]
        if l[i]<=stop: return finish(min(o[i],stop)),peak
        if tp is not None and h[i]>=fill*(1+tp/100): return finish(fill*(1+tp/100)),peak
        if half is not None and banked is None and h[i]>=fill*(1+half/100):
            banked=half; Kc=half_K if half_K else K
        rh=max(rh,h[i]); peak=max(peak,h[i])
        if (i+1)%5==0 and i+1<=end:
            live=c[i]; ns=None
            if Kc:
                cand=math.floor(rh*(1-Kc*t['stall']/100)*100)/100
                if live>fill and live>cand and cand-stop>=t['mm']*mmf/100*fill: ns=cand
            if be is not None and rh>=fill*(1+be/100): ns=max(ns or 0,fill)
            if lock is not None and rh>=fill*(1+lock[1]/100):
                c2=math.floor((fill+lock[0]*(rh-fill))*100)/100
                if c2-stop>=0.0005*fill: ns=max(ns or 0,c2)
            if ns and ns>stop: pend.append((i+1+latency-1,ns))
    return finish(c[end]),peak
def run(**kw):
    out=[]
    for t in T:
        r,p=sim(t,**kw); out.append((r,(p/t['fill']-1)*100))
    return out
