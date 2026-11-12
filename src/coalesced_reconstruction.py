"""Experimental 100s prediction suppression; not the paper algorithm."""
from collections import defaultdict
from reconstitution_v2 import index_predictions as full_index, match_count

def index_predictions(events,lookup,window=100):
    raw=full_index(events,lookup);direct=defaultdict(set)
    for ts,sig in events:direct[sig[0]].add((ts,sig))
    result={}
    for vp,predictions in raw.items():
        by_sig=defaultdict(list)
        for ts,sig in predictions:by_sig[sig].append(ts)
        compact=set(direct[vp])
        for sig,times in by_sig.items():
            last=None
            for ts in sorted(times):
                if last is None or ts-last>window:
                    compact.add((ts,sig));last=ts
        result[vp]=compact
    return result

def select_vps(events,lookup,target=.94):
    predictions=index_predictions(events,lookup);vps=sorted(predictions);selected=[];current=set();n=len(events)
    while vps:
        scored=[(match_count(events,current|predictions[v]),v) for v in vps]
        best=max(x[0] for x in scored);vp=min(v for hit,v in scored if hit==best)
        if best<=match_count(events,current):break
        selected.append(vp);vps.remove(vp);current.update(predictions[vp])
        if best/n>=target:break
    return selected,current
