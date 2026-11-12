#!/usr/bin/env python3
"""Evaluate frozen, approximate rules and anchors on a subsequent MRT file."""
import argparse,collections,csv,json,math,random,statistics,time
from pathlib import Path
from phase3 import records
from pipeline import apply_policy

ROOT=Path(__file__).resolve().parent.parent

def links(path):
    seq=[]
    for asn in path:
        if not seq or asn!=seq[-1]:seq.append(asn)
    return {tuple(sorted((a,b),key=int)) for a,b in zip(seq,seq[1:]) if a!=b and a.isdigit() and b.isdigit()}

def stats(events, reference):
    e=list(events);found=set();prefixes=set();paths=set();origins=set();vps=set()
    for prefix,ts,sig in e:
        vp,path,community=sig;found.update(links(path));prefixes.add(prefix);paths.add((prefix,path));vps.add(vp)
        if path:origins.add((prefix,path[-1]))
    return {'records':len(e),'links':len(found),'link_recall':len(found)/reference if reference else 0,'prefixes':len(prefixes),'prefix_path_pairs':len(paths),'prefix_origin_pairs':len(origins),'vps':len(vps)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repeats',type=int,default=100);ap.add_argument('--seed',type=int,default=42);ap.add_argument('--test-slot',choices=['0015','0020'],default='0015');ap.add_argument('--output',default='results/heldout');args=ap.parse_args()
    if args.repeats<1:ap.error('--repeats must be positive')
    p=json.loads((ROOT/'results/pipeline/report.json').read_text());a=json.loads((ROOT/'results/topology_anchor/summary.json').read_text());
    anchors=set(a['anchors']);drops={tuple(pair) for pair in p['drop_pairs']};prefixes=set(p['groups'])
    input_path=ROOT/'data/rrc00'/f'updates.20230901.{args.test_slot}.gz'; print('Parsing held-out',args.test_slot,'UTC file...',flush=True)
    start=time.time();by_prefix,counts=records(input_path)
    events=sorted(((prefix,ts,sig) for prefix in sorted(prefixes) for ts,sig in by_prefix.get(prefix,[])),key=lambda x:(x[1],x[0],x[2]))
    if not events:raise RuntimeError('no selected IPv4 announcements in test file')
    train_end=max(e['end'] for e in a['selected_events']); test_start=events[0][1]
    if test_start<=train_end:raise ValueError('test data overlaps anchor training events')
    union=set().union(*(links(sig[1]) for _,_,sig in events));ref=len(union)
    chosen=[e for e in events if apply_policy(e[2][0],e[0],anchors,drops)]
    g=stats(chosen,ref);full=stats(events,ref);rng=random.Random(args.seed);random_rows=[]
    ablations={}
    for name,anchor_set in [('update_only',set()),('previous_proxy_anchors',set(p['anchors'])),('graph_proxy_anchors',anchors)]:
        kept=[e for e in events if apply_policy(e[2][0],e[0],anchor_set,drops)]
        measured=stats(kept,ref); measured['retained_fraction']=len(kept)/len(events);measured['anchor_count']=len(anchor_set)
        baseline=[]; ab_rng=random.Random(args.seed)
        for _ in range(args.repeats):baseline.append(stats(ab_rng.sample(events,len(kept)),ref)['link_recall'])
        measured['random_same_count_mean_link_recall']=statistics.fmean(baseline)
        ablations[name]=measured
    for i in range(args.repeats):random_rows.append({'repeat':i,**stats(rng.sample(events,len(chosen)),ref)})
    result={'experiment':'held-out evaluation of simplified filtering policy + graph-feature proxy anchors','train_event_end_utc':train_end,'test_first_selected_record_utc':test_start,'test_last_selected_record_utc':events[-1][1], 'test_file':str(input_path.relative_to(ROOT)),'test_parse_counts':dict(counts),'candidate_prefixes':len(prefixes),'observed_prefixes':len({e[0] for e in events}),'anchor_count':len(anchors),'drop_rules':len(drops),'full':full,'policy':g,'ablations':ablations,'retained_fraction':len(chosen)/len(events),'random_same_record_budget':{'repeats':args.repeats,'seed':args.seed,'mean_link_recall':statistics.fmean(x['link_recall'] for x in random_rows),'min_link_recall':min(x['link_recall'] for x in random_rows),'max_link_recall':max(x['link_recall'] for x in random_rows),'mean_prefixes':statistics.fmean(x['prefixes'] for x in random_rows),'mean_prefix_path_pairs':statistics.fmean(x['prefix_path_pairs'] for x in random_rows)},'elapsed_seconds':round(time.time()-start,2),'scope_and_limitations':'20 train-selected IPv4 prefixes; prefix-expanded IPv4 announcements with AS_SEQUENCE only, not all BGP UPDATEs. Random draws exactly same number of records but allows arbitrary message splitting and is not deployable VP-prefix filters. Link denominator is the same scoped held-out file, not global ground truth. Anchors are proxy features on truncated graphs; the original update component and anchors are approximate. No RIB or withdrawals in scoring, no MOAS/hijack inference.'}
    out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'random_runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=random_rows[0]);w.writeheader();w.writerows(random_rows)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
