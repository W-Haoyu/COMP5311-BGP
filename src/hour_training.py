#!/usr/bin/env python3
"""One-hour small-prefix reproduction with original and coalesced variants."""
import collections,csv,json,random,statistics,time
from pathlib import Path
from fast_selected import read_selected_fast
from phase3 import groups,model
import reconstitution_v2 as original
import coalesced_reconstruction as compact
from heldout_eval import links,stats
ROOT=Path(__file__).resolve().parent.parent
TRAIN=tuple(f'00{m:02d}' for m in range(0,60,5));TEST=('0100','0110','0125','0130')

def main():
 start=time.time();source=json.loads((ROOT/'results/reconstitution_v2_0015/rules.json').read_text())
 prefixes=sorted(source)[:5];wanted=set(prefixes);print('Preselected 5 prefixes:',prefixes,flush=True)
 data={};parses={}
 for slot in TRAIN+TEST:
  data[slot],parses[slot]=read_selected_fast(ROOT/'data/rrc00'/f'updates.20230901.{slot}.gz',wanted)
  print('Parsed',slot,parses[slot].get('selected_prefix_announcements',0),flush=True)
 results={};trainrows=[];models={}
 for name,mod in [('original',original),('coalesced',compact)]:
  rules={};lookup_by_prefix={}
  for p in prefixes:
   events=[e for slot in TRAIN for e in data[slot].get(p,[])]
   if not events:raise ValueError(f'No training events: {p}')
   lookup=model(groups(events));chosen,pred=mod.select_vps(events,lookup);allvp={sig[0] for _,sig in events}
   hit=original.match_count(events,pred);rules[p]={'keep_vps':sorted(chosen),'drop_vps':sorted(allvp-set(chosen))};lookup_by_prefix[p]=lookup
   trainrows.append({'variant':name,'prefix':p,'records':len(events),'vps':len(allvp),'selected_vps':len(chosen),'training_hits':hit,'training_recall':hit/len(events)})
   print('Training',name,p,'VPs',len(chosen),'/',len(allvp),'recall',round(hit/len(events),3),flush=True)
  results[name]=rules;models[name]=lookup_by_prefix
 anchors={'none':set(),'visibility35':set(json.loads((ROOT/'results/pipeline/report.json').read_text())['anchors']),'graph50':set(json.loads((ROOT/'results/topology_anchor/summary.json').read_text())['anchors'])}
 evaluation=[];reconstruction=[]
 for slot in TEST:
  ev=sorted(((p,t,s) for p in prefixes for t,s in data[slot].get(p,[])),key=lambda x:(x[1],x[0],x[2]))
  if not ev:raise ValueError('No test events: '+slot)
  ref=set().union(*(links(s[1]) for _,_,s in ev))
  for name,mod in [('original',original),('coalesced',compact)]:
   for anchorname,anchor in anchors.items():
    chosen=[e for e in ev if e[2][0] in anchor or e[2][0] not in results[name][e[0]]['drop_vps']]
    m=stats(chosen,len(ref));rng=random.Random(42);baseline=[stats(rng.sample(ev,len(chosen)),len(ref))['link_recall'] for _ in range(100)]
    evaluation.append({'slot':slot,'variant':name,'scheme':anchorname,'records':len(ev),'kept':len(chosen),'retained_fraction':len(chosen)/len(ev),'reference_links':len(ref),'links':m['links'],'coverage':m['link_recall'],'random_mean_coverage':statistics.fmean(baseline)})
   total=collections.Counter()
   for p in prefixes:
    actual=data[slot].get(p,[]);drop=set(results[name][p]['drop_vps']);candidates=mod.index_predictions(actual,models[name][p]);vs={sig[0] for _,sig in actual}-drop
    predicted=set().union(*(candidates.get(v,set()) for v in vs));hits=original.match_count(actual,predicted)
    total.update({'actual':len(actual),'retained':sum(sig[0] not in drop for _,sig in actual),'predictions':len(predicted),'hits':hits})
   reconstruction.append({'slot':slot,'variant':name,**total,'recall':total['hits']/total['actual'] if total['actual'] else 0,'precision':total['hits']/total['predictions'] if total['predictions'] else 0})
  print('Evaluated',slot,[(x['variant'],round(x['retained_fraction'],3),round(x['coverage'],3)) for x in evaluation if x['slot']==slot and x['scheme']=='none'],flush=True)
 out=ROOT/'results/hour_training';out.mkdir(parents=True,exist_ok=True)
 for name,rows in [('training.csv',trainrows),('evaluation.csv',evaluation),('reconstruction.csv',reconstruction)]:
  with (out/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 for name,rules in results.items():(out/f'rules_{name}.json').write_text(json.dumps(rules,indent=2)+'\n')
 (out/'metadata.json').write_text(json.dumps({'prefixes':prefixes,'training_slots':TRAIN,'development_slots':TEST[:2],'holdout_slots':TEST[2:],'parser_statistics':parses,'elapsed_seconds':round(time.time()-start,2),'limitations':'Only five alphabetically preselected IPv4 prefixes and one collector; training one hour vs paper two days. Both variants share simplified disjoint correlation groups. Coalesced is extra heuristic, not GILL. Proxy anchors 35/50 trained on only 20 prefixes, not paper anchors. Random prefix-level sampling can split messages. No RIB/withdrawals in coverage metrics.'},indent=2)+'\n')
 print('Completed in',round(time.time()-start,2),'seconds')
if __name__=='__main__':main()
