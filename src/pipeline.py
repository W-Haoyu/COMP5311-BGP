#!/usr/bin/env python3
"""Small offline GILL-inspired pipeline; see results/pipeline/README.md."""
from collections import Counter, defaultdict
from pathlib import Path
import csv, json, math
from phase3 import records,groups,model,metrics
from experiment import parse

ROOT=Path(__file__).resolve().parent.parent

def choose_anchors(vps, features, volumes, gamma=.1):
    # Prototype: binary event visibility instead of the paper's 15 RIB graph features.
    if not vps: return []
    def dist(a,b):
        return math.sqrt(len(features[a] ^ features[b]))
    distances={(a,b):dist(a,b) for a in vps for b in vps}
    hi=max(distances.values(),default=0)
    score=lambda a,b: 1-distances[a,b]/hi if hi else 1.0
    chosen=[min(vps,key=lambda a:(sum(distances[a,b] for b in vps),a))]
    while len(chosen)<len(vps):
        remaining=[v for v in vps if v not in chosen]
        maximum={v:max(score(v,a) for a in chosen) for v in remaining}
        if all(abs(maximum[v]-1)<1e-12 for v in remaining): break
        candidates=sorted(remaining,key=lambda v:(maximum[v],v))[:max(1,math.ceil(gamma*len(remaining)))]
        chosen.append(min(candidates,key=lambda v:(volumes[v],v)))
    return chosen

def cross_prefix(kept, slack=100):
    # Compare only sets with same VP and attribute multiplicities; require a
    # one-to-one timestamp match for every attribute, within 100 seconds.
    by_vp=defaultdict(list)
    for (vp,prefix),events in kept.items():
        attr=defaultdict(list)
        for ts,path,communities in events: attr[(path,communities)].append(ts)
        by_vp[vp].append((prefix,{k:sorted(v) for k,v in attr.items()}))
    dropped=set()
    for vp,items in by_vp.items():
        representatives=[]
        for prefix,attrs in sorted(items):
            def matches(other):
                return attrs.keys()==other.keys() and all(
                    len(vals)==len(other[key]) and all(abs(a-b)<=slack for a,b in zip(vals,other[key]))
                    for key,vals in attrs.items())
            if any(matches(rep) for rep in representatives): dropped.add((vp,prefix))
            else: representatives.append(attrs)
    return dropped

def apply_policy(vp,prefix,anchors,drops):
    return vp in anchors or (vp,prefix) not in drops

def main():
    out=ROOT/'results/pipeline';out.mkdir(parents=True,exist_ok=True)
    trainpath=ROOT/'data/rrc00/updates.20230901.0000.gz';testpath=ROOT/'data/rrc00/updates.20230901.0010.gz'
    train,st=records(trainpath); print('train parsed', flush=True); test,se=records(testpath); print('test parsed', flush=True)
    volumes=Counter(sig[0] for events in train.values() for _,sig in events)
    candidates=[]
    for p,ev in train.items():
        gs=groups(ev); vps={s[0] for g in gs for s in g}
        if len(gs)>=2 and len(vps)>=2: candidates.append((len(ev),p))
    prefixes=[p for _,p in sorted(candidates,key=lambda z:(-z[0],z[1]))[:20]]
    retained={}; allpairs=set(); groupdata={}; vp_events=defaultdict(set)
    for p in prefixes:
        gs=groups(train[p]); lookup=model(gs); vps=sorted({s[0] for g in gs for s in g}); selected=set()
        for i,g in enumerate(gs):
            for sig in g: vp_events[sig[0]].add((p,i))
        while len(selected)<len(vps):
            nextvp=min((v for v in vps if v not in selected),key=lambda v:(-metrics(gs,selected|{v},lookup)[0],v))
            selected.add(nextvp);hit,_,total=metrics(gs,selected,lookup)
            if total and hit/total>=.94: break
        for ts,sig in train[p]:
            pair=(sig[0],p);allpairs.add(pair)
            if sig[0] in selected: retained.setdefault(pair,[]).append((ts,sig[1],sig[2]))
        groupdata[p]={'groups':len(gs),'unique_groups':len(Counter(gs)),'vps':len(vps),'selected_vps':len(selected)}
    drops=allpairs-set(retained); extra=cross_prefix(retained);drops|=extra
    vps=sorted(vp_events); dimensions=sorted(set().union(*vp_events.values())) if vps else []
    features={v:vp_events[v] for v in vps}
    anchors=choose_anchors(vps,features,{v:volumes[v] for v in vps})
    direct=[]
    for p in prefixes:
        for ts,sig in test.get(p,[]): direct.append((p,ts,sig,apply_policy(sig[0],p,set(anchors),drops)))
    accepted=sum(x[3] for x in direct)
    result={'scope':'20 training-selected prefixes; IPv4 announcements only; historical stream replay, not a BGP session', 'train_prefixes':len(prefixes),'selected_vps':len(vps),'anchor_vps':len(anchors),'trained_drop_pairs':len(drops),'cross_prefix_extra_drop_pairs':len(extra),'test_prefix_announcements':len(direct),'test_accepted':accepted,'test_dropped':len(direct)-accepted,'accepted_fraction':accepted/len(direct) if direct else None,'training_parse':dict(st),'test_parse':dict(se),'groups':groupdata,'anchors':anchors,'drop_pairs':[list(x) for x in sorted(drops)]}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'replay.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['prefix','timestamp','vp','decision']);w.writerows((p,t,s[0],'accept' if ok else 'drop') for p,t,s,ok in direct)
    print(json.dumps({k:v for k,v in result.items() if k not in ('groups','anchors','drop_pairs')},indent=2))
if __name__=='__main__':main()
