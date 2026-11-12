#!/usr/bin/env python3
"""Timestamp-aware per-prefix reconstruction prototype; not full GILL."""
import argparse,bisect,collections,csv,json,time
from pathlib import Path
from phase3 import records,groups,model
ROOT=Path(__file__).resolve().parent.parent

def index_predictions(events, lookup):
    by_vp=collections.defaultdict(set)
    for ts,sig in events:
        # The observation itself is always retained. Reconstituted records use
        # the retained observation's timestamp as in the paper's formulation.
        by_vp[sig[0]].add((ts,sig))
        for inferred in lookup.get(sig,()):by_vp[sig[0]].add((ts,inferred))
    return by_vp

def match_count(actual, predicted, slack=100):
    """Maximum one-to-one time matching independently for each signature."""
    aa=collections.defaultdict(list);pp=collections.defaultdict(list)
    for ts,sig in actual:aa[sig].append(ts)
    for ts,sig in predicted:pp[sig].append(ts)
    hit=0
    for sig,times in aa.items():
        x=sorted(times);y=sorted(pp.get(sig,()));i=j=0
        while i<len(x) and j<len(y):
            if y[j]<x[i]-slack:j+=1
            elif y[j]>x[i]+slack:i+=1
            else:hit+=1;i+=1;j+=1
    return hit

def select_vps(events,lookup,target=.94):
    predictions=index_predictions(events,lookup);vps=sorted(predictions);selected=[];current=set();n=len(events)
    while vps:
        scored=[(match_count(events,current|predictions[v]),v) for v in vps]
        best=max(v[0] for v in scored);vp=min(v for score,v in scored if score==best)
        if best<=match_count(events,current):break
        selected.append(vp);vps.remove(vp);current.update(predictions[vp])
        if best/n>=target:break
    return selected,current

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--test-slot',choices=['0015','0020'],default='0015');args=ap.parse_args()
    start=time.time();policy=json.loads((ROOT/'results/pipeline/report.json').read_text());prefixes=sorted(policy['groups'])
    print('Parsing train and holdout...',flush=True)
    train,train_stats=records(ROOT/'data/rrc00/updates.20230901.0000.gz')
    test,test_stats=records(ROOT/'data/rrc00'/f'updates.20230901.{args.test_slot}.gz')
    rows=[];rules={}; totals=collections.Counter()
    for index,prefix in enumerate(prefixes):
        tr=train.get(prefix,[]);te=test.get(prefix,[])
        if not tr:continue
        lookup=model(groups(tr));selected,pred=select_vps(tr,lookup);selected=set(selected)
        train_vps={sig[0] for _,sig in tr}; test_vps={sig[0] for _,sig in te}
        unseen=test_vps-train_vps; keep_vps=selected|unseen
        testpred=index_predictions(te,lookup);prediction=set().union(*(testpred.get(v,set()) for v in keep_vps))
        direct=[(ts,sig) for ts,sig in te if sig[0] in keep_vps]
        hit=match_count(te,prediction);train_hit=match_count(tr,pred)
        rule={v for v in train_vps if v not in selected};rules[prefix]={'keep_vps':sorted(selected),'drop_vps':sorted(rule)}
        row={'prefix':prefix,'train_records':len(tr),'train_vps':len(train_vps),'selected_vps':len(selected),'train_reconstruction_hits':train_hit,'train_recall':train_hit/len(tr),'test_records':len(te),'test_unseen_vps':len(unseen),'test_retained':len(direct),'test_reconstruction_hits':hit,'test_predicted':len(prediction),'test_recall':hit/len(te) if te else None,'test_precision':hit/len(prediction) if prediction else None}
        rows.append(row)
        for k in ('test_records','test_retained','test_reconstruction_hits','test_predicted'):totals[k]+=row[k]
        print(f"{index+1}/{len(prefixes)} {prefix}: train={len(tr)}, holdout={len(te)}",flush=True)
    result={'train_file':'data/rrc00/updates.20230901.0000.gz','test_file':f'data/rrc00/updates.20230901.{args.test_slot}.gz','train_stats':dict(train_stats),'test_stats':dict(test_stats),'prefixes':len(rows),'total':dict(totals),'elapsed_seconds':round(time.time()-start,2),'method':'Approximate correlation groups: disjoint first-update anchored 100-second windows and group signature sets; per update highest-weight matching training group. Greedy per-prefix all-or-none VP selection aims for training recall >=94%. Actual and predicted records are matched one-to-one by identical VP/path/communities and timestamps within 100s; duplicate predictions at identical timestamps collapse. Unseen test VPs are retained by default. IPv4 announcement records only; no withdrawals, cross-prefix stage, anchors, or full GILL.'}
    out=ROOT/'results'/f'reconstitution_v2_{args.test_slot}';out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(out/'rules.json').write_text(json.dumps(rules,indent=2)+'\n')
    with (out/'prefixes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
