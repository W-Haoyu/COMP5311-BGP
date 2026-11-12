#!/usr/bin/env python3
"""Retrospectively compare frozen filters to random whole-VP selections."""
import collections,csv,json,random,statistics
from pathlib import Path
from fast_selected import read_selected_fast
from heldout_eval import links,stats
ROOT=Path(__file__).resolve().parent.parent

def main():
 rules={name:json.loads((ROOT/f'results/hour_training/rules_{name}.json').read_text()) for name in ('original','coalesced')};prefixes=set(rules['original'])
 if prefixes!=set(rules['coalesced']):raise ValueError('prefix scopes differ')
 anchors={'none':set(),'visibility35':set(json.loads((ROOT/'results/pipeline/report.json').read_text())['anchors']),'graph50':set(json.loads((ROOT/'results/topology_anchor/summary.json').read_text())['anchors'])}
 rows=[]
 for slot in ('0125','0130'):
  data,counts=read_selected_fast(ROOT/f'data/rrc00/updates.20230901.{slot}.gz',prefixes)
  events=[(p,t,s) for p in sorted(prefixes) for t,s in data.get(p,[])]; vpmap=collections.defaultdict(list)
  for e in events:vpmap[e[2][0]].append(e)
  ref=set().union(*(links(e[2][1]) for e in events));vps=sorted(vpmap)
  for variant in rules:
   for name,anchor in anchors.items():
    selected=[e for e in events if e[2][0] in anchor or e[2][0] not in rules[variant][e[0]]['drop_vps']];budget=len(selected);policy=stats(selected,len(ref));rng=random.Random(42);runs=[]
    for _ in range(100):
     order=rng.sample(vps,len(vps));picked=[];used=0
     for vp in order:
      if used+len(vpmap[vp])<=budget:picked.extend(vpmap[vp]);used+=len(vpmap[vp])
     m=stats(picked,len(ref));runs.append((used,m['link_recall']))
    rows.append({'slot':slot,'variant':variant,'scheme':name,'total':len(events),'filter_records':budget,'filter_retained':budget/len(events),'filter_link_coverage':policy['link_recall'],'random_vp_mean_records':statistics.fmean(x[0] for x in runs),'random_vp_mean_retained':statistics.fmean(x[0] for x in runs)/len(events),'random_vp_mean_link_coverage':statistics.fmean(x[1] for x in runs),'random_vp_min_coverage':min(x[1] for x in runs),'random_vp_max_coverage':max(x[1] for x in runs)})
    print(slot,variant,name,'filter',round(policy['link_recall'],3),'rndVP',round(statistics.fmean(x[1] for x in runs),3),flush=True)
 out=ROOT/'results/hour_training/vp_baselines.csv'
 with out.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
if __name__=='__main__':main()
