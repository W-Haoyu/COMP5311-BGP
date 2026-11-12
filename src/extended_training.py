#!/usr/bin/env python3
"""Train timestamp-aware per-prefix VP rules on 15 minutes and test later."""
import argparse,collections,csv,json,random,statistics,time
from pathlib import Path
from reconstruction_diagnostics import read_selected
from phase3 import groups,model
from reconstitution_v2 import select_vps,index_predictions,match_count
from heldout_eval import links,stats
ROOT=Path(__file__).resolve().parent.parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['original','coalesced'],default='original');args=ap.parse_args()
    global select_vps,index_predictions
    if args.mode=='coalesced':
        from coalesced_reconstruction import select_vps,index_predictions
    start=time.time();old=json.loads((ROOT/'results/reconstitution_v2_0015/rules.json').read_text());prefixes=sorted(old);wanted=set(prefixes)
    data={};parse={}
    for slot in ('0000','0005','0010','0015','0020','0025'):
        print('Parsing',slot,flush=True);data[slot],parse[slot]=read_selected(ROOT/'data/rrc00'/f'updates.20230901.{slot}.gz',wanted)
    rules={};train_rows=[];models={}
    for idx,p in enumerate(prefixes):
        events=[x for slot in ('0000','0005','0010') for x in data[slot].get(p,[])]
        if not events:continue
        lookup=model(groups(events));selected,pred=select_vps(events,lookup);allvp={s[0] for _,s in events};hit=match_count(events,pred)
        rules[p]={'keep_vps':sorted(selected),'drop_vps':sorted(allvp-set(selected))}
        models[p]=lookup;train_rows.append({'prefix':p,'train_records':len(events),'vp_count':len(allvp),'selected_vps':len(selected),'training_hits':hit,'training_recall':hit/len(events)})
        print(f'Trained {idx+1}/{len(prefixes)} {p}: {len(events)} records, {len(selected)}/{len(allvp)} VPs, recall {hit/len(events):.3f}',flush=True)
    anchor50=set(json.loads((ROOT/'results/topology_anchor/summary.json').read_text())['anchors'])
    anchor35=set(json.loads((ROOT/'results/pipeline/report.json').read_text())['anchors'])
    rows=[]; detail=[]
    for slot in ('0015','0020','0025'):
        ev=sorted(((p,t,s) for p in sorted(rules) for t,s in data[slot].get(p,[])),key=lambda x:(x[1],x[0],x[2]))
        ref=set().union(*(links(sig[1]) for _,_,sig in ev));
        for modelname,anchor in [('no_anchors',set()),('visibility_proxy_35',anchor35),('graph_proxy_50',anchor50)]:
            chosen=[e for e in ev if e[2][0] in anchor or e[2][0] not in rules[e[0]]['drop_vps']]
            m=stats(chosen,len(ref));rng=random.Random(42)
            baselines=[stats(rng.sample(ev,len(chosen)),len(ref))['link_recall'] for _ in range(100)]
            rows.append({'test_slot':slot,'scheme':modelname,'anchors':len(anchor),'records':len(ev),'reference_links':len(ref),'kept_records':len(chosen),'retained_fraction':len(chosen)/len(ev),'links':m['links'],'link_recall':m['link_recall'],'random_mean_link_recall':statistics.fmean(baselines),'random_min_link_recall':min(baselines),'random_max_link_recall':max(baselines)})
        # Per-prefix reconstruction diagnostic uses no anchors; no inferential claims about MOAS.
        total=collections.Counter()
        for p in prefixes:
            actual=data[slot].get(p,[]);drop=set(rules[p]['drop_vps']);allvp={s[0] for _,s in actual};pred=index_predictions(actual,models[p]);predicted=set().union(*(pred.get(v,set()) for v in allvp-drop));hit=match_count(actual,predicted)
            detail.append({'test_slot':slot,'prefix':p,'records':len(actual),'retained':sum(s[0] not in drop for _,s in actual),'hits':hit,'predictions':len(predicted)})
            total.update({'records':len(actual),'hits':hit,'predictions':len(predicted)})
        print(slot,'retained/link recall',[(r['scheme'],round(r['retained_fraction'],3),round(r['link_recall'],3)) for r in rows if r['test_slot']==slot],flush=True)
    out=ROOT/('results/extended_training' if args.mode=='original' else 'results/coalesced_training');out.mkdir(parents=True,exist_ok=True)
    (out/'rules.json').write_text(json.dumps(rules,indent=2)+'\n')
    (out/'metadata.json').write_text(json.dumps({'mode':args.mode,'train_slots':['0000','0005','0010'],'test_slots':['0015','0020','0025'],'parse':parse,'duration_seconds':round(time.time()-start,2),'limitations':'15 minute training, 20 selected IPv4 prefixes, disjoint anchored 100s approximate correlation groups, no cross-prefix stage, excludes withdrawals and non-AS_SEQUENCE paths; proxy anchors based on only 20 prefixes, trained through 00:15. Random prefix-level sampling can split messages. No paper-wide performance claim.'},indent=2)+'\n')
    for name,values in [('training.csv',train_rows),('evaluation.csv',rows),('reconstruction.csv',detail)]:
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=values[0]);w.writeheader();w.writerows(values)
if __name__=='__main__':main()
