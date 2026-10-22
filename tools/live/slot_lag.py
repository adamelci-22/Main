import re,collections,statistics as st,datetime as dt
f='/root/.claude/projects/-home-user-Main/d6a9e090-9583-566d-9ad1-594794b6be25.jsonl'
txt=open(f).read().replace('\\n','\n').replace('\\"','"')
parts=txt.split('This read was made at ')[1:]
recs=[];seen=set()
for p in parts:
    rd=re.match(r'(\d{4}-\d\d-\d\d)T([\d:]+)',p)
    if not rd: continue
    read=dt.datetime.fromisoformat(rd.group(1)+'T'+rd.group(2))
    for n in re.split(r'--- Notification \d+ of \d+',p)[1:]:
        m=re.search(r'queued at: (\d{4}-\d\d-\d\dT[\d:]+)Z',n); f2=re.search(r'This task fired at \w+ (\d{4}-\d\d-\d\d) ([\d:]+) UTC',n); nm=re.search(r'Fired by routine "(.*?)" \(trigger_id: (trig_\w+)',n)
        if not(m and f2 and nm): continue
        if nm.group(2) in seen: continue
        seen.add(nm.group(2))
        fire=dt.datetime.fromisoformat(f2.group(1)+'T'+f2.group(2)); name=nm.group(1)
        t=re.search(r'(\d{1,2}):(\d\d)\s*(?:ET|AM|PM|am|pm|:)',name) or re.search(r'(\d{1,2}):(\d\d)',name)
        if not t: continue
        h,mi=int(t.group(1)),int(t.group(2))
        if h<8: h+=12
        sched=dt.datetime.fromisoformat(f2.group(1)+'T00:00:00')+dt.timedelta(hours=h+4,minutes=mi)
        bk=bool(re.search('backup',name,re.I)) and 'verification' not in name.lower() and 'BACKUP checkpoint' in n[:3000] or name.lower().startswith('backup')
        recs.append(dict(day=f2.group(1),name=name,slot=f'{h}:{mi:02d}',backup=bk,sched_lag=(fire-sched).total_seconds(),proc=(read-fire).total_seconds()))
print(len(recs),'unique notifications; sample names:',[r['name'] for r in recs[-3:]])
print(collections.Counter(r['name'].split('—')[0].strip()[:12] for r in recs if 'BACKUP' in r['name'].upper()).most_common(3))
bk=[r for r in recs if 'BACKUP' in r['name'].upper() and 'verification' not in r['name'].lower()]
prim=[r for r in recs if r not in bk and 'verification' not in r['name'].lower()]
def stats(rs,key):
    v=sorted(r[key] for r in rs)
    return f"n={len(v):3d} median {st.median(v):5.0f}s mean {st.mean(v):5.0f}s p90 {v[int(.9*(len(v)-1))]:5.0f}s max {v[-1]:5.0f}s"
print('primaries, scheduler lag (fire - scheduled):',stats(prim,'sched_lag'))
print('primaries, delivery to my read (read - fire):',stats(prim,'proc'))
z=lambda s:s.zfill(5)
ent=[r for r in prim if '10:00'<=z(r['slot'])<='12:55']
print('entry window 10:00-12:55 sched lag:',stats(ent,'sched_lag'))
print('entry window share >120s: %.0f%%  >300s: %.0f%%'%(100*sum(r['sched_lag']>120 for r in ent)/len(ent),100*sum(r['sched_lag']>300 for r in ent)/len(ent)))
print('\nby day (entry window)')
for d in sorted({r['day'] for r in ent}):
    rs=[r for r in ent if r['day']==d]; v=[r['sched_lag'] for r in rs]
    print(f" {d} n={len(rs):2d} med {st.median(v):4.0f}s max {max(v):5.0f}s  >2min {sum(x>120 for x in v):2d} >5min {sum(x>300 for x in v):2d} delivery-to-read mean {st.mean(r['proc'] for r in rs):4.0f}s")
print('\nby hour (entry window) mean sched lag:')
byh=collections.defaultdict(list)
for r in ent: byh[z(r['slot'])[:2]].append(r['sched_lag'])
print(' '.join(f"{k}h:{st.mean(v):.0f}s(n{len(v)})" for k,v in sorted(byh.items())))
print('\nworst 10 primaries:')
for r in sorted(prim,key=lambda r:-r['sched_lag'])[:10]: print(f" {r['day']} {r['slot']:>5} lag {r['sched_lag']:5.0f}s read-after-fire {r['proc']:4.0f}s")
if bk: print('\nbackups',stats(bk,'sched_lag'),'| by day',collections.Counter(r['day'] for r in bk))
# missing slots: primaries per day in the entry window
print('\nentry slots (10:00-12:55) received per day, expected 36:')
for d in sorted({r['day'] for r in prim}):
    print(' ',d,sum(1 for r in ent if r['day']==d))

# ---- correlation with my activity / user messages
import json,bisect
ev=[];users=[]
for line in open(f):
    d=json.loads(line); ts=d.get('timestamp')
    if not ts: continue
    t=dt.datetime.fromisoformat(ts.replace('Z','')); 
    if d.get('type') in('assistant','user'): ev.append(t)
    if d.get('type')=='user' and not d.get('toolUseResult') and d.get('turnOrigin') in (None,'human','user') and not d.get('isCompactSummary'):
        m=d.get('message',{}); c=m.get('content') if isinstance(m,dict) else ''
        s=c if isinstance(c,str) else ' '.join(x.get('text','') for x in c if isinstance(x,dict) and x.get('type')=='text') if isinstance(c,list) else ''
        if s and 'task-notification' not in s and 'SYSTEM NOTIFICATION' not in s and 'system-reminder' not in s[:40]: users.append(t)
ev.sort(); users.sort()
print('\nhuman-ish messages found:',len(users))
def busy(t,w=45):
    i=bisect.bisect_left(ev,t-dt.timedelta(seconds=w)); return i<len(ev) and ev[i]<=t   # any assistant/tool event in the w seconds before scheduled time
def user_near(t,mins=10):
    i=bisect.bisect_left(users,t-dt.timedelta(minutes=mins)); return i<len(users) and users[i]<=t
rows=[]
for r in ent:
    h,mi=map(int,r['slot'].split(':')); s=dt.datetime.fromisoformat(r['day']+'T00:00:00')+dt.timedelta(hours=h+4,minutes=mi)
    rows.append((busy(s),user_near(s),r['sched_lag'],r))
for lab,idx in (('session busy at scheduled time',0),('human message in prior 10 min',1)):
    a=[x[2] for x in rows if x[idx]]; b=[x[2] for x in rows if not x[idx]]
    print(f"{lab}: yes n={len(a)} median {st.median(a) if a else 0:.0f}s mean {st.mean(a) if a else 0:.0f}s >300s {sum(x>300 for x in a)} | no n={len(b)} median {st.median(b):.0f}s mean {st.mean(b):.0f}s >300s {sum(x>300 for x in b)}")
# does lag of slot k correlate with lag of previous slot (persistence)?
import itertools
byd=collections.defaultdict(list)
for r in sorted(ent,key=lambda r:(r['day'],z(r['slot']))): byd[r['day']].append(r['sched_lag'])
pairs=[(a,b) for v in byd.values() for a,b in zip(v,v[1:])]
xs=[p[0] for p in pairs]; ys=[p[1] for p in pairs]
mx,my=st.mean(xs),st.mean(ys); cov=sum((x-mx)*(y-my) for x,y in pairs)/len(pairs)
print('lag autocorrelation slot->next slot: %.2f'%(cov/(st.pstdev(xs)*st.pstdev(ys))))
# does a long-lag slot make the NEXT slots late (batch)?
big=[(d,i) for d,v in byd.items() for i,x in enumerate(v) if x>300]
print('slots >300s:',len(big))
nxt=[byd[d][i+1] for d,i in big if i+1<len(byd[d])]; print('lag of the slot right after a >300s one: median %.0f mean %.0f'%(st.median(nxt),st.mean(nxt)))
# time-of-day UTC for >300s events
print('>300s events:',sorted((r['day'][5:],r['slot']) for r in ent if r['sched_lag']>300))
print('\nmean / p90 / share>300s by minute-of-hour (entry window):')
bm=collections.defaultdict(list)
for r in ent: bm[int(r['slot'].split(':')[1])].append(r['sched_lag'])
for k in sorted(bm): v=sorted(bm[k]); print(f" :{k:02d} n={len(v):2d} mean {st.mean(v):4.0f}s median {st.median(v):4.0f}s p90 {v[int(.9*(len(v)-1))]:4.0f}s >300s {sum(x>300 for x in v)}")
print('\nby UTC clock minute of the scheduled time (share of the 21 late slots by slot):')
print('backups vs primaries on 10-22 for the same slots (primary slot, lag, its backup lag):')
pb={r['slot']:r['sched_lag'] for r in ent if r['day']=='2026-10-22'}
for b in sorted(bk,key=lambda r:z(r['slot'])):
    h,mi=map(int,b['slot'].split(':')); ps=f"{h}:{(mi-2):02d}"
    if ps in pb: print(f"  {ps:>5} primary +{pb[ps]:4.0f}s   backup(+2min) fired +{b['sched_lag']:4.0f}s after ITS time -> {b['sched_lag']-120+120:4.0f}")
