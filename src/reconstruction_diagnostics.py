#!/usr/bin/env python3
"""Compare training horizon and conservative prediction on frozen VP rules."""
import collections,csv,json,time
from pathlib import Path
import mrtparse
from phase3 import groups
from reconstitution_v2 import match_count
ROOT=Path(__file__).resolve().parent.parent

def read_selected(path,wanted):
    events=collections.defaultdict(list);counts=collections.Counter()
    for obj in mrtparse.Reader(str(path)):
        if obj.err:counts['parse_errors']+=1;obj.err=0;continue
        d=obj.data;msg=d.get('bgp_message',{})
        if 2 not in msg.get('type',{}) or not msg.get('nlri'):continue
        prefixes=[f"{n['prefix']}/{n['length']}" for n in msg['nlri'] if f"{n['prefix']}/{n['length']}" in wanted]
        if not prefixes:continue
        attrs=msg.get('path_attributes',[]);paths=[a.get('value',[]) for a in attrs if 2 in a.get('type',{})]
        if len(paths)!=1 or any(2 not in s.get('type',{}) for s in paths[0]):counts['excluded_paths']+=len(prefixes);continue
        pathseq=tuple(str(v) for s in paths[0] for v in s.get('value',[]));com=[]
        for a in attrs:
            t=next(iter(a.get('type',{})),None)
            if t in (8,32):com.extend((t,str(v)) for v in a.get('value',[]))
        sig=(str(d.get('peer_as'))+'@'+str(d.get('peer_ip')),pathseq,tuple(sorted(com)))
        ts=int(next(iter(d['timestamp'])))
        for p in prefixes:events[p].append((ts,sig));counts['selected_prefix_announcements']+=1
    return events,dict(counts)

def confidence_model(events):
    weights=collections.Counter(groups(events));by_sig=collections.defaultdict(list)
    for group,weight in weights.items():
        for sig in group:by_sig[sig].append((weight,group))
    lookup={}
    for sig,options in by_sig.items():
        options.sort(key=lambda v:(-v[0],repr(sorted(v[1]))));total=sum(w for w,_ in options)
        lookup[sig]=(options[0][1],options[0][0]/total,total,len(options))
    return lookup

def predict(events,drop_vps,lookup,threshold):
    out=set();stats=collections.Counter()
    for ts,sig in events:
        if sig[0] in drop_vps:continue
        stats['retained_records']+=1;out.add((ts,sig))
        entry=lookup.get(sig)
        if entry is None:stats['unseen_signature']+=1;continue
        group,confidence,support,options=entry
        if confidence<threshold:stats['below_threshold']+=1;continue
        stats['expanded_triggers']+=1
        for x in group:out.add((ts,x))
    return out,stats

def main():
    start=time.time();rules=json.loads((ROOT/'results/reconstitution_v2_0015/rules.json').read_text());wanted=set(rules)
    data={};parse={}
    for slot in ('0000','0005','0015','0020','0025'):
        print('Parsing',slot,flush=True);data[slot],parse[slot]=read_selected(ROOT/'data/rrc00'/f'updates.20230901.{slot}.gz',wanted)
    rows=[];details=[]
    for horizon,slots in [('5min',('0000',)),('10min',('0000','0005'))]:
        models={p:confidence_model([event for s in slots for event in data[s].get(p,[])]) for p in wanted}
        for slot in ('0015','0020','0025'):
            for threshold in (0.0,.7,.9,1.0):
                total=collections.Counter()
                for p in sorted(wanted):
                    actual=data[slot].get(p,[]);drop=set(rules[p]['drop_vps']);lookup=models[p]
                    prediction,st=predict(actual,drop,lookup,threshold);hits=match_count(actual,prediction)
                    direct,ds=predict(actual,drop,{},1.0);direct_hits=match_count(actual,direct)
                    total.update({'actual':len(actual),'retained':st['retained_records'],'prediction_count':len(prediction),'hits':hits,'direct_hits':direct_hits,'unseen_signature':st['unseen_signature'],'below_threshold':st['below_threshold'],'expanded_triggers':st['expanded_triggers']})
                    details.append({'horizon':horizon,'test_slot':slot,'threshold':threshold,'prefix':p,'actual':len(actual),'hits':hits,'prediction_count':len(prediction),'retained':st['retained_records']})
                n=total['actual'];pr=total['prediction_count'];rows.append({'horizon':horizon,'test_slot':slot,'threshold':threshold,**total,'recall':total['hits']/n if n else 0,'precision':total['hits']/pr if pr else 0,'direct_recall':total['direct_hits']/n if n else 0})
                print(horizon,slot,threshold,'recall',round(total['hits']/n,4),'precision',round(total['hits']/pr,4),flush=True)
    out=ROOT/'results/reconstruction_diagnostics';out.mkdir(parents=True,exist_ok=True)
    for name,values in [('summary.csv',rows),('prefixes.csv',details)]:
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=values[0]);w.writeheader();w.writerows(values)
    (out/'metadata.json').write_text(json.dumps({'parse_counts':parse,'fixed_rules':'results/reconstitution_v2_0015/rules.json','train_slots':['0000','0005'],'test_slots':['0015','0020','0025'],'duration_seconds':round(time.time()-start,2),'note':'Post-hoc confidence threshold is an experimental deviation from paper, not author algorithm. Existing fixed VP selection uses only 0000. Confidence is highest group weight divided by total group weights containing a signature; correlated windows are not independent. 0025 was not used to select thresholds during this run.'},indent=2)+'\n')
if __name__=='__main__':main()
