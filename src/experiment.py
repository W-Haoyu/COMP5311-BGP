#!/usr/bin/env python3
"""Small, GILL-inspired VP selection experiment, not a GILL implementation."""
import argparse, collections, csv, json, random, time
from pathlib import Path
import mrtparse


def parse(path):
    peers = collections.defaultdict(lambda: {'updates': 0, 'links': set()})
    counts = collections.Counter()
    for entry in mrtparse.Reader(str(path)):
        if entry.err:
            counts['parse_errors'] += 1
            entry.err = 0
            continue
        d = entry.data
        msg = d.get('bgp_message', {})
        if 2 not in msg.get('type', {}):
            continue
        counts['update_messages'] += 1
        peer = str(d.get('peer_as')) + '@' + str(d.get('peer_ip'))
        peers[peer]['updates'] += 1
        attrs = msg.get('path_attributes', [])
        # Count only ordinary IPv4 announcements with an AS_SEQUENCE-only path.
        if not msg.get('nlri'):
            continue
        counts['ipv4_announcement_messages'] += 1
        paths = [a.get('value', []) for a in attrs if 2 in a.get('type', {})]
        if len(paths) != 1 or any(2 not in s.get('type', {}) for s in paths[0]):
            counts['excluded_missing_or_nonsequence_path'] += 1
            continue
        path_as = []
        for seg in paths[0]:
            for asn in seg.get('value', []):
                if not str(asn).isdigit():
                    continue
                if not path_as or path_as[-1] != str(asn):
                    path_as.append(str(asn))
        links = {tuple(sorted((a,b), key=int)) for a,b in zip(path_as, path_as[1:]) if a != b}
        peers[peer]['links'].update(links)
        counts['usable_ipv4_announcement_messages'] += 1
    return peers, counts


def select(train, eligible, budget):
    selected, covered = [], set()
    remaining = set(eligible)
    spent = 0
    while remaining:
        feasible = [p for p in remaining if spent + train[p]['updates'] <= budget]
        if not feasible: break
        # Gain per training update; deterministic tie break.
        best = min(feasible, key=lambda p: (-(len(train[p]['links'] - covered) / max(1,train[p]['updates'])), p))
        if not (train[best]['links'] - covered): break
        selected.append(best); covered |= train[best]['links']; spent += train[best]['updates']; remaining.remove(best)
    return selected


def evaluate(peers, selected, total_links, total_updates):
    links = set()
    for p in selected: links |= peers[p]['links']
    return {'vp_count': len(selected), 'update_count': sum(peers[p]['updates'] for p in selected), 'update_fraction': sum(peers[p]['updates'] for p in selected)/total_updates if total_updates else 0, 'links': len(links), 'link_coverage': len(links)/len(total_links) if total_links else 0}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',type=Path,default=Path('data')); ap.add_argument('--output',type=Path,default=Path('results')); ap.add_argument('--repeats',type=int,default=100); ap.add_argument('--seed',type=int,default=42); args=ap.parse_args()
    start=time.time(); train,tc=parse(args.data/'updates.20230901.0000.gz'); test,ec=parse(args.data/'updates.20230901.0010.gz')
    eligible=sorted(set(train)&set(test)); links=set().union(*(test[p]['links'] for p in test)); total_updates=sum(v['updates'] for v in test.values()); train_total=sum(train[p]['updates'] for p in eligible)
    args.output.mkdir(parents=True,exist_ok=True)
    summary={'train_counts':dict(tc),'test_counts':dict(ec),'train_vps':len(train),'test_vps':len(test),'common_vps':len(eligible),'test_reference_links_all_vps':len(links),'test_reference_updates_all_vps':total_updates,'seed':args.seed,'repeats':args.repeats,'description':'Selection uses training updates and links only. Test includes all VPs as reference; non-common VPs cannot be selected. Budgets are approximate on test because VP activity changes.'}
    rng=random.Random(args.seed); rows=[]; selections={}
    for frac in [0.05,0.1,0.2,0.4,0.6,0.8,1.0]:
        budget=train_total*frac; chosen=select(train,eligible,budget); selections[str(frac)]=chosen
        value=evaluate(test,chosen,links,total_updates); rows.append({'training_budget_fraction':frac,'method':'greedy_training_gain_per_update','repeat':0,**value})
        # Same training budget; random permutations packed under budget.
        for rep in range(args.repeats):
            order=eligible[:]; rng.shuffle(order); picked=[]; spent=0
            for p in order:
                n=train[p]['updates']
                if spent+n<=budget: picked.append(p); spent+=n
            rows.append({'training_budget_fraction':frac,'method':'random_vp','repeat':rep,**evaluate(test,picked,links,total_updates)})
    summary['elapsed_seconds']=round(time.time()-start,2)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    (args.output/'selected_vps.json').write_text(json.dumps(selections,indent=2)+'\n')
    with (args.output/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2)); print('Results:',args.output/'results.csv')
if __name__=='__main__': main()
