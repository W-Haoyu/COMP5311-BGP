#!/usr/bin/env python3
"""Select anchor count on development data, evaluate once on later windows."""
import collections,csv,json,random,statistics
from pathlib import Path
from fast_selected import read_selected_fast
from heldout_eval import links
ROOT=Path(__file__).resolve().parent.parent
GRID=[0,5,10,15,20,25,30,35,40,45,50]

def load(slot,prefixes):
 d,counts=read_selected_fast(ROOT/f'data/rrc00/updates.20230901.{slot}.gz',prefixes)
 ev=[(p,t,s) for p in sorted(prefixes) for t,s in d.get(p,[])]
 if not ev:raise ValueError('no records in '+slot)
 vpmap=collections.defaultdict(list);vplinks=collections.defaultdict(set);reference=set()
 for e in ev:
  vp=e[2][0];vpmap[vp].append(e);ls=links(e[2][1]);vplinks[vp].update(ls);reference.update(ls)
 return ev,vpmap,vplinks,reference,counts

def measure(dataset,rules,anchors,repeats=100):
 ev,vpmap,vplinks,reference,_=dataset
 picked=[e for e in ev if e[2][0] in anchors or e[2][0] not in rules[e[0]]['drop_vps']]
 found=set().union(*(links(e[2][1]) for e in picked));budget=len(picked);vps=sorted(vpmap);rng=random.Random(42);baselines=[];costs=[]
 for _ in range(repeats):
  order=rng.sample(vps,len(vps));used=0;seen=set()
  for vp in order:
   if used+len(vpmap[vp])<=budget:used+=len(vpmap[vp]);seen.update(vplinks[vp])
  baselines.append(len(seen)/len(reference));costs.append(used)
 return {'records':len(ev),'kept':budget,'retained':budget/len(ev),'coverage':len(found)/len(reference),'random_vp_coverage':statistics.fmean(baselines),'random_vp_retained':statistics.fmean(costs)/len(ev),'reference_links':len(reference)}

def main():
 rules=json.loads((ROOT/'results/hour_training/rules_original.json').read_text());prefixes=set(rules)
 order=json.loads((ROOT/'results/topology_anchor/summary.json').read_text())['anchors']
 if len(order)<max(GRID):raise ValueError('anchor ranking too short')
 development={slot:load(slot,prefixes) for slot in ('0100','0110')};rows=[]
 for k in GRID:
  for slot,dataset in development.items():
   row={'phase':'development','slot':slot,'anchor_count':k,**measure(dataset,rules,set(order[:k]))};rows.append(row)
  print('development anchors',k,'coverage',[(r['slot'],round(r['coverage'],3),round(r['retained'],3)) for r in rows if r['anchor_count']==k],flush=True)
 # Fixed before evaluation: >=85% in each development window, then minimum mean volume.
 eligible=[k for k in GRID if all(r['coverage']>=.85 for r in rows if r['anchor_count']==k)]
 if not eligible:raise RuntimeError('No anchor count reaches the prespecified validation target')
 best=min(eligible,key=lambda k:(statistics.fmean(r['retained'] for r in rows if r['anchor_count']==k),k))
 print('Frozen anchor count',best,flush=True)
 for slot in ('0145','0150'):
  dataset=load(slot,prefixes);row={'phase':'holdout','slot':slot,'anchor_count':best,**measure(dataset,rules,set(order[:best]))};rows.append(row)
  print('holdout',slot,'retention',round(row['retained'],3),'coverage',round(row['coverage'],3),'random VP',round(row['random_vp_coverage'],3),flush=True)
 out=ROOT/'results/anchor_sweep';out.mkdir(parents=True,exist_ok=True)
 with (out/'evaluation.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 (out/'selection.json').write_text(json.dumps({'grid':GRID,'minimum_development_coverage_each_window':.85,'selected_count':best,'anchors':order[:best],'development_slots':['0100','0110'],'holdout_slots':['0145','0150'],'random_seed':42,'random_repeats':100,'limitations':'Anchor-count cap is a heuristic and changes paper stopping rule. Graph anchors trained on truncated 20-prefix RIB and six events; 5 prefixes alphabetically selected; one collector/day. Random VP uses test period volume retrospectively to fit upper bound, so it is an offline cost-controlled baseline; actual use may be slightly below cap. Scope is expanded IPv4 prefix announcements, not all updates or global links.'},indent=2)+'\n')
if __name__=='__main__':main()
