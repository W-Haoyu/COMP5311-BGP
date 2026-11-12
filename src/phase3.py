#!/usr/bin/env python3
"""Training-cost VP selection and an explicitly simplified correlation model."""
import collections,csv,json,random,time
from pathlib import Path
import mrtparse
from experiment import parse
from multicase import ranking

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results'/'phase3'

def online_simulation():
 rows=[]; meta=[]
 for collector in ['rrc00','rrc01']:
  for train_slot,test_slot in [('0000','0010'),('0100','0110')]:
   name=f'{collector}_{train_slot}_{test_slot}'; print('VP selection:',name,flush=True)
   train,_=parse(ROOT/'data'/collector/f'updates.20230901.{train_slot}.gz')
   test,_=parse(ROOT/'data'/collector/f'updates.20230901.{test_slot}.gz')
   # Select solely among training VPs; test-only VPs may contribute to reference.
   eligible=sorted(train); order=ranking(train,eligible)
   train_total=sum(v['updates'] for v in train.values()); test_total=sum(v['updates'] for v in test.values())
   ref=set().union(*(v['links'] for v in test.values())); rng=random.Random(42)
   meta.append(dict(case=name,train_vps=len(train),test_vps=len(test),reference_links=len(ref),train_updates=train_total,test_updates=test_total))
   for frac in [.05,.1,.2,.4]:
    budget=int(train_total*frac)
    for method,rep,sequence in [('greedy',0,order)]+[('random',i,rng.sample(eligible,len(eligible))) for i in range(100)]:
     chosen=[]; predicted=0
     for p in sequence:
      if predicted+train[p]['updates']<=budget:
       chosen.append(p); predicted+=train[p]['updates']
     actual=sum(test[p]['updates'] for p in chosen if p in test)
     links=set().union(*(test[p]['links'] for p in chosen if p in test))
     rows.append(dict(case=name,method=method,repeat=rep,budget_fraction=frac,train_budget=budget,train_cost=predicted,test_cost=actual,test_fraction=actual/test_total,coverage=len(links)/len(ref),vps=len(chosen)))
 write_csv(OUT/'online_runs.csv',rows)
 (OUT/'online_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')

def write_csv(path,rows):
 if rows:
  with path.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader();w.writerows(rows)

def records(path):
 # One announcement can carry multiple prefixes; count them independently.
 stats=collections.Counter(); events=collections.defaultdict(list)
 for obj in mrtparse.Reader(str(path)):
  if obj.err:
   stats['parse_errors']+=1; obj.err=0; continue
  d=obj.data; msg=d.get('bgp_message',{})
  if 2 not in msg.get('type',{}) or not msg.get('nlri'): continue
  attrs=msg.get('path_attributes',[])
  paths=[a.get('value',[]) for a in attrs if 2 in a.get('type',{})]
  if len(paths)!=1 or any(2 not in s.get('type',{}) for s in paths[0]):
   stats['excluded_paths']+=1;continue
  path_tuple=tuple(str(v) for seg in paths[0] for v in seg.get('value',[]))
  # Include standard and large communities separately.
  comm=[]
  for a in attrs:
   t=next(iter(a.get('type',{})),None)
   if t in (8,32): comm.extend((t,str(v)) for v in a.get('value',[]))
  sig=(str(d.get('peer_as'))+'@'+str(d.get('peer_ip')),path_tuple,tuple(sorted(comm)))
  ts=int(next(iter(d['timestamp'])))
  for n in msg['nlri']:
   p=str(n['prefix'])+'/'+str(n['length']);events[p].append((ts,sig));stats['prefix_announcements']+=1
 return events,stats

def groups(events):
 # Disjoint anchored windows: this is a documented simplified grouping rule.
 groups=[]; current=set(); start=None
 for ts,sig in sorted(events,key=lambda x:x[0]):
  if start is None or ts-start>100:
   if current: groups.append(frozenset(current))
   start=ts;current=set()
  current.add(sig)
 if current: groups.append(frozenset(current))
 return groups

def model(groups_list):
 weights=collections.Counter(groups_list); index=collections.defaultdict(list)
 for g,w in weights.items():
  for sig in g: index[sig].append((w,g))
 # deterministic tie breaking
 return {sig:sorted(lst,key=lambda x:(-x[0],repr(sorted(x[1]))))[0][1] for sig,lst in index.items()}

def reconstruct(g,selected,lookup):
 out=set(s for s in g if s[0] in selected)
 for sig in list(out): out.update(lookup.get(sig,()))
 return out

def metrics(gs,selected,lookup):
 tp=pred=actual=0
 for g in gs:
  out=reconstruct(g,selected,lookup);tp+=len(out&g);pred+=len(out);actual+=len(g)
 return tp,pred,actual

def correlation():
 print('Correlation prototype: rrc00 0000 -> 0010',flush=True)
 train,st=records(ROOT/'data/rrc00/updates.20230901.0000.gz')
 test,se=records(ROOT/'data/rrc00/updates.20230901.0010.gz')
 # Choose prefixes entirely on training activity, requiring >1 VP and >= 2 groups.
 candidates=[]
 for p,ev in train.items():
  gs=groups(ev); vps={s[0] for g in gs for s in g}
  if len(gs)>=2 and len(vps)>=2: candidates.append((len(ev),p))
 candidates.sort(key=lambda x:(-x[0],x[1])); chosen=[p for _,p in candidates[:20]]
 rows=[]; settings=[]
 for p in chosen:
  tr=groups(train[p]); te=groups(test.get(p,[])); lookup=model(tr)
  vps=sorted({s[0] for g in tr for s in g}); selected=set()
  while len(selected)<len(vps):
   base=metrics(tr,selected,lookup)[0]
   best=min((v for v in vps if v not in selected),key=lambda v:(-metrics(tr,selected|{v},lookup)[0],v))
   selected.add(best); tp,_,total=metrics(tr,selected,lookup)
   if total and tp/total>=.94:break
   if tp==base and len(selected)==len(vps):break
  tp,pred,total=metrics(te,selected,lookup)
  retained=sum(1 for g in te for sig in g if sig[0] in selected)
  train_tp,train_pred,train_total=metrics(tr,selected,lookup)
  rows.append(dict(prefix=p,training_records=len(train[p]),training_groups=len(tr),training_vps=len(vps),selected_vps=len(selected),train_recall=train_tp/train_total if train_total else '',test_groups=len(te),test_retained_signatures=retained,test_total_signatures=total,test_true_reconstructed=tp,test_predicted=pred,test_recall=tp/total if total else '',test_precision=tp/pred if pred else ''))
  settings.append({'prefix':p,'vps':sorted(selected)})
 write_csv(OUT/'correlation_prefixes.csv',rows)
 (OUT/'correlation_metadata.json').write_text(json.dumps({'train_file':'rrc00/updates.20230901.0000.gz','test_file':'rrc00/updates.20230901.0010.gz','training':dict(st),'testing':dict(se),'candidate_prefixes':len(candidates),'selected_prefixes':len(chosen),'method':'Simplified: disjoint 100-second anchored windows, IPv4 announcement signatures VP+AS_PATH+standard/large communities; duplicates collapse within window; most frequent training group per signature; greedy per-prefix VP selection aiming for 94% training recall. Predicted set includes observed retained signatures. No cross-prefix component, RIB, withdrawals, rolling filter deployment or full GILL implementation.','selected_vps':settings},indent=2)+'\n')
 print('prefixes',len(chosen),'test signatures',sum(r['test_total_signatures'] for r in rows),flush=True)
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True); start=time.time(); online_simulation();correlation();print('elapsed',round(time.time()-start,1))
