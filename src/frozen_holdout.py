#!/usr/bin/env python3
"""Evaluate frozen extended-training rules on two untouched later windows."""
import argparse,csv,hashlib,json,random,statistics
from pathlib import Path
from reconstruction_diagnostics import read_selected
from heldout_eval import links,stats
ROOT=Path(__file__).resolve().parent.parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--rules',default='results/extended_training/rules.json');ap.add_argument('--output',default='results/frozen_holdout');ap.add_argument('--compare-rules');ap.add_argument('--slots',nargs='+',default=['0030','0035']);args=ap.parse_args()
 rules=json.loads((ROOT/args.rules).read_text());prefixes=set(rules)
 rule_sets={'original':rules}
 if args.compare_rules:
  alternate=json.loads((ROOT/args.compare_rules).read_text())
  if set(alternate)!=prefixes:raise ValueError('rule sets have different prefix scopes')
  rule_sets['coalesced']=alternate
 policies={'no_anchors':set(),'visibility_proxy_35':set(json.loads((ROOT/'results/pipeline/report.json').read_text())['anchors']),'graph_proxy_50':set(json.loads((ROOT/'results/topology_anchor/summary.json').read_text())['anchors'])}
 rows=[];metadata={}
 for slot in args.slots:
  print('Testing',slot,flush=True)
  events_by_prefix,parse=read_selected(ROOT/'data/rrc00'/f'updates.20230901.{slot}.gz',prefixes)
  ev=sorted(((p,t,s) for p in sorted(prefixes) for t,s in events_by_prefix.get(p,[])),key=lambda x:(x[1],x[0],x[2]))
  if not ev:raise ValueError('empty test window')
  reference=set().union(*(links(x[2][1]) for x in ev));metadata[slot]={'parse':parse,'first_timestamp':ev[0][1],'last_timestamp':ev[-1][1]}
  for rule_name,rule in rule_sets.items():
   for name,anchors in policies.items():
    selected=[e for e in ev if e[2][0] in anchors or e[2][0] not in rule[e[0]]['drop_vps']]
    m=stats(selected,len(reference));rng=random.Random(42);samples=[stats(rng.sample(ev,len(selected)),len(reference))['link_recall'] for _ in range(100)]
    rows.append({'slot':slot,'rule_variant':rule_name,'scheme':name,'records':len(ev),'reference_links':len(reference),'kept':len(selected),'retained_fraction':len(selected)/len(ev),'links':m['links'],'link_recall':m['link_recall'],'random_mean_link_recall':statistics.fmean(samples),'random_min_link_recall':min(samples),'random_max_link_recall':max(samples)})
    print(slot,rule_name,name,'keep',round(len(selected)/len(ev),3),'links',round(m['link_recall'],3),'random',round(statistics.fmean(samples),3),flush=True)
 out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
 with (out/'evaluation.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 (out/'metadata.json').write_text(json.dumps({'rules':args.rules,'rules_sha256':hashlib.sha256((ROOT/args.rules).read_bytes()).hexdigest(),'compare_rules':args.compare_rules,'compare_rules_sha256':hashlib.sha256((ROOT/args.compare_rules).read_bytes()).hexdigest() if args.compare_rules else None,'train_slots':['0000','0005','0010'],'test':metadata,'seed':42,'random_repetitions':100,'limitations':'Approximate rules and proxy anchors; selected 20 IPv4 prefixes; independent later time but same day and collector; random records can split messages; excludes withdrawal and RIB in evaluation.'},indent=2)+'\n')
if __name__=='__main__':main()
