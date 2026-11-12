#!/usr/bin/env python3
"""Compare old/new update-only rules on identical held-out records."""
import argparse,collections,json,random,statistics
from pathlib import Path
from phase3 import records
from heldout_eval import stats,links
ROOT=Path(__file__).resolve().parent.parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--test-slot',choices=['0015','0020'],default='0015');args=ap.parse_args()
 original=json.loads((ROOT/'results/pipeline/report.json').read_text());rules=json.loads((ROOT/f'results/reconstitution_v2_{args.test_slot}/rules.json').read_text())
 events_by_prefix,parse=records(ROOT/'data/rrc00'/f'updates.20230901.{args.test_slot}.gz')
 events=sorted(((p,t,s) for p in sorted(rules) for t,s in events_by_prefix.get(p,[])),key=lambda e:(e[1],e[0],e[2]))
 if not events:raise RuntimeError('empty heldout set')
 reference=set().union(*(links(s[1]) for _,_,s in events));old_drop={tuple(x) for x in original['drop_pairs']};new_drop={(vp,p) for p,r in rules.items() for vp in r['drop_vps']}
 out={'records':len(events),'reference_links':len(reference),'parse':dict(parse),'methods':{}}
 for name,drop in [('previous_update_only_including_cross_prefix',old_drop),('timestamp_aware_per_prefix',new_drop)]:
  selected=[e for e in events if (e[2][0],e[0]) not in drop];measured=stats(selected,len(reference));measured['retained_fraction']=len(selected)/len(events)
  r=random.Random(42);baseline=[stats(r.sample(events,len(selected)),len(reference))['link_recall'] for _ in range(100)]
  measured['random_same_count_mean_link_recall']=statistics.fmean(baseline)
  out['methods'][name]=measured
 out['limitations']='Old includes cross-prefix deduplication; new has per-prefix rules only. Different budgets; compare each to random at its own exact prefix-level count. IPv4 announcement only, 20 training-selected prefixes. No anchors, RIB or withdrawals in evaluation. Random sample can split BGP messages.'
 path=ROOT/f'results/reconstitution_v2_{args.test_slot}/comparison.json';path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
