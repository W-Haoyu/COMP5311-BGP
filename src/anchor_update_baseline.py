#!/usr/bin/env python3
"""Record-level random baseline at frozen anchor sweep budgets."""
import csv,json,random,statistics
from pathlib import Path
from fast_selected import read_selected_fast
from heldout_eval import stats,links
ROOT=Path(__file__).resolve().parent.parent
rules=json.loads((ROOT/'results/hour_training/rules_original.json').read_text());prefixes=set(rules)
anchors=set(json.loads((ROOT/'results/anchor_sweep/selection.json').read_text())['anchors']);rows=[]
for slot in ('0145','0150'):
 d,_=read_selected_fast(ROOT/f'data/rrc00/updates.20230901.{slot}.gz',prefixes)
 events=[(p,t,s) for p in sorted(prefixes) for t,s in d.get(p,[])];ref=set().union(*(links(s[1]) for _,_,s in events))
 picked=[e for e in events if e[2][0] in anchors or e[2][0] not in rules[e[0]]['drop_vps']]
 rng=random.Random(42);sample=[stats(rng.sample(events,len(picked)),len(ref))['link_recall'] for _ in range(100)]
 rows.append({'slot':slot,'retained_records':len(picked),'total_records':len(events),'random_record_mean_coverage':statistics.fmean(sample),'random_record_min_coverage':min(sample),'random_record_max_coverage':max(sample)})
with (ROOT/'results/anchor_sweep/random_record_baseline.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print(json.dumps(rows,indent=2))
