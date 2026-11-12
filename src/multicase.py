#!/usr/bin/env python3
"""Multi-window exploratory VP experiment; test-budget matching is retrospective."""
import csv, json, random, statistics, time
from pathlib import Path
from experiment import parse

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results'/'multicase'
REPEATS=100
FRACTIONS=(.05,.1,.2,.4)

def ranking(train, eligible):
    remaining=set(eligible); covered=set(); ordered=[]
    while remaining:
        p=min(remaining,key=lambda v:(-len(train[v]['links']-covered)/max(1,train[v]['updates']),v))
        ordered.append(p); covered.update(train[p]['links']); remaining.remove(p)
    return ordered

def pick(order,test,budget):
    selected=[]; used=0; links=set()
    for p in order:
        cost=test[p]['updates']
        if used+cost<=budget:
            selected.append(p); used+=cost; links.update(test[p]['links'])
    return selected,used,links

def main():
    OUT.mkdir(parents=True,exist_ok=True); all_rows=[]; summaries=[]; started=time.time()
    for collector in ['rrc00','rrc01']:
        for start,end in [('0000','0010'),('0100','0110')]:
            case=collector+'_'+start+'_'+end; print('Running',case,flush=True)
            directory=ROOT/'data'/collector
            train,tc=parse(directory/f'updates.20230901.{start}.gz')
            test,ec=parse(directory/f'updates.20230901.{end}.gz')
            eligible=sorted(set(train)&set(test)); order=ranking(train,eligible)
            reference=set().union(*(v['links'] for v in test.values()))
            total=sum(v['updates'] for v in test.values())
            assert eligible and reference and total
            summaries.append({'case':case,'train_counts':dict(tc),'test_counts':dict(ec),'train_vps':len(train),'test_vps':len(test),'common_vps':len(eligible),'reference_links':len(reference),'test_updates':total})
            rng=random.Random(42)
            for frac in FRACTIONS:
                budget=int(total*frac)
                for method,repeat,seq in [('greedy',0,order)]+[('random',i,rng.sample(eligible,len(eligible))) for i in range(REPEATS)]:
                    selected,used,links=pick(seq,test,budget)
                    assert used <= budget and links <= reference
                    all_rows.append({'case':case,'budget_fraction':frac,'budget_updates':budget,'method':method,'repeat':repeat,'selected_vps':len(selected),'updates':used,'actual_update_fraction':used/total,'links':len(links),'coverage':len(links)/len(reference)})
    with (OUT/'runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=all_rows[0]); w.writeheader(); w.writerows(all_rows)
    summaryrows=[]
    for case in [s['case'] for s in summaries]:
        for frac in FRACTIONS:
            g=next(x for x in all_rows if x['case']==case and x['budget_fraction']==frac and x['method']=='greedy')
            r=[x for x in all_rows if x['case']==case and x['budget_fraction']==frac and x['method']=='random']
            vals=sorted(x['coverage'] for x in r)
            summaryrows.append({'case':case,'budget_fraction':frac,'greedy_update_fraction':g['actual_update_fraction'],'greedy_coverage':g['coverage'],'random_mean_update_fraction':statistics.mean(x['actual_update_fraction'] for x in r),'random_mean_coverage':statistics.mean(vals),'random_p05_coverage':vals[4],'random_p95_coverage':vals[94]})
    with (OUT/'comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=summaryrows[0]);w.writeheader();w.writerows(summaryrows)
    (OUT/'metadata.json').write_text(json.dumps({'seed':42,'repeats':REPEATS,'cases':summaries,'elapsed_seconds':round(time.time()-started,2),'budget_note':'Retrospective test-period VP counts used to enforce common caps; not deployable online. Actual usage can differ below cap.'},indent=2)+'\n')
    print(json.dumps(summaries,indent=2)); print('elapsed',round(time.time()-started,2))
if __name__=='__main__':main()
